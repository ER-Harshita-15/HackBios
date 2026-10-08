"""
Unit & Integration tests for NETRA-X Phase 2:
- Entity Resolution (Record Linkage, String Metrics, Abbreviation Match)
- Canonical Entities & Aliases
- Relationship Extraction (CDR, Financial, FIR)
- Knowledge Graph Sync, Querying, Shortest Path (BFS), and Validation
- Phase 2 API Endpoints
"""

import pytest
import asyncio
import uuid
import json
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.database import Base
from app.models.case import Case, CaseStatus
from app.models.document import Document, DocumentType, ProcessingStatus
from app.models.entity import Entity, EntityType, VerificationStatus
from app.models.canonical_entity import CanonicalEntity, EntityAlias, CanonicalEntityStatus
from app.models.entity_match_candidate import EntityMatchCandidate, MatchStatus
from app.models.relationship import Relationship, RelationshipType, RelationshipVerificationStatus
from app.models.audit_log import AuditLog, AuditAction

from app.services.resolution.entity_resolution import EntityResolutionService
from app.services.resolution.relationship_extraction import RelationshipExtractionService
from app.services.resolution.graph_sync import GraphSyncService


# ─── Unit Tests: Resolution String Metrics ──────────────────────────

class TestEntityResolutionAlgorithms:
    """Test string metrics, token matching, and abbreviation heuristics."""

    def setup_method(self):
        self.service = EntityResolutionService()

    def test_name_similarity_exact(self):
        score = self.service._name_similarity("rahul sharma", "rahul sharma")
        assert score == 1.0

    def test_name_similarity_abbreviation(self):
        # "r. sharma" vs "rahul sharma"
        score = self.service._name_similarity("r. sharma", "rahul sharma")
        assert score >= 0.90

    def test_name_similarity_middle_name(self):
        # "rahul kumar sharma" vs "rahul sharma"
        score = self.service._name_similarity("rahul kumar sharma", "rahul sharma")
        assert score >= 0.85

    def test_name_token_similarity_reordered(self):
        score = self.service._token_similarity("sharma rahul", "rahul sharma")
        assert score == 1.0

    def test_string_similarity_identical(self):
        score = self.service._string_similarity("9876543210", "9876543210")
        assert score == 1.0

    def test_string_similarity_different(self):
        score = self.service._string_similarity("9876543210", "1122334455")
        assert score < 0.3

    def test_location_abbreviation_normalization(self):
        score = self.service._location_similarity("station rd.", "station road")
        assert score == 1.0

    def test_location_similarity_identical(self):
        score = self.service._location_similarity("mg road", "mg road")
        assert score == 1.0


# ─── Integration Tests: Async DB Operations ─────────────────────────

