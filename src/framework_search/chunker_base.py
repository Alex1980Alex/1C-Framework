"""Chunk dataclass and base interface for framework_search chunkers."""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import ClassVar


_UUID_NAMESPACE = uuid.UUID("8b9b3f2c-1c6f-4a23-9c8a-3f7d8e1a2b3c")


@dataclass
class Chunk:
    """One indexed unit. Stored in Qdrant with payload mirroring all fields."""

    relative_path: str          # repo-relative POSIX path
    content: str                # actual chunk text (truncated by embedder if needed)
    language: str               # python | markdown | json | text
    chunk_type: str             # function | class | module | section | config | text
    line_start: int
    line_end: int
    mtime: float                # source file mtime at index time
    symbol_name: str | None = None
    sha1: str = field(default="")          # sha1 of content (filled in __post_init__)
    chunk_id: str = field(default="")      # deterministic UUID5 (filled in __post_init__)

    EXPECTED_DIMS: ClassVar[int] = 4096    # Qwen3-Embedding-8B native

    def __post_init__(self) -> None:
        if not self.sha1:
            self.sha1 = hashlib.sha1(self.content.encode("utf-8", errors="ignore")).hexdigest()
        if not self.chunk_id:
            key = f"{self.relative_path}:{self.line_start}:{self.sha1[:12]}"
            self.chunk_id = str(uuid.uuid5(_UUID_NAMESPACE, key))

    def to_payload(self) -> dict:
        """Qdrant payload — everything searchable lives here."""
        return {
            "relative_path": self.relative_path,
            "content": self.content,
            "language": self.language,
            "chunk_type": self.chunk_type,
            "symbol_name": self.symbol_name,
            "line_start": self.line_start,
            "line_end": self.line_end,
            "mtime": self.mtime,
            "sha1": self.sha1,
        }
