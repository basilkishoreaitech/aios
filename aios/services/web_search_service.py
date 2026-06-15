import logging
import httpx
from typing import List
from config import Settings
from models.evidence import WebCitation

logger = logging.getLogger(__name__)

class WebSearchService:
    """Queries the configured web search provider for external documentation and incident references."""
    
    def __init__(self, config: Settings):
        self.config = config
        self.provider = self._resolve_provider()
        self.enabled = self.provider != "none"
        if config.REQUIRE_LIVE_WEB_SEARCH and not self.enabled:
            raise ValueError(
                "Live web search is required but no provider is configured. "
                "Set TAVILY_API_KEY or BING_SEARCH_API_KEY."
            )

    def _resolve_provider(self) -> str:
        preferred = (self.config.WEB_SEARCH_PROVIDER or "auto").lower()
        if preferred in {"auto", "tavily"} and self.config.TAVILY_API_KEY:
            return "tavily"
        if preferred in {"auto", "bing"} and self.config.BING_SEARCH_API_KEY:
            return "bing"
        return "none"

    @property
    def provider_label(self) -> str:
        if self.provider == "tavily":
            return "tavily_search_api"
        if self.provider == "bing":
            return "bing_search_api"
        return "disabled"

    async def search(self, query: str) -> List[WebCitation]:
        """Perform a web search and return normalized WebCitation objects."""
        if not query:
            return []
            
        if not self.enabled:
            logger.info("No web search provider configured. Returning no external web search results.")
            return []

        if self.provider == "tavily":
            return await self._search_tavily(query)
        if self.provider == "bing":
            return await self._search_bing(query)
        return []

    async def _search_tavily(self, query: str) -> List[WebCitation]:
        headers = {"Content-Type": "application/json"}
        payload = {
            "api_key": self.config.TAVILY_API_KEY,
            "query": query,
            "topic": "general",
            "search_depth": "basic",
            "max_results": 5,
            "include_answer": False,
            "include_raw_content": False,
        }

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(self.config.TAVILY_SEARCH_ENDPOINT, headers=headers, json=payload)
                if response.status_code != 200:
                    logger.error("Tavily Search returned error code %s: %s", response.status_code, response.text)
                    return []

                data = response.json()
                results = data.get("results", [])
                citations = []
                for item in results:
                    citations.append(
                        WebCitation(
                            title=item.get("title", "Unknown Page"),
                            url=item.get("url", ""),
                            snippet=item.get("content", "")
                        )
                    )
                return citations
        except Exception as exc:
            logger.error("Exception during Tavily Search API call: %s", exc)
            return []

    async def _search_bing(self, query: str) -> List[WebCitation]:
        headers = {"Ocp-Apim-Subscription-Key": self.config.BING_SEARCH_API_KEY}
        params = {
            "q": query,
            "count": 5,
            "textDecorations": "True",
            "textFormat": "Raw",
            "safeSearch": "Strict"
        }

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(self.config.BING_SEARCH_ENDPOINT, headers=headers, params=params)
                if response.status_code == 200:
                    data = response.json()
                    pages = data.get("webPages", {}).get("value", [])
                    citations = []
                    for page in pages:
                        citations.append(
                            WebCitation(
                                title=page.get("name", "Unknown Page"),
                                url=page.get("url", ""),
                                snippet=page.get("snippet", "")
                            )
                        )
                    return citations
                else:
                    logger.error(f"Bing Search returned error code {response.status_code}: {response.text}")
                    return []
        except Exception as e:
            logger.error(f"Exception during Bing Search API call: {e}")
            return []
