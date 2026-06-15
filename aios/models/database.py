"""
AIOS ORM Models — SQLAlchemy tables.
Tables: users, incidents, agent_traces, kb_documents, action_items, service_topology
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime, JSON,
    ForeignKey, Index, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from database import Base


class User(Base):
    """User accounts with RBAC roles."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="operator")  # admin, operator, executive
    display_name = Column(String(200), default="")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


class Incident(Base):
    """Incident records — created by the pipeline for each alert."""
    __tablename__ = "incidents"

    id = Column(String(36), primary_key=True)  # UUID
    title = Column(String(500), nullable=False)
    service_name = Column(String(200), nullable=False, index=True)
    severity = Column(String(20), nullable=False)  # SEV-1, SEV-2, SEV-3, SEV-4
    status = Column(String(50), default="open")  # open, investigating, resolved
    raw_alert = Column(Text, nullable=True)
    incident_packet = Column(JSON, nullable=True)  # Normalized IncidentPacket

    # Diagnosis results
    hypotheses = Column(JSON, nullable=True)  # List of ranked hypotheses
    risk_assessment = Column(JSON, nullable=True)
    action_plan = Column(JSON, nullable=True)
    engineer_view = Column(Text, nullable=True)
    executive_view = Column(Text, nullable=True)

    # Evidence
    evidence_bundle = Column(JSON, nullable=True)
    operational_context = Column(JSON, nullable=True)
    web_search_results = Column(JSON, nullable=True)

    # Reviewer
    reviewer_verdict = Column(String(50), nullable=True)  # approved, challenged
    reviewer_confidence_delta = Column(Float, nullable=True)
    review_cycles = Column(Integer, default=0)

    # Retrospective
    actual_root_cause = Column(Text, nullable=True)
    accuracy_score = Column(Float, nullable=True)
    resolved_by = Column(String(100), nullable=True)

    # Pipeline metadata
    pipeline_duration_ms = Column(Integer, nullable=True)
    model_used = Column(String(100), nullable=True)
    total_tokens = Column(Integer, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    traces = relationship("AgentTrace", back_populates="incident", cascade="all, delete-orphan")
    actions = relationship("ActionItem", back_populates="incident", cascade="all, delete-orphan")


class AgentTrace(Base):
    """Per-agent execution trace — for observability panel."""
    __tablename__ = "agent_traces"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False)  # running, completed, failed, skipped
    model_used = Column(String(100), nullable=True)
    duration_ms = Column(Integer, nullable=True)
    tokens_used = Column(Integer, nullable=True)
    input_summary = Column(Text, nullable=True)
    output_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    started_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    incident = relationship("Incident", back_populates="traces")


class KBDocument(Base):
    """Knowledge base document — runbooks, postmortems, architecture docs."""
    __tablename__ = "kb_documents"

    id = Column(String(100), primary_key=True)  # e.g., "runbook_api_gateway_restart"
    title = Column(String(500), nullable=False)
    category = Column(String(50), nullable=False, index=True)  # runbook, postmortem, architecture
    content = Column(Text, nullable=False)
    tags = Column(JSON, nullable=True)  # List of tags
    embedding = Column(JSON, nullable=True)  # List[float] — embedding vector
    source_file = Column(String(300), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    __table_args__ = (Index("ix_kb_category_title", "category", "title"),)


class ActionItem(Base):
    """Recommended actions from the action planner — with approval state."""
    __tablename__ = "action_items"

    id = Column(String(100), primary_key=True)  # "{incident_id}_{step_id}" — wider than UUID
    incident_id = Column(String(36), ForeignKey("incidents.id"), nullable=False, index=True)
    action = Column(Text, nullable=False)
    risk_tag = Column(String(30), nullable=False)  # auto_approve, approval_required, blocked
    risk_level = Column(String(20), nullable=False)  # low, medium, high, critical
    rationale = Column(Text, nullable=True)
    verification_check = Column(Text, nullable=True)
    status = Column(String(30), default="pending")  # pending, approved, rejected, executed
    approved_by = Column(String(100), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    incident = relationship("Incident", back_populates="actions")


class ServiceTopology(Base):
    """Service dependency graph — nodes and directed edges."""
    __tablename__ = "service_topology"

    id = Column(Integer, primary_key=True, index=True)
    source = Column(String(200), nullable=False, index=True)
    target = Column(String(200), nullable=False, index=True)
    relationship_type = Column(String(50), default="http")  # http, grpc, postgres, redis
    is_critical = Column(Boolean, default=True)


class OperationalEvent(Base):
    """Operational context events — calendar, teams chats, oncall."""
    __tablename__ = "operational_events"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(50), nullable=False, index=True)  # calendar, teams_chat, oncall
    service_name = Column(String(200), nullable=True, index=True)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=True)
    author = Column(String(200), nullable=True)
    event_time = Column(DateTime(timezone=True), nullable=True)
    metadata_json = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


