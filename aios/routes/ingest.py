import json
import uuid
import logging
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from sqlalchemy.ext.asyncio import AsyncSession
from slowapi import Limiter
from slowapi.util import get_remote_address

from database import get_db
from auth.dependencies import get_current_user
from models.database import User

logger = logging.getLogger("aios.routes.ingest")
router = APIRouter()

# Shared limiter instance (wired to app.state.limiter in main.py)
_limiter = Limiter(key_func=get_remote_address)

class AlertIngestRequest(BaseModel):
    """Payload format for alert ingestion."""
    raw_alert: str

@router.post("/ingest")
@_limiter.limit("10/minute")
async def ingest_alert(
    request: Request,
    payload: AlertIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ingest a raw alert, initiate the 11-agent pipeline, and stream execution progress (SSE).
    Rate limited to 10 requests/minute per IP to prevent runaway pipeline invocations.
    """
    incident_id = str(uuid.uuid4())
    logger.info(f"Incoming alert. Initializing pipeline execution under incident {incident_id}")

    pipeline = request.app.state.pipeline

    async def event_generator():
        try:
            # We must run the streaming generator from pipeline
            async for event in pipeline.run_pipeline_streaming(
                session=db,
                raw_alert=payload.raw_alert,
                incident_id=incident_id
            ):
                # Format for SSE
                yield {
                    "event": event["event"],
                    "data": event["data"]
                }
        except Exception as e:
            logger.error(f"Error streaming incident pipeline {incident_id}: {e}", exc_info=True)
            yield {
                "event": "pipeline_error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())


class HintIngestRequest(BaseModel):
    """Payload format for operator hint injection."""
    operator_hint: str


@router.post("/incident/{incident_id}/hint")
async def ingest_hint(
    incident_id: str,
    request: Request,
    payload: HintIngestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Ingest an operator hint for an existing incident, and rerun the pipeline streaming (SSE)."""
    from models.database import Incident
    from sqlalchemy.future import select

    # Load the existing incident to get its raw alert
    stmt = select(Incident).where(Incident.id == incident_id)
    res = await db.execute(stmt)
    incident = res.scalars().first()

    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )

    logger.info(f"Incoming operator hint for incident {incident_id}. Rerunning pipeline.")
    pipeline = request.app.state.pipeline

    async def event_generator():
        try:
            async for event in pipeline.run_pipeline_streaming(
                session=db,
                raw_alert=incident.raw_alert,
                incident_id=incident_id,
                operator_hint=payload.operator_hint
            ):
                yield {
                    "event": event["event"],
                    "data": event["data"]
                }
        except Exception as e:
            logger.error(f"Error streaming incident pipeline hint {incident_id}: {e}", exc_info=True)
            yield {
                "event": "pipeline_error",
                "data": json.dumps({"error": str(e)})
            }

    return EventSourceResponse(event_generator())

