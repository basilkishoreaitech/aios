"""
AIOS Scenario Accuracy Harness
==============================

Drives all 10 golden scenarios through the LIVE pipeline against a running AIOS
server, then resolves each incident with its expected root cause so the A9
Retrospective agent produces a self-scored diagnosis-accuracy value. Prints a
per-scenario table and the headline average — a real, reproducible number you can
screenshot for the README / demo.

Prerequisites
-------------
1. A running AIOS server with live Azure credentials:
       uvicorn main:app --reload          # http://localhost:8000
2. Seeded users (python seed.py).

Usage
-----
    python evaluate_scenarios.py
    python evaluate_scenarios.py --base-url http://localhost:8000 --username engineer --password aios-eng-2026
    python evaluate_scenarios.py --json results.json     # also write machine-readable results

Notes
-----
- Each scenario costs real Azure OpenAI tokens (full 11-agent run + retrospective).
- The /api/ingest endpoint is rate-limited to 10/min per IP; the harness paces
  requests so it stays within that budget.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional

import httpx

ALERTS_DIR = Path(__file__).parent / "knowledge" / "alerts"
SCENARIO_FILES = [
    "scenario_01_db_pool.json",
    "scenario_02_memory_leak.json",
    "scenario_03_payment_latency.json",
    "scenario_04_jvm_heap.json",
    "scenario_05_cascading.json",
    "scenario_06_dns.json",
    "scenario_07_tls_cert.json",
    "scenario_08_k8s_oom.json",
    "scenario_09_disk_io.json",
    "scenario_10_novel_jwks.json",
]


def login(client: httpx.Client, base_url: str, username: str, password: str) -> str:
    resp = client.post(
        f"{base_url}/api/auth/login",
        json={"username": username, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def run_scenario(client: httpx.Client, base_url: str, headers: dict, raw_alert: str) -> Optional[str]:
    """POST the alert to /api/ingest and parse the SSE stream to capture the incident_id."""
    incident_id: Optional[str] = None
    with client.stream(
        "POST",
        f"{base_url}/api/ingest",
        headers=headers,
        json={"raw_alert": raw_alert},
        timeout=180,
    ) as resp:
        resp.raise_for_status()
        current_event = None
        for line in resp.iter_lines():
            if not line:
                continue
            if line.startswith("event:"):
                current_event = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data = line[len("data:"):].strip()
                if current_event == "pipeline_start" and incident_id is None:
                    try:
                        incident_id = json.loads(data).get("incident_id")
                    except json.JSONDecodeError:
                        pass
                if current_event == "pipeline_error":
                    print(f"    ! pipeline_error: {data}", file=sys.stderr)
    return incident_id


def resolve_incident(client: httpx.Client, base_url: str, headers: dict, incident_id: str, root_cause: str) -> Optional[float]:
    resp = client.post(
        f"{base_url}/api/incident/{incident_id}/resolve",
        headers=headers,
        json={"actual_root_cause": root_cause},
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json().get("accuracy_score")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run AIOS golden-scenario accuracy harness.")
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--username", default="engineer")
    parser.add_argument("--password", default="aios-eng-2026")
    parser.add_argument("--json", dest="json_out", default=None, help="Optional path to write JSON results.")
    parser.add_argument("--pace", type=float, default=7.0, help="Seconds to wait between scenarios (rate-limit safe).")
    args = parser.parse_args()

    client = httpx.Client()
    try:
        token = login(client, args.base_url, args.username, args.password)
    except Exception as exc:  # noqa: BLE001
        print(f"Login failed against {args.base_url}: {exc}", file=sys.stderr)
        print("Is the server running?  uvicorn main:app --reload", file=sys.stderr)
        return 1

    headers = {"Authorization": f"Bearer {token}"}
    results = []

    print("\n  AIOS — Golden Scenario Accuracy Harness")
    print("  " + "=" * 60)
    print(f"  Target: {args.base_url}   Scenarios: {len(SCENARIO_FILES)}\n")

    for idx, fn in enumerate(SCENARIO_FILES, 1):
        path = ALERTS_DIR / fn
        scenario = json.loads(path.read_text(encoding="utf-8"))
        name = scenario.get("name", fn)
        raw_alert = json.dumps(scenario["alert_payload"])
        expected = scenario["expected_diagnosis"]

        print(f"  [{idx:02d}/{len(SCENARIO_FILES)}] {name[:54]:<54}", end="", flush=True)
        score: Optional[float] = None
        try:
            incident_id = run_scenario(client, args.base_url, headers, raw_alert)
            if incident_id:
                score = resolve_incident(client, args.base_url, headers, incident_id, expected)
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")
            results.append({"scenario": scenario.get("id", fn), "accuracy_score": None, "error": str(exc)})
            continue

        if score is None:
            print("  no score")
        else:
            print(f"  accuracy {score * 100:5.1f}%")
        results.append({"scenario": scenario.get("id", fn), "name": name, "accuracy_score": score})

        if idx < len(SCENARIO_FILES):
            time.sleep(args.pace)  # stay within the 10/min ingest rate limit

    scored = [r["accuracy_score"] for r in results if r.get("accuracy_score") is not None]
    avg = sum(scored) / len(scored) if scored else 0.0

    print("\n  " + "-" * 60)
    print(f"  Scenarios scored : {len(scored)}/{len(SCENARIO_FILES)}")
    print(f"  Average accuracy : {avg * 100:.1f}%")
    print("  " + "-" * 60 + "\n")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"results": results, "average_accuracy": avg, "scored": len(scored)}, indent=2),
            encoding="utf-8",
        )
        print(f"  Results written to {args.json_out}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
