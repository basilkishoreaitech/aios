import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import AsyncSessionLocal, init_db, Base
from models.database import User, KBDocument, ServiceTopology, OperationalEvent
from auth.rbac import SEED_USERS, hash_password
from services.embedding_service import EmbeddingService
from config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("aios.seed")

async def seed_users(session: AsyncSession):
    """Seed system users if not already present."""
    logger.info("Seeding users...")
    for user_data in SEED_USERS:
        # Check if user already exists
        stmt = select(User).where(User.username == user_data["username"])
        res = await session.execute(stmt)
        existing = res.scalars().first()
        
        if not existing:
            hashed = hash_password(user_data["password"])
            db_user = User(
                username=user_data["username"],
                hashed_password=hashed,
                role=user_data["role"],
                display_name=user_data["display_name"]
            )
            session.add(db_user)
            logger.info(f"Created user: {user_data['username']}")
    await session.commit()

import re as _re
_GENERATED_POSTMORTEM_RE = _re.compile(
    r"^incident_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_postmortem$",
    _re.IGNORECASE,
)

async def seed_knowledge_base(session: AsyncSession, embedding_service: EmbeddingService):
    """Seed KB JSON files into kb_documents for semantic reranking and local grounding cache."""
    logger.info("Seeding local KB cache into database...")
    knowledge_dir = Path(settings.KNOWLEDGE_DIR)
    created = 0
    updated = 0
    skipped = 0
    
    categories = ["runbooks", "postmortems", "architecture_docs"]
    for category in categories:
        cat_dir = knowledge_dir / category
        if not cat_dir.exists():
            logger.warning(f"Category directory does not exist: {cat_dir}")
            continue
            
        for path in cat_dir.glob("*.json"):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    doc = json.load(f)

                if not isinstance(doc, dict):
                    logger.debug(f"Skipping non-document JSON file: {path.name}")
                    skipped += 1
                    continue

                doc_id = doc.get("id")
                if not doc_id:
                    logger.warning(f"Skipping KB document without id: {path.name}")
                    skipped += 1
                    continue

                # Skip auto-generated postmortems from runtime incidents — these
                # belong to specific incidents and should not be blindly re-seeded
                # on startup (they may reference already-deleted incidents).
                if _GENERATED_POSTMORTEM_RE.match(doc_id):
                    logger.debug(f"Skipping runtime-generated postmortem on seed: {doc_id}")
                    skipped += 1
                    continue

                title = doc.get("title", "")
                content = doc.get("content", "")
                tags = doc.get("tags", [])
                resolved_category = doc.get("category", "architecture" if category == "architecture_docs" else category[:-1])
                source_file = str(path.relative_to(knowledge_dir))
                
                # Check if already seeded
                stmt = select(KBDocument).where(KBDocument.id == doc_id)
                res = await session.execute(stmt)
                existing = res.scalars().first()

                if existing and (
                    existing.title == title
                    and existing.category == resolved_category
                    and existing.content == content
                    and existing.tags == tags
                    and existing.source_file == source_file
                ):
                    logger.debug(f"Document already up to date: {doc_id}")
                    skipped += 1
                    continue

                content_text = f"{title} {content} {' '.join(tags)}"
                logger.info(f"Computing embedding for document: {doc_id}")
                embedding = await embedding_service.embed(content_text)

                if existing:
                    existing.title = title
                    existing.category = resolved_category
                    existing.content = content
                    existing.tags = tags
                    existing.embedding = embedding
                    existing.source_file = source_file
                    updated += 1
                    logger.info(f"Updated KB document: {doc_id}")
                    continue

                db_doc = KBDocument(
                    id=doc_id,
                    title=title,
                    category=resolved_category,
                    content=content,
                    tags=tags,
                    embedding=embedding,
                    source_file=source_file
                )
                session.add(db_doc)
                created += 1
                logger.info(f"Seeded KB document: {doc_id}")
            except Exception as e:
                logger.error(f"Error seeding document {path}: {e}")
                
    await session.commit()
    logger.info(
        "KB cache sync complete. created=%s updated=%s skipped=%s",
        created,
        updated,
        skipped,
    )

