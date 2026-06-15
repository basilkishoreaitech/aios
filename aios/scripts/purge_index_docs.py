import asyncio
import os

import httpx
from dotenv import load_dotenv

load_dotenv()

IDS = [
    "postmortem_cascading_failure_6023",
    "runbook_dns_resolution",
    "runbook_jvm_heap_exhaustion",
    "runbook_k8s_oom_recovery",
    "runbook_payment_latency",
    "runbook_tls_certificate_renewal",
    "service_topology",
]


async def main() -> None:
    endpoint = os.getenv("FOUNDRY_IQ_ENDPOINT", "").rstrip("/")
    key = os.getenv("FOUNDRY_IQ_KEY", "")
    index = os.getenv("FOUNDRY_IQ_INDEX_NAME", "aios-kb")
    url = f"{endpoint}/indexes/{index}/docs/index?api-version=2024-07-01"
    headers = {"api-key": key, "Content-Type": "application/json"}
    payload = {"value": [{"@search.action": "delete", "id": doc_id} for doc_id in IDS]}

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=headers, json=payload)
        print(response.status_code)
        print(response.text)


if __name__ == "__main__":
    asyncio.run(main())
