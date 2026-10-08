"""
Pydantic schemas for Case API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class CaseCreate(BaseModel):
    case_number: str = Field(..., min_length=1, max_length=50, examples=["CASE-001"])
    title: str = Field(..., min_length=1, max_length=255, examples=["Operation Nightwatch"])
    description: Optional[str] = Field(None, examples=["Multi-suspect investigation"])
    status: str = Field("OPEN", examples=["OPEN"])


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    status: Optional[str] = None


class CaseResponse(BaseModel):
    id: str
    case_number: str
    title: str
    description: Optional[str]
    status: str
    document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CaseListResponse(BaseModel):
    cases: list[CaseResponse]
    total: int
