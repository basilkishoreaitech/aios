from pydantic import BaseModel, Field
from typing import List

class ServiceTopologyNode(BaseModel):
    """Represent a node in the dynamic dependency graph."""
    id: str = Field(description="Unique identifier / service name")
    status: str = Field(description="Operational status: healthy, degraded, down")

class ServiceTopologyLink(BaseModel):
    """Represent an edge between nodes in the dependency graph."""
    source: str = Field(description="Source service name")
    target: str = Field(description="Target service name")
    relationship_type: str = Field(description="Connection type: http, grpc, postgres, redis")
    is_critical: bool = Field(default=True, description="Whether this is a critical dependency path")

class ServiceTopologyResponse(BaseModel):
    """Full service dependency graph topology payload."""
    nodes: List[ServiceTopologyNode] = Field(default_factory=list)
    links: List[ServiceTopologyLink] = Field(default_factory=list)
