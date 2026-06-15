import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from mcp_server import list_active_incidents, get_incident_reasoning, approve_action_gate
from models.database import Incident, ActionItem

@pytest.mark.asyncio
async def test_list_active_incidents_empty():
    with patch("mcp_server.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        
        res = await list_active_incidents()
        assert "No active incidents found" in res

@pytest.mark.asyncio
async def test_list_active_incidents_success():
    with patch("mcp_server.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_inc = Incident(
            id="inc_123",
            title="Outage",
            service_name="payment-service",
            severity="SEV-1",
            status="active"
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_inc]
        mock_session.execute.return_value = mock_result
        
        res = await list_active_incidents()
        assert "Incident ID: inc_123" in res
        assert "payment-service" in res

@pytest.mark.asyncio
async def test_get_incident_reasoning_not_found():
    with patch("mcp_server.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result
        
        res = await get_incident_reasoning("inc_999")
        assert "not found" in res

@pytest.mark.asyncio
async def test_get_incident_reasoning_success():
    with patch("mcp_server.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_inc = Incident(
            id="inc_123",
            title="Outage",
            service_name="payment-service",
            severity="SEV-1",
            status="active",
            reviewer_verdict="approved",
            hypotheses={"hypotheses": [{"title": "DB saturated", "confidence": 0.9, "description": "Too many connections"}]},
            engineer_view="Logs look bad"
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_inc
        mock_session.execute.return_value = mock_result
        
        res = await get_incident_reasoning("inc_123")
        assert "approved" in res
        assert "DB saturated" in res
        assert "Logs look bad" in res

@pytest.mark.asyncio
async def test_approve_action_gate_not_found():
    with patch("mcp_server.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_session.execute.return_value = mock_result
        
        res = await approve_action_gate("inc_123", "act_999", "operator")
        assert "Error" in res

@pytest.mark.asyncio
async def test_approve_action_gate_success():
    with patch("mcp_server.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        mock_action = ActionItem(
            id="act_456",
            incident_id="inc_123",
            action="restart pod",
            status="pending"
        )
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_action
        mock_session.execute.return_value = mock_result
        
        res = await approve_action_gate("inc_123", "act_456", "test_op")
        assert "Success" in res
        assert mock_action.status == "executed"
        assert mock_action.approved_by == "MCP:test_op"
        mock_session.commit.assert_called_once()
