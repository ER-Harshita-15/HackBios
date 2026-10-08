"""
Relationships API — Phase 2

Endpoints for listing, verifying, rejecting, and extracting evidence-backed relationships.
Relationships describe what the evidence shows, NOT guilt or criminality.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.database import get_db
from app.models.relationship import Relationship, RelationshipType, RelationshipVerificationStatus
from app.models.canonical_entity import CanonicalEntity
from app.models.document import Document
from app.schemas.phase2 import (
    RelationshipResponse, RelationshipListResponse,
    RelationshipVerifyRequest, RelationshipExtractRequest,
    RelationshipExtractResponse,
)
from app.services.resolution.relationship_extraction import RelationshipExtractionService
from app.models.audit_log import AuditLog, AuditAction
import json
from datetime import datetime, timezone

router = APIRouter(prefix="/relationships", tags=["Relationships"])

extraction_service = RelationshipExtractionService()


def _rel_to_response(
    rel: Relationship,
    source_name: str = "",
    target_name: str = "",
    source_type: str = "",
    target_type: str = "",
    doc_name: str = "",
) -> RelationshipResponse:
    props = {}
    if rel.properties_json:
        try:
            props = json.loads(rel.properties_json)
        except (json.JSONDecodeError, TypeError):
            props = {}

    return RelationshipResponse(
        id=rel.id,
        relationship_type=rel.relationship_type.value if hasattr(rel.relationship_type, "value") else str(rel.relationship_type),
        source_entity_id=rel.source_entity_id,
        target_entity_id=rel.target_entity_id,
        source_entity_name=source_name,
        target_entity_name=target_name,
        source_entity_type=source_type,
        target_entity_type=target_type,
        source_document_id=rel.source_document_id,
        source_document_name=doc_name,
        source_page=rel.source_page,
        source_record_id=rel.source_record_id,
        extraction_method=rel.extraction_method.value if hasattr(rel.extraction_method, "value") else str(rel.extraction_method),
        confidence=rel.confidence,
        verification_status=rel.verification_status.value if hasattr(rel.verification_status, "value") else str(rel.verification_status),
        properties=props,
        case_id=rel.case_id,
        created_at=rel.created_at,
        updated_at=rel.updated_at,
        verified_by=rel.verified_by,
        verified_at=rel.verified_at,
    )


@router.get("", response_model=RelationshipListResponse)
async def list_relationships(
    case_id: str | None = None,
    relationship_type: str | None = None,
    status: str | None = None,
    search: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List relationships with optional filtering and pagination."""
    query = select(Relationship)

    if case_id:
        query = query.where(Relationship.case_id == case_id)
    if relationship_type:
        try:
            query = query.where(Relationship.relationship_type == RelationshipType(relationship_type))
        except ValueError:
            pass
    if status:
        try:
            query = query.where(Relationship.verification_status == RelationshipVerificationStatus(status))
        except ValueError:
            pass

    # Count total
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0

    if total == 0 and not case_id and not relationship_type and not status and not search:
        extracted = await extraction_service.extract_all(db)
        if extracted > 0:
            total = (await db.execute(count_query)).scalar() or 0

    # Paginate
    query = query.order_by(Relationship.created_at.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    rels = result.scalars().all()

    # Pre-fetch entities and docs for display
    source_ids = {r.source_entity_id for r in rels}
    target_ids = {r.target_entity_id for r in rels}
    doc_ids = {r.source_document_id for r in rels if r.source_document_id}

    entities_map = {}
    if source_ids or target_ids:
        all_eids = source_ids | target_ids
        eq = select(CanonicalEntity).where(CanonicalEntity.id.in_(all_eids))
        for ce in (await db.execute(eq)).scalars().all():
            entities_map[ce.id] = ce

    docs_map = {}
    if doc_ids:
        dq = select(Document).where(Document.id.in_(doc_ids))
        for d in (await db.execute(dq)).scalars().all():
            docs_map[d.id] = d.original_filename

    items = []
    for r in rels:
        src = entities_map.get(r.source_entity_id)
        tgt = entities_map.get(r.target_entity_id)
        items.append(_rel_to_response(
            rel=r,
            source_name=src.canonical_name if src else r.source_entity_id[:8],
            target_name=tgt.canonical_name if tgt else r.target_entity_id[:8],
            source_type=src.entity_type if src else "",
            target_type=tgt.entity_type if tgt else "",
            doc_name=docs_map.get(r.source_document_id, ""),
        ))

    return RelationshipListResponse(relationships=items, total=total)


@router.get("/types")
async def get_relationship_types():
    """Return all supported relationship types."""
    return [{"name": rt.name, "value": rt.value} for rt in RelationshipType]


@router.get("/{relationship_id}", response_model=RelationshipResponse)
async def get_relationship(
    relationship_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get single relationship by ID."""
    query = select(Relationship).where(Relationship.id == relationship_id)
    rel = (await db.execute(query)).scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    src = (await db.execute(select(CanonicalEntity).where(CanonicalEntity.id == rel.source_entity_id))).scalar_one_or_none()
    tgt = (await db.execute(select(CanonicalEntity).where(CanonicalEntity.id == rel.target_entity_id))).scalar_one_or_none()
    doc = None
    if rel.source_document_id:
        doc = (await db.execute(select(Document).where(Document.id == rel.source_document_id))).scalar_one_or_none()

    return _rel_to_response(
        rel=rel,
        source_name=src.canonical_name if src else "",
        target_name=tgt.canonical_name if tgt else "",
        source_type=src.entity_type if src else "",
        target_type=tgt.entity_type if tgt else "",
        doc_name=doc.original_filename if doc else "",
    )


@router.post("/{relationship_id}/verify", response_model=RelationshipResponse)
async def verify_relationship(
    relationship_id: str,
    payload: RelationshipVerifyRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Verify an evidence-backed relationship."""
    query = select(Relationship).where(Relationship.id == relationship_id)
    rel = (await db.execute(query)).scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    verifier = payload.verified_by if payload else "investigator"
    rel.verification_status = RelationshipVerificationStatus.VERIFIED
    rel.verified_by = verifier
    rel.verified_at = datetime.now(timezone.utc)
    rel.updated_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        action=AuditAction.RELATIONSHIP_VERIFIED,
        resource_type="relationship",
        resource_id=rel.id,
        user=verifier,
        new_value=json.dumps({"status": "VERIFIED"}),
    ))
    await db.commit()
    await db.refresh(rel)

    src = (await db.execute(select(CanonicalEntity).where(CanonicalEntity.id == rel.source_entity_id))).scalar_one_or_none()
    tgt = (await db.execute(select(CanonicalEntity).where(CanonicalEntity.id == rel.target_entity_id))).scalar_one_or_none()

    return _rel_to_response(
        rel=rel,
        source_name=src.canonical_name if src else "",
        target_name=tgt.canonical_name if tgt else "",
        source_type=src.entity_type if src else "",
        target_type=tgt.entity_type if tgt else "",
    )


