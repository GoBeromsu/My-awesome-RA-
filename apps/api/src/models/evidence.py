"""Evidence search models."""

from pydantic import BaseModel, Field, field_validator


class EvidenceSearchRequest(BaseModel):
    """Request model for evidence search."""

    query: str = Field(
        ..., min_length=3, max_length=500, description="Search query text"
    )
    project_id: str | None = Field(
        default=None, description="Optional project ID to scope the search"
    )
    top_k: int = Field(default=10, ge=1, le=20, description="Number of results to return")
    threshold: float = Field(
        default=0.3, ge=0.0, le=1.0, description="Minimum similarity threshold"
    )
    document_ids: list[str] | None = Field(
        default=None, description="Optional filter by document IDs"
    )

    @field_validator("query", mode="before")
    @classmethod
    def validate_query(cls, v: str) -> str:
        """Strip whitespace and validate non-empty query."""
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise ValueError("Query cannot be empty after stripping whitespace")
        return v


class EvidenceResult(BaseModel):
    """Single evidence result."""

    document_id: str = Field(..., description="Source document identifier")
    chunk_id: str = Field(..., description="Chunk identifier within document")
    text: str = Field(..., description="Evidence text content")
    page: int | None = Field(default=None, description="Page number in source document")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    title: str | None = Field(default=None, description="Document title")
    authors: str | None = Field(default=None, description="Document authors")
    year: int | None = Field(default=None, description="Publication year")
    source_pdf: str | None = Field(default=None, description="Source PDF path")
    metadata: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict, description="Additional metadata"
    )


class EvidenceSearchResponse(BaseModel):
    """Response model for evidence search."""

    results: list[EvidenceResult] = Field(..., description="List of evidence results")
    query: str = Field(..., description="Original search query")
    total: int = Field(..., ge=0, description="Total number of results")
