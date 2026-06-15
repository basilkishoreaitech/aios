# AIOS — Agentic Incident Operating System

> **An 11-agent AI system that takes a production alert and returns a grounded, risk-scored, approval-gated action plan in under 60 seconds — and gets smarter after every incident.**
> Microsoft Agents League 2026 · Reasoning Agents Track

[![Python 3.11](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![Azure OpenAI](https://img.shields.io/badge/Azure_OpenAI-gpt--5.4-0089D6?logo=microsoftazure)](https://azure.microsoft.com)
[![Foundry IQ](https://img.shields.io/badge/Foundry_IQ-Azure_AI_Search-5C2D91?logo=microsoftazure)](https://azure.microsoft.com)
[![CI](https://img.shields.io/badge/CI-pytest-brightgreen?logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![41 Tests Passing](https://img.shields.io/badge/tests-41%20passed-brightgreen?logo=pytest)](aios/tests/)
[![Architecture](https://img.shields.io/badge/Architecture-Mermaid_Diagram-ff6b35)](ARCHITECTURE.md)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## What Is AIOS?

When a production service breaks at 3 AM, the problem is rarely a lack of data — it's the lack of fast, disciplined reasoning across too many signals at once.

**AIOS turns alerts, deployments, team chat, runbooks, and past incidents into a single answer: "here is the most likely cause, here is the safest next step, and here is the evidence behind it."** It does this in under a minute, and it asks a human before doing anything risky.

|  | |
|---|---|
| **11 specialized AI agents** | each one does a single job well, then hands off |
| **Self-critiquing** | one agent's job is to challenge the others before any action is proposed |
| **Grounded in real knowledge** | every claim cites a real document from the knowledge base |
| **Safe by default** | risky actions are blocked or require human approval |
| **Learns continuously** | every resolved incident is scored and written back as new knowledge |
| **Proven** | 41 automated tests passing · live Azure integration · full infrastructure-as-code |

Every AI call hits real Azure OpenAI and every knowledge lookup queries live Azure AI Search — there is no mock or simulation path.

> **Human-in-the-loop is a feature, not a limitation.** AIOS deliberately does **not** auto-execute high-risk production changes. It does the hard part — reasoning, grounding, and risk-scoring — then hands a human a ready-to-approve action with full evidence. Governed autonomy, not blind autonomy.

→ **[▶ Open the animated architecture](docs/architecture.html)** (open in a browser — live data-flow animation) · [Mermaid diagram](#how-it-works--the-11-agent-pipeline) · [Full Architecture Doc](ARCHITECTURE.md)

---

## Why This Stands Out

- **It argues with itself before it acts.** One agent proposes causes; an independent critic agent tries to break them. Only what survives moves forward.
- **It shows its homework.** Every diagnosis cites a real document. Made-up citations are automatically rejected.
- **It refuses to do anything dangerous on its own.** High-risk fixes are blocked or held for human approval — never executed blindly.
- **It gets better every time.** After each incident, the system grades its own diagnosis and saves the lesson for next time.
- **It is a reasoning system, not a chat wrapper.** A staged pipeline with retrieval, critique, risk analysis, guardrails, and communication — not a single prompt.

**Business value:** shorter outages, fewer risky mistakes, clear accountability, and a team knowledge base that compounds with every incident.

### Engineering Highlights

AIOS is a governed, multi-agent reasoning system. Each capability below is implemented end to end and verifiable in the codebase.

| Capability | How AIOS implements it | Why it matters |
|---|---|---|
| **Deep reasoning** | 11 specialized agents in a staged pipeline | Each step is purpose-built and inspectable, not one opaque prompt |
| **Self-correction** | Adversarial critic (A8) runs on a *different* model and challenges every hypothesis | Catches confident-but-wrong conclusions before they act |
| **Hallucination control** | Citation enforcement — uncited hypotheses are rejected | Every diagnosis is grounded in a real document |
| **Safety** | Guardrails + RBAC + approval gates | Prompt injection and high-risk commands are blocked or held for sign-off |
| **Continuous learning** | A9 self-scores accuracy and A10 writes lessons back to the knowledge base | The system measurably improves with every incident |
| **Grounded retrieval** | Foundry IQ over runbooks, postmortems & topology | Answers are anchored to operational knowledge, not generic text |
| **Multiple surfaces** | Custom SPA + CLI + MCP server | Usable in the browser, terminal, and inside VS Code Copilot Chat |
| **Production readiness** | Terraform IaC + CI + 41 automated tests | Reproducible deployment and a tested, maintainable codebase |

---

## Table of Contents

- [Demo](#demo)
- [How It Works — The 11-Agent Pipeline](#how-it-works--the-11-agent-pipeline)
- [What Makes It Different](#what-makes-it-different)
- [Reliability, Safety & Governance](#reliability-safety--governance)
- [Data & Privacy](#data--privacy)
- [Built on Microsoft Azure](#built-on-microsoft-azure)
- [Use It Anywhere](#use-it-anywhere)
- [Contest Alignment](#contest-alignment)
- [Get Started](#get-started)

---

## Demo

> **▶ Video walkthrough** — [Watch on YouTube](https://youtu.be/-s4gOLjw7aY)


---

## Screenshots

<table>
  <tr>
    <td colspan="2" align="center">
      <img src="aios/screenshots/screenshot%20(4).png" alt="Full AIOS Reasoning Canvas" width="100%"/>
      <br/><strong>Full Reasoning Canvas</strong> — Incident Explorer · Grounded Evidence · 11-Agent Pipeline · Blast Radius · AI Chatbot, all live
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="aios/screenshots/screenshot%20(5).png" alt="AIOS login page" width="100%"/>
      <br/><strong>Login</strong> — animated AIOS logo with cyber-eye icon
    </td>
    <td width="50%" align="center">
      <img src="aios/screenshots/screenshot%20(7).png" alt="Incident Evidence panel" width="100%"/>
      <br/><strong>Incident Evidence</strong> — KB citations with relevance scores (runbooks · past incident reports)
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="aios/screenshots/screenshot%20(8).png" alt="Blast radius and risk analysis" width="100%"/>
      <br/><strong>Blast Radius Diagram</strong> — downstream impact, risk level, affected services count
    </td>
    <td width="50%" align="center">
      <img src="aios/screenshots/screenshot%20(9).png" alt="A9 self-scored diagnosis accuracy" width="100%"/>
      <br/><strong>A9 Self-Scored Accuracy</strong> — 100% diagnosis accuracy · auto-approved low-risk action
    </td>
  </tr>
  <tr>
    <td width="50%" align="center">
      <img src="aios/screenshots/screenshot%20(6).png" alt="AIOS AI Assistant chatbot" width="100%"/>
      <br/><strong>AIOS AI Assistant</strong> — grounded chatbot with cited KB sources (93% confidence)
    </td>
    <td width="50%" align="center">
      <img src="aios/screenshots/screenshot%20(10).png" alt="Incident postmortem export" width="100%"/>
      <br/><strong>Incident Report Export</strong> — full postmortem generated by A10 · downloadable Markdown
    </td>
  </tr>
  <tr>
    <td align="center">
      <img src="aios/screenshots/screenshot%20(1).png" alt="AIOS screenshot 1" width="100%"/>
    </td>
    <td align="center">
      <img src="aios/screenshots/screenshot%20(2).png" alt="AIOS screenshot 2" width="100%"/>
    </td>
  </tr>
  <tr>
    <td colspan="2" align="center">
      <img src="aios/screenshots/screenshot%20(3).png" alt="AIOS screenshot 3" width="70%"/>
    </td>
  </tr>
</table>

---

## How It Works — The 11-Agent Pipeline

**At a glance** — one alert flows top-to-bottom through four stages and comes out as a safe, evidence-backed plan:

```
ALERT → ① Understand & gather evidence → ② Form theories, then attack them
      → ③ Score risk & plan the fix safely → ④ Explain, get approval, and learn
```

Each agent has exactly one job and hands off to the next. Two feedback loops make it a *reasoning* system, not a single prompt: a critic can bounce a weak theory back to be re-thought, and every solved incident is written back as new knowledge.

> 💡 **Prefer a moving picture?** Open the **[animated architecture](docs/architecture.html)** in any browser to watch the signals flow through the pipeline live.

| Stage | What happens | Agents |
|---|---|---|
| **① Intake & Grounding** | Read the alert, scrub secrets, classify severity, and pull every relevant signal — runbooks, past incidents, deployments, on-call, chat (and the web only if nothing matches) | A1 · A2 · A2b · A11 |
| **② Reasoning & Critique** | Build ranked, explained root-cause theories — then an **independent critic on a different model** tries to break them | A3 · A8 |
| **③ Risk, Action & Guardrails** | Estimate blast radius, plan ordered fix steps, and run a deterministic safety check (injection, unsafe commands, citations) | A4 · A5 · A6 |
| **④ Communicate & Learn** | Write exec + engineer summaries, self-score the diagnosis, and write the resolved incident back to the knowledge base | A7 · A9 · A10 |

```mermaid
flowchart TB
    ALERT([" Live Alert / Raw Signal "]):::entry

    subgraph INTAKE["① INTAKE & GROUNDING"]
        direction TB
        A1["<b>A1 · Intake</b><br/>Parse · PII-scrub · Classify severity"]:::core
        A2["<b>A2 · Knowledge Retrieval</b><br/>Semantic search → runbooks · reviews"]:::retrieve
        A2b["<b>A2b · Operational Context</b><br/>Deployments · on-call · Teams chat"]:::core
        A11["<b>A11 · Web Search</b><br/>Novel failure patterns"]:::web
    end

    subgraph REASON["② REASONING & CRITIQUE"]
        direction TB
        A3["<b>A3 · Causal Correlation</b><br/>Evidence convergence · ranked hypotheses"]:::core
        A8{{"<b>A8 · Adversarial Review</b><br/>Independent critic challenges A3"}}:::critic
    end

    subgraph PLAN["③ RISK, ACTION & GUARDRAILS"]
        direction TB
        A4["<b>A4 · Risk Analyzer</b><br/>Blast radius · rollback cost"]:::core
        A5["<b>A5 · Action Planner</b><br/>Ordered remediation steps"]:::core
        A6["<b>A6 · Guardrail</b><br/>Injection · unsafe cmd · citation check"]:::guard
    end

    subgraph DELIVER["④ COMMUNICATE & LEARN"]
        direction TB
        A7["<b>A7 · Communication</b><br/>Exec summary · operator view · Teams"]:::core
        A9["<b>A9 · Retrospective</b><br/>Self-scores diagnosis accuracy"]:::learn
        A10["<b>A10 · Knowledge Ingest</b><br/>Writes incident review back to KB"]:::learn
    end

    ALERT --> A1
    A1 --> A2
    A1 --> A2b
    A2 -. "weak match" .-> A11
    A2 --> A3
    A2b --> A3
    A11 --> A3
    A3 --> A8
    A8 == "approved" ==> A4
    A8 -. "challenged · re-think" .-> A3
    A4 --> A5
    A5 --> A6
    A6 --> A7
    A7 --> A9
    A7 --> A10
    A10 -. "compounding knowledge" .-> A2

    classDef entry fill:#0f172a,stroke:#38bdf8,stroke-width:2px,color:#e0f2fe,font-weight:bold;
    classDef core fill:#1e293b,stroke:#475569,stroke-width:1px,color:#e2e8f0;
    classDef retrieve fill:#0c4a6e,stroke:#38bdf8,stroke-width:2px,color:#e0f2fe;
    classDef critic fill:#7f1d1d,stroke:#f87171,stroke-width:2px,color:#fee2e2;
    classDef guard fill:#7c2d12,stroke:#fb923c,stroke-width:2px,color:#ffedd5;
    classDef web fill:#4c1d95,stroke:#a78bfa,stroke-width:2px,color:#ede9fe;
    classDef learn fill:#064e3b,stroke:#34d399,stroke-width:2px,color:#d1fae5;

    style INTAKE fill:#f8fafc,stroke:#cbd5e1,stroke-width:1px,color:#475569;
    style REASON fill:#f8fafc,stroke:#cbd5e1,stroke-width:1px,color:#475569;
    style PLAN fill:#f8fafc,stroke:#cbd5e1,stroke-width:1px,color:#475569;
    style DELIVER fill:#f8fafc,stroke:#cbd5e1,stroke-width:1px,color:#475569;
```

> The dotted feedback arrows are what make this a *reasoning* system: **A8 → A3** sends a weak diagnosis back to re-think, and **A10 → A2** writes every resolved incident back into the knowledge base so the next outage is solved faster.

> **How alerts reach AIOS:** alerts are submitted to the `/api/ingest` endpoint — from the dashboard, the CLI, or any monitoring tool that can POST a webhook. Native one-click wiring to an Azure Monitor action group is on the near-term roadmap; today the same JSON contract any alerting system emits is accepted directly.


| Agent | Job |
|---|---|
| **A1 Intake** | Read the raw alert, remove sensitive data, classify severity |
| **A2 Knowledge Retrieval** | Search the knowledge base for relevant runbooks and past incidents |
| **A2b Operational Context** | Pull recent deployments, on-call roster, and team chat |
| **A11 Web Search** | Look up novel failure patterns when the knowledge base has no strong match |
| **A3 Correlation** | Combine all evidence into ranked, explained hypotheses |
| **A8 Adversarial Review** | Independently challenge those hypotheses to catch bias and errors |
| **A4 Risk Analyzer** | Estimate blast radius and rollback cost for each option |
| **A5 Action Planner** | Produce ordered, risk-tagged remediation steps |
| **A6 Guardrail** | Block unsafe commands, injection attempts, and unsupported claims |
| **A7 Communication** | Write both an executive summary and an engineer-level view |
| **A9 Retrospective** | Grade the diagnosis against the confirmed root cause |
| **A10 Knowledge Ingest** | Turn the resolved incident into reusable knowledge |

<details>
<summary>Model assignments and reasoning traces</summary>

| Agent | Deployment | Notes |
|---|---|---|
| A3, A4, A5 | `gpt-5.4` | Primary deployment for heavy reasoning |
| A8 | `gpt-4.1` | Deliberately a *different, independent* model so the critic isn't an echo chamber |
| A1, A7, A9, A10 | `gpt-5.4-mini` | Fast utility tasks and fallbacks |
| A6 | *Regex Guardrails* | No LLM used! Fast, deterministic pattern-matching safety layer |
| A2 | `text-embedding-3-small` | Knowledge base embedding and retrieval |

Every inference records a `reasoning_path`, so each step of the chain is auditable rather than a single opaque answer.

</details>

---

## What Makes It Different

### 1. It critiques itself before acting

Most AI incident tools produce a diagnosis and stop. AIOS runs an **independent critic** (a separate, low-cost model) that actively tries to disprove the diagnosis. If it finds a flaw, it lowers confidence and sends the pipeline back to re-think; if the reasoning holds, it lets it through. This single design choice is what separates a reasoning system from a confident-sounding guess.

<details>
<summary>The three failure modes the critic looks for</summary>

| Failure mode | Example it catches |
|---|---|
| Recency bias | "Blamed the latest deployment with no evidence the code change caused the errors" |
| Hallucinated correlation | "Cited a database-pool runbook when the real issue was DNS" |
| Missing external signals | "Ignored a Stripe outage mentioned in Teams messages" |

When the critic challenges a hypothesis it applies a negative confidence adjustment (e.g. −0.15) that flows downstream to the risk and action agents; an approval applies a small positive adjustment (+0.05).

</details>

### 2. It learns from every incident

After an incident is resolved, the **Retrospective agent grades its own diagnosis** on a 0.0–1.0 scale against the operator-confirmed root cause — giving the team a real, measurable signal of whether the AI is improving. The **Knowledge Ingest agent** then writes that resolved incident back into the knowledge base, so the next similar outage can be solved faster.

<details>
<summary>How the self-score works</summary>

```
1.0 — Exact match: top hypothesis identified the correct cause
0.8 — A secondary hypothesis was correct
0.5 — Right service, wrong cause (e.g. blamed pool size, real cause was a query lock)
0.0 — Complete mismatch
```

The score is stored per incident and shown on the dashboard.

</details>

### 3. It handles outages it has never seen

When the knowledge base has no strong match for an alert, AIOS automatically reaches out to **web search** for novel failure patterns — but only then, so it never wastes time or budget when it already has a good answer. A three-tier model fallback chain and a hard token budget keep it resilient and cost-bounded.

---

## Reliability, Safety & Governance

AIOS is built so that *being wrong is safe*. Six independent layers stand between an incoming alert and any real-world action:

1. **Rate limiting** — abusive request volume is rejected before a single AI token is spent
2. **Sensitive-data scrubbing** — credentials, tokens, and emails are stripped from alert text before any AI sees it
3. **Prompt-injection detection** — attempts to hijack the system ("ignore previous instructions", "auto-approve") block the entire action plan
4. **Unsafe-command blocking** — destructive commands (`rm -rf`, `DROP DATABASE`, and similar) can never appear in a generated fix
5. **Citation verification** — every conclusion must cite a real retrieved document; invented citations are flagged
6. **Human approval gate** — low/medium-risk actions need an on-call engineer; high-risk actions need an admin, and every approval is logged

Together these give the four properties a leadership team cares about: **security** (secrets in Key Vault, data scrubbed), **governance** (role-based approvals), **guardrails** (nothing dangerous is auto-executed), and **auditability** (every recommendation, approval, and outcome is traceable).

A pipeline-wide **token budget** acts as a circuit breaker: if reasoning ever runs away, execution halts cleanly instead of burning unbounded cost.

<details>
<summary>Implementation detail — guardrail and budget logic</summary>

```python
# Prompt-injection detection — any match blocks the whole plan
INJECTION_KEYWORDS = [
    "ignore previous instructions", "system override",
    "you must auto-approve", "bypass the gatekeeper",
]

# Unsafe-command blocking — any match tags that step "blocked"
UNSAFE_COMMANDS = [
    r"\brm\s+-rf\b", r"\bdrop\s+database\b",
    r"\bdelete\s+from\s+[a-zA-Z0-9_]+\s*$",   # DELETE without WHERE
    r"\bkill\s+-9\s+1\b", r"\bmkfs\b",
]

# Citation check  — each hypothesis must cite a doc_id/URL actually retrieved
# RBAC gate       — Low/Medium → "sre" role · High/Critical → "admin" role
# Rate limit      — @limiter.limit("10/minute") → HTTP 429 before any agent fires
```

**Token budget** — a `TokenBudgetTracker` monitors per-agent limits (advisory warnings) and enforces a 500,000-token global hard cap; breaching the global cap acts as a circuit breaker, raising a `TokenBudgetExceededError` to halt the run.

</details>

---

## Data & Privacy

AIOS is designed for enterprise deployment with privacy built into the pipeline, not bolted on afterward.

| Control | How AIOS handles it |
|---|---|
| **Regional data residency** | Deploys to whichever Azure region you choose — all data, models, and search stay inside that region |
| **Privacy by design** (GDPR Art. 25) | The Intake agent (A1) scrubs emails, IP addresses, tokens, and credentials from alert text **before any model sees it** |
| **No data used for training** | Azure OpenAI does not use prompts or completions to train models — your operational data stays yours |
| **No stored credentials** | All secrets live in Azure Key Vault; service-to-service auth uses Managed Identity |
| **Access control & accountability** (Art. 5) | JWT-based RBAC with role claims; every approval and outcome is logged with an incident ID and timestamp |
| **Data minimization** | Only scrubbed operational signals reach the reasoning models — raw alert payloads are never forwarded to external services |

> **Scope note:** AIOS is an internal operations tool. Incident records contain service telemetry and reasoning traces, not customer personal data — so consumer-facing GDPR mechanisms (consent banners, right-to-erasure portals) are out of scope by design, while the privacy controls above remain enforced.

---

## Built on Microsoft Azure

AIOS is a real cloud application, fully defined as infrastructure-as-code and deployable to any Azure region.

| Resource | Purpose |
|---|---|
| **Azure OpenAI** | The four AI models (reasoning, critic, utility, embedding) |
| **Azure AI Search (Foundry IQ)** | The grounded knowledge base behind every citation |
| **Azure App Service** | Hosts the application |
| **Azure PostgreSQL** | Stores incidents, reasoning traces, and topology |
| **Azure Key Vault** | Holds all secrets — none live in code |
| **Application Insights + Log Analytics** | Telemetry and centralized logging |
| **Managed Identity** | Passwordless, credential-free access between services |

### The Knowledge Base (Foundry IQ)

The knowledge base is what keeps every answer grounded. It is uploaded to Azure AI Search on first setup:

| Category | Content |
|---|---|
| **Alert scenarios** | 10 real-world failure patterns (DB pool exhaustion, memory leaks, DNS, TLS expiry, K8s OOM, and more) |
| **Runbooks** | 11 operational fix procedures |
| **Incident reviews** | 13 past incidents explaining what happened and how it was fixed |
| **Operational context** | Deployment calendar, on-call roster, team chat history |

The retrieval agent cites specific documents, and the guardrail agent verifies those citations exist — so the system shows its evidence instead of making unsupported claims.

> 🗺️ **Full system architecture** (client surfaces → FastAPI backend → Azure platform) lives in **[ARCHITECTURE.md](ARCHITECTURE.md)**, and the **[animated version](docs/architecture.html)** opens in any browser.

**Stack:** Python 3.11 · FastAPI (async) · SQLAlchemy · Azure OpenAI · Azure AI Search · Vanilla-JS SPA · FastMCP · `click` CLI · Microsoft Teams webhooks.

---

## Use It Anywhere

The same reasoning engine is reachable from three surfaces, so it fits however a team already works.

### Reasoning Canvas (browser)
A live dashboard that streams each agent's progress as it thinks, draws the affected service and its dependencies, shows confidence bars per hypothesis, and offers inline approval buttons. Operators can even attach a screenshot of an error graph for the AI to analyze.

The UI uses a **floating action button (FAB) layout**:
- **IE button** (bottom-left) — opens the Incident Explorer sidebar on demand
- **AI button** (bottom-right) — opens the AI chatbot assistant panel on demand
- When both panels are closed, the main canvas expands to a three-column view: evidence · diagnostics+actions · AI reasoning
- Both panels are hidden off-canvas by default and slide in on FAB click

### VS Code / Copilot Chat (MCP)
Through the Model Context Protocol, any LLM client can drive AIOS in natural language — *"What are the active incidents?"* or *"Approve the DB rollback for incident 4217."*

| Tool | What it does |
|---|---|
| `list_active_incidents` | List unresolved outages with severity and status |
| `get_incident_reasoning` | Full hypotheses, critic verdict, and engineer trace |
| `approve_action_gate` | Approve a pending fix from inside the chat window |

### Terminal (CLI)
```bash
python cli.py login
python cli.py query "list active incidents"
python cli.py approve INC-0042 ACT-001
```

<details>
<summary>MCP client configuration (VS Code / Cursor)</summary>

```json
{
  "mcpServers": {
    "aios-operations": {
      "command": "python",
      "args": ["/path/to/aios/mcp_server.py"],
            "env": { "DATABASE_URL": "postgresql+asyncpg://user:password@your-postgres-server.postgres.database.azure.com:5432/aiosdev?ssl=require" }
    }
  }
}
```

</details>

---

## Contest Alignment

AIOS covers **every** judging criterion for the Reasoning Agents track — and treats the mandatory Foundry IQ layer as the backbone of the whole system, not an add-on.

| Evaluation Criterion | How AIOS Delivers | Source |
|---|---|---|
| 🧠 **Reasoning & Multi-Step** | 11-agent pipeline · evidence convergence · **adversarial critic loop** · auditable reasoning traces · **self-scored diagnosis accuracy** · continuous learning | [a3_correlation.py](aios/agents/a3_correlation.py) · [a8_adversarial_review.py](aios/agents/a8_adversarial_review.py) · [a9_retrospective.py](aios/agents/a9_retrospective.py) |
| 🛡️ **Reliability & Safety** | **6-layer safety stack**: rate limit → data scrub → injection detection → unsafe-command block → citation check → human approval gate · evidence-grounded confidence ceiling | [a6_guardrail.py](aios/agents/a6_guardrail.py) · [rbac.py](aios/auth/rbac.py) · [ingest.py](aios/routes/ingest.py) |
| ✅ **Accuracy & Relevance** | Every hypothesis cites a real retrieved document · invented citations are rejected · answers never exceed the confidence their evidence supports · 10 deterministic golden scenarios | [a2_foundry_iq.py](aios/agents/a2_foundry_iq.py) · [test_golden_scenarios.py](aios/tests/test_golden_scenarios.py) |
| 🔌 **Foundry IQ Integration** | Live Azure AI Search retrieval · grounded citation per hypothesis · resolved incidents written **back** to the knowledge base so it compounds | [a2_foundry_iq.py](aios/agents/a2_foundry_iq.py) · [embedding_service.py](aios/services/embedding_service.py) |
| 🎨 **Creative UX & Ecosystem** | Streaming Reasoning Canvas · dependency graph · **MCP server** · CLI · Teams webhook · screenshot analysis | [mcp_server.py](mcp_server.py) · [cli.py](cli.py) |
| 🌐 **Resilience & Novel Failures** | Web-search fallback for unseen outages · 3-tier model chain · token-budget circuit breaker | [a11_web_search.py](aios/agents/a11_web_search.py) · [model_router.py](aios/services/model_router.py) · [token_budget.py](aios/services/token_budget.py) |

---

## Get Started

> **Evaluating this project?** The fastest path is the **[▶ video walkthrough](#demo)** and the **[animated architecture](docs/architecture.html)** — they show the full reasoning loop without any setup. The steps below are for running it yourself, and require **your own Azure resources** (Azure OpenAI + Azure AI Search), so they're optional.

### Prerequisites
Python 3.11 · PowerShell 7.4+ · an Azure OpenAI resource with `gpt-5.4`, `gpt-5.4-mini`, `gpt-4.1`, and `text-embedding-3-small` deployments · an Azure AI Search service · (PostgreSQL optional — falls back as configured).

> ⚠️ **Model availability varies by region.** If a deployment name isn't available in your Azure region, just point the matching `AZURE_OPENAI_DEPLOYMENT_*` variable in `.env` at a model you do have — the code works with any chat-completions deployment.

### Run it locally (against your Azure resources)
```powershell
# 1. From the repo root
cd aios
python -m pip install -r requirements.txt

# 2. Create your .env from the template and fill in your Azure endpoints/keys
Copy-Item .env.example .env
notepad .env          # set AZURE_OPENAI_*, FOUNDRY_IQ_*, DATABASE_URL

# 3. Seed the demo users and topology data, then start the server
python seed.py        # run once to create users, topology, and operational context
cd ..
./start-aios.ps1 -ForceRestart      # serves http://localhost:8000
# Note: the server no longer auto-seeds on startup — run seed.py manually once
```

Then open `http://localhost:8000` and log in as **`admin` / `aios-admin-2026`**.

- **Diagnostics:** `python verify_setup.py` (checks config, Azure connectivity, and the knowledge base)
- **Tests:** `python -m pytest -q` *(41 passed)* — these run without any Azure resources
- **Accuracy harness:** `python evaluate_scenarios.py` — replays all 10 golden scenarios and prints average diagnosis accuracy

### Deploy to Azure (optional)
Full infrastructure-as-code lives in [aios/terraform/](aios/terraform/). Provide your own variables (subscription, region, resource names) and apply:
```powershell
cd aios/terraform
terraform init
terraform apply        # provisions Azure OpenAI, AI Search, App Service, Key Vault, etc.
```
After the resources exist, populate the knowledge base and deploy the app code, then browse to your App Service URL.

<details>
<summary>Default accounts, test suite, and repository layout</summary>

**Pre-seeded accounts** (change passwords outside of demo environments):

| Role | Username | Permissions |
|---|---|---|
| SRE Admin | `admin` | Approve high-risk actions · manage KB · full read |
| On-Call Engineer | `engineer` | Query KB · approve low/medium actions · run triage |
| Executive | `executive` | Read-only dashboards and summaries |

**Test suite — 41 tests across 16 files:**

| File | Covers |
|---|---|
| `test_a1_intake.py` | Intake parsing, data scrub, severity |
| `test_a3_correlation.py` | Hypothesis generation and scoring |
| `test_a6_guardrail.py` | Injection detection, unsafe-command blocking |
| `test_a8_reviewer.py` | Critic verdict and confidence propagation |
| `test_a11_web_search.py` | Web-search fallback gate |
| `test_auth.py` | JWT roles and RBAC |
| `test_cli.py` | CLI and operator-hint re-evaluation |
| `test_golden_scenarios.py` | End-to-end over all 10 scenarios |
| `test_model_router.py` | Model fallback chain |
| `test_query_service.py` | KB search, image evidence, and zero-evidence grounding guard |

**Repository layout:**

```
aios/
├── main.py          # FastAPI entry point
├── seed.py          # DB seeder (users, topology, context)
├── cli.py           # terminal companion
├── mcp_server.py    # MCP server — 3 SRE tools for LLM clients
├── config.py        # env-based configuration
├── agents/          # 11 cognitive agents (A1 → A11)
├── orchestrator/    # streaming pipeline coordinator
├── routes/          # API endpoints
├── services/        # model router, embeddings, token budget, web search
├── models/          # request/response and ORM schemas
├── auth/            # JWT decoding and RBAC gates
├── knowledge/       # corpus uploaded to Azure AI Search
├── static/          # Reasoning Canvas frontend
├── terraform/       # full Azure infrastructure-as-code
├── scripts/         # PowerShell bootstrap scripts
└── tests/           # 41 passing tests
```

</details>
