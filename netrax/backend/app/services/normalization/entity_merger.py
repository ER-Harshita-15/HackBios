"""
Entity Merger — merges duplicate entities extracted by different methods.
When Regex, NER, and LLM all extract the same entity, they are merged
into a single entity with combined mentions.
"""

import logging
from dataclasses import dataclass, field

from app.services.extraction.regex_extractor import ExtractedEntity
from app.services.normalization.entity_normalizer import EntityNormalizationService

logger = logging.getLogger(__name__)


@dataclass
class MergedEntity:
    """An entity after merging duplicates from different extractors."""
    entity_type: str
    value: str
    normalized_value: str
    confidence: float
    extraction_method: str  # Primary method or "HYBRID"
    mentions: list[ExtractedEntity] = field(default_factory=list)


class EntityMerger:
    """
    Merges extraction results from multiple extractors (Regex, NER, LLM)
    into deduplicated entities with combined mentions.
    """

    def __init__(self, normalizer: EntityNormalizationService | None = None):
        self._normalizer = normalizer or EntityNormalizationService()

    def merge(self, all_entities: list[ExtractedEntity]) -> list[MergedEntity]:
        """
        Merge a list of extracted entities by normalized value and type.
        
        Args:
            all_entities: All entities from all extractors for a given page.
            
        Returns:
            Deduplicated list of MergedEntity objects.
        """
        # Group by (entity_type, normalized_value)
        groups: dict[tuple[str, str], list[ExtractedEntity]] = {}

        for entity in all_entities:
            normalized = self._normalizer.normalize(entity.entity_type, entity.value)
            key = (entity.entity_type, normalized)

            if key not in groups:
                groups[key] = []
            groups[key].append(entity)

        # Create merged entities
        merged = []
        for (entity_type, normalized_value), group in groups.items():
            # Pick the best value (original form from highest confidence extraction)
            best = max(group, key=lambda e: e.confidence)

            # Determine extraction method
            methods = set(e.method for e in group)
            if len(methods) > 1:
                method = "HYBRID"
            else:
                method = methods.pop()

            # Confidence strategy:
            # - If multiple methods agree, boost confidence slightly
            # - Use the highest individual confidence as base
            # - Cap at 0.99
            max_confidence = max(e.confidence for e in group)
            if len(methods) > 1:
                # Multiple methods agreeing boosts confidence
                confidence = min(max_confidence + 0.03, 0.99)
            else:
                confidence = max_confidence

            merged.append(MergedEntity(
                entity_type=entity_type,
                value=best.value,
                normalized_value=normalized_value,
                confidence=round(confidence, 3),
                extraction_method=method,
                mentions=group,  # Keep all mentions for traceability
            ))

        logger.info(f"Merged {len(all_entities)} extractions into {len(merged)} unique entities")
        return merged
