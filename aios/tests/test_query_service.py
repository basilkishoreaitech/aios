import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession

from services.query_service import QueryService, scrub_pii
from models.query import QueryRequest
from services.model_router import ModelRouter
from services.embedding_service import EmbeddingService
from services.web_search_service import WebSearchService

def test_pii_scrubbing():
    email_text = "Contact admin@corp.com or checkout key bearer ghp_19A9f23"
    scrubbed = scrub_pii(email_text)
    assert "[EMAIL_REDACTED]" in scrubbed
    assert "Bearer [SECRET_REDACTED]" in scrubbed or "[SECRET_REDACTED]" in scrubbed

@pytest.mark.asyncio
async def test_query_service_flow():
    # Mock dependencies — provide a grounded KB hit so synthesis runs.
    from models.evidence import Citation
    embedding = AsyncMock(spec=EmbeddingService)
    embedding.search_kb.return_value = [
        Citation(
            doc_id="rb-db-pool",
            title="Database Connection Pool Exhaustion",
            category="runbook",
            relevance=0.82,
            content_snippet="Increase max pool size and tune idle timeout.",
        )
    ]
    embedding.embed.return_value = [1.0, 0.0]
    
    web = AsyncMock(spec=WebSearchService)
    web.search.return_value = []
    
    # Mock LLM response format
    from pydantic import BaseModel
    class MockSynthesis(BaseModel):
        answer: str
        confidence: float
        
    router = AsyncMock(spec=ModelRouter)
    router.call_with_fallback.return_value = MockSynthesis(
        answer="The database pool size must be increased.",
        confidence=0.92
    )
    
    service = QueryService(embedding_service=embedding, web_search_service=web, model_router=router)
    
    session = AsyncMock(spec=AsyncSession)
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result
    
    req = QueryRequest(question="How to fix connection pool limits?")
    response = await service.run_query(session, req)
    
    # Strong KB grounding (sim 0.82) keeps the high model confidence under the 0.95 ceiling.
    assert response.confidence == 0.92
    assert "database pool size" in response.answer
    assert response.source_breakdown["kb"] == 1
    # Every KB hit is surfaced as an aligned citation.
    assert len(response.citations) == 1


@pytest.mark.asyncio
async def test_query_service_hides_weak_related_incidents():
    from datetime import datetime, UTC
    from unittest.mock import MagicMock
    from models.database import Incident
    from models.evidence import Citation

    embedding = AsyncMock(spec=EmbeddingService)
    embedding.search_kb.return_value = [
        Citation(
            doc_id="rb-api-restart",
            title="API Gateway Safe Restart",
            category="runbook",
            relevance=0.70,
            content_snippet="Restart the API gateway after connection pool validation.",
        )
    ]
    embedding.embed.side_effect = [[1.0, 0.0], [0.1, 0.2]]

    web = AsyncMock(spec=WebSearchService)
    web.search.return_value = []

    from pydantic import BaseModel
    class MockSynthesis(BaseModel):
        answer: str
        confidence: float

    router = AsyncMock(spec=ModelRouter)
    router.call_with_fallback.return_value = MockSynthesis(answer="Use the restart guide.", confidence=0.6)

    service = QueryService(embedding_service=embedding, web_search_service=web, model_router=router)

    incident = Incident(
        id="inc-1",
        title="Gateway alert",
        service_name="api-gateway",
        severity="SEV-2",
        status="resolved",
        created_at=datetime.now(UTC),
        engineer_view="A single gateway keyword matched.",
        actual_root_cause="Unknown"
    )

    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [incident]
    session.execute.return_value = mock_result

    req = QueryRequest(question="gateway")
    response = await service.run_query(session, req)

    assert response.related_incidents == []
    assert response.source_breakdown["incidents_db"] == 0


@pytest.mark.asyncio
async def test_query_service_llm_failure_returns_grounded_fallback():
    from unittest.mock import MagicMock
    from models.evidence import Citation

    embedding = AsyncMock(spec=EmbeddingService)
    embedding.search_kb.return_value = [
        Citation(
            doc_id="rb-db-pool",
            title="Database Connection Pool Exhaustion",
            category="runbook",
            relevance=0.82,
            content_snippet="Increase max pool size and tune idle timeout.",
        )
    ]
    embedding.embed.return_value = [1.0, 0.0]

    web = AsyncMock(spec=WebSearchService)
    web.search.return_value = []

    router = AsyncMock(spec=ModelRouter)
    router.call_with_fallback.side_effect = RuntimeError("429")

    service = QueryService(embedding_service=embedding, web_search_service=web, model_router=router)

    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    req = QueryRequest(question="How to fix connection pool limits?")
    response = await service.run_query(session, req)

    assert "temporarily busy" in response.answer
    assert "Raw search results summary" not in response.answer
    assert response.confidence == 0.0


@pytest.mark.asyncio
async def test_query_zero_evidence_guard():
    """With no KB, incident, or web evidence the service must not sound confident."""
    embedding = AsyncMock(spec=EmbeddingService)
    embedding.search_kb.return_value = []
    embedding.embed.return_value = [1.0, 0.0]
    web = AsyncMock(spec=WebSearchService)
    web.search.return_value = []

    router = AsyncMock(spec=ModelRouter)  # should never be called

    service = QueryService(embedding_service=embedding, web_search_service=web, model_router=router)

    session = AsyncMock(spec=AsyncSession)
    from unittest.mock import MagicMock
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result

    req = QueryRequest(question="What is happening right now?")
    response = await service.run_query(session, req)

    assert response.confidence == 0.0
    assert response.citations == []
    assert len(response.clarifying_questions) > 0
    router.call_with_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_query_firewall_blocks_general_knowledge():
    embedding = AsyncMock(spec=EmbeddingService)
    web = AsyncMock(spec=WebSearchService)
    router = AsyncMock(spec=ModelRouter)

    service = QueryService(embedding_service=embedding, web_search_service=web, model_router=router)

    session = AsyncMock(spec=AsyncSession)
    req = QueryRequest(question="Tell me a joke about servers")
    response = await service.run_query(session, req)

    assert response.confidence == 0.0
    assert "scoped to incidents" in response.answer.lower()
    embedding.search_kb.assert_not_called()
    router.call_with_fallback.assert_not_called()


@pytest.mark.asyncio
async def test_show_open_incidents_returns_db_list_directly():
    """'Show me open incidents' must query the DB directly — no KB, no LLM."""
    from unittest.mock import MagicMock
    from models.database import Incident
    from datetime import datetime, timezone

    embedding = AsyncMock(spec=EmbeddingService)
    web = AsyncMock(spec=WebSearchService)
    router = AsyncMock(spec=ModelRouter)

    service = QueryService(embedding_service=embedding, web_search_service=web, model_router=router)

    incident = Incident(
        id="inc-open-1",
        title="Payment service latency spike",
        service_name="payment-api",
        severity="SEV-1",
        status="open",
        created_at=datetime.now(timezone.utc),
    )

    session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [incident]
    session.execute.return_value = mock_result

    for question in [
        "Show me open incidents",
        "list active incidents",
        "what are the current incidents",
        "get all open incidents",
    ]:
        response = await service.run_query(session, QueryRequest(question=question))
        assert "payment service latency spike" in response.answer.lower(), f"Failed for: {question!r}"
        assert response.confidence == 1.0
        assert response.source_breakdown["incidents_db"] == 1
        # KB and LLM must NOT be called for list intents
        embedding.search_kb.assert_not_called()
        router.call_with_fallback.assert_not_called()
        # reset mock call tracking between iterations
        embedding.search_kb.reset_mock()
        router.call_with_fallback.reset_mock()

