"""
LLM Entity Extractor — optional structured extraction using LLM APIs.
The application works without this; it is only used when LLM_ENABLED=true and API key is configured.
"""

import json
import logging
from abc import ABC, abstractmethod

from app.services.extraction.regex_extractor import ExtractedEntity

logger = logging.getLogger(__name__)


class BaseLLMExtractionService(ABC):
    """Abstract LLM extraction service — implement to add any LLM provider."""

    @abstractmethod
    async def extract_entities(self, text: str, page_number: int = 1) -> list[ExtractedEntity]:
        """Extract entities from text using an LLM."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the LLM service is configured and available."""
        ...


class OpenAILLMExtractor(BaseLLMExtractionService):
    """
    LLM extraction using OpenAI-compatible APIs.
    Sends text with a structured extraction prompt and parses JSON response.
    """

    CONTEXT_WINDOW = 80
    ENTITY_TYPES = ["PERSON", "PHONE", "LOCATION", "ORGANIZATION", "ACCOUNT",
                    "VEHICLE", "CASE", "DATE", "DEVICE", "EMAIL"]

    SYSTEM_PROMPT = """You are an entity extraction system for criminal investigation documents.
Extract ONLY entities that are explicitly mentioned in the text.
Do NOT invent or hallucinate entities.
Do NOT make assumptions about entities not present in the text.

Return a JSON object with the following structure:
{
  "entities": [
    {
      "type": "<ENTITY_TYPE>",
      "value": "<exact text from document>",
      "confidence": <float between 0 and 1>,
      "start": <character offset>,
      "end": <character offset>
    }
  ]
}

Valid entity types: PERSON, PHONE, LOCATION, ORGANIZATION, ACCOUNT, VEHICLE, CASE, DATE, DEVICE, EMAIL

Rules:
- Only extract entities that appear verbatim in the text
- confidence should reflect how certain you are about the entity type classification
- Provide exact character offsets for start and end positions
- Do not add any entities not found in the source text
"""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o-mini",
                 provider: str = "openai"):
        self._api_key = api_key
        self._model = model
        self._provider = provider
        self._available = bool(api_key)
        if self._available:
            logger.info(f"LLM extraction enabled with provider: {provider}, model: {model}")
        else:
            logger.info("LLM extraction disabled — no API key configured")

    def is_available(self) -> bool:
        return self._available

    async def extract_entities(self, text: str, page_number: int = 1) -> list[ExtractedEntity]:
        """Extract entities using LLM structured extraction."""
        if not self._available:
            return []

        try:
            import httpx

            # Truncate text for LLM context window
            max_chars = 8000
            processing_text = text[:max_chars] if len(text) > max_chars else text

            if self._provider == "openai":
                response = await self._call_openai(processing_text)
            else:
                logger.warning(f"Unsupported LLM provider: {self._provider}")
                return []

            return self._parse_response(response, text, page_number)

        except Exception as e:
            logger.error(f"LLM extraction failed: {e}")
            return []

    async def _call_openai(self, text: str) -> dict:
        """Call OpenAI-compatible API."""
        import httpx

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {"role": "system", "content": self.SYSTEM_PROMPT},
                        {"role": "user", "content": f"Extract entities from this text:\n\n{text}"},
                    ],
                    "temperature": 0.1,
                    "response_format": {"type": "json_object"},
                },
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return json.loads(content)

    def _parse_response(self, response: dict, original_text: str,
                        page_number: int) -> list[ExtractedEntity]:
        """Parse LLM JSON response into ExtractedEntity objects."""
        entities = []
        raw_entities = response.get("entities", [])

        for raw in raw_entities:
            entity_type = raw.get("type", "").upper()
            value = raw.get("value", "").strip()
            confidence = float(raw.get("confidence", 0.7))

            if not value or entity_type not in self.ENTITY_TYPES:
                continue

            # Verify entity actually exists in text (prevent hallucination)
            start = raw.get("start")
            end = raw.get("end")

            if start is None or end is None:
                # Try to find the value in text
                idx = original_text.find(value)
                if idx == -1:
                    logger.warning(f"LLM entity '{value}' not found in source text — skipping")
                    continue
                start = idx
                end = idx + len(value)

            # Extract context
            context_start = max(0, start - self.CONTEXT_WINDOW)
            context_end = min(len(original_text), end + self.CONTEXT_WINDOW)
            context = original_text[context_start:context_end].strip()

            # Cap LLM confidence slightly lower than regex for deterministic patterns
            confidence = min(confidence, 0.93)

            entities.append(ExtractedEntity(
                entity_type=entity_type,
                value=value,
                confidence=confidence,
                method="LLM",
                start=start,
                end=end,
                context=context,
            ))

        logger.info(f"LLM extracted {len(entities)} entities from page {page_number}")
        return entities


class NoOpLLMExtractor(BaseLLMExtractionService):
    """No-op LLM extractor when LLM is disabled."""

    async def extract_entities(self, text: str, page_number: int = 1) -> list[ExtractedEntity]:
        return []

    def is_available(self) -> bool:
        return False


def create_llm_extractor(enabled: bool = False, api_key: str | None = None,
                         model: str = "gpt-4o-mini",
                         provider: str = "openai") -> BaseLLMExtractionService:
    """Factory function to create LLM extractor."""
    if not enabled or not api_key:
        logger.info("LLM extraction disabled")
        return NoOpLLMExtractor()
    return OpenAILLMExtractor(api_key=api_key, model=model, provider=provider)
