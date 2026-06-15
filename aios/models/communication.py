from pydantic import BaseModel, Field
from typing import List, Optional

class EngineerView(BaseModel):
    """Deep technical perspective for on-call SREs."""
    status_summary: str = Field(description="One-sentence technical status")
    detailed_diagnosis: str = Field(description="Detailed root cause analysis findings")
    evidence_timeline: List[str] = Field(default_factory=list, description="Chronological timeline of events/metrics leading to failure")
    suggested_commands: List[str] = Field(default_factory=list, description="CLI diagnostic or troubleshooting commands to execute")

class ExecutiveView(BaseModel):
    """High-level business perspective for management stakeholders."""
    status_summary: str = Field(description="One-sentence executive summary")
    business_impact: str = Field(description="Operational or financial impact breakdown")
    oncall_assigned: str = Field(description="Names of SREs/engineers currently responding")
    estimated_resolution_time: str = Field(description="Estimated Time to Resolution (TTR)")

class CommunicationBundle(BaseModel):
    """Dual-audience communication packet."""
    engineer_view: EngineerView = Field(description="Technical response details")
    executive_view: ExecutiveView = Field(description="Non-technical summary details")
    notification_text: str = Field(description="Raw text snippet suitable for Teams push notification")
