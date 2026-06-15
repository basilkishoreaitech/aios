import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from database import get_db
from auth.dependencies import get_current_user
from models.database import User, ServiceTopology, Incident

logger = logging.getLogger("aios.routes.topology")
router = APIRouter()

@router.get("/topology")
async def get_topology(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Retrieve service nodes and links for dynamic SVG dependency rendering, correlating active incidents to state."""
    logger.info("Fetching service topology graph metadata...")
    
    # 1. Fetch links from database
    stmt = select(ServiceTopology)
    res = await db.execute(stmt)
    relations = res.scalars().all()
    
    links = []
    nodes_set = set()
    
    for r in relations:
        links.append({
            "source": r.source,
            "target": r.target,
            "relationship_type": r.relationship_type,
            "is_critical": r.is_critical
        })
        nodes_set.add(r.source)
        nodes_set.add(r.target)
        
    # 2. Fetch active incidents to correlate states
    incident_stmt = select(Incident).where(Incident.status != "resolved")
    res = await db.execute(incident_stmt)
    active_incidents = res.scalars().all()
    
    active_map = {}
    blast_radius_services = set()
    for inc in active_incidents:
        active_map[inc.service_name] = inc.severity
        if inc.risk_assessment:
            # Parse impacted services from the risk assessment JSON column
            ra = inc.risk_assessment
            if isinstance(ra, dict):
                br = ra.get("blast_radius", {})
                if isinstance(br, dict):
                    services = br.get("impacted_services", [])
                    for s in services:
                        blast_radius_services.add(s)
        
    # 3. Formulate nodes with state
    nodes = []
    for node_name in nodes_set:
        status_state = "healthy"
        if node_name in active_map:
            sev = active_map[node_name]
            if sev == "SEV-1":
                status_state = "down"
            elif sev in ["SEV-2", "SEV-3"]:
                status_state = "degraded"
        elif node_name in blast_radius_services:
            status_state = "blast_radius"
                
        nodes.append({
            "id": node_name,
            "status": status_state
        })
        
    return {
        "nodes": nodes,
        "links": links
    }

