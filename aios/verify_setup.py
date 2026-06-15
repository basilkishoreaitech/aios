import os
import sys
import importlib
from pathlib import Path

# Print helper
def print_status(msg, ok=True):
    status_tag = "[\033[92mOK\033[0m]" if ok else "[\033[91mFAIL\033[0m]"
    print(f"{status_tag} {msg}")

def verify():
    print("\033[95m=== AIOS Local Verification & Diagnostics ===\033[0m\n")
    
    # 1. Check folder structure
    base_dir = Path(__file__).resolve().parent
    print(f"Working Directory: {base_dir}")
    
    # Required dirs
    dirs = ["agents", "auth", "models", "orchestrator", "routes", "static", "services", "knowledge", "tests", "terraform"]
    missing_dirs = []
    for d in dirs:
        p = base_dir / d
        if not p.is_dir():
            missing_dirs.append(d)
    
    if missing_dirs:
        print_status(f"Missing folders: {missing_dirs}", False)
    else:
        print_status("Folder structure verified")

    # 2. Check essential files
    files = [
        "main.py", "seed.py", "cli.py", "mcp_server.py", "config.py", "database.py", "requirements.txt"
    ]
    missing_files = []
    for f in files:
        p = base_dir / f
        if not p.is_file():
            missing_files.append(f)
            
    if missing_files:
        print_status(f"Missing core files: {missing_files}", False)
    else:
        print_status("Core code files verified")

    # 3. Check packages / config
    sys.path.append(str(base_dir))
    try:
        from config import settings
        print_status(f"Configuration loaded (Environment: {settings.ENVIRONMENT})")
    except Exception as e:
        print_status(f"Configuration load failed: {e}", False)

    # 4. Check database models & schema tables
    try:
        from models.database import User, Incident, AgentTrace, KBDocument, ActionItem, ServiceTopology
        print_status("Database schema definitions imported successfully")
    except Exception as e:
        print_status(f"Database schema import failed: {e}", False)

    # 5. Check all 11 Agents imports
    agents = [
        "a1_intake", "a2_foundry_iq", "a2b_operational_context", "a3_correlation",
        "a4_risk_analyzer", "a5_action_planner", "a6_guardrail", "a7_communication",
        "a8_adversarial_review", "a9_retrospective", "a10_knowledge_ingest", "a11_web_search"
    ]
    missing_agents = []
    for a in agents:
        try:
            importlib.import_module(f"agents.{a}")
        except Exception as e:
            missing_agents.append((a, str(e)))
            
    if missing_agents:
        print_status(f"Agent imports failed: {missing_agents}", False)
    else:
        print_status("All 11 SRE Cognitive Agents imported successfully")

    # 6. Check UI files
    ui_files = [
        "static/index.html", "static/css/styles.css", "static/css/reasoning-canvas.css",
        "static/js/app.js", "static/js/components/decisionPanel.js", "static/js/components/dependencyGraph.js"
    ]
    missing_ui = []
    for u in ui_files:
        p = base_dir / u
        if not p.is_file():
            missing_ui.append(u)
            
    if missing_ui:
        print_status(f"Missing UI assets: {missing_ui}", False)
    else:
        print_status("Web SPA (Reasoning Canvas) UI assets verified")

    # 7. Check knowledge files
    knowledge_types = ["runbooks", "postmortems", "architecture_docs", "alerts", "work_iq_context"]
    missing_seed = []
    for k in knowledge_types:
        p = base_dir / "knowledge" / k
        if not p.is_dir() or not any(p.glob("*.json")):
            missing_seed.append(k)
            
    if missing_seed:
        print_status(f"Missing or empty knowledge seed directories: {missing_seed}", False)
    else:
        print_status("Runbook, postmortem, and knowledge asset files verified")

    print("\n\033[92m=== Diagnosis Complete: Ready to Run! ===\033[0m")
    print("Run `python seed.py` to initialize PostgreSQL-backed seed data.")
    print("Run `uvicorn main:app --reload` to start server.")

if __name__ == "__main__":
    verify()
