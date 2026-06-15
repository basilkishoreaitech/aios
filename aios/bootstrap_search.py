"""
bootstrap_search.py — One-time setup for Azure AI Search index.
Creates the 'aios-kb' index and ingests all runbooks + postmortems from knowledge/.

Usage:
    python bootstrap_search.py
"""
import asyncio
import json
import os
import logging
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("bootstrap_search")

ENDPOINT = os.environ["FOUNDRY_IQ_ENDPOINT"].rstrip("/")
API_KEY = os.environ["FOUNDRY_IQ_KEY"]
INDEX_NAME = os.environ.get("FOUNDRY_IQ_INDEX_NAME", "aios-kb")
API_VERSION = "2024-07-01"
KNOWLEDGE_DIR = Path(__file__).parent / "knowledge"

HEADERS = {"api-key": API_KEY, "Content-Type": "application/json"}


INDEX_SCHEMA = {
    "name": INDEX_NAME,
    "fields": [
        {"name": "id",          "type": "Edm.String", "key": True,  "searchable": False, "filterable": True},
        {"name": "title",       "type": "Edm.String", "searchable": True, "filterable": False, "sortable": True},
        {"name": "content",     "type": "Edm.String", "searchable": True, "filterable": False},
        {"name": "category",    "type": "Edm.String", "searchable": True, "filterable": True,  "facetable": True},
        {"name": "source_file", "type": "Edm.String", "searchable": False, "filterable": False},
        {"name": "tags",        "type": "Collection(Edm.String)", "searchable": True, "filterable": True, "facetable": True},
    ],
}


async def create_or_update_index(client: httpx.AsyncClient) -> None:
    url = f"{ENDPOINT}/indexes/{INDEX_NAME}?api-version={API_VERSION}&allowIndexDowntime=true"
    response = await client.put(url, headers=HEADERS, json=INDEX_SCHEMA)
    if response.status_code in (200, 201):
        logger.info("Index '%s' created/updated successfully.", INDEX_NAME)
    else:
        logger.error("Failed to create index: %s — %s", response.status_code, response.text)
        response.raise_for_status()


async def upload_documents(client: httpx.AsyncClient, documents: list) -> None:
    if not documents:
        return
    url = f"{ENDPOINT}/indexes/{INDEX_NAME}/docs/index?api-version={API_VERSION}"
    batch = {"value": [{"@search.action": "mergeOrUpload", **doc} for doc in documents]}
    response = await client.post(url, headers=HEADERS, json=batch)
    if response.status_code in (200, 207):
        results = response.json().get("value", [])
        ok = sum(1 for r in results if r.get("status"))
        failed = [r for r in results if not r.get("status")]
        logger.info("  Uploaded %d docs OK, %d failed.", ok, len(failed))
        for f in failed:
            logger.warning("  Failed doc: %s — %s", f.get("key"), f.get("errorMessage"))
    else:
        logger.error("Upload failed: %s — %s", response.status_code, response.text)
        response.raise_for_status()


