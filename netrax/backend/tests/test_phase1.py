"""
Unit tests for NETRA-X Phase 1 extraction and normalization services.
Uses synthetic data — no real personal or criminal information.
"""

import pytest
import os
import tempfile
from pathlib import Path

from app.services.extraction.regex_extractor import RegexEntityExtractor
from app.services.normalization.entity_normalizer import EntityNormalizationService
from app.services.normalization.entity_merger import EntityMerger
from app.services.normalization.text_cleaning import TextCleaningService
from app.services.extraction.regex_extractor import ExtractedEntity


# ─── Regex Extraction Tests ───────────────────────────────────────────────

class TestRegexExtraction:
    """Test regex-based entity extraction."""

    def setup_method(self):
        self.extractor = RegexEntityExtractor()

    def test_phone_extraction(self):
        text = "Contact Rahul at 9876543210 or call 8877665544 for details."
        entities = self.extractor.extract(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) == 2
        phone_values = {e.value for e in phones}
        assert "9876543210" in phone_values
        assert "8877665544" in phone_values

    def test_phone_with_country_code(self):
        text = "Call +91 9876543210 for information."
        entities = self.extractor.extract(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) >= 1

    def test_phone_confidence(self):
        text = "Number: 9876543210"
        entities = self.extractor.extract(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) == 1
        assert phones[0].confidence >= 0.90

    def test_email_extraction(self):
        text = "Send report to rahul.sharma@email.com and cc neha@mail.co.in"
        entities = self.extractor.extract(text)
        emails = [e for e in entities if e.entity_type == "EMAIL"]
        assert len(emails) == 2
        email_values = {e.value for e in emails}
        assert "rahul.sharma@email.com" in email_values
        assert "neha@mail.co.in" in email_values

    def test_email_confidence(self):
        text = "Email: test@example.com"
        entities = self.extractor.extract(text)
        emails = [e for e in entities if e.entity_type == "EMAIL"]
        assert len(emails) == 1
        assert emails[0].confidence >= 0.95

    def test_vehicle_extraction(self):
        text = "Vehicle bearing registration CG10AB1234 was spotted near the scene."
        entities = self.extractor.extract(text)
        vehicles = [e for e in entities if e.entity_type == "VEHICLE"]
        assert len(vehicles) >= 1
        assert any("CG10AB1234" in v.value.replace(" ", "").replace("-", "").upper()
                    for v in vehicles)

    def test_case_fir_extraction(self):
        text = "FIR Number: NX-001/2026 was registered at Central Station."
        entities = self.extractor.extract(text)
        cases = [e for e in entities if e.entity_type == "CASE"]
        assert len(cases) >= 1

    def test_device_imei_extraction(self):
        text = "IMEI: 123456789012345 was recovered from the device."
        entities = self.extractor.extract(text)
        devices = [e for e in entities if e.entity_type == "DEVICE"]
        assert len(devices) >= 1
        assert any("123456789012345" in d.value for d in devices)

    def test_date_extraction(self):
        text = "The incident occurred on 12/08/2026 at approximately 14:30."
        entities = self.extractor.extract(text)
        dates = [e for e in entities if e.entity_type == "DATE"]
        assert len(dates) >= 1

    def test_context_captured(self):
        text = "The suspect Rahul Sharma contacted someone at 9876543210 near Station Road."
        entities = self.extractor.extract(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) == 1
        assert phones[0].context  # Context should not be empty
        assert "9876543210" in phones[0].context

    def test_start_end_positions(self):
        text = "Phone: 9876543210"
        entities = self.extractor.extract(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) == 1
        assert phones[0].start >= 0
        assert phones[0].end > phones[0].start
        assert text[phones[0].start:phones[0].end].strip().replace("+91 ", "").replace("+91", "") in "9876543210"

    def test_no_false_positives_short_numbers(self):
        text = "There were 12345 items in the warehouse."
        entities = self.extractor.extract(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) == 0  # 5-digit number should not be a phone

    def test_empty_text(self):
        entities = self.extractor.extract("")
        assert len(entities) == 0

    def test_method_is_regex(self):
        text = "Call 9876543210"
        entities = self.extractor.extract(text)
        for e in entities:
            assert e.method == "REGEX"


# ─── Normalization Tests ──────────────────────────────────────────────────

