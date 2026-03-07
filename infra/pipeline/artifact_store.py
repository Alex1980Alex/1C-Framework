"""
Artifact Store - Centralized storage for pipeline artifacts.

Based on MetaGPT's artifact management approach with:
- Versioning
- Dependency tracking
- Rollback support
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import shutil

from constants import ArtifactType, AgentRole
from models import Artifact, ArtifactMetadata

logger = logging.getLogger(__name__)


class ArtifactStore:
    """
    Centralized artifact storage with versioning and dependencies.

    Features:
    - Store and retrieve artifacts by type
    - Version history with rollback
    - Dependency tracking between artifacts
    - Persistence to filesystem
    """

    def __init__(self, base_path: Path, session_id: Optional[str] = None) -> None:
        """
        Initialize artifact store.

        Args:
            base_path: Base directory for artifact storage
            session_id: Optional session identifier for isolation
        """
        self.base_path = Path(base_path)
        self.session_id = session_id or datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_path = self.base_path / self.session_id

        # In-memory cache
        self._artifacts: Dict[ArtifactType, Artifact] = {}
        self._history: Dict[ArtifactType, List[Artifact]] = {}

        # Ensure directories exist
        self._init_directories()

    def _init_directories(self) -> None:
        """Create necessary directories."""
        self.session_path.mkdir(parents=True, exist_ok=True)
        (self.session_path / "history").mkdir(exist_ok=True)
        (self.session_path / "metadata").mkdir(exist_ok=True)

    def store(
        self,
        artifact_type: ArtifactType,
        content: str,
        producer: AgentRole,
        dependencies: Optional[List[ArtifactType]] = None,
        tags: Optional[Dict] = None,
    ) -> Artifact:
        """
        Store an artifact.

        Args:
            artifact_type: Type of artifact
            content: Artifact content (markdown)
            producer: Agent that produced the artifact
            dependencies: List of dependent artifact types
            tags: Additional metadata tags

        Returns:
            Created Artifact instance
        """
        # Check dependencies
        if dependencies:
            for dep in dependencies:
                if dep not in self._artifacts:
                    raise ValueError(f"Missing dependency: {dep.value}")

        # Create metadata
        metadata = ArtifactMetadata(
            artifact_type=artifact_type,
            producer=producer,
            dependencies=[d.value for d in (dependencies or [])],
            tags=tags or {},
        )

        # Handle versioning if artifact exists
        if artifact_type in self._artifacts:
            existing = self._artifacts[artifact_type]
            # Save to history
            if artifact_type not in self._history:
                self._history[artifact_type] = []
            self._history[artifact_type].append(existing)

            # Update version
            metadata.version = existing.metadata.version + 1
            metadata.created_at = existing.metadata.created_at

        # Create artifact
        artifact = Artifact(
            name=artifact_type.value,
            content=content,
            metadata=metadata,
            path=self.session_path / artifact_type.value,
        )

        # Validate
        errors = artifact.validate()
        if errors:
            logger.warning(f"Artifact validation warnings: {errors}")

        # Store in memory and filesystem
        self._artifacts[artifact_type] = artifact
        self._persist_artifact(artifact)

        logger.info(
            f"Stored artifact {artifact_type.value} v{metadata.version} "
            f"by {producer.value}"
        )

        return artifact

    def get(self, artifact_type: ArtifactType) -> Optional[Artifact]:
        """
        Retrieve an artifact by type.

        Args:
            artifact_type: Type of artifact to retrieve

        Returns:
            Artifact or None if not found
        """
        return self._artifacts.get(artifact_type)

    def get_content(self, artifact_type: ArtifactType) -> Optional[str]:
        """Get artifact content only."""
        artifact = self.get(artifact_type)
        return artifact.content if artifact else None

    def get_all(self) -> Dict[ArtifactType, Artifact]:
        """Get all current artifacts."""
        return self._artifacts.copy()

    def get_history(self, artifact_type: ArtifactType) -> List[Artifact]:
        """Get version history for an artifact type."""
        return self._history.get(artifact_type, [])

    def rollback(self, artifact_type: ArtifactType, version: int) -> Optional[Artifact]:
        """
        Rollback artifact to a specific version.

        Args:
            artifact_type: Type of artifact
            version: Target version number

        Returns:
            Restored artifact or None if version not found
        """
        history = self.get_history(artifact_type)

        for hist_artifact in history:
            if hist_artifact.metadata.version == version:
                # Restore artifact
                self._artifacts[artifact_type] = hist_artifact
                self._persist_artifact(hist_artifact)
                logger.info(f"Rolled back {artifact_type.value} to v{version}")
                return hist_artifact

        logger.warning(f"Version {version} not found for {artifact_type.value}")
        return None

    def _persist_artifact(self, artifact: Artifact) -> None:
        """Save artifact to filesystem."""
        # Save content
        content_path = self.session_path / artifact.name
        with open(content_path, "w", encoding="utf-8") as f:
            f.write(artifact.full_content)

        # Save metadata
        metadata_path = self.session_path / "metadata" / f"{artifact.name}.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(artifact.metadata.to_dict(), f, indent=2, ensure_ascii=False)

        # Save to history
        if artifact.metadata.version > 1:
            history_path = (
                self.session_path
                / "history"
                / f"{artifact.name}.v{artifact.metadata.version - 1}"
            )
            current = self.get(artifact.metadata.artifact_type)
            if current and artifact.metadata.version > 1:
                prev_history = self._history.get(artifact.metadata.artifact_type, [])
                if prev_history:
                    with open(history_path, "w", encoding="utf-8") as f:
                        f.write(prev_history[-1].full_content)

    def load_session(self, session_id: str) -> bool:
        """
        Load artifacts from a previous session.

        Args:
            session_id: Session identifier to load

        Returns:
            True if session loaded successfully
        """
        session_path = self.base_path / session_id
        if not session_path.exists():
            logger.error(f"Session {session_id} not found")
            return False

        self.session_id = session_id
        self.session_path = session_path

        # Load all artifacts
        for artifact_file in session_path.glob("*.md"):
            artifact_type_str = artifact_file.name
            try:
                artifact_type = ArtifactType(artifact_type_str)
            except ValueError:
                continue

            # Load metadata
            metadata_path = session_path / "metadata" / f"{artifact_type_str}.json"
            if metadata_path.exists():
                with open(metadata_path, "r", encoding="utf-8") as f:
                    metadata = ArtifactMetadata.from_dict(json.load(f))
            else:
                # Create default metadata
                metadata = ArtifactMetadata(
                    artifact_type=artifact_type,
                    producer=artifact_type.producer,
                )

            # Load content (skip header if present)
            with open(artifact_file, "r", encoding="utf-8") as f:
                content = f.read()
                # Remove YAML front matter if present
                if content.startswith("---"):
                    parts = content.split("---", 2)
                    if len(parts) >= 3:
                        content = parts[2].strip()

            artifact = Artifact(
                name=artifact_type_str,
                content=content,
                metadata=metadata,
                path=artifact_file,
            )
            self._artifacts[artifact_type] = artifact

        logger.info(f"Loaded session {session_id} with {len(self._artifacts)} artifacts")
        return True

    def get_dependency_chain(
        self, artifact_type: ArtifactType
    ) -> List[ArtifactType]:
        """Get ordered list of dependencies for an artifact."""
        artifact = self.get(artifact_type)
        if not artifact:
            return []

        chain = []
        for dep_str in artifact.metadata.dependencies:
            try:
                dep_type = ArtifactType(dep_str)
                # Recursively get dependencies
                chain.extend(self.get_dependency_chain(dep_type))
                chain.append(dep_type)
            except ValueError:
                continue

        return chain

    def export_session(self, export_path: Path) -> None:
        """Export current session to a directory."""
        shutil.copytree(self.session_path, export_path, dirs_exist_ok=True)
        logger.info(f"Exported session to {export_path}")

    def get_summary(self) -> str:
        """Get human-readable summary of current artifacts."""
        lines = [
            f"# Artifact Store Summary",
            f"Session: {self.session_id}",
            f"Artifacts: {len(self._artifacts)}",
            "",
            "## Current Artifacts:",
        ]

        for artifact_type, artifact in self._artifacts.items():
            meta = artifact.metadata
            lines.append(
                f"- **{artifact_type.value}** v{meta.version} "
                f"by {meta.producer.value} "
                f"({meta.updated_at.strftime('%Y-%m-%d %H:%M')})"
            )

        return "\n".join(lines)
