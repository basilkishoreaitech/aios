import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from models.database import Incident, ActionItem
from services.query_service import QueryService
from services.model_router import ModelRouter
from services.embedding_service import EmbeddingService
from services.web_search_service import WebSearchService

logger = logging.getLogger("aios.routes.teams")
router = APIRouter()

class TeamsWebhookPayload(BaseModel):
    """Represent callback payload sent by Teams channels or Adaptive Cards action buttons."""
    text: Optional[str] = None
    user: str = "Teams SRE"
    role: str = "operator"
    action: Optional[str] = None  # e.g., 'approve' or 'reject'
    incident_id: Optional[str] = None
    action_id: Optional[str] = None

@router.post("/messages")
async def teams_callback(
    payload: TeamsWebhookPayload,
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Callback endpoint for Teams Chatbot questions and Adaptive Card approvals."""
    logger.info(f"Teams Webhook triggered by user '{payload.user}' (Role: {payload.role})")
    
    # Check if this is an Adaptive Card action (Approve/Reject)
    if payload.action and payload.incident_id and payload.action_id:
        # Check action in DB
        stmt = select(ActionItem).where(
            (ActionItem.id == payload.action_id) & 
            (ActionItem.incident_id == payload.incident_id)
        )
        res = await db.execute(stmt)
        action_item = res.scalars().first()
        
        if not action_item:
            return {
                "text": f"❌ Action item {payload.action_id} not found."
            }
            
        if action_item.status != "pending":
            return {
                "text": f"⚠️ Action item is already in status '{action_item.status}'."
            }
            
        # Role checking (RBAC)
        if payload.action == "approve":
            if action_item.risk_level.lower() in ["high", "critical"] and payload.role != "admin":
                return {
                    "text": f"❌ SRE Operator '{payload.user}' is unauthorized to execute High-Risk actions. SRE Admin role is required."
                }
                
            action_item.status = "executed"
            action_item.approved_by = payload.user
            action_item.approved_at = datetime.now(timezone.utc)
            await db.commit()
            return {
                "text": f"✅ **Mitigation Executed**: Action `{action_item.action}` was approved by **{payload.user}** and executed successfully."
            }
        else:
            action_item.status = "rejected"
            action_item.approved_by = payload.user
            action_item.approved_at = datetime.now(timezone.utc)
            await db.commit()
            return {
                "text": f"❌ **Mitigation Rejected**: Action `{action_item.action}` was rejected by **{payload.user}**."
            }
            
    # Check if it is a natural language question (Mode B query)
    if payload.text:
        question = payload.text.replace("@AIOS", "").strip()
        logger.info(f"Teams Chatbot query: '{question}'")
        
        # Instantiate query service
        query_service = QueryService(
            embedding_service=request.app.state.embedding_service,
            web_search_service=request.app.state.web_search_service,
            model_router=request.app.state.model_router
        )
        
        from models.query import QueryRequest
        query_req = QueryRequest(question=question)
        
        try:
            res = await query_service.run_query(db, query_req)
            
            # Format answers as a markdown Teams message card
            msg = f"### 💬 AIOS Chatbot Answer\n{res.answer}\n\n"
            if res.citations:
                msg += "**📄 Citations:**\n"
                for c in res.citations[:3]:
                    msg += f"- [{c.title}] Category: {c.category} (Score: {c.relevance * 100:.1f}%)\n"
            return {
                "text": msg
            }
        except Exception as e:
            logger.error(f"Error executing Teams query: {e}")
            return {
                "text": f"❌ Error processing query: {str(e)}"
            }

    return {
        "text": "⚠️ Teams webhook payload unhandled. Ensure 'text' or 'action' parameters are provided."
    }
