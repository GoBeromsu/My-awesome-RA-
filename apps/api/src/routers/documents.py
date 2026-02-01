"""Document management router."""

import hashlib
import logging
import os
import re
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from src.dependencies import get_index_service, get_solar_service
from src.models.document import (
    DocumentChunksResponse,
    DocumentDeleteResponse,
    DocumentInfo,
    DocumentListResponse,
    DocumentStatusResponse,
    DocumentUploadResponse,
)
from src.services.index import IndexService
from src.services.solar import SolarService

logger = logging.getLogger(__name__)

router = APIRouter()

# Configuration
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
DOCUMENT_ID_PATTERN = re.compile(r"^[\w\-\.]+_[a-f0-9]{12}$")
PDF_STORAGE_PATH = Path(os.getenv("PDF_STORAGE_PATH", "data/pdfs"))
PDF_STORAGE_PATH.mkdir(parents=True, exist_ok=True)

# In-memory storage for document processing status
# In production, use Redis or database
_document_status: dict[str, dict] = {}


def validate_document_id(document_id: str) -> str:
    """Validate document ID format to prevent injection."""
    if len(document_id) > 256:
        raise HTTPException(status_code=400, detail="Document ID too long")
    if not DOCUMENT_ID_PATTERN.match(document_id):
        raise HTTPException(status_code=400, detail="Invalid document ID format")
    return document_id


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    index_service: Annotated[IndexService, Depends(get_index_service)],
) -> DocumentListResponse:
    """
    List all indexed documents.

    Returns:
        List of indexed documents with metadata.
    """
    documents = index_service.list_documents()

    return DocumentListResponse(
        documents=[
            DocumentInfo(
                document_id=doc["document_id"],
                cite_key=doc.get("cite_key"),
                title=doc.get("title"),
                authors=doc.get("authors"),
                year=doc.get("year"),
                page_count=doc.get("page_count"),
                chunk_count=doc["chunk_count"],
                indexed_at=doc.get("indexed_at"),
                has_pdf=doc.get("has_pdf", False),
            )
            for doc in documents
        ],
        total=len(documents),
    )


@router.get("/{document_id}/chunks", response_model=DocumentChunksResponse)
async def get_document_chunks(
    document_id: str,
    index_service: Annotated[IndexService, Depends(get_index_service)],
) -> DocumentChunksResponse:
    """
    Get all chunks for a document.

    Args:
        document_id: Document identifier.
        index_service: Shared IndexService instance.

    Returns:
        List of document chunks.
    """
    try:
        chunks = await index_service.get_chunks(document_id)

        return DocumentChunksResponse(
            document_id=document_id,
            chunks=chunks,
            total=len(chunks),
        )
    except Exception as e:
        logger.exception(f"Error getting document chunks: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve document chunks. Please try again later.",
        ) from e


@router.delete("/{document_id}", response_model=DocumentDeleteResponse)
async def delete_document(
    document_id: str,
    index_service: Annotated[IndexService, Depends(get_index_service)],
) -> DocumentDeleteResponse:
    """
    Delete a document and all its chunks from the index.

    Args:
        document_id: Document identifier to delete.
        index_service: Shared IndexService instance.

    Returns:
        Deletion result with chunk count.
    """
    validate_document_id(document_id)
    try:
        chunks_deleted = index_service.delete_document(document_id)

        if chunks_deleted == 0:
            raise HTTPException(status_code=404, detail="Document not found")

        # Clean up status storage
        if document_id in _document_status:
            del _document_status[document_id]

        # Clean up PDF file
        pdf_path = PDF_STORAGE_PATH / f"{document_id}.pdf"
        if pdf_path.exists():
            pdf_path.unlink()

        return DocumentDeleteResponse(
            document_id=document_id,
            chunks_deleted=chunks_deleted,
            status="deleted",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error deleting document: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to delete document. Please try again later.",
        ) from e


@router.get("/{document_id}/file")
async def get_document_file(document_id: str) -> FileResponse:
    """
    Serve the original PDF file.

    Browser can open with #page=N to jump to a specific page.

    Args:
        document_id: Document identifier.

    Returns:
        PDF file response.
    """
    validate_document_id(document_id)
    pdf_path = (PDF_STORAGE_PATH / f"{document_id}.pdf").resolve()

    # Defense in depth: ensure path is within storage directory
    if not pdf_path.is_relative_to(PDF_STORAGE_PATH.resolve()):
        raise HTTPException(status_code=400, detail="Invalid document path")

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")

    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


