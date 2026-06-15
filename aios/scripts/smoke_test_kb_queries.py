import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

from config import settings
from database import AsyncSessionLocal
from services.embedding_service import EmbeddingService


async def run_query(label: str, query: str) -> None:
    service = EmbeddingService(settings)
    async with AsyncSessionLocal() as session:
        docs = await service.search_kb(session, query, top_k=5, threshold=0.20)
        print(label)
        if not docs:
            print("  NO RESULTS")
            return
        for doc in docs:
            print(f"  {doc.doc_id} | {doc.title} | {doc.relevance:.2f}")


async def main() -> None:
    await run_query(
        "QUERY 1 - lambda timeout / postgres lock contention",
        "lm-lambda timeout after 10 minutes waiting on postgres lock contention",
    )
    await run_query(
        "QUERY 2 - ecs draining / health check failure",
        "ecs fargate tasks draining every 10 seconds target group health check failed",
    )


if __name__ == "__main__":
    asyncio.run(main())
