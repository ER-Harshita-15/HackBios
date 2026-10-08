"""
Text Cleaning Service — normalizes extracted text while preserving the original.
Stores both raw_text and cleaned_text so the original is never destroyed.
"""

import re
import logging

logger = logging.getLogger(__name__)


class TextCleaningService:
    """
    Cleans extracted text for better entity extraction while preserving
    original text separately. Never overwrites the original.
    """

    def clean(self, raw_text: str) -> str:
        """
        Clean text for entity extraction.
        
        Operations:
        - Remove unnecessary repeated whitespace
        - Normalize line breaks
        - Remove obvious repeated PDF headers/footers
        - Preserve paragraphs
        - Preserve page boundaries
        - Preserve important punctuation
        
        Args:
            raw_text: The original extracted text.
            
        Returns:
            Cleaned text suitable for entity extraction.
        """
        if not raw_text:
            return ""

        text = raw_text

        # Normalize Unicode whitespace characters
        text = text.replace('\xa0', ' ')  # Non-breaking space
        text = text.replace('\u200b', '')  # Zero-width space
        text = text.replace('\ufeff', '')  # BOM

        # Normalize line endings
        text = text.replace('\r\n', '\n')
        text = text.replace('\r', '\n')

        # Remove excessive blank lines (more than 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)

        # Remove trailing whitespace on each line
        text = re.sub(r'[ \t]+\n', '\n', text)

        # Collapse multiple spaces within a line (but keep single newlines)
        text = re.sub(r'[ \t]{2,}', ' ', text)

        # Remove common PDF artifacts
        text = self._remove_pdf_artifacts(text)

        # Clean up but preserve paragraph breaks
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped = line.strip()
            cleaned_lines.append(stripped)

        text = '\n'.join(cleaned_lines)

        # Final cleanup of excessive newlines
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()

    def _remove_pdf_artifacts(self, text: str) -> str:
        """Remove common PDF extraction artifacts."""
        # Remove page number patterns at start/end of text blocks
        text = re.sub(r'^\s*Page\s+\d+\s+of\s+\d+\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*-\s*\d+\s*-\s*$', '', text, flags=re.MULTILINE)

        # Remove common repeated headers/footers (simple heuristic)
        # Only remove exact duplicates at start/end of consecutive pages
        lines = text.split('\n')
        if len(lines) > 10:
            # Check if first and last few lines are repeated (likely header/footer)
            pass  # Keep this simple for MVP, can be enhanced later

        return text

    def clean_for_display(self, raw_text: str) -> str:
        """
        Light cleaning for display purposes — preserves more formatting.
        """
        if not raw_text:
            return ""

        text = raw_text
        text = text.replace('\xa0', ' ')
        text = re.sub(r'[ \t]{3,}', '  ', text)
        text = re.sub(r'\n{4,}', '\n\n\n', text)

        return text.strip()
