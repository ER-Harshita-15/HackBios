"""
OCR Service — modular OCR abstraction for scanned document processing.
Uses Tesseract as the default implementation, but can be replaced.
"""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class OCRResult:
    """Result of OCR processing."""
    text: str
    confidence: float = 0.0
    success: bool = True
    error: str | None = None


class BaseOCRService(ABC):
    """Abstract base class for OCR services. Implement to swap OCR providers."""

    @abstractmethod
    def extract_text(self, image) -> OCRResult:
        """Extract text from an image."""
        ...

    @abstractmethod
    def extract_text_from_pdf_page(self, pdf_path: str, page_number: int) -> OCRResult:
        """Extract text from a specific PDF page using OCR."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if the OCR service is available."""
        ...


class TesseractOCRService(BaseOCRService):
    """
    OCR implementation using Tesseract.
    Falls back gracefully if Tesseract is not installed.
    """

    def __init__(self, tesseract_cmd: str | None = None):
        self._available = False
        try:
            import pytesseract
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            # Test availability
            pytesseract.get_tesseract_version()
            self._available = True
            logger.info("Tesseract OCR is available")
        except Exception as e:
            logger.warning(f"Tesseract OCR is not available: {e}")

    def is_available(self) -> bool:
        return self._available

    def extract_text(self, image) -> OCRResult:
        """Extract text from a PIL Image."""
        if not self._available:
            return OCRResult(text="", success=False, error="Tesseract is not available")

        try:
            import pytesseract
            text = pytesseract.image_to_string(image)
            # Get confidence data
            data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
            confidences = [int(c) for c in data['conf'] if int(c) > 0]
            avg_confidence = sum(confidences) / len(confidences) / 100 if confidences else 0.0

            return OCRResult(text=text, confidence=avg_confidence, success=True)
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return OCRResult(text="", success=False, error=str(e))

    def extract_text_from_pdf_page(self, pdf_path: str, page_number: int) -> OCRResult:
        """
        Extract text from a PDF page by rendering it as an image first.
        page_number is 0-indexed.
        """
        if not self._available:
            return OCRResult(text="", success=False, error="Tesseract is not available")

        try:
            try:
                import pymupdf as fitz
            except ImportError:
                import fitz
            from PIL import Image
            import io

            doc = fitz.open(pdf_path)
            page = doc[page_number]

            # Render page as image at 300 DPI for good OCR quality
            mat = fitz.Matrix(300 / 72, 300 / 72)
            pix = page.get_pixmap(matrix=mat)
            img_data = pix.tobytes("png")
            doc.close()

            image = Image.open(io.BytesIO(img_data))
            return self.extract_text(image)

        except Exception as e:
            logger.error(f"OCR PDF page extraction failed: {e}")
            return OCRResult(text="", success=False, error=str(e))


class NoOpOCRService(BaseOCRService):
    """No-op OCR service when OCR is disabled or unavailable."""

    def extract_text(self, image) -> OCRResult:
        return OCRResult(text="", success=False, error="OCR is disabled")

    def extract_text_from_pdf_page(self, pdf_path: str, page_number: int) -> OCRResult:
        return OCRResult(text="", success=False, error="OCR is disabled")

    def is_available(self) -> bool:
        return False


def create_ocr_service(enabled: bool = True, tesseract_cmd: str | None = None) -> BaseOCRService:
    """Factory function to create the appropriate OCR service."""
    if not enabled:
        return NoOpOCRService()
    service = TesseractOCRService(tesseract_cmd=tesseract_cmd)
    if not service.is_available():
        logger.warning("Falling back to NoOp OCR — Tesseract not found")
        return NoOpOCRService()
    return service
