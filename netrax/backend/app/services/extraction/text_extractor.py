"""
PDF Text Extractor — extracts text page-by-page using PyMuPDF (fitz).
Falls back to OCR when a page contains no extractable text.
"""

try:
    import pymupdf as fitz
except ImportError:
    import fitz  # Fallback for older versions
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class PageText:
    """Represents extracted text from a single page."""
    page_number: int
    raw_text: str
    ocr_applied: bool = False


@dataclass
class ExtractionResult:
    """Result of text extraction from a document."""
    pages: list[PageText] = field(default_factory=list)
    total_pages: int = 0
    errors: list[str] = field(default_factory=list)


class PDFTextExtractor:
    """
    Extracts text from PDF documents page-by-page using PyMuPDF.
    If a page has no extractable text, it is flagged for OCR processing.
    """

    MIN_TEXT_LENGTH = 10  # Minimum characters to consider a page as having text

    def extract(self, file_path: str | Path) -> ExtractionResult:
        """
        Extract text from a PDF file page-by-page.

        Args:
            file_path: Path to the PDF file.

        Returns:
            ExtractionResult with page-by-page text.
        """
        file_path = Path(file_path)
        result = ExtractionResult()

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            doc = fitz.open(str(file_path))
            result.total_pages = len(doc)

            for page_num in range(len(doc)):
                try:
                    page = doc[page_num]
                    text = page.get_text("text")

                    needs_ocr = len(text.strip()) < self.MIN_TEXT_LENGTH

                    result.pages.append(PageText(
                        page_number=page_num + 1,  # 1-indexed
                        raw_text=text if not needs_ocr else "",
                        ocr_applied=False,
                    ))

                    if needs_ocr:
                        logger.info(f"Page {page_num + 1} has minimal text, flagged for OCR")

                except Exception as e:
                    logger.error(f"Error extracting page {page_num + 1}: {e}")
                    result.errors.append(f"Page {page_num + 1}: {str(e)}")
                    result.pages.append(PageText(
                        page_number=page_num + 1,
                        raw_text="",
                        ocr_applied=False,
                    ))

            doc.close()

        except Exception as e:
            logger.error(f"Error opening PDF {file_path}: {e}")
            result.errors.append(f"Failed to open PDF: {str(e)}")

        return result


class TXTTextExtractor:
    """Extracts text from plain text files. Treats entire file as one page."""

    def extract(self, file_path: str | Path) -> ExtractionResult:
        file_path = Path(file_path)
        result = ExtractionResult()

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()

            result.total_pages = 1
            result.pages.append(PageText(
                page_number=1,
                raw_text=text,
                ocr_applied=False,
            ))

        except Exception as e:
            logger.error(f"Error reading TXT {file_path}: {e}")
            result.errors.append(f"Failed to read file: {str(e)}")

        return result


class CSVTextExtractor:
    """
    Extracts text from CSV files. 
    Each chunk of rows is treated as a page for entity extraction purposes.
    """

    ROWS_PER_PAGE = 100

    def extract(self, file_path: str | Path) -> ExtractionResult:
        import csv

        file_path = Path(file_path)
        result = ExtractionResult()

        if not file_path.exists():
            result.errors.append(f"File not found: {file_path}")
            return result

        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = list(reader)

            if not rows:
                result.errors.append("CSV file is empty")
                return result

            header = rows[0]
            data_rows = rows[1:]

            # Split into pages of ROWS_PER_PAGE
            page_num = 1
            for i in range(0, max(len(data_rows), 1), self.ROWS_PER_PAGE):
                chunk = data_rows[i:i + self.ROWS_PER_PAGE]
                # Reconstruct as text with headers for NER processing
                lines = [",".join(header)]
                for row in chunk:
                    lines.append(",".join(row))
                text = "\n".join(lines)

                result.pages.append(PageText(
                    page_number=page_num,
                    raw_text=text,
                    ocr_applied=False,
                ))
                page_num += 1

            result.total_pages = len(result.pages)

        except Exception as e:
            logger.error(f"Error reading CSV {file_path}: {e}")
            result.errors.append(f"Failed to read CSV: {str(e)}")

        return result


class TextExtractorFactory:
    """Factory for creating appropriate text extractors based on file type."""

    _extractors = {
        "application/pdf": PDFTextExtractor,
        "text/plain": TXTTextExtractor,
        "text/csv": CSVTextExtractor,
    }

    @classmethod
    def get_extractor(cls, mime_type: str):
        """Get the appropriate extractor for the given MIME type."""
        extractor_class = cls._extractors.get(mime_type)
        if extractor_class is None:
            raise ValueError(f"Unsupported file type: {mime_type}")
        return extractor_class()

    @classmethod
    def register_extractor(cls, mime_type: str, extractor_class):
        """Register a new extractor for a MIME type (extensibility)."""
        cls._extractors[mime_type] = extractor_class
