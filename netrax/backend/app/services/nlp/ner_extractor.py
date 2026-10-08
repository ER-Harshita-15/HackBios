"""
NER Entity Extractor — pretrained NLP model-based extraction.
Uses spaCy as the default implementation but is designed to be replaceable.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.services.extraction.regex_extractor import ExtractedEntity

logger = logging.getLogger(__name__)

# Mapping from spaCy entity labels to NETRA-X entity types
SPACY_TO_NETRAX = {
    "PERSON": "PERSON",
    "PER": "PERSON",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "FAC": "LOCATION",
    "ORG": "ORGANIZATION",
    "NORP": "ORGANIZATION",
    "DATE": "DATE",
    "TIME": "DATE",
    "MONEY": "ACCOUNT",
}


class BaseNERExtractor(ABC):
    """Abstract NER extractor — implement to swap NLP models."""

    @abstractmethod
    def extract(self, text: str, page_number: int = 1) -> list[ExtractedEntity]:
        """Extract entities from text using NER."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the NER model is loaded and available."""
        ...


class SpacyNERExtractor(BaseNERExtractor):
    """
    NER extractor using spaCy pretrained models.
    Focuses on: PERSON, LOCATION, ORGANIZATION, DATE.
    """

    CONTEXT_WINDOW = 80

    def __init__(self, model_name: str = "en_core_web_sm"):
        self._model_name = model_name
        self._nlp = None
        self._available = False
        self._load_model()

    def _load_model(self):
        """Load the spaCy model."""
        try:
            import spacy
            self._nlp = spacy.load(self._model_name)
            self._available = True
            logger.info(f"Loaded spaCy model: {self._model_name}")
        except Exception as e:
            logger.warning(f"Failed to load spaCy model '{self._model_name}': {e}")
            self._available = False

    def is_available(self) -> bool:
        return self._available

    def extract(self, text: str, page_number: int = 1) -> list[ExtractedEntity]:
        """Extract entities using spaCy NER."""
        if not self._available or not self._nlp:
            logger.warning("spaCy NER is not available, returning empty results")
            return []

        entities = []

        try:
            # Process text — limit to avoid memory issues with very long texts
            max_length = 100000
            processing_text = text[:max_length] if len(text) > max_length else text

            doc = self._nlp(processing_text)

            for ent in doc.ents:
                netrax_type = SPACY_TO_NETRAX.get(ent.label_)
                if netrax_type is None:
                    continue

                # Skip very short or very long entities
                value = ent.text.strip()
                if len(value) < 2 or len(value) > 200:
                    continue

                # Extract context
                context_start = max(0, ent.start_char - self.CONTEXT_WINDOW)
                context_end = min(len(text), ent.end_char + self.CONTEXT_WINDOW)
                context = text[context_start:context_end].strip()

                # Base confidence from spaCy (heuristic since spaCy doesn't expose per-entity confidence easily)
                # We use a reasonable default based on entity type
                confidence = self._estimate_confidence(ent, netrax_type)

                entities.append(ExtractedEntity(
                    entity_type=netrax_type,
                    value=value,
                    confidence=confidence,
                    method="NER",
                    start=ent.start_char,
                    end=ent.end_char,
                    context=context,
                ))

        except Exception as e:
            logger.error(f"spaCy NER extraction failed: {e}")

        logger.info(f"NER extracted {len(entities)} entities from page {page_number}")
        return entities

    def _estimate_confidence(self, ent, netrax_type: str) -> float:
        """
        Estimate confidence for a spaCy entity.
        spaCy doesn't natively expose per-entity confidence for its default pipeline,
        so we use heuristics based on entity type and length.
        """
        base_confidence = 0.80

        # Well-known entity types get higher base confidence
        if netrax_type == "PERSON":
            base_confidence = 0.85
            # Multi-word person names are more likely correct
            if " " in ent.text:
                base_confidence = 0.90
        elif netrax_type == "LOCATION":
            base_confidence = 0.82
        elif netrax_type == "ORGANIZATION":
            base_confidence = 0.78
        elif netrax_type == "DATE":
            base_confidence = 0.88

        return min(base_confidence, 0.95)


class NoOpNERExtractor(BaseNERExtractor):
    """No-op NER extractor when NLP model is unavailable."""

    def extract(self, text: str, page_number: int = 1) -> list[ExtractedEntity]:
        return []

    def is_available(self) -> bool:
        return False


def create_ner_extractor(model_name: str = "en_core_web_sm") -> BaseNERExtractor:
    """Factory function to create NER extractor."""
    extractor = SpacyNERExtractor(model_name=model_name)
    if not extractor.is_available():
        logger.warning("Falling back to NoOp NER extractor")
        return NoOpNERExtractor()
    return extractor