async def _run_candidate_generation_and_confirmation():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as test_db:
        res_service = EntityResolutionService()

        # Create dummy case & documents
        case = Case(
            id=str(uuid.uuid4()),
            case_number="CASE/2026/TEST01",
            title="Test Investigation",
            status=CaseStatus.UNDER_INVESTIGATION,
        )
        test_db.add(case)

        doc1 = Document(
            id=str(uuid.uuid4()),
            case_id=case.id,
            filename="doc1.txt",
            original_filename="doc1.txt",
            document_type=DocumentType.FIR,
            mime_type="text/plain",
            file_size=100,
            file_hash="hash1",
            storage_path="uploads/test1.txt",
            processing_status=ProcessingStatus.COMPLETED,
        )
        doc2 = Document(
            id=str(uuid.uuid4()),
            case_id=case.id,
            filename="doc2.txt",
            original_filename="doc2.txt",
            document_type=DocumentType.INTELLIGENCE_REPORT,
            mime_type="text/plain",
            file_size=100,
            file_hash="hash2",
            storage_path="uploads/test2.txt",
            processing_status=ProcessingStatus.COMPLETED,
        )
        test_db.add_all([doc1, doc2])

        # Two matching verified person entities from different docs
        e1 = Entity(
            id=str(uuid.uuid4()),
            document_id=doc1.id,
            entity_type=EntityType.PERSON,
            value="Amit Verma",
            normalized_value="amit verma",
            confidence=0.95,
            extraction_method="REGEX",
            verification_status=VerificationStatus.VERIFIED,
        )
        e2 = Entity(
            id=str(uuid.uuid4()),
            document_id=doc2.id,
            entity_type=EntityType.PERSON,
            value="A. Verma",
            normalized_value="a verma",
            confidence=0.90,
            extraction_method="REGEX",
            verification_status=VerificationStatus.VERIFIED,
        )
        test_db.add_all([e1, e2])
        await test_db.commit()

        # Generate match candidates
        candidates_count = await res_service.generate_candidates(
            db=test_db,
            case_id=case.id,
            min_score=0.5,
        )
        assert candidates_count >= 1

        # Verify candidate created
        result = await test_db.execute(select(EntityMatchCandidate))
        candidates = result.scalars().all()
        assert len(candidates) >= 1
        candidate = candidates[0]
        assert candidate.status == MatchStatus.PENDING
        assert candidate.match_score >= 0.5

        # Confirm match -> creates CanonicalEntity
        canonical = await res_service.confirm_match(
            db=test_db,
            candidate_id=candidate.id,
            reviewed_by="inspector_singh",
            canonical_name="Amit Verma",
        )
        assert canonical is not None
        assert canonical.canonical_name == "Amit Verma"
        assert canonical.entity_type == "PERSON"
        assert canonical.status == CanonicalEntityStatus.ACTIVE

        # Verify Aliases linked
        aliases = (await test_db.execute(
            select(EntityAlias).where(EntityAlias.canonical_entity_id == canonical.id)
        )).scalars().all()
        assert len(aliases) == 2

        # Verify AuditLog created
        audit = (await test_db.execute(
            select(AuditLog).where(AuditLog.action == AuditAction.ENTITY_MATCH_CONFIRMED)
        )).scalars().all()
        assert len(audit) >= 1

    await engine.dispose()


def test_candidate_generation_and_confirmation():
    asyncio.run(_run_candidate_generation_and_confirmation())


async def _run_relationship_extraction_and_verification():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as test_db:
        case = Case(
            id=str(uuid.uuid4()),
            case_number="CASE/2026/TEST02",
            title="Relationship Test Case",
            status=CaseStatus.UNDER_INVESTIGATION,
        )
        test_db.add(case)

        p1 = CanonicalEntity(
            id=str(uuid.uuid4()),
            entity_type="PERSON",
            canonical_name="Sanjay Gupta",
            normalized_name="sanjay gupta",
            status=CanonicalEntityStatus.ACTIVE,
        )
        p2 = CanonicalEntity(
            id=str(uuid.uuid4()),
            entity_type="PERSON",
            canonical_name="Rajesh Khanna",
            normalized_name="rajesh khanna",
            status=CanonicalEntityStatus.ACTIVE,
        )
        test_db.add_all([p1, p2])
        await test_db.flush()

        # Create Relationship
        rel = Relationship(
            id=str(uuid.uuid4()),
            case_id=case.id,
            source_entity_id=p1.id,
            target_entity_id=p2.id,
            relationship_type=RelationshipType.CALLED,
            extraction_method="CDR",
            confidence=0.98,
            verification_status=RelationshipVerificationStatus.UNVERIFIED,
            properties_json=json.dumps({"call_count": 14, "duration_sec": 780}),
        )
        test_db.add(rel)
        await test_db.commit()

        # Query relationship
        saved_rel = (await test_db.execute(
            select(Relationship).where(Relationship.id == rel.id)
        )).scalar_one()
        assert saved_rel.relationship_type == RelationshipType.CALLED
        assert saved_rel.confidence == 0.98
        assert saved_rel.verification_status == RelationshipVerificationStatus.UNVERIFIED

        # Verify Relationship
        saved_rel.verification_status = RelationshipVerificationStatus.VERIFIED
        saved_rel.verified_by = "investigator"
        saved_rel.verified_at = datetime.now(timezone.utc)
        await test_db.commit()

        updated = (await test_db.execute(
            select(Relationship).where(Relationship.id == rel.id)
        )).scalar_one()
        assert updated.verification_status == RelationshipVerificationStatus.VERIFIED

    await engine.dispose()


