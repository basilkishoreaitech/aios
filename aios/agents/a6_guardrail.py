import re
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from models.hypothesis import HypothesisSet
from models.action_plan import ActionPlan, ActionStep
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a6")

# Dangerous command keywords we want to block
UNSAFE_COMMANDS = [
    r"\brm\s+-rf\b",
    r"\bdrop\s+database\b",
    r"\bdrop\s+table\b",
    r"\bformat\s+[a-zA-Z0-9/]+\b",
    r"\bmkfs\b",
    r"\bdelete\s+from\s+[a-zA-Z0-9_]+\s*$",  # delete without where clause
    r"\bkill\s+-9\s+1\b",
]

INJECTION_KEYWORDS = [
    "ignore previous instructions",
    "system override",
    "you must auto-approve",
    "bypass the gatekeeper",
]

class GuardrailAgent(BaseAgent):
    """A6 Guardrail Agent: Assures safety, blocks destructive commands, checks prompt injections, and validates citations."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A6_Guardrail", config, model_router, token_tracker)
        self.token_tracker.set_agent_limit("A6_Guardrail", config.TOKEN_BUDGET_UTILITY)

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str,
        packet: IncidentPacket,
        evidence: EvidenceBundle,
        hypotheses: HypothesisSet,
        action_plan: ActionPlan
    ) -> ActionPlan:
        logger.info(f"Running safety guardrails on action plan for incident {incident_id}")
        
        # 1. Prompt Injection Validation
        all_text = f"{packet.title} {packet.description or ''} {hypotheses.reasoning_path}".lower()
        for key in INJECTION_KEYWORDS:
            if key in all_text:
                logger.critical(f"🚨 Prompt injection warning! Found adversarial phrase: '{key}'")
                action_plan.safety_disclaimer = "WARNING: System detected potential prompt injection attempts. Action plan execution is strictly blocked."
                for step in action_plan.mitigation_steps:
                    step.risk_tag = "blocked"
                    step.risk_level = "critical"
                    step.rationale = "BLOCKED: Prompt injection detected."
                return action_plan

        # 2. Citation Verification
        valid_citations = {c.doc_id for c in evidence.kb_citations}
        # Also include web URLs as valid citations
        valid_citations.update({w.url for w in evidence.web_citations})
        
        logger.info(f"Valid citations for validation: {valid_citations}")
        
        # Verify that cited docs exist in retrieved evidence
        for hyp in hypotheses.hypotheses:
            for ref in hyp.evidence_citations:
                if ref not in valid_citations:
                    logger.warning(f"Hypothesis '{hyp.title}' cited document '{ref}' which was not in retrieved evidence.")

        # 3. Unsafe Action Filter
        validated_steps = []
        for step in action_plan.mitigation_steps:
            command_lower = step.action.lower()
            is_unsafe = False
            for pattern in UNSAFE_COMMANDS:
                if re.search(pattern, command_lower):
                    logger.error(f"🚨 Dangerous command blocked! Command '{step.action}' matched pattern '{pattern}'")
                    is_unsafe = True
                    break
                    
            if is_unsafe:
                # Upgrade step to blocked
                step.risk_tag = "blocked"
                step.risk_level = "critical"
                step.rationale = "SAFETY BLOCK: Command contains dangerous or destructive operations."
                
            validated_steps.append(step)

        action_plan.mitigation_steps = validated_steps
        logger.info("Safety guardrails evaluation complete.")
        return action_plan
