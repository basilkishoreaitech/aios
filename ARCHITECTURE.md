# AIOS Architecture

```mermaid
graph TD
    U[Operator Browser / MCP Client / CLI] --> W[AIOS FastAPI App]
    W --> P[Incident Pipeline]

    P --> I1[A1 Intake · PII scrub · severity]
    P --> I2[A2 Foundry IQ Retrieval · semantic KB search]
    P --> I3[A2b Operational Context · deployments · Teams · on-call]
    I2 -->|max_sim lt 0.55| I11[A11 Web Search · Bing · novel patterns]
    I1 --> I4
    I2 --> I4
    I3 --> I4
    I11 --> I4

    I4[A3 Correlation · 4-vector convergence · ranked hypotheses] --> I5
    I5{A8 Adversarial Review · confidence_delta · echo-chamber check}
    I5 -->|challenged| I4
    I5 -->|approved| I6

    I6[A4 Risk Analyzer · blast radius · rollback cost]
    I6 --> I7[A5 Action Planner · staged remediation · risk_tags]
    I7 --> I8[A6 Guardrail · injection · unsafe cmd · citation check]
    I8 --> I9[A7 Communication · exec summary · Teams webhook]
    I9 --> I10[A9 Retrospective · self-score diagnosis accuracy 0.0-1.0]
    I9 --> I12[A10 Knowledge Ingest · postmortem → KB continuous learning]

    I2 --> S[Azure AI Search Knowledge Base]
    S --> KB[Foundry IQ Knowledge Source / Index]
    KB --> DOCS[Runbooks · Postmortems · Work IQ Context]

    I4 --> OAI[Azure OpenAI · gpt-5.4]
    I5 --> OAI2[Azure OpenAI · gpt-4.1 · independent critic]
    I6 --> OAI
    I7 --> OAI
    I9 --> OAI3[Azure OpenAI · gpt-5.4-mini]
    I10 --> OAI3
    I12 --> EMB[Azure OpenAI · text-embedding-3-small]

    W --> DB[(Azure PostgreSQL Flexible Server)]
    W --> KV[Azure Key Vault · all secrets passwordless]
    W --> AI[Application Insights · telemetry]
    W --> LA[Log Analytics]
    W -. conditional .-> B[Bing Search API · A11 fallback only]

    style I5 fill:#e74c3c,color:#fff
    style I8 fill:#e67e22,color:#fff
    style I2 fill:#2980b9,color:#fff
    style I11 fill:#8e44ad,color:#fff
    style I10 fill:#27ae60,color:#fff
    style I12 fill:#27ae60,color:#fff
```

## Runtime Notes

- The web application runs on Azure App Service with a user-assigned managed identity.
- Secrets are written to Key Vault and then injected into App Service settings.
- Foundry IQ retrieval is implemented through Azure AI Search knowledge base APIs using the `retrieve` endpoint.
- The bootstrap PowerShell script creates the search index, uploads repository knowledge, creates the knowledge source, and creates the knowledge base.