async def _process_document_in_background(
    document_id: str,
    content: bytes,
    filename: str,
    solar_service: SolarService,
    index_service: IndexService,
    cite_key: str | None = None,
) -> None:
    """Background task to parse and index a document."""
    try:
        logger.info(f"Starting background processing for {document_id}")
        _document_status[document_id] = {
            "status": "processing",
            "message": "Saving PDF...",
        }

        # Save PDF file for later retrieval
        pdf_path = PDF_STORAGE_PATH / f"{document_id}.pdf"
        pdf_path.write_bytes(content)

        _document_status[document_id]["message"] = "Parsing PDF..."

        # Parse PDF
        parsed = await solar_service.parse_document(content, filename)

        _document_status[document_id]["message"] = "Indexing content..."

        # Index with metadata and grounding info
        result = await index_service.index_document(
            document_id=document_id,
            content=parsed["content"],
            metadata={
                "cite_key": cite_key,
                "title": filename.rsplit(".", 1)[0],
                "source_pdf": filename,
                "page_count": parsed["pages"],
                "indexed_at": datetime.now(timezone.utc).isoformat(),
                **parsed.get("metadata", {}),
            },
            grounding=parsed.get("grounding"),
        )

        _document_status[document_id] = {
            "status": "indexed",
            "message": "Indexing complete",
            "chunk_count": result["chunk_count"],
        }
        logger.info(f"Completed processing for {document_id}: {result['chunk_count']} chunks")

    except Exception as e:
        error_msg = str(e) if str(e) else repr(e)
        logger.error(f"Error processing {document_id}: {error_msg}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        _document_status[document_id] = {
            "status": "error",
            "message": error_msg,
        }


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(document_id: str) -> DocumentStatusResponse:
    """
    Get the processing status of a document.

    Args:
        document_id: Document identifier.

    Returns:
        Current processing status.
    """
    validate_document_id(document_id)
    if document_id not in _document_status:
        raise HTTPException(status_code=404, detail="Document not found")

    status_info = _document_status[document_id]
    return DocumentStatusResponse(
        document_id=document_id,
        status=status_info["status"],
        message=status_info.get("message"),
        chunk_count=status_info.get("chunk_count"),
    )


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_and_index_document(
    file: Annotated[UploadFile, File(description="PDF file to upload and index")],
    background_tasks: BackgroundTasks,
    solar_service: Annotated[SolarService, Depends(get_solar_service)],
    index_service: Annotated[IndexService, Depends(get_index_service)],
    cite_key: Annotated[str | None, Form(description="BibTeX cite key")] = None,
) -> DocumentUploadResponse:
    """
    Upload a PDF and start background processing.

    This endpoint:
    1. Accepts the PDF file
    2. Returns immediately with a document ID
    3. Processes (parse + index) in the background

    Poll GET /documents/{id}/status to check processing status.

    Args:
        file: PDF file to upload.
        background_tasks: FastAPI background tasks.
        solar_service: Shared SolarService instance.
        index_service: Shared IndexService instance.

    Returns:
        Document ID and initial processing status.
    """
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        content = await file.read()

        # Validate file size
        if len(content) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)} MB",
            )

        # Generate document_id from cite_key or filename hash
        file_hash = hashlib.sha256(content).hexdigest()[:12]
        if cite_key:
            # Validate cite_key length
            if len(cite_key) > 200:
                raise HTTPException(status_code=400, detail="cite_key too long (max 200)")
            # Use cite_key as document ID base (citeKey_hash format)
            safe_key = re.sub(r"[^\w\-\.]", "_", cite_key)
            document_id = f"{safe_key}_{file_hash}"
        else:
            # Fallback: use filename
            safe_name = re.sub(r"[^\w\-\.]", "_", file.filename.rsplit(".", 1)[0])
            document_id = f"{safe_name}_{file_hash}"

        # Check if already processing or indexed
        if document_id in _document_status:
            current = _document_status[document_id]
            if current["status"] == "processing":
                return DocumentUploadResponse(
                    document_id=document_id,
                    status="processing",
                    message="Document is already being processed",
                )
            if current["status"] == "indexed":
                return DocumentUploadResponse(
                    document_id=document_id,
                    status="indexed",
                    message="Document is already indexed",
                )

        # Initialize status
        _document_status[document_id] = {
            "status": "processing",
            "message": "Queued for processing",
        }

        # Add background task
        background_tasks.add_task(
            _process_document_in_background,
            document_id,
            content,
            file.filename,
            solar_service,
            index_service,
            cite_key,
        )

        return DocumentUploadResponse(
            document_id=document_id,
            status="processing",
            message="Document queued for processing",
        )
    except Exception as e:
        logger.exception(f"Error uploading document: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to upload document. Please try again later.",
        ) from e


@router.post("/{document_id}/reindex", response_model=DocumentUploadResponse)
async def reindex_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    solar_service: Annotated[SolarService, Depends(get_solar_service)],
    index_service: Annotated[IndexService, Depends(get_index_service)],
) -> DocumentUploadResponse:
    """
    Re-parse and re-index an existing PDF document.

    This endpoint:
    1. Validates the document exists
    2. Deletes existing index entries
    3. Re-parses and re-indexes in background

    Poll GET /documents/{id}/status to check processing status.

    Args:
        document_id: Document identifier.
        background_tasks: FastAPI background tasks.
        solar_service: Shared SolarService instance.
        index_service: Shared IndexService instance.

    Returns:
        Document ID and processing status.
    """
    validate_document_id(document_id)
    pdf_path = PDF_STORAGE_PATH / f"{document_id}.pdf"

    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="PDF file not found")

    try:
        # Delete existing index entries
        index_service.delete_document(document_id)

        # Clear any existing status
        if document_id in _document_status:
            del _document_status[document_id]

        # Read PDF content
        content = pdf_path.read_bytes()
        filename = f"{document_id}.pdf"

        # Initialize status
        _document_status[document_id] = {
            "status": "processing",
            "message": "Queued for reindexing",
        }

        # Add background task for reindexing
        background_tasks.add_task(
            _process_document_in_background,
            document_id,
            content,
            filename,
            solar_service,
            index_service,
        )

        return DocumentUploadResponse(
            document_id=document_id,
            status="processing",
            message="Reindexing started",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error reindexing document: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to reindex document. Please try again later.",
        ) from e
