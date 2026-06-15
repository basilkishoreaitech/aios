import logging
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from services.embedding_service import EmbeddingService
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a2")

class RetrievalAgent(BaseAgent):
    """A2 Retrieval Agent: Performs semantic search against runbooks and past incident postmortems."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker,
        embedding_service: EmbeddingService
    ):
        super().__init__("A2_Retrieval", config, model_router, token_tracker)
        self.embedding_service = embedding_service
        # Embeddings are non-LLM or simple helper; set default budget limit
        self.token_tracker.set_agent_limit("A2_Retrieval", config.TOKEN_BUDGET_UTILITY)

    async def _run(self, session: AsyncSession, incident_id: str, packet: IncidentPacket) -> EvidenceBundle:
        # Two queries with different roles:
        #  - keyword_query: tight (service + title + tags) so Azure AI Search BM25 actually matches.
        #  - semantic_query: rich (adds a description excerpt) for the embedding/vector rerank.
        desc_excerpt = (packet.description or "")[:300]
        tag_text = " ".join(packet.tags or [])
        keyword_query = f"{packet.service_name} {packet.title} {tag_text}".strip()
        semantic_query = f"{packet.service_name} {packet.title} {desc_excerpt}".strip()
        logger.info(f"KB search — keyword:'{keyword_query[:80]}' | semantic:'{semantic_query[:80]}...'")

        # Hybrid retrieval with a banded relevance gate.
        # threshold=0.44 is the honesty floor: if nothing clears it, we return no citations
        # so A3 can fall back to general reasoning / A11 can fire web search.
        kb_citations = await self.embedding_service.search_kb(
            session=session,
            query_text=semantic_query,
            category=None,
            top_k=5,
            threshold=0.44,
            keyword_query=keyword_query,
        )
        
        # Calculate maximum similarity score
        max_sim = max([c.relevance for c in kb_citations]) if kb_citations else 0.0
        
        logger.info(f"Retrieved {len(kb_citations)} local documents. Max similarity score: {max_sim:.2f}")
        
        # Consolidate into an EvidenceBundle
        evidence_bundle = EvidenceBundle(
            kb_citations=kb_citations,
            web_citations=[],  # Will be populated by A11 Web Search if similarity threshold is not met
            max_similarity=max_sim
        )
        
        return evidence_bundle
