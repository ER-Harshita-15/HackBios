"""
Document Processing Pipeline — orchestrates the entire Phase 1 extraction flow.

Pipeline:
1. Validate file
2. Identify document type  
3. Extract text (page-by-page)
4. OCR if required
5. Clean text
6. Run regex extraction
7. Run NER extraction
8. Run optional LLM extraction
9. Merge extraction results
10. Normalize entities
11. Save entities + mentions
12. Set status READY_FOR_REVIEW
"""

import logging
import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, ProcessingStatus
from app.models.document_page import DocumentPage
from app.models.entity import Entity, EntityType, ExtractionMethod, VerificationStatus
from app.models.entity_mention import EntityMention
from app.services.extraction.text_extractor import TextExtractorFactory
from app.services.extraction.ocr_service import BaseOCRService, create_ocr_service
from app.services.extraction.regex_extractor import RegexEntityExtractor, ExtractedEntity
from app.services.nlp.ner_extractor import BaseNERExtractor, create_ner_extractor
from app.services.nlp.llm_extractor import BaseLLMExtractionService, create_llm_extractor
from app.services.normalization.text_cleaning import TextCleaningService
from app.services.normalization.entity_normalizer import EntityNormalizationService
from app.services.normalization.entity_merger import EntityMerger
from app.config import settings

logger = logging.getLogger(__name__)


