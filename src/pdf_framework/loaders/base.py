"""Abstract base class for document loaders.

All loader implementations (PDF, web, structured) must implement this interface.
Supports both single file and batch loading.
"""

from abc import ABC, abstractmethod
from pathlib import Path

from src.pdf_framework.schemas.documents import ProcessedDocument


class BaseLoader(ABC):
    """Abstract interface for document loading."""

    @abstractmethod
    async def load(self, source: str | Path) -> ProcessedDocument:
        """Load and process a single document from file path or URL."""

    @abstractmethod
    async def load_batch(self, sources: list[str | Path]) -> list[ProcessedDocument]:
        """Load multiple documents."""

    @abstractmethod
    def supported_extensions(self) -> list[str]:
        """Return list of supported file extensions (e.g., ['.pdf'])."""
