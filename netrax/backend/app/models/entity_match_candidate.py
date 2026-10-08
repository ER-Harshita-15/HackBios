"""
EntityMatchCandidate model — stores potential entity matches for human review.

Match scores represent record-linkage confidence, NOT criminality or suspicion.
Every candidate match requires investigator review before confirmation.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Enum, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MatchStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    REJECTED = "REJECTED"


class EntityMatchCandidate(Base):
    __tablename__ = "entity_match_candidates"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    entity_a_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    entity_b_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    match_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    matching_features: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[MatchStatus] = mapped_column(
        Enum(MatchStatus), default=MatchStatus.PENDING, nullable=False, index=True
    )
    canonical_entity_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("canonical_entities.id", ondelete="SET NULL"),
        nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    entity_a = relationship("Entity", foreign_keys=[entity_a_id])
    entity_b = relationship("Entity", foreign_keys=[entity_b_id])

    def __repr__(self):
        return f"<EntityMatchCandidate {self.entity_a_id} ↔ {self.entity_b_id} ({self.match_score:.0%}, {self.status.value})>"
