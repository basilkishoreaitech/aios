import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from agents.a11_web_search import WebSearchAgent
from config import get_settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker
from services.web_search_service import WebSearchService
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle, WebCitation

@pytest.mark.asyncio
async def test_web_search_agent_success():
    settings = get_settings()
    tracker = TokenBudgetTracker()
    
    # Mock ModelRouter
    router = AsyncMock(spec=ModelRouter)
    router.last_model_used = "n/a"
    router.last_tokens_used = 0
    
    # Mock WebSearchService
    web_service = AsyncMock(spec=WebSearchService)
    mock_citations = [
        WebCitation(
            title="Postgres connection pool exhaustion documentation",
            url="https://postgresql.org/docs/connection-pool",
            snippet="How to configure max_connections and handle saturation issues."
        )
    ]
    web_service.search.return_value = mock_citations
    
    agent = WebSearchAgent(settings, router, tracker, web_service)
    session = AsyncMock(spec=AsyncSession)
    
    packet = IncidentPacket(
        incident_id="inc_123",
        title="OOM alert",
        service_name="api-gateway",
        severity="SEV-2",
        raw_alert_sanitized="alert",
        metrics=None
    )
    evidence = EvidenceBundle(kb_citations=[], web_citations=[], max_similarity=0.0)
    
    result = await agent.execute(session, "inc_123", packet, evidence)
    
    assert len(result.web_citations) == 1
    assert result.web_citations[0].title == "Postgres connection pool exhaustion documentation"
    web_service.search.assert_called_once()
    assert session.add.call_count > 0
    assert session.commit.call_count > 0
