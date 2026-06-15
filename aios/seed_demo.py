"""
seed_demo.py — Seeds historical mock incidents into the DB for demo/testing.
Produces 10 realistic resolved incidents spanning the alert scenarios.

Usage:
    python seed_demo.py
"""
import asyncio
import json
import os
import uuid
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()
os.chdir(os.path.dirname(os.path.abspath(__file__)))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("seed_demo")

from database import AsyncSessionLocal, init_db
from models.database import Incident, AgentTrace, ActionItem
from sqlalchemy import select

NOW = datetime.now(timezone.utc)

MOCK_INCIDENTS = [
    {
        "id": "inc-demo-001",
        "title": "SEV-1: Database Connection Pool Exhaustion — api-gateway-prod",
        "service_name": "api-gateway-prod",
        "severity": "SEV-1",
        "status": "resolved",
        "raw_alert": json.dumps({"alert_name": "ConnectionPoolExhausted", "service": "api-gateway-prod", "details": "QueuePool limit of size 5 overflow 10 reached"}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "Recent v2.3 deployment introduced unclosed DB transactions", "confidence": 0.91, "supporting_evidence": ["Pool exhaustion began 4min after deploy", "pg_stat_activity shows 34 idle-in-transaction sessions"]},
            {"rank": 2, "hypothesis": "Traffic spike exceeded baseline pool sizing", "confidence": 0.42, "supporting_evidence": ["P99 latency +320ms", "But RPS only 1.2x baseline"]}
        ],
        "risk_assessment": {"overall_risk": "high", "blast_radius": "All API consumers", "estimated_impact": "~$28k/hr revenue at risk"},
        "action_plan": {"actions": [{"action": "Increase DATABASE_POOL_SIZE to 20", "risk_tag": "auto_approve", "risk_level": "low"}, {"action": "Kill idle-in-transaction sessions older than 5min", "risk_tag": "approval_required", "risk_level": "medium"}]},
        "engineer_view": "Root cause: v2.3 introduced async context manager misuse in `/api/checkout` — transactions not closed on timeout. Immediate fix: revert to v2.2 or hot-patch connection cleanup. Pool increase buys ~15min headroom.",
        "executive_view": "Payment API is degraded. Engineering has identified the root cause in the last deployment. Remediation in progress — ETA 12 minutes to resolution. Revenue impact: ~$28k/hr.",
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.05,
        "review_cycles": 1,
        "actual_root_cause": "Unclosed DB transactions in v2.3 checkout service caused pool exhaustion",
        "accuracy_score": 0.94,
        "resolved_by": "admin",
        "pipeline_duration_ms": 8420,
        "model_used": "gpt-5.4",
        "total_tokens": 14200,
        "created_at": NOW - timedelta(days=5, hours=3),
        "resolved_at": NOW - timedelta(days=5, hours=2, minutes=48),
    },
    {
        "id": "inc-demo-002",
        "title": "SEV-2: Memory Leak — payment-processor-prod gradual heap growth",
        "service_name": "payment-processor-prod",
        "severity": "SEV-2",
        "status": "resolved",
        "raw_alert": json.dumps({"alert_name": "HighMemoryUsage", "service": "payment-processor-prod", "details": "Heap usage at 87% — growing 2MB/min"}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "Unbounded cache in stripe-integration library (v4.1.2 regression)", "confidence": 0.88, "supporting_evidence": ["Heap dump shows 3.2GB in HashMap entries", "Issue filed in stripe-java v4.1.2 changelog"]},
            {"rank": 2, "hypothesis": "Event listener not deregistered on session close", "confidence": 0.55, "supporting_evidence": ["15k+ registered listeners in JVM heap"]}
        ],
        "risk_assessment": {"overall_risk": "medium", "blast_radius": "Payment processing", "estimated_impact": "OOM crash within ~2 hours if unmitigated"},
        "action_plan": {"actions": [{"action": "Rolling restart of payment-processor pods", "risk_tag": "approval_required", "risk_level": "medium"}, {"action": "Pin stripe-integration to v4.1.1", "risk_tag": "approval_required", "risk_level": "low"}]},
        "engineer_view": "Memory leak traced to stripe-java v4.1.2 regression. Rolled back to v4.1.1, restarted 3 pods with zero payment failures (circuit breaker active during restart).",
        "executive_view": "Payment processing fully healthy. Memory issue resolved via dependency rollback. No customer impact — circuit breaker handled failover transparently.",
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.03,
        "review_cycles": 2,
        "actual_root_cause": "stripe-java v4.1.2 regression: unbounded response cache",
        "accuracy_score": 0.91,
        "resolved_by": "engineer",
        "pipeline_duration_ms": 11350,
        "model_used": "gpt-5.4",
        "total_tokens": 18900,
        "created_at": NOW - timedelta(days=4, hours=1),
        "resolved_at": NOW - timedelta(days=3, hours=22),
    },
    {
        "id": "inc-demo-003",
        "title": "SEV-1: Payment API P99 Latency Spike — checkout-service",
        "service_name": "checkout-service",
        "severity": "SEV-1",
        "status": "resolved",
        "raw_alert": json.dumps({"alert_name": "HighP99Latency", "service": "checkout-service", "details": "P99 latency 4200ms (SLO: 500ms). 12% error rate."}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "Downstream payment-gateway-external saturated — circuit breaker not tripping", "confidence": 0.87, "supporting_evidence": ["payment-gateway-external P99: 6800ms", "Circuit breaker threshold set to 10s — too high"]},
            {"rank": 2, "hypothesis": "Database read replica lag causing checkout query stalls", "confidence": 0.61, "supporting_evidence": ["Read replica lag: 8.3s", "Checkout queries routing to replica by default"]}
        ],
        "risk_assessment": {"overall_risk": "critical", "blast_radius": "All checkout flows", "estimated_impact": "~$95k/hr conversion loss"},
        "action_plan": {"actions": [{"action": "Force checkout queries to primary DB", "risk_tag": "auto_approve", "risk_level": "low"}, {"action": "Lower circuit breaker threshold to 2s", "risk_tag": "approval_required", "risk_level": "medium"}]},
        "engineer_view": "Dual root cause: replica lag + permissive circuit breaker. Switched checkout to primary. CB threshold lowered to 2s. P99 dropped to 180ms within 90 seconds.",
        "executive_view": "Checkout fully restored. Dual issue identified and fixed. Revenue impact: ~22 min at degraded state. Postmortem scheduled for Tue.",
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.07,
        "review_cycles": 1,
        "actual_root_cause": "Read replica lag + permissive circuit breaker allowed cascade",
        "accuracy_score": 0.89,
        "resolved_by": "admin",
        "pipeline_duration_ms": 9870,
        "model_used": "gpt-5.4",
        "total_tokens": 21400,
        "created_at": NOW - timedelta(days=3, hours=6),
        "resolved_at": NOW - timedelta(days=3, hours=5, minutes=38),
    },
    {
        "id": "inc-demo-004",
        "title": "SEV-2: JVM Heap OOM — inventory-service",
        "service_name": "inventory-service",
        "severity": "SEV-2",
        "status": "resolved",
        "raw_alert": json.dumps({"alert_name": "JVMHeapCritical", "service": "inventory-service", "details": "JVM heap 95%, full GC pauses 12s, 3 pods OOM-killed"}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "Bulk inventory sync job holding large object graphs in memory", "confidence": 0.93, "supporting_evidence": ["Heap dump: 4.1GB in inventory batch objects", "Job started 40min before incident", "No streaming — full dataset loaded"]},
        ],
        "risk_assessment": {"overall_risk": "medium", "blast_radius": "Inventory reads and order validation", "estimated_impact": "Order validation degraded"},
        "action_plan": {"actions": [{"action": "Cancel running batch sync job", "risk_tag": "auto_approve", "risk_level": "low"}, {"action": "Restart OOM-killed pods", "risk_tag": "auto_approve", "risk_level": "low"}, {"action": "Patch batch job to use streaming cursor", "risk_tag": "approval_required", "risk_level": "low"}]},
        "engineer_view": "Batch inventory sync loading 2.8M SKUs into memory. Job cancelled, pods restarted, heap normalised to 42% in 4min. Engineering patching sync to use DB cursor streaming.",
        "executive_view": "Inventory service restored. Root cause: scheduled batch job design flaw. Permanent fix in progress — ETA 2 days.",
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.02,
        "review_cycles": 1,
        "actual_root_cause": "Inventory batch job loaded full dataset into JVM heap without streaming",
        "accuracy_score": 0.96,
        "resolved_by": "engineer",
        "pipeline_duration_ms": 7600,
        "model_used": "gpt-5.4",
        "total_tokens": 12800,
        "created_at": NOW - timedelta(days=2, hours=14),
        "resolved_at": NOW - timedelta(days=2, hours=13, minutes=52),
    },
    {
        "id": "inc-demo-005",
        "title": "SEV-2: Cascading Failure — order-service → inventory-service → auth-service",
        "service_name": "order-service",
        "severity": "SEV-2",
        "status": "resolved",
        "raw_alert": json.dumps({"alert_name": "CascadingDependencyFailure", "service": "order-service", "details": "503 rate: 34%. Root: inventory-service timeout propagating up"}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "inventory-service degradation cascading via synchronous call chain (no timeout/bulkhead)", "confidence": 0.95, "supporting_evidence": ["All 503s trace to inventory calls", "No timeout set on inventory HTTP client", "Thread pool exhausted by hanging requests"]},
        ],
        "risk_assessment": {"overall_risk": "high", "blast_radius": "Order creation + auth token refresh", "estimated_impact": "~$42k/hr"},
        "action_plan": {"actions": [{"action": "Set HTTP timeout on inventory client to 800ms", "risk_tag": "auto_approve", "risk_level": "low"}, {"action": "Enable bulkhead isolation for inventory dependency", "risk_tag": "approval_required", "risk_level": "medium"}]},
        "engineer_view": "Classic cascading failure from missing timeout. Remediated with emergency config push (timeout: 800ms). Bulkhead isolation added to prevent recurrence.",
        "executive_view": "Order creation restored. Cascading failure contained within 18 minutes. Architecture hardening underway.",
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.01,
        "review_cycles": 1,
        "actual_root_cause": "Missing HTTP timeout on inventory-service client caused thread pool exhaustion and cascade",
        "accuracy_score": 0.97,
        "resolved_by": "admin",
        "pipeline_duration_ms": 10200,
        "model_used": "gpt-5.4",
        "total_tokens": 19600,
        "created_at": NOW - timedelta(days=1, hours=20),
        "resolved_at": NOW - timedelta(days=1, hours=19, minutes=42),
    },
    {
        "id": "inc-demo-006",
        "title": "SEV-3: DNS Resolution Failures — notification-service",
        "service_name": "notification-service",
        "severity": "SEV-3",
        "status": "resolved",
        "raw_alert": json.dumps({"alert_name": "DNSResolutionFailure", "service": "notification-service", "details": "NXDOMAIN errors 18% of requests to email-relay.internal"}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "Kubernetes CoreDNS cache stale after internal service rename", "confidence": 0.84, "supporting_evidence": ["email-relay.internal renamed to smtp-relay.internal 2h ago", "CoreDNS TTL: 30s but negative cache holding NXDOMAIN for 300s"]}
        ],
        "risk_assessment": {"overall_risk": "low", "blast_radius": "Email notifications only", "estimated_impact": "Delayed order confirmation emails"},
        "action_plan": {"actions": [{"action": "Update notification-service config to smtp-relay.internal", "risk_tag": "auto_approve", "risk_level": "low"}, {"action": "Flush CoreDNS negative cache", "risk_tag": "auto_approve", "risk_level": "low"}]},
        "engineer_view": "Config mismatch after service rename. Updated endpoint reference and flushed DNS cache. Email delivery normalised.",
        "executive_view": "Email notifications delayed ~40 minutes for a subset of orders. Now resolved. No orders lost.",
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.04,
        "review_cycles": 1,
        "actual_root_cause": "Service rename without updating consumer config + CoreDNS negative cache TTL",
        "accuracy_score": 0.88,
        "resolved_by": "engineer",
        "pipeline_duration_ms": 5900,
        "model_used": "gpt-5.4-mini",
        "total_tokens": 9400,
        "created_at": NOW - timedelta(hours=18),
        "resolved_at": NOW - timedelta(hours=17, minutes=30),
    },
    {
        "id": "inc-demo-007",
        "title": "SEV-1: TLS Certificate Expiry — api-gateway-prod",
        "service_name": "api-gateway-prod",
        "severity": "SEV-1",
        "status": "resolved",
        "raw_alert": json.dumps({"alert_name": "TLSCertExpired", "service": "api-gateway-prod", "details": "SSL certificate for api.company.com expired 14 minutes ago. All HTTPS traffic failing."}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "Certificate auto-renewal job failed silently 30 days ago — cert expired today", "confidence": 0.99, "supporting_evidence": ["cert expiry: 2026-06-12T03:00:00Z", "Renewal cron last run: 2026-05-13 — exit code 1, no alert configured"]}
        ],
        "risk_assessment": {"overall_risk": "critical", "blast_radius": "100% HTTPS external traffic", "estimated_impact": "Complete service outage for external users"},
        "action_plan": {"actions": [{"action": "Issue new certificate via Let's Encrypt emergency renewal", "risk_tag": "auto_approve", "risk_level": "low"}, {"action": "Deploy updated cert to api-gateway-prod", "risk_tag": "approval_required", "risk_level": "medium"}]},
        "engineer_view": "Emergency cert renewed and deployed in 11 minutes. Root cause: renewal cron silently failing for 30 days with no alerting on cron exit codes. Fix: add cron failure alerting + 30-day expiry warning.",
        "executive_view": "API fully restored. 14-minute outage from expired TLS cert. Prevention measures in place.",
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.01,
        "review_cycles": 1,
        "actual_root_cause": "TLS cert auto-renewal cron silently failing — no alerting on failure",
        "accuracy_score": 0.99,
        "resolved_by": "admin",
        "pipeline_duration_ms": 6100,
        "model_used": "gpt-5.4",
        "total_tokens": 11200,
        "created_at": NOW - timedelta(hours=10),
        "resolved_at": NOW - timedelta(hours=9, minutes=49),
    },
    {
        "id": "inc-demo-008",
        "title": "SEV-2: Kubernetes OOM Kill — recommendation-engine",
        "service_name": "recommendation-engine",
        "severity": "SEV-2",
        "status": "resolved",
        "raw_alert": json.dumps({"alert_name": "K8sOOMKilled", "service": "recommendation-engine", "details": "Pod OOM killed 4x in 30min. Memory limit: 2Gi. ML model inference exceeding limit."}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "ML model updated to larger variant (v3 → v4) without updating K8s memory limits", "confidence": 0.92, "supporting_evidence": ["Model v4 deployed yesterday", "Model v4 footprint: 3.1Gi vs v3: 1.4Gi", "Memory limit unchanged at 2Gi"]}
        ],
        "risk_assessment": {"overall_risk": "medium", "blast_radius": "Product recommendation API", "estimated_impact": "Degraded recommendation quality (fallback to static)"},
        "action_plan": {"actions": [{"action": "Increase K8s memory limit to 4Gi", "risk_tag": "approval_required", "risk_level": "low"}, {"action": "Rollback to model v3 as interim", "risk_tag": "auto_approve", "risk_level": "low"}]},
        "engineer_view": "Memory limit not updated for model v4 upgrade. Rolled back to v3 immediately. Memory limits updated to 4Gi + 20% headroom for v4 redeployment.",
        "executive_view": "Recommendations degraded for ~35min (static fallback served). Now fully restored with improved model.",
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.03,
        "review_cycles": 1,
        "actual_root_cause": "ML model v4 memory footprint 2.2x v3 — K8s limits not updated with model upgrade",
        "accuracy_score": 0.94,
        "resolved_by": "engineer",
        "pipeline_duration_ms": 8800,
        "model_used": "gpt-5.4",
        "total_tokens": 13500,
        "created_at": NOW - timedelta(hours=6),
        "resolved_at": NOW - timedelta(hours=5, minutes=25),
    },
    {
        "id": "inc-demo-009",
        "title": "SEV-2: Disk I/O Saturation — analytics-pipeline",
        "service_name": "analytics-pipeline",
        "severity": "SEV-2",
        "status": "investigating",
        "raw_alert": json.dumps({"alert_name": "DiskIOSaturation", "service": "analytics-pipeline", "details": "Disk I/O wait: 94%. Write throughput: 180MB/s (limit: 200MB/s). Pipeline stalling."}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "Daily analytics export job and real-time stream processor contending for same disk", "confidence": 0.79, "supporting_evidence": ["Export job started 20min before saturation", "Both processes writing to /data/analytics/", "No I/O priority separation"]}
        ],
        "risk_assessment": {"overall_risk": "medium", "blast_radius": "Analytics dashboards and reporting", "estimated_impact": "Analytics data 20-40min delayed"},
        "action_plan": {"actions": [{"action": "Throttle export job I/O with ionice", "risk_tag": "auto_approve", "risk_level": "low"}, {"action": "Separate export job to dedicated volume", "risk_tag": "approval_required", "risk_level": "medium"}]},
        "engineer_view": "I/O contention between batch export and streaming ingestion. Applying ionice throttling on export job now.",
        "executive_view": "Analytics dashboards delayed. Engineering actively remediating. No production data loss.",
        "reviewer_verdict": "challenged",
        "reviewer_confidence_delta": -0.08,
        "review_cycles": 2,
        "actual_root_cause": None,
        "accuracy_score": None,
        "resolved_by": None,
        "pipeline_duration_ms": 12300,
        "model_used": "gpt-5.4",
        "total_tokens": 17800,
        "created_at": NOW - timedelta(hours=2),
        "resolved_at": None,
    },
    {
        "id": "inc-demo-010",
        "title": "SEV-1: Novel Auth Failure — JWKS endpoint returning 500",
        "service_name": "auth-service",
        "severity": "SEV-1",
        "status": "open",
        "raw_alert": json.dumps({"alert_name": "JWKSEndpointError", "service": "auth-service", "details": "JWKS endpoint /auth/.well-known/jwks.json returning 500. Token validation failing across all services."}),
        "hypotheses": [
            {"rank": 1, "hypothesis": "Key rotation job corrupted in-memory JWKS cache", "confidence": 0.71, "supporting_evidence": ["Key rotation ran 8min ago", "JWKS cache shows malformed JSON for kid:2026-06-12", "Previous rotations were clean"]},
            {"rank": 2, "hypothesis": "Redis cache TTL expired leaving auth-service unable to re-populate from KMS", "confidence": 0.58, "supporting_evidence": ["Redis eviction events logged at T-10min", "KMS API rate limit hit 3x in past hour"]}
        ],
        "risk_assessment": {"overall_risk": "critical", "blast_radius": "All authenticated API calls system-wide", "estimated_impact": "Full authentication outage — all logged-in users affected"},
        "action_plan": {"actions": [{"action": "Flush JWKS in-memory cache and force reload from KMS", "risk_tag": "approval_required", "risk_level": "medium"}, {"action": "Roll back key rotation to previous key version", "risk_tag": "approval_required", "risk_level": "high"}]},
        "engineer_view": "Active investigation. JWKS cache corruption likely from key rotation. Awaiting approval to flush and reload.",
        "executive_view": "Critical: All authenticated APIs are down. Engineering has isolated the cause and is awaiting approval to execute recovery. ETA: 8 minutes pending approval.",
        "reviewer_verdict": None,
        "reviewer_confidence_delta": None,
        "review_cycles": 0,
        "actual_root_cause": None,
        "accuracy_score": None,
        "resolved_by": None,
        "pipeline_duration_ms": 14700,
        "model_used": "gpt-5.4",
        "total_tokens": 24100,
        "created_at": NOW - timedelta(minutes=25),
        "resolved_at": None,
    },
]


