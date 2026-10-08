"""
Canonical Entities API — Phase 2

CRUD operations for canonical (resolved) entities.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.canonical_entity import CanonicalEntity, EntityAlias, CanonicalEntityStatus
from app.models.relationship import Relationship
from app.models.entity import Entity
from app.models.entity_mention import EntityMention
from app.models.document import Document
from app.schemas.phase2 import (
    CanonicalEntityResponse, CanonicalEntityListResponse,
    CanonicalEntityDetailResponse, EntityAliasResponse,
)

router = APIRouter(prefix="/canonical-entities", tags=["Canonical Entities"])


async def _build_response(
    db: AsyncSession, ce: CanonicalEntity
) -> CanonicalEntityResponse:
    """Build a canonical entity response with counts."""
    # Count relationships
    rel_count = (await db.execute(
        select(func.count(Relationship.id)).where(
            (Relationship.source_entity_id == ce.id) |
            (Relationship.target_entity_id == ce.id)
        )
    )).scalar() or 0

    # Get case IDs from relationships
    case_ids_result = (await db.execute(
        select(Relationship.case_id).where(
            (Relationship.source_entity_id == ce.id) |
            (Relationship.target_entity_id == ce.id),
            Relationship.case_id.isnot(None),
        ).distinct()
    )).scalars().all()

    # Count unique source documents
    doc_count = len(set(
        a.source_document_id for a in ce.aliases if a.source_document_id
    ))

    return CanonicalEntityResponse(
        id=ce.id,
        entity_type=ce.entity_type,
        canonical_name=ce.canonical_name,
        normalized_name=ce.normalized_name,
        status=ce.status.value,
        aliases=[
            EntityAliasResponse(
                id=a.id,
                entity_id=a.entity_id,
                alias_value=a.alias_value,
                normalized_value=a.normalized_value,
                source_document_id=a.source_document_id,
                created_at=a.created_at,
            )
            for a in ce.aliases
        ],
        relationship_count=rel_count,
        case_ids=list(set(case_ids_result)),
        source_document_count=doc_count,
        created_at=ce.created_at,
        updated_at=ce.updated_at,
    )


@router.get("", response_model=CanonicalEntityListResponse)
async def list_canonical_entities(
    entity_type: str | None = Query(None),
    status: str | None = Query(None),
    search: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List all canonical entities."""
    query = select(CanonicalEntity).order_by(CanonicalEntity.created_at.desc())

    if entity_type:
        query = query.where(CanonicalEntity.entity_type == entity_type)
    if status:
        query = query.where(CanonicalEntity.status == CanonicalEntityStatus(status))
    if search:
        query = query.where(
            CanonicalEntity.canonical_name.ilike(f"%{search}%") |
            CanonicalEntity.normalized_name.ilike(f"%{search}%")
        )

    # Count total
    count_query = select(func.count(CanonicalEntity.id))
    if entity_type:
        count_query = count_query.where(CanonicalEntity.entity_type == entity_type)
    if status:
        count_query = count_query.where(CanonicalEntity.status == CanonicalEntityStatus(status))
    total = (await db.execute(count_query)).scalar() or 0

    if total == 0 and not entity_type and not status and not search:
        from app.services.resolution.entity_resolution import EntityResolutionService
        res_service = EntityResolutionService()
        synced = await res_service.sync_all_entities(db, include_unverified=False)
        if synced > 0:
            total = (await db.execute(count_query)).scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    entities = result.scalars().all()

    responses = []
    for ce in entities:
        responses.append(await _build_response(db, ce))

    return CanonicalEntityListResponse(entities=responses, total=total)


@router.post("/sync")
async def sync_canonical_entities(
    case_id: str | None = Query(None),
    include_unverified: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Synchronize extracted entities into canonical entities."""
    from app.services.resolution.entity_resolution import EntityResolutionService
    res_service = EntityResolutionService()
    synced_count = await res_service.sync_all_entities(
        db, case_id=case_id, include_unverified=include_unverified
    )
    return {"message": f"Synchronized {synced_count} entities", "synced": synced_count}


@router.get("/{entity_id}", response_model=CanonicalEntityDetailResponse)
async def get_canonical_entity(entity_id: str, db: AsyncSession = Depends(get_db)):
    """Get canonical entity details including source records and mentions."""
    ce = (await db.execute(
        select(CanonicalEntity).where(CanonicalEntity.id == entity_id)
    )).scalar_one_or_none()
    if not ce:
        raise HTTPException(status_code=404, detail="Canonical entity not found")

    base = await _build_response(db, ce)

    # Get source entities with their details
    source_entities = []
    all_mentions = []
    for alias in ce.aliases:
        entity = (await db.execute(
            select(Entity).where(Entity.id == alias.entity_id)
        )).scalar_one_or_none()
        if entity:
            doc = (await db.execute(
                select(Document).where(Document.id == entity.document_id)
            )).scalar_one_or_none()

            source_entities.append({
                "entity_id": entity.id,
                "value": entity.value,
                "normalized_value": entity.normalized_value,
                "entity_type": entity.entity_type.value,
                "confidence": entity.confidence,
                "verification_status": entity.verification_status.value,
                "document_id": entity.document_id,
                "document_name": doc.original_filename if doc else "",
            })

            # Get mentions
            mentions = (await db.execute(
                select(EntityMention).where(EntityMention.entity_id == entity.id)
            )).scalars().all()
            for m in mentions:
                all_mentions.append({
                    "mention_id": m.id,
                    "entity_id": entity.id,
                    "document_id": m.document_id,
                    "page_number": m.page_number,
                    "context": m.context,
                    "confidence": m.confidence,
                })

    return CanonicalEntityDetailResponse(
        **base.model_dump(),
        source_entities=source_entities,
        mentions=all_mentions,
    )
