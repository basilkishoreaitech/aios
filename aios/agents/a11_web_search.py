import logging
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from services.web_search_service import WebSearchService
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a11")

class WebSearchAgent(BaseAgent):
    """A11 Web Search Agent: Triggered when local KB similarity is weak. Queries the configured web provider for secondary SRE evidence."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker,
        web_search_service: WebSearchService
    ):
        super().__init__("A11_WebSearch", config, model_router, token_tracker)
        self.web_search_service = web_search_service
        # API wrapper, set low budget
        self.token_tracker.set_agent_limit("A11_WebSearch", config.TOKEN_BUDGET_UTILITY)

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str,
        packet: IncidentPacket,
        evidence: EvidenceBundle
    ) -> EvidenceBundle:
        logger.info(f"A11 Web Search triggered for incident {incident_id}. Constructing query.")
        
        # Build a more SRE-focused query with service name and trusted-doc hints.
        hints = []
        lowered = f"{packet.service_name} {packet.title} {packet.description or ''}".lower()
        if any(token in lowered for token in ["aws", "lambda", "ecs", "fargate", "cloudwatch", "nat"]):
            hints.append("site:docs.aws.amazon.com")
        if any(token in lowered for token in ["azure", "aks", "functions", "app service", "key vault", "jwks"]):
            hints.append("site:learn.microsoft.com")
        if any(token in lowered for token in ["kubernetes", "k8s", "coredns"]):
            hints.append("site:kubernetes.io")
        hints.append("site:stackoverflow.com")

        metrics_text = ""
        if packet.metrics:
            metrics_text = f" metrics={packet.metrics}"

        query = (
            f"SRE incident troubleshooting {packet.service_name} {packet.title} {packet.description or ''}"
            f"{metrics_text} {' OR '.join(hints)}"
        ).strip()
        logger.info(f"Querying external search engines for: '{query[:100]}...'")
        
        # Execute configured web search
        web_results = await self.web_search_service.search(query)
        
        # Merge web results into the evidence bundle
        evidence.web_citations = web_results
        
        logger.info(f"Web Search returned {len(web_results)} results. Evidence bundle updated.")
        return evidence
