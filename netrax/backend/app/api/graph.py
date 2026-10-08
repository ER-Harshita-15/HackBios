"""
Graph API — Phase 2

Endpoints for knowledge graph construction, exploration, path-finding,
validation, and cross-case intelligence analysis.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.phase2 import (
    GraphResponse, GraphBuildRequest, GraphBuildResponse,
    GraphPathRequest, GraphPathResponse,
    GraphSearchResponse, GraphSearchResult,
    GraphValidationResponse, GraphConnectionsResponse,
)
from app.services.resolution.graph_sync import GraphSyncService

router = APIRouter(prefix="/graph", tags=["Knowledge Graph"])

graph_service = GraphSyncService()


@router.post("/build/{case_id}", response_model=GraphBuildResponse)
async def build_case_graph(
    case_id: str,
    payload: GraphBuildRequest | None = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Build or rebuild the knowledge graph projection for a case.
    Consolidates canonical entities and evidence-backed relationships.
    """
    try:
        include_unverified = payload.include_unverified if payload else False
        result = await graph_service.build_case_graph(
            db=db,
            case_id=case_id,
            include_unverified=include_unverified,
        )
        return GraphBuildResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build graph: {e}")


@router.get("/{case_id}", response_model=GraphResponse)
async def get_case_graph(
    case_id: str,
    entity_types: str | None = Query(None, description="Comma-separated entity types to include"),
    relationship_types: str | None = Query(None, description="Comma-separated relationship types to include"),
    include_unverified: bool = Query(True, description="Whether to include unverified relationships"),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the complete knowledge graph for visualization in Cytoscape.js.
    Supports filtering by entity types and relationship types.
    """
    e_types = [t.strip().upper() for t in entity_types.split(",")] if entity_types else None
    r_types = [t.strip().upper() for t in relationship_types.split(",")] if relationship_types else None

    return await graph_service.get_case_graph(
        db=db,
        case_id=case_id,
        entity_types=e_types,
        relationship_types=r_types,
        include_unverified=include_unverified,
    )


@router.post("/path", response_model=GraphPathResponse)
async def find_path(
    payload: GraphPathRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Find the shortest evidence-backed path between two canonical entities.
    Uses BFS to trace connective evidence trails.
    """
    return await graph_service.find_shortest_path(
        db=db,
        source_id=payload.source_entity_id,
        target_id=payload.target_entity_id,
        max_depth=payload.max_depth,
    )


@router.get("/entity/{entity_id}/connections", response_model=GraphConnectionsResponse)
async def get_entity_connections(
    entity_id: str,
    depth: int = Query(1, ge=1, le=3),
    db: AsyncSession = Depends(get_db),
):
    """
    Get the ego network (direct and n-hop connections) for an entity.
    """
    try:
        return await graph_service.get_entity_connections(
            db=db,
            entity_id=entity_id,
            depth=depth,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/search", response_model=GraphSearchResponse)
async def search_graph(
    query: str = Query(..., min_length=1),
    entity_types: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """
    Search graph nodes by name or identifier.
    """
    e_types = [t.strip().upper() for t in entity_types.split(",")] if entity_types else None
    results = await graph_service.search_graph(
        db=db,
        query=query,
        entity_types=e_types,
        limit=limit,
    )
    return GraphSearchResponse(results=results, total=len(results))


@router.get("/validate/{case_id}", response_model=GraphValidationResponse)
async def validate_graph(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Validate graph consistency (check for orphan nodes, dangling relationships, missing provenance).
    """
    return await graph_service.validate_graph(db=db, case_id=case_id)


@router.get("/cross-case/{case_id}")
async def get_cross_case_connections(
    case_id: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Detect entities that connect this case to other investigation cases.
    """
    return await graph_service.get_cross_case_connections(db=db, case_id=case_id)
