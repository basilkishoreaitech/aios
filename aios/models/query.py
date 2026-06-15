from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from models.evidence import Citation

class QueryRequest(BaseModel):
    """User-initiated natural language query for Mode B."""
    question: str = Field(description="Natural language question from the operator")
    filters: Optional[Dict[str, Any]] = Field(None, description="Optional filters like service_name, severity")

class IncidentSummary(BaseModel):
    """Short summary of a past incident returned in search/query."""
    id: str = Field(description="Incident UUID")
    title: str = Field(description="Incident title")
    service_name: str = Field(description="Affected service name")
    severity: str = Field(description="Severity (e.g. SEV-1)")
    status: str = Field(description="Incident status (e.g. resolved)")
    created_at: datetime = Field(description="Creation timestamp")

class QueryResponse(BaseModel):
    """Synthesized query answer with grounding citations and metadata."""
    answer: str = Field(description="LLM-synthesized natural language answer")
    citations: List[Citation] = Field(default_factory=list, description="Grounding knowledge base document matches")
    related_incidents: List[IncidentSummary] = Field(default_factory=list, description="Matching past database incidents")
    clarifying_questions: List[str] = Field(default_factory=list, description="Targeted follow-up questions the operator should answer before accepting the diagnosis")
    evidence_summary: Optional[str] = Field(default=None, description="Structured summary of any uploaded or extracted evidence")
    confidence: float = Field(description="Model confidence rating for the answer (0.0 to 1.0)")
    source_breakdown: Dict[str, int] = Field(default_factory=dict, description="Count of sources by category e.g., {'kb': 2, 'db': 1, 'web': 0}")
