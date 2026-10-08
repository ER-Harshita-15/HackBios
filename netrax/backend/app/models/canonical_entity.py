"""
CanonicalEntity & EntityAlias models — Phase 2 Entity Resolution.

A CanonicalEntity is the resolved, deduplicated representation of one real-world entity.
EntityAlias links individual Phase 1 Entity records back to their canonical form.

This does NOT represent guilt or criminality — only record linkage.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Enum, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CanonicalEntityStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    MERGED = "MERGED"
    REJECTED = "REJECTED"


class CanonicalEntity(Base):
    __tablename__ = "canonical_entities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    entity_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    canonical_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    normalized_name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    status: Mapped[CanonicalEntityStatus] = mapped_column(
        Enum(CanonicalEntityStatus), default=CanonicalEntityStatus.ACTIVE, nullable=False
    )
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    aliases = relationship("EntityAlias", back_populates="canonical_entity", lazy="selectin",
                           cascade="all, delete-orphan")

    def __repr__(self):
        return f"<CanonicalEntity {self.entity_type}: {self.canonical_name} ({self.status.value})>"


class EntityAlias(Base):
    __tablename__ = "entity_aliases"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    canonical_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("canonical_entities.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False, index=True, unique=True
    )
    alias_value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    source_document_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    canonical_entity = relationship("CanonicalEntity", back_populates="aliases")
    entity = relationship("Entity", foreign_keys=[entity_id])

    def __repr__(self):
        return f"<EntityAlias '{self.alias_value}' → CE:{self.canonical_entity_id}>"
