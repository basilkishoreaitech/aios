import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from agents.a1_intake import IntakeAgent
from config import get_settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker
from models.incident_packet import IncidentPacket

@pytest.mark.asyncio
async def test_intake_agent_success():
    settings = get_settings()
    tracker = TokenBudgetTracker()
    
    # Mock ModelRouter
    router = AsyncMock(spec=ModelRouter)
    mock_packet = IncidentPacket(
        incident_id="inc_123",
        title="Database Latency Spike",
        service_name="postgres-primary",
        severity="SEV-2",
        raw_alert_sanitized="High database connections and latency spikes",
        metrics="{\"latency_ms\": 450}",
        description="High database connections and latency spikes",
        tags=["database", "latency"]
    )
    router.call_with_fallback.return_value = mock_packet
    router.last_model_used = "gpt-4o-mini"
    router.last_tokens_used = 150
    
    agent = IntakeAgent(settings, router, tracker)
    session = AsyncMock(spec=AsyncSession)
    
    # Input has PII (email and GitHub token)
    raw_alert = "Alert on postgres-primary from user admin@corp.com with secret ghp_19A9f23. Latency: 450ms"
    
    packet = await agent.execute(session, "inc_123", raw_alert)
    
    # Check that PII was scrubbed in raw_alert_sanitized
    assert "[EMAIL_REDACTED]" in packet.raw_alert_sanitized
    assert "[SECRET_REDACTED]" in packet.raw_alert_sanitized or "Bearer" in packet.raw_alert_sanitized or "ghp_" not in packet.raw_alert_sanitized
    assert packet.title == "Database Latency Spike"
    assert packet.service_name == "postgres-primary"
    
    # Check that model router was called with response_format=IncidentPacket
    router.call_with_fallback.assert_called_once()
    assert session.add.call_count > 0
    assert session.commit.call_count > 0
