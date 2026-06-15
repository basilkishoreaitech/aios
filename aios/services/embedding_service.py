import logging
import hashlib
import math
import numpy as np
import httpx
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from openai import AsyncAzureOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from config import Settings
from models.database import KBDocument
from models.evidence import Citation

logger = logging.getLogger(__name__)


def normalize_search_score(score: float) -> float:
    """Normalize Azure Search BM25 scores into a 0..1 relevance band.

    Azure AI Search BM25 scores are unbounded and have no inherent meaning at
    1.0 (they are NOT percentages).  The old linear mapping treated a BM25 score
    of 1.0 as 100% relevance, which caused every keyword-matched document to
    appear as a "100% match" regardless of semantic relevance.

    Log scaling compresses the range honestly:
      BM25 0.5  → ~22%   (weak keyword hit)
      BM25 1.0  → ~39%   (moderate keyword match)
      BM25 2.0  → ~61%   (solid keyword match)
      BM25 5.0  → 100%   (strong full-document match, normalisation ceiling)
    """
    if score <= 0:
        return 0.0
    return float(min(1.0, math.log1p(score) / math.log1p(5.0)))

def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Compute cosine similarity between two float vectors."""
    dot = np.dot(a, b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))

class KBAdapter(ABC):
    """Abstract interface for knowledge-base adapters."""
    
    @abstractmethod
    async def search(
        self,
        session: AsyncSession,
        query_text: str,
        embedding: List[float],
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def add_document(self, session: AsyncSession, doc: Dict[str, Any], embedding: List[float]) -> str:
        pass


class FoundryIQAdapter(KBAdapter):
    """Grounded Retrieval adapter using Azure AI Search REST API."""

    # Azure AI Search stable API version
    SEARCH_API_VERSION = "2024-07-01"

    def __init__(self, endpoint: str, api_key: str, api_version: str, knowledge_base_name: str, knowledge_source_name: str):
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key
        if api_version and api_version != self.SEARCH_API_VERSION:
            logger.warning(
                "Ignoring unsupported FOUNDRY_IQ_API_VERSION '%s' and using Azure Search API '%s' instead.",
                api_version,
                self.SEARCH_API_VERSION,
            )
        self.api_version = self.SEARCH_API_VERSION
        self.index_name = knowledge_base_name  # treated as index name

    async def search(
        self,
        session: AsyncSession,
        query_text: str,
        embedding: List[float],
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        logger.info("Routing search query to Azure AI Search index '%s'", self.index_name)

        url = f"{self.endpoint}/indexes/{self.index_name}/docs/search?api-version={self.SEARCH_API_VERSION}"

        payload: Dict[str, Any] = {
            "search": query_text,
            "queryType": "simple",
            "searchMode": "any",   # OR semantics — keyword hits BOOST ranking; the banded gate in search_kb filters noise
            "top": 5,
            "select": "id,title,content,category,tags",
        }
        if category:
            payload["filter"] = f"category eq '{category}'"

        headers = {
            "api-key": self.api_key,
            "Content-Type": "application/json",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPStatusError as e:
            logger.error("Azure AI Search returned %s: %s", e.response.status_code, e.response.text)
            raise

        results = data.get("value", [])
        matches = []
        for item in results:
            raw_score = float(item.get("@search.score", 1.0))
            matches.append({
                "doc_id": str(item.get("id", "unknown")),
                "title": item.get("title", "Unknown"),
                "category": item.get("category", category or "unknown"),
                "relevance": normalize_search_score(raw_score),
                "content_snippet": (item.get("content") or "")[:2000],
            })
        return matches

    async def add_document(self, session: AsyncSession, doc: Dict[str, Any], embedding: List[float]) -> str:
        """Upload a single document to the Azure AI Search index."""
        url = f"{self.endpoint}/indexes/{self.index_name}/docs/index?api-version={self.SEARCH_API_VERSION}"
        headers = {"api-key": self.api_key, "Content-Type": "application/json"}
        payload = {
            "value": [{
                "@search.action": "mergeOrUpload",
                "id": doc["id"],
                "title": doc.get("title", ""),
                "content": doc.get("content", ""),
                "category": doc.get("category", ""),
                "tags": doc.get("tags", []),
                "source_file": doc.get("source_file", ""),
            }]
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
        return doc["id"]


class EmbeddingService:
    """Handles embedding generation and semantic similarity search against the KB."""
    
    def __init__(self, config: Settings):
        self.config = config
        self._cache: Dict[str, List[float]] = {}  # In-memory embedding cache
        
        if config.AZURE_OPENAI_API_KEY and config.AZURE_OPENAI_ENDPOINT:
            self.client = AsyncAzureOpenAI(
                api_key=config.AZURE_OPENAI_API_KEY,
                azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
                api_version=config.AZURE_OPENAI_API_VERSION
            )
            self.enabled = True
        else:
            raise ValueError("Azure OpenAI key/endpoint missing. EmbeddingService requires live model configuration.")
            
        # Select Adapter
        if config.KB_PROVIDER == "foundry_iq":
            if not (config.FOUNDRY_IQ_ENDPOINT and config.FOUNDRY_IQ_KEY and config.FOUNDRY_IQ_INDEX_NAME):
                raise ValueError(
                    "Foundry IQ mode requires FOUNDRY_IQ_ENDPOINT, FOUNDRY_IQ_KEY, and FOUNDRY_IQ_INDEX_NAME."
                )
            self.adapter = FoundryIQAdapter(
                config.FOUNDRY_IQ_ENDPOINT,
                config.FOUNDRY_IQ_KEY,
                config.FOUNDRY_IQ_API_VERSION,
                config.FOUNDRY_IQ_INDEX_NAME,
                config.FOUNDRY_IQ_INDEX_NAME,
            )
        else:
            raise ValueError("AIOS now requires KB_PROVIDER=foundry_iq. Local knowledge base mode is disabled.")

    async def _search_postgres_vector(
        self,
        session: AsyncSession,
        embedding: List[float],
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Semantic vector rerank using embeddings stored in the Azure PostgreSQL kb_documents table.

        NOTE: This is NOT a local/offline fallback. It reads the persisted embedding
        vectors from the cloud Azure Database for PostgreSQL and reranks by cosine
        similarity. It runs alongside Azure AI Search (keyword) to form hybrid retrieval.
        """
        stmt = select(KBDocument)
        if category:
            stmt = stmt.where(KBDocument.category == category)

        result = await session.execute(stmt)
        documents = result.scalars().all()

        matches: List[Dict[str, Any]] = []
        for doc in documents:
            if not doc.embedding:
                continue

            relevance = cosine_similarity(embedding, doc.embedding)
            matches.append({
                "doc_id": doc.id,
                "title": doc.title,
                "category": doc.category,
                "relevance": float(relevance),
                "content_snippet": (doc.content or "")[:2000],
            })

        matches.sort(key=lambda item: item["relevance"], reverse=True)
        return matches

    async def embed(self, text: str) -> List[float]:
        """Generate embedding vector for text using cache to optimize API credits."""
        if not text:
            return []
            
        cache_key = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        if not self.enabled:
            raise ValueError("EmbeddingService is not initialized with a live Azure OpenAI client.")
            
        try:
            response = await self.client.embeddings.create(
                model=self.config.AZURE_OPENAI_DEPLOYMENT_EMBEDDING,
                input=text
            )
            embedding = response.data[0].embedding
            self._cache[cache_key] = embedding
            return embedding
        except Exception as e:
            logger.error(f"Failed to generate embedding from Azure OpenAI: {e}")
            raise

    async def search_kb(
        self,
        session: AsyncSession,
        query_text: str,
        category: Optional[str] = None,
        top_k: int = 5,
        threshold: float = 0.44,
        keyword_query: Optional[str] = None,
    ) -> List[Citation]:
        """Hybrid KB search: Azure AI Search (keyword) + Azure PostgreSQL vector rerank.

        Uses a *banded* relevance gate rather than a flat cutoff:
          - If the single best match cannot clear ``threshold`` (the relevance floor),
            return EMPTY — honest "no grounded evidence" instead of a tangential doc.
          - Otherwise keep only the cluster of documents within 0.12 of the top match,
            so one marginal doc can never become the sole (and misleading) evidence.
        """
        embedding = await self.embed(query_text)
        if not embedding:
            return []

        # Keyword path may use a tighter query (service + title) to avoid long-query misses;
        # the semantic path always uses the full rich query embedding.
        lexical_matches = await self.adapter.search(session, keyword_query or query_text, embedding, category)
        semantic_matches = await self._search_postgres_vector(session, embedding, category)

        # SEMANTIC (cosine) is the relevance authority — its scores are comparable across
        # documents. Azure BM25 keyword scores are unbounded/non-comparable and would
        # otherwise let a keyword-only match (e.g. shares a word like 'database') dominate
        # a far more relevant semantic match. So keyword presence only applies a small boost
        # to a doc that is ALREADY semantically scored; it can never inject an unrelated doc.
        keyword_ids = {m["doc_id"] for m in lexical_matches}
        merged: Dict[str, Dict[str, Any]] = {m["doc_id"]: m for m in semantic_matches}
        for doc_id, rec in merged.items():
            if doc_id in keyword_ids:
                rec["relevance"] = min(1.0, rec["relevance"] + 0.03)
        # Include any keyword-only docs but only at their (low) semantic standing — if a
        # keyword doc has no embedding/semantic score it simply won't clear the floor below.
        for m in lexical_matches:
            if m["doc_id"] not in merged:
                merged[m["doc_id"]] = {**m, "relevance": 0.0}

        matches = sorted(merged.values(), key=lambda item: item["relevance"], reverse=True)
        if not matches:
            return []

        top_relevance = matches[0]["relevance"]
        # Honest empty: nothing is actually relevant → let A3 fall back / A11 web search fire.
        if top_relevance < threshold:
            logger.info(
                "KB retrieval: best match %.3f below floor %.2f — returning no citations (honest gap).",
                top_relevance, threshold,
            )
            return []

        band_floor = max(threshold, top_relevance - 0.12)
        citations = []
        for match in matches:
            if match["relevance"] >= band_floor:
                citations.append(
                    Citation(
                        doc_id=match["doc_id"],
                        title=match["title"],
                        category=match["category"],
                        relevance=match["relevance"],
                        content_snippet=match["content_snippet"]
                    )
                )
                if len(citations) >= top_k:
                    break
        return citations
