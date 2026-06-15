from config import Settings
from services.web_search_service import WebSearchService


def test_web_search_service_prefers_tavily_when_configured():
    settings = Settings(
        TAVILY_API_KEY="tvly-demo-key",
        BING_SEARCH_API_KEY="",
        WEB_SEARCH_PROVIDER="auto",
    )

    service = WebSearchService(settings)

    assert service.enabled is True
    assert service.provider == "tavily"
    assert service.provider_label == "tavily_search_api"


def test_web_search_service_uses_bing_when_requested():
    settings = Settings(
        TAVILY_API_KEY="",
        BING_SEARCH_API_KEY="bing-demo-key",
        WEB_SEARCH_PROVIDER="bing",
    )

    service = WebSearchService(settings)

    assert service.enabled is True
    assert service.provider == "bing"
    assert service.provider_label == "bing_search_api"


def test_web_search_service_disabled_without_keys():
    settings = Settings(
        TAVILY_API_KEY="",
        BING_SEARCH_API_KEY="",
        WEB_SEARCH_PROVIDER="auto",
        REQUIRE_LIVE_WEB_SEARCH=False,
    )

    service = WebSearchService(settings)

    assert service.enabled is False
    assert service.provider == "none"
    assert service.provider_label == "disabled"