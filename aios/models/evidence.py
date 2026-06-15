from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime

class Citation(BaseModel):
    """Refers to a specific grounded knowledge base article or postmortem."""
    doc_id: str = Field(description="ID of the knowledge base document")
    title: str = Field(description="Title of the document")
    category: str = Field(description="Category (runbook, postmortem, architecture)")
    relevance: float = Field(description="Cosine similarity relevance score (0.0 to 1.0)")
    content_snippet: str = Field(description="Extracted snippet of relevant content")

class WebCitation(BaseModel):
    """Refers to a web search result fallback citation."""
    title: str = Field(description="Title of the webpage")
    url: str = Field(description="URL link to the source website")
    snippet: str = Field(description="Relevant text snippet from the web page")

class EvidenceBundle(BaseModel):
    """Consolidated evidence collected from local database KB and Web Search fallbacks."""
    kb_citations: List[Citation] = Field(default_factory=list, description="Local knowledge base matches")
    web_citations: List[WebCitation] = Field(default_factory=list, description="External web search fallback results")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow, description="Timestamp of evidence gathering")
    max_similarity: float = Field(default=0.0, description="Highest similarity score among local matches")
