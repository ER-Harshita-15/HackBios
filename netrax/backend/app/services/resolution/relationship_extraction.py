"""
Relationship Extraction Service — Phase 2

Extracts evidence-backed relationships from Phase 1 entities and documents.
Handles CDR, financial records, FIR, and general document-based relationships.

Relationships describe what the evidence shows.
They do NOT determine guilt or criminality.
"""

import json
import csv
import io
import logging
from datetime import datetime, timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity, EntityType, VerificationStatus
from app.models.entity_mention import EntityMention
from app.models.document import Document, DocumentType
from app.models.document_page import DocumentPage
from app.models.canonical_entity import CanonicalEntity, EntityAlias, CanonicalEntityStatus
from app.models.relationship import Relationship, RelationshipType, RelationshipVerificationStatus
from app.models.audit_log import AuditLog, AuditAction
from app.services.resolution.entity_resolution import EntityResolutionService

logger = logging.getLogger(__name__)


class RelationshipExtractionService:
    """
    Extracts relationships from processed documents.
    All relationships are evidence-backed with provenance.
    """

    def __init__(self):
        self.resolution_service = EntityResolutionService()

    async def extract_all(
        self,
        db: AsyncSession,
        case_id: str | None = None,
        document_id: str | None = None,
    ) -> int:
        """
        Extract all relationships from documents.

        Returns:
            Number of relationships created.
        """
        total = 0

        # Get documents to process
        query = select(Document)
        if case_id:
            query = query.where(Document.case_id == case_id)
        if document_id:
            query = query.where(Document.id == document_id)

        result = await db.execute(query)
        documents = result.scalars().all()

        for doc in documents:
            if doc.document_type == DocumentType.CDR:
                total += await self._extract_cdr_relationships(db, doc)
            elif doc.document_type == DocumentType.FINANCIAL_RECORD:
                total += await self._extract_financial_relationships(db, doc)
            elif doc.document_type in (DocumentType.FIR, DocumentType.INTELLIGENCE_REPORT,
                                       DocumentType.SURVEILLANCE, DocumentType.OTHER,
                                       DocumentType.CRIMINAL_RECORD):
                total += await self._extract_document_relationships(db, doc)

        logger.info(f"Extracted {total} relationships from {len(documents)} documents")
        return total

    # ─── CDR Relationship Extraction ────────────────────────────────────

    async def _extract_cdr_relationships(
        self, db: AsyncSession, document: Document
    ) -> int:
        """
        Extract CALLED relationships from CDR documents.

        CDR data contains caller/receiver phone numbers, timestamps, durations.
        We create Person → CALLED → Person relationships backed by evidence.
        """
        count = 0

        # Get page text to parse CDR data
        pages = (await db.execute(
            select(DocumentPage).where(
                DocumentPage.document_id == document.id
            ).order_by(DocumentPage.page_number)
        )).scalars().all()

        full_text = "\n".join(
            p.cleaned_text or p.raw_text or "" for p in pages
        )

        # Try to parse as CSV
        cdr_records = self._parse_cdr_text(full_text)

        # Check phone entities from this document
        phone_entities = (await db.execute(
            select(Entity).where(
                Entity.document_id == document.id,
                Entity.entity_type == EntityType.PHONE,
            )
        )).scalars().all()

        if len(phone_entities) < 2 and not cdr_records:
            return 0

        for record in cdr_records:
            caller = record.get("caller_number") or record.get("calling_number") or record.get("caller") or ""
            called = record.get("receiver_number") or record.get("called_number") or record.get("callee") or record.get("receiver") or ""
            if not caller or not called or caller == called:
                continue

            rec_id = record.get("call_id") or record.get("record_id") or ""
            caller_name = record.get("caller_name", "")
            receiver_name = record.get("receiver_name", "")
            ts = record.get("timestamp", "")
            call_date = record.get("call_date") or (ts.split()[0] if " " in ts else ts)
            call_time = record.get("call_time") or (ts.split()[1] if " " in ts else "")
            duration = record.get("duration_sec") or record.get("duration_seconds") or record.get("duration") or ""
            call_type = record.get("call_type", "")
            cell_tower_id = record.get("cell_tower_id", "")
            cell_tower_location = record.get("location_name") or record.get("cell_tower_location", "")

            # Find or create canonical entities for phones
            caller_ce = await self._get_or_create_phone_canonical(db, caller, document)
            called_ce = await self._get_or_create_phone_canonical(db, called, document)

            if not caller_ce or not called_ce:
                continue

            # Link caller_name -> USES -> caller_ce if caller_name exists
            if caller_name:
                p_caller = await self._find_or_create_person_canonical(db, caller_name, document.case_id)
                if p_caller and not await self._relationship_exists(db, p_caller.id, caller_ce.id, RelationshipType.USES):
                    db.add(Relationship(
                        relationship_type=RelationshipType.USES,
                        source_entity_id=p_caller.id,
                        target_entity_id=caller_ce.id,
                        source_document_id=document.id,
                        source_record_id=rec_id,
                        extraction_method="CDR_PARSE",
                        confidence=0.90,
                        verification_status=RelationshipVerificationStatus.UNVERIFIED,
                        case_id=document.case_id,
                    ))
                    count += 1

            # Link receiver_name -> USES -> called_ce if receiver_name exists
            if receiver_name:
                p_receiver = await self._find_or_create_person_canonical(db, receiver_name, document.case_id)
                if p_receiver and not await self._relationship_exists(db, p_receiver.id, called_ce.id, RelationshipType.USES):
                    db.add(Relationship(
                        relationship_type=RelationshipType.USES,
                        source_entity_id=p_receiver.id,
                        target_entity_id=called_ce.id,
                        source_document_id=document.id,
                        source_record_id=rec_id,
                        extraction_method="CDR_PARSE",
                        confidence=0.90,
                        verification_status=RelationshipVerificationStatus.UNVERIFIED,
                        case_id=document.case_id,
                    ))
                    count += 1

            # Check for existing relationship
            existing = await self._relationship_exists(
                db, caller_ce.id, called_ce.id,
                RelationshipType.CALLED, rec_id
            )
            if existing:
                continue

            # Create relationship with provenance
            props = {
                "call_id": rec_id,
                "call_date": call_date,
                "call_time": call_time,
                "duration_seconds": duration,
                "call_type": call_type,
                "cell_tower_id": cell_tower_id,
                "cell_tower_location": cell_tower_location,
                "caller_name": caller_name,
                "receiver_name": receiver_name,
            }

            rel = Relationship(
                relationship_type=RelationshipType.CALLED,
                source_entity_id=caller_ce.id,
                target_entity_id=called_ce.id,
                source_document_id=document.id,
                source_record_id=rec_id,
                extraction_method="CDR_PARSE",
                confidence=0.95,
                verification_status=RelationshipVerificationStatus.UNVERIFIED,
                properties_json=json.dumps(props),
                case_id=document.case_id,
            )
            db.add(rel)
            count += 1

            db.add(AuditLog(
                action=AuditAction.RELATIONSHIP_CREATED,
                resource_type="relationship",
                resource_id=rel.id,
                details=json.dumps({
                    "type": "CALLED",
                    "source": caller,
                    "target": called,
                    "document": document.original_filename,
                }),
            ))

        await db.flush()
        return count

    def _parse_cdr_text(self, text: str) -> list[dict]:
        """Parse CDR CSV data from document text."""
        records = []
        raw_lines = text.strip().split('\n')
        lines = [l.strip() for l in raw_lines if l.strip() and not l.strip().startswith('#')]

        # Find header line
        header_idx = -1
        for i, line in enumerate(lines):
            line_str = line.lower()
            if any(k in line_str for k in ['caller_number', 'calling_number', 'call_id', 'record_id']):
                header_idx = i
                break

        if header_idx < 0:
            return records

        try:
            reader = csv.DictReader(lines[header_idx:])
            for row in reader:
                clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k and v is not None}
                caller_val = clean_row.get("caller_number") or clean_row.get("calling_number") or ""
                if caller_val.lower() in ("caller_number", "calling_number", "caller"):
                    continue
                records.append(clean_row)
        except Exception as e:
            logger.warning(f"Failed to parse CDR CSV: {e}")

        return records

    # ─── Financial Relationship Extraction ──────────────────────────────

    async def _extract_financial_relationships(
        self, db: AsyncSession, document: Document
    ) -> int:
        """
        Extract financial relationships from transaction records.

        Creates Account → PARTICIPATED_IN → Transaction relationships
        and Person → HAS_ACCOUNT → Account when ownership can be established.
        """
        count = 0

        pages = (await db.execute(
            select(DocumentPage).where(
                DocumentPage.document_id == document.id
            ).order_by(DocumentPage.page_number)
        )).scalars().all()

        full_text = "\n".join(
            p.cleaned_text or p.raw_text or "" for p in pages
        )

        txn_records = self._parse_financial_text(full_text)

        for record in txn_records:
            acc_from = record.get("from_account") or record.get("account_from") or record.get("sender_account") or ""
            acc_to = record.get("to_account") or record.get("account_to") or record.get("receiver_account") or ""
            beneficiary = record.get("beneficiary_name") or record.get("beneficiary") or record.get("recipient_name") or ""

            if not acc_from or not acc_to:
                continue

            # Create canonical entities for accounts
            from_ce = await self._get_or_create_account_canonical(db, acc_from, document)
            to_ce = await self._get_or_create_account_canonical(db, acc_to, document)

            if not from_ce or not to_ce or from_ce.id == to_ce.id:
                continue

            txn_id = record.get("transaction_id") or record.get("txn_id") or ""
            ts = record.get("timestamp", "")
            txn_date = record.get("date") or (ts.split()[0] if " " in ts else ts)

            existing = await self._relationship_exists(
                db, from_ce.id, to_ce.id,
                RelationshipType.TRANSFERRED_TO, txn_id
            )
            if not existing:
                props = {
                    "transaction_id": txn_id,
                    "amount": record.get("amount", ""),
                    "currency": record.get("currency", "INR"),
                    "date": txn_date,
                    "description": record.get("description", ""),
                    "beneficiary_name": beneficiary,
                    "bank_name": record.get("bank_name", ""),
                    "status": record.get("status", ""),
                }

                rel = Relationship(
                    relationship_type=RelationshipType.TRANSFERRED_TO,
                    source_entity_id=from_ce.id,
                    target_entity_id=to_ce.id,
                    source_document_id=document.id,
                    source_record_id=txn_id,
                    extraction_method="FINANCIAL_PARSE",
                    confidence=0.90,
                    verification_status=RelationshipVerificationStatus.UNVERIFIED,
                    properties_json=json.dumps(props),
                    case_id=document.case_id,
                )
                db.add(rel)
                count += 1

            # Link beneficiary to account if we can match or create
            if beneficiary:
                person_ce = await self._find_or_create_person_canonical(db, beneficiary, document.case_id)
                if person_ce:
                    has_acc_existing = await self._relationship_exists(
                        db, person_ce.id, to_ce.id, RelationshipType.HAS_ACCOUNT
                    )
                    if not has_acc_existing:
                        db.add(Relationship(
                            relationship_type=RelationshipType.HAS_ACCOUNT,
                            source_entity_id=person_ce.id,
                            target_entity_id=to_ce.id,
                            source_document_id=document.id,
                            source_record_id=txn_id,
                            extraction_method="FINANCIAL_PARSE",
                            confidence=0.75,
                            verification_status=RelationshipVerificationStatus.UNVERIFIED,
                            properties_json=json.dumps({"inferred_from": "transaction_beneficiary"}),
                            case_id=document.case_id,
                        ))
                        count += 1

        await db.flush()
        return count

    def _parse_financial_text(self, text: str) -> list[dict]:
        """Parse financial CSV data from document text."""
        records = []
        raw_lines = text.strip().split('\n')
        lines = [l.strip() for l in raw_lines if l.strip() and not l.strip().startswith('#')]

        header_idx = -1
        for i, line in enumerate(lines):
            line_str = line.lower()
            if any(k in line_str for k in ['transaction_id', 'from_account', 'account_from', 'txn_id']):
                header_idx = i
                break

        if header_idx < 0:
            return records

        try:
            reader = csv.DictReader(lines[header_idx:])
            for row in reader:
                clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k and v is not None}
                acc_val = clean_row.get("from_account") or clean_row.get("account_from") or ""
                if acc_val.lower() in ("from_account", "account_from", "account"):
                    continue
                records.append(clean_row)
        except Exception as e:
            logger.warning(f"Failed to parse financial CSV: {e}")

        return records

    # ─── FIR / Document Relationship Extraction ─────────────────────────

    async def _extract_document_relationships(
        self, db: AsyncSession, document: Document
    ) -> int:
        """
        Extract relationships from FIR and general investigation documents.

        Creates Person → USES → Phone, Person → LOCATED_AT → Location, etc.
        based on entity co-occurrence within the same document.
        """
        count = 0

        # Get entities from this document (fall back to unverified if none verified)
        v_entities = (await db.execute(
            select(Entity).where(
                Entity.document_id == document.id,
                Entity.verification_status.in_([
                    VerificationStatus.VERIFIED,
                    VerificationStatus.MODIFIED,
                ]),
            )
        )).scalars().all()

        if v_entities:
            entities = v_entities
        else:
            entities = (await db.execute(
                select(Entity).where(
                    Entity.document_id == document.id,
                    Entity.verification_status != VerificationStatus.REJECTED,
                )
            )).scalars().all()

        # Group by type
        by_type: dict[str, list[Entity]] = {}
        for ent in entities:
            by_type.setdefault(ent.entity_type.value, []).append(ent)

        persons = by_type.get("PERSON", [])
        phones = by_type.get("PHONE", [])
        locations = by_type.get("LOCATION", [])
        accounts = by_type.get("ACCOUNT", [])
        vehicles = by_type.get("VEHICLE", [])
        organizations = by_type.get("ORGANIZATION", [])
        cases = by_type.get("CASE", [])
        emails = by_type.get("EMAIL", [])

        # Use context/co-occurrence to create relationships
        # Person → USES → Phone
        for person in persons:
            person_ce = await self.resolution_service.ensure_canonical_entity(db, person)

            for phone in phones:
                if await self._entities_co_occur(person, phone, db):
                    phone_ce = await self.resolution_service.ensure_canonical_entity(db, phone)
                    if not await self._relationship_exists(db, person_ce.id, phone_ce.id, RelationshipType.USES):
                        db.add(Relationship(
                            relationship_type=RelationshipType.USES,
                            source_entity_id=person_ce.id,
                            target_entity_id=phone_ce.id,
                            source_document_id=document.id,
                            extraction_method="CO_OCCURRENCE",
                            confidence=0.80,
                            verification_status=RelationshipVerificationStatus.UNVERIFIED,
                            case_id=document.case_id,
                        ))
                        count += 1

            # Person → LOCATED_AT → Location
            for loc in locations:
                if await self._entities_co_occur(person, loc, db):
                    loc_ce = await self.resolution_service.ensure_canonical_entity(db, loc)
                    if not await self._relationship_exists(db, person_ce.id, loc_ce.id, RelationshipType.LOCATED_AT):
                        db.add(Relationship(
                            relationship_type=RelationshipType.LOCATED_AT,
                            source_entity_id=person_ce.id,
                            target_entity_id=loc_ce.id,
                            source_document_id=document.id,
                            extraction_method="CO_OCCURRENCE",
                            confidence=0.70,
                            verification_status=RelationshipVerificationStatus.UNVERIFIED,
                            case_id=document.case_id,
                        ))
                        count += 1

            # Person → OWNS → Vehicle
            for vehicle in vehicles:
                if await self._entities_co_occur(person, vehicle, db):
                    veh_ce = await self.resolution_service.ensure_canonical_entity(db, vehicle)
                    if not await self._relationship_exists(db, person_ce.id, veh_ce.id, RelationshipType.OWNS):
                        db.add(Relationship(
                            relationship_type=RelationshipType.OWNS,
                            source_entity_id=person_ce.id,
                            target_entity_id=veh_ce.id,
                            source_document_id=document.id,
                            extraction_method="CO_OCCURRENCE",
                            confidence=0.70,
                            verification_status=RelationshipVerificationStatus.UNVERIFIED,
                            case_id=document.case_id,
                        ))
                        count += 1

            # Person → WORKS_FOR / ASSOCIATED_WITH → Organization
            for org in organizations:
                if await self._entities_co_occur(person, org, db):
                    org_ce = await self.resolution_service.ensure_canonical_entity(db, org)
                    if not await self._relationship_exists(db, person_ce.id, org_ce.id, RelationshipType.ASSOCIATED_WITH):
                        db.add(Relationship(
                            relationship_type=RelationshipType.ASSOCIATED_WITH,
                            source_entity_id=person_ce.id,
                            target_entity_id=org_ce.id,
                            source_document_id=document.id,
                            extraction_method="CO_OCCURRENCE",
                            confidence=0.65,
                            verification_status=RelationshipVerificationStatus.UNVERIFIED,
                            case_id=document.case_id,
                        ))
                        count += 1

            # Person → INVOLVED_IN → Case
            for case_ent in cases:
                case_ce = await self.resolution_service.ensure_canonical_entity(db, case_ent)
                if not await self._relationship_exists(db, person_ce.id, case_ce.id, RelationshipType.INVOLVED_IN):
                    db.add(Relationship(
                        relationship_type=RelationshipType.INVOLVED_IN,
                        source_entity_id=person_ce.id,
                        target_entity_id=case_ce.id,
                        source_document_id=document.id,
                        extraction_method="CO_OCCURRENCE",
                        confidence=0.85,
                        verification_status=RelationshipVerificationStatus.UNVERIFIED,
                        case_id=document.case_id,
                    ))
                    count += 1

            # Person → MENTIONED_IN → Document (as evidence)
            doc_ce = await self._get_or_create_evidence_canonical(db, document)
            if not await self._relationship_exists(db, person_ce.id, doc_ce.id, RelationshipType.MENTIONED_IN):
                db.add(Relationship(
                    relationship_type=RelationshipType.MENTIONED_IN,
                    source_entity_id=person_ce.id,
                    target_entity_id=doc_ce.id,
                    source_document_id=document.id,
                    extraction_method="DOCUMENT",
                    confidence=0.95,
                    verification_status=RelationshipVerificationStatus.UNVERIFIED,
                    case_id=document.case_id,
                ))
                count += 1

        await db.flush()
        return count

    # ─── Helper Methods ─────────────────────────────────────────────────

    async def _entities_co_occur(
        self, entity_a: Entity, entity_b: Entity, db: AsyncSession
    ) -> bool:
        """Check if two entities appear on the same page or nearby context."""
        # Same document is a baseline
        if entity_a.document_id != entity_b.document_id:
            return False

        # Check same page
        mentions_a = (await db.execute(
            select(EntityMention.page_number).where(EntityMention.entity_id == entity_a.id)
        )).scalars().all()
        mentions_b = (await db.execute(
            select(EntityMention.page_number).where(EntityMention.entity_id == entity_b.id)
        )).scalars().all()

        # If on same page, they co-occur
        pages_a = set(mentions_a)
        pages_b = set(mentions_b)
        return bool(pages_a & pages_b) or (not pages_a and not pages_b)

    async def _relationship_exists(
        self, db: AsyncSession,
        source_id: str, target_id: str,
        rel_type: RelationshipType,
        record_id: str | None = None,
    ) -> bool:
        """Check if a relationship already exists."""
        query = select(Relationship.id).where(
            Relationship.source_entity_id == source_id,
            Relationship.target_entity_id == target_id,
            Relationship.relationship_type == rel_type,
        )
        if record_id:
            query = query.where(Relationship.source_record_id == record_id)

        result = await db.execute(query)
        return result.scalar_one_or_none() is not None

    async def _get_or_create_phone_canonical(
        self, db: AsyncSession, phone_number: str, document: Document
    ) -> CanonicalEntity | None:
        """Get or create a canonical entity for a phone number."""
        from app.services.normalization.entity_normalizer import EntityNormalizationService
        normalizer = EntityNormalizationService()
        normalized = normalizer.normalize("PHONE", phone_number)

        # Check if entity exists in entities table
        entity = (await db.execute(
            select(Entity).where(
                Entity.entity_type == EntityType.PHONE,
                Entity.normalized_value == normalized,
            ).limit(1)
        )).scalar_one_or_none()

        if entity:
            return await self.resolution_service.ensure_canonical_entity(db, entity)

        # Check if canonical already exists
        existing = (await db.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.entity_type == "PHONE",
                CanonicalEntity.normalized_name == normalized,
            ).limit(1)
        )).scalar_one_or_none()

        if existing:
            return existing

        # Create new
        ce = CanonicalEntity(
            entity_type="PHONE",
            canonical_name=phone_number,
            normalized_name=normalized,
        )
        db.add(ce)
        await db.flush()
        return ce

    async def _get_or_create_account_canonical(
        self, db: AsyncSession, account: str, document: Document
    ) -> CanonicalEntity | None:
        """Get or create a canonical entity for an account."""
        from app.services.normalization.entity_normalizer import EntityNormalizationService
        normalizer = EntityNormalizationService()
        normalized = normalizer.normalize("ACCOUNT", account)

        entity = (await db.execute(
            select(Entity).where(
                Entity.entity_type == EntityType.ACCOUNT,
                Entity.normalized_value == normalized,
            ).limit(1)
        )).scalar_one_or_none()

        if entity:
            return await self.resolution_service.ensure_canonical_entity(db, entity)

        existing = (await db.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.entity_type == "ACCOUNT",
                CanonicalEntity.normalized_name == normalized,
            ).limit(1)
        )).scalar_one_or_none()

        if existing:
            return existing

        # Mask account number for display
        masked = f"****{normalized[-4:]}" if len(normalized) >= 4 else normalized
        ce = CanonicalEntity(
            entity_type="ACCOUNT",
            canonical_name=masked,
            normalized_name=normalized,
        )
        db.add(ce)
        await db.flush()
        return ce

    async def _get_or_create_evidence_canonical(
        self, db: AsyncSession, document: Document
    ) -> CanonicalEntity:
        """Get or create a canonical entity representing a document as evidence."""
        doc_key = f"DOC-{document.id}"
        existing = (await db.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.entity_type == "EVIDENCE",
                CanonicalEntity.normalized_name == doc_key,
            ).limit(1)
        )).scalar_one_or_none()

        if existing:
            return existing

        ce = CanonicalEntity(
            entity_type="EVIDENCE",
            canonical_name=document.original_filename,
            normalized_name=doc_key,
        )
        db.add(ce)
        await db.flush()
        return ce

    async def _find_person_canonical(
        self, db: AsyncSession, name: str, case_id: str | None
    ) -> CanonicalEntity | None:
        """Try to find a canonical person entity by name."""
        from app.services.normalization.entity_normalizer import EntityNormalizationService
        normalizer = EntityNormalizationService()
        normalized = normalizer.normalize("PERSON", name)

        result = await db.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.entity_type == "PERSON",
                CanonicalEntity.normalized_name == normalized,
            ).limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_or_create_person_canonical(
        self, db: AsyncSession, name: str, case_id: str | None = None
    ) -> CanonicalEntity | None:
        """Find or create a canonical person entity by name."""
        if not name or not name.strip():
            return None

        from app.services.normalization.entity_normalizer import EntityNormalizationService
        normalizer = EntityNormalizationService()
        normalized = normalizer.normalize("PERSON", name.strip())
        if not normalized:
            return None

        # Check existing canonical entity
        result = await db.execute(
            select(CanonicalEntity).where(
                CanonicalEntity.entity_type == "PERSON",
                CanonicalEntity.normalized_name == normalized,
            ).limit(1)
        )
        ce = result.scalar_one_or_none()
        if ce:
            return ce

        # Check existing extracted Entity
        entity = (await db.execute(
            select(Entity).where(
                Entity.entity_type == EntityType.PERSON,
                Entity.normalized_value == normalized,
            ).limit(1)
        )).scalar_one_or_none()
        if entity:
            return await self.resolution_service.ensure_canonical_entity(db, entity)

        # Create new canonical entity
        ce = CanonicalEntity(
            entity_type="PERSON",
            canonical_name=name.strip(),
            normalized_name=normalized,
            status=CanonicalEntityStatus.ACTIVE,
        )
        db.add(ce)
        await db.flush()
        return ce
