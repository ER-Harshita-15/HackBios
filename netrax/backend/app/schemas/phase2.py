"""
Pydantic schemas for Phase 2 — Entity Resolution, Canonical Entities,
Relationships, Graph, and Audit.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ─── Entity Resolution ──────────────────────────────────────────────

class MatchFeature(BaseModel):
    """A single matching feature with its score."""
    feature: str
    score: float
    description: str


class MatchCandidateResponse(BaseModel):
    id: str
    entity_a_id: str
    entity_b_id: str
    entity_a_value: str = ""
    entity_b_value: str = ""
    entity_a_type: str = ""
    entity_b_type: str = ""
    entity_a_document_id: str = ""
    entity_b_document_id: str = ""
    match_score: float
    matching_features: list[MatchFeature] = []
    explanation: str = ""
    status: str
    created_at: datetime
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class MatchCandidateListResponse(BaseModel):
    candidates: list[MatchCandidateResponse]
    total: int


class MatchConfirmRequest(BaseModel):
    reviewed_by: str = Field("investigator", examples=["investigator"])
    notes: Optional[str] = None


class MatchRejectRequest(BaseModel):
    reviewed_by: str = Field("investigator", examples=["investigator"])
    reason: Optional[str] = None


class ResolutionRunRequest(BaseModel):
    """Request to run entity resolution for a case."""
    case_id: Optional[str] = None
    entity_type: Optional[str] = None
    min_score: float = Field(0.5, ge=0.0, le=1.0)


class ResolutionRunResponse(BaseModel):
    candidates_generated: int
    case_id: Optional[str] = None


# ─── Canonical Entities ─────────────────────────────────────────────

class EntityAliasResponse(BaseModel):
    id: str
    entity_id: str
    alias_value: str
    normalized_value: str
    source_document_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CanonicalEntityResponse(BaseModel):
    id: str
    entity_type: str
    canonical_name: str
    normalized_name: str
    status: str
    aliases: list[EntityAliasResponse] = []
    relationship_count: int = 0
    case_ids: list[str] = []
    source_document_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CanonicalEntityListResponse(BaseModel):
    entities: list[CanonicalEntityResponse]
    total: int


class CanonicalEntityDetailResponse(CanonicalEntityResponse):
    """Extended canonical entity details with evidence links."""
    source_entities: list[dict] = []
    mentions: list[dict] = []


# ─── Relationships ──────────────────────────────────────────────────

class RelationshipResponse(BaseModel):
    id: str
    relationship_type: str
    source_entity_id: str
    target_entity_id: str
    source_entity_name: str = ""
    target_entity_name: str = ""
    source_entity_type: str = ""
    target_entity_type: str = ""
    source_document_id: Optional[str] = None
    source_document_name: Optional[str] = None
    source_page: Optional[int] = None
    source_record_id: Optional[str] = None
    extraction_method: str
    confidence: float
    verification_status: str
    properties: dict = {}
    case_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    verified_by: Optional[str] = None
    verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class RelationshipListResponse(BaseModel):
    relationships: list[RelationshipResponse]
    total: int


class RelationshipVerifyRequest(BaseModel):
    verified_by: str = Field("investigator", examples=["investigator"])
    notes: Optional[str] = None


class RelationshipExtractRequest(BaseModel):
    """Request to extract relationships from processed documents."""
    case_id: Optional[str] = None
    document_id: Optional[str] = None


class RelationshipExtractResponse(BaseModel):
    relationships_created: int
    case_id: Optional[str] = None
    document_id: Optional[str] = None


# ─── Graph ──────────────────────────────────────────────────────────

class GraphNode(BaseModel):
    id: str
    label: str
    entity_type: str
    properties: dict = {}


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    relationship_type: str
    label: str = ""
    properties: dict = {}


class GraphResponse(BaseModel):
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    case_id: Optional[str] = None


class GraphBuildRequest(BaseModel):
    include_unverified: bool = False


class GraphBuildResponse(BaseModel):
    case_id: str
    nodes_created: int
    relationships_created: int
    status: str


class GraphPathRequest(BaseModel):
    source_entity_id: str
    target_entity_id: str
    max_depth: int = Field(5, ge=1, le=10)


class GraphPathResponse(BaseModel):
    found: bool
    path: list[GraphNode] = []
    edges: list[GraphEdge] = []
    length: int = 0


class GraphSearchRequest(BaseModel):
    query: str
    entity_types: list[str] = []
    limit: int = Field(20, ge=1, le=100)


class GraphSearchResult(BaseModel):
    id: str
    label: str
    entity_type: str
    match_field: str = ""


class GraphSearchResponse(BaseModel):
    results: list[GraphSearchResult]
    total: int


class GraphValidationResponse(BaseModel):
    valid: bool
    orphan_nodes: int = 0
    orphan_relationships: int = 0
    missing_sources: int = 0
    details: list[str] = []


class GraphConnectionsResponse(BaseModel):
    entity: GraphNode
    connections: list[GraphNode] = []
    edges: list[GraphEdge] = []


# ─── Dashboard Phase 2 ─────────────────────────────────────────────

class Phase2DashboardStats(BaseModel):
    # Phase 1 stats
    total_documents: int = 0
    processed_documents: int = 0
    total_entities: int = 0
    pending_verification: int = 0
    verified_entities: int = 0
    rejected_entities: int = 0
    failed_documents: int = 0
    total_cases: int = 0
    # Phase 2 stats
    canonical_entities: int = 0
    potential_matches: int = 0
    confirmed_matches: int = 0
    rejected_matches: int = 0
    pending_review: int = 0
    total_relationships: int = 0
    verified_relationships: int = 0
    graph_nodes: int = 0
    graph_relationships: int = 0
    cross_case_connections: int = 0


# ─── Audit ──────────────────────────────────────────────────────────

class AuditLogResponse(BaseModel):
    id: str
    user: str
    action: str
    resource_type: str
    resource_id: Optional[str]
    details: Optional[str]
    timestamp: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    logs: list[AuditLogResponse]
    total: int