@router.post("/{relationship_id}/reject", response_model=RelationshipResponse)
async def reject_relationship(
    relationship_id: str,
    payload: RelationshipVerifyRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """Reject a relationship as unsupported by evidence."""
    query = select(Relationship).where(Relationship.id == relationship_id)
    rel = (await db.execute(query)).scalar_one_or_none()
    if not rel:
        raise HTTPException(status_code=404, detail="Relationship not found")

    verifier = payload.verified_by if payload else "investigator"
    rel.verification_status = RelationshipVerificationStatus.REJECTED
    rel.verified_by = verifier
    rel.verified_at = datetime.now(timezone.utc)
    rel.updated_at = datetime.now(timezone.utc)

    db.add(AuditLog(
        action=AuditAction.RELATIONSHIP_REJECTED,
        resource_type="relationship",
        resource_id=rel.id,
        user=verifier,
        new_value=json.dumps({"status": "REJECTED"}),
    ))
    await db.commit()
    await db.refresh(rel)

    src = (await db.execute(select(CanonicalEntity).where(CanonicalEntity.id == rel.source_entity_id))).scalar_one_or_none()
    tgt = (await db.execute(select(CanonicalEntity).where(CanonicalEntity.id == rel.target_entity_id))).scalar_one_or_none()

    return _rel_to_response(
        rel=rel,
        source_name=src.canonical_name if src else "",
        target_name=tgt.canonical_name if tgt else "",
        source_type=src.entity_type if src else "",
        target_type=tgt.entity_type if tgt else "",
    )


@router.post("/extract", response_model=RelationshipExtractResponse)
async def trigger_extraction(
    payload: RelationshipExtractRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger automated relationship extraction for a case or document."""
    created = await extraction_service.extract_all(
        db=db,
        case_id=payload.case_id,
        document_id=payload.document_id,
    )
    return RelationshipExtractResponse(
        relationships_created=created,
        case_id=payload.case_id,
        document_id=payload.document_id,
    )
