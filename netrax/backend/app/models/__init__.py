"""NETRA-X Models Package — Phase 1 + Phase 2"""

# Phase 1 models
from app.models.case import Case
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.entity import Entity
from app.models.entity_mention import EntityMention

# Phase 2 models
from app.models.canonical_entity import CanonicalEntity, EntityAlias
from app.models.entity_match_candidate import EntityMatchCandidate
from app.models.relationship import Relationship
from app.models.audit_log import AuditLog

__all__ = [
    # Phase 1
    "Case", "Document", "DocumentPage", "Entity", "EntityMention",
    # Phase 2
    "CanonicalEntity", "EntityAlias", "EntityMatchCandidate",
    "Relationship", "AuditLog",
]