EXTRA_RUNBOOKS = [
    {
        "id": "runbook_jvm_heap_exhaustion",
        "title": "JVM Heap Exhaustion Diagnosis and Recovery",
        "content": (
            "JVM Heap Exhaustion Diagnosis and Recovery:\n\n"
            "### Symptoms\n"
            "- Service returns 503 or hangs; GC logs show 'java.lang.OutOfMemoryError: Java heap space'.\n"
            "- JVM GC overhead limit exceeded; CPU spike followed by pod restart.\n\n"
            "### Diagnosis\n"
            "1. Capture heap info: kubectl exec <pod> -- jcmd <pid> GC.heap_info\n"
            "2. Check GC logs for allocation rates and old-gen occupancy.\n"
            "3. Identify if heap grew after a recent deployment.\n\n"
            "### Safe Mitigation Steps\n"
            "Option A: Increase -Xmx JVM flag (e.g. -Xmx2g to -Xmx4g) in deployment env vars.\n"
            "Option B: Rolling restart to clear leaked objects if root cause unknown.\n"
            "Option C: Enable G1GC with -XX:+UseStringDeduplication if strings dominate heap.\n\n"
            "### Rollback Plan\n"
            "Redeploy previous image tag if heap usage returns to normal after rollback."
        ),
        "category": "runbook",
        "tags": ["jvm", "heap", "oom", "gc", "java", "memory"],
        "source_file": "synthetic/runbook_jvm_heap.json",
    },
    {
        "id": "runbook_payment_latency",
        "title": "Payment Service High Latency Diagnosis",
        "content": (
            "Payment Service High Latency Diagnosis:\n\n"
            "### Symptoms\n"
            "- p99 latency > 8 seconds on /checkout endpoint; timeout errors for customers.\n"
            "- Downstream payment gateway calls taking > 5 seconds.\n\n"
            "### Diagnosis\n"
            "1. Check distributed trace spans for the slow component.\n"
            "2. Review payment-gateway integration: retry policy, circuit breaker state.\n"
            "3. Look for sudden spike in transaction volume or large batch jobs running.\n\n"
            "### Safe Mitigation Steps\n"
            "Option A: Enable circuit breaker to fail fast instead of queueing.\n"
            "Option B: Reduce retry count from 5 to 2 for payment-gateway timeouts.\n"
            "Option C: Route traffic to backup payment provider if primary SLA breached.\n\n"
            "### Escalation\n"
            "If customer-facing transactions failing > 5 minutes, escalate to VP Payments immediately."
        ),
        "category": "runbook",
        "tags": ["payment", "latency", "timeout", "circuit-breaker", "checkout"],
        "source_file": "synthetic/runbook_payment_latency.json",
    },
    {
        "id": "runbook_dns_resolution",
        "title": "DNS Resolution Failure Recovery for Microservices",
        "content": (
            "DNS Resolution Failure Recovery:\n\n"
            "### Symptoms\n"
            "- Services returning 'Temporary failure in name resolution' or 'NXDOMAIN'.\n"
            "- Intermittent 502/503 errors; affects multiple downstream services.\n\n"
            "### Diagnosis\n"
            "1. kubectl exec into a pod: nslookup kubernetes.default.svc.cluster.local\n"
            "2. Check CoreDNS pods: kubectl get pods -n kube-system -l k8s-app=kube-dns\n"
            "3. Review CoreDNS ConfigMap for recent changes.\n\n"
            "### Safe Mitigation Steps\n"
            "Option A: Restart CoreDNS: kubectl rollout restart deploy/coredns -n kube-system\n"
            "Option B: Add ndots:2 to pod DNS config to reduce unnecessary lookups.\n"
            "Option C: Scale CoreDNS replicas from 2 to 4 if cluster DNS load is high.\n\n"
            "### Rollback Plan\n"
            "Revert CoreDNS ConfigMap to last known-good version."
        ),
        "category": "runbook",
        "tags": ["dns", "coredns", "kubernetes", "nxdomain", "network"],
        "source_file": "synthetic/runbook_dns.json",
    },
    {
        "id": "runbook_tls_certificate_renewal",
        "title": "TLS Certificate Expiry — Emergency Renewal Runbook",
        "content": (
            "TLS Certificate Emergency Renewal:\n\n"
            "### Symptoms\n"
            "- Browser shows 'NET::ERR_CERT_DATE_INVALID'; curl returns SSL error.\n"
            "- Certificate days_remaining < 7; monitoring alert fired.\n\n"
            "### Diagnosis\n"
            "1. Check cert expiry: openssl s_client -connect <host>:443 </dev/null | openssl x509 -noout -dates\n"
            "2. Check cert-manager CertificateRequest status in Kubernetes.\n\n"
            "### Safe Mitigation Steps\n"
            "Option A (cert-manager): kubectl annotate certificate <name> cert-manager.io/issue-temporary-certificate=true\n"
            "Option B (manual): Request new cert from CA, update Kubernetes secret, restart ingress controller.\n"
            "Option C: Enable Let's Encrypt auto-renewal via cert-manager ACME issuer.\n\n"
            "### Escalation\n"
            "Certificate renewal must complete within 4 hours of expiry alert to avoid customer impact."
        ),
        "category": "runbook",
        "tags": ["tls", "certificate", "ssl", "cert-manager", "expiry", "https"],
        "source_file": "synthetic/runbook_tls.json",
    },
    {
        "id": "runbook_k8s_oom_recovery",
        "title": "Kubernetes OOMKill Recovery — Pod Memory Limit Exceeded",
        "content": (
            "Kubernetes OOMKill Recovery:\n\n"
            "### Symptoms\n"
            "- kubectl get pods shows CrashLoopBackOff; events show OOMKilled exit code 137.\n"
            "- Container memory usage hit the configured limit repeatedly.\n\n"
            "### Diagnosis\n"
            "1. kubectl describe pod <pod-name> — look for OOMKilled in Last State.\n"
            "2. kubectl top pods — check current memory consumption.\n"
            "3. Review if recent deployment increased memory footprint.\n\n"
            "### Safe Mitigation Steps\n"
            "Option A: Increase memory limits in Deployment spec (resources.limits.memory).\n"
            "Option B: Add Vertical Pod Autoscaler to auto-tune resource requests/limits.\n"
            "Option C: Profile application for memory leaks and roll back if recent deploy is culprit.\n\n"
            "### Rollback Plan\n"
            "kubectl rollout undo deployment/<name> to restore prior resource config."
        ),
        "category": "runbook",
        "tags": ["kubernetes", "oom", "oomkill", "memory", "limits", "crashloop"],
        "source_file": "synthetic/runbook_k8s_oom.json",
    },
    {
        "id": "postmortem_cascading_failure_6023",
        "title": "Postmortem - Incident #6023: Cascading Failure from DB Overload",
        "content": (
            "Postmortem - Incident #6023: Cascading Failure from DB Overload\n\n"
            "### Incident Summary\n"
            "On April 22, a slow query on db-service caused connection exhaustion, cascading to order-service, "
            "inventory-service, and api-gateway going offline for 72 minutes.\n\n"
            "### Root Cause\n"
            "A missing index on the orders table caused full-table scans under peak load. "
            "This saturated the DB connection pool, creating a deadlock cascade across dependent services.\n\n"
            "### Resolution\n"
            "DBA team created the missing index online (CREATE INDEX CONCURRENTLY). "
            "Connection pools were reset. Circuit breakers were manually tripped to shed load.\n\n"
            "### Action Items\n"
            "- Add query performance monitoring to alert on table scans > 1M rows.\n"
            "- Implement circuit breakers on all DB-dependent services.\n"
            "- Require index review as part of schema migration checklist."
        ),
        "category": "postmortem",
        "tags": ["cascading", "database", "index", "deadlock", "circuit-breaker", "order-service"],
        "source_file": "synthetic/postmortem_cascading.json",
    },
]


