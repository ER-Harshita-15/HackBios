"""
Dashboard API — aggregated statistics for Phase 1 & Phase 2.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.document import Document, ProcessingStatus
from app.models.entity import Entity, VerificationStatus
from app.models.case import Case
from app.models.canonical_entity import CanonicalEntity
from app.models.entity_match_candidate import EntityMatchCandidate, MatchStatus
from app.models.relationship import Relationship, RelationshipVerificationStatus
from app.schemas.entity import DashboardStats
from app.schemas.document import DocumentResponse
from app.schemas.phase2 import Phase2DashboardStats

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get aggregated Phase 1 dashboard statistics."""
    total_docs = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    processed_docs = (await db.execute(
        select(func.count(Document.id)).where(
            Document.processing_status.in_([
                ProcessingStatus.READY_FOR_REVIEW,
                ProcessingStatus.COMPLETED,
            ])
        )
    )).scalar() or 0
    failed_docs = (await db.execute(
        select(func.count(Document.id)).where(
            Document.processing_status == ProcessingStatus.FAILED
        )
    )).scalar() or 0
    total_entities = (await db.execute(select(func.count(Entity.id)))).scalar() or 0
    pending = (await db.execute(
        select(func.count(Entity.id)).where(
            Entity.verification_status == VerificationStatus.UNVERIFIED
        )
    )).scalar() or 0
    verified = (await db.execute(
        select(func.count(Entity.id)).where(
            Entity.verification_status == VerificationStatus.VERIFIED
        )
    )).scalar() or 0
    rejected = (await db.execute(
        select(func.count(Entity.id)).where(
            Entity.verification_status == VerificationStatus.REJECTED
        )
    )).scalar() or 0
    total_cases = (await db.execute(select(func.count(Case.id)))).scalar() or 0

    return DashboardStats(
        total_documents=total_docs,
        processed_documents=processed_docs,
        total_entities=total_entities,
        pending_verification=pending,
        verified_entities=verified,
        rejected_entities=rejected,
        failed_documents=failed_docs,
        total_cases=total_cases,
    )


@router.get("/phase2-stats", response_model=Phase2DashboardStats)
async def get_phase2_dashboard_stats(db: AsyncSession = Depends(get_db)):
    """Get comprehensive Phase 1 + Phase 2 dashboard metrics."""
    total_docs = (await db.execute(select(func.count(Document.id)))).scalar() or 0
    processed_docs = (await db.execute(
        select(func.count(Document.id)).where(
            Document.processing_status.in_([
                ProcessingStatus.READY_FOR_REVIEW,
                ProcessingStatus.COMPLETED,
            ])
        )
    )).scalar() or 0
    failed_docs = (await db.execute(
        select(func.count(Document.id)).where(
            Document.processing_status == ProcessingStatus.FAILED
        )
    )).scalar() or 0
    total_entities = (await db.execute(select(func.count(Entity.id)))).scalar() or 0
    pending = (await db.execute(
        select(func.count(Entity.id)).where(
            Entity.verification_status == VerificationStatus.UNVERIFIED
        )
    )).scalar() or 0
    verified = (await db.execute(
        select(func.count(Entity.id)).where(
            Entity.verification_status == VerificationStatus.VERIFIED
        )
    )).scalar() or 0
    rejected = (await db.execute(
        select(func.count(Entity.id)).where(
            Entity.verification_status == VerificationStatus.REJECTED
        )
    )).scalar() or 0
    total_cases = (await db.execute(select(func.count(Case.id)))).scalar() or 0

    # Phase 2 metrics
    canonical_count = (await db.execute(select(func.count(CanonicalEntity.id)))).scalar() or 0
    potential_matches = (await db.execute(
        select(func.count(EntityMatchCandidate.id)).where(
            EntityMatchCandidate.status == MatchStatus.PENDING
        )
    )).scalar() or 0
    confirmed_matches = (await db.execute(
        select(func.count(EntityMatchCandidate.id)).where(
            EntityMatchCandidate.status == MatchStatus.CONFIRMED
        )
    )).scalar() or 0
    rejected_matches = (await db.execute(
        select(func.count(EntityMatchCandidate.id)).where(
            EntityMatchCandidate.status == MatchStatus.REJECTED
        )
    )).scalar() or 0

    total_rels = (await db.execute(select(func.count(Relationship.id)))).scalar() or 0
    verified_rels = (await db.execute(
        select(func.count(Relationship.id)).where(
            Relationship.verification_status == RelationshipVerificationStatus.VERIFIED
        )
    )).scalar() or 0

    return Phase2DashboardStats(
        total_documents=total_docs,
        processed_documents=processed_docs,
        total_entities=total_entities,
        pending_verification=pending,
        verified_entities=verified,
        rejected_entities=rejected,
        failed_documents=failed_docs,
        total_cases=total_cases,
        canonical_entities=canonical_count,
        potential_matches=potential_matches,
        confirmed_matches=confirmed_matches,
        rejected_matches=rejected_matches,
        pending_review=pending + potential_matches,
        total_relationships=total_rels,
        verified_relationships=verified_rels,
        graph_nodes=canonical_count,
        graph_relationships=total_rels,
        cross_case_connections=0,
    )


@router.get("/recent-documents", response_model=list[DocumentResponse])
async def get_recent_documents(limit: int = 10, db: AsyncSession = Depends(get_db)):
    """Get recently uploaded documents."""
    result = await db.execute(
        select(Document).order_by(Document.created_at.desc()).limit(limit)
    )
    documents = result.scalars().all()

    return [
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
    ]
