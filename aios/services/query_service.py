import re
import logging
import json
import base64
from typing import List, Dict, Any, Optional, Tuple
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_
from pydantic import BaseModel

from config import Settings
from models.database import Incident, KBDocument
from models.evidence import Citation, WebCitation
from models.query import QueryRequest, QueryResponse, IncidentSummary
from services.embedding_service import EmbeddingService, cosine_similarity
from services.llm_firewall import LLMFirewall
from services.web_search_service import WebSearchService
from services.model_router import ModelRouter

logger = logging.getLogger(__name__)

PROMPT_SNIPPET_LIMIT = 220
PROMPT_INCIDENT_LIMIT = 260

# ── Intent detection patterns ─────────────────────────────────────────────────
import re as _re

_OPEN_STATUSES   = {"open", "active", "ongoing", "in progress", "current", "live", "investigating", "investigation", "unresolved", "outstanding", "pending"}
_CLOSED_STATUSES = {"resolved", "closed", "fixed", "done", "completed"}

# Phrases that signal "list all incidents" intent — broad to catch natural phrasing
_LIST_INCIDENT_RE = _re.compile(
    r"\b(show|list|get|display|fetch|give me|what are|tell me|find|pull up|check)\b.{0,50}\b(incidents?|alerts?|issues?|outages?|tickets?)\b"
    r"|\b(incidents?|alerts?|issues?|outages?|tickets?)\b.{0,30}\b(open|active|ongoing|current|all|recent|latest|investigating|investigation|in progress|right now)\b"
    r"|\b(all|any|current|active|open|recent|latest|ongoing|live)\b.{0,30}\b(incidents?|alerts?|issues?|outages?|tickets?)\b"
    r"|\bwhat.{0,30}(incidents?|alerts?|outages?).{0,30}(open|active|current|have|exist|happening|going on)\b"
    r"|\b(are there|is there|do we have|do i have).{0,30}(open|active|ongoing|current)?.{0,20}(incidents?|alerts?|issues?|outages?)\b",
    _re.IGNORECASE
)

# Broader guard: queries that are clearly about AIOS's internal state, not general knowledge
# Used to suppress web search even when the list intent regex misses
_INTERNAL_DATA_RE = _re.compile(
    r"\b(my|our|aios|current|active|open|ongoing|live|the)\b.{0,50}\b(incidents?|alerts?|outages?|issues?)\b"
    r"|\b(incidents?|alerts?)\b.{0,40}\b(now|today|currently|at the moment|right now|in progress|investigating)\b"
    r"|\b(how many|count|number of).{0,30}(incidents?|alerts?|issues?)\b"
    r"|\bincident (history|list|count|status|summary|detail)\b"
    r"|\b(status of|update on|progress on).{0,40}(incident|alert|outage|issue)\b",
    _re.IGNORECASE
)


def _detect_incident_list_intent(question: str) -> Optional[str]:
    """Return the target status filter if the question is a direct incident list request.

    Returns:
        'open'     — wants active/open/ongoing incidents
        'resolved' — wants resolved/closed incidents
        'all'      — wants every incident
        None       — not a list intent
    """
    if not _LIST_INCIDENT_RE.search(question):
        return None
    q = question.lower()
    if any(w in q for w in _OPEN_STATUSES):
        return "open"
    if any(w in q for w in _CLOSED_STATUSES):
        return "resolved"
    return "all"


def _is_internal_data_query(question: str) -> bool:
    """Return True if the question is about AIOS's own internal incidents/data.

    Web search can never answer these — they require DB access.
    Used to suppress the web-search fallback for internal management queries.
    """
    if _detect_incident_list_intent(question) is not None:
        return True
    return bool(_INTERNAL_DATA_RE.search(question))


