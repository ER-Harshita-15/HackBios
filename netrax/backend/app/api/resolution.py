"""
Entity Resolution API — Phase 2

Endpoints for generating, reviewing, and confirming/rejecting entity match candidates.
Match scores represent record-linkage confidence, NOT criminality.
"""

import json
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.entity import Entity
from app.models.entity_match_candidate import EntityMatchCandidate, MatchStatus
from app.schemas.phase2 import (
    MatchCandidateResponse, MatchCandidateListResponse, MatchFeature,
    MatchConfirmRequest, MatchRejectRequest,
    ResolutionRunRequest, ResolutionRunResponse,
    CanonicalEntityResponse, EntityAliasResponse,
)
from app.services.resolution.entity_resolution import EntityResolutionService

router = APIRouter(prefix="/resolution", tags=["Entity Resolution"])

resolution_service = EntityResolutionService()


def _candidate_to_response(
    candidate: EntityMatchCandidate,
    entity_a: Entity | None = None,
    entity_b: Entity | None = None,
) -> MatchCandidateResponse:
    """Convert a match candidate to response schema."""
    features = []
    if candidate.matching_features:
        try:
            raw = json.loads(candidate.matching_features)
            features = [MatchFeature(**f) if isinstance(f, dict) else f for f in raw]
        except (json.JSONDecodeError, TypeError):
            pass

    return MatchCandidateResponse(
        id=candidate.id,
        entity_a_id=candidate.entity_a_id,
        entity_b_id=candidate.entity_b_id,
        entity_a_value=entity_a.value if entity_a else "",
        entity_b_value=entity_b.value if entity_b else "",
        entity_a_type=entity_a.entity_type.value if entity_a else "",
        entity_b_type=entity_b.entity_type.value if entity_b else "",
        entity_a_document_id=entity_a.document_id if entity_a else "",
        entity_b_document_id=entity_b.document_id if entity_b else "",
        match_score=candidate.match_score,
        matching_features=features,
        explanation=candidate.explanation or "",
        status=candidate.status.value,
        created_at=candidate.created_at,
        reviewed_by=candidate.reviewed_by,
        reviewed_at=candidate.reviewed_at,
    )


@router.post("/run", response_model=ResolutionRunResponse)
async def run_entity_resolution(
    data: ResolutionRunRequest,
    db: AsyncSession = Depends(get_db),
):
    """Run entity resolution to generate match candidates."""
    count = await resolution_service.generate_candidates(
        db,
        case_id=data.case_id,
        entity_type=data.entity_type,
        min_score=data.min_score,
    )
    return ResolutionRunResponse(
        candidates_generated=count,
        case_id=data.case_id,
    )


@router.get("/candidates", response_model=MatchCandidateListResponse)
async def list_candidates(
    status: str | None = Query(None, description="Filter by status: PENDING, CONFIRMED, REJECTED"),
    entity_type: str | None = Query(None),
    min_score: float | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List entity match candidates with optional filters."""
    query = select(EntityMatchCandidate).order_by(
        EntityMatchCandidate.match_score.desc()
    )

    if status:
        query = query.where(EntityMatchCandidate.status == MatchStatus(status))
    if min_score is not None:
        query = query.where(EntityMatchCandidate.match_score >= min_score)

    # Count total
    count_query = select(func.count(EntityMatchCandidate.id))
    if status:
        count_query = count_query.where(EntityMatchCandidate.status == MatchStatus(status))
    total = (await db.execute(count_query)).scalar() or 0

    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    candidates = result.scalars().all()

    # Fetch entities for each candidate
    responses = []
    for c in candidates:
        entity_a = (await db.execute(
            select(Entity).where(Entity.id == c.entity_a_id)
        )).scalar_one_or_none()
        entity_b = (await db.execute(
            select(Entity).where(Entity.id == c.entity_b_id)
        )).scalar_one_or_none()

        if entity_type and entity_a and entity_a.entity_type.value != entity_type:
            continue

        responses.append(_candidate_to_response(c, entity_a, entity_b))

    return MatchCandidateListResponse(candidates=responses, total=total)


@router.get("/candidates/{candidate_id}", response_model=MatchCandidateResponse)
async def get_candidate(candidate_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific match candidate with details."""
    candidate = (await db.execute(
        select(EntityMatchCandidate).where(EntityMatchCandidate.id == candidate_id)
    )).scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Match candidate not found")

    entity_a = (await db.execute(
        select(Entity).where(Entity.id == candidate.entity_a_id)
    )).scalar_one_or_none()
    entity_b = (await db.execute(
        select(Entity).where(Entity.id == candidate.entity_b_id)
    )).scalar_one_or_none()

    return _candidate_to_response(candidate, entity_a, entity_b)


@router.post("/candidates/{candidate_id}/confirm", response_model=CanonicalEntityResponse)
async def confirm_match(
    candidate_id: str,
    data: MatchConfirmRequest,
    db: AsyncSession = Depends(get_db),
):
    """Confirm an entity match. Creates/updates canonical entity."""
    try:
        canonical = await resolution_service.confirm_match(
            db, candidate_id, reviewed_by=data.reviewed_by
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return CanonicalEntityResponse(
        id=canonical.id,
        entity_type=canonical.entity_type,
        canonical_name=canonical.canonical_name,
        normalized_name=canonical.normalized_name,
        status=canonical.status.value,
        aliases=[
            EntityAliasResponse(
                id=a.id,
                entity_id=a.entity_id,
                alias_value=a.alias_value,
                normalized_value=a.normalized_value,
                source_document_id=a.source_document_id,
                created_at=a.created_at,
            )
            for a in canonical.aliases
        ],
        created_at=canonical.created_at,
        updated_at=canonical.updated_at,
    )


@router.post("/candidates/{candidate_id}/reject")
async def reject_match(
    candidate_id: str,
    data: MatchRejectRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reject an entity match. Entity A ≠ Entity B."""
    try:
        await resolution_service.reject_match(
            db, candidate_id, reviewed_by=data.reviewed_by, reason=data.reason
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {"status": "rejected", "candidate_id": candidate_id}
