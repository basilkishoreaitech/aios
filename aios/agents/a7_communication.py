import logging
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from models.hypothesis import HypothesisSet
from models.risk_assessment import RiskAssessment
from models.action_plan import ActionPlan
from models.operational_context import OperationalContext
from models.communication import CommunicationBundle
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a7")

A7_SYSTEM_PROMPT = """You are the AIOS Communication Agent (A7).
Your job is to format the incident analysis, findings, and remediation steps for two distinct audiences:

1. Engineer View: Clear, technical, structured SRE logs, event timeline, and troubleshooting CLI commands.
2. Executive View: Non-technical summary, business/financial/customer impact, who is responding (oncall SREs), and Estimated Time to Resolution (TTR).

Generate a CommunicationBundle. Ensure the notification_text is a brief one-liner suitable for a Microsoft Teams notification.
"""

class CommunicationAgent(BaseAgent):
    """A7 Communication Agent: Generates distinct Engineer-focused and Executive-focused summaries."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A7_Communication", config, model_router, token_tracker)
        self.token_tracker.set_agent_limit("A7_Communication", config.TOKEN_BUDGET_UTILITY)

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str,
        packet: IncidentPacket,
        evidence: EvidenceBundle,
        hypotheses: HypothesisSet,
        risks: RiskAssessment,
        action_plan: ActionPlan,
        context: OperationalContext
    ) -> CommunicationBundle:
        logger.info(f"Generating communication logs for incident {incident_id}")
        
        # Format names of SREs
        oncall_names = ", ".join([eng.name for eng in context.oncall_roster]) or "On-Call Pool"
        
        prompt = f"""=== INCIDENT INFO ===
ID: {incident_id}
Title: {packet.title}
Service: {packet.service_name}
Severity: {packet.severity}
Description: {packet.description}

=== ROOT CAUSE HYPOTHESIS ===
Top Causal Factor: {hypotheses.hypotheses[0].causal_factor if hypotheses.hypotheses else 'Unknown'}
Reasoning: {hypotheses.reasoning_path}

=== RISK & IMPACT ===
Overall Risk: {risks.overall_risk_level}
Blast Radius Services: {', '.join(risks.blast_radius.impacted_services)}
Business Impact: {risks.business_impact_summary}

=== RECOMMENDED REMEDIATION ===
Staged Actions:
{chr(10).join([f'- [{step.risk_level}] {step.action} (Verification: {step.verification_check})' for step in action_plan.mitigation_steps])}

=== ON-CALL ENGINEERS ===
{oncall_names}
"""

        messages = [
            {"role": "system", "content": A7_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        logger.info("Executing communication format generation.")
        try:
            # Preferred: low-cost reviewer deployment, fallback: utility deployment
            bundle = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=CommunicationBundle,
                preferred="fallback",
                fallback="utility"
            )
            return bundle
        except Exception as e:
            logger.error(f"Error executing communication agent: {e}")
            raise e