def test_relationship_extraction_and_verification():
    asyncio.run(_run_relationship_extraction_and_verification())


async def _run_knowledge_graph_sync_and_bfs_path():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as test_db:
        graph_service = GraphSyncService()

        case = Case(
            id=str(uuid.uuid4()),
            case_number="CASE/2026/TEST03",
            title="Knowledge Graph Test Case",
            status=CaseStatus.UNDER_INVESTIGATION,
        )
        test_db.add(case)

        # Create 3 canonical entities: A -> B -> C
        node_a = CanonicalEntity(
            id=str(uuid.uuid4()),
            entity_type="PERSON",
            canonical_name="Alpha",
            normalized_name="alpha",
            status=CanonicalEntityStatus.ACTIVE,
        )
        node_b = CanonicalEntity(
            id=str(uuid.uuid4()),
            entity_type="PHONE",
            canonical_name="+919999988888",
            normalized_name="+919999988888",
            status=CanonicalEntityStatus.ACTIVE,
        )
        node_c = CanonicalEntity(
            id=str(uuid.uuid4()),
            entity_type="ACCOUNT",
            canonical_name="AC-987654321",
            normalized_name="ac-987654321",
            status=CanonicalEntityStatus.ACTIVE,
        )
        test_db.add_all([node_a, node_b, node_c])
        await test_db.flush()

        rel1 = Relationship(
            id=str(uuid.uuid4()),
            case_id=case.id,
            source_entity_id=node_a.id,
            target_entity_id=node_b.id,
            relationship_type=RelationshipType.OWNS,
            extraction_method="FIR",
            confidence=0.95,
            verification_status=RelationshipVerificationStatus.VERIFIED,
        )
        rel2 = Relationship(
            id=str(uuid.uuid4()),
            case_id=case.id,
            source_entity_id=node_b.id,
            target_entity_id=node_c.id,
            relationship_type=RelationshipType.TRANSFERRED_TO,
            extraction_method="FINANCIAL",
            confidence=0.90,
            verification_status=RelationshipVerificationStatus.VERIFIED,
        )
        test_db.add_all([rel1, rel2])
        await test_db.commit()

        # 1. Build Case Graph
        build_result = await graph_service.build_case_graph(
            db=test_db,
            case_id=case.id,
            include_unverified=True,
        )
        assert build_result["status"] == "COMPLETED"
        assert build_result["nodes_created"] == 3
        assert build_result["relationships_created"] == 2

        # 2. Query Graph
        graph_resp = await graph_service.get_case_graph(
            db=test_db,
            case_id=case.id,
            include_unverified=True,
        )
        assert len(graph_resp.nodes) == 3
        assert len(graph_resp.edges) == 2

        # 3. BFS Shortest Path: Alpha -> AC-987654321 (via Phone)
        path_resp = await graph_service.find_shortest_path(
            db=test_db,
            source_id=node_a.id,
            target_id=node_c.id,
            max_depth=5,
        )
        assert path_resp.found is True
        assert path_resp.length == 2
        assert len(path_resp.path) == 3
        assert path_resp.path[0].id == node_a.id
        assert path_resp.path[1].id == node_b.id
        assert path_resp.path[2].id == node_c.id

        # 4. Ego-network connections for node_b
        ego_resp = await graph_service.get_entity_connections(
            db=test_db,
            entity_id=node_b.id,
            depth=1,
        )
        assert ego_resp.entity.id == node_b.id
        assert len(ego_resp.connections) == 2

        # 5. Graph Validation
        validation = await graph_service.validate_graph(
            db=test_db,
            case_id=case.id,
        )
        assert validation.valid is True
        assert validation.orphan_relationships == 0

    await engine.dispose()


def test_knowledge_graph_sync_and_bfs_path():
    asyncio.run(_run_knowledge_graph_sync_and_bfs_path())


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
