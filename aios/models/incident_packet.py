from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class IncidentPacket(BaseModel):
    """Normalized incident representation parsed from raw alert and scrubbed of PII."""
    incident_id: str = Field(description="UUID for the incident")
    title: str = Field(description="Summarized title of the alert")
    service_name: str = Field(description="Name of the affected service/component")
    severity: str = Field(description="Incident severity level (SEV-1, SEV-2, SEV-3, SEV-4)")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Time when the alert occurred")
    raw_alert_sanitized: str = Field(description="PII-scrubbed raw alert text")
    metrics: Optional[str] = Field(None, description="Extracted metric key-value pairs as a JSON string, e.g. '{\"cpu\": \"95%\"}'")
    description: Optional[str] = Field(None, description="Detailed description of the alert")
    tags: List[str] = Field(default_factory=list, description="Extracted alert tags")
    operator_hint: Optional[str] = Field(None, description="Diagnostic input hint provided by the SRE operator")
