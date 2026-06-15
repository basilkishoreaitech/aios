import json
import logging
import time
from typing import AsyncGenerator, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from config import Settings
from models.database import Incident, ActionItem
from models.incident_packet import IncidentPacket
from models.evidence import EvidenceBundle
from models.operational_context import OperationalContext
from models.hypothesis import HypothesisSet
from models.risk_assessment import RiskAssessment
from models.action_plan import ActionPlan
from models.communication import CommunicationBundle
from models.pipeline_trace import AgentTraceSchema, PipelineResult

# Import Agents
from agents.a1_intake import IntakeAgent
from agents.a2_foundry_iq import RetrievalAgent
from agents.a2b_operational_context import OperationalContextAgent
from agents.a3_correlation import CorrelationAgent
from agents.a4_risk_analyzer import RiskAnalyzerAgent
from agents.a5_action_planner import ActionPlannerAgent
from agents.a6_guardrail import GuardrailAgent
from agents.a7_communication import CommunicationAgent
from agents.a8_adversarial_review import AdversarialReviewAgent
from agents.a11_web_search import WebSearchAgent

# Import Services
from services.model_router import ModelRouter
from services.embedding_service import EmbeddingService
from services.web_search_service import WebSearchService
from services.token_budget import TokenBudgetTracker

logger = logging.getLogger("aios.orchestrator")