def _trim_for_prompt(text: str, limit: int) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _build_llm_failure_answer(
    kb_citations: List[Citation],
    related_incidents: List[IncidentSummary],
    web_citations: List[WebCitation]
) -> str:
    lines = [
        "The AI answer generator is temporarily busy, so this is a grounded fallback based only on retrieved evidence.",
    ]

    if kb_citations:
        lines.append("Top supporting materials:")
        for citation in kb_citations[:3]:
            lines.append(f"- {citation.title}: {_trim_for_prompt(citation.content_snippet, 120)}")

    if related_incidents:
        lines.append("Closest verified past incidents:")
        for incident in related_incidents[:2]:
            lines.append(f"- {incident.title} ({incident.severity}, {incident.service_name})")

    if web_citations:
        lines.append("Additional external references:")
        for web_result in web_citations[:2]:
            lines.append(f"- {web_result.title}")

    lines.append("Retry in a few seconds or narrow the question to a specific service, error, or timeframe for a more precise answer.")
    return "\n".join(lines)

# --- PII & Secrets Sanitization Regex Pattern List ---
PII_PATTERNS = [
    (re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'), '[EMAIL_REDACTED]'),
    (re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'), '[IP_REDACTED]'),
    (re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'), '[IP_REDACTED]'),
    (re.compile(r'(?i)(bearer\s+[a-zA-Z0-9_\-\.]+)'), 'Bearer [SECRET_REDACTED]'),
    (re.compile(r'(?i)(password|passwd|client_secret|api_key|secret)\s*[:=]\s*[^\s,\'\"#]+'), r'\1=[SECRET_REDACTED]'),
    (re.compile(r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}[A-Z0-9]{1,16}\b'), '[IBAN_REDACTED]'),
    (re.compile(r'\b\d{3}-\d{2}-\d{4}\b'), '[SSN_REDACTED]'),
    (re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b'), '[CARD_REDACTED]'),
    (re.compile(r'\bghp_[a-zA-Z0-9]+\b'), '[SECRET_REDACTED]'),
]

def scrub_pii(text: str) -> str:
    """Scrub PII, emails, secrets, credentials, and IP addresses from any string."""
    if not text:
        return text
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


QUERY_SYSTEM_PROMPT = """You are AIOS — an Agentic Incident Operating System assistant for SRE and operations teams.
Answer questions about past incidents, runbooks, procedures, and operational knowledge using the retrieved evidence below.

Rules:
1. Write a direct, technically precise answer in 2–4 sentences. One flowing paragraph — no bullet points, no headers, no markdown.
2. Lead with the answer immediately. No preamble like "Based on the evidence..." or "According to the knowledge base..."
3. Do NOT put citation numbers like [1] or [2] in your answer text — sources are displayed separately in the UI.
4. Synthesize the evidence naturally into plain prose. If a runbook has key steps, summarize them concisely in one sentence.
5. If no relevant evidence is provided, say: "I don't have enough context — try specifying the service name, error message, or timeframe."
6. Never mention external tools (ServiceNow, PagerDuty, Jira, Datadog) unless they appear in the actual evidence.
7. Confidence 0.0–1.0: 0.85–0.95 if evidence directly answers; 0.60–0.75 if partial match; 0.35–0.55 if weak.
"""

class QueryService:
    """Orchestrates natural language searches across knowledge base documents, past incidents, and Bing Web Search."""
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        web_search_service: WebSearchService,
        model_router: ModelRouter
    ):
        self.embedding_service = embedding_service
        self.web_search_service = web_search_service
        self.model_router = model_router
        self.firewall = LLMFirewall()

    async def analyze_image_evidence(self, image_evidence: Dict[str, Any]) -> Dict[str, Any]:
        """Extract structured operational signals from an uploaded screenshot or log image."""
        filename = image_evidence.get("filename", "evidence")
        content_type = image_evidence.get("content_type", "application/octet-stream")
        raw_bytes = image_evidence.get("bytes", b"")

        if not raw_bytes:
            return {"summary": "No image bytes were provided.", "signals": [], "clarifying_questions": []}

        if not self.model_router.enabled:
            raise ValueError("Image evidence analysis requires a live Azure OpenAI deployment.")

        prompt = [
            {
                "type": "text",
                "text": (
                    "You are extracting only operational evidence from an outage screenshot or log image. "
                    "Return strict JSON with keys summary, signals, probable_services, and clarifying_questions. "
                    "Do not infer root cause. Extract visible error strings, service names, HTTP codes, timestamps, and stack fragments only."
                )
            },
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{content_type};base64,{base64.b64encode(raw_bytes).decode('utf-8')}"
                }
            }
        ]

        response_text = await self.model_router.call_with_fallback(
            messages=[
                {"role": "system", "content": "Extract structured evidence from SRE screenshots without hallucinating."},
                {"role": "user", "content": prompt}
            ],
            preferred="fallback",
            fallback="utility"
        )

        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.warning("Vision evidence response was not valid JSON. Returning raw summary.")
            return {
                "summary": str(response_text),
                "signals": [],
                "probable_services": [],
                "clarifying_questions": []
            }

    async def _classify_intent(self, question: str) -> str:
        """Classify query intent via LLM for robust natural-language understanding.

        Returns one of: list_open | list_resolved | list_all | kb_search | general
        Falls back to the compiled regex if the LLM call fails.
        """
        system = (
            "You are an intent classifier for an incident management chatbot. "
            "Classify the user query into exactly one label. Reply with ONLY the label, nothing else.\n\n"
            "Labels:\n"
            "- list_open: show/list open, active, current, unresolved, ongoing, or investigating incidents/alerts/issues\n"
            "- list_resolved: show/list resolved, closed, fixed, or completed incidents\n"
            "- list_all: show/list all incidents regardless of status\n"
            "- kb_search: asking about runbooks, procedures, how-to guides, postmortems, or documentation\n"
            "- general: root cause, details of a specific incident, diagnosis, error explanation, or anything else\n\n"
            "Examples:\n"
            '"show me open incidents" \u2192 list_open\n'
            '"show me unresolved issues" \u2192 list_open\n'
            '"what incidents are active right now" \u2192 list_open\n'
            '"any ongoing outages" \u2192 list_open\n'
            '"list resolved incidents" \u2192 list_resolved\n'
            '"show all closed tickets" \u2192 list_resolved\n'
            '"show all incidents" \u2192 list_all\n'
            '"walk me through the db connection pool runbook" \u2192 kb_search\n'
            '"how do I handle OOMKill" \u2192 kb_search\n'
            '"what was the root cause of the api-gateway outage" \u2192 general\n'
            '"what happened to db-service last week" \u2192 general'
        )
        try:
            result = await self.model_router.call_with_fallback(
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": question}
                ],
                preferred="utility",
                fallback="fallback"
            )
            intent = str(result).strip().lower()
            valid = {"list_open", "list_resolved", "list_all", "kb_search", "general"}
            if intent not in valid:
                regex_result = _detect_incident_list_intent(question)
                return f"list_{regex_result}" if regex_result else "general"
            return intent
        except Exception:
            regex_result = _detect_incident_list_intent(question)
            return f"list_{regex_result}" if regex_result else "general"

    async def list_incidents(
        self,
        session: AsyncSession,
        status_filter: str = "open",
        limit: int = 20
    ) -> QueryResponse:
        """Return a direct, formatted list of incidents from the database.

        Used when intent detection identifies the question as a list/show request
        rather than a knowledge-retrieval question.
        """
        stmt = select(Incident).order_by(Incident.created_at.desc()).limit(limit)
        if status_filter in ("open", "resolved"):
            if status_filter == "open":
                stmt = stmt.where(Incident.status.in_(["open", "investigating"]))
            else:
                stmt = stmt.where(Incident.status == "resolved")

        result = await session.execute(stmt)
        incidents = result.scalars().all()

        label = {
            "open":     "open / active",
            "resolved": "resolved",
            "all":      "all",
        }.get(status_filter, status_filter)

        if not incidents:
            answer = f"No {label} incidents found in the database."
        else:
            lines = [f"**{len(incidents)} {label} incident(s):**\n"]
            for inc in incidents:
                age = ""
                if inc.created_at:
                    from datetime import timezone as _tz
                    now = __import__('datetime').datetime.now(_tz.utc)
                    delta = now - inc.created_at.replace(tzinfo=_tz.utc) if inc.created_at.tzinfo is None else now - inc.created_at
                    mins = int(delta.total_seconds() / 60)
                    age = f"{mins}m ago" if mins < 120 else f"{mins // 60}h ago"
                lines.append(
                    f"• **[{inc.severity}]** {inc.title}  "
                    f"— `{inc.service_name}` | status: `{inc.status}` | {age}"
                )
            answer = "\n".join(lines)

        summaries = [
            IncidentSummary(
                id=inc.id,
                title=inc.title,
                service_name=inc.service_name,
                severity=inc.severity,
                status=inc.status,
                created_at=inc.created_at,
            )
            for inc in incidents
        ]

        return QueryResponse(
            answer=answer,
            citations=[],
            related_incidents=summaries,
            clarifying_questions=[],
            evidence_summary=None,
            confidence=1.0,
            source_breakdown={"kb": 0, "incidents_db": len(incidents), "web": 0},
        )

    async def search_past_incidents(
        self,
        session: AsyncSession,
        query_text: str,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Tuple[Incident, float]]:
        """Search the database for past incidents using hybrid lexical + semantic scoring.

        Returns (incident, match_score) tuples sorted by descending relevance so
        callers can distinguish a strong match from an incidental keyword hit.
        """
        stmt = select(Incident)

        # Apply filters if present
        if filters:
            if filters.get("service_name"):
                stmt = stmt.where(Incident.service_name == filters["service_name"])
            if filters.get("severity"):
                stmt = stmt.where(Incident.severity == filters["severity"])
            if filters.get("status"):
                stmt = stmt.where(Incident.status == filters["status"])

        # Execute query
        result = await session.execute(stmt)
        incidents = result.scalars().all()

        query_embedding = await self.embedding_service.embed(query_text)
        
        # Keyword search in Python over incident fields. Drop trivial short tokens
        # so single characters and noise words do not produce phantom matches.
        matched: List[Tuple[Incident, float]] = []
        words = [w for w in query_text.lower().split() if len(w) > 2]
        for inc in incidents:
            searchable_fields = [
                inc.title or "",
                inc.service_name or "",
                inc.engineer_view or "",
                inc.executive_view or "",
                inc.actual_root_cause or ""
            ]
            combined = " ".join(searchable_fields).lower()
            keyword_hits = sum(1 for w in words if w in combined)
            keyword_score = min(1.0, keyword_hits / max(2, len(words))) if words else 0.0

            semantic_text = " ".join(field for field in searchable_fields if field).strip()
            semantic_score = 0.0
            if semantic_text and query_embedding:
                incident_embedding = await self.embedding_service.embed(semantic_text)
                if incident_embedding:
                    semantic_score = cosine_similarity(query_embedding, incident_embedding)

            combined_score = max(semantic_score, keyword_score)
            if combined_score >= 0.35 or keyword_hits >= 2:
                matched.append((inc, combined_score))
                
        # Sort by match score descending
        matched.sort(key=lambda x: x[1], reverse=True)
        return matched[:5]

    async def run_query(
        self,
        session: AsyncSession,
        request: QueryRequest,
        image_evidence: Optional[Dict[str, Any]] = None
    ) -> QueryResponse:
        """Run the interactive query pipeline: intake -> search KB -> search DB -> web fallback -> LLM answer."""
        # 1. Scrub PII from query
        sanitized_query = scrub_pii(request.question)
        logger.info(f"Query intake: '{request.question}' -> Scrubbed: '{sanitized_query}'")

        # ── LLM intent classification — routes list queries directly to DB ──────
        intent = await self._classify_intent(sanitized_query)
        if intent.startswith("list_"):
            status_map = {"list_open": "open", "list_resolved": "resolved", "list_all": "all"}
            logger.info("Intent '%s' detected. Querying DB directly.", intent)
            return await self.list_incidents(session, status_filter=status_map[intent])

        firewall_decision = self.firewall.inspect_user_question(sanitized_query)
        if not firewall_decision.allowed:
            logger.warning("LLM firewall blocked query with code '%s'", firewall_decision.code)
            return QueryResponse(
                answer=firewall_decision.message,
                citations=[],
                related_incidents=[],
                clarifying_questions=[
                    "Which service, alert, or incident do you want investigated?",
                    "What exact error, symptom, or business impact are you seeing?",
                    "Do you want diagnosis, blast radius, remediation, or evidence review?"
                ],
                evidence_summary=None,
                confidence=0.0,
                source_breakdown={"kb": 0, "incidents_db": 0, "web": 0}
            )

        evidence_summary = None
        image_questions: List[str] = []
        image_signals: List[str] = []
        search_query = sanitized_query
        if image_evidence:
            image_analysis = await self.analyze_image_evidence(image_evidence)
            evidence_summary = scrub_pii(image_analysis.get("summary", ""))
            image_signals = [scrub_pii(signal) for signal in image_analysis.get("signals", [])]
            image_questions = [scrub_pii(question) for question in image_analysis.get("clarifying_questions", [])]
            search_query = "\n".join(filter(None, [sanitized_query, evidence_summary, *image_signals]))
        
        # 2. Search local Knowledge Base via semantic search
        kb_citations = await self.embedding_service.search_kb(
            session=session,
            query_text=search_query,
            top_k=5,
            threshold=0.40  # Broad match query threshold
        )
        
        # Calculate max local similarity
        max_sim = max([c.relevance for c in kb_citations]) if kb_citations else 0.0
        
        # 3. Search past database incidents (returns (incident, match_score) tuples)
        matched_incidents = await self.search_past_incidents(session, search_query, request.filters)
        STRONG_INCIDENT_MATCH = 0.55
        strong_past_incidents = [inc for inc, score in matched_incidents if score >= STRONG_INCIDENT_MATCH]
        has_strong_incident = bool(strong_past_incidents)
        
        # Convert past incidents to summaries
        related_incidents = []
        for inc in strong_past_incidents:
            related_incidents.append(
                IncidentSummary(
                    id=inc.id,
                    title=inc.title,
                    service_name=inc.service_name,
                    severity=inc.severity,
                    status=inc.status,
                    created_at=inc.created_at
                )
            )

        # 4. Web search is disabled — this chatbot answers only from internal KB
        # (runbooks, postmortems) and the incidents database. External web pages
        # cannot help with internal operational queries.
        web_citations: list = []
            
        # 5. Build prompt evidence sections
        evidence_kb = ""
        for i, c in enumerate(kb_citations, 1):
            evidence_kb += (
                f"[{i}] Category: {c.category} | Title: {_trim_for_prompt(c.title, 120)} (Doc ID: {c.doc_id})\n"
                f"Snippet: {_trim_for_prompt(c.content_snippet, PROMPT_SNIPPET_LIMIT)}\n\n"
            )
            
        evidence_db = ""
        for i, inc in enumerate(strong_past_incidents, len(kb_citations) + 1):
            evidence_db += (
                f"[{i}] Past Incident: {_trim_for_prompt(inc.title or '', 120)} (ID: {inc.id}) | "
                f"Service: {inc.service_name} | Root Cause: {_trim_for_prompt(inc.actual_root_cause or '', 140)}\n"
                f"Diagnosis: {_trim_for_prompt(inc.engineer_view or '', PROMPT_INCIDENT_LIMIT)}\n\n"
            )
            
        # Build the prompt from available evidence only — omit empty sections
        prompt_parts = [f"Question: {sanitized_query}"]
        if evidence_summary:
            prompt_parts.append(f"\nExtracted Evidence Summary:\n{evidence_summary}")
        if image_signals:
            prompt_parts.append("\nScreenshot Signals:\n" + "\n".join(f"- {s}" for s in image_signals))
        if evidence_kb:
            prompt_parts.append(f"\nRetrieved KB Documents:\n{evidence_kb.rstrip()}")
        if evidence_db:
            prompt_parts.append(f"\nRetrieved Past Incidents:\n{evidence_db.rstrip()}")
        prompt = "\n".join(prompt_parts)

        # 6. LLM synthesis
        messages = [
            {"role": "system", "content": QUERY_SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]
        
        # Define Pydantic schema for structured output to ensure we get a clean result
        class LLMSynthesisSchema(BaseModel):
            answer: str
            confidence: float
            clarifying_questions: List[str] = []

        logger.info("Calling model router for Mode B answer synthesis.")
        total_evidence = len(kb_citations) + len(strong_past_incidents) + len(web_citations)

        # Hard grounding guard: with zero retrieved evidence we never let the model
        # sound confident. Return a deterministic insufficient-evidence answer.
        if total_evidence == 0:
            logger.warning("No evidence retrieved for query. Checking for conversational intent.")
            
            # Allow basic conversational greetings to pass naturally
            lowered = sanitized_query.lower().strip()
            # Remove punctuation for matching
            for punc in [',', '.', '!', '?']:
                lowered = lowered.replace(punc, '')
                
            greeting_phrases = {"hi", "hello", "hey", "help", "who are you", "what are you", "what can you do", "hi aios", "hello aios", "greetings", "good morning", "good afternoon"}
            if lowered in greeting_phrases or any(lowered.startswith(p + " ") for p in greeting_phrases):
                return QueryResponse(
                    answer="Hello! I'm your AIOS Incident Operating assistant. I can look up past incidents, analyze current alerts, and walk you through runbooks. How can I help you today?",
                    citations=[],
                    related_incidents=[],
                    clarifying_questions=[],
                    evidence_summary=None,
                    confidence=1.0,
                    source_breakdown={"kb": 0, "incidents_db": 0, "web": 0}
                )

            answer = (
                "I don't have enough grounded context in the knowledge base, past incidents, "
                "or web search to answer this confidently. Please add more detail (affected "
                "service, error text, timeframe) or attach a screenshot so I can ground a response."
            )
            return QueryResponse(
                answer=answer,
                citations=[],
                related_incidents=[],
                clarifying_questions=(image_questions or [
                    "Which service or component is affected?",
                    "What exact error message or status code are you seeing?",
                    "When did the issue start, and was there a recent deployment?"
                ])[:3],
                evidence_summary=evidence_summary,
                confidence=0.0,
                source_breakdown={"kb": 0, "incidents_db": 0, "web": 0}
            )

        try:
            llm_result = await self.model_router.call_with_fallback(
                messages=messages,
                response_format=LLMSynthesisSchema,
                preferred="primary",
                fallback="fallback"
            )
            answer = llm_result.answer
            confidence = llm_result.confidence
            model_questions = getattr(llm_result, "clarifying_questions", []) or []
            clarifying_questions = image_questions + [q for q in model_questions if q not in image_questions]
        except Exception as e:
            logger.error(f"Error synthesizing query answer via LLM: {e}")
            answer = _build_llm_failure_answer(kb_citations, related_incidents, web_citations)
            confidence = 0.0
            clarifying_questions = image_questions

        # Evidence-grounded confidence ceiling: the model's self-reported confidence
        # cannot exceed what the retrieved evidence actually supports. Web-only
        # grounding caps lower than local KB / incident grounding.
        if max_sim >= 0.55 or has_strong_incident:
            confidence_ceiling = 0.95
        elif kb_citations or strong_past_incidents:
            confidence_ceiling = 0.75
        elif web_citations:
            confidence_ceiling = 0.55
        else:
            confidence_ceiling = 0.30
        confidence = max(0.0, min(confidence, confidence_ceiling))

        # Calculate counts
        source_breakdown = {
            "kb": len(kb_citations),
            "incidents_db": len(related_incidents),
            "web": len(web_citations)
        }

        # Collate citations in the SAME order they were numbered in the prompt
        # ([1..KB] -> [KB+1..incidents] -> [..web]) so every bracketed reference the
        # model emits maps to a real, correctly-indexed citation.
        all_citations = []
        all_citations.extend(kb_citations)

        # Past database incidents — numbered right after the KB block in the prompt.
        for inc in strong_past_incidents:
            all_citations.append(
                Citation(
                    doc_id=f"incident:{inc.id}",
                    title=inc.title or f"Incident {inc.id}",
                    category="past_incident",
                    relevance=0.60,
                    content_snippet=(inc.actual_root_cause or inc.engineer_view or "")[:400]
                )
            )

        # Web pages — numbered last in the prompt.
        for w in web_citations:
            all_citations.append(
                Citation(
                    doc_id=w.url,
                    title=w.title,
                    category="web_search",
                    relevance=0.50, # constant score for web citation relevance
                    content_snippet=w.snippet
                )
            )

        return QueryResponse(
            answer=answer,
            citations=all_citations,
            related_incidents=related_incidents,
            clarifying_questions=clarifying_questions[:3],
            evidence_summary=evidence_summary,
            confidence=confidence,
            source_breakdown=source_breakdown
        )
