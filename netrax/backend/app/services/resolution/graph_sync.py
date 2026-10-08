"""
Graph Synchronization Service — Phase 2

Syncs PostgreSQL canonical entities and relationships to Neo4j.
PostgreSQL remains the source of truth; Neo4j is the graph projection.

Also provides graph querying capabilities when Neo4j is not available
by falling back to PostgreSQL-based graph operations.
"""

import json
import logging
from datetime import datetime, timezone
from collections import defaultdict

from sqlalchemy import select, func, and_, or_, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity, VerificationStatus
from app.models.canonical_entity import CanonicalEntity, EntityAlias, CanonicalEntityStatus
from app.models.relationship import Relationship, RelationshipType, RelationshipVerificationStatus
from app.models.document import Document
from app.models.case import Case
from app.models.audit_log import AuditLog, AuditAction
from app.schemas.phase2 import (
    GraphNode, GraphEdge, GraphResponse,
    GraphPathResponse, GraphValidationResponse,
    GraphSearchResult, GraphConnectionsResponse,
)

logger = logging.getLogger(__name__)


# ─── Neo4j Driver (Optional) ───────────────────────────────────────────

_neo4j_driver = None


def get_neo4j_driver():
    """Get Neo4j driver if available."""
    global _neo4j_driver
    if _neo4j_driver is None:
        try:
            from neo4j import GraphDatabase
            from app.config import settings
            uri = getattr(settings, 'NEO4J_URI', 'bolt://localhost:7687')
            user = getattr(settings, 'NEO4J_USER', 'neo4j')
            password = getattr(settings, 'NEO4J_PASSWORD', 'netrax_neo4j')
            driver = GraphDatabase.driver(uri, auth=(user, password), connection_timeout=1.0)
            driver.verify_connectivity()
            _neo4j_driver = driver
            logger.info(f"Connected to Neo4j at {uri}")
        except Exception as e:
            logger.info(f"Neo4j not available ({e}). Using relational graph projection.")
            _neo4j_driver = False
    return _neo4j_driver if _neo4j_driver else None


# ─── Entity Type → Node Color/Icon Mapping ─────────────────────────────

ENTITY_TYPE_CONFIG = {
    "PERSON": {"color": "#3b82f6", "icon": "👤", "shape": "ellipse"},
    "PHONE": {"color": "#10b981", "icon": "📱", "shape": "round-rectangle"},
    "LOCATION": {"color": "#f59e0b", "icon": "📍", "shape": "diamond"},
    "ORGANIZATION": {"color": "#8b5cf6", "icon": "🏢", "shape": "round-rectangle"},
    "ACCOUNT": {"color": "#ef4444", "icon": "🏦", "shape": "round-rectangle"},
    "VEHICLE": {"color": "#06b6d4", "icon": "🚗", "shape": "round-rectangle"},
    "CASE": {"color": "#ec4899", "icon": "📂", "shape": "hexagon"},
    "EVIDENCE": {"color": "#64748b", "icon": "📄", "shape": "rectangle"},
    "DEVICE": {"color": "#84cc16", "icon": "📟", "shape": "round-rectangle"},
    "EMAIL": {"color": "#14b8a6", "icon": "📧", "shape": "round-rectangle"},
    "DATE": {"color": "#a3a3a3", "icon": "📅", "shape": "round-rectangle"},
}


