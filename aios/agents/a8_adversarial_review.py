import logging
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from models.hypothesis import HypothesisSet
from models.operational_context import OperationalContext
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a8")

class ReviewerVerdict(BaseModel):
    """Pydantic model representing the adversarial reviewer's verdict."""
    verdict: str = Field(description="Adversarial evaluation verdict: 'approved' or 'challenged'")
    confidence_delta: float = Field(description="Delta change applied to confidence. Negative if challenged (e.g., -0.15), positive if approved (e.g., +0.05).")
    critique: str = Field(description="Detailed critique, identifying gaps in correlation, missing links, or confirming validity.")

A8_SYSTEM_PROMPT = """You are the AIOS Adversarial Reviewer and Critic Agent (A8).
Your role is to critically analyze the root-cause hypotheses proposed by the Correlation Agent (A3) using an independent low-cost reviewer model.

You must be highly skeptical. Look for the following pitfalls:
1. Jumping to conclusions: Did A3 blame the deployment just because it happened recently, without confirming that the error symptoms (e.g., memory usage or DB queries) relate to the code changes?
2. Hallucinating correlation: Is A3 citing runbooks that are unrelated to the actual error metrics?
3. Missing external indicators: Did A3 ignore an obvious Stripe API outage mentioned in Teams or web search?

Provide a verdict:
- 'challenged': If you find logical flaws, lack of evidence convergence, or contradictory signals. Assign a negative confidence_delta (e.g., -0.15).
- 'approved': If the hypotheses are logically sound, grounded in runbooks/postmortems, and supported by operational timelines. Assign a positive confidence_delta (e.g., +0.05).

Give detailed, actionable SRE critique explaining your reasoning.
"""

class AdversarialReviewAgent(BaseAgent):
    """A8 Adversarial Review Agent: challenges or approves the Correlation Agent's hypotheses."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A8_AdversarialReview", config, model_router, token_tracker)
        self.token_tracker.set_agent_limit("A8_AdversarialReview", config.TOKEN_BUDGET_UTILITY)

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str,
        packet: IncidentPacket,
        evidence: EvidenceBundle,
        context: OperationalContext,
        hypotheses: HypothesisSet
    ) -> ReviewerVerdict:
        logger.info(f"Reviewing hypotheses for incident {incident_id}")
        
        # Build KB citations block so A8 can verify whether cited docs are actually relevant
        kb_lines = [
            f"- [{c.relevance:.2f}] {c.title} (category: {c.category}, doc_id: {c.doc_id})"
            for c in evidence.kb_citations
        ]
        kb_block = "\n".join(kb_lines) if kb_lines else "No KB documents retrieved."

        web_lines = [f"- {w.title} ({w.url})" for w in evidence.web_citations]
        web_block = "\n".join(web_lines) if web_lines else "No web results."

        prompt = f"""=== ACTIVE ALERT ===
Service: {packet.service_name}
Title: {packet.title}
Severity: {packet.severity}
Description: {packet.description}

=== ROOT CAUSE HYPOTHESES ===
Reasoning Path: {hypotheses.reasoning_path}
Convergence Score: {hypotheses.convergence_score:.2f}
Proposed Hypotheses:
{chr(10).join([f'- {h.title} (Confidence: {h.confidence:.2f}) -> {h.description}' for h in hypotheses.hypotheses])}

=== OPERATIONAL CONTEXT ===
Deployments: {len(context.deployments)}
Teams Messages: {len(context.teams_messages)}

=== RETRIEVED KB EVIDENCE (verify citation relevance) ===
{kb_block}

=== WEB SEARCH EVIDENCE ===
{web_block}

Critically check: Do the KB citations match the actual error type? Are the hypotheses grounded in the cited documents?"""

        messages = [
            {"role": "system", "content": A8_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        logger.info("Executing adversarial review via verification model.")
        try:
            # Critic runs on gpt-4.1 — a deliberately different model family from the gpt-5.4 primary
            verdict = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=ReviewerVerdict,
                preferred="critic",
                fallback="utility"
            )
            return verdict
        except Exception as e:
            logger.error(f"Error executing reviewer agent: {e}")
            raise e
