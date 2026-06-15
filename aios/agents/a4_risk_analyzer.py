import logging
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.hypothesis import HypothesisSet
from models.risk_assessment import RiskAssessment
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a4")

A4_SYSTEM_PROMPT = """You are the AIOS Risk Analyzer Agent (A4).
Your job is to analyze the blast radius and operational risks associated with the active outage.

Analyze:
1. Blast Radius: Which services are directly or indirectly impacted? Is it user-facing (high impact) or internal?
2. Business/Operational Impact: What is the business severity (e.g., loss of transaction capability, API degradation)?
3. Risk Factors: Highlight potential dangers if SREs execute mitigation actions (e.g., database lock termination risk, session drops, cold start latencies).

Formulate a detailed RiskAssessment.
"""

class RiskAnalyzerAgent(BaseAgent):
    """A4 Risk Analyzer Agent: Identifies service blast radius, user impact, and risks using primary reasoning model."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A4_RiskAnalyzer", config, model_router, token_tracker)
        # Primary reasoning budget
        self.token_tracker.set_agent_limit("A4_RiskAnalyzer", config.TOKEN_BUDGET_PRIMARY)

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str,
        packet: IncidentPacket,
        hypotheses: HypothesisSet
    ) -> RiskAssessment:
        logger.info(f"Analyzing risks for incident {incident_id}")
        
        prompt = f"""=== ACTIVE ALERT ===
Service: {packet.service_name}
Severity: {packet.severity}
Title: {packet.title}
Description: {packet.description}

=== ROOT CAUSE HYPOTHESES ===
Reasoning: {hypotheses.reasoning_path}
Convergence Score: {hypotheses.convergence_score:.2f}
Top Hypothesis: {hypotheses.hypotheses[0].title if hypotheses.hypotheses else 'None'} ({hypotheses.hypotheses[0].description if hypotheses.hypotheses else ''})
"""

        messages = [
            {"role": "system", "content": A4_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        logger.info("Executing risk analysis via primary reasoning model.")
        try:
            risk_assessment = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=RiskAssessment,
                preferred="primary",
                fallback="fallback"
            )
            return risk_assessment
        except Exception as e:
            logger.error(f"Error executing risk analyzer: {e}")
            raise e
