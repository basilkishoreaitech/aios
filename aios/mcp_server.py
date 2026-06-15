import asyncio
from datetime import datetime, timezone
from mcp.server.fastmcp import FastMCP
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal
from models.database import Incident, ActionItem, KBDocument

mcp = FastMCP("AIOS-Operations")

@mcp.tool()
async def list_active_incidents() -> str:
    """List all currently active/unresolved SRE outages in AIOS."""
    async with AsyncSessionLocal() as session:
        stmt = select(Incident).where(Incident.status != "resolved")
        res = await session.execute(stmt)
        incidents = res.scalars().all()
        
        if not incidents:
            return "No active incidents found in database. Systems healthy."
            
        output = "ACTIVE AIOS INCIDENTS:\n"
        for inc in incidents:
            output += f"- [{inc.severity}] Incident ID: {inc.id} | Title: {inc.title} | Service: {inc.service_name} | Status: {inc.status}\n"
        return output

@mcp.tool()
async def get_incident_reasoning(incident_id: str) -> str:
    """Get the full AI hypotheses, risk assessment, and SRE logs for an incident."""
    async with AsyncSessionLocal() as session:
        stmt = select(Incident).where(Incident.id == incident_id)
        res = await session.execute(stmt)
        inc = res.scalars().first()
        
        if not inc:
            return f"Incident {incident_id} not found."
            
        output = f"INCIDENT REASONING REPORT (ID: {inc.id})\n"
        output += f"Title: {inc.title}\n"
        output += f"Service: {inc.service_name} | Severity: {inc.severity}\n"
        output += f"Reviewer Verdict: {inc.reviewer_verdict or 'N/A'}\n"
        output += "\n--- TOP ROOT CAUSE HYPOTHESES ---\n"
        
        if inc.hypotheses:
            hyps = inc.hypotheses.get("hypotheses", [])
            for h in hyps:
                output += f"- {h.get('title')} (Confidence: {h.get('confidence')}): {h.get('description')}\n"
        else:
            output += "No hypotheses generated yet.\n"
            
        output += "\n--- ENGINEER ANALYSIS VIEW ---\n"
        output += inc.engineer_view or "No technical logs generated."
        
        return output

@mcp.tool()
async def approve_action_gate(incident_id: str, action_id: str, operator_name: str) -> str:
    """Execute a recommended remediation command through the safety approval gate."""
    async with AsyncSessionLocal() as session:
        stmt = select(ActionItem).where(
            (ActionItem.id == action_id) & 
            (ActionItem.incident_id == incident_id)
        )
        res = await session.execute(stmt)
        action_item = res.scalars().first()
        
        if not action_item:
            return f"Error: Action {action_id} not found for incident {incident_id}."
            
        if action_item.status != "pending":
            return f"Warning: Action {action_id} is already in status '{action_item.status}'."
            
        # Execute action (simulate)
        action_item.status = "executed"
        action_item.approved_by = f"MCP:{operator_name}"
        action_item.approved_at = datetime.now(timezone.utc)
        await session.commit()
        
        return f"Success: Action {action_id} ('{action_item.action}') approved via MCP and executed by {operator_name}."

if __name__ == "__main__":
    mcp.run()
