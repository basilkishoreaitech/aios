import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
from agents.a3_correlation import CorrelationAgent
from config import get_settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle, Citation
from models.operational_context import OperationalContext, DeploymentEvent, TeamsMessage
from models.hypothesis import HypothesisSet, Hypothesis

@pytest.mark.asyncio
async def test_correlation_agent_success():
    settings = get_settings()
    tracker = TokenBudgetTracker()
    
    # Mock ModelRouter
    router = AsyncMock(spec=ModelRouter)
    mock_hypotheses = HypothesisSet(
        hypotheses=[
            Hypothesis(
                title="Database Pool Exhaustion",
                description="Database pool is saturated due to high traffic.",
                causal_factor="High traffic volume",
                severity_implication="High latency and dropped connections",
                confidence=0.9,
                evidence_citations=["doc_db_pool_1"],
                recommended_actions=["restart database", "increase pool size"]
            )
        ],
        convergence_score=0.92,
        reasoning_path="Correlated alert with recent deployment and DB pools runbook."
    )
    router.call_with_fallback.return_value = mock_hypotheses
    router.last_model_used = "gpt-4o"
    router.last_tokens_used = 450
    
    agent = CorrelationAgent(settings, router, tracker)
    session = AsyncMock(spec=AsyncSession)
    
    packet = IncidentPacket(
        incident_id="inc_123",
        title="OOM alert",
        service_name="api-gateway",
        severity="SEV-2",
        raw_alert_sanitized="alert",
        metrics=None
    )
    
    evidence = EvidenceBundle(
        kb_citations=[
            Citation(
                doc_id="doc_db_pool_1",
                title="Database Connection Pool Runbook",
                content_snippet="Ensure db pool connection limits are raised.",
                category="runbook",
                relevance=0.85
            )
        ],
        web_citations=[],
        max_similarity=0.85
    )
    
    context = OperationalContext(
        deployments=[
            DeploymentEvent(
                service_name="api-gateway",
                version="v1.2",
                deployed_at=datetime.now(timezone.utc),
                deployed_by="Alice",
                status="success",
                details="Updated libraries"
            )
        ],
        teams_messages=[
            TeamsMessage(
                timestamp=datetime.now(timezone.utc),
                author="Bob",
                channel="sre-alerts",
                content="Db pool connection issues observed in prod"
            )
        ]
    )
    
    result = await agent.execute(session, "inc_123", packet, evidence, context)
    
    assert result.convergence_score == 0.92
    assert len(result.hypotheses) == 1
    assert result.hypotheses[0].title == "Database Pool Exhaustion"
    
    router.call_with_fallback.assert_called_once()
    assert session.add.call_count > 0
    assert session.commit.call_count > 0
