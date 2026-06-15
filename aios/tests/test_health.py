from unittest.mock import AsyncMock

import pytest

from routes.health import readiness_check, settings


@pytest.mark.asyncio
async def test_ready_ignores_bing_when_optional(monkeypatch):
    mock_db = AsyncMock()
    mock_db.execute.return_value = object()

    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_ENDPOINT", "https://search.windows.net")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_KEY", "search-key")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_INDEX_NAME", "aios-kb")
    monkeypatch.setattr(settings, "BING_SEARCH_API_KEY", "")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(settings, "REQUIRE_LIVE_WEB_SEARCH", False)

    result = await readiness_check(db=mock_db)

    assert result["ready"] is True
    assert result["checks"]["bing_search"] is False
    assert "bing_search" not in result["required_checks"]


@pytest.mark.asyncio
async def test_ready_requires_bing_when_enabled(monkeypatch):
    mock_db = AsyncMock()
    mock_db.execute.return_value = object()

    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_ENDPOINT", "https://search.windows.net")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_KEY", "search-key")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_INDEX_NAME", "aios-kb")
    monkeypatch.setattr(settings, "BING_SEARCH_API_KEY", "")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(settings, "REQUIRE_LIVE_WEB_SEARCH", True)

    result = await readiness_check(db=mock_db)

    assert result["ready"] is False
    assert result["checks"]["bing_search"] is False
    assert "bing_search" in result["required_checks"]


@pytest.mark.asyncio
async def test_ready_requires_foundry_iq(monkeypatch):
    mock_db = AsyncMock()
    mock_db.execute.return_value = object()

    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_ENDPOINT", "")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_KEY", "")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_INDEX_NAME", "")
    monkeypatch.setattr(settings, "BING_SEARCH_API_KEY", "")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "")
    monkeypatch.setattr(settings, "REQUIRE_LIVE_WEB_SEARCH", False)

    result = await readiness_check(db=mock_db)

    assert result["ready"] is False
    assert result["checks"]["foundry_iq"] is False


@pytest.mark.asyncio
async def test_ready_accepts_tavily_as_web_search(monkeypatch):
    mock_db = AsyncMock()
    mock_db.execute.return_value = object()

    monkeypatch.setattr(settings, "AZURE_OPENAI_API_KEY", "key")
    monkeypatch.setattr(settings, "AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_ENDPOINT", "https://search.windows.net")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_KEY", "search-key")
    monkeypatch.setattr(settings, "FOUNDRY_IQ_INDEX_NAME", "aios-kb")
    monkeypatch.setattr(settings, "BING_SEARCH_API_KEY", "")
    monkeypatch.setattr(settings, "TAVILY_API_KEY", "tvly-demo-key")
    monkeypatch.setattr(settings, "REQUIRE_LIVE_WEB_SEARCH", False)

    result = await readiness_check(db=mock_db)

    assert result["ready"] is True
    assert result["checks"]["bing_search"] is True
