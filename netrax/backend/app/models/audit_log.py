"""
AuditLog model — tracks all Phase 2 entity resolution and graph operations.

Logs are for investigative accountability, not surveillance.
"""

import uuid
import enum
from datetime import datetime, timezone

from sqlalchemy import String, Text, Enum, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AuditAction(str, enum.Enum):
    ENTITY_MATCH_SUGGESTED = "ENTITY_MATCH_SUGGESTED"
    ENTITY_MATCH_CONFIRMED = "ENTITY_MATCH_CONFIRMED"
    ENTITY_MATCH_REJECTED = "ENTITY_MATCH_REJECTED"
    CANONICAL_ENTITY_CREATED = "CANONICAL_ENTITY_CREATED"
    CANONICAL_ENTITY_UPDATED = "CANONICAL_ENTITY_UPDATED"
    RELATIONSHIP_CREATED = "RELATIONSHIP_CREATED"
    RELATIONSHIP_VERIFIED = "RELATIONSHIP_VERIFIED"
    RELATIONSHIP_REJECTED = "RELATIONSHIP_REJECTED"
    GRAPH_BUILT = "GRAPH_BUILT"
    GRAPH_REBUILT = "GRAPH_REBUILT"
    GRAPH_VALIDATED = "GRAPH_VALIDATED"


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    user: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction), nullable=False, index=True
    )
    resource_type: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    previous_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    def __repr__(self):
        return f"<AuditLog {self.action.value} on {self.resource_type}:{self.resource_id}>"
