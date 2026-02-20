"""Content Safety Filter (Phase 53.3).

Validates input and output content for safety constraints:
- Maximum query length
- Maximum file size
- Maximum response length
- Hallucinated URL detection
"""

import re
from dataclasses import dataclass


@dataclass
class FilterResult:
    allowed: bool
    reason: str = ""
    filtered_text: str = ""


# Known safe URL domains (documentation, official sources)
_SAFE_DOMAINS = {
    "its.1c.ru", "v8.1c.ru", "1c.ru",
    "docs.python.org", "github.com",
    "arxiv.org", "wikipedia.org",
    "qdrant.tech", "neo4j.com",
}

_URL_PATTERN = re.compile(
    r'https?://[A-Za-z0-9\-._~:/?#\[\]@!$&\'()*+,;=%]+'
)


class ContentFilter:
    """Validate input and output content for safety."""

    def __init__(
        self,
        max_query_length: int = 10_000,
        max_file_size_bytes: int = 100 * 1024 * 1024,  # 100MB
        max_response_length: int = 50_000,
    ):
        self.max_query_length = max_query_length
        self.max_file_size_bytes = max_file_size_bytes
        self.max_response_length = max_response_length

    def validate_input(self, text: str) -> FilterResult:
        """Validate input query."""
        if len(text) > self.max_query_length:
            return FilterResult(
                allowed=False,
                reason=f"Query too long: {len(text)} chars (max {self.max_query_length})",
            )

        if not text.strip():
            return FilterResult(
                allowed=False,
                reason="Empty query",
            )

        return FilterResult(allowed=True, filtered_text=text)

    def validate_file_size(self, size_bytes: int) -> FilterResult:
        """Validate uploaded file size."""
        if size_bytes > self.max_file_size_bytes:
            max_mb = self.max_file_size_bytes / (1024 * 1024)
            actual_mb = size_bytes / (1024 * 1024)
            return FilterResult(
                allowed=False,
                reason=f"File too large: {actual_mb:.1f}MB (max {max_mb:.0f}MB)",
            )
        return FilterResult(allowed=True)

    def validate_output(self, text: str) -> FilterResult:
        """Validate and sanitize output text."""
        # Truncate if too long
        if len(text) > self.max_response_length:
            text = text[:self.max_response_length] + "\n\n[Ответ усечён из-за ограничения длины]"

        return FilterResult(allowed=True, filtered_text=text)

    def check_hallucinated_urls(self, text: str) -> list[str]:
        """Find URLs in text that look potentially hallucinated.

        Returns list of suspicious URLs (not in safe domains).
        """
        suspicious: list[str] = []
        for match in _URL_PATTERN.finditer(text):
            url = match.group()
            # Extract domain
            domain_match = re.search(r'https?://([^/:]+)', url)
            if domain_match:
                domain = domain_match.group(1).lower()
                # Check against safe domains
                if not any(domain.endswith(safe) for safe in _SAFE_DOMAINS):
                    suspicious.append(url)
        return suspicious
