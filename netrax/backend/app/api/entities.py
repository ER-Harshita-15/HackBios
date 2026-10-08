"""
Entities API — entity retrieval, verification, rejection, and modification.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.document import Document
from app.models.entity import Entity, EntityType, VerificationStatus
from app.models.entity_mention import EntityMention
from app.schemas.entity import (
    EntityResponse, EntityListResponse, EntityMentionResponse,
    EntityUpdate, EntityVerifyRequest, EntityRejectRequest,
)
from app.services.normalization.entity_normalizer import EntityNormalizationService

router = APIRouter(prefix="/entities", tags=["Entities"])

normalizer = EntityNormalizationService()


def _entity_to_response(entity: Entity) -> EntityResponse:
    """Convert an Entity model to response schema."""
    return EntityResponse(
        id=entity.id,
        document_id=entity.document_id,
        entity_type=entity.entity_type.value,
        value=entity.value,
        normalized_value=entity.normalized_value,
        confidence=entity.confidence,
        extraction_method=entity.extraction_method.value,
        verification_status=entity.verification_status.value,
        verified_by=entity.verified_by,
        verified_at=entity.verified_at,
        notes=entity.notes,
        mentions=[
            EntityMentionResponse(
                id=m.id,
                page_number=m.page_number,
                text_start=m.text_start,
                text_end=m.text_end,
                context=m.context,
                confidence=m.confidence,
                extraction_method=m.extraction_method,
                created_at=m.created_at,
            )
            for m in entity.mentions
        ],
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


@router.get("/by-document/{document_id}", response_model=EntityListResponse)
async def get_document_entities(document_id: str, db: AsyncSession = Depends(get_db)):
    """Get all entities extracted from a document."""
    doc_result = await db.execute(select(Document).where(Document.id == document_id))
    doc = doc_result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    result = await db.execute(
        select(Entity)
        .where(Entity.document_id == document_id)
        .order_by(Entity.entity_type, Entity.confidence.desc())
    )
    entities = result.scalars().all()

    return EntityListResponse(
        document_id=document_id,
        status=doc.processing_status.value,
        entities=[_entity_to_response(e) for e in entities],
        total=len(entities),
    )


@router.get("/{entity_id}", response_model=EntityResponse)
async def get_entity(entity_id: str, db: AsyncSession = Depends(get_db)):
    """Get entity details including all mentions."""
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    return _entity_to_response(entity)


@router.patch("/{entity_id}", response_model=EntityResponse)
@router.put("/{entity_id}", response_model=EntityResponse)
async def update_entity(
    entity_id: str, data: EntityUpdate, db: AsyncSession = Depends(get_db)
):
    """Modify an entity (value, type, or notes)."""
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    if data.value is not None:
        entity.value = data.value
        entity.normalized_value = normalizer.normalize(entity.entity_type.value, data.value)
        entity.verification_status = VerificationStatus.MODIFIED

    if data.entity_type is not None:
        try:
            entity.entity_type = EntityType(data.entity_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid entity type: {data.entity_type}")
        # Re-normalize with new type
        entity.normalized_value = normalizer.normalize(data.entity_type, entity.value)
        entity.verification_status = VerificationStatus.MODIFIED

    if data.notes is not None:
        entity.notes = data.notes

    await db.flush()
    return _entity_to_response(entity)


@router.post("/{entity_id}/verify", response_model=EntityResponse)
async def verify_entity(
    entity_id: str, data: EntityVerifyRequest, db: AsyncSession = Depends(get_db)
):
    """Mark an entity as verified by an investigator."""
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity.verification_status = VerificationStatus.VERIFIED
    entity.verified_by = data.verified_by
    entity.verified_at = datetime.now(timezone.utc)
    if data.notes:
        entity.notes = data.notes

    # Automatically ensure CanonicalEntity representation in Phase 2
    from app.services.resolution.entity_resolution import EntityResolutionService
    res_svc = EntityResolutionService()
    await res_svc.ensure_canonical_entity(db, entity)

    await db.flush()
    return _entity_to_response(entity)


@router.post("/{entity_id}/reject", response_model=EntityResponse)
async def reject_entity(
    entity_id: str, data: EntityRejectRequest, db: AsyncSession = Depends(get_db)
):
    """Reject an incorrectly extracted entity."""
    result = await db.execute(select(Entity).where(Entity.id == entity_id))
    entity = result.scalar_one_or_none()
    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    entity.verification_status = VerificationStatus.REJECTED
    entity.verified_by = data.verified_by
    entity.verified_at = datetime.now(timezone.utc)
    if data.reason:
        entity.notes = data.reason

    await db.flush()
    return _entity_to_response(entity)
