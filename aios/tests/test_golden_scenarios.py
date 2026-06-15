import os
import json
import pytest
from pathlib import Path

def test_golden_scenarios_files_exist():
    """Verify that all 10 golden scenarios exist and have valid JSON structures."""
    alerts_dir = Path("knowledge") / "alerts"
    
    assert alerts_dir.exists() is True
    
    expected_scenarios = [
        "scenario_01_db_pool.json",
        "scenario_02_memory_leak.json",
        "scenario_03_payment_latency.json",
        "scenario_04_jvm_heap.json",
        "scenario_05_cascading.json",
        "scenario_06_dns.json",
        "scenario_07_tls_cert.json",
        "scenario_08_k8s_oom.json",
        "scenario_09_disk_io.json",
        "scenario_10_novel_jwks.json"
    ]
    
    for fn in expected_scenarios:
        path = alerts_dir / fn
        assert path.exists() is True
        
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        assert "id" in data
        assert "name" in data
        assert "alert_payload" in data
        assert "expected_diagnosis" in data
        assert "expected_risk_level" in data