class IncidentPipeline:
    """Manages execution of the 11-agent incident response pipeline and pushes live progress updates (SSE)."""
    
    def __init__(
        self,
        config: Settings,
        model_router: ModelRouter,
        embedding_service: EmbeddingService,
        web_search_service: WebSearchService
    ):
        self.config = config
        self.model_router = model_router
        self.embedding_service = embedding_service
        self.web_search_service = web_search_service
        self.token_tracker = TokenBudgetTracker(global_limit=500000)
        
        # Instantiate Agents
        self.a1_intake = IntakeAgent(config, model_router, self.token_tracker)
        self.a2_retrieval = RetrievalAgent(config, model_router, self.token_tracker, embedding_service)
        # A2b runs in parallel with A2 (same evidence-gathering stage); both feed A3
        self.a2b_operational_context = OperationalContextAgent(config, model_router, self.token_tracker)
        self.a3_correlation = CorrelationAgent(config, model_router, self.token_tracker)
        self.a4_risk = RiskAnalyzerAgent(config, model_router, self.token_tracker)
        self.a5_action = ActionPlannerAgent(config, model_router, self.token_tracker)
        self.a6_guardrail = GuardrailAgent(config, model_router, self.token_tracker)
        self.a7_comm = CommunicationAgent(config, model_router, self.token_tracker)
        self.a8_adversarial_review = AdversarialReviewAgent(config, model_router, self.token_tracker)
        self.a11_web = WebSearchAgent(config, model_router, self.token_tracker, web_search_service)

    async def run_pipeline_streaming(
        self,
        session: AsyncSession,
        raw_alert: str,
        incident_id: str,
        operator_hint: str = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """Runs the agentic pipeline end-to-end, writing trace updates and yielding real-time SSE progress events."""
        
        start_time = time.perf_counter()
        logger.info(f"Running End-to-End Pipeline for Incident {incident_id}")

        # 1. Create or retrieve DB Incident record (prevents Primary Key conflicts on re-running with hints)
        stmt = select(Incident).where(Incident.id == incident_id)
        res = await session.execute(stmt)
        db_incident = res.scalars().first()
        
        if not db_incident:
            db_incident = Incident(
                id=incident_id,
                title="Ingesting Alert...",
                service_name="unknown",
                severity="SEV-3",
                status="investigating",
                raw_alert=raw_alert
            )
            session.add(db_incident)
        else:
            db_incident.status = "investigating"
            db_incident.title = "Re-evaluating with hint..."
            # Clear old actions so they are re-generated fresh with hint
            from sqlalchemy import delete
            await session.execute(delete(ActionItem).where(ActionItem.incident_id == incident_id))
            
        await session.commit()

        yield {"event": "pipeline_start", "data": json.dumps({"incident_id": incident_id, "status": "started"})}

        # --- A1 Intake Agent ---
        yield {"event": "agent_start", "data": json.dumps({"agent": "A1_Intake"})}
        a1_started = time.perf_counter()
        packet: IncidentPacket = await self.a1_intake.execute(session, incident_id, raw_alert)
        a1_duration_ms = int((time.perf_counter() - a1_started) * 1000)
        if operator_hint:
            packet.operator_hint = operator_hint
        
        # Update incident database fields with parsed results
        db_incident.title = packet.title
        db_incident.service_name = packet.service_name
        db_incident.severity = packet.severity
        db_incident.incident_packet = packet.model_dump(mode="json")
        await session.commit()
        
        yield {
            "event": "agent_complete",
            "data": json.dumps({
                "agent": "A1_Intake",
                "status": "completed",
                "duration_ms": a1_duration_ms,
                "model_used": self.a1_intake.model_router.last_model_used
            })
        }

        # --- A2 KB Retrieval & A2b Operational Context (parallelized conceptually) ---
        yield {"event": "agent_start", "data": json.dumps({"agent": "A2_Retrieval"})}
        evidence: EvidenceBundle = await self.a2_retrieval.execute(session, incident_id, packet)
        db_incident.evidence_bundle = evidence.model_dump(mode="json")
        await session.commit()
        yield {
            "event": "agent_complete",
            "data": json.dumps({
                "agent": "A2_Retrieval",
                "status": "completed",
                "model_used": "embeddings"
            })
        }

        yield {"event": "agent_start", "data": json.dumps({"agent": "A2b_OperationalContext"})}
        context: OperationalContext = await self.a2b_operational_context.execute(session, incident_id, packet)
        db_incident.operational_context = context.model_dump(mode="json")
        await session.commit()
        yield {
            "event": "agent_complete",
            "data": json.dumps({
                "agent": "A2b_OperationalContext",
                "status": "completed",
                "model_used": "sql"
            })
        }

        # --- A11 Web Search Fallback ---
        # Only fire A11 if: (a) web search is configured (API key present), AND (b) local KB similarity is weak
        if self.web_search_service.enabled and evidence.max_similarity < 0.55:
            yield {"event": "agent_start", "data": json.dumps({"agent": "A11_WebSearch"})}
            evidence = await self.a11_web.execute(session, incident_id, packet, evidence)
            db_incident.evidence_bundle = evidence.model_dump(mode="json")
            db_incident.web_search_results = [w.model_dump(mode="json") for w in evidence.web_citations]
            await session.commit()
            yield {
                "event": "agent_complete",
                "data": json.dumps({
                    "agent": "A11_WebSearch",
                    "status": "completed",
                    "model_used": self.web_search_service.provider_label
                })
            }

        # --- A3 Correlation Agent (Adversarial A8 Review Loop) ---
        reviewer_approved = False
        review_cycles = 0
        hypotheses: HypothesisSet = None
        
        while not reviewer_approved and review_cycles < 2:
            yield {"event": "agent_start", "data": json.dumps({"agent": "A3_Correlation"})}
            # In a real SRE scenario, we could pass feedback if review_cycles > 0.
            hypotheses = await self.a3_correlation.execute(session, incident_id, packet, evidence, context)
            
            db_incident.hypotheses = hypotheses.model_dump(mode="json")
            await session.commit()
            
            yield {
                "event": "agent_complete",
                "data": json.dumps({
                    "agent": "A3_Correlation",
                    "status": "completed",
                    "model_used": self.a3_correlation.model_router.last_model_used
                })
            }
            
            # --- A8 Adversarial Review Agent ---
            yield {"event": "agent_start", "data": json.dumps({"agent": "A8_AdversarialReview"})}
            verdict = await self.a8_adversarial_review.execute(session, incident_id, packet, evidence, context, hypotheses)
            
            db_incident.reviewer_verdict = verdict.verdict
            db_incident.reviewer_confidence_delta = verdict.confidence_delta
            db_incident.review_cycles = review_cycles + 1
            await session.commit()
            
            yield {
                "event": "agent_complete",
                "data": json.dumps({
                    "agent": "A8_AdversarialReview",
                    "status": f"completed_{verdict.verdict}",
                    "model_used": self.a8_adversarial_review.model_router.last_model_used,
                    "critique": verdict.critique
                })
            }
            
            if verdict.verdict == "approved":
                reviewer_approved = True
                # Boost confidence of top hypothesis
                for h in hypotheses.hypotheses:
                    h.confidence = min(1.0, h.confidence + verdict.confidence_delta)
            else:
                logger.warning(f"A8 Adversarial Review challenged hypotheses: {verdict.critique}. Cycling back to A3 Correlation.")
                review_cycles += 1
                # Lower confidence
                for h in hypotheses.hypotheses:
                    h.confidence = max(0.0, h.confidence + verdict.confidence_delta)
                # We inject critic findings into the context description for the next loop run
                packet.description = f"{packet.description or ''}\n\n[Reviewer critique cycle {review_cycles}]: {verdict.critique}"

        # --- A4 Risk Analyzer Agent ---
        yield {"event": "agent_start", "data": json.dumps({"agent": "A4_RiskAnalyzer"})}
        risks: RiskAssessment = await self.a4_risk.execute(session, incident_id, packet, hypotheses)
        db_incident.risk_assessment = risks.model_dump(mode="json")
        await session.commit()
        yield {
            "event": "agent_complete",
            "data": json.dumps({
                "agent": "A4_RiskAnalyzer",
                "status": "completed",
                "model_used": self.a4_risk.model_router.last_model_used
            })
        }

        # --- A5 Action Planner Agent ---
        yield {"event": "agent_start", "data": json.dumps({"agent": "A5_ActionPlanner"})}
        action_plan: ActionPlan = await self.a5_action.execute(session, incident_id, packet, evidence, hypotheses, risks)
        db_incident.action_plan = action_plan.model_dump(mode="json")
        await session.commit()
        yield {
            "event": "agent_complete",
            "data": json.dumps({
                "agent": "A5_ActionPlanner",
                "status": "completed",
                "model_used": self.a5_action.model_router.last_model_used
            })
        }

        # --- A6 Guardrail Agent ---
        yield {"event": "agent_start", "data": json.dumps({"agent": "A6_Guardrail"})}
        action_plan = await self.a6_guardrail.execute(session, incident_id, packet, evidence, hypotheses, action_plan)
        db_incident.action_plan = action_plan.model_dump(mode="json")
        
        # Save ActionItems to DB action_items table
        # Use incident-scoped IDs to avoid PK conflicts when multiple incidents run (step_1…step_N repeat)
        for step in action_plan.mitigation_steps:
            db_action = ActionItem(
                id=f"{incident_id}_{step.id}",
                incident_id=incident_id,
                action=step.action,
                risk_tag=step.risk_tag,
                risk_level=step.risk_level,
                rationale=step.rationale,
                verification_check=step.verification_check,
                status="pending"
            )
            session.add(db_action)
            
        await session.commit()
        yield {
            "event": "agent_complete",
            "data": json.dumps({
                "agent": "A6_Guardrail",
                "status": "completed",
                "model_used": "regex_and_rules"
            })
        }

        # --- A7 Communication Agent ---
        yield {"event": "agent_start", "data": json.dumps({"agent": "A7_Communication"})}
        comm: CommunicationBundle = await self.a7_comm.execute(
            session, incident_id, packet, evidence, hypotheses, risks, action_plan, context
        )
        
        # Update communication logs
        db_incident.engineer_view = comm.engineer_view.model_dump_json()
        db_incident.executive_view = comm.executive_view.model_dump_json()
        db_incident.pipeline_duration_ms = int((time.perf_counter() - start_time) * 1000)
        db_incident.model_used = (self.a3_correlation.model_router.last_model_used or "MAI")[:100]
        db_incident.total_tokens = self.token_tracker.total_consumed
        
        await session.commit()
        yield {
            "event": "agent_complete",
            "data": json.dumps({
                "agent": "A7_Communication",
                "status": "completed",
                "model_used": self.a7_comm.model_router.last_model_used
            })
        }

        # Final return values payload
        yield {
            "event": "pipeline_complete",
            "data": json.dumps({
                "incident_id": incident_id,
                "title": db_incident.title,
                "service_name": db_incident.service_name,
                "severity": db_incident.severity,
                "status": db_incident.status,
                "engineer_view": comm.engineer_view.model_dump(mode="json"),
                "executive_view": comm.executive_view.model_dump(mode="json"),
                "action_plan": action_plan.model_dump(mode="json"),
                "evidence_bundle": evidence.model_dump(mode="json"),
                "duration_ms": db_incident.pipeline_duration_ms,
                "total_tokens": db_incident.total_tokens
            })
        }
