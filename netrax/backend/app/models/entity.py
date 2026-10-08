"""
Entity model — stores extracted and normalized entities with verification status.
Confidence represents extraction confidence, NOT guilt or criminality.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Enum, DateTime, Float, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class EntityType(str, enum.Enum):
    PERSON = "PERSON"
    PHONE = "PHONE"
    LOCATION = "LOCATION"
    ORGANIZATION = "ORGANIZATION"
    ACCOUNT = "ACCOUNT"
    VEHICLE = "VEHICLE"
    CASE = "CASE"
    DATE = "DATE"
    DEVICE = "DEVICE"
    EMAIL = "EMAIL"


class ExtractionMethod(str, enum.Enum):
    REGEX = "REGEX"
    NER = "NER"
    LLM = "LLM"
    MANUAL = "MANUAL"
    HYBRID = "HYBRID"


class VerificationStatus(str, enum.Enum):
    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REJECTED = "REJECTED"
    MODIFIED = "MODIFIED"


class Entity(Base):
    __tablename__ = "entities"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    document_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    entity_type: Mapped[EntityType] = mapped_column(
        Enum(EntityType), nullable=False, index=True
    )
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    normalized_value: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    extraction_method: Mapped[ExtractionMethod] = mapped_column(
        Enum(ExtractionMethod), nullable=False
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus), default=VerificationStatus.UNVERIFIED, nullable=False
    )
    verified_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    document = relationship("Document", back_populates="entities")
    mentions = relationship("EntityMention", back_populates="entity", lazy="selectin",
                            cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Entity {self.entity_type.value}: {self.value} ({self.confidence:.0%})>"
