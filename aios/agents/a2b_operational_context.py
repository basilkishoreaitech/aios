import logging
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.operational_context import (
    OperationalContext, DeploymentEvent, TeamsMessage, OnCallEngineer
)
from models.database import OperationalEvent
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a2b")

class OperationalContextAgent(BaseAgent):
    """A2b Operational Context Agent: gathers recent deployments, chat signals, and on-call data for correlation."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A2b_OperationalContext", config, model_router, token_tracker)
        self.token_tracker.set_agent_limit("A2b_OperationalContext", config.TOKEN_BUDGET_UTILITY)

    async def _run(self, session: AsyncSession, incident_id: str, packet: IncidentPacket) -> OperationalContext:
        logger.info(f"Gathering operational events for service: '{packet.service_name}'")
        
        # 1. Fetch calendar/deployment events for this service
        deployment_stmt = select(OperationalEvent).where(
            (OperationalEvent.event_type == "calendar") &
            (OperationalEvent.service_name == packet.service_name)
        )
        res = await session.execute(deployment_stmt)
        dep_events = res.scalars().all()
        
        deployments = []
        for e in dep_events:
            meta = e.metadata_json or {}
            deployments.append(
                DeploymentEvent(
                    service_name=e.service_name or "",
                    version=meta.get("version", "unknown"),
                    status=meta.get("status", "completed"),
                    deployed_at=e.event_time or datetime.now(timezone.utc),
                    deployed_by=e.author or "unknown",
                    details=e.content
                )
            )

        # 2. Fetch recent Teams chat messages
        teams_stmt = select(OperationalEvent).where(
            (OperationalEvent.event_type == "teams_chat") &
            ((OperationalEvent.service_name == packet.service_name) | (OperationalEvent.service_name == None))
        )
        res = await session.execute(teams_stmt)
        chat_events = res.scalars().all()
        
        teams_messages = []
        for e in chat_events:
            teams_messages.append(
                TeamsMessage(
                    author=e.author or "unknown",
                    content=e.content or "",
                    timestamp=e.event_time or datetime.now(timezone.utc),
                    channel=e.title or "#general"
                )
            )

        # 3. Fetch active oncall SRE list
        oncall_stmt = select(OperationalEvent).where(
            OperationalEvent.event_type == "oncall"
        )
        res = await session.execute(oncall_stmt)
        oncall_events = res.scalars().all()
        
        oncall_roster = []
        for e in oncall_events:
            # Match service name or list generic oncall SREs
            if not e.service_name or e.service_name == packet.service_name or packet.service_name in e.content:
                meta = e.metadata_json or {}
                oncall_roster.append(
                    OnCallEngineer(
                        name=e.content.split(":")[1].split(",")[0].strip() if ":" in e.content else e.content,
                        role=meta.get("tier", "primary"),
                        contact=e.content.split("Phone:")[1].strip() if "Phone:" in e.content else "unknown"
                    )
                )

        logger.info(
            "Operational context gathered: %s deployments, %s chats, %s oncall engineers.",
            len(deployments),
            len(teams_messages),
            len(oncall_roster),
        )
        
        return OperationalContext(
            deployments=deployments,
            teams_messages=teams_messages,
            oncall_roster=oncall_roster
        )
