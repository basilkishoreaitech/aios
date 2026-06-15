"""
sync_kb_to_search.py
====================
Bulk-uploads ALL local KB documents (runbooks/, postmortems/, architecture_docs/)
to the Azure AI Search index defined by FOUNDRY_IQ_* env vars.

Skips documents already present in the index (idempotent).

Usage:
    cd aios
    python scripts/sync_kb_to_search.py
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

# Add aios/ to path so config + services resolve
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger("sync_kb")

# ---------------------------------------------------------------------------
# Config from env (same vars as .env)
# ---------------------------------------------------------------------------
SEARCH_ENDPOINT = os.getenv("FOUNDRY_IQ_ENDPOINT", "").rstrip("/")
SEARCH_KEY      = os.getenv("FOUNDRY_IQ_KEY", "")
INDEX_NAME      = os.getenv("FOUNDRY_IQ_INDEX_NAME", "aios-kb")
API_VERSION     = "2024-07-01"

KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"

CATEGORY_DIRS = {
    "runbooks":         "runbook",
    "postmortems":      "postmortem",
    "architecture_docs": "architecture",
}


# ---------------------------------------------------------------------------
# Azure AI Search helpers
# ---------------------------------------------------------------------------
async def get_indexed_ids(client: httpx.AsyncClient) -> set[str]:
    """Return the set of all doc IDs currently in the search index."""
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"
    headers = {"api-key": SEARCH_KEY, "Content-Type": "application/json"}
    skip = 0
    all_ids: set[str] = set()
    while True:
        payload = {"search": "*", "top": 100, "skip": skip, "select": "id"}
        r = await client.post(url, headers=headers, json=payload)
        r.raise_for_status()
        items = r.json().get("value", [])
        if not items:
            break
        for item in items:
            all_ids.add(item["id"])
        skip += len(items)
        if len(items) < 100:
            break
    return all_ids


async def upload_batch(client: httpx.AsyncClient, documents: list[dict]) -> None:
    """Upload a batch of documents to the index (mergeOrUpload)."""
    if not documents:
        return
    url = f"{SEARCH_ENDPOINT}/indexes/{INDEX_NAME}/docs/index?api-version={API_VERSION}"
    headers = {"api-key": SEARCH_KEY, "Content-Type": "application/json"}
    payload = {
        "value": [
            {
                "@search.action": "mergeOrUpload",
                "id": d["id"],
                "title": d.get("title", ""),
                "content": d.get("content", ""),
                "category": d.get("category", ""),
                "tags": d.get("tags", []),
                "source_file": d.get("source_file", ""),
            }
            for d in documents
        ]
    }
    r = await client.post(url, headers=headers, json=payload)
    if r.status_code not in (200, 207):
        logger.error("Upload failed %s: %s", r.status_code, r.text[:300])
        r.raise_for_status()
    results = r.json().get("value", [])
    for res in results:
        status = res.get("status")
        doc_id = res.get("key")
        if not status:
            logger.error("  FAILED  %s — %s", doc_id, res.get("errorMessage"))
        else:
            logger.info("  ✓ uploaded  %s", doc_id)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
async def main() -> None:
    if not SEARCH_ENDPOINT or not SEARCH_KEY or not INDEX_NAME:
        logger.error("Missing FOUNDRY_IQ_ENDPOINT / FOUNDRY_IQ_KEY / FOUNDRY_IQ_INDEX_NAME in .env")
        sys.exit(1)

    logger.info("Azure AI Search endpoint : %s", SEARCH_ENDPOINT)
    logger.info("Index                    : %s", INDEX_NAME)
    logger.info("Knowledge dir            : %s", KNOWLEDGE_DIR)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # 1. Fetch IDs already in the index
        indexed_ids = await get_indexed_ids(client)
        logger.info("Documents already in index: %d", len(indexed_ids))

        # 2. Walk every category directory and collect local docs
        to_upload: list[dict] = []
        skipped = 0

        for dir_name, category in CATEGORY_DIRS.items():
            cat_dir = KNOWLEDGE_DIR / dir_name
            if not cat_dir.exists():
                logger.warning("Directory not found, skipping: %s", cat_dir)
                continue

            for json_file in sorted(cat_dir.glob("*.json")):
                try:
                    doc = json.loads(json_file.read_text(encoding="utf-8"))
                except Exception as exc:
                    logger.error("Cannot parse %s: %s", json_file, exc)
                    continue

                # Skip files that are arrays (e.g. topology link lists) — not KB documents
                if not isinstance(doc, dict):
                    logger.debug("Skipping non-document JSON array: %s", json_file.name)
                    continue

                doc_id = doc.get("id")
                if not doc_id:
                    logger.warning("No 'id' field in %s — skipping", json_file.name)
                    continue

                if doc_id in indexed_ids:
                    logger.debug("Already indexed, skip: %s", doc_id)
                    skipped += 1
                    continue

                # Ensure category is set
                if "category" not in doc:
                    doc["category"] = category

                doc["source_file"] = f"{dir_name}/{json_file.name}"
                to_upload.append(doc)
                logger.info("  queued : %s — %s", doc_id, doc.get("title", "")[:60])

        logger.info("")
        logger.info("Already indexed: %d   To upload: %d", skipped, len(to_upload))

        if not to_upload:
            logger.info("Nothing to upload. Index is up to date.")
            return

        # 3. Upload in batches of 10 (Search API batch limit is 1000 docs, 16 MB)
        batch_size = 10
        for i in range(0, len(to_upload), batch_size):
            batch = to_upload[i : i + batch_size]
            logger.info("Uploading batch %d–%d ...", i + 1, i + len(batch))
            await upload_batch(client, batch)

    logger.info("")
    logger.info("Sync complete. Total uploaded: %d", len(to_upload))


if __name__ == "__main__":
    asyncio.run(main())
