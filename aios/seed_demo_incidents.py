"""
seed_demo_incidents.py — Populate PostgreSQL with realistic historical incidents for demo.

Inserts 8 fully-resolved incidents spanning the past 30 days, each with:
  - Full incident_packet, hypotheses, risk_assessment, action_plan
  - Human-readable engineer_view and executive_view
  - Agent traces (all 11 agents)
  - Action items with approval status
  - Accuracy scores and retrospective data

Run:  python seed_demo_incidents.py
Safe to re-run (skips existing incident IDs).
"""

import asyncio
import os
import sys
import json
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, str(Path(__file__).parent))

from database import AsyncSessionLocal, init_db
from models.database import Incident, AgentTrace, ActionItem
from sqlalchemy.future import select

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def ago(days: int, hours: int = 0) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days, hours=hours)

def resolved_at(created: datetime, minutes: int) -> datetime:
    return created + timedelta(minutes=minutes)

def make_traces(incident_id: str, started: datetime, scenario: str) -> list[dict]:
    """Generate realistic agent trace records for all 11 agents."""
    agents = [
        ("A1-Intake",             "completed", 1200,  350,  "Parsed alert payload, normalized fields, scrubbed PII"),
        ("A2-FoundryIQ",          "completed", 2800,  820,  f"Retrieved 4 KB docs matching '{scenario}'"),
        ("A2b-WorkIQ",            "completed", 1100,  290,  "Pulled calendar context: 2 deploys in last 24h"),
        ("A3-Correlation",        "completed", 4200, 1450,  "Generated 3 ranked hypotheses; convergence=0.87"),
        ("A4-RiskAnalyzer",       "completed", 1800,  540,  "Risk: MEDIUM — contained to single service"),
        ("A5-ActionPlanner",      "completed", 3100,  970,  "Produced 3-step mitigation plan with guardrails"),
        ("A6-Guardrail",          "completed",  800,  210,  "All actions passed safety checks"),
        ("A7-Communication",      "completed", 2200,  680,  "Generated engineer + executive views"),
        ("A8-Reviewer",           "completed", 3400, 1100,  "Reviewer approved with confidence delta +0.09"),
        ("A9-Retrospective",      "completed", 1500,  420,  "Retrospective logged; accuracy score computed"),
        ("A10-KnowledgeIngest",   "completed",  600,  180,  "Postmortem stub written to KB"),
    ]
    traces = []
    offset = 0
    for name, status, dur_ms, tokens, summary in agents:
        traces.append({
            "incident_id":    incident_id,
            "agent_name":     name,
            "status":         status,
            "model_used":     "gpt-5.4",
            "duration_ms":    dur_ms,
            "tokens_used":    tokens,
            "input_summary":  f"Input for {name}",
            "output_summary": summary,
            "error_message":  None,
            "started_at":     started + timedelta(milliseconds=offset),
        })
        offset += dur_ms + 200
    return traces


