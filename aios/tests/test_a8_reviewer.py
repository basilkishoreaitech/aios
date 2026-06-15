import pytest
from unittest.mock import AsyncMock
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from agents.a8_adversarial_review import AdversarialReviewAgent, ReviewerVerdict
from config import get_settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from models.operational_context import OperationalContext
from models.hypothesis import HypothesisSet, Hypothesis

@pytest.mark.asyncio
async def test_reviewer_agent_approved():
    settings = get_settings()
    tracker = TokenBudgetTracker()
    
    # Mock ModelRouter
    router = AsyncMock(spec=ModelRouter)
    mock_verdict = ReviewerVerdict(
        verdict="approved",
        confidence_delta=0.05,
        critique="The deployment correlates perfectly with the memory leak pattern seen in postmortems."
    )
    router.call_with_fallback.return_value = mock_verdict
    router.last_model_used = "gpt-5.4-mini"
    router.last_tokens_used = 200
    
    agent = AdversarialReviewAgent(settings, router, tracker)
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
    context = OperationalContext(deployments=[], teams_messages=[])
    hypotheses = HypothesisSet(
        hypotheses=[
                Hypothesis(
                    title="Memory Leak",
                    description="Memory leak in recent version",
                    causal_factor="Memory leak",
                    severity_implication="OOM kills and downtime",
                    confidence=0.8,
                    evidence_citations=[],
                    recommended_actions=[]
                )      ],
        convergence_score=0.8,
        reasoning_path="path"
    )
    
    result = await agent.execute(session, "inc_123", packet, evidence, context, hypotheses)
    
    assert result.verdict == "approved"
    assert result.confidence_delta == 0.05
    assert "memory leak" in result.critique.lower()
    
    router.call_with_fallback.assert_called_once()
    assert session.add.call_count > 0
    assert session.commit.call_count > 0