async def seed_demo_incidents():
    await init_db()
    async with AsyncSessionLocal() as session:
        for data in MOCK_INCIDENTS:
            stmt = select(Incident).where(Incident.id == data["id"])
            existing = (await session.execute(stmt)).scalars().first()
            if existing:
                logger.info("Skipping existing: %s", data["id"])
                continue

            inc = Incident(
                id=data["id"],
                title=data["title"],
                service_name=data["service_name"],
                severity=data["severity"],
                status=data["status"],
                raw_alert=data.get("raw_alert"),
                hypotheses=data.get("hypotheses"),
                risk_assessment=data.get("risk_assessment"),
                action_plan=data.get("action_plan"),
                engineer_view=data.get("engineer_view"),
                executive_view=data.get("executive_view"),
                reviewer_verdict=data.get("reviewer_verdict"),
                reviewer_confidence_delta=data.get("reviewer_confidence_delta"),
                review_cycles=data.get("review_cycles", 0),
                actual_root_cause=data.get("actual_root_cause"),
                accuracy_score=data.get("accuracy_score"),
                resolved_by=data.get("resolved_by"),
                pipeline_duration_ms=data.get("pipeline_duration_ms"),
                model_used=data.get("model_used"),
                total_tokens=data.get("total_tokens"),
                created_at=data["created_at"],
                resolved_at=data.get("resolved_at"),
            )
            session.add(inc)
            logger.info("Created incident: %s", data["id"])

            # Add action items for the first 3 incidents
            if data.get("action_plan"):
                for i, action in enumerate(data["action_plan"].get("actions", [])[:2]):
                    ai = ActionItem(
                        id=str(uuid.uuid4()),
                        incident_id=data["id"],
                        action=action["action"],
                        risk_tag=action["risk_tag"],
                        risk_level=action["risk_level"],
                        rationale=f"Auto-generated by AIOS pipeline for {data['service_name']}",
                        status="executed" if data["status"] == "resolved" else "pending",
                        approved_by="admin" if data["status"] == "resolved" else None,
                        approved_at=data.get("resolved_at"),
                        created_at=data["created_at"],
                    )
                    session.add(ai)

        await session.commit()
        logger.info("✅ Demo incidents seeded successfully!")


if __name__ == "__main__":
    asyncio.run(seed_demo_incidents())