# ---------------------------------------------------------------------------
# 8 Demo incidents
# ---------------------------------------------------------------------------
INCIDENTS = [

    # ── 1. DB Connection Pool Exhaustion ────────────────────────────────────
    {
        "id": "demo-inc-001",
        "title": "SEV-1: Database Connection Pool Exhausted on api-gateway-prod",
        "service_name": "api-gateway-prod",
        "severity": "SEV-1",
        "status": "resolved",
        "created_at": ago(28, 3),
        "resolved_at_offset": 47,
        "pipeline_duration_ms": 22400,
        "model_used": "gpt-5.4",
        "total_tokens": 6800,
        "accuracy_score": 0.91,
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.08,
        "review_cycles": 1,
        "actual_root_cause": "api-gateway-prod v2.3 deployment introduced unclosed DB transactions. Pool of 5 connections exhausted within 8 minutes of deploy.",
        "raw_alert": '{"alert_name":"ConnectionPoolExhausted","service":"api-gateway-prod","severity":"SEV-1","details":"QueuePool limit 5/10 reached; 34 requests waiting","metrics":{"active_connections":15,"waiting":34}}',
        "incident_packet": {
            "incident_id": "demo-inc-001",
            "title": "Database Connection Pool Exhausted on api-gateway-prod",
            "service_name": "api-gateway-prod",
            "severity": "SEV-1",
            "timestamp": ago(28, 3).isoformat(),
            "raw_alert_sanitized": "ConnectionPoolExhausted on api-gateway-prod — QueuePool limit reached",
            "metrics": {"pool_size": 5, "active_connections": 15, "waiting_requests": 34},
            "tags": ["database", "connection-pool", "api-gateway"],
        },
        "hypotheses": {
            "hypotheses": [
                {
                    "title": "Unclosed DB Transactions from v2.3 Deploy",
                    "description": "The v2.3 deployment introduced a code path that opens a DB transaction but fails to close it on certain error conditions, causing connections to stay 'idle in transaction' indefinitely.",
                    "causal_factor": "Missing connection release in exception handler",
                    "confidence": 0.92,
                    "evidence_citations": ["runbook_database_connection_pool", "incident_4217_db_pool"],
                    "severity_implication": "SEV-1 — all incoming requests fail once pool exhausted",
                },
                {
                    "title": "Connection Leak in Batch Job",
                    "description": "A scheduled batch job added in v2.3 may be holding connections open across its entire run duration.",
                    "causal_factor": "Batch job not releasing connections after each chunk",
                    "confidence": 0.61,
                    "evidence_citations": ["runbook_database_connection_pool"],
                    "severity_implication": "SEV-2 — gradual pool starvation over minutes",
                },
            ],
            "convergence_score": 0.87,
            "reasoning_path": "KB runbook + postmortem #4217 both point to unclosed transactions as primary cause. Deployment timestamp correlates with pool exhaustion onset.",
        },
        "risk_assessment": {
            "overall_risk": "medium",
            "blast_radius": "api-gateway-prod and all upstream clients",
            "estimated_user_impact": "100% of requests failing; ~12,000 users affected",
            "rollback_safe": True,
            "time_to_impact": "Immediate",
        },
        "action_plan": {
            "summary": "Kill idle transactions, increase pool size, roll back to v2.2.",
            "mitigation_steps": [
                {
                    "id": "act-001-1",
                    "action": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND state_change < now() - interval '5 minutes';",
                    "risk_tag": "approval_required",
                    "risk_level": "medium",
                    "rationale": "Terminates idle-blocking connections to immediately free pool",
                    "verification_check": "SELECT count(*) FROM pg_stat_activity WHERE state='idle in transaction'; — should be 0",
                },
                {
                    "id": "act-001-2",
                    "action": "kubectl set env deployment/api-gateway-prod DATABASE_POOL_SIZE=20 DATABASE_MAX_OVERFLOW=30",
                    "risk_tag": "auto_approve",
                    "risk_level": "low",
                    "rationale": "Increases headroom while root cause is being fixed",
                    "verification_check": "kubectl rollout status deployment/api-gateway-prod",
                },
                {
                    "id": "act-001-3",
                    "action": "kubectl rollout undo deployment/api-gateway-prod",
                    "risk_tag": "approval_required",
                    "risk_level": "high",
                    "rationale": "Roll back to v2.2 eliminates the transaction-leak code path",
                    "verification_check": "curl -s https://api-gateway-prod/health | jq .status",
                },
            ],
            "safety_disclaimer": "Terminate idle transactions only after operator confirms no active long-running migrations.",
        },
        "engineer_view": "**Root Cause**: api-gateway-prod v2.3 introduced an unclosed DB transaction in the error handling path. Under load, this exhausted the pool of 5 connections in ~8 minutes.\n\n**Impact**: 100% request failure rate for 47 minutes. ~34 requests queued at peak.\n\n**Resolution**: Idle transactions terminated via pg_terminate_backend, pool size increased to 20, service rolled back to v2.2.\n\n**Next Steps**: Add middleware to enforce connection release on all request paths. Increase pool size permanently. Add pre-deployment query for open idle transactions.",
        "executive_view": "**Incident**: api-gateway-prod was fully unavailable for 47 minutes due to a database configuration issue introduced in a routine deployment.\n\n**Business Impact**: All API traffic failed during this window. Approximately 12,000 users affected.\n\n**Resolution**: Our on-call team identified and resolved the issue within the SLA window. No data was lost.\n\n**Prevention**: We are implementing automated pre-flight checks for database configuration changes in future deployments.",
        "action_items": [
            {"id": "act-001-1", "action": "Kill idle transactions", "risk_tag": "approval_required", "risk_level": "medium", "status": "executed", "approved_by": "admin"},
            {"id": "act-001-2", "action": "Increase pool size env vars", "risk_tag": "auto_approve", "risk_level": "low", "status": "executed", "approved_by": None},
            {"id": "act-001-3", "action": "kubectl rollout undo api-gateway-prod", "risk_tag": "approval_required", "risk_level": "high", "status": "executed", "approved_by": "admin"},
        ],
    },

    # ── 2. Memory Leak / OOMKill ─────────────────────────────────────────────
    {
        "id": "demo-inc-002",
        "title": "SEV-2: Memory Leak causing OOMKill on auth-service",
        "service_name": "auth-service",
        "severity": "SEV-2",
        "status": "resolved",
        "created_at": ago(24, 1),
        "resolved_at_offset": 31,
        "pipeline_duration_ms": 19800,
        "model_used": "gpt-5.4",
        "total_tokens": 5900,
        "accuracy_score": 0.88,
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.11,
        "review_cycles": 1,
        "actual_root_cause": "Log formatting library v1.4.2 introduced object retention in heap under async log writers. Heap grew from 512MB to 1.9GB over 4 hours before OOMKill.",
        "raw_alert": '{"alert_name":"PodOOMKilled","service":"auth-service","severity":"SEV-2","details":"Container auth-service OOMKilled — exit code 137","metrics":{"memory_usage_mb":1950,"memory_limit_mb":2048}}',
        "incident_packet": {
            "incident_id": "demo-inc-002",
            "title": "OOMKill on auth-service — memory exhaustion",
            "service_name": "auth-service",
            "severity": "SEV-2",
            "timestamp": ago(24, 1).isoformat(),
            "raw_alert_sanitized": "auth-service pod OOMKilled; exit code 137",
            "metrics": {"memory_usage_mb": 1950, "memory_limit_mb": 2048, "restart_count": 3},
            "tags": ["memory", "oomkill", "auth-service"],
        },
        "hypotheses": {
            "hypotheses": [
                {
                    "title": "Log Library Heap Retention Bug",
                    "description": "The recently upgraded log formatting library (v1.4.2) introduced async log writers that retain object references across request boundaries, causing heap to grow unboundedly.",
                    "causal_factor": "Object reference retention in async log handler",
                    "confidence": 0.89,
                    "evidence_citations": ["runbook_memory_leak_diagnosis", "incident_3891_memory_leak"],
                    "severity_implication": "SEV-2 — pod restarts cause 30-60s auth unavailability each cycle",
                },
                {
                    "title": "JWT Cache Growing Unboundedly",
                    "description": "The JWT validation cache may not have an eviction policy, causing it to grow with each unique token until memory is exhausted.",
                    "causal_factor": "Unbounded in-memory JWT cache",
                    "confidence": 0.44,
                    "evidence_citations": [],
                    "severity_implication": "SEV-3 — slower growth pattern, days before OOMKill",
                },
            ],
            "convergence_score": 0.83,
            "reasoning_path": "Postmortem #3891 describes identical symptom pattern after a log library upgrade. Deployment timeline matches heap growth onset.",
        },
        "risk_assessment": {
            "overall_risk": "medium",
            "blast_radius": "auth-service — affects all authenticated API calls",
            "estimated_user_impact": "Auth failures during each OOMKill restart cycle (~60s window)",
            "rollback_safe": True,
            "time_to_impact": "Next OOMKill in ~45 minutes at current growth rate",
        },
        "action_plan": {
            "summary": "Immediate rolling restart, then downgrade log library.",
            "mitigation_steps": [
                {
                    "id": "act-002-1",
                    "action": "kubectl rollout restart deployment/auth-service",
                    "risk_tag": "auto_approve",
                    "risk_level": "low",
                    "rationale": "Clears heap immediately; rolling restart minimises auth downtime",
                    "verification_check": "kubectl rollout status deployment/auth-service && kubectl top pod -l app=auth-service",
                },
                {
                    "id": "act-002-2",
                    "action": "Downgrade log-formatter to v1.4.1 in requirements.txt and redeploy",
                    "risk_tag": "approval_required",
                    "risk_level": "medium",
                    "rationale": "Removes the heap-retaining code path introduced in v1.4.2",
                    "verification_check": "Monitor memory metrics for 30 min; confirm no growth trend",
                },
            ],
            "safety_disclaimer": "Rolling restart causes brief auth token validation gaps. Schedule during low-traffic window if possible.",
        },
        "engineer_view": "**Root Cause**: Log library v1.4.2 introduced heap retention in async writers. Heap grew from 512MB to 1.9GB over 4 hours.\n\n**Impact**: 3 OOMKill restarts, each causing ~60s auth unavailability. Total exposure: ~3 minutes of auth failures.\n\n**Resolution**: Rolling restart cleared heap. Log library downgraded to v1.4.1.\n\n**Next Steps**: Pin log library version. Add memory growth alert (>80% for >10 min). Set memory limits at 3GB for buffer.",
        "executive_view": "**Incident**: The authentication service experienced intermittent restarts over a 3-hour period due to a memory issue in a recently updated software library.\n\n**Business Impact**: Users experienced brief login failures (estimated <3 minutes cumulative) during restart cycles.\n\n**Resolution**: Team identified and resolved the root cause within SLA. The faulty library version was downgraded.\n\n**Prevention**: We are implementing automated memory trend monitoring with proactive alerting.",
        "action_items": [
            {"id": "act-002-1", "action": "kubectl rollout restart deployment/auth-service", "risk_tag": "auto_approve", "risk_level": "low", "status": "executed", "approved_by": None},
            {"id": "act-002-2", "action": "Downgrade log-formatter to v1.4.1", "risk_tag": "approval_required", "risk_level": "medium", "status": "executed", "approved_by": "engineer"},
        ],
    },

    # ── 3. Payment Service Latency ───────────────────────────────────────────
    {
        "id": "demo-inc-003",
        "title": "SEV-1: Payment Processing p99 Latency Spike — checkout.service",
        "service_name": "payment-service",
        "severity": "SEV-1",
        "status": "resolved",
        "created_at": ago(20, 6),
        "resolved_at_offset": 22,
        "pipeline_duration_ms": 21100,
        "model_used": "gpt-5.4",
        "total_tokens": 6200,
        "accuracy_score": 0.93,
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.07,
        "review_cycles": 1,
        "actual_root_cause": "Stripe payment gateway introduced a 6-second p99 response time spike due to their own infrastructure event. Retry policy with count=5 amplified latency 5x.",
        "raw_alert": '{"alert_name":"PaymentLatencyHigh","service":"payment-service","severity":"SEV-1","details":"p99 latency 28.4s; 12% of transactions timing out","metrics":{"p99_ms":28400,"p50_ms":1200,"timeout_rate":0.12}}',
        "incident_packet": {
            "incident_id": "demo-inc-003",
            "title": "Payment service p99 latency 28.4s — customer checkout failing",
            "service_name": "payment-service",
            "severity": "SEV-1",
            "timestamp": ago(20, 6).isoformat(),
            "raw_alert_sanitized": "PaymentLatencyHigh — p99=28.4s, 12% timeout rate",
            "metrics": {"p99_ms": 28400, "p50_ms": 1200, "timeout_rate_pct": 12},
            "tags": ["payment", "latency", "checkout", "stripe"],
        },
        "hypotheses": {
            "hypotheses": [
                {
                    "title": "Upstream Payment Gateway Degradation + Retry Amplification",
                    "description": "Stripe gateway p99 spiked to 6s. Our retry policy (5 retries × 6s) produces 30s total latency for failed transactions.",
                    "causal_factor": "External dependency degradation amplified by aggressive retry policy",
                    "confidence": 0.94,
                    "evidence_citations": ["runbook_payment_latency"],
                    "severity_implication": "SEV-1 — customer-facing checkout blocking",
                },
            ],
            "convergence_score": 0.91,
            "reasoning_path": "Distributed traces show all latency in Stripe API call spans. Runbook confirms retry amplification pattern. Status page check shows Stripe infrastructure event active.",
        },
        "risk_assessment": {
            "overall_risk": "high",
            "blast_radius": "All checkout transactions; ~8% revenue stream",
            "estimated_user_impact": "12% of checkout attempts timing out; ~2,400 users/hour affected",
            "rollback_safe": False,
            "time_to_impact": "Ongoing — revenue loss accumulating",
        },
        "action_plan": {
            "summary": "Reduce retries, enable circuit breaker, activate backup payment provider.",
            "mitigation_steps": [
                {
                    "id": "act-003-1",
                    "action": "kubectl set env deployment/payment-service PAYMENT_GATEWAY_RETRY_COUNT=2 PAYMENT_GATEWAY_TIMEOUT_MS=4000",
                    "risk_tag": "auto_approve",
                    "risk_level": "low",
                    "rationale": "Reduces worst-case retry latency from 30s to 8s immediately",
                    "verification_check": "Monitor p99 latency metric for 5 minutes after redeploy",
                },
                {
                    "id": "act-003-2",
                    "action": "Enable CIRCUIT_BREAKER_ENABLED=true for payment-gateway integration",
                    "risk_tag": "approval_required",
                    "risk_level": "medium",
                    "rationale": "Circuit breaker fails fast when gateway >50% error rate, preventing queue buildup",
                    "verification_check": "Confirm circuit breaker state open/closed in /actuator/circuitbreakers",
                },
            ],
            "safety_disclaimer": "Enabling circuit breaker will cause immediate payment failures (fast-fail) rather than slow timeouts. Confirm with product team before activating.",
        },
        "engineer_view": "**Root Cause**: Stripe infrastructure event caused 6s p99. Our 5-retry policy amplified this to 30s p99 end-to-end.\n\n**Impact**: 12% checkout timeout rate; ~22 minutes of elevated latency.\n\n**Resolution**: Retry count reduced to 2, circuit breaker enabled. Stripe event resolved independently after 18 minutes.\n\n**Next Steps**: Implement circuit breaker as permanent standard. Add Stripe status page monitoring to on-call runbook.",
        "executive_view": "**Incident**: Our payment processing service experienced elevated latency for 22 minutes due to an issue at our payment gateway provider (Stripe).\n\n**Business Impact**: Approximately 12% of checkout attempts failed during this window. Estimated revenue impact: ~$4,200.\n\n**Resolution**: Engineering team mitigated within 22 minutes by reducing retry aggressiveness. Stripe resolved their own incident in parallel.\n\n**Prevention**: We are implementing circuit breakers and a backup payment provider for future resilience.",
        "action_items": [
            {"id": "act-003-1", "action": "Reduce retry count to 2", "risk_tag": "auto_approve", "risk_level": "low", "status": "executed", "approved_by": None},
            {"id": "act-003-2", "action": "Enable circuit breaker for payment-gateway", "risk_tag": "approval_required", "risk_level": "medium", "status": "executed", "approved_by": "admin"},
        ],
    },

    # ── 4. JVM Heap Exhaustion ───────────────────────────────────────────────
    {
        "id": "demo-inc-004",
        "title": "SEV-2: JVM Heap Exhaustion on order-service — OOM crash loop",
        "service_name": "order-service",
        "severity": "SEV-2",
        "status": "resolved",
        "created_at": ago(17, 2),
        "resolved_at_offset": 38,
        "pipeline_duration_ms": 20500,
        "model_used": "gpt-5.4",
        "total_tokens": 6100,
        "accuracy_score": 0.86,
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.09,
        "review_cycles": 1,
        "actual_root_cause": "Order serialization buffer in Kafka consumer was not releasing byte arrays after ACK, causing heap to grow 50MB/min. -Xmx was set at 1GB.",
        "raw_alert": '{"alert_name":"JVMHeapExhausted","service":"order-service","severity":"SEV-2","details":"java.lang.OutOfMemoryError: Java heap space — pod CrashLoopBackOff","metrics":{"heap_used_mb":1024,"heap_max_mb":1024,"gc_pause_ms":4500}}',
        "incident_packet": {
            "incident_id": "demo-inc-004",
            "title": "JVM Heap Exhausted on order-service",
            "service_name": "order-service",
            "severity": "SEV-2",
            "timestamp": ago(17, 2).isoformat(),
            "raw_alert_sanitized": "JVMHeapExhausted — OutOfMemoryError heap space",
            "metrics": {"heap_used_mb": 1024, "heap_max_mb": 1024, "gc_pause_ms": 4500},
            "tags": ["jvm", "heap", "order-service", "kafka"],
        },
        "hypotheses": {
            "hypotheses": [
                {
                    "title": "Kafka Consumer Buffer Leak",
                    "description": "The Kafka consumer's message buffer retains byte array references after offset commit, preventing GC from reclaiming heap space.",
                    "causal_factor": "ByteArray reference retention in Kafka consumer callback",
                    "confidence": 0.87,
                    "evidence_citations": ["runbook_jvm_heap_exhaustion"],
                    "severity_implication": "SEV-2 — order processing halted; inventory sync paused",
                },
                {
                    "title": "Deserialization Cache Unbounded",
                    "description": "The order deserialization layer may be caching all deserialized objects without TTL.",
                    "causal_factor": "No eviction policy on deserialization result cache",
                    "confidence": 0.51,
                    "evidence_citations": [],
                    "severity_implication": "SEV-3 — slower pattern, would take 6-8h to OOM",
                },
            ],
            "convergence_score": 0.81,
            "reasoning_path": "Heap dump analysis shows 78% heap occupied by byte arrays associated with Kafka consumer thread pool. Runbook pattern matches exactly.",
        },
        "risk_assessment": {
            "overall_risk": "medium",
            "blast_radius": "order-service; cascades to inventory-service (no new order events)",
            "estimated_user_impact": "Order placement failing; ~1,800 users impacted",
            "rollback_safe": True,
            "time_to_impact": "Crash loop every ~8 minutes at current rate",
        },
        "action_plan": {
            "summary": "Increase -Xmx, rolling restart, patch consumer buffer release.",
            "mitigation_steps": [
                {
                    "id": "act-004-1",
                    "action": "kubectl set env deployment/order-service JAVA_OPTS='-Xmx3g -XX:+UseG1GC -XX:+UseStringDeduplication'",
                    "risk_tag": "auto_approve",
                    "risk_level": "low",
                    "rationale": "Triples heap headroom; G1GC better handles fragmented allocation",
                    "verification_check": "kubectl rollout status deployment/order-service",
                },
                {
                    "id": "act-004-2",
                    "action": "Deploy hotfix release order-service:v3.1.2 (patches consumer buffer release)",
                    "risk_tag": "approval_required",
                    "risk_level": "medium",
                    "rationale": "Permanent fix — removes the buffer retention code path",
                    "verification_check": "Monitor heap usage for 20 min; confirm flat growth curve",
                },
            ],
            "safety_disclaimer": "Increasing -Xmx requires at least 4GB node capacity available. Verify node resource budget before applying.",
        },
        "engineer_view": "**Root Cause**: Kafka consumer byte array buffer not released after offset commit. Heap filled at 50MB/min, exhausting 1GB -Xmx in 20 minutes.\n\n**Impact**: Order service crash loop every 8 min for 38 minutes. ~1,800 order placements failed.\n\n**Resolution**: Increased -Xmx to 3GB as immediate relief. Hotfix v3.1.2 deployed to remove buffer retention.\n\n**Next Steps**: Add heap growth rate alert. Require load testing with heap profiler for all Kafka consumer changes.",
        "executive_view": "**Incident**: Our order processing service experienced a crash loop for 38 minutes due to a memory management issue.\n\n**Business Impact**: Approximately 1,800 order placements failed or were delayed. Estimated revenue impact: ~$18,000.\n\n**Resolution**: Engineering resolved within 38 minutes. A permanent code fix was deployed the same day.\n\n**Prevention**: We are adding memory profiling to our CI/CD pipeline for all Kafka-related changes.",
        "action_items": [
            {"id": "act-004-1", "action": "Increase JVM -Xmx to 3g, enable G1GC", "risk_tag": "auto_approve", "risk_level": "low", "status": "executed", "approved_by": None},
            {"id": "act-004-2", "action": "Deploy order-service:v3.1.2 hotfix", "risk_tag": "approval_required", "risk_level": "medium", "status": "executed", "approved_by": "admin"},
        ],
    },

    # ── 5. Cascading Failure ─────────────────────────────────────────────────
    {
        "id": "demo-inc-005",
        "title": "SEV-1: Cascading Failure — db-service → order-service → api-gateway",
        "service_name": "db-service",
        "severity": "SEV-1",
        "status": "resolved",
        "created_at": ago(14, 4),
        "resolved_at_offset": 72,
        "pipeline_duration_ms": 24800,
        "model_used": "gpt-5.4",
        "total_tokens": 7600,
        "accuracy_score": 0.89,
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.06,
        "review_cycles": 2,
        "actual_root_cause": "Missing index on orders.created_at caused full table scan during peak load. DB connections saturated → order-service 503 → inventory-service unavailable → api-gateway 502 cascade.",
        "raw_alert": '{"alert_name":"CascadingServiceFailure","service":"api-gateway","severity":"SEV-1","details":"api-gateway returning 502 Bad Gateway; upstream services unreachable","metrics":{"error_rate":0.94,"affected_services":["order-service","inventory-service","db-service"]}}',
        "incident_packet": {
            "incident_id": "demo-inc-005",
            "title": "Cascading failure from db-service propagating to api-gateway",
            "service_name": "db-service",
            "severity": "SEV-1",
            "timestamp": ago(14, 4).isoformat(),
            "raw_alert_sanitized": "CascadingServiceFailure — api-gateway 94% error rate; 3 upstream services down",
            "metrics": {"error_rate_pct": 94, "affected_services": 3},
            "tags": ["cascading", "database", "index", "api-gateway"],
        },
        "hypotheses": {
            "hypotheses": [
                {
                    "title": "Missing DB Index Causing Full Table Scan Cascade",
                    "description": "A schema migration deployed at 02:30 UTC removed an index on orders.created_at. Under peak load, queries run full table scans, saturating DB connections. This exhausts the pool for all dependent services.",
                    "causal_factor": "Missing orders.created_at index after schema migration",
                    "confidence": 0.93,
                    "evidence_citations": ["postmortem_cascading_failure_6023", "runbook_database_connection_pool"],
                    "severity_implication": "SEV-1 — entire purchase funnel unavailable",
                },
                {
                    "title": "DB Primary Failover in Progress",
                    "description": "RDS/PostgreSQL primary may have failed over, causing a connection storm during promotion.",
                    "causal_factor": "Database primary failover connection reset",
                    "confidence": 0.35,
                    "evidence_citations": [],
                    "severity_implication": "SEV-1 — temporary; resolves in <5 min after failover",
                },
            ],
            "convergence_score": 0.88,
            "reasoning_path": "Topology graph shows db-service as root dependency for all three failing services. Postmortem #6023 matches exact cascade pattern. DB slow query log confirms full table scans starting at 02:31 UTC, 1 minute after schema migration.",
        },
        "risk_assessment": {
            "overall_risk": "critical",
            "blast_radius": "Entire purchase funnel — api-gateway, order-service, inventory-service, payment-service",
            "estimated_user_impact": "94% of all requests failing; ~45,000 users affected",
            "rollback_safe": True,
            "time_to_impact": "Ongoing — full platform outage",
        },
        "action_plan": {
            "summary": "Create missing index online, reset connection pools, verify cascade recovery.",
            "mitigation_steps": [
                {
                    "id": "act-005-1",
                    "action": "CREATE INDEX CONCURRENTLY idx_orders_created_at ON orders(created_at);",
                    "risk_tag": "approval_required",
                    "risk_level": "medium",
                    "rationale": "Restores query performance without locking the table (CONCURRENTLY)",
                    "verification_check": "EXPLAIN ANALYZE SELECT * FROM orders WHERE created_at > now()-interval '1 hour'; — confirm index scan used",
                },
                {
                    "id": "act-005-2",
                    "action": "kubectl rollout restart deployment/order-service deployment/inventory-service",
                    "risk_tag": "auto_approve",
                    "risk_level": "low",
                    "rationale": "Resets connection pools after DB is healthy; clears blocked connection state",
                    "verification_check": "kubectl get pods -l app in (order-service,inventory-service) — all Running",
                },
                {
                    "id": "act-005-3",
                    "action": "Revert schema migration: psql -c \"ALTER TABLE orders ADD INDEX ...\" (from migration rollback script)",
                    "risk_tag": "blocked",
                    "risk_level": "critical",
                    "rationale": "Full migration rollback as last resort if CONCURRENTLY index fails",
                    "verification_check": "Full DB health check + all service health probes green",
                },
            ],
            "safety_disclaimer": "CREATE INDEX CONCURRENTLY may take 10-15 minutes on large orders table. Do not cancel mid-operation. Monitor pg_stat_progress_create_index.",
        },
        "engineer_view": "**Root Cause**: Schema migration at 02:30 UTC dropped the orders.created_at index. Full table scans under peak load saturated DB connections, cascading to 3 dependent services.\n\n**Impact**: 94% error rate platform-wide for 72 minutes. Estimated ~45,000 users impacted.\n\n**Resolution**: CREATE INDEX CONCURRENTLY restored in 14 minutes. Service restarts reset connection pools. Full recovery at 03:47 UTC.\n\n**Next Steps**: Require index existence check in migration pre-flight script. Add circuit breakers to all DB-dependent services. Topology-aware alerting to detect cascade origin.",
        "executive_view": "**Incident**: A database configuration change triggered a platform-wide outage lasting 72 minutes during off-peak hours.\n\n**Business Impact**: The entire purchase funnel was unavailable. Estimated revenue impact: ~$85,000. No data was lost.\n\n**Resolution**: The database team restored the missing configuration within 14 minutes of identification. Full platform recovery followed within 72 minutes of initial alert.\n\n**Prevention**: We are implementing automated pre-deployment database validation to prevent similar configuration errors in future releases.",
        "action_items": [
            {"id": "act-005-1", "action": "CREATE INDEX CONCURRENTLY idx_orders_created_at", "risk_tag": "approval_required", "risk_level": "medium", "status": "executed", "approved_by": "admin"},
            {"id": "act-005-2", "action": "Restart order-service and inventory-service", "risk_tag": "auto_approve", "risk_level": "low", "status": "executed", "approved_by": None},
            {"id": "act-005-3", "action": "Schema migration rollback (last resort)", "risk_tag": "blocked", "risk_level": "critical", "status": "rejected", "approved_by": None},
        ],
    },

    # ── 6. DNS Resolution Failure ────────────────────────────────────────────
    {
        "id": "demo-inc-006",
        "title": "SEV-2: DNS Resolution Failures across multiple pods — CoreDNS overload",
        "service_name": "cdn-service",
        "severity": "SEV-2",
        "status": "resolved",
        "created_at": ago(10, 5),
        "resolved_at_offset": 19,
        "pipeline_duration_ms": 18200,
        "model_used": "gpt-5.4",
        "total_tokens": 5400,
        "accuracy_score": 0.90,
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.12,
        "review_cycles": 1,
        "actual_root_cause": "CoreDNS pods were running on only 2 replicas during a node scaling event. DNS query backlog exceeded UDP buffer limits. ndots:5 default caused 3x query amplification.",
        "raw_alert": '{"alert_name":"DNSResolutionFailures","service":"cdn-service","severity":"SEV-2","details":"Temporary failure in name resolution for multiple external endpoints","metrics":{"dns_error_rate":0.31,"affected_pods":12}}',
        "incident_packet": {
            "incident_id": "demo-inc-006",
            "title": "DNS resolution failures — 31% error rate across 12 pods",
            "service_name": "cdn-service",
            "severity": "SEV-2",
            "timestamp": ago(10, 5).isoformat(),
            "raw_alert_sanitized": "DNSResolutionFailures — 31% NXDOMAIN rate, 12 pods affected",
            "metrics": {"dns_error_rate_pct": 31, "affected_pods": 12},
            "tags": ["dns", "coredns", "kubernetes"],
        },
        "hypotheses": {
            "hypotheses": [
                {
                    "title": "CoreDNS Overload During Node Scale-Out",
                    "description": "A node scaling event brought up 8 new pods simultaneously. Default ndots:5 causes each pod to make 3 DNS queries per external lookup. CoreDNS at 2 replicas became the bottleneck.",
                    "causal_factor": "CoreDNS under-provisioned for burst DNS traffic",
                    "confidence": 0.91,
                    "evidence_citations": ["runbook_dns_resolution"],
                    "severity_implication": "SEV-2 — external service calls failing intermittently",
                },
            ],
            "convergence_score": 0.88,
            "reasoning_path": "CoreDNS CPU at 98% during incident window. Pod scaling event at identical timestamp. ndots:5 confirmed in cluster DNS config — 3x amplification factor calculated.",
        },
        "risk_assessment": {
            "overall_risk": "medium",
            "blast_radius": "All pods relying on external DNS resolution (12 pods across 4 services)",
            "estimated_user_impact": "31% of external API calls failing intermittently",
            "rollback_safe": True,
            "time_to_impact": "Ongoing — resolves if DNS load drops but will recur",
        },
        "action_plan": {
            "summary": "Scale CoreDNS replicas, reduce ndots to 2.",
            "mitigation_steps": [
                {
                    "id": "act-006-1",
                    "action": "kubectl scale deployment coredns -n kube-system --replicas=4",
                    "risk_tag": "auto_approve",
                    "risk_level": "low",
                    "rationale": "Doubles DNS capacity immediately; resolves overload within seconds",
                    "verification_check": "kubectl get pods -n kube-system -l k8s-app=kube-dns — 4 Running",
                },
                {
                    "id": "act-006-2",
                    "action": "Update cluster DNS config: set ndots:2 in kubelet resolv.conf template",
                    "risk_tag": "approval_required",
                    "risk_level": "medium",
                    "rationale": "Reduces DNS query amplification from 3x to 1x per lookup",
                    "verification_check": "Verify with nslookup in a test pod; confirm single DNS query per lookup in tcpdump",
                },
            ],
            "safety_disclaimer": "Changing ndots requires rolling restart of all pods to pick up new DNS config.",
        },
        "engineer_view": "**Root Cause**: CoreDNS at 2 replicas hit CPU ceiling during scale-out. ndots:5 tripled DNS query volume per lookup.\n\n**Impact**: 31% DNS failure rate for 19 minutes, affecting 12 pods across cdn-service and dependents.\n\n**Resolution**: CoreDNS scaled to 4 replicas. ndots changed to 2 in cluster config.\n\n**Next Steps**: Set CoreDNS HPA with min=4 replicas. Add CoreDNS CPU alert at 70%.",
        "executive_view": "**Incident**: A network configuration issue caused intermittent failures for calls to external services over a 19-minute window.\n\n**Business Impact**: CDN asset delivery experienced a 31% partial failure rate. User experience was degraded but not fully blocked.\n\n**Resolution**: Engineering scaled the DNS service and optimised configuration within 19 minutes.\n\n**Prevention**: We are implementing auto-scaling for our DNS infrastructure to handle traffic spikes automatically.",
        "action_items": [
            {"id": "act-006-1", "action": "Scale CoreDNS to 4 replicas", "risk_tag": "auto_approve", "risk_level": "low", "status": "executed", "approved_by": None},
            {"id": "act-006-2", "action": "Set ndots:2 in cluster DNS config", "risk_tag": "approval_required", "risk_level": "medium", "status": "executed", "approved_by": "engineer"},
        ],
    },

    # ── 7. TLS Certificate Expiry ────────────────────────────────────────────
    {
        "id": "demo-inc-007",
        "title": "SEV-3: TLS Certificate Near-Expiry on api-gateway — 6 days remaining",
        "service_name": "api-gateway",
        "severity": "SEV-3",
        "status": "resolved",
        "created_at": ago(6, 2),
        "resolved_at_offset": 14,
        "pipeline_duration_ms": 15400,
        "model_used": "gpt-5.4",
        "total_tokens": 4800,
        "accuracy_score": 0.95,
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.04,
        "review_cycles": 1,
        "actual_root_cause": "Let's Encrypt auto-renewal via cert-manager failed silently because the DNS TXT validation challenge was blocked by a firewall rule added 10 days prior.",
        "raw_alert": '{"alert_name":"TLSCertNearExpiry","service":"api-gateway","severity":"SEV-3","details":"TLS certificate expires in 6 days: *.api.example.com","metrics":{"days_remaining":6,"cert_subject":"*.api.example.com"}}',
        "incident_packet": {
            "incident_id": "demo-inc-007",
            "title": "TLS certificate expiring in 6 days on api-gateway",
            "service_name": "api-gateway",
            "severity": "SEV-3",
            "timestamp": ago(6, 2).isoformat(),
            "raw_alert_sanitized": "TLSCertNearExpiry — *.api.example.com expires in 6 days",
            "metrics": {"days_remaining": 6, "cert_domain": "*.api.example.com"},
            "tags": ["tls", "certificate", "cert-manager", "api-gateway"],
        },
        "hypotheses": {
            "hypotheses": [
                {
                    "title": "cert-manager ACME Challenge Blocked by Firewall",
                    "description": "cert-manager's Let's Encrypt DNS-01 challenge requires outbound UDP/TCP to the DNS provider API. A new firewall rule blocking outbound port 443 to external APIs broke the renewal silently.",
                    "causal_factor": "Firewall rule blocking cert-manager ACME DNS challenge",
                    "confidence": 0.94,
                    "evidence_citations": ["runbook_tls_certificate_renewal", "runbook_certificate_renewal"],
                    "severity_implication": "SEV-3 now → SEV-1 in 6 days if not resolved",
                },
            ],
            "convergence_score": 0.92,
            "reasoning_path": "cert-manager CertificateRequest shows repeated 'DNS-01 challenge failed' errors starting 10 days ago. Firewall rule added 10 days ago correlates exactly. Calendar shows no other infrastructure changes in that window.",
        },
        "risk_assessment": {
            "overall_risk": "high",
            "blast_radius": "api-gateway — all HTTPS traffic; would become SEV-1 at expiry",
            "estimated_user_impact": "Zero current impact; 100% HTTPS failure in 6 days if unresolved",
            "rollback_safe": True,
            "time_to_impact": "6 days",
        },
        "action_plan": {
            "summary": "Remove firewall block, trigger manual certificate renewal.",
            "mitigation_steps": [
                {
                    "id": "act-007-1",
                    "action": "Remove firewall rule blocking outbound to Let's Encrypt API: az network nsg rule delete --name BlockLEAcme",
                    "risk_tag": "approval_required",
                    "risk_level": "medium",
                    "rationale": "Re-enables cert-manager ACME challenge to complete auto-renewal",
                    "verification_check": "curl -v https://acme-v02.api.letsencrypt.org/directory — confirm 200 OK",
                },
                {
                    "id": "act-007-2",
                    "action": "kubectl annotate certificate api-gateway-tls cert-manager.io/issue-temporary-certificate=true -n ingress",
                    "risk_tag": "auto_approve",
                    "risk_level": "low",
                    "rationale": "Forces immediate renewal attempt by cert-manager",
                    "verification_check": "kubectl describe certificate api-gateway-tls -n ingress — status Ready, notAfter > 90 days",
                },
            ],
            "safety_disclaimer": "Certificate renewal may cause a brief ingress controller reload (~2s). Schedule during low-traffic if possible.",
        },
        "engineer_view": "**Root Cause**: Firewall rule added 10 days ago blocked cert-manager's outbound ACME DNS challenge. Auto-renewal failed silently for 10 days until near-expiry alert fired.\n\n**Impact**: No current user impact. Would become SEV-1 total HTTPS outage in 6 days.\n\n**Resolution**: Firewall rule removed. cert-manager triggered renewal. Certificate renewed with 90-day validity within 14 minutes.\n\n**Next Steps**: Add cert-manager challenge failure monitoring. Add pre-firewall-change checklist item for cert-manager connectivity. Set renewal alert at 30 days.",
        "executive_view": "**Incident**: A proactive security monitoring alert caught a TLS certificate approaching expiry 6 days in advance, preventing a potential service outage.\n\n**Business Impact**: Zero customer impact — the issue was detected and resolved before any disruption occurred.\n\n**Resolution**: The engineering team identified and resolved a network configuration conflict that was preventing automatic certificate renewal. Resolution took 14 minutes.\n\n**Prevention**: We are adding enhanced monitoring for certificate renewal failures and pre-change network validation checks.",
        "action_items": [
            {"id": "act-007-1", "action": "Remove firewall rule blocking ACME challenge", "risk_tag": "approval_required", "risk_level": "medium", "status": "executed", "approved_by": "admin"},
            {"id": "act-007-2", "action": "Trigger cert-manager manual renewal", "risk_tag": "auto_approve", "risk_level": "low", "status": "executed", "approved_by": None},
        ],
    },

    # ── 8. K8s OOM — Recommendation Engine ──────────────────────────────────
    {
        "id": "demo-inc-008",
        "title": "SEV-2: Kubernetes OOMKill loop on recommendation-engine — pod thrashing",
        "service_name": "recommendation-engine",
        "severity": "SEV-2",
        "status": "resolved",
        "created_at": ago(2, 3),
        "resolved_at_offset": 28,
        "pipeline_duration_ms": 20100,
        "model_used": "gpt-5.4",
        "total_tokens": 5700,
        "accuracy_score": 0.87,
        "reviewer_verdict": "approved",
        "reviewer_confidence_delta": 0.10,
        "review_cycles": 1,
        "actual_root_cause": "ML model inference batch size set to 512 in a config change; each batch allocates 1.8GB for embedding matrix multiplication. Container memory limit was 2GB, causing OOMKill mid-inference.",
        "raw_alert": '{"alert_name":"K8sOOMKill","service":"recommendation-engine","severity":"SEV-2","details":"Pod recommendation-engine-7d9f8b CrashLoopBackOff; OOMKilled exit code 137","metrics":{"memory_rss_mb":2048,"memory_limit_mb":2048,"restart_count":5}}',
        "incident_packet": {
            "incident_id": "demo-inc-008",
            "title": "recommendation-engine OOMKill — CrashLoopBackOff after batch size config change",
            "service_name": "recommendation-engine",
            "severity": "SEV-2",
            "timestamp": ago(2, 3).isoformat(),
            "raw_alert_sanitized": "K8sOOMKill recommendation-engine — exit 137, 5 restarts",
            "metrics": {"memory_rss_mb": 2048, "memory_limit_mb": 2048, "restart_count": 5},
            "tags": ["kubernetes", "oom", "oomkill", "ml", "recommendation"],
        },
        "hypotheses": {
            "hypotheses": [
                {
                    "title": "ML Batch Size Increase Exceeds Memory Limit",
                    "description": "Config change set INFERENCE_BATCH_SIZE=512. Each batch allocates a 512×3584 float32 embedding matrix (~1.8GB). This exceeds the 2GB container memory limit, triggering OOMKill.",
                    "causal_factor": "Batch size config change incompatible with container memory limits",
                    "confidence": 0.96,
                    "evidence_citations": ["runbook_k8s_oom_recovery", "runbook_kubernetes_oom_recovery"],
                    "severity_implication": "SEV-2 — recommendation features unavailable; degraded UX",
                },
            ],
            "convergence_score": 0.94,
            "reasoning_path": "Config change audit shows INFERENCE_BATCH_SIZE changed from 64 to 512 at 21:14 UTC, 3 minutes before first OOMKill. Memory calculation confirms 512 batch × 3584 float32 = 1.8GB allocation exceeds 2GB limit including OS overhead.",
        },
        "risk_assessment": {
            "overall_risk": "medium",
            "blast_radius": "recommendation-engine only — non-critical path; api-gateway falls back to static recommendations",
            "estimated_user_impact": "Personalised recommendations unavailable; ~8% CTR degradation expected",
            "rollback_safe": True,
            "time_to_impact": "Ongoing crash loop — recovering every 8 minutes",
        },
        "action_plan": {
            "summary": "Revert batch size config, increase memory limits permanently.",
            "mitigation_steps": [
                {
                    "id": "act-008-1",
                    "action": "kubectl set env deployment/recommendation-engine INFERENCE_BATCH_SIZE=64",
                    "risk_tag": "auto_approve",
                    "risk_level": "low",
                    "rationale": "Reverts to safe batch size; allocation drops to ~225MB",
                    "verification_check": "kubectl rollout status deployment/recommendation-engine && kubectl top pod -l app=recommendation-engine",
                },
                {
                    "id": "act-008-2",
                    "action": "Update deployment spec: resources.limits.memory=6Gi to support batch size 512 for future",
                    "risk_tag": "approval_required",
                    "risk_level": "medium",
                    "rationale": "Permanent fix — properly sizes memory limits for ML workload",
                    "verification_check": "Run inference with INFERENCE_BATCH_SIZE=512; confirm pod stays healthy for 15 min",
                },
            ],
            "safety_disclaimer": "Increasing memory limits to 6Gi requires node with ≥8GB available. Check cluster capacity with 'kubectl describe nodes' before applying.",
        },
        "engineer_view": "**Root Cause**: INFERENCE_BATCH_SIZE increased from 64 to 512 in a config push. Each batch requires 1.8GB for embedding matrix — exceeding the 2GB container limit by ~200MB including OS overhead.\n\n**Impact**: recommendation-engine CrashLoopBackOff for 28 minutes (5 restarts). Personalised recommendations degraded to static fallback.\n\n**Resolution**: Batch size reverted to 64. Pod stable within 2 minutes.\n\n**Next Steps**: Implement memory-aware batch size validation in config deployment. Set memory limits to 6GB to support production batch size 512. Add pre-deploy memory estimation step.",
        "executive_view": "**Incident**: Our recommendation system experienced a crash loop for 28 minutes due to a configuration change that exceeded the system's memory allocation.\n\n**Business Impact**: Users received static rather than personalised recommendations during this window. No data loss occurred. Estimated CTR impact: ~8% degradation over 28 minutes.\n\n**Resolution**: Engineering reverted the configuration change within 28 minutes. A permanent fix to increase memory capacity is scheduled for the next release.\n\n**Prevention**: We are implementing automated memory impact analysis for all ML configuration changes.",
        "action_items": [
            {"id": "act-008-1", "action": "Revert INFERENCE_BATCH_SIZE to 64", "risk_tag": "auto_approve", "risk_level": "low", "status": "executed", "approved_by": None},
            {"id": "act-008-2", "action": "Update memory limits to 6Gi for recommendation-engine", "risk_tag": "approval_required", "risk_level": "medium", "status": "pending", "approved_by": None},
        ],
    },
]


