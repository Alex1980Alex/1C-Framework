"""
MemoryCube — Unified Memory Container (MemOS pattern).

A single dataclass that encapsulates content + metadata for any memory subsystem.
Eliminates the need to work with 3 separate store formats — all subsystems
accept and return MemoryCube instances.

Reference: MemOS project (MemTensor/MemOS) — MemCube abstraction.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from .unified_id import MemoryType, SourceServer


class ContentType(str, Enum):
    """Auto-classified content type (Memori pattern)."""

    FACT = "fact"                # Episodic fact, decision, conclusion
    PREFERENCE = "preference"    # User preference, style choice
    RULE = "rule"               # Coding rule, convention, standard
    SKILL = "skill"             # Confirmed workflow, practice
    CODE = "code"               # Code snippet, function, pattern
    OBSERVATION = "observation"  # General observation, note
    WIKI = "wiki"               # Wiki page content (frontmatter + markdown)


@dataclass
class MemoryCube:
    """Unified memory container for all subsystems.

    Inspired by MemOS MemCube: a single composable object that travels
    through the entire pipeline (classify -> route -> store -> search -> return).

    Fields:
        cube_id: Unique identifier (UUIDv4).
        content: The actual content string.
        content_type: Auto-classified type (fact/preference/rule/skill/code/observation).
        memory_type: Target memory type (episodic/semantic/learning/doc).
        source: Which subsystem stores this cube.
        title: Optional short title / summary.

        confidence: Confidence score 0..1.
        importance: Importance score 0..1.
        tags: Searchable tags.
        metadata: Arbitrary key-value metadata.

        what: What happened / what is it.
        why: Why it matters.
        where: Where it applies (file, module, context).
        learned: What was learned from it.

        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
        expires_at: Optional TTL expiry.
        version: Version counter for updates.
    """

    # --- Identity ---
    cube_id: str = field(default_factory=lambda: str(uuid4()))
    content: str = ""
    content_type: ContentType = ContentType.OBSERVATION
    memory_type: MemoryType = MemoryType.EPISODIC
    source: SourceServer = SourceServer.MEMORY_AI
    title: str | None = None

    # --- Scoring ---
    confidence: float = 0.7
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- Structured observations (Engram pattern) ---
    what: str | None = None
    why: str | None = None
    where: str | None = None
    learned: str | None = None

    # --- Temporal ---
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    expires_at: datetime | None = None
    version: int = 1

    # --- Lifecycle ---

    def touch(self) -> None:
        """Update the modification timestamp and bump version."""
        self.updated_at = datetime.now()
        self.version += 1

    def is_expired(self) -> bool:
        """Check if this cube has passed its TTL."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at

    # --- Serialization ---

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary (JSON-safe with isoformat dates)."""
        return {
            "cube_id": self.cube_id,
            "content": self.content,
            "content_type": self.content_type.value,
            "memory_type": self.memory_type.value,
            "source": self.source.value,
            "title": self.title,
            "confidence": self.confidence,
            "importance": self.importance,
            "tags": self.tags,
            "metadata": self.metadata,
            "what": self.what,
            "why": self.why,
            "where": self.where,
            "learned": self.learned,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "version": self.version,
        }

    def to_json(self) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryCube:
        """Deserialize from dictionary."""
        cube = cls(
            cube_id=data.get("cube_id", str(uuid4())),
            content=data.get("content", ""),
            content_type=ContentType(data["content_type"]) if "content_type" in data else ContentType.OBSERVATION,
            memory_type=MemoryType(data["memory_type"]) if "memory_type" in data else MemoryType.EPISODIC,
            source=SourceServer(data["source"]) if "source" in data else SourceServer.MEMORY_AI,
            title=data.get("title"),
            confidence=data.get("confidence", 0.7),
            importance=data.get("importance", 0.5),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
            what=data.get("what"),
            why=data.get("why"),
            where=data.get("where"),
            learned=data.get("learned"),
            version=data.get("version", 1),
        )
        if "created_at" in data and data["created_at"]:
            cube.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and data["updated_at"]:
            cube.updated_at = datetime.fromisoformat(data["updated_at"])
        if "expires_at" in data and data["expires_at"]:
            cube.expires_at = datetime.fromisoformat(data["expires_at"])
        return cube

    @classmethod
    def from_json(cls, json_str: str) -> MemoryCube:
        """Deserialize from JSON string."""
        return cls.from_dict(json.loads(json_str))

    # --- Conversion helpers ---

    def to_ai_memory_row(self) -> dict[str, Any]:
        """Convert to memory-ai SQLite row format."""
        return {
            "id": self.cube_id,
            "content": self.content,
            "importance": self.importance,
            "category": self.content_type.value,
            "tags": json.dumps(self.tags, ensure_ascii=False),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": json.dumps(self.metadata, ensure_ascii=False),
        }

    def to_vector_memory_payload(self) -> dict[str, Any]:
        """Convert to vector-memory Qdrant payload format."""
        return {
            "pattern_id": self.cube_id,
            "pattern_type": self.metadata.get("pattern_type", "code-convention"),
            "name": self.title or self.content[:50],
            "description": self.what or "",
            "content": self.content,
            "confidence": self.confidence,
            "evidence_sources": [],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "last_applied": None,
            "decay_rate": 0.05,
            "application_count": 0,
            "version": self.version,
            "tags": self.tags,
            "metadata": self.metadata,
        }

    def to_skill_learning_record(self) -> dict[str, Any]:
        """Convert to skill-learning JSONL record format."""
        return {
            "pattern_id": self.cube_id,
            "pattern_type": self.metadata.get("pattern_type", "workflow-pattern"),
            "name": self.title or self.content[:50],
            "content": self.content,
            "description": self.what or "",
            "confidence": self.confidence,
            "tags": self.tags,
            "application_count": 0,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
        }

    def to_wiki_page(self) -> str:
        """Serialize to Obsidian-compatible markdown with YAML frontmatter."""
        import yaml

        frontmatter = {
            "unified_id": f"{self.memory_type.value}:{self.source.value}:{self.cube_id}",
            "memory_type": self.memory_type.value,
            "content_type": self.content_type.value,
            "source": self.source.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "confidence": self.confidence,
            "importance": self.importance,
            "version": self.version,
        }
        if self.title:
            frontmatter["title"] = self.title
        if self.tags:
            frontmatter["tags"] = self.tags
        if self.expires_at:
            frontmatter["expires_at"] = self.expires_at.isoformat()
        if self.metadata:
            frontmatter["metadata"] = self.metadata

        lines = ["---"]
        lines.append(yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip())
        lines.append("---")
        lines.append("")

        if self.what:
            lines.append(f"## What\n\n{self.what}\n")
        if self.why:
            lines.append(f"## Why\n\n{self.why}\n")
        if self.where:
            lines.append(f"## Where\n\n{self.where}\n")
        if self.learned:
            lines.append(f"## Learned\n\n{self.learned}\n")
        if self.content:
            lines.append(self.content)

        return "\n".join(lines)

    @classmethod
    def from_wiki_page(cls, md: str) -> MemoryCube:
        """Parse wiki page markdown with YAML frontmatter back to MemoryCube."""
        import yaml

        if not md.startswith("---"):
            return cls(content=md, content_type=ContentType.WIKI)

        parts = md.split("---", 2)
        if len(parts) < 3:
            return cls(content=md, content_type=ContentType.WIKI)

        frontmatter = yaml.safe_load(parts[1])
        body = parts[2].strip()

        # Parse structured sections from body
        sections = {"what": None, "why": None, "where": None, "learned": None}
        current_section = None
        content_lines = []

        for line in body.split("\n"):
            if line.startswith("## "):
                section_name = line[3:].strip().lower()
                if section_name in sections:
                    current_section = section_name
                else:
                    current_section = None
                    content_lines.append(line)
            elif current_section and line.strip():
                sections[current_section] = (sections[current_section] or "") + line + "\n"
            elif current_section and not line.strip():
                pass  # skip blank lines between section content
            else:
                content_lines.append(line)

        content = "\n".join(content_lines).strip()

        cube = cls(
            cube_id=frontmatter.get("unified_id", "").split(":")[-1] or str(uuid4()),
            content=content,
            content_type=ContentType(frontmatter.get("content_type", "wiki")),
            memory_type=MemoryType(frontmatter["memory_type"]) if "memory_type" in frontmatter else MemoryType.EPISODIC,
            source=SourceServer(frontmatter["source"]) if "source" in frontmatter else SourceServer.MEMORY_AI,
            title=frontmatter.get("title"),
            confidence=frontmatter.get("confidence", 0.7),
            importance=frontmatter.get("importance", 0.5),
            tags=frontmatter.get("tags", []),
            metadata=frontmatter.get("metadata", {}),
            what=sections["what"].strip() if sections["what"] else None,
            why=sections["why"].strip() if sections["why"] else None,
            where=sections["where"].strip() if sections["where"] else None,
            learned=sections["learned"].strip() if sections["learned"] else None,
            version=frontmatter.get("version", 1),
        )

        if "created_at" in frontmatter:
            cube.created_at = datetime.fromisoformat(frontmatter["created_at"])
        if "updated_at" in frontmatter:
            cube.updated_at = datetime.fromisoformat(frontmatter["updated_at"])
        if "expires_at" in frontmatter:
            cube.expires_at = datetime.fromisoformat(frontmatter["expires_at"])

        return cube

    def __repr__(self) -> str:
        return (
            f"MemoryCube(id={self.cube_id[:8]}..., "
            f"type={self.content_type.value}, "
            f"source={self.source.value}, "
            f"conf={self.confidence:.2f})"
        )


__all__ = [
    "ContentType",
    "MemoryCube",
]
