"""
Pydantic schemas for Document API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class DocumentUploadMeta(BaseModel):
    case_id: str = Field(..., examples=["case-uuid-here"])
    document_type: str = Field(..., examples=["FIR"])
    description: Optional[str] = Field(None, examples=["First Information Report for case"])
    source: Optional[str] = Field(None, examples=["Central Police Station"])


class DocumentPageResponse(BaseModel):
    id: str
    page_number: int
    raw_text: Optional[str]
    cleaned_text: Optional[str]
    ocr_applied: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    case_id: str
    filename: str
    original_filename: str
    document_type: str
    mime_type: str
    file_size: int
    file_hash: str
    source: Optional[str]
    description: Optional[str]
    processing_status: str
    processing_error: Optional[str]
    total_pages: Optional[int]
    uploaded_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class ProcessingStatusResponse(BaseModel):
    document_id: str
    status: str
    total_pages: Optional[int]
    error: Optional[str]
    progress: Optional[str]
