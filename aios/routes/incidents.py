import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any

from database import get_db
from auth.dependencies import get_current_user
from models.database import User, Incident, AgentTrace, ActionItem

logger = logging.getLogger("aios.routes.incidents")
router = APIRouter()

@router.get("/incidents")
async def list_incidents(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    search: str = None,
    service_name: str = None,
    severity: str = None,
    status: str = None,
    limit: int = 20,
    offset: int = 0
):
    """Retrieve all logged incidents from the DB with optional filters (paginated)."""
    stmt = select(Incident)
    
    # Apply filters
    if service_name:
        stmt = stmt.where(Incident.service_name == service_name)
    if severity:
        stmt = stmt.where(Incident.severity == severity)
    if status:
        stmt = stmt.where(Incident.status == status)
        
    # Order by creation date descending
    stmt = stmt.order_by(Incident.created_at.desc()).limit(limit).offset(offset)
    
    res = await db.execute(stmt)
    incidents = res.scalars().all()

    if search:
        lowered = search.lower()
        incidents = [
            inc for inc in incidents
            if lowered in (inc.title or "").lower()
            or lowered in (inc.service_name or "").lower()
            or lowered in (inc.engineer_view or "").lower()
            or lowered in (inc.executive_view or "").lower()
            or lowered in (inc.actual_root_cause or "").lower()
        ]
    
    # Return as list
    data = []
    for inc in incidents:
        data.append({
            "id": inc.id,
            "title": inc.title,
            "service_name": inc.service_name,
            "severity": inc.severity,
            "status": inc.status,
            "created_at": inc.created_at,
            "resolved_at": inc.resolved_at,
            "pipeline_duration_ms": inc.pipeline_duration_ms,
            "accuracy_score": inc.accuracy_score
        })
    return data

@router.get("/incident/{incident_id}")
async def get_incident(
    incident_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve details, agent execution traces, and mitigation action gates for a single incident."""
    stmt = select(Incident).where(Incident.id == incident_id).options(
        selectinload(Incident.traces),
        selectinload(Incident.actions)
    )
    
    res = await db.execute(stmt)
    inc = res.scalars().first()
    
    if not inc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident with ID {incident_id} not found"
        )
        
    # Construct response payload
    traces_payload = []
    for t in inc.traces:
        traces_payload.append({
            "agent_name": t.agent_name,
            "status": t.status,
            "model_used": t.model_used,
            "duration_ms": t.duration_ms,
            "tokens_used": t.tokens_used,
            "input_summary": t.input_summary,
            "output_summary": t.output_summary,
            "error_message": t.error_message,
            "started_at": t.started_at
        })
        
    actions_payload = []
    for a in inc.actions:
        # step_id is the original step identifier (e.g. "step_1") — strip the incident_id prefix
        step_id = a.id[len(inc.id) + 1:] if a.id.startswith(inc.id + "_") else a.id
        actions_payload.append({
            "id": a.id,
            "step_id": step_id,
            "action": a.action,
            "risk_tag": a.risk_tag,
            "risk_level": a.risk_level,
            "rationale": a.rationale,
            "verification_check": a.verification_check,
            "status": a.status,
            "approved_by": a.approved_by,
            "approved_at": a.approved_at
        })

    return {
        "id": inc.id,
        "title": inc.title,
        "service_name": inc.service_name,
        "severity": inc.severity,
        "status": inc.status,
        "raw_alert": inc.raw_alert,
        "incident_packet": inc.incident_packet,
        "hypotheses": inc.hypotheses,
        "risk_assessment": inc.risk_assessment,
        "action_plan": inc.action_plan,
        "engineer_view": inc.engineer_view,
        "executive_view": inc.executive_view,
        "evidence_bundle": inc.evidence_bundle,
        "operational_context": inc.operational_context,
        "web_search_results": inc.web_search_results,
        "reviewer_verdict": inc.reviewer_verdict,
        "reviewer_confidence_delta": inc.reviewer_confidence_delta,
        "review_cycles": inc.review_cycles,
        "actual_root_cause": inc.actual_root_cause,
        "accuracy_score": inc.accuracy_score,
        "resolved_by": inc.resolved_by,
        "pipeline_duration_ms": inc.pipeline_duration_ms,
        "total_tokens": inc.total_tokens,
        "created_at": inc.created_at,
        "resolved_at": inc.resolved_at,
        "traces": traces_payload,
        "actions": actions_payload
    }
