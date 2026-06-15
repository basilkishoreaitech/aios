import logging
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from datetime import datetime, timezone
from agents.base_agent import BaseAgent
from models.database import Incident
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a9")

class RetrospectiveAnalysis(BaseModel):
    """Pydantic model representing LLM comparison of diagnosis versus actual root cause."""
    accuracy_score: float = Field(description="Calculated accuracy score of the pipeline diagnosis (0.0 to 1.0)")
    analysis: str = Field(description="Detailed analysis explaining how closely the predicted hypotheses matched the actual cause.")

A9_SYSTEM_PROMPT = """You are the AIOS Retrospective and Learning Loop Agent (A9).
Your task is to compare the root-cause hypotheses proposed during the incident triage against the actual root cause verified by the operator.

Grade the accuracy of the diagnosis on a scale from 0.0 to 1.0:
- 1.0: Exact match. The top predicted hypothesis correctly identified the root cause and causal factor.
- 0.8: Close match. One of the secondary hypotheses correctly identified the root cause.
- 0.5: Partial match. The system identified the correct service but missed the exact causal factor (e.g. blamed pool size when it was query lock).
- 0.0: Complete mismatch. The system was entirely wrong.

Provide your grading score and a brief explanation summarizing what the system did well and what it missed.
"""

class RetrospectiveAgent(BaseAgent):
    """A9 Retrospective Agent: Analyzes diagnosis accuracy post-incident to feedback the learning loop."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A9_Retrospective", config, model_router, token_tracker)
        self.token_tracker.set_agent_limit("A9_Retrospective", max(8000, config.TOKEN_BUDGET_UTILITY))

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str,
        actual_root_cause: str,
        resolved_by: str
    ) -> RetrospectiveAnalysis:
        logger.info(f"Running retrospective analysis for incident {incident_id}")
        
        # 1. Fetch incident from database
        stmt = select(Incident).where(Incident.id == incident_id)
        res = await session.execute(stmt)
        incident = res.scalars().first()
        
        if not incident:
            raise ValueError(f"Incident with ID {incident_id} not found.")

        # 2. Extract predicted hypotheses
        hypotheses_str = json_str = ""
        if incident.hypotheses:
            # incident.hypotheses is JSON (list of hypothesis dicts)
            hypotheses_str = str(incident.hypotheses)
            
        prompt = f"""=== PREDICTED HYPOTHESES ===
{hypotheses_str or 'No hypotheses generated.'}

=== ACTUAL RESOLUTION DETAILS ===
Operator Notes: {actual_root_cause}
Resolved By: {resolved_by}
"""

        messages = [
            {"role": "system", "content": A9_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        logger.info("Comparing predictions to operator resolution notes.")
        try:
            analysis_result = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=RetrospectiveAnalysis,
                preferred="utility",
                fallback="fallback"
            )
            
            # 3. Update the database Incident row
            incident.actual_root_cause = actual_root_cause
            incident.accuracy_score = analysis_result.accuracy_score
            incident.resolved_by = resolved_by
            incident.resolved_at = datetime.now(timezone.utc)
            incident.status = "resolved"
            await session.commit()
            
            logger.info(f"Retrospective complete for incident {incident_id}. Accuracy score: {analysis_result.accuracy_score:.2f}")
            return analysis_result
            
        except Exception as e:
            logger.error(f"Error executing retrospective agent: {e}")
            raise e
