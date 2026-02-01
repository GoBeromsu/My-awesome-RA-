"""Document management models."""

from pydantic import BaseModel, Field


class DocumentParseResponse(BaseModel):
    """Response model for document parsing."""

    filename: str = Field(..., description="Original filename")
    pages: int = Field(..., ge=1, description="Number of pages")
    content: str = Field(..., description="Extracted text content")
    metadata: dict[str, str | int | float | bool] = Field(
        default_factory=dict, description="Document metadata"
    )


class DocumentIndexRequest(BaseModel):
    """Request model for document indexing."""

    document_id: str = Field(..., description="Unique document identifier")
    content: str = Field(..., description="Document text content to index")
    metadata: dict[str, str | int | float | bool] = Field(
        default_factory=dict, description="Additional metadata"
    )


class DocumentIndexResponse(BaseModel):
    """Response model for document indexing."""

    document_id: str = Field(..., description="Document identifier")
    chunk_count: int = Field(..., ge=0, description="Number of chunks created")
    status: str = Field(..., description="Indexing status")


class DocumentChunk(BaseModel):
    """Single document chunk."""

    chunk_id: str = Field(..., description="Chunk identifier")
    text: str = Field(..., description="Chunk text content")
    page: int | None = Field(default=None, description="Source page number")
    start_idx: int = Field(..., ge=0, description="Start character index")
    end_idx: int = Field(..., ge=0, description="End character index")


class DocumentChunksResponse(BaseModel):
    """Response model for document chunks."""

    document_id: str = Field(..., description="Document identifier")
    chunks: list[DocumentChunk] = Field(..., description="List of chunks")
    total: int = Field(..., ge=0, description="Total number of chunks")


class DocumentInfo(BaseModel):
    """Information about an indexed document."""

    document_id: str = Field(..., description="Document identifier")
    cite_key: str | None = Field(default=None, description="BibTeX cite key")
    title: str | None = Field(default=None, description="Document title")
    authors: str | None = Field(default=None, description="Document authors")
    year: int | None = Field(default=None, description="Publication year")
    page_count: int | None = Field(default=None, ge=1, description="Number of pages")
    chunk_count: int = Field(..., ge=0, description="Number of chunks")
    indexed_at: str | None = Field(default=None, description="Indexing timestamp")
    has_pdf: bool = Field(default=False, description="Whether document has indexed PDF")


class DocumentListResponse(BaseModel):
    """Response model for document list."""

    documents: list[DocumentInfo] = Field(..., description="List of indexed documents")
    total: int = Field(..., ge=0, description="Total number of documents")


class DocumentDeleteResponse(BaseModel):
    """Response model for document deletion."""

    document_id: str = Field(..., description="Deleted document identifier")
    chunks_deleted: int = Field(..., ge=0, description="Number of chunks deleted")
    status: str = Field(..., description="Deletion status")


class DocumentStatusResponse(BaseModel):
    """Response model for document processing status."""

    document_id: str = Field(..., description="Document identifier")
    status: str = Field(
        ..., description="Processing status: processing | indexed | error"
    )
    message: str | None = Field(default=None, description="Status message or error")
    chunk_count: int | None = Field(
        default=None, ge=0, description="Number of chunks if indexed"
    )


class DocumentUploadResponse(BaseModel):
    """Response model for document upload (background processing)."""

    document_id: str = Field(..., description="Document identifier")
    status: str = Field(..., description="Initial status: processing")
    message: str = Field(..., description="Status message")
