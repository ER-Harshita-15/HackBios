"""
Entity Resolution Service — Phase 2

Generates candidate matches between verified entities, calculates similarity scores,
and provides explainable match evidence for human review.

Match scores represent RECORD-LINKAGE CONFIDENCE, not criminality.
The system suggests matches; humans decide.
"""

import json
import logging
import re
from difflib import SequenceMatcher
from datetime import datetime, timezone

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entity import Entity, EntityType, VerificationStatus
from app.models.entity_mention import EntityMention
from app.models.canonical_entity import CanonicalEntity, EntityAlias, CanonicalEntityStatus
from app.models.entity_match_candidate import EntityMatchCandidate, MatchStatus
from app.models.audit_log import AuditLog, AuditAction

logger = logging.getLogger(__name__)


class EntityResolutionService:
    """
    Service for resolving entity duplicates across documents.

    Architecture:
        Phase 1 Entities → Candidate Generation → Similarity Calculation
        → Evidence Comparison → Match Score → Candidate Match → Human Review
        → Canonical Entity
    """

    # ─── Similarity Weights by Entity Type ──────────────────────────────

    PERSON_WEIGHTS = {
        "name": 0.35,
        "phone": 0.30,
        "email": 0.15,
        "location": 0.10,
        "account": 0.05,
        "vehicle": 0.05,
    }

    PHONE_WEIGHTS = {"number": 0.90, "associated_name": 0.10}
    ACCOUNT_WEIGHTS = {"number": 0.85, "associated_name": 0.15}
    VEHICLE_WEIGHTS = {"registration": 0.85, "associated_name": 0.15}
    LOCATION_WEIGHTS = {"name": 0.80, "context": 0.20}
    EMAIL_WEIGHTS = {"address": 0.90, "associated_name": 0.10}
    ORGANIZATION_WEIGHTS = {"name": 0.80, "location": 0.20}

    # ─── Candidate Generation ───────────────────────────────────────────

    async def generate_candidates(
        self,
        db: AsyncSession,
        case_id: str | None = None,
        entity_type: str | None = None,
        min_score: float = 0.5,
        include_unverified: bool = False,
    ) -> int:
        """
        Generate candidate matches from entities across documents.

        Only compares entities from different documents to find cross-document
        matches. Does NOT automatically merge entities.

        Returns:
            Number of new candidates generated.
        """
        # Fetch entities for candidate generation
        query = select(Entity).where(Entity.verification_status != VerificationStatus.REJECTED)

        if not include_unverified:
            # Check if verified entities exist
            v_check = await db.execute(
                select(func.count(Entity.id)).where(
                    Entity.verification_status.in_([
                        VerificationStatus.VERIFIED,
                        VerificationStatus.MODIFIED,
                    ])
                )
            )
            has_verified = (v_check.scalar() or 0) > 1
            if has_verified:
                query = query.where(
                    Entity.verification_status.in_([
                        VerificationStatus.VERIFIED,
                        VerificationStatus.MODIFIED,
                    ])
                )

        if entity_type:
            query = query.where(Entity.entity_type == EntityType(entity_type))

        if case_id:
            from app.models.document import Document
            query = query.join(Document, Entity.document_id == Document.id).where(
                Document.case_id == case_id
            )

        result = await db.execute(query)
        entities = list(result.scalars().all())

        if len(entities) < 2:
            return 0

        # Get existing candidate pairs to avoid duplicates
        existing = await db.execute(select(EntityMatchCandidate))
        existing_pairs = set()
        for c in existing.scalars().all():
            existing_pairs.add((c.entity_a_id, c.entity_b_id))
            existing_pairs.add((c.entity_b_id, c.entity_a_id))

        # Check canonical mapping to avoid comparing entities already merged in the same canonical entity
        alias_result = await db.execute(select(EntityAlias.entity_id, EntityAlias.canonical_entity_id))
        entity_canonical_map = {row[0]: row[1] for row in alias_result.all()}

        new_candidates = 0

        # Group entities by type for comparison
        by_type: dict[str, list[Entity]] = {}
        for ent in entities:
            type_key = ent.entity_type.value
            by_type.setdefault(type_key, []).append(ent)

        for etype, group in by_type.items():
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]

                    # Only compare across different documents
                    if a.document_id == b.document_id:
                        continue

                    # If both entities already belong to the exact same canonical entity, skip
                    can_a = entity_canonical_map.get(a.id)
                    can_b = entity_canonical_map.get(b.id)
                    if can_a and can_b and can_a == can_b:
                        continue

                    # Skip if already compared
                    if (a.id, b.id) in existing_pairs:
                        continue

                    # Calculate similarity
                    score, features, explanation = await self.calculate_similarity(
                        a, b, db
                    )

                    if score >= min_score:
                        candidate = EntityMatchCandidate(
                            entity_a_id=a.id,
                            entity_b_id=b.id,
                            match_score=round(score, 4),
                            matching_features=json.dumps([f.__dict__ if hasattr(f, '__dict__') else f for f in features]),
                            explanation=explanation,
                            status=MatchStatus.PENDING,
                        )
                        db.add(candidate)
                        new_candidates += 1
                        existing_pairs.add((a.id, b.id))

                        # Audit log
                        db.add(AuditLog(
                            action=AuditAction.ENTITY_MATCH_SUGGESTED,
                            resource_type="entity_match_candidate",
                            resource_id=candidate.id,
                            details=json.dumps({
                                "entity_a": a.value,
                                "entity_b": b.value,
                                "score": score,
                            }),
                        ))

        if new_candidates > 0:
            await db.flush()

        logger.info(f"Generated {new_candidates} entity match candidates")
        return new_candidates

    # ─── Similarity Calculation ─────────────────────────────────────────

    async def calculate_similarity(
        self,
        entity_a: Entity,
        entity_b: Entity,
        db: AsyncSession,
    ) -> tuple[float, list[dict], str]:
        """
        Calculate similarity between two entities.

        Returns:
            (score, features, explanation) where score is 0.0-1.0,
            features is a list of matching features with scores,
            and explanation is a human-readable explanation.
        """
        etype = entity_a.entity_type.value
        strategy = self._get_strategy(etype)
        return await strategy(entity_a, entity_b, db)

    def _get_strategy(self, entity_type: str):
        strategies = {
            "PERSON": self._compare_persons,
            "PHONE": self._compare_phones,
            "EMAIL": self._compare_emails,
            "LOCATION": self._compare_locations,
            "ORGANIZATION": self._compare_organizations,
            "VEHICLE": self._compare_vehicles,
            "ACCOUNT": self._compare_accounts,
        }
        return strategies.get(entity_type, self._compare_default)

    # ─── Person Comparison ──────────────────────────────────────────────

    async def _compare_persons(
        self, a: Entity, b: Entity, db: AsyncSession
    ) -> tuple[float, list[dict], str]:
        features = []
        reasons = []

        # Name similarity
        name_score = self._name_similarity(a.normalized_value, b.normalized_value)
        features.append({"feature": "Name similarity", "score": name_score,
                         "description": f"'{a.value}' vs '{b.value}'"})
        if name_score > 0.7:
            reasons.append("✓ Similar name")

        # Check for shared phone numbers
        phone_score = await self._shared_attribute_score(
            a, b, EntityType.PHONE, db
        )
        if phone_score > 0:
            features.append({"feature": "Phone similarity", "score": phone_score,
                             "description": "Same phone number found"})
            reasons.append("✓ Same phone number")

        # Check for shared email
        email_score = await self._shared_attribute_score(
            a, b, EntityType.EMAIL, db
        )
        if email_score > 0:
            features.append({"feature": "Email similarity", "score": email_score,
                             "description": "Same email address found"})
            reasons.append("✓ Same email")

        # Check for shared location
        location_score = await self._shared_attribute_score(
            a, b, EntityType.LOCATION, db
        )
        if location_score > 0:
            features.append({"feature": "Location similarity", "score": location_score,
                             "description": "Same location mentioned"})
            reasons.append("✓ Same location")

        # Check for shared account
        account_score = await self._shared_attribute_score(
            a, b, EntityType.ACCOUNT, db
        )
        if account_score > 0:
            features.append({"feature": "Account similarity", "score": account_score,
                             "description": "Same account number found"})
            reasons.append("✓ Same account")

        # Check for shared vehicle
        vehicle_score = await self._shared_attribute_score(
            a, b, EntityType.VEHICLE, db
        )
        if vehicle_score > 0:
            features.append({"feature": "Vehicle similarity", "score": vehicle_score,
                             "description": "Same vehicle found"})
            reasons.append("✓ Same vehicle")

        # Weighted score
        w = self.PERSON_WEIGHTS
        has_other_evidence = any(s > 0 for s in [phone_score, email_score, location_score, account_score, vehicle_score])
        if not has_other_evidence:
            # When only name comparison is available between the records
            total = name_score * 0.85
        else:
            total = (
                name_score * w["name"]
                + phone_score * w["phone"]
                + email_score * w["email"]
                + location_score * w["location"]
                + account_score * w["account"]
                + vehicle_score * w["vehicle"]
            )

        # Boost if multiple strong matches
        strong_matches = sum(1 for f in features if f["score"] > 0.8)
        if strong_matches >= 2:
            total = min(total * 1.15, 1.0)

        explanation = f"Entity Match Score: {total:.0%}\n\nReasons:\n" + "\n".join(reasons) if reasons else "No matching features found"

        return total, features, explanation

    # ─── Phone Comparison ───────────────────────────────────────────────

    async def _compare_phones(
        self, a: Entity, b: Entity, db: AsyncSession
    ) -> tuple[float, list[dict], str]:
        features = []
        reasons = []

        score = 1.0 if a.normalized_value == b.normalized_value else self._string_similarity(a.normalized_value, b.normalized_value)
        features.append({"feature": "Phone number match", "score": score,
                         "description": f"'{a.value}' vs '{b.value}'"})
        if score > 0.9:
            reasons.append("✓ Same phone number")

        explanation = f"Entity Match Score: {score:.0%}\n\nReasons:\n" + "\n".join(reasons)
        return score, features, explanation

    # ─── Email Comparison ───────────────────────────────────────────────

    async def _compare_emails(
        self, a: Entity, b: Entity, db: AsyncSession
    ) -> tuple[float, list[dict], str]:
        features = []
        reasons = []

        score = 1.0 if a.normalized_value == b.normalized_value else self._string_similarity(a.normalized_value, b.normalized_value)
        features.append({"feature": "Email address match", "score": score,
                         "description": f"'{a.value}' vs '{b.value}'"})
        if score > 0.9:
            reasons.append("✓ Same email address")

        explanation = f"Entity Match Score: {score:.0%}\n\nReasons:\n" + "\n".join(reasons)
        return score, features, explanation

    # ─── Vehicle Comparison ─────────────────────────────────────────────

    async def _compare_vehicles(
        self, a: Entity, b: Entity, db: AsyncSession
    ) -> tuple[float, list[dict], str]:
        features = []
        reasons = []

        score = 1.0 if a.normalized_value == b.normalized_value else self._string_similarity(a.normalized_value, b.normalized_value)
        features.append({"feature": "Vehicle registration match", "score": score,
                         "description": f"'{a.value}' vs '{b.value}'"})
        if score > 0.9:
            reasons.append("✓ Same vehicle registration")

        explanation = f"Entity Match Score: {score:.0%}\n\nReasons:\n" + "\n".join(reasons)
        return score, features, explanation

    # ─── Account Comparison ─────────────────────────────────────────────

    async def _compare_accounts(
        self, a: Entity, b: Entity, db: AsyncSession
    ) -> tuple[float, list[dict], str]:
        features = []
        reasons = []

        score = 1.0 if a.normalized_value == b.normalized_value else self._string_similarity(a.normalized_value, b.normalized_value)
        features.append({"feature": "Account number match", "score": score,
                         "description": f"Masked: ...{a.normalized_value[-4:]} vs ...{b.normalized_value[-4:]}"})
        if score > 0.9:
            reasons.append("✓ Same account number")

        explanation = f"Entity Match Score: {score:.0%}\n\nReasons:\n" + "\n".join(reasons)
        return score, features, explanation

    # ─── Location Comparison ────────────────────────────────────────────

    async def _compare_locations(
        self, a: Entity, b: Entity, db: AsyncSession
    ) -> tuple[float, list[dict], str]:
        features = []
        reasons = []

        score = self._location_similarity(a.normalized_value, b.normalized_value)
        features.append({"feature": "Location name match", "score": score,
                         "description": f"'{a.value}' vs '{b.value}'"})
        if score > 0.7:
            reasons.append("✓ Similar location name")

        explanation = f"Entity Match Score: {score:.0%}\n\nReasons:\n" + "\n".join(reasons)
        return score, features, explanation

    # ─── Organization Comparison ────────────────────────────────────────

    async def _compare_organizations(
        self, a: Entity, b: Entity, db: AsyncSession
    ) -> tuple[float, list[dict], str]:
        features = []
        reasons = []

        score = self._name_similarity(a.normalized_value, b.normalized_value)
        features.append({"feature": "Organization name match", "score": score,
                         "description": f"'{a.value}' vs '{b.value}'"})
        if score > 0.7:
            reasons.append("✓ Similar organization name")

        explanation = f"Entity Match Score: {score:.0%}\n\nReasons:\n" + "\n".join(reasons)
        return score, features, explanation

    # ─── Default Comparison ─────────────────────────────────────────────

    async def _compare_default(
        self, a: Entity, b: Entity, db: AsyncSession
    ) -> tuple[float, list[dict], str]:
        score = self._string_similarity(a.normalized_value, b.normalized_value)
        features = [{"feature": "Value similarity", "score": score,
                     "description": f"'{a.value}' vs '{b.value}'"}]
        explanation = f"Entity Match Score: {score:.0%}"
        return score, features, explanation

    # ─── Shared Attribute Scoring ───────────────────────────────────────

    async def _shared_attribute_score(
        self,
        entity_a: Entity,
        entity_b: Entity,
        attr_type: EntityType,
        db: AsyncSession,
    ) -> float:
        """
        Check if two entities share a co-occurring attribute in their documents.

        E.g., if entity_a (PERSON in Doc A) and entity_b (PERSON in Doc B)
        both have the same PHONE number in their respective documents,
        that's evidence they might be the same person.
        """
        # Get all entities of attr_type from doc A
        result_a = await db.execute(
            select(Entity.normalized_value).where(
                Entity.document_id == entity_a.document_id,
                Entity.entity_type == attr_type,
                Entity.verification_status.in_([
                    VerificationStatus.VERIFIED,
                    VerificationStatus.MODIFIED,
                ]),
            )
        )
        values_a = set(result_a.scalars().all())

        if not values_a:
            return 0.0

        # Get all entities of attr_type from doc B
        result_b = await db.execute(
            select(Entity.normalized_value).where(
                Entity.document_id == entity_b.document_id,
                Entity.entity_type == attr_type,
                Entity.verification_status.in_([
                    VerificationStatus.VERIFIED,
                    VerificationStatus.MODIFIED,
                ]),
            )
        )
        values_b = set(result_b.scalars().all())

        if not values_b:
            return 0.0

        # Check overlap
        overlap = values_a & values_b
        if overlap:
            return 1.0

        # Check for partial matches (e.g., location abbreviations)
        for va in values_a:
            for vb in values_b:
                sim = self._string_similarity(va, vb)
                if sim > 0.85:
                    return sim

        return 0.0

    # ─── String Similarity Utilities ────────────────────────────────────

    def _name_similarity(self, a: str, b: str) -> float:
        """
        Compare names using multiple strategies:
        1. Exact match
        2. One name is abbreviation of another (R. Sharma / Rahul Sharma)
        3. SequenceMatcher ratio
        """
        if a == b:
            return 1.0

        # Check if one is abbreviation of the other
        abbrev_score = self._abbreviation_match(a, b)
        if abbrev_score > 0:
            return abbrev_score

        # SequenceMatcher
        seq_score = SequenceMatcher(None, a, b).ratio()

        # Token-level similarity (handles reordered names)
        token_score = self._token_similarity(a, b)

        return max(seq_score, token_score)

    def _abbreviation_match(self, a: str, b: str) -> float:
        """Check if one name is an abbreviation of another."""
        parts_a = a.split()
        parts_b = b.split()

        if not parts_a or not parts_b:
            return 0.0

        # Check if last names match and first name is abbreviated
        if len(parts_a) >= 2 and len(parts_b) >= 2:
            if parts_a[-1] == parts_b[-1]:  # Same last name
                first_a = parts_a[0].rstrip('.')
                first_b = parts_b[0].rstrip('.')
                if len(first_a) == 1 and first_b.startswith(first_a):
                    return 0.92
                if len(first_b) == 1 and first_a.startswith(first_b):
                    return 0.92

        # Check if one name has middle name/initial
        if len(parts_a) != len(parts_b):
            shorter = parts_a if len(parts_a) < len(parts_b) else parts_b
            longer = parts_b if len(parts_a) < len(parts_b) else parts_a

            if shorter[0] == longer[0] and shorter[-1] == longer[-1]:
                return 0.88

        return 0.0

    def _token_similarity(self, a: str, b: str) -> float:
        """Compare names at token level, handling reordering."""
        tokens_a = set(a.split())
        tokens_b = set(b.split())

        if not tokens_a or not tokens_b:
            return 0.0

        intersection = tokens_a & tokens_b
        union = tokens_a | tokens_b

        return len(intersection) / len(union) if union else 0.0

    def _string_similarity(self, a: str, b: str) -> float:
        """Basic string similarity using SequenceMatcher."""
        if a == b:
            return 1.0
        return SequenceMatcher(None, a, b).ratio()

    def _location_similarity(self, a: str, b: str) -> float:
        """Location-aware similarity that handles abbreviations."""
        if a == b:
            return 1.0

        # Normalize common abbreviations
        abbrevs = {
            "rd.": "road", "rd": "road",
            "st.": "street", "st": "street",
            "ave.": "avenue", "ave": "avenue",
            "blvd.": "boulevard", "blvd": "boulevard",
            "nr.": "near", "nr": "near",
            "opp.": "opposite", "opp": "opposite",
        }

        norm_a = a
        norm_b = b
        for abbr, full in abbrevs.items():
            pattern = r'\b' + re.escape(abbr) + (r'\b' if abbr[-1].isalnum() else r'(?!\w)')
            norm_a = re.sub(pattern, full, norm_a)
            norm_b = re.sub(pattern, full, norm_b)

        if norm_a == norm_b:
            return 1.0

        # Check if one is a substring of the other
        if norm_a in norm_b or norm_b in norm_a:
            return 0.9

        return SequenceMatcher(None, norm_a, norm_b).ratio()

    async def confirm_match(
        self,
        db: AsyncSession,
        candidate_id: str,
        reviewed_by: str = "investigator",
        canonical_name: str | None = None,
    ) -> CanonicalEntity:
        """
        Confirm an entity match and create/update canonical entity.

        When confirmed:
            Entity A → Canonical Entity ← Entity B
        """
        result = await db.execute(
            select(EntityMatchCandidate).where(EntityMatchCandidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise ValueError(f"Match candidate {candidate_id} not found")

        if candidate.status != MatchStatus.PENDING:
            raise ValueError(f"Candidate already {candidate.status.value}")

        # Fetch both entities
        entity_a = (await db.execute(
            select(Entity).where(Entity.id == candidate.entity_a_id)
        )).scalar_one()
        entity_b = (await db.execute(
            select(Entity).where(Entity.id == candidate.entity_b_id)
        )).scalar_one()

        # Check if either entity already has a canonical entity
        alias_a = (await db.execute(
            select(EntityAlias).where(EntityAlias.entity_id == entity_a.id)
        )).scalar_one_or_none()
        alias_b = (await db.execute(
            select(EntityAlias).where(EntityAlias.entity_id == entity_b.id)
        )).scalar_one_or_none()

        canonical = None
        if alias_a and alias_b:
            if alias_a.canonical_entity_id == alias_b.canonical_entity_id:
                canonical = (await db.execute(
                    select(CanonicalEntity).where(CanonicalEntity.id == alias_a.canonical_entity_id)
                )).scalar_one()
            else:
                # Merge canonical_b into canonical_a
                canonical = (await db.execute(
                    select(CanonicalEntity).where(CanonicalEntity.id == alias_a.canonical_entity_id)
                )).scalar_one()
                can_b = (await db.execute(
                    select(CanonicalEntity).where(CanonicalEntity.id == alias_b.canonical_entity_id)
                )).scalar_one_or_none()

                from sqlalchemy import update
                await db.execute(
                    update(EntityAlias)
                    .where(EntityAlias.canonical_entity_id == alias_b.canonical_entity_id)
                    .values(canonical_entity_id=canonical.id)
                )
                await db.execute(
                    update(Relationship)
                    .where(Relationship.source_entity_id == alias_b.canonical_entity_id)
                    .values(source_entity_id=canonical.id)
                )
                await db.execute(
                    update(Relationship)
                    .where(Relationship.target_entity_id == alias_b.canonical_entity_id)
                    .values(target_entity_id=canonical.id)
                )
                if can_b:
                    can_b.status = CanonicalEntityStatus.MERGED
                    can_b.merged_into_id = canonical.id
        elif alias_a:
            canonical = (await db.execute(
                select(CanonicalEntity).where(CanonicalEntity.id == alias_a.canonical_entity_id)
            )).scalar_one()
        elif alias_b:
            canonical = (await db.execute(
                select(CanonicalEntity).where(CanonicalEntity.id == alias_b.canonical_entity_id)
            )).scalar_one()

        if not canonical:
            # Create new canonical entity using custom name or entity_a's data
            c_name = canonical_name if canonical_name else entity_a.value
            canonical = CanonicalEntity(
                entity_type=entity_a.entity_type.value,
                canonical_name=c_name,
                normalized_name=c_name.lower().strip(),
                status=CanonicalEntityStatus.ACTIVE,
            )
            db.add(canonical)
            await db.flush()

            db.add(AuditLog(
                user=reviewed_by,
                action=AuditAction.CANONICAL_ENTITY_CREATED,
                resource_type="canonical_entity",
                resource_id=canonical.id,
                new_value=json.dumps({
                    "name": canonical.canonical_name,
                    "type": canonical.entity_type,
                }),
            ))

        # Link entities to canonical (if not already linked)
        if not alias_a:
            db.add(EntityAlias(
                canonical_entity_id=canonical.id,
                entity_id=entity_a.id,
                alias_value=entity_a.value,
                normalized_value=entity_a.normalized_value,
                source_document_id=entity_a.document_id,
            ))
        if not alias_b:
            db.add(EntityAlias(
                canonical_entity_id=canonical.id,
                entity_id=entity_b.id,
                alias_value=entity_b.value,
                normalized_value=entity_b.normalized_value,
                source_document_id=entity_b.document_id,
            ))

        # Update candidate
        candidate.status = MatchStatus.CONFIRMED
        candidate.reviewed_by = reviewed_by
        candidate.reviewed_at = datetime.now(timezone.utc)
        candidate.canonical_entity_id = canonical.id

        # Audit
        db.add(AuditLog(
            user=reviewed_by,
            action=AuditAction.ENTITY_MATCH_CONFIRMED,
            resource_type="entity_match_candidate",
            resource_id=candidate.id,
            new_value=json.dumps({
                "entity_a": entity_a.value,
                "entity_b": entity_b.value,
                "canonical_id": canonical.id,
            }),
        ))

        await db.flush()
        return canonical

    async def reject_match(
        self,
        db: AsyncSession,
        candidate_id: str,
        reviewed_by: str = "investigator",
        reason: str | None = None,
    ) -> None:
        """Reject an entity match. Entity A ≠ Entity B."""
        result = await db.execute(
            select(EntityMatchCandidate).where(EntityMatchCandidate.id == candidate_id)
        )
        candidate = result.scalar_one_or_none()
        if not candidate:
            raise ValueError(f"Match candidate {candidate_id} not found")

        candidate.status = MatchStatus.REJECTED
        candidate.reviewed_by = reviewed_by
        candidate.reviewed_at = datetime.now(timezone.utc)

        db.add(AuditLog(
            user=reviewed_by,
            action=AuditAction.ENTITY_MATCH_REJECTED,
            resource_type="entity_match_candidate",
            resource_id=candidate.id,
            details=reason,
        ))

        await db.flush()

    # ─── Canonical Entity for Standalone Entities ───────────────────────

    async def ensure_canonical_entity(
        self, db: AsyncSession, entity: Entity
    ) -> CanonicalEntity:
        """
        Ensure a verified entity has a canonical entity.
        If it doesn't have one, create one (1:1 for unmatched entities).
        """
        # Check if already aliased
        alias = (await db.execute(
            select(EntityAlias).where(EntityAlias.entity_id == entity.id)
        )).scalar_one_or_none()

        if alias:
            return (await db.execute(
                select(CanonicalEntity).where(CanonicalEntity.id == alias.canonical_entity_id)
            )).scalar_one()

        # Create new canonical entity
        canonical = CanonicalEntity(
            entity_type=entity.entity_type.value,
            canonical_name=entity.value,
            normalized_name=entity.normalized_value,
            status=CanonicalEntityStatus.ACTIVE,
        )
        db.add(canonical)
        await db.flush()

        # Create alias link
        db.add(EntityAlias(
            canonical_entity_id=canonical.id,
            entity_id=entity.id,
            alias_value=entity.value,
            normalized_value=entity.normalized_value,
            source_document_id=entity.document_id,
        ))
        await db.flush()

        return canonical

    async def sync_all_entities(
        self,
        db: AsyncSession,
        case_id: str | None = None,
        include_unverified: bool = False,
    ) -> int:
        """
        Synchronize extracted entities into canonical entities.
        Ensures entities have a CanonicalEntity profile and EntityAlias.
        """
        query = select(Entity).where(Entity.verification_status != VerificationStatus.REJECTED)

        if not include_unverified:
            v_check = await db.execute(
                select(func.count(Entity.id)).where(
                    Entity.verification_status.in_([
                        VerificationStatus.VERIFIED,
                        VerificationStatus.MODIFIED,
                    ])
                )
            )
            has_verified = (v_check.scalar() or 0) > 0
            if has_verified:
                query = query.where(
                    Entity.verification_status.in_([
                        VerificationStatus.VERIFIED,
                        VerificationStatus.MODIFIED,
                    ])
                )

        if case_id:
            from app.models.document import Document
            query = query.join(Document, Entity.document_id == Document.id).where(
                Document.case_id == case_id
            )

        entities = (await db.execute(query)).scalars().all()
        created = 0
        for ent in entities:
            alias = (await db.execute(
                select(EntityAlias.id).where(EntityAlias.entity_id == ent.id)
            )).scalar_one_or_none()
            if not alias:
                await self.ensure_canonical_entity(db, ent)
                created += 1

        if created > 0:
            await db.flush()

        logger.info(f"Synchronized {created} canonical entities (include_unverified={include_unverified})")
        return created

