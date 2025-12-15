"""
Pydantic models for data validation and serialization
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class USCodeSection(BaseModel):
    """A section of the US Code"""

    identifier: str = Field(..., description="Section identifier (e.g., '17 USC 102')")
    heading: str = Field(..., description="Section heading/title")
    text: str = Field(..., description="Full text content")
    notes: str = Field(default="", description="Additional notes")

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    """A search result from the vector database"""

    identifier: str
    heading: str
    text: str
    relevance: float = Field(..., ge=0, le=1, description="Relevance score 0-1")


class RAGResponse(BaseModel):
    """Response from RAG query"""

    answer: str = Field(..., description="Generated answer")
    sections: List[SearchResult] = Field(default_factory=list)
    provider: str = Field(..., description="LLM provider used")
    model: str = Field(..., description="Model name used")


class PublicLaw(BaseModel):
    """A US Public Law from Congress.gov"""

    congress: int = Field(..., description="Congress number")
    bill_number: str = Field(..., description="Bill number")
    public_law: str = Field(default="", description="Public law number")
    title: str = Field(..., description="Law title")
    origin_chamber: str = Field(..., description="House or Senate")
    latest_action_date: Optional[str] = None
    latest_action: Optional[str] = None


class USCodeTitle(BaseModel):
    """A title of the US Code"""

    number: int = Field(..., description="Title number (1-54)")
    name: str = Field(..., description="Title name")
    enacted: bool = Field(..., description="Enacted as positive law")


class TitleStructure(BaseModel):
    """Structure of a US Code title"""

    title_number: str
    title_name: str
    chapters: List[dict] = Field(default_factory=list)


class SearchRequest(BaseModel):
    """API request for search"""

    query: str = Field(..., min_length=1, max_length=1000)
    n_results: int = Field(default=10, ge=1, le=100)


class RAGRequest(BaseModel):
    """API request for RAG query"""

    question: str = Field(..., min_length=1, max_length=2000)
    provider: str = Field(default="openai", pattern="^(openai|anthropic)$")
    model: Optional[str] = None
    n_sections: int = Field(default=5, ge=1, le=20)


class HealthResponse(BaseModel):
    """Health check response"""

    status: str = "ok"
    vector_db_available: bool = False
    openai_configured: bool = False
    anthropic_configured: bool = False
    sections_indexed: int = 0
