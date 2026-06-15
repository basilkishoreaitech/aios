"""
Bulk-sync all local KB JSON documents into the kb_documents table.

This keeps semantic fallback aligned with the Azure AI Search index so search_kb()
can use both lexical search (Azure Search) and semantic reranking (DB embeddings).
"""

import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

from database import AsyncSessionLocal
from models.database import KBDocument
from services.embedding_service import EmbeddingService
from config import settings

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"
CATEGORY_DIRS = {
    "runbooks": "runbook",
    "postmortems": "postmortem",
    "architecture_docs": "architecture",
}


def read_local_docs() -> list[dict]:
    docs: list[dict] = []
    for dir_name, default_category in CATEGORY_DIRS.items():
        cat_dir = KNOWLEDGE_DIR / dir_name
        if not cat_dir.exists():
            continue
        for json_file in sorted(cat_dir.glob("*.json")):
            payload = json.loads(json_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                continue
            doc_id = payload.get("id")
            if not doc_id:
                continue
            docs.append(
                {
                    "id": doc_id,
                    "title": payload.get("title", ""),
                    "category": payload.get("category", default_category),
                    "content": payload.get("content", ""),
                    "tags": payload.get("tags", []),
                    "source_file": f"{dir_name}/{json_file.name}",
                }
            )
    return docs


async def main() -> None:
    docs = read_local_docs()
    service = EmbeddingService(settings)

    created = 0
    updated = 0

    async with AsyncSessionLocal() as session:
        for doc in docs:
            stmt = select(KBDocument).where(KBDocument.id == doc["id"])
            existing = (await session.execute(stmt)).scalars().first()
            content_text = f"{doc['title']} {doc['content']} {' '.join(doc.get('tags', []))}"
            embedding = await service.embed(content_text)

            if existing:
                existing.title = doc["title"]
                existing.category = doc["category"]
                existing.content = doc["content"]
                existing.tags = doc["tags"]
                existing.embedding = embedding
                existing.source_file = doc["source_file"]
                updated += 1
            else:
                session.add(
                    KBDocument(
                        id=doc["id"],
                        title=doc["title"],
                        category=doc["category"],
                        content=doc["content"],
                        tags=doc["tags"],
                        embedding=embedding,
                        source_file=doc["source_file"],
                    )
                )
                created += 1

        await session.commit()

    print(f"KB DB sync complete. Created={created} Updated={updated} Total={len(docs)}")


if __name__ == "__main__":
    asyncio.run(main())
