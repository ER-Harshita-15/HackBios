"""
Documents API — upload, list, process, and retrieve investigation documents.
"""

import hashlib
import os
import uuid
import asyncio
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db, async_session_factory
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.document_page import DocumentPage
from app.models.case import Case
from app.schemas.document import (
    DocumentResponse, DocumentListResponse,
    DocumentPageResponse, ProcessingStatusResponse,
)
from app.config import settings
from app.services.processing.pipeline import get_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/documents", tags=["Documents"])

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    "application/pdf": ".pdf",
    "text/plain": ".txt",
    "text/csv": ".csv",
    "application/csv": ".csv",
}

MAX_FILENAME_LENGTH = 200


def _sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and other issues."""
    # Remove path separators
    filename = filename.replace("/", "_").replace("\\", "_")
    # Remove null bytes
    filename = filename.replace("\x00", "")
    # Limit length
    name, ext = os.path.splitext(filename)
    if len(name) > MAX_FILENAME_LENGTH:
        name = name[:MAX_FILENAME_LENGTH]
    return f"{name}{ext}"


def _get_mime_type(filename: str, content_type: str | None) -> str:
    """Determine MIME type from filename extension and content type."""
    ext = Path(filename).suffix.lower()
    ext_to_mime = {
        ".pdf": "application/pdf",
        ".txt": "text/plain",
        ".csv": "text/csv",
    }
    mime = ext_to_mime.get(ext)
    if mime:
        return mime
    if content_type and content_type in ALLOWED_MIME_TYPES:
        return content_type
    return content_type or "application/octet-stream"


async def _run_processing(document_id: str):
    """Background task to run the processing pipeline."""
    async with async_session_factory() as db:
        try:
            result = await db.execute(
                select(Document).where(Document.id == document_id)
            )
            document = result.scalar_one_or_none()
            if not document:
                logger.error(f"Document {document_id} not found for processing")
                return

            pipeline = get_pipeline()
            await pipeline.process(document, db)

        except Exception as e:
            logger.error(f"Background processing failed for {document_id}: {e}", exc_info=True)
            # Try to update status to FAILED
            try:
                result = await db.execute(
                    select(Document).where(Document.id == document_id)
                )
                doc = result.scalar_one_or_none()
                if doc:
                    doc.processing_status = ProcessingStatus.FAILED
                    doc.processing_error = str(e)
                    await db.commit()
            except Exception:
                pass


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_id: str = Form(...),
    document_type: str = Form(...),
    description: str = Form(""),
    source: str = Form(""),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload an investigation document.
    
    Validates the file, saves it securely, computes SHA-256 hash,
    and queues it for background processing.
    """
    # Validate case exists
    case_result = await db.execute(select(Case).where(Case.id == case_id))
    case = case_result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    # Validate document type
    try:
        doc_type = DocumentType(document_type)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid document type: {document_type}. Valid types: {[t.value for t in DocumentType]}",
        )

    # Validate file
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    sanitized_filename = _sanitize_filename(file.filename)
    mime_type = _get_mime_type(sanitized_filename, file.content_type)

    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {mime_type}. Allowed: {list(ALLOWED_MIME_TYPES.keys())}",
        )

    # Read file content
    content = await file.read()

    # Validate file size
    if len(content) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size: {settings.MAX_FILE_SIZE_MB}MB",
        )

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # Calculate SHA-256 hash
    file_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicate file
    existing = await db.execute(
        select(Document).where(Document.file_hash == file_hash, Document.case_id == case_id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=409,
            detail="A file with identical content has already been uploaded to this case",
        )

    # Save file
    file_id = str(uuid.uuid4())
    ext = ALLOWED_MIME_TYPES[mime_type]
    stored_filename = f"{file_id}{ext}"
    storage_dir = Path(settings.UPLOAD_DIR) / case_id
    storage_dir.mkdir(parents=True, exist_ok=True)
    storage_path = storage_dir / stored_filename

    with open(storage_path, "wb") as f:
        f.write(content)

    # Create document record
    document = Document(
        id=file_id,
        case_id=case_id,
        filename=stored_filename,
        original_filename=sanitized_filename,
        document_type=doc_type,
        mime_type=mime_type,
        file_size=len(content),
        file_hash=file_hash,
        storage_path=str(storage_path),
        source=source or None,
        description=description or None,
        processing_status=ProcessingStatus.UPLOADED,
    )
    db.add(document)
    await db.flush()

    # Queue background processing
    background_tasks.add_task(_run_processing, document.id)

    logger.info(f"Document uploaded: {sanitized_filename} -> {stored_filename} (case: {case.case_number})")

    return DocumentResponse(
        id=document.id,
        case_id=document.case_id,
        filename=document.filename,
        original_filename=document.original_filename,
        document_type=document.document_type.value,
        mime_type=document.mime_type,
        file_size=document.file_size,
        file_hash=document.file_hash,
        source=document.source,
        description=document.description,
        processing_status=document.processing_status.value,
        processing_error=document.processing_error,
        total_pages=document.total_pages,
        uploaded_by=document.uploaded_by,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    case_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    """List documents, optionally filtered by case."""
    query = select(Document).order_by(Document.created_at.desc())
    if case_id:
        query = query.where(Document.case_id == case_id)

    result = await db.execute(query)
    documents = result.scalars().all()

    return DocumentListResponse(
        documents=[
            DocumentResponse(
                id=doc.id,
                case_id=doc.case_id,
                filename=doc.filename,
                original_filename=doc.original_filename,
                document_type=doc.document_type.value,
                mime_type=doc.mime_type,
                file_size=doc.file_size,
                file_hash=doc.file_hash,
                source=doc.source,
                description=doc.description,
                processing_status=doc.processing_status.value,
                processing_error=doc.processing_error,
                total_pages=doc.total_pages,
                uploaded_by=doc.uploaded_by,
                created_at=doc.created_at,
                updated_at=doc.updated_at,
            )
            for doc in documents
        ],
        total=len(documents),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get document details."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    return DocumentResponse(
        id=doc.id,
        case_id=doc.case_id,
        filename=doc.filename,
        original_filename=doc.original_filename,
        document_type=doc.document_type.value,
        mime_type=doc.mime_type,
        file_size=doc.file_size,
        file_hash=doc.file_hash,
        source=doc.source,
        description=doc.description,
        processing_status=doc.processing_status.value,
        processing_error=doc.processing_error,
        total_pages=doc.total_pages,
        uploaded_by=doc.uploaded_by,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.post("/{document_id}/process", response_model=ProcessingStatusResponse)
async def process_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Manually trigger document processing."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if doc.processing_status in (ProcessingStatus.PROCESSING, ProcessingStatus.ENTITY_EXTRACTION):
        raise HTTPException(status_code=409, detail="Document is already being processed")

    # Reset status and reprocess
    doc.processing_status = ProcessingStatus.UPLOADED
    doc.processing_error = None
    await db.flush()

    background_tasks.add_task(_run_processing, doc.id)

    return ProcessingStatusResponse(
        document_id=doc.id,
        status=doc.processing_status.value,
        total_pages=doc.total_pages,
        error=None,
        progress="Queued for processing",
    )


@router.get("/{document_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get document processing status for polling."""
    result = await db.execute(select(Document).where(Document.id == document_id))
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    progress_map = {
        ProcessingStatus.UPLOADED: "Waiting to process",
        ProcessingStatus.PROCESSING: "Extracting text...",
        ProcessingStatus.TEXT_EXTRACTED: "Text extracted, starting entity extraction...",
        ProcessingStatus.ENTITY_EXTRACTION: "Extracting entities...",
        ProcessingStatus.READY_FOR_REVIEW: "Ready for review",
        ProcessingStatus.COMPLETED: "Completed",
        ProcessingStatus.FAILED: "Processing failed",
    }

    return ProcessingStatusResponse(
        document_id=doc.id,
        status=doc.processing_status.value,
        total_pages=doc.total_pages,
        error=doc.processing_error,
        progress=progress_map.get(doc.processing_status, "Unknown"),
    )


@router.get("/{document_id}/pages", response_model=list[DocumentPageResponse])
async def get_document_pages(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get extracted pages for a document."""
    result = await db.execute(
        select(DocumentPage)
        .where(DocumentPage.document_id == document_id)
        .order_by(DocumentPage.page_number)
    )
    pages = result.scalars().all()

    return [
        DocumentPageResponse(
            id=page.id,
            page_number=page.page_number,
            raw_text=page.raw_text,
            cleaned_text=page.cleaned_text,
            ocr_applied=page.ocr_applied,
            created_at=page.created_at,
        )
        for page in pages
    ]


@router.get("/{document_id}/entities")
async def get_document_entities_alias(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get all entities extracted from a document (convenience alias)."""
    from app.api.entities import get_document_entities
    return await get_document_entities(document_id=document_id, db=db)

