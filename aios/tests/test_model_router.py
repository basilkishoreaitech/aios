import pytest
import httpx
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from config import get_settings
from services.model_router import ModelRouter
from openai import RateLimitError

@pytest.mark.asyncio
async def test_model_router_fallback():
    settings = get_settings()
    settings.AZURE_OPENAI_API_KEY = "test-key"
    settings.AZURE_OPENAI_ENDPOINT = "https://test-endpoint.openai.azure.com"
    settings.AZURE_OPENAI_FALLBACK_COOLDOWN_SECONDS = 0
    
    router = ModelRouter(settings)
    
    # Mock the client's beta chat completions parse method to fail on first attempt, succeed on fallback
    router.client = AsyncMock()
    
    # Exhaust primary retries, then succeed on fallback.
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(parsed=SimpleNamespace(val="ok")))],
        usage=SimpleNamespace(total_tokens=120)
    )
    rate_limited_response = httpx.Response(429, request=httpx.Request("POST", "https://test-endpoint.openai.azure.com"))
    
    # We raise rate limit on first call (primary) and return mock on fallback
    # To mock this, we can set side_effect
    router.client.beta.chat.completions.parse.side_effect = [
        RateLimitError(message="Rate limited", response=rate_limited_response, body=None),
        RateLimitError(message="Rate limited", response=rate_limited_response, body=None),
        RateLimitError(message="Rate limited", response=rate_limited_response, body=None),
        mock_response
    ]
    
    from pydantic import BaseModel
    class MockSchema(BaseModel):
        val: str

    await router.call_with_fallback(
        messages=[{"role": "user", "content": "hi"}],
        response_format=MockSchema
    )
    
    # Verify both models were attempted (3 retries on primary, then 1 success on fallback)
    assert router.client.beta.chat.completions.parse.call_count == 4
    assert router.last_model_used == settings.AZURE_OPENAI_DEPLOYMENT_FALLBACK
