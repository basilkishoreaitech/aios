import pytest
from unittest.mock import AsyncMock

from fastapi import HTTPException

from auth.rbac import hash_password, verify_password, create_access_token, decode_access_token, has_permission
from routes.auth import LoginRequest, UserCreateRequest, login, register
from models.database import User

def test_password_hashing():
    pwd = "my-secure-password"
    hashed = hash_password(pwd)
    assert hashed != pwd
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrong-password", hashed) is False

def test_jwt_tokens():
    payload = {"sub": "engineer", "role": "operator"}
    token = create_access_token(payload)
    assert isinstance(token, str)
    
    decoded = decode_access_token(token)
    assert decoded is not None
    assert decoded["sub"] == "engineer"
    assert decoded["role"] == "operator"

def test_rbac_permissions():
    assert has_permission("admin", "execute:high_risk") is True
    assert has_permission("operator", "execute:high_risk") is False
    assert has_permission("operator", "execute:low_risk") is True
    assert has_permission("executive", "execute:low_risk") is False


@pytest.mark.asyncio
async def test_login_returns_503_when_database_unavailable():
    mock_db = AsyncMock()
    mock_db.execute.side_effect = OSError("WinError 121")

    with pytest.raises(HTTPException) as exc:
        await login(LoginRequest(username="engineer", password="pw"), db=mock_db)

    assert exc.value.status_code == 503
    assert "Database temporarily unavailable" in exc.value.detail


@pytest.mark.asyncio
async def test_register_returns_503_when_database_unavailable():
    mock_db = AsyncMock()
    mock_db.execute.side_effect = OSError("WinError 121")
    admin_user = User(username="admin", hashed_password="x", role="admin", display_name="Admin")

    with pytest.raises(HTTPException) as exc:
        await register(
            UserCreateRequest(username="new-user", password="pw", role="operator", display_name="New User"),
            db=mock_db,
            admin_user=admin_user,
        )

    assert exc.value.status_code == 503
    assert "Database temporarily unavailable" in exc.value.detail