async def seed_service_topology(session: AsyncSession):
    """Seed service dependency relations from topology file."""
    if not settings.ENABLE_SEED_SAMPLE_DATA:
        logger.info("Skipping sample topology seeding.")
        return
    logger.info("Seeding service topology...")
    topology_file = Path(settings.KNOWLEDGE_DIR) / "architecture_docs" / "service_topology.json"
    if not topology_file.exists():
        logger.warning(f"Topology file not found: {topology_file}")
        return
        
    try:
        with open(topology_file, "r", encoding="utf-8") as f:
            links = json.load(f)
            
        for link in links:
            # Check if exists
            stmt = select(ServiceTopology).where(
                (ServiceTopology.source == link["source"]) & 
                (ServiceTopology.target == link["target"])
            )
            res = await session.execute(stmt)
            existing = res.scalars().first()
            
            if not existing:
                db_link = ServiceTopology(
                    source=link["source"],
                    target=link["target"],
                    relationship_type=link.get("relationship_type", "http"),
                    is_critical=link.get("is_critical", True)
                )
                session.add(db_link)
                logger.info(f"Seeded topology relation: {link['source']} -> {link['target']}")
        await session.commit()
    except Exception as e:
        logger.error(f"Error seeding service topology: {e}")

async def seed_operational_context(session: AsyncSession):
    """Seed operational context events (calendar, teams chat, oncall)."""
    if not settings.ENABLE_SEED_SAMPLE_DATA:
        logger.info("Skipping sample operational context seeding.")
        return
    logger.info("Seeding operational events...")
    context_dir = Path(settings.KNOWLEDGE_DIR) / "work_iq_context"
    if not context_dir.exists():
        logger.warning(f"Operational context directory not found: {context_dir}")
        return
        
    files = ["calendar_events.json", "teams_messages.json", "oncall_roster.json"]
    for fn in files:
        path = context_dir / fn
        if not path.exists():
            logger.warning(f"Context file not found: {path}")
            continue
            
        try:
            with open(path, "r", encoding="utf-8") as f:
                events = json.load(f)
                
            for event in events:
                # Check for existing
                stmt = select(OperationalEvent).where(
                    (OperationalEvent.event_type == event["event_type"]) &
                    (OperationalEvent.title == event["title"]) &
                    (OperationalEvent.service_name == event.get("service_name"))
                )
                res = await session.execute(stmt)
                existing = res.scalars().first()
                
                if not existing:
                    event_time_str = event.get("event_time")
                    event_time = datetime.fromisoformat(event_time_str.replace("Z", "+00:00")) if event_time_str else datetime.now(timezone.utc)
                    
                    db_event = OperationalEvent(
                        event_type=event["event_type"],
                        service_name=event.get("service_name"),
                        title=event.get("title"),
                        content=event.get("content"),
                        author=event.get("author"),
                        event_time=event_time,
                        metadata_json=event.get("metadata_json", {})
                    )
                    session.add(db_event)
                    logger.info(f"Seeded operational event: {event['event_type']} - {event.get('title')}")
            await session.commit()
        except Exception as e:
            logger.error(f"Error seeding operational context from {path}: {e}")

async def run_seeder():
    """Main execution entry point for database seeder."""
    # Ensure database tables exist
    await init_db()
    
    # Initialize EmbeddingService
    embedding_service = EmbeddingService(settings)
    
    async with AsyncSessionLocal() as session:
        await seed_users(session)
        await seed_knowledge_base(session, embedding_service)
        await seed_service_topology(session)
        await seed_operational_context(session)
        logger.info("🎉 Database seeding completed successfully!")

if __name__ == "__main__":
    asyncio.run(run_seeder())
