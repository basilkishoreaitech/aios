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
        "QUERY 1 - azure functions key vault secret reference",
        "azure function app failing after deployment because key vault secret reference and managed identity access are broken",
    )
    await run_query(
        "QUERY 2 - aks jwks dns egress",
        "aks pods cannot fetch jwks endpoint due to dns or outbound egress failure token validation broken",
    )
    await run_query(
        "QUERY 3 - aws lambda vpc nat timeout",
        "aws lambda in private vpc timing out because nat gateway egress to jwks and partner api is missing",
    )


if __name__ == "__main__":
    asyncio.run(main())
