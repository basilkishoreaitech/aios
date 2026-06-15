import json
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from services.query_service import scrub_pii
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a1")

A1_SYSTEM_PROMPT = """You are the AIOS Alert Ingestion Agent (A1).
Your task is to parse a raw incident/alert payload and normalize it.

Extract the following details:
1. title: A concise, descriptive title for the incident.
2. service_name: The name of the affected service or resource (e.g. 'api-gateway', 'payment-service', 'postgres-primary').
3. severity: The normalized severity tier: SEV-1 (Critical outage), SEV-2 (Major degradation), SEV-3 (Warning), or SEV-4 (Informational).
4. metrics: A short JSON string containing only simple metric key-value pairs mentioned in the alert (e.g. '{"memory_pct": 92, "http_status": 504}'). Use null if none are present.
5. description: Detailed description of what failed.
6. tags: A list of relevant tags (e.g., 'database', 'rest-api', 'k8s').

Ensure that all outputs are derived strictly from the scrubbed input. Do not guess or add external details.
"""

class IntakeAgent(BaseAgent):
    """A1 Intake Agent: Sanitizes raw alert payloads, extracts metadata, and normalizes into an IncidentPacket."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A1_Intake", config, model_router, token_tracker)
        # Set agent budget limit
        self.token_tracker.set_agent_limit("A1_Intake", config.TOKEN_BUDGET_UTILITY)

    async def _run(self, session: AsyncSession, incident_id: str, raw_alert: str) -> IncidentPacket:
        # 1. Scrub PII using the regex utility
        sanitized_alert = scrub_pii(raw_alert)
        logger.info(f"PII scrubbing complete for incident {incident_id}")
        
        # 2. Extract structured fields via the utility deployment (gpt-4o-mini)
        messages = [
            {"role": "system", "content": A1_SYSTEM_PROMPT},
            {"role": "user", "content": f"Raw Alert Payload:\n{sanitized_alert}"}
        ]
        
        try:
            # We call with response_format=IncidentPacket
            # Preferred: utility deployment, fallback: low-cost reviewer deployment
            packet = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=IncidentPacket,
                preferred="utility",
                fallback="fallback"
            )
            # Ensure the incident_id is correctly set
            packet.incident_id = incident_id
            packet.raw_alert_sanitized = sanitized_alert
            return packet
        except Exception as e:
            logger.error(f"Error parsing alert via LLM: {e}. Falling back to default packet.")
            # Fail-safe default packet if LLM fails
            return IncidentPacket(
                incident_id=incident_id,
                title="Unhandled Alert Ingestion Failure",
                service_name="unknown",
                severity="SEV-3",
                raw_alert_sanitized=sanitized_alert,
                metrics=None,
                description=f"Automated fallback due to parsing error: {str(e)}",
                tags=["ingest-failure"]
            )
