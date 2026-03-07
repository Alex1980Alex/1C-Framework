"""
Artifact Models for Development Pipeline.

Defines data structures for artifacts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import hashlib

from constants import AgentRole, ArtifactType


@dataclass
class ArtifactMetadata:
    """Metadata for an artifact."""

    artifact_type: ArtifactType
    producer: AgentRole
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    version: int = 1
    checksum: str = ""
    dependencies: List[str] = field(default_factory=list)
    tags: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "artifact_type": self.artifact_type.value,
            "producer": self.producer.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "version": self.version,
            "checksum": self.checksum,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactMetadata":
        """Create from dictionary."""
        return cls(
            artifact_type=ArtifactType(data["artifact_type"]),
            producer=AgentRole(data["producer"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            version=data.get("version", 1),
            checksum=data.get("checksum", ""),
            dependencies=data.get("dependencies", []),
            tags=data.get("tags", {}),
        )


@dataclass
class Artifact:
    """Represents a pipeline artifact (spec.md, design.md, etc.)."""

    name: str
    content: str
    metadata: ArtifactMetadata
    path: Optional[Path] = None

    def __post_init__(self) -> None:
        """Calculate checksum after initialization."""
        if not self.metadata.checksum:
            self.metadata.checksum = self._calculate_checksum()

    def _calculate_checksum(self) -> str:
        """Calculate MD5 checksum of content."""
        return hashlib.md5(self.content.encode("utf-8")).hexdigest()

    def update_content(self, new_content: str) -> None:
        """Update artifact content and metadata."""
        self.content = new_content
        self.metadata.updated_at = datetime.now()
        self.metadata.version += 1
        self.metadata.checksum = self._calculate_checksum()

    def to_markdown_header(self) -> str:
        """Generate markdown header with metadata."""
        return f"""---
artifact_type: {self.metadata.artifact_type.value}
producer: {self.metadata.producer.value}
version: {self.metadata.version}
created_at: {self.metadata.created_at.isoformat()}
updated_at: {self.metadata.updated_at.isoformat()}
checksum: {self.metadata.checksum}
---

"""

    @property
    def full_content(self) -> str:
        """Get content with metadata header."""
        return self.to_markdown_header() + self.content

    def validate(self) -> List[str]:
        """Validate artifact structure. Returns list of errors."""
        errors = []

        if not self.name:
            errors.append("Artifact name is required")

        if not self.content:
            errors.append("Artifact content is empty")

        # Check required sections based on artifact type
        required_sections = self._get_required_sections()
        for section in required_sections:
            if section.lower() not in self.content.lower():
                errors.append(f"Missing required section: {section}")

        return errors

    def _get_required_sections(self) -> List[str]:
        """Get required sections based on artifact type."""
        sections = {
            ArtifactType.CONTEXT: ["# Контекст проекта", "## Структура"],
            ArtifactType.SPEC: ["# Спецификация", "## Требования", "## Критерии приёмки"],
            ArtifactType.DESIGN: ["# Техническое решение", "## Архитектурные решения", "## План изменений"],
            ArtifactType.RESULT: ["# Результат реализации", "## Выполненные шаги", "## Созданные файлы"],
            ArtifactType.VERIFICATION: ["# Верификация", "## Статус", "## Вердикт"],
        }
        return sections.get(self.metadata.artifact_type, [])