# ---------------------------------------------------------------------------
# Insert logic
# ---------------------------------------------------------------------------
async def insert_incidents() -> None:
    await init_db()

    async with AsyncSessionLocal() as session:
        inserted = 0
        skipped = 0

        for inc_data in INCIDENTS:
            # Skip if already exists
            stmt = select(Incident).where(Incident.id == inc_data["id"])
            res = await session.execute(stmt)
            if res.scalars().first():
                print(f"  SKIP (exists): {inc_data['id']}")
                skipped += 1
                continue

            created = inc_data["created_at"]
            resolved = resolved_at(created, inc_data["resolved_at_offset"])

            inc = Incident(
                id=inc_data["id"],
                title=inc_data["title"],
                service_name=inc_data["service_name"],
                severity=inc_data["severity"],
                status=inc_data["status"],
                raw_alert=inc_data["raw_alert"],
                incident_packet=inc_data["incident_packet"],
                hypotheses=inc_data["hypotheses"],
                risk_assessment=inc_data["risk_assessment"],
                action_plan=inc_data["action_plan"],
                engineer_view=inc_data["engineer_view"],
                executive_view=inc_data["executive_view"],
                reviewer_verdict=inc_data.get("reviewer_verdict"),
                reviewer_confidence_delta=inc_data.get("reviewer_confidence_delta"),
                review_cycles=inc_data.get("review_cycles", 1),
                actual_root_cause=inc_data.get("actual_root_cause"),
                accuracy_score=inc_data.get("accuracy_score"),
                pipeline_duration_ms=inc_data.get("pipeline_duration_ms"),
                model_used=inc_data.get("model_used", "gpt-5.4"),
                total_tokens=inc_data.get("total_tokens"),
                created_at=created,
                resolved_at=resolved,
            )
            session.add(inc)
            await session.flush()  # get the id committed before adding traces

            # Agent traces
            for trace_data in make_traces(inc_data["id"], created, inc_data["service_name"]):
                trace = AgentTrace(
                    incident_id=trace_data["incident_id"],
                    agent_name=trace_data["agent_name"],
                    status=trace_data["status"],
                    model_used=trace_data["model_used"],
                    duration_ms=trace_data["duration_ms"],
                    tokens_used=trace_data["tokens_used"],
                    input_summary=trace_data["input_summary"],
                    output_summary=trace_data["output_summary"],
                    error_message=trace_data["error_message"],
                    started_at=trace_data["started_at"],
                )
                session.add(trace)

            # Action items
            for act in inc_data.get("action_items", []):
                approved_at = resolved if act.get("status") == "executed" and act.get("approved_by") else None
                item = ActionItem(
                    id=act["id"],
                    incident_id=inc_data["id"],
                    action=act["action"],
                    risk_tag=act["risk_tag"],
                    risk_level=act["risk_level"],
                    rationale=inc_data["action_plan"]["mitigation_steps"][0]["rationale"],
                    status=act["status"],
                    approved_by=act.get("approved_by"),
                    approved_at=approved_at,
                    created_at=created,
                )
                session.add(item)

            print(f"  INSERT: {inc_data['id']} — {inc_data['title'][:60]}")
            inserted += 1

        await session.commit()
        print(f"\nDone -- {inserted} incidents inserted, {skipped} skipped.")


if __name__ == "__main__":
    asyncio.run(insert_incidents())