class TestEntityNormalization:
    """Test entity value normalization."""

    def setup_method(self):
        self.normalizer = EntityNormalizationService()

    def test_person_normalization_case(self):
        assert self.normalizer.normalize("PERSON", "Rahul Sharma") == "rahul sharma"
        assert self.normalizer.normalize("PERSON", "RAHUL SHARMA") == "rahul sharma"
        assert self.normalizer.normalize("PERSON", "rahul sharma") == "rahul sharma"

    def test_person_normalization_whitespace(self):
        assert self.normalizer.normalize("PERSON", "rahul  sharma") == "rahul sharma"
        assert self.normalizer.normalize("PERSON", "  Rahul   Sharma  ") == "rahul sharma"

    def test_person_normalization_titles(self):
        assert self.normalizer.normalize("PERSON", "Mr. Rahul Sharma") == "rahul sharma"
        assert self.normalizer.normalize("PERSON", "Shri Rahul Sharma") == "rahul sharma"

    def test_phone_normalization(self):
        assert self.normalizer.normalize("PHONE", "9876543210") == "9876543210"
        assert self.normalizer.normalize("PHONE", "+91 9876543210") == "9876543210"
        assert self.normalizer.normalize("PHONE", "+919876543210") == "9876543210"
        assert self.normalizer.normalize("PHONE", "09876543210") == "9876543210"

    def test_email_normalization(self):
        assert self.normalizer.normalize("EMAIL", "Test@Example.COM") == "test@example.com"
        assert self.normalizer.normalize("EMAIL", "  user@mail.com  ") == "user@mail.com"

    def test_vehicle_normalization(self):
        assert self.normalizer.normalize("VEHICLE", "CG 10 AB 1234") == "CG10AB1234"
        assert self.normalizer.normalize("VEHICLE", "cg-10-ab-1234") == "CG10AB1234"

    def test_device_normalization(self):
        assert self.normalizer.normalize("DEVICE", "IMEI: 123456789012345") == "123456789012345"

    def test_account_normalization(self):
        assert self.normalizer.normalize("ACCOUNT", "Acc: 1234567890123") == "1234567890123"


# ─── Entity Merger Tests ──────────────────────────────────────────────────

class TestEntityMerger:
    """Test merging of duplicate entities from different extractors."""

    def setup_method(self):
        self.merger = EntityMerger()

    def test_merge_same_phone_from_regex_and_ner(self):
        entities = [
            ExtractedEntity("PHONE", "9876543210", 0.95, "REGEX", 10, 20, "...9876543210..."),
            ExtractedEntity("PHONE", "9876543210", 0.80, "NER", 10, 20, "...9876543210..."),
        ]
        merged = self.merger.merge(entities)
        assert len(merged) == 1
        assert merged[0].entity_type == "PHONE"
        assert merged[0].extraction_method == "HYBRID"
        assert merged[0].confidence > 0.95  # Boosted by multi-method agreement

    def test_merge_same_person_different_case(self):
        entities = [
            ExtractedEntity("PERSON", "Rahul Sharma", 0.90, "NER", 10, 22, "..."),
            ExtractedEntity("PERSON", "RAHUL SHARMA", 0.85, "LLM", 10, 22, "..."),
        ]
        merged = self.merger.merge(entities)
        assert len(merged) == 1
        assert merged[0].normalized_value == "rahul sharma"

    def test_no_merge_different_types(self):
        entities = [
            ExtractedEntity("PERSON", "Station Road", 0.60, "NER", 10, 22, "..."),
            ExtractedEntity("LOCATION", "Station Road", 0.85, "NER", 10, 22, "..."),
        ]
        merged = self.merger.merge(entities)
        assert len(merged) == 2

    def test_merge_preserves_all_mentions(self):
        entities = [
            ExtractedEntity("PHONE", "9876543210", 0.95, "REGEX", 10, 20, "mention1"),
            ExtractedEntity("PHONE", "9876543210", 0.80, "NER", 50, 60, "mention2"),
        ]
        merged = self.merger.merge(entities)
        assert len(merged) == 1
        assert len(merged[0].mentions) == 2

    def test_empty_input(self):
        merged = self.merger.merge([])
        assert len(merged) == 0

    def test_single_entity_no_merge_needed(self):
        entities = [
            ExtractedEntity("EMAIL", "test@example.com", 0.97, "REGEX", 5, 21, "..."),
        ]
        merged = self.merger.merge(entities)
        assert len(merged) == 1
        assert merged[0].extraction_method == "REGEX"


# ─── Text Cleaning Tests ──────────────────────────────────────────────────

class TestTextCleaning:
    """Test text cleaning service."""

    def setup_method(self):
        self.cleaner = TextCleaningService()

    def test_collapse_whitespace(self):
        text = "Hello    world   test"
        cleaned = self.cleaner.clean(text)
        assert "    " not in cleaned
        assert "Hello world test" == cleaned

    def test_normalize_line_breaks(self):
        text = "Line 1\r\nLine 2\rLine 3\nLine 4"
        cleaned = self.cleaner.clean(text)
        assert "\r" not in cleaned

    def test_remove_excessive_blank_lines(self):
        text = "Para 1\n\n\n\n\n\nPara 2"
        cleaned = self.cleaner.clean(text)
        assert "\n\n\n" not in cleaned

    def test_preserve_paragraphs(self):
        text = "Paragraph one.\n\nParagraph two."
        cleaned = self.cleaner.clean(text)
        assert "Paragraph one." in cleaned
        assert "Paragraph two." in cleaned

    def test_empty_text(self):
        assert self.cleaner.clean("") == ""
        assert self.cleaner.clean(None) == ""

    def test_unicode_normalization(self):
        text = "Hello\xa0World"  # Non-breaking space
        cleaned = self.cleaner.clean(text)
        assert "\xa0" not in cleaned


