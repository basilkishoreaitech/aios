from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class DeploymentEvent(BaseModel):
    """Operational database deployment event."""
    service_name: str = Field(description="Name of the service deployed")
    version: str = Field(description="Version string e.g., v2.3")
    status: str = Field(description="Status of deployment (completed, failed, rollback)")
    deployed_at: datetime = Field(description="Deployment timestamp")
    deployed_by: str = Field(description="Operator name")
    details: Optional[str] = Field(None, description="Details or changelog summary")

class TeamsMessage(BaseModel):
    """Correlated Teams chat room message."""
    author: str = Field(description="Sender of the message")
    content: str = Field(description="Message body text")
    timestamp: datetime = Field(description="Message send time")
    channel: str = Field(description="Channel/room name")

class OnCallEngineer(BaseModel):
    """Currently on-call engineer info."""
    name: str = Field(description="Name of engineer")
    role: str = Field(description="On-call tier/role e.g., primary, secondary")
    contact: str = Field(description="Email or contact info")

class OperationalContext(BaseModel):
    """Correlated operational activity context from the operations event store."""
    deployments: List[DeploymentEvent] = Field(default_factory=list, description="Recent deployments within the window")
    teams_messages: List[TeamsMessage] = Field(default_factory=list, description="Relevant Teams messages within the window")
    oncall_roster: List[OnCallEngineer] = Field(default_factory=list, description="Active on-call SREs and engineers")
