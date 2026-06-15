import logging
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from auth.dependencies import get_current_user
from models.database import User, Incident
from agents.a9_retrospective import RetrospectiveAgent
from agents.a10_knowledge_ingest import KnowledgeIngestAgent
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.routes.retrospective")
router = APIRouter()

class ResolveIncidentRequest(BaseModel):
    actual_root_cause: str

@router.post("/incident/{incident_id}/resolve")
async def resolve_incident(
    incident_id: str,
    payload: ResolveIncidentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Mark an incident resolved, running retrospective accuracy analysis (A9) and knowledge ingestion (A10)."""
    # 1. Verify incident exists
    stmt = select(Incident).where(Incident.id == incident_id)
    res = await db.execute(stmt)
    incident = res.scalars().first()
    
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found."
        )
        
    if incident.status == "resolved":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incident is already resolved."
        )

    logger.info(f"Resolving incident {incident_id}. Triggering retrospective and ingestion loop...")

    # Load lifespanned services
    model_router = request.app.state.model_router
    embedding_service = request.app.state.embedding_service
    pipeline = request.app.state.pipeline

    # Fresh tracker — resolve runs after the pipeline has consumed its budget,
    # so reusing pipeline.token_tracker would trip A9/A10 per-agent limits.
    resolve_tracker = TokenBudgetTracker(global_limit=100000)

    # 2. Instantiate and run A9 Retrospective Agent
    a9_agent = RetrospectiveAgent(
        config=pipeline.config,
        model_router=model_router,
        token_tracker=resolve_tracker
    )
    
    try:
        retrospective_analysis = await a9_agent.execute(
            session=db,
            incident_id=incident_id,
            actual_root_cause=payload.actual_root_cause,
            resolved_by=current_user.username
        )
        
        # 3. Instantiate and run A10 Knowledge Ingestion Agent
        a10_agent = KnowledgeIngestAgent(
            config=pipeline.config,
            model_router=model_router,
            token_tracker=resolve_tracker,
            embedding_service=embedding_service
        )
        
        new_postmortem_id = await a10_agent.execute(
            session=db,
            incident_id=incident_id
        )
        
        return {
            "message": f"Incident {incident_id} resolved successfully.",
            "status": "resolved",
            "accuracy_score": retrospective_analysis.accuracy_score,
            "analysis": retrospective_analysis.analysis,
            "ingested_postmortem_id": new_postmortem_id
        }
    except Exception as e:
        logger.error(f"Error executing retrospective/ingest pipeline for incident {incident_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Incident resolved but learning loop failed: {str(e)}"
        )


@router.post("/incident/{incident_id}/retry-learning-loop")
async def retry_learning_loop(
    incident_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Re-run A9 (accuracy scoring) + A10 (KB ingestion) for an already-resolved incident.

    Safe to call multiple times — both agents are idempotent.  Useful when a
    transient OpenAI / DB error caused the learning loop to fail on first resolve.
    """
    stmt = select(Incident).where(Incident.id == incident_id)
    res = await db.execute(stmt)
    incident = res.scalars().first()

    if not incident:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Incident {incident_id} not found.")

    if incident.status != "resolved":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Incident must already be resolved before retrying the learning loop.")

    if not incident.actual_root_cause:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="No actual_root_cause stored — use the Resolve endpoint first.")

    model_router = request.app.state.model_router
    embedding_service = request.app.state.embedding_service
    pipeline = request.app.state.pipeline

    # Fresh tracker so accumulated pipeline tokens don't trip the per-agent budget
    retry_tracker = TokenBudgetTracker(global_limit=100000)

    a9_agent = RetrospectiveAgent(
        config=pipeline.config,
        model_router=model_router,
        token_tracker=retry_tracker
    )

    try:
        retrospective_analysis = await a9_agent.execute(
            session=db,
            incident_id=incident_id,
            actual_root_cause=incident.actual_root_cause,
            resolved_by=current_user.username
        )

        a10_agent = KnowledgeIngestAgent(
            config=pipeline.config,
            model_router=model_router,
            token_tracker=retry_tracker,
            embedding_service=embedding_service
        )

        new_postmortem_id = await a10_agent.execute(
            session=db,
            incident_id=incident_id
        )

        return {
            "message": f"Learning loop re-run successfully for incident {incident_id}.",
            "accuracy_score": retrospective_analysis.accuracy_score,
            "analysis": retrospective_analysis.analysis,
            "ingested_postmortem_id": new_postmortem_id
        }

    except Exception as e:
        logger.error(f"Retry learning loop failed for incident {incident_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Retry failed: {str(e)}"
        )
