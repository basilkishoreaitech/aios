import os
import json
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from agents.base_agent import BaseAgent
from models.database import Incident, KBDocument
from services.embedding_service import EmbeddingService
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a10")

A10_SYSTEM_PROMPT = """You are the AIOS Knowledge Ingestion and Learning Loop Agent (A10).
Your job is to structure a resolved incident's findings, timeline, and actions into a standardized postmortem document format.

Your output must be a JSON object with:
- id: A unique string identifier, e.g. 'incident_<incident_id>_postmortem'.
- title: A descriptive title, e.g. 'Postmortem - Incident #<id>: <Title>'.
- category: Set this to 'postmortem'.
- content: Markdown document containing Incident Summary, Causal Factor, Resolution Steps, and Lessons Learned.
- tags: List of keywords, e.g. ['database', 'postgres', 'pool'].

Synthesize a professional SRE postmortem based on the provided incident history.
"""

class KnowledgeIngestAgent(BaseAgent):
    """A10 Knowledge Ingest Agent: Synthesizes structured postmortems from resolved incidents and ingests them into the KB."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker,
        embedding_service: EmbeddingService
    ):
        super().__init__("A10_KnowledgeIngest", config, model_router, token_tracker)
        self.embedding_service = embedding_service
        # Postmortem synthesis needs more tokens than the generic utility budget
        self.token_tracker.set_agent_limit("A10_KnowledgeIngest", max(12000, config.TOKEN_BUDGET_UTILITY))

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str
    ) -> str:
        logger.info(f"Generating postmortem for resolved incident {incident_id}")
        
        # 1. Retrieve incident from DB
        stmt = select(Incident).where(Incident.id == incident_id)
        res = await session.execute(stmt)
        incident = res.scalars().first()
        
        if not incident or incident.status != "resolved":
            logger.warning(f"Incident {incident_id} not found or not resolved. Skipping knowledge ingestion.")
            return ""

        # 2. Run LLM to synthesize postmortem JSON structure
        prompt = f"""=== INCIDENT METADATA ===
ID: {incident.id}
Title: {incident.title}
Service: {incident.service_name}
Severity: {incident.severity}
Created At: {incident.created_at.isoformat() if incident.created_at else ''}
Resolved At: {incident.resolved_at.isoformat() if incident.resolved_at else ''}

=== DIAGNOSIS & CAUSE ===
Predicted Hypotheses: {incident.hypotheses}
Actual Root Cause: {incident.actual_root_cause}
Resolved By: {incident.resolved_by}

=== REMEDIATION ACTIONS ===
Action Plan: {incident.action_plan}
"""

        # Define Schema for structured output
        class PostmortemSchema(BaseModel):
            id: str
            title: str
            category: str
            content: str
            tags: list[str]

        messages = [
            {"role": "system", "content": A10_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        logger.info("Synthesizing postmortem document structure via LLM.")
        try:
            doc = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=PostmortemSchema,
                preferred="utility",
                fallback="fallback"
            )
            
            # 3. Compute Embedding
            content_text = f"{doc.title} {doc.content} {' '.join(doc.tags)}"
            logger.info(f"Computing embedding for new postmortem document: {doc.id}")
            embedding = await self.embedding_service.embed(content_text)
            
            # 4. Save to Database (idempotent check)
            stmt = select(KBDocument).where(KBDocument.id == doc.id)
            res = await session.execute(stmt)
            existing = res.scalars().first()
            
            if existing:
                logger.info(f"KB document {doc.id} already exists in database. Updating content.")
                existing.content = doc.content
                existing.tags = doc.tags
                existing.embedding = embedding
            else:
                db_doc = KBDocument(
                    id=doc.id,
                    title=doc.title,
                    category=doc.category,
                    content=doc.content,
                    tags=doc.tags,
                    embedding=embedding,
                    source_file=f"postmortems/{doc.id}.json"
                )
                session.add(db_doc)
                logger.info(f"Saved new postmortem {doc.id} to KB database.")

            # 5. Write to local filesystem to maintain zero-drift files sync
            local_postmortem_path = Path(self.config.KNOWLEDGE_DIR) / "postmortems" / f"{doc.id}.json"
            # Ensure folder exists
            local_postmortem_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(local_postmortem_path, "w", encoding="utf-8") as f:
                json.dump({
                    "id": doc.id,
                    "title": doc.title,
                    "category": doc.category,
                    "content": doc.content,
                    "tags": doc.tags
                }, f, indent=2)
                
            logger.info(f"Synced postmortem file to local disk: {local_postmortem_path}")
            await session.commit()
            return doc.id
            
        except Exception as e:
            logger.error(f"Error executing knowledge ingest: {e}")
            raise e
