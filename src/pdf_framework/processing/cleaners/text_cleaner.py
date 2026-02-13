"""Text cleaning utilities for PDF content."""

import re
import unicodedata


class TextCleaner:
    """Clean and normalize text extracted from PDFs."""

    def clean(self, text: str) -> str:
        """Apply all cleaning steps."""
        text = self.normalize_unicode(text)
        text = self.fix_whitespace(text)
        text = self.remove_control_chars(text)
        text = self.fix_hyphenation(text)
        return text.strip()

    @staticmethod
    def normalize_unicode(text: str) -> str:
        """Normalize Unicode characters to NFC form."""
        return unicodedata.normalize("NFC", text)

    @staticmethod
    def fix_whitespace(text: str) -> str:
        """Normalize whitespace: collapse multiple spaces, fix line breaks."""
        # Replace multiple spaces with single space
        text = re.sub(r"[^\S\n]+", " ", text)
        # Collapse 3+ newlines into 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove trailing spaces on lines
        text = re.sub(r" +\n", "\n", text)
        return text

    @staticmethod
    def remove_control_chars(text: str) -> str:
        """Remove control characters except newlines and tabs."""
        return "".join(
            c for c in text
            if c in ("\n", "\t") or not unicodedata.category(c).startswith("C")
        )

    @staticmethod
    def fix_hyphenation(text: str) -> str:
        """Rejoin hyphenated words split across lines."""
        return re.sub(r"(\w)-\n(\w)", r"\1\2", text)
