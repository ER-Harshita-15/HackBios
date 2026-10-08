"""
Pydantic schemas for Entity API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class EntityMentionResponse(BaseModel):
    id: str
    page_number: int
    text_start: Optional[int]
    text_end: Optional[int]
    context: Optional[str]
    confidence: float
    extraction_method: str
    created_at: datetime

    model_config = {"from_attributes": True}


class EntityResponse(BaseModel):
    id: str
    document_id: str
    entity_type: str
    value: str
    normalized_value: str
    confidence: float
    extraction_method: str
    verification_status: str
    verified_by: Optional[str]
    verified_at: Optional[datetime]
    notes: Optional[str]
    mentions: list[EntityMentionResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class EntityListResponse(BaseModel):
    document_id: str
    status: str
    entities: list[EntityResponse]
    total: int


class EntityUpdate(BaseModel):
    value: Optional[str] = None
    entity_type: Optional[str] = None
    notes: Optional[str] = None


class EntityVerifyRequest(BaseModel):
    verified_by: str = Field("investigator", examples=["investigator"])
    notes: Optional[str] = None


class EntityRejectRequest(BaseModel):
    verified_by: str = Field("investigator", examples=["investigator"])
    reason: Optional[str] = None


class DashboardStats(BaseModel):
    total_documents: int = 0
    processed_documents: int = 0
    total_entities: int = 0
    pending_verification: int = 0
    verified_entities: int = 0
    rejected_entities: int = 0
    failed_documents: int = 0
    total_cases: int = 0
