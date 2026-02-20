"""Graph change detection for incremental updates.

Phase 61: Incremental Graph Update - detect changed chunks.
"""

import hashlib
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from src.pdf_framework.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


@dataclass
class ChangeSet:
    """Set of changes detected in documents."""

    added: list[str] = field(default_factory=list)  # New chunk IDs
    modified: list[str] = field(default_factory=list)  # Modified chunk IDs
    deleted: list[str] = field(default_factory=list)  # Deleted chunk IDs

    def has_changes(self) -> bool:
        """Check if any changes detected."""
        return bool(self.added or self.modified or self.deleted)

    def summary(self) -> dict:
        """Get summary of changes."""
        return {
            "added": len(self.added),
            "modified": len(self.modified),
            "deleted": len(self.deleted),
            "total": len(self.added) + len(self.modified) + len(self.deleted),
        }


@dataclass
class ChunkHash:
    """Content hash for a chunk."""

    chunk_id: str
    document_id: str
    content_hash: str  # SHA-256 of content
    metadata_hash: str  # SHA-256 of metadata


class GraphChangeDetector:
    """Detect changes in document chunks for incremental graph updates.

    Compares current chunks with stored hashes to identify:
    - New chunks (not in hash database)
    - Modified chunks (content hash changed)
    - Deleted chunks (in hash database but not in current)
    """

    def __init__(self, hash_db_path: Optional[Path] = None):
        """Initialize change detector.

        Args:
            hash_db_path: Path to hash database (JSON file)
        """
        self.hash_db_path = hash_db_path or settings.data_dir / "graph_chunk_hashes.json"
        self.hash_db_path.parent.mkdir(parents=True, exist_ok=True)
        self._hashes: dict[str, ChunkHash] = {}
        self._load()

    def _compute_content_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content.

        Args:
            content: Text content

        Returns:
            Hexadecimal hash string
        """
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _compute_metadata_hash(self, metadata: dict) -> str:
        """Compute SHA-256 hash of metadata.

        Args:
            metadata: Metadata dictionary

        Returns:
            Hexadecimal hash string
        """
        import json

        # Sort keys for consistent hashing
        normalized = json.dumps(metadata, sort_keys=True)
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    async def detect_changes(
        self,
        current_chunks: list[dict],
        document_id: str,
    ) -> ChangeSet:
        """Detect changes between current chunks and stored hashes.

        Args:
            current_chunks: List of current chunks with id, content, metadata
            document_id: Document ID

        Returns:
            ChangeSet with detected changes
        """
        changes = ChangeSet()
        current_ids = set()

        # Check for new and modified chunks
        for chunk in current_chunks:
            chunk_id = chunk.get("id") or chunk.get("chunk_id")
            if not chunk_id:
                logger.warning("[CHANGE] Chunk missing ID, skipping")
                continue

            current_ids.add(chunk_id)

            content_hash = self._compute_content_hash(chunk.get("content", ""))
            metadata_hash = self._compute_metadata_hash(chunk.get("metadata", {}))

            stored = self._hashes.get(chunk_id)

            if stored is None:
                # New chunk
                changes.added.append(chunk_id)
                logger.debug(f"[CHANGE] New chunk: {chunk_id}")

            elif (
                stored.content_hash != content_hash
                or stored.metadata_hash != metadata_hash
            ):
                # Modified chunk
                changes.modified.append(chunk_id)
                logger.debug(f"[CHANGE] Modified chunk: {chunk_id}")

        # Check for deleted chunks
        for chunk_id, stored_hash in self._hashes.items():
            if stored_hash.document_id == document_id and chunk_id not in current_ids:
                changes.deleted.append(chunk_id)
                logger.debug(f"[CHANGE] Deleted chunk: {chunk_id}")

        return changes

    async def update_hashes(
        self,
        chunks: list[dict],
        document_id: str,
    ) -> None:
        """Update stored hashes for chunks.

        Args:
            chunks: List of chunks with id, content, metadata
            document_id: Document ID
        """
        for chunk in chunks:
            chunk_id = chunk.get("id") or chunk.get("chunk_id")
            if not chunk_id:
                continue

            content_hash = self._compute_content_hash(chunk.get("content", ""))
            metadata_hash = self._compute_metadata_hash(chunk.get("metadata", {}))

            self._hashes[chunk_id] = ChunkHash(
                chunk_id=chunk_id,
                document_id=document_id,
                content_hash=content_hash,
                metadata_hash=metadata_hash,
            )

        # Remove deleted chunks for this document
        to_delete = [
            chunk_id
            for chunk_id, stored in self._hashes.items()
            if stored.document_id == document_id
            and chunk_id not in {c.get("id") or c.get("chunk_id") for c in chunks if c.get("id") or c.get("chunk_id")}
        ]

        for chunk_id in to_delete:
            del self._hashes[chunk_id]

        self._save()

    async def remove_document(self, document_id: str) -> None:
        """Remove all hashes for a document.

        Args:
            document_id: Document ID
        """
        to_delete = [
            chunk_id
            for chunk_id, stored in self._hashes.items()
            if stored.document_id == document_id
        ]

        for chunk_id in to_delete:
            del self._hashes[chunk_id]

        self._save()
        logger.info(f"[CHANGE] Removed {len(to_delete)} hashes for document: {document_id}")

    def _load(self) -> None:
        """Load hashes from disk."""
        import json

        if not self.hash_db_path.exists():
            return

        try:
            with open(self.hash_db_path, "r") as f:
                data = json.load(f)

            for chunk_id, hash_data in data.items():
                self._hashes[chunk_id] = ChunkHash(**hash_data)

            logger.info(f"[CHANGE] Loaded {len(self._hashes)} chunk hashes")

        except Exception as e:
            logger.error(f"[CHANGE] Failed to load hashes: {e}")

    def _save(self) -> None:
        """Save hashes to disk."""
        import json

        try:
            data = {
                chunk_id: {
                    "chunk_id": hash.chunk_id,
                    "document_id": hash.document_id,
                    "content_hash": hash.content_hash,
                    "metadata_hash": hash.metadata_hash,
                }
                for chunk_id, hash in self._hashes.items()
            }

            with open(self.hash_db_path, "w") as f:
                json.dump(data, f, indent=2)

        except Exception as e:
            logger.error(f"[CHANGE] Failed to save hashes: {e}")


# Singleton instance
_change_detector: Optional[GraphChangeDetector] = None


def get_change_detector() -> GraphChangeDetector:
    """Get change detector singleton."""
    global _change_detector
    if _change_detector is None:
        _change_detector = GraphChangeDetector()
    return _change_detector
