import logging
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from models.hypothesis import HypothesisSet
from models.risk_assessment import RiskAssessment
from models.action_plan import ActionPlan
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a5")

A5_SYSTEM_PROMPT = """You are the AIOS Action Planner Agent (A5).
Your job is to generate a prioritized, staged, and safety-gated ActionPlan to mitigate the active outage.

Follow these strict rules when defining ActionSteps:
1. Each step must contain:
   - id: Unique string identifier (e.g. 'step_1', 'step_2').
   - action: Action description or exact CLI command (e.g. `kubectl rollout restart deployment api-gateway`).
   - risk_level: 'low', 'medium', 'high', or 'critical'.
   - risk_tag:
     - 'auto_approve': For low-risk, non-destructive steps.
     - 'approval_required': For medium/high risk steps (e.g., restarts, terminating database backend processes).
     - 'blocked': For critical risk or unsafe steps (e.g., deleting volumes).
   - rationale: Technical reason why this step helps.
   - verification_check: How to check if this step succeeded (e.g. `curl https://api-gateway/health`).
2. Order steps logically (Immediate relief -> Verification -> Long-term mitigation).
"""

class ActionPlannerAgent(BaseAgent):
    """A5 Action Planner Agent: Generates staged, risk-tagged remediation commands using primary reasoning model."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A5_ActionPlanner", config, model_router, token_tracker)
        # Primary reasoning budget
        self.token_tracker.set_agent_limit("A5_ActionPlanner", config.TOKEN_BUDGET_PRIMARY)

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str,
        packet: IncidentPacket,
        evidence: EvidenceBundle,
        hypotheses: HypothesisSet,
        risks: RiskAssessment
    ) -> ActionPlan:
        logger.info(f"Generating mitigation action plan for incident {incident_id}")

        # Build grounded KB evidence block — include content snippets so the LLM can read actual runbook steps
        kb_evidence_lines = []
        for i, c in enumerate(evidence.kb_citations, 1):
            kb_evidence_lines.append(
                f"[{i}] {c.title} (category: {c.category}, relevance: {c.relevance:.2f})\n"
                f"{c.content_snippet or '(no content)'}"
            )
        kb_evidence_block = "\n\n".join(kb_evidence_lines) if kb_evidence_lines else "No KB documents retrieved."

        # Build web citation block
        web_evidence_lines = []
        for i, w in enumerate(evidence.web_citations, 1):
            snippet = getattr(w, "snippet", "") or ""
            web_evidence_lines.append(f"[W{i}] {w.title} ({w.url})\n{snippet[:500]}")
        web_evidence_block = "\n\n".join(web_evidence_lines) if web_evidence_lines else "No web search results."

        # All hypotheses + reasoning path
        hyp_lines = []
        for h in hypotheses.hypotheses:
            hyp_lines.append(
                f"- [{h.confidence:.0%}] {h.title}: {h.description} (causal_factor: {h.causal_factor})"
            )
        hyp_block = "\n".join(hyp_lines) if hyp_lines else "No hypotheses."

        prompt = f"""=== ACTIVE ALERT ===
Service: {packet.service_name}
Severity: {packet.severity}
Title: {packet.title}
Description: {packet.description or 'N/A'}
Metrics: {packet.metrics}

=== ROOT CAUSE ANALYSIS ===
Reasoning Path: {hypotheses.reasoning_path}
Hypotheses:
{hyp_block}

=== RISK ASSESSMENT ===
Overall Risk Tier: {risks.overall_risk_level}
Blast Radius: {', '.join(risks.blast_radius.impacted_services)}
Business Impact: {risks.business_impact_summary}
Mitigation Risk Factors: {', '.join(risks.mitigation_risk_factors)}

=== KNOWLEDGE BASE RUNBOOKS / PLAYBOOKS ===
{kb_evidence_block}

=== WEB SEARCH RESULTS ===
{web_evidence_block}

Use the KB runbooks and web results above to generate specific, grounded remediation steps — not generic templates.
Reference exact commands from the runbooks where available."""

        messages = [
            {"role": "system", "content": A5_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        logger.info("Executing action planning via primary reasoning model.")
        try:
            action_plan = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=ActionPlan,
                preferred="primary",
                fallback="fallback"
            )
            return action_plan
        except Exception as e:
            logger.error(f"Error executing action planner: {e}")
            raise e