class DocumentProcessingPipeline:
    """
    Orchestrates the complete document processing pipeline.
    Modular design allows swapping any component.
    """

    def __init__(
        self,
        ocr_service: BaseOCRService | None = None,
        ner_extractor: BaseNERExtractor | None = None,
        llm_extractor: BaseLLMExtractionService | None = None,
        text_cleaner: TextCleaningService | None = None,
        entity_normalizer: EntityNormalizationService | None = None,
        entity_merger: EntityMerger | None = None,
    ):
        self.ocr_service = ocr_service or create_ocr_service(
            enabled=settings.OCR_ENABLED,
            tesseract_cmd=settings.TESSERACT_CMD,
        )
        self.ner_extractor = ner_extractor or create_ner_extractor(
            model_name=settings.NER_MODEL
        )
        self.llm_extractor = llm_extractor or create_llm_extractor(
            enabled=settings.LLM_ENABLED,
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            provider=settings.LLM_PROVIDER,
        )
        self.text_cleaner = text_cleaner or TextCleaningService()
        self.entity_normalizer = entity_normalizer or EntityNormalizationService()
        self.entity_merger = entity_merger or EntityMerger(self.entity_normalizer)
        self.regex_extractor = RegexEntityExtractor()

    async def process(self, document: Document, db: AsyncSession) -> None:
        """
        Process a document through the complete pipeline.
        
        Args:
            document: The Document model to process.
            db: Database session.
        """
        try:
            logger.info(f"Starting pipeline for document {document.id}: {document.original_filename}")

            # Step 1: Update status to PROCESSING
            document.processing_status = ProcessingStatus.PROCESSING
            await db.flush()

            # Step 2: Extract text
            await self._extract_text(document, db)

            # Step 3: Update status to TEXT_EXTRACTED
            document.processing_status = ProcessingStatus.TEXT_EXTRACTED
            await db.flush()

            # Step 4: Extract entities
            document.processing_status = ProcessingStatus.ENTITY_EXTRACTION
            await db.flush()

            await self._extract_entities(document, db)

            # Step 5: Set READY_FOR_REVIEW
            document.processing_status = ProcessingStatus.READY_FOR_REVIEW
            document.processing_error = None
            await db.commit()

            logger.info(f"Pipeline completed for document {document.id}")

        except Exception as e:
            logger.error(f"Pipeline failed for document {document.id}: {e}", exc_info=True)
            document.processing_status = ProcessingStatus.FAILED
            document.processing_error = str(e)
            await db.commit()

    async def _extract_text(self, document: Document, db: AsyncSession) -> None:
        """Extract text from document using appropriate extractor + OCR fallback."""
        logger.info(f"Extracting text from {document.original_filename} (type: {document.mime_type})")

        extractor = TextExtractorFactory.get_extractor(document.mime_type)
        result = extractor.extract(document.storage_path)

        if result.errors and not result.pages:
            raise ValueError(f"Text extraction failed: {'; '.join(result.errors)}")

        document.total_pages = result.total_pages

        for page_data in result.pages:
            raw_text = page_data.raw_text
            ocr_applied = False

            # OCR fallback for pages with no text
            if not raw_text.strip() and document.mime_type == "application/pdf":
                if self.ocr_service.is_available():
                    logger.info(f"Applying OCR to page {page_data.page_number}")
                    ocr_result = self.ocr_service.extract_text_from_pdf_page(
                        document.storage_path, page_data.page_number - 1  # 0-indexed for fitz
                    )
                    if ocr_result.success and ocr_result.text.strip():
                        raw_text = ocr_result.text
                        ocr_applied = True

            # Clean text
            cleaned_text = self.text_cleaner.clean(raw_text) if raw_text else ""

            # Save page
            page = DocumentPage(
                document_id=document.id,
                page_number=page_data.page_number,
                raw_text=raw_text,
                cleaned_text=cleaned_text,
                ocr_applied=ocr_applied,
            )
            db.add(page)

        await db.flush()
        logger.info(f"Extracted {len(result.pages)} pages from {document.original_filename}")

    async def _extract_entities(self, document: Document, db: AsyncSession) -> None:
        """Run all entity extractors on each page and merge results."""
        logger.info(f"Extracting entities from {document.original_filename}")

        # Reload pages
        from sqlalchemy import select
        pages_result = await db.execute(
            select(DocumentPage)
            .where(DocumentPage.document_id == document.id)
            .order_by(DocumentPage.page_number)
        )
        pages = pages_result.scalars().all()

        all_document_entities: list[tuple] = []  # (MergedEntity, page)

        for page in pages:
            text = page.cleaned_text or page.raw_text or ""
            if not text.strip():
                continue

            # Run all extractors on this page
            page_entities: list[ExtractedEntity] = []

            # 1. Regex extraction
            regex_results = self.regex_extractor.extract(text, page.page_number)
            page_entities.extend(regex_results)

            # 2. NER extraction
            if self.ner_extractor.is_available():
                ner_results = self.ner_extractor.extract(text, page.page_number)
                page_entities.extend(ner_results)

            # 3. Optional LLM extraction
            if self.llm_extractor.is_available():
                try:
                    llm_results = await self.llm_extractor.extract_entities(text, page.page_number)
                    page_entities.extend(llm_results)
                except Exception as e:
                    logger.warning(f"LLM extraction failed for page {page.page_number}: {e}")

            # Merge entities from this page
            merged = self.entity_merger.merge(page_entities)

            for merged_entity in merged:
                all_document_entities.append((merged_entity, page))

        # Now deduplicate across pages — same entity on different pages should still be one entity
        # but with multiple mentions
        entity_map: dict[tuple[str, str], tuple] = {}  # (type, normalized) -> (Entity data, mentions)

        for merged_entity, page in all_document_entities:
            key = (merged_entity.entity_type, merged_entity.normalized_value)

            if key not in entity_map:
                entity_map[key] = {
                    "entity_type": merged_entity.entity_type,
                    "value": merged_entity.value,
                    "normalized_value": merged_entity.normalized_value,
                    "confidence": merged_entity.confidence,
                    "extraction_method": merged_entity.extraction_method,
                    "mentions": [],
                }

            # Update confidence if higher
            if merged_entity.confidence > entity_map[key]["confidence"]:
                entity_map[key]["confidence"] = merged_entity.confidence
                entity_map[key]["value"] = merged_entity.value

            # Add mentions from this page
            for mention in merged_entity.mentions:
                entity_map[key]["mentions"].append({
                    "page": page,
                    "mention": mention,
                })

        # Save to database
        for entity_data in entity_map.values():
            try:
                entity_type_enum = EntityType(entity_data["entity_type"])
            except ValueError:
                logger.warning(f"Unknown entity type: {entity_data['entity_type']}")
                continue

            try:
                method_enum = ExtractionMethod(entity_data["extraction_method"])
            except ValueError:
                method_enum = ExtractionMethod.REGEX

            entity = Entity(
                document_id=document.id,
                entity_type=entity_type_enum,
                value=entity_data["value"],
                normalized_value=entity_data["normalized_value"],
                confidence=entity_data["confidence"],
                extraction_method=method_enum,
                verification_status=VerificationStatus.UNVERIFIED,
            )
            db.add(entity)
            await db.flush()  # Get entity ID

            # Save mentions
            for mention_data in entity_data["mentions"]:
                page = mention_data["page"]
                mention = mention_data["mention"]

                entity_mention = EntityMention(
                    entity_id=entity.id,
                    document_id=document.id,
                    document_page_id=page.id,
                    page_number=page.page_number,
                    text_start=mention.start,
                    text_end=mention.end,
                    context=mention.context,
                    confidence=mention.confidence,
                    extraction_method=mention.method,
                )
                db.add(entity_mention)

        await db.flush()
        logger.info(f"Saved {len(entity_map)} entities with mentions for document {document.id}")


# Singleton pipeline instance (initialized lazily)
_pipeline_instance: DocumentProcessingPipeline | None = None


def get_pipeline() -> DocumentProcessingPipeline:
    """Get or create the singleton pipeline instance."""
    global _pipeline_instance
    if _pipeline_instance is None:
        _pipeline_instance = DocumentProcessingPipeline()
    return _pipeline_instance
