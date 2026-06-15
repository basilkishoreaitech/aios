"""
Read-only audit of local KB files versus Azure AI Search index contents.

Outputs:
- local document count by category
- indexed document count by category
- missing local documents that are not in the index
- extra indexed documents that do not exist locally

Usage:
    cd aios
    python scripts/audit_kb_index.py
"""

import asyncio
import json
import os
import sys
from collections import Counter
from pathlib import Path

import httpx
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
load_dotenv()

SEARCH_ENDPOINT = os.getenv("FOUNDRY_IQ_ENDPOINT", "").rstrip("/")
SEARCH_KEY = os.getenv("FOUNDRY_IQ_KEY", "")
INDEX_NAME = os.getenv("FOUNDRY_IQ_INDEX_NAME", "aios-kb")
API_VERSION = "2024-07-01"
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

CATEGORY_DIRS = {
    "runbooks": "runbook",
    "postmortems": "postmortem",
    "architecture_docs": "architecture",
}


def read_local_docs() -> dict[str, dict]:
    docs: dict[str, dict] = {}
    for dir_name, default_category in CATEGORY_DIRS.items():
        cat_dir = KNOWLEDGE_DIR / dir_name
        if not cat_dir.exists():
            continue
        for json_file in sorted(cat_dir.glob("*.json")):
            try:
                payload = json.loads(json_file.read_text(encoding="utf-8"))
            except Exception:
                continue
            if not isinstance(payload, dict):
                continue
            doc_id = payload.get("id")
            if not doc_id:
                continue
            docs[doc_id] = {
                "id": doc_id,
                "title": payload.get("title", ""),
                "category": payload.get("category", default_category),
                "source_file": f"{dir_name}/{json_file.name}",
            }
    return docs


async def read_index_docs() -> dict[str, dict]:
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"
    headers = {"api-key": SEARCH_KEY, "Content-Type": "application/json"}
    docs: dict[str, dict] = {}
    skip = 0
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            payload = {"search": "*", "top": 100, "skip": skip, "select": "id,title,category,source_file"}
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            items = response.json().get("value", [])
            if not items:
                break
            for item in items:
                doc_id = item.get("id")
                if not doc_id:
                    continue
                docs[doc_id] = {
                    "id": doc_id,
                    "title": item.get("title", ""),
                    "category": item.get("category", "unknown"),
                    "source_file": item.get("source_file", ""),
                }
            skip += len(items)
            if len(items) < 100:
                break
    return docs


async def main() -> None:
    if not SEARCH_ENDPOINT or not SEARCH_KEY or not INDEX_NAME:
        print("Missing FOUNDRY_IQ_ENDPOINT / FOUNDRY_IQ_KEY / FOUNDRY_IQ_INDEX_NAME in .env")
        raise SystemExit(1)

    local_docs = read_local_docs()
    index_docs = await read_index_docs()

    local_counts = Counter(doc["category"] for doc in local_docs.values())
    index_counts = Counter(doc["category"] for doc in index_docs.values())

    missing_from_index = sorted(set(local_docs) - set(index_docs))
    extra_in_index = sorted(set(index_docs) - set(local_docs))

    print("KB Audit")
    print(f"Local docs : {len(local_docs)}")
    print(f"Index docs : {len(index_docs)}")
    print("")
    print("Local by category:")
    for category, count in sorted(local_counts.items()):
        print(f"  {category}: {count}")
    print("Index by category:")
    for category, count in sorted(index_counts.items()):
        print(f"  {category}: {count}")

    print("")
    print(f"Missing from index: {len(missing_from_index)}")
    for doc_id in missing_from_index:
        doc = local_docs[doc_id]
        print(f"  - {doc_id} | {doc['category']} | {doc['source_file']}")

    print(f"Extra in index: {len(extra_in_index)}")
    for doc_id in extra_in_index:
        doc = index_docs[doc_id]
        print(f"  - {doc_id} | {doc['category']} | {doc['source_file']}")


if __name__ == "__main__":
    asyncio.run(main())
