import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from auth.dependencies import get_current_user
from auth.rbac import has_permission
from models.database import User, ActionItem

logger = logging.getLogger("aios.routes.approve")
router = APIRouter()

class ApproveActionRequest(BaseModel):
    incident_id: str
    decision: str = "approve"  # approve or reject

@router.post("/action/{action_id}/approve")
async def approve_action(
    action_id: str,
    payload: ApproveActionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Approve or reject a recommended mitigation action, enforcing RBAC limits based on action risk level."""
    # 1. Fetch ActionItem from DB
    # IDs are stored as "{incident_id}_{step_id}" to avoid PK conflicts across incidents
    full_id = f"{payload.incident_id}_{action_id}"
    stmt = select(ActionItem).where(
        (ActionItem.id == full_id) &
        (ActionItem.incident_id == payload.incident_id)
    )
    res = await db.execute(stmt)
    action_item = res.scalars().first()
    
    if not action_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action item with ID {action_id} for incident {payload.incident_id} not found"
        )
        
    if action_item.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Action item is already in status '{action_item.status}'"
        )

    # 2. Enforce RBAC constraints based on risk level
    risk = action_item.risk_level.lower()
    
    if payload.decision == "approve":
        if risk in ["high", "critical"]:
            # Requires execute:high_risk
            if not has_permission(current_user.role, "execute:high_risk"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: High-risk actions require SRE Admin role."
                )
        else:
            # Low/medium risks require execute:low_risk
            if not has_permission(current_user.role, "execute:low_risk"):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: Operator role required to execute mitigation actions."
                )
                
        # 3. Simulate execution and update DB
        logger.info(f"User '{current_user.username}' APPROVED action: {action_item.action}")
        action_item.status = "executed"
        action_item.approved_by = current_user.username
        action_item.approved_at = datetime.now(timezone.utc)
        await db.commit()
        
        return {
            "message": f"Action {action_id} approved and executed successfully.",
            "action": action_item.action,
            "status": action_item.status,
            "operator": current_user.username,
            "timestamp": action_item.approved_at
        }
    else:
        # Reject action
        logger.info(f"User '{current_user.username}' REJECTED action: {action_item.action}")
        action_item.status = "rejected"
        action_item.approved_by = current_user.username
        action_item.approved_at = datetime.now(timezone.utc)
        await db.commit()
        
        return {
            "message": f"Action {action_id} was rejected by operator.",
            "action": action_item.action,
            "status": action_item.status,
            "operator": current_user.username,
            "timestamp": action_item.approved_at
        }