# ─── Text Extraction Tests ────────────────────────────────────────────────

class TestTextExtraction:
    """Test text extraction from files."""

    def test_txt_extraction(self):
        from app.services.extraction.text_extractor import TXTTextExtractor

        extractor = TXTTextExtractor()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Test content for extraction.\nLine 2.\nLine 3.")
            f.flush()
            temp_path = f.name

        try:
            result = extractor.extract(temp_path)
            assert result.total_pages == 1
            assert len(result.pages) == 1
            assert "Test content" in result.pages[0].raw_text
            assert result.pages[0].page_number == 1
        finally:
            os.unlink(temp_path)

    def test_csv_extraction(self):
        from app.services.extraction.text_extractor import CSVTextExtractor

        extractor = CSVTextExtractor()

        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8', newline='') as f:
            import csv
            writer = csv.writer(f)
            writer.writerow(["name", "phone", "location"])
            writer.writerow(["Rahul Sharma", "9876543210", "Station Road"])
            writer.writerow(["Amit Verma", "8877665544", "MG Road"])
            f.flush()
            temp_path = f.name

        try:
            result = extractor.extract(temp_path)
            assert result.total_pages >= 1
            assert "Rahul Sharma" in result.pages[0].raw_text
            assert "9876543210" in result.pages[0].raw_text
        finally:
            os.unlink(temp_path)

    def test_missing_file(self):
        from app.services.extraction.text_extractor import TXTTextExtractor

        extractor = TXTTextExtractor()
        result = extractor.extract("/nonexistent/file.txt")
        assert len(result.errors) > 0
        assert len(result.pages) == 0

    def test_extractor_factory(self):
        from app.services.extraction.text_extractor import TextExtractorFactory

        pdf_ext = TextExtractorFactory.get_extractor("application/pdf")
        assert pdf_ext is not None

        txt_ext = TextExtractorFactory.get_extractor("text/plain")
        assert txt_ext is not None

        csv_ext = TextExtractorFactory.get_extractor("text/csv")
        assert csv_ext is not None

        with pytest.raises(ValueError):
            TextExtractorFactory.get_extractor("application/unknown")


# ─── Entity Mention Tests ─────────────────────────────────────────────────

class TestEntityMentions:
    """Test that entity mentions capture page number and context."""

    def test_mention_has_page_context(self):
        extractor = RegexEntityExtractor()
        text = "Contact Rahul at 9876543210 near Station Road."
        entities = extractor.extract(text, page_number=2)

        for entity in entities:
            assert entity.context  # Context must exist
            assert entity.start >= 0
            assert entity.end > entity.start


# ─── Integration Test ─────────────────────────────────────────────────────

class TestFullExtractionPipeline:
    """Test the extraction pipeline end-to-end (without database)."""

    def test_fir_text_extraction_and_entity_extraction(self):
        """Test extracting entities from a synthetic FIR text."""
        fir_text = """FIRST INFORMATION REPORT

FIR Number: NX-001/2026
Police Station: Central Station
Date: 12/08/2026

Complainant: Rahul Sharma
Phone: 9876543210
Email: rahul.sharma@email.com

Accused: Amit Verma
Phone: 8877665544

Vehicle: CG10AB1234

Location: Station Road, near MG Road

The complainant Rahul Sharma reported that on 12/08/2026,
the accused Amit Verma was seen near Station Road in a vehicle
bearing registration CG10AB1234. Contact was made on 9876543210.
IMEI: 123456789012345
Account No: 1234567890123
"""
        # Regex extraction
        regex = RegexEntityExtractor()
        entities = regex.extract(fir_text)

        # Verify we found key entities
        types_found = {e.entity_type for e in entities}
        assert "PHONE" in types_found
        assert "EMAIL" in types_found
        assert "VEHICLE" in types_found
        assert "DATE" in types_found

        # Verify phone numbers
        phones = [e for e in entities if e.entity_type == "PHONE"]
        phone_values = {e.value for e in phones}
        assert "9876543210" in phone_values
        assert "8877665544" in phone_values

        # Verify email
        emails = [e for e in entities if e.entity_type == "EMAIL"]
        assert any("rahul.sharma@email.com" in e.value for e in emails)

        # All entities have method="REGEX"
        for e in entities:
            assert e.method == "REGEX"
            assert e.confidence > 0
            assert e.context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
