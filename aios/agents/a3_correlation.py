import logging
from sqlalchemy.ext.asyncio import AsyncSession

from agents.base_agent import BaseAgent
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from models.operational_context import OperationalContext
from models.hypothesis import HypothesisSet
from config import Settings
from services.model_router import ModelRouter
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.agents.a3")

A3_SYSTEM_PROMPT = """You are the AIOS Causal Correlation and Multi-Signal Convergence Agent (A3).
Your job is to correlate multiple signals (alert details, local KB runbooks/postmortems, recent deployments, Teams chats, and web search results) to formulate root-cause hypotheses for the active incident.

Analyze the correlation vectors:
1. Time correlation: Did a recent deployment occur just before the alert fired?
2. Chat correlation: Did engineers chat about changing database configurations, hotfixes, or upstream API issues?
3. Historical correlation: Does a past incident postmortem document similar symptoms (e.g. connection pool size, memory leak libraries)?
4. Web correlation: If this is a novel error with no local matches, do web search results explain what the error means (e.g., JWKS endpoint network rules)?

GROUNDING RULES — STRICTLY FOLLOW:
- Base every GROUNDED hypothesis on EVIDENCE provided in the prompt sections below (KB citations, web results, deployments, Teams messages, operator hints).
- When a hypothesis is supported by evidence, cite it: use ONLY the doc_id values listed in the KB section in evidence_citations — never fabricate IDs.
- Do NOT claim a hypothesis is grounded if no evidence supports it.

WHEN EVIDENCE IS PRESENT: rank grounded hypotheses by confidence (highest first), each tied to its supporting evidence.

WHEN ALL EVIDENCE SECTIONS ARE EMPTY ('No local knowledge base documents matched' AND 'No web search fallback results' AND no deployments AND no Teams messages):
- You MAY still provide up to TWO best-effort hypotheses derived from general SRE/engineering knowledge of the alert symptoms, so the operator is never left with nothing.
- BUT for every such ungrounded hypothesis you MUST: (a) cap confidence at 0.35 or lower, (b) prefix causal_factor with 'ungrounded:' (e.g. 'ungrounded:connection_pool_exhaustion'), (c) leave evidence_citations EMPTY, and (d) state explicitly in reasoning_path that these are general-knowledge inferences NOT grounded in the knowledge base or web, and recommend verification before action.
- Never present an ungrounded hypothesis above 0.35 confidence. Set convergence_score <= 0.2 in this case.

Rank your root-cause hypotheses by confidence (highest first).
Compute a 'convergence_score' (0.0 to 1.0) indicating how strongly the different signals (alert, KB runbooks/postmortems, calendar deployment, Teams messages) point to the same root cause.
If an 'OPERATOR DIAGNOSTIC HINT' is present, treat it as high-priority context and align your hypotheses accordingly.
Detail your step-by-step reasoning in the 'reasoning_path' field.
"""

class CorrelationAgent(BaseAgent):
    """A3 Correlation Agent: Formulates root-cause hypotheses by correlating alert telemetry with KB files and operational logs."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        token_tracker: TokenBudgetTracker
    ):
        super().__init__("A3_Correlation", config, model_router, token_tracker)
        # Primary reasoning budget
        self.token_tracker.set_agent_limit("A3_Correlation", config.TOKEN_BUDGET_PRIMARY)

    async def _run(
        self,
        session: AsyncSession,
        incident_id: str,
        packet: IncidentPacket,
        evidence: EvidenceBundle,
        context: OperationalContext
    ) -> HypothesisSet:
        logger.info(f"Formulating hypotheses for incident {incident_id} (Service: {packet.service_name})")

        has_kb  = bool(evidence.kb_citations)
        has_web = bool(evidence.web_citations)
        if not has_kb and not has_web:
            logger.warning(
                "No KB or web evidence available for incident %s — grounding gap. "
                "A3 will return low-confidence 'insufficient_evidence' hypothesis.",
                incident_id
            )
        
        # 1. Format the inputs for the LLM prompt
        kb_text = ""
        for i, c in enumerate(evidence.kb_citations, 1):
            kb_text += (
                f"[{i}] Category: {c.category} | Title: {c.title} (Doc ID: {c.doc_id})"
                f" | Relevance: {c.relevance:.2f}\nSnippet: {c.content_snippet}\n\n"
            )
            
        web_text = ""
        for i, w in enumerate(evidence.web_citations, 1):
            web_text += f"[{i}] Title: {w.title} | URL: {w.url}\nSnippet: {w.snippet}\n\n"

        deploy_text = ""
        for d in context.deployments:
            deploy_text += f"- Service '{d.service_name}' version {d.version} deployed by {d.deployed_by} at {d.deployed_at.isoformat()}. Status: {d.status}. Details: {d.details}\n"

        chat_text = ""
        for m in context.teams_messages:
            chat_text += f"- [{m.timestamp.isoformat()}] {m.author} in {m.channel}: \"{m.content}\"\n"

        prompt = f"""=== ACTIVE ALERT DETAILS ===
Title: {packet.title}
Service: {packet.service_name}
Severity: {packet.severity}
Description: {packet.description}
Metrics: {packet.metrics}

=== EVIDENCE: LOCAL KB MATCHES ===
{kb_text or 'No local knowledge base documents matched.'}

=== EVIDENCE: WEB SEARCH RESULTS ===
{web_text or 'No web search fallback results.'}

=== OPERATIONAL CONTEXT: RECENT DEPLOYMENTS ===
{deploy_text or 'No recent deployments.'}

=== OPERATIONAL CONTEXT: RECENT TEAMS CHAT ===
{chat_text or 'No recent Teams messages.'}
"""

        if packet.operator_hint:
            prompt += f"\n=== OPERATOR DIAGNOSTIC HINT ===\n{packet.operator_hint}\n"

        messages = [
            {"role": "system", "content": A3_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        logger.info("Executing hypothesis generation via primary reasoning model.")
        try:
            hypothesis_set = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=HypothesisSet,
                preferred="primary",  # mai-thinking-1
                fallback="fallback"   # gpt-5.4-mini low-cost reviewer deployment
            )
            return hypothesis_set
        except Exception as e:
            logger.error(f"Error executing correlation agent: {e}")
            raise e
