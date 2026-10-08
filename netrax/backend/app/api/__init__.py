"""NETRA-X API Package — Phase 1 & Phase 2"""

from fastapi import APIRouter

from app.api.cases import router as cases_router
from app.api.documents import router as documents_router
from app.api.entities import router as entities_router
from app.api.dashboard import router as dashboard_router
from app.api.resolution import router as resolution_router
from app.api.canonical_entities import router as canonical_entities_router
from app.api.relationships import router as relationships_router
from app.api.graph import router as graph_router

api_router = APIRouter(prefix="/api")
api_router.include_router(cases_router)
api_router.include_router(documents_router)
api_router.include_router(entities_router)
api_router.include_router(dashboard_router)
api_router.include_router(resolution_router)
api_router.include_router(canonical_entities_router)
api_router.include_router(relationships_router)
api_router.include_router(graph_router)