class GraphSyncService:
    """
    Synchronizes PostgreSQL data to Neo4j and provides graph query capabilities.
    Falls back to PostgreSQL-based graph operations when Neo4j is unavailable.
    """

    # ─── Build Graph ────────────────────────────────────────────────────

    async def build_case_graph(
        self,
        db: AsyncSession,
        case_id: str,
        include_unverified: bool = False,
    ) -> dict:
        """
        Build the knowledge graph for a case.

        Returns:
            {case_id, nodes_created, relationships_created, status}
        """
        # Verify case exists
        case = (await db.execute(
            select(Case).where(Case.id == case_id)
        )).scalar_one_or_none()
        if not case:
            raise ValueError(f"Case {case_id} not found")

        nodes_created = 0
        rels_created = 0

        # Get all canonical entities related to this case
        # via relationships or entity aliases
        ce_ids = set()

        # From relationships
        rel_query = select(Relationship).where(Relationship.case_id == case_id)
        if not include_unverified:
            rel_query = rel_query.where(
                Relationship.verification_status != RelationshipVerificationStatus.REJECTED
            )
        relationships = (await db.execute(rel_query)).scalars().all()

        for rel in relationships:
            ce_ids.add(rel.source_entity_id)
            ce_ids.add(rel.target_entity_id)

        # From entity aliases via documents
        docs = (await db.execute(
            select(Document.id).where(Document.case_id == case_id)
        )).scalars().all()

        for doc_id in docs:
            aliases = (await db.execute(
                select(EntityAlias).where(EntityAlias.source_document_id == doc_id)
            )).scalars().all()
            for alias in aliases:
                ce_ids.add(alias.canonical_entity_id)

        # Get canonical entities
        canonical_entities = []
        if ce_ids:
            canonical_entities = (await db.execute(
                select(CanonicalEntity).where(
                    CanonicalEntity.id.in_(ce_ids),
                    CanonicalEntity.status == CanonicalEntityStatus.ACTIVE,
                )
            )).scalars().all()

        nodes_created = len(canonical_entities)
        rels_created = len(relationships)

        # Sync to Neo4j if available
        driver = get_neo4j_driver()
        if driver:
            await self._sync_to_neo4j(driver, canonical_entities, relationships, case_id)

        # Audit
        db.add(AuditLog(
            action=AuditAction.GRAPH_BUILT,
            resource_type="case",
            resource_id=case_id,
            new_value=json.dumps({
                "nodes": nodes_created,
                "relationships": rels_created,
            }),
        ))
        await db.flush()

        return {
            "case_id": case_id,
            "nodes_created": nodes_created,
            "relationships_created": rels_created,
            "status": "COMPLETED",
        }

    # ─── Get Case Graph ────────────────────────────────────────────────

    async def get_case_graph(
        self,
        db: AsyncSession,
        case_id: str,
        entity_types: list[str] | None = None,
        relationship_types: list[str] | None = None,
        include_unverified: bool = True,
    ) -> GraphResponse:
        """Get the full graph for a case."""
        # Get relationships
        query = select(Relationship).where(Relationship.case_id == case_id)
        if relationship_types:
            query = query.where(
                Relationship.relationship_type.in_(
                    [RelationshipType(rt) for rt in relationship_types]
                )
            )
        if not include_unverified:
            query = query.where(
                Relationship.verification_status != RelationshipVerificationStatus.REJECTED
            )

        relationships = (await db.execute(query)).scalars().all()

        # Collect entity IDs
        entity_ids = set()
        for rel in relationships:
            entity_ids.add(rel.source_entity_id)
            entity_ids.add(rel.target_entity_id)

        # Also add standalone canonical entities from this case's documents
        docs = (await db.execute(
            select(Document.id).where(Document.case_id == case_id)
        )).scalars().all()

        for doc_id in docs:
            aliases = (await db.execute(
                select(EntityAlias.canonical_entity_id).where(
                    EntityAlias.source_document_id == doc_id
                )
            )).scalars().all()
            entity_ids.update(aliases)

        # Get canonical entities
        nodes = []
        if entity_ids:
            ce_query = select(CanonicalEntity).where(
                CanonicalEntity.id.in_(entity_ids),
                CanonicalEntity.status == CanonicalEntityStatus.ACTIVE,
            )
            if entity_types:
                ce_query = ce_query.where(CanonicalEntity.entity_type.in_(entity_types))

            entities = (await db.execute(ce_query)).scalars().all()

            # Filter entity_ids to only those that passed the type filter
            filtered_ids = set()
            for ent in entities:
                config = ENTITY_TYPE_CONFIG.get(ent.entity_type, {})
                nodes.append(GraphNode(
                    id=ent.id,
                    label=ent.canonical_name,
                    entity_type=ent.entity_type,
                    properties={
                        "normalized_name": ent.normalized_name,
                        "status": ent.status.value,
                        "color": config.get("color", "#94a3b8"),
                        "icon": config.get("icon", "●"),
                        "shape": config.get("shape", "ellipse"),
                    },
                ))
                filtered_ids.add(ent.id)

            # Filter relationships to only include edges between visible nodes
            entity_ids = filtered_ids

        edges = []
        for rel in relationships:
            if rel.source_entity_id in entity_ids and rel.target_entity_id in entity_ids:
                props = json.loads(rel.properties_json) if rel.properties_json else {}
                props["confidence"] = rel.confidence
                props["verification_status"] = rel.verification_status.value
                props["source_document_id"] = rel.source_document_id
                props["source_record_id"] = rel.source_record_id

                edges.append(GraphEdge(
                    id=rel.id,
                    source=rel.source_entity_id,
                    target=rel.target_entity_id,
                    relationship_type=rel.relationship_type.value,
                    label=rel.relationship_type.value,
                    properties=props,
                ))

        return GraphResponse(nodes=nodes, edges=edges, case_id=case_id)

    # ─── Entity Connections ─────────────────────────────────────────────

    async def get_entity_connections(
        self,
        db: AsyncSession,
        entity_id: str,
        depth: int = 1,
    ) -> GraphConnectionsResponse:
        """Get direct connections of an entity."""
        # Get the entity
        entity = (await db.execute(
            select(CanonicalEntity).where(CanonicalEntity.id == entity_id)
        )).scalar_one_or_none()
        if not entity:
            raise ValueError(f"Entity {entity_id} not found")

        config = ENTITY_TYPE_CONFIG.get(entity.entity_type, {})
        center_node = GraphNode(
            id=entity.id,
            label=entity.canonical_name,
            entity_type=entity.entity_type,
            properties={
                "color": config.get("color", "#94a3b8"),
                "icon": config.get("icon", "●"),
                "shape": config.get("shape", "ellipse"),
            },
        )

        visited = {entity_id}
        all_connections = []
        all_edges = []

        current_ids = {entity_id}

        for d in range(depth):
            next_ids = set()

            # Outgoing relationships
            outgoing = (await db.execute(
                select(Relationship).where(
                    Relationship.source_entity_id.in_(current_ids)
                )
            )).scalars().all()

            for rel in outgoing:
                if rel.target_entity_id not in visited:
                    next_ids.add(rel.target_entity_id)
                    visited.add(rel.target_entity_id)
                props = json.loads(rel.properties_json) if rel.properties_json else {}
                props["confidence"] = rel.confidence
                props["verification_status"] = rel.verification_status.value
                all_edges.append(GraphEdge(
                    id=rel.id,
                    source=rel.source_entity_id,
                    target=rel.target_entity_id,
                    relationship_type=rel.relationship_type.value,
                    label=rel.relationship_type.value,
                    properties=props,
                ))

            # Incoming relationships
            incoming = (await db.execute(
                select(Relationship).where(
                    Relationship.target_entity_id.in_(current_ids)
                )
            )).scalars().all()

            for rel in incoming:
                if rel.source_entity_id not in visited:
                    next_ids.add(rel.source_entity_id)
                    visited.add(rel.source_entity_id)
                props = json.loads(rel.properties_json) if rel.properties_json else {}
                props["confidence"] = rel.confidence
                props["verification_status"] = rel.verification_status.value
                all_edges.append(GraphEdge(
                    id=rel.id,
                    source=rel.source_entity_id,
                    target=rel.target_entity_id,
                    relationship_type=rel.relationship_type.value,
                    label=rel.relationship_type.value,
                    properties=props,
                ))

            # Fetch connected entities
            if next_ids:
                connected = (await db.execute(
                    select(CanonicalEntity).where(
                        CanonicalEntity.id.in_(next_ids),
                        CanonicalEntity.status == CanonicalEntityStatus.ACTIVE,
                    )
                )).scalars().all()

                for ent in connected:
                    cfg = ENTITY_TYPE_CONFIG.get(ent.entity_type, {})
                    all_connections.append(GraphNode(
                        id=ent.id,
                        label=ent.canonical_name,
                        entity_type=ent.entity_type,
                        properties={
                            "color": cfg.get("color", "#94a3b8"),
                            "icon": cfg.get("icon", "●"),
                            "shape": cfg.get("shape", "ellipse"),
                        },
                    ))

            current_ids = next_ids
            if not next_ids:
                break

        return GraphConnectionsResponse(
            entity=center_node,
            connections=all_connections,
            edges=all_edges,
        )

    # ─── Shortest Path ──────────────────────────────────────────────────

    async def find_shortest_path(
        self,
        db: AsyncSession,
        source_id: str,
        target_id: str,
        max_depth: int = 5,
    ) -> GraphPathResponse:
        """Find shortest path between two entities using BFS."""
        if source_id == target_id:
            entity = (await db.execute(
                select(CanonicalEntity).where(CanonicalEntity.id == source_id)
            )).scalar_one_or_none()
            if entity:
                cfg = ENTITY_TYPE_CONFIG.get(entity.entity_type, {})
                return GraphPathResponse(
                    found=True,
                    path=[GraphNode(id=entity.id, label=entity.canonical_name,
                                   entity_type=entity.entity_type,
                                   properties={"color": cfg.get("color", "#94a3b8")})],
                    edges=[],
                    length=0,
                )

        # BFS
        queue = [(source_id, [source_id], [])]
        visited = {source_id}

        while queue:
            current_id, path, edge_ids = queue.pop(0)

            if len(path) > max_depth + 1:
                break

            # Get all relationships from current node
            rels = (await db.execute(
                select(Relationship).where(
                    or_(
                        Relationship.source_entity_id == current_id,
                        Relationship.target_entity_id == current_id,
                    )
                )
            )).scalars().all()

            for rel in rels:
                neighbor = (
                    rel.target_entity_id
                    if rel.source_entity_id == current_id
                    else rel.source_entity_id
                )

                if neighbor in visited:
                    continue

                new_path = path + [neighbor]
                new_edges = edge_ids + [rel.id]

                if neighbor == target_id:
                    # Found! Build response
                    path_nodes = []
                    for nid in new_path:
                        ent = (await db.execute(
                            select(CanonicalEntity).where(CanonicalEntity.id == nid)
                        )).scalar_one_or_none()
                        if ent:
                            cfg = ENTITY_TYPE_CONFIG.get(ent.entity_type, {})
                            path_nodes.append(GraphNode(
                                id=ent.id,
                                label=ent.canonical_name,
                                entity_type=ent.entity_type,
                                properties={"color": cfg.get("color", "#94a3b8")},
                            ))

                    path_edges = []
                    for eid in new_edges:
                        r = (await db.execute(
                            select(Relationship).where(Relationship.id == eid)
                        )).scalar_one_or_none()
                        if r:
                            props = json.loads(r.properties_json) if r.properties_json else {}
                            path_edges.append(GraphEdge(
                                id=r.id,
                                source=r.source_entity_id,
                                target=r.target_entity_id,
                                relationship_type=r.relationship_type.value,
                                label=r.relationship_type.value,
                                properties=props,
                            ))

                    return GraphPathResponse(
                        found=True,
                        path=path_nodes,
                        edges=path_edges,
                        length=len(new_edges),
                    )

                visited.add(neighbor)
                queue.append((neighbor, new_path, new_edges))

        return GraphPathResponse(found=False)

    # ─── Graph Search ───────────────────────────────────────────────────

    async def search_graph(
        self,
        db: AsyncSession,
        query: str,
        entity_types: list[str] | None = None,
        limit: int = 20,
    ) -> list[GraphSearchResult]:
        """Search the graph by entity name/value."""
        search_query = select(CanonicalEntity).where(
            CanonicalEntity.status == CanonicalEntityStatus.ACTIVE,
            or_(
                CanonicalEntity.canonical_name.ilike(f"%{query}%"),
                CanonicalEntity.normalized_name.ilike(f"%{query}%"),
            ),
        )
        if entity_types:
            search_query = search_query.where(
                CanonicalEntity.entity_type.in_(entity_types)
            )
        search_query = search_query.limit(limit)

        results = (await db.execute(search_query)).scalars().all()

        return [
            GraphSearchResult(
                id=r.id,
                label=r.canonical_name,
                entity_type=r.entity_type,
                match_field="name",
            )
            for r in results
        ]

    # ─── Graph Validation ───────────────────────────────────────────────

    async def validate_graph(
        self, db: AsyncSession, case_id: str
    ) -> GraphValidationResponse:
        """Validate graph consistency for a case."""
        details = []
        orphan_nodes = 0
        orphan_rels = 0
        missing_sources = 0

        # Get all relationships for this case
        rels = (await db.execute(
            select(Relationship).where(Relationship.case_id == case_id)
        )).scalars().all()

        ce_ids_in_rels = set()
        for rel in rels:
            ce_ids_in_rels.add(rel.source_entity_id)
            ce_ids_in_rels.add(rel.target_entity_id)

            # Check source entity exists
            src = (await db.execute(
                select(CanonicalEntity.id).where(CanonicalEntity.id == rel.source_entity_id)
            )).scalar_one_or_none()
            if not src:
                orphan_rels += 1
                details.append(f"Orphan relationship {rel.id}: source {rel.source_entity_id} not found")

            # Check target entity exists
            tgt = (await db.execute(
                select(CanonicalEntity.id).where(CanonicalEntity.id == rel.target_entity_id)
            )).scalar_one_or_none()
            if not tgt:
                orphan_rels += 1
                details.append(f"Orphan relationship {rel.id}: target {rel.target_entity_id} not found")

            # Check source document exists
            if rel.source_document_id:
                doc = (await db.execute(
                    select(Document.id).where(Document.id == rel.source_document_id)
                )).scalar_one_or_none()
                if not doc:
                    missing_sources += 1
                    details.append(f"Missing source document {rel.source_document_id} for relationship {rel.id}")

        # Check for canonical entities with no relationships
        docs = (await db.execute(
            select(Document.id).where(Document.case_id == case_id)
        )).scalars().all()

        for doc_id in docs:
            aliases = (await db.execute(
                select(EntityAlias.canonical_entity_id).where(
                    EntityAlias.source_document_id == doc_id
                )
            )).scalars().all()
            for ce_id in aliases:
                if ce_id not in ce_ids_in_rels:
                    # Check if it has ANY relationships
                    has_rels = (await db.execute(
                        select(Relationship.id).where(
                            or_(
                                Relationship.source_entity_id == ce_id,
                                Relationship.target_entity_id == ce_id,
                            )
                        ).limit(1)
                    )).scalar_one_or_none()
                    if not has_rels:
                        orphan_nodes += 1

        valid = orphan_rels == 0 and missing_sources == 0
        return GraphValidationResponse(
            valid=valid,
            orphan_nodes=orphan_nodes,
            orphan_relationships=orphan_rels,
            missing_sources=missing_sources,
            details=details[:20],  # Limit detail messages
        )

    # ─── Cross-Case Connections ─────────────────────────────────────────

    async def get_cross_case_connections(
        self, db: AsyncSession, case_id: str
    ) -> list[dict]:
        """Find entities that appear in multiple cases."""
        connections = []

        # Get canonical entities in this case
        docs = (await db.execute(
            select(Document.id).where(Document.case_id == case_id)
        )).scalars().all()

        case_ce_ids = set()
        for doc_id in docs:
            aliases = (await db.execute(
                select(EntityAlias.canonical_entity_id).where(
                    EntityAlias.source_document_id == doc_id
                )
            )).scalars().all()
            case_ce_ids.update(aliases)

        # Also from relationships
        rels = (await db.execute(
            select(Relationship).where(Relationship.case_id == case_id)
        )).scalars().all()
        for rel in rels:
            case_ce_ids.add(rel.source_entity_id)
            case_ce_ids.add(rel.target_entity_id)

        # Find these entities in other cases
        for ce_id in case_ce_ids:
            other_rels = (await db.execute(
                select(Relationship).where(
                    or_(
                        Relationship.source_entity_id == ce_id,
                        Relationship.target_entity_id == ce_id,
                    ),
                    Relationship.case_id != case_id,
                    Relationship.case_id.isnot(None),
                )
            )).scalars().all()

            if other_rels:
                entity = (await db.execute(
                    select(CanonicalEntity).where(CanonicalEntity.id == ce_id)
                )).scalar_one_or_none()
                if entity:
                    other_case_ids = set(r.case_id for r in other_rels if r.case_id)
                    for other_cid in other_case_ids:
                        other_case = (await db.execute(
                            select(Case).where(Case.id == other_cid)
                        )).scalar_one_or_none()
                        connections.append({
                            "entity_id": ce_id,
                            "entity_name": entity.canonical_name,
                            "entity_type": entity.entity_type,
                            "source_case_id": case_id,
                            "connected_case_id": other_cid,
                            "connected_case_number": other_case.case_number if other_case else "Unknown",
                            "relationship_count": len([r for r in other_rels if r.case_id == other_cid]),
                        })

        return connections

    # ─── Neo4j Sync ─────────────────────────────────────────────────────

    async def _sync_to_neo4j(self, driver, entities, relationships, case_id):
        """Sync entities and relationships to Neo4j."""
        try:
            with driver.session() as session:
                # Create nodes
                for ent in entities:
                    session.run(
                        """
                        MERGE (n {id: $id})
                        SET n:%(label)s,
                            n.name = $name,
                            n.normalized_name = $normalized_name,
                            n.entity_type = $entity_type,
                            n.case_id = $case_id
                        """ % {"label": ent.entity_type},
                        id=ent.id,
                        name=ent.canonical_name,
                        normalized_name=ent.normalized_name,
                        entity_type=ent.entity_type,
                        case_id=case_id,
                    )

                # Create relationships
                for rel in relationships:
                    props = json.loads(rel.properties_json) if rel.properties_json else {}
                    session.run(
                        """
                        MATCH (a {id: $source_id}), (b {id: $target_id})
                        MERGE (a)-[r:%(type)s {id: $rel_id}]->(b)
                        SET r.confidence = $confidence,
                            r.verification_status = $verification,
                            r.source_document_id = $doc_id
                        """ % {"type": rel.relationship_type.value},
                        source_id=rel.source_entity_id,
                        target_id=rel.target_entity_id,
                        rel_id=rel.id,
                        confidence=rel.confidence,
                        verification=rel.verification_status.value,
                        doc_id=rel.source_document_id,
                    )

                logger.info(f"Synced {len(entities)} nodes and {len(relationships)} relationships to Neo4j")
        except Exception as e:
            logger.error(f"Neo4j sync failed: {e}")

    # ─── Sync Individual Entity ─────────────────────────────────────────

    async def sync_entity(self, entity: CanonicalEntity):
        """Sync a single entity to Neo4j."""
        driver = get_neo4j_driver()
        if not driver:
            return

        try:
            with driver.session() as session:
                session.run(
                    """
                    MERGE (n {id: $id})
                    SET n.name = $name,
                        n.normalized_name = $normalized_name,
                        n.entity_type = $entity_type
                    """,
                    id=entity.id,
                    name=entity.canonical_name,
                    normalized_name=entity.normalized_name,
                    entity_type=entity.entity_type,
                )
        except Exception as e:
            logger.error(f"Failed to sync entity {entity.id} to Neo4j: {e}")

    # ─── Sync Individual Relationship ───────────────────────────────────

    async def sync_relationship(self, relationship: Relationship):
        """Sync a single relationship to Neo4j."""
        driver = get_neo4j_driver()
        if not driver:
            return

        try:
            with driver.session() as session:
                session.run(
                    """
                    MATCH (a {id: $source_id}), (b {id: $target_id})
                    MERGE (a)-[r:%(type)s {id: $rel_id}]->(b)
                    SET r.confidence = $confidence,
                        r.verification_status = $verification
                    """ % {"type": relationship.relationship_type.value},
                    source_id=relationship.source_entity_id,
                    target_id=relationship.target_entity_id,
                    rel_id=relationship.id,
                    confidence=relationship.confidence,
                    verification=relationship.verification_status.value,
                )
        except Exception as e:
            logger.error(f"Failed to sync relationship {relationship.id} to Neo4j: {e}")
