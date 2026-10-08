"""
Relationship model — evidence-backed relationships between canonical entities.

Every relationship must have provenance tracing back to source evidence.
Relationships describe what the evidence shows, NOT guilt or criminality.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Enum, DateTime, Float, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class RelationshipType(str, enum.Enum):
    USES = "USES"
    HAS_ACCOUNT = "HAS_ACCOUNT"
    OWNS = "OWNS"
    LOCATED_AT = "LOCATED_AT"
    INVOLVED_IN = "INVOLVED_IN"
    MENTIONED_IN = "MENTIONED_IN"
    WORKS_FOR = "WORKS_FOR"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    CALLED = "CALLED"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    PARTICIPATED_IN = "PARTICIPATED_IN"
    CAPTURED_BY = "CAPTURED_BY"
    HAS_EVIDENCE = "HAS_EVIDENCE"
    SAME_AS = "SAME_AS"


class RelationshipVerificationStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"


class Relationship(Base):
    """An evidence-backed relationship between two entities."""
    __tablename__ = "relationships"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    relationship_type: Mapped[RelationshipType] = mapped_column(
        Enum(RelationshipType), nullable=False, index=True
    )
    source_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    target_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    # Provenance
    source_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    source_page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_record_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    extraction_method: Mapped[str] = mapped_column(String(50), nullable=False, default="AUTO")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    verification_status: Mapped[RelationshipVerificationStatus] = mapped_column(
        Enum(RelationshipVerificationStatus),
        default=RelationshipVerificationStatus.UNVERIFIED,
        nullable=False, index=True
    )
    # Properties (JSON-encoded metadata like timestamp, duration, amount, etc.)
    properties_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("cases.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ORM relationships
    source_entity = relationship("CanonicalEntity", foreign_keys=[source_entity_id])
    target_entity = relationship("CanonicalEntity", foreign_keys=[target_entity_id])
    source_document = relationship("Document", foreign_keys=[source_document_id])

    def __repr__(self):
        return (
            f"<Relationship {self.source_entity_id} "
            f"-[{self.relationship_type.value}]-> "
            f"{self.target_entity_id}>"
        )
