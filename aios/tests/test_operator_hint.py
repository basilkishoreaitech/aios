import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

from main import app
from database import get_db
from models.database import Incident
from auth.dependencies import get_current_user
from models.database import User

@pytest.fixture
def mock_db():
    db = AsyncMock()
    return db

@pytest.fixture
def mock_user():
    return User(username="engineer", role="operator")

def test_operator_hint_route(mock_db, mock_user):
    # Mock database responses
    mock_incident = Incident(
        id="inc_test_123",
        title="Test Alert",
        service_name="auth-service",
        severity="SEV-3",
        status="open",
        raw_alert='{"alert": "High replication lag"}'
    )
    
    # We mock db.execute to return our mock incident
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = mock_incident
    mock_db.execute = AsyncMock(return_value=mock_result)
    
    # Mock pipeline state in app
    app.state.pipeline = MagicMock()
    
    # run_pipeline_streaming is an async generator returning events
    async def mock_generator(*args, **kwargs):
        yield {"event": "pipeline_start", "data": '{"incident_id": "inc_test_123"}'}
        yield {"event": "pipeline_complete", "data": '{"incident_id": "inc_test_123"}'}
        
    app.state.pipeline.run_pipeline_streaming = mock_generator

    # Override dependencies
    app.dependency_overrides[get_db] = lambda: mock_db
    app.dependency_overrides[get_current_user] = lambda: mock_user

    client = TestClient(app)
    response = client.post(
        "/api/incident/inc_test_123/hint",
        json={"operator_hint": "Try checking the replica DB nodes"}
    )
    
    # Clean up overrides
    app.dependency_overrides.clear()
    
    assert response.status_code == 200
    # SSE streams have event/data text format
    content = response.text
    assert "event: pipeline_start" in content
    assert "event: pipeline_complete" in content
