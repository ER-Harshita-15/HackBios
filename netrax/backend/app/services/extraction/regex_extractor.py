"""
Regex Entity Extractor — rule-based extraction for structured entity types.
Each regex pattern returns entities with high extraction confidence.
Confidence represents extraction certainty, NOT truthfulness.
"""

import re
import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class ExtractedEntity:
    """A single extracted entity with source information."""
    entity_type: str
    value: str
    confidence: float
    method: str
    start: int  # Character offset in text
    end: int    # Character offset in text
    context: str = ""  # Surrounding text for evidence


class RegexEntityExtractor:
    """
    Rule-based entity extraction using configurable regex patterns.
    Designed for highly structured entities: phone, email, vehicle, FIR, IMEI, account.
    """

    CONTEXT_WINDOW = 80  # Characters of surrounding context to capture

    def __init__(self):
        self._patterns = self._build_default_patterns()

    def _build_default_patterns(self) -> dict[str, list[dict]]:
        """Build default regex patterns for Indian-style investigation documents."""
        return {
            "PHONE": [
                {
                    "pattern": re.compile(
                        r'(?<!\d)(?:\+91[\s\-]?)?(?:0)?([6-9]\d{9})(?!\d)',
                        re.MULTILINE
                    ),
                    "confidence": 0.95,
                    "group": 0,
                    "description": "Indian 10-digit mobile number",
                },
            ],
            "EMAIL": [
                {
                    "pattern": re.compile(
                        r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}',
                        re.IGNORECASE
                    ),
                    "confidence": 0.97,
                    "group": 0,
                    "description": "Email address",
                },
            ],
            "VEHICLE": [
                {
                    "pattern": re.compile(
                        r'(?<![A-Z0-9])[A-Z]{2}[\s\-]?\d{1,2}[\s\-]?[A-Z]{1,3}[\s\-]?\d{4}(?![A-Z0-9])',
                        re.IGNORECASE
                    ),
                    "confidence": 0.92,
                    "group": 0,
                    "description": "Indian vehicle registration number",
                },
            ],
            "CASE": [
                {
                    "pattern": re.compile(
                        r'(?:FIR|Case|CR|TXN)[\s\-\.]*(?:No\.?|Number|#)?[\s\-:]*([A-Z]*[\-/]?\d{1,6}[/\-]?\d{0,4})',
                        re.IGNORECASE
                    ),
                    "confidence": 0.90,
                    "group": 0,
                    "description": "FIR, Case, or Transaction number",
                },
            ],
            "ACCOUNT": [
                {
                    "pattern": re.compile(
                        r'(?:A/C|Acc(?:ount)?|Account)[\s\-\.]*(?:No\.?|Number|#)?[\s\-:]*(\d{9,18})',
                        re.IGNORECASE
                    ),
                    "confidence": 0.88,
                    "group": 0,
                    "description": "Bank account number",
                },
                {
                    "pattern": re.compile(
                        r'(?:from_account|to_account)[\s\-\.:=,]*(\d{9,18})',
                        re.IGNORECASE
                    ),
                    "confidence": 0.85,
                    "group": 0,
                    "description": "Bank account in tabular data",
                },
            ],
            "DEVICE": [
                {
                    "pattern": re.compile(
                        r'(?:IMEI)[\s\-:]*(\d{15})',
                        re.IGNORECASE
                    ),
                    "confidence": 0.94,
                    "group": 0,
                    "description": "IMEI number",
                },
                {
                    "pattern": re.compile(
                        r'(?<!\d)(\d{15})(?!\d)',
                    ),
                    "confidence": 0.60,
                    "group": 0,
                    "description": "Possible IMEI (15-digit number without context)",
                },
            ],
            "DATE": [
                {
                    "pattern": re.compile(
                        r'\b(\d{1,2}[/\-\.]\d{1,2}[/\-\.]\d{2,4})\b'
                    ),
                    "confidence": 0.85,
                    "group": 0,
                    "description": "Date in DD/MM/YYYY or similar format",
                },
                {
                    "pattern": re.compile(
                        r'\b(\d{4}[/\-\.]\d{1,2}[/\-\.]\d{1,2})\b'
                    ),
                    "confidence": 0.85,
                    "group": 0,
                    "description": "Date in YYYY-MM-DD format",
                },
            ],
        }

    def extract(self, text: str, page_number: int = 1) -> list[ExtractedEntity]:
        """
        Extract entities from text using regex patterns.

        Args:
            text: The text to extract entities from.
            page_number: Page number for evidence context.

        Returns:
            List of ExtractedEntity objects.
        """
        entities = []

        for entity_type, patterns in self._patterns.items():
            for pattern_config in patterns:
                pattern = pattern_config["pattern"]
                confidence = pattern_config["confidence"]
                group = pattern_config.get("group", 0)

                for match in pattern.finditer(text):
                    value = match.group(group).strip()
                    if not value:
                        continue

                    start = match.start(group)
                    end = match.end(group)

                    # Extract surrounding context
                    context_start = max(0, start - self.CONTEXT_WINDOW)
                    context_end = min(len(text), end + self.CONTEXT_WINDOW)
                    context = text[context_start:context_end].strip()

                    entities.append(ExtractedEntity(
                        entity_type=entity_type,
                        value=value,
                        confidence=confidence,
                        method="REGEX",
                        start=start,
                        end=end,
                        context=context,
                    ))

        logger.info(f"Regex extracted {len(entities)} entities from page {page_number}")
        return entities

    def add_pattern(self, entity_type: str, pattern: str, confidence: float = 0.85,
                    group: int = 0, description: str = ""):
        """Add a custom regex pattern for extraction."""
        if entity_type not in self._patterns:
            self._patterns[entity_type] = []
        self._patterns[entity_type].append({
            "pattern": re.compile(pattern),
            "confidence": confidence,
            "group": group,
            "description": description,
        })
