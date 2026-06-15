from pydantic import BaseModel, Field
from typing import List

class BlastRadius(BaseModel):
    """Scope of technical and user-facing impact."""
    impacted_services: List[str] = Field(default_factory=list, description="Services affected by the outage")
    downstream_impact_rating: str = Field(description="Rating of downstream impact (low, medium, high, critical)")
    user_facing_impact: bool = Field(description="Whether the incident affects customer-facing APIs/UI")
    estimated_data_loss: str = Field(description="Data loss risk level (none, potential, verified)")

class RiskAssessment(BaseModel):
    """Risk assessment for the active incident."""
    overall_risk_level: str = Field(description="Overall risk tier (low, medium, high, critical)")
    blast_radius: BlastRadius = Field(description="Scope of impact details")
    business_impact_summary: str = Field(description="Description of business/financial impact")
    mitigation_risk_factors: List[str] = Field(default_factory=list, description="Potential risks during mitigation steps")