def load_knowledge_documents() -> list:
    docs = []
    categories = [("runbooks", "runbook"), ("postmortems", "postmortem")]
    for folder, category_label in categories:
        cat_dir = KNOWLEDGE_DIR / folder
        if not cat_dir.exists():
            logger.warning("Folder not found: %s", cat_dir)
            continue
        for path in sorted(cat_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
                doc = {
                    "id": raw["id"],
                    "title": raw.get("title", path.stem),
                    "content": raw.get("content", json.dumps(raw)),
                    "category": raw.get("category", category_label),
                    "source_file": str(path.relative_to(KNOWLEDGE_DIR)),
                    "tags": raw.get("tags", []),
                }
                docs.append(doc)
                logger.info("  Loaded: %s", doc["id"])
            except Exception as e:
                logger.warning("  Skipped %s: %s", path.name, e)

    # Architecture docs — convert edge list to searchable text
    arch_dir = KNOWLEDGE_DIR / "architecture_docs"
    if arch_dir.exists():
        for path in sorted(arch_dir.glob("*.json")):
            try:
                with open(path, encoding="utf-8") as f:
                    raw = json.load(f)
                if isinstance(raw, list):
                    lines = ["Service dependency topology:"]
                    for edge in raw:
                        lines.append(
                            f"  {edge.get('source','?')} -> {edge.get('target','?')}"
                            f" [{edge.get('relationship_type','?')}]"
                            f"{'  CRITICAL' if edge.get('is_critical') else ''}"
                        )
                    content = "\n".join(lines)
                    doc_id = path.stem
                    title = "Service Topology — Dependency Map"
                else:
                    content = raw.get("content", json.dumps(raw))
                    doc_id = raw.get("id", path.stem)
                    title = raw.get("title", path.stem)
                docs.append({
                    "id": doc_id,
                    "title": title,
                    "content": content,
                    "category": "architecture",
                    "tags": ["topology", "dependencies", "services", "microservices"],
                    "source_file": str(path.relative_to(KNOWLEDGE_DIR)),
                })
                logger.info("  Loaded architecture: %s", doc_id)
            except Exception as e:
                logger.warning("  Skipped %s: %s", path.name, e)

    # Synthetic extras for broader coverage
    docs += EXTRA_RUNBOOKS
    for d in EXTRA_RUNBOOKS:
        logger.info("  Loaded synthetic: %s", d["id"])

    return docs


async def main() -> None:
    async with httpx.AsyncClient(timeout=60.0) as client:
        logger.info("=== Creating / updating Azure AI Search index '%s' ===", INDEX_NAME)
        await create_or_update_index(client)

        logger.info("=== Loading knowledge documents from knowledge/ ===")
        docs = load_knowledge_documents()
        logger.info("Total documents to ingest: %d", len(docs))

        if docs:
            logger.info("=== Uploading documents to Azure AI Search ===")
            # Upload in batches of 100
            batch_size = 100
            for i in range(0, len(docs), batch_size):
                batch = docs[i : i + batch_size]
                logger.info("Uploading batch %d-%d...", i + 1, i + len(batch))
                await upload_documents(client, batch)

        logger.info("=== Verifying index document count ===")
        count_url = f"{ENDPOINT}/indexes/{INDEX_NAME}/docs/$count?api-version={API_VERSION}"
        r = await client.get(count_url, headers=HEADERS)
        if r.status_code == 200:
            logger.info("Index '%s' now contains %s documents.", INDEX_NAME, r.text.strip())
        else:
            logger.warning("Could not get count: %s", r.text)

        logger.info("=== Verifying index with sample search ===")
        search_url = f"{ENDPOINT}/indexes/{INDEX_NAME}/docs/search?api-version={API_VERSION}"
        r2 = await client.post(search_url, headers=HEADERS, json={"search": "database connection pool", "top": 3, "select": "id,title,category"})
        if r2.status_code == 200:
            hits = r2.json().get("value", [])
            for h in hits:
                logger.info("  hit: [%s] %s", h.get("category","?"), h.get("title","?"))
        else:
            logger.warning("Verification search failed: %s", r2.text)

    logger.info("Done. Azure AI Search index is ready.")


if __name__ == "__main__":
    asyncio.run(main())
