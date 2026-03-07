"""
Project Resolver for Development Pipeline.

Provides unified project parameter resolution for all subagents.
Accepts either project name (folder name) or full path.

Example usage:
    resolver = ProjectResolver()
    info = resolver.resolve("251222_GKSTCPLK-1996")
    # or
    info = resolver.resolve("D:/1C-Enterprise_Framework/src/projects/configuration/251222_GKSTCPLK-1996")
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional
import os
import re


@dataclass
class ProjectInfo:
    """Resolved project information.

    Attributes:
        path: Full absolute path to project root
        name: Project folder name (e.g., "251222_GKSTCPLK-1996")
        project_id: Extracted project ID (e.g., "GKSTCPLK-1996")
        project_type: Type of project (configuration, extension, dataprocessor)
    """

    path: Path
    name: str
    project_id: str
    project_type: str = "unknown"

    @property
    def src_path(self) -> Path:
        """Path to src directory within project."""
        return self.path / "src"

    @property
    def docs_path(self) -> Path:
        """Path to docs directory within project."""
        return self.path / "docs"

    @property
    def artifacts_path(self) -> Path:
        """Path to artifacts directory within project."""
        return self.path / "artifacts"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "path": str(self.path),
            "name": self.name,
            "project_id": self.project_id,
            "project_type": self.project_type,
            "src_path": str(self.src_path),
            "docs_path": str(self.docs_path),
            "artifacts_path": str(self.artifacts_path),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectInfo":
        """Create from dictionary."""
        return cls(
            path=Path(data["path"]),
            name=data["name"],
            project_id=data["project_id"],
            project_type=data.get("project_type", "unknown"),
        )


class ProjectResolverError(Exception):
    """Raised when project cannot be resolved."""
    pass


class ProjectResolver:
    """Resolves project parameter to ProjectInfo.

    Accepts either:
    - Project name (folder name): "251222_GKSTCPLK-1996"
    - Full path: "D:/1C-Enterprise_Framework/src/projects/configuration/251222_GKSTCPLK-1996"

    Searches in known project directories if only name is provided.
    """

    # Default search directories (relative to framework root)
    DEFAULT_SEARCH_PATHS = [
        "src/projects/configuration",
        "src/projects/extensions",
        "src/projects/dataprocessors",
        "src/projects/reports",
    ]

    # Pattern to extract project ID from folder name
    # Examples: 251222_GKSTCPLK-1996 -> GKSTCPLK-1996
    #          GKSTCPLK-1996 -> GKSTCPLK-1996
    PROJECT_ID_PATTERN = re.compile(r"(?:\d{6}_)?([A-Z]+-\d+)", re.IGNORECASE)

    def __init__(
        self,
        framework_root: Optional[Path] = None,
        additional_search_paths: Optional[List[str]] = None,
    ):
        """Initialize resolver.

        Args:
            framework_root: Root directory of 1C-Enterprise_Framework.
                           Defaults to auto-detection.
            additional_search_paths: Extra paths to search for projects.
        """
        self.framework_root = framework_root or self._detect_framework_root()
        self.search_paths = self._build_search_paths(additional_search_paths or [])

    def _detect_framework_root(self) -> Path:
        """Auto-detect framework root directory."""
        # Try common locations
        candidates = [
            Path("D:/1C-Enterprise_Framework"),
            Path.cwd(),
            Path(__file__).parent.parent,  # development-pipeline -> root
        ]

        for candidate in candidates:
            if (candidate / "CLAUDE.md").exists():
                return candidate
            if (candidate / "src" / "projects").exists():
                return candidate

        # Fallback to current directory
        return Path.cwd()

    def _build_search_paths(self, additional: List[str]) -> List[Path]:
        """Build list of absolute search paths."""
        paths = []

        # Add default paths
        for rel_path in self.DEFAULT_SEARCH_PATHS:
            full_path = self.framework_root / rel_path
            if full_path.exists():
                paths.append(full_path)

        # Add additional paths
        for path_str in additional:
            path = Path(path_str)
            if path.is_absolute():
                if path.exists():
                    paths.append(path)
            else:
                full_path = self.framework_root / path_str
                if full_path.exists():
                    paths.append(full_path)

        return paths

    def _is_path(self, project: str) -> bool:
        """Check if input looks like a file path."""
        # Contains path separators
        if "/" in project or "\\" in project:
            return True
        # Contains drive letter (Windows)
        if len(project) >= 2 and project[1] == ":":
            return True
        return False

    def _extract_project_id(self, name: str) -> str:
        """Extract project ID from folder name.

        Examples:
            251222_GKSTCPLK-1996 -> GKSTCPLK-1996
            GKSTCPLK-1996 -> GKSTCPLK-1996
            my_project -> my_project (fallback to name)
        """
        match = self.PROJECT_ID_PATTERN.search(name)
        if match:
            return match.group(1).upper()
        return name

    def _detect_project_type(self, path: Path) -> str:
        """Detect project type based on path or contents."""
        path_str = str(path).lower()

        if "configuration" in path_str:
            return "configuration"
        elif "extension" in path_str:
            return "extension"
        elif "dataprocessor" in path_str:
            return "dataprocessor"
        elif "report" in path_str:
            return "report"

        # Check for project structure indicators
        src_path = path / "src"
        if src_path.exists():
            # Check for Configuration.xml or similar markers
            if (src_path / "Configuration.xml").exists():
                return "configuration"
            if any(src_path.glob("*.cfe")):
                return "extension"

        return "unknown"

    def _find_by_name(self, name: str) -> Optional[Path]:
        """Find project by name in search paths."""
        for search_path in self.search_paths:
            candidate = search_path / name
            if candidate.exists() and candidate.is_dir():
                return candidate

        # Try partial match (name might be partial)
        for search_path in self.search_paths:
            if search_path.exists():
                for item in search_path.iterdir():
                    if item.is_dir() and name.lower() in item.name.lower():
                        return item

        return None

    def resolve(self, project: str) -> ProjectInfo:
        """Resolve project parameter to ProjectInfo.

        Args:
            project: Either project name or full path.
                    Examples:
                    - "251222_GKSTCPLK-1996"
                    - "GKSTCPLK-1996"
                    - "D:/1C-Enterprise_Framework/src/projects/configuration/251222_GKSTCPLK-1996"

        Returns:
            ProjectInfo with resolved paths and metadata.

        Raises:
            ProjectResolverError: If project cannot be found.
        """
        project = project.strip()

        if self._is_path(project):
            # Input is a path
            path = Path(project)
            if not path.exists():
                raise ProjectResolverError(f"Project path does not exist: {project}")
            if not path.is_dir():
                raise ProjectResolverError(f"Project path is not a directory: {project}")

            path = path.resolve()  # Get absolute path
            name = path.name
        else:
            # Input is a name, search for it
            found_path = self._find_by_name(project)
            if not found_path:
                # Try to find by project ID
                for search_path in self.search_paths:
                    if search_path.exists():
                        for item in search_path.iterdir():
                            if item.is_dir():
                                extracted_id = self._extract_project_id(item.name)
                                if extracted_id.lower() == project.lower():
                                    found_path = item
                                    break
                    if found_path:
                        break

            if not found_path:
                raise ProjectResolverError(
                    f"Project not found: {project}\n"
                    f"Searched in: {[str(p) for p in self.search_paths]}"
                )

            path = found_path.resolve()
            name = path.name

        project_id = self._extract_project_id(name)
        project_type = self._detect_project_type(path)

        return ProjectInfo(
            path=path,
            name=name,
            project_id=project_id,
            project_type=project_type,
        )

    def resolve_or_none(self, project: str) -> Optional[ProjectInfo]:
        """Resolve project, returning None if not found."""
        try:
            return self.resolve(project)
        except ProjectResolverError:
            return None

    def list_projects(self, project_type: Optional[str] = None) -> List[ProjectInfo]:
        """List all available projects.

        Args:
            project_type: Filter by type (configuration, extension, etc.)

        Returns:
            List of ProjectInfo for all found projects.
        """
        projects = []

        for search_path in self.search_paths:
            if not search_path.exists():
                continue

            for item in search_path.iterdir():
                if not item.is_dir():
                    continue

                try:
                    info = self.resolve(str(item))
                    if project_type is None or info.project_type == project_type:
                        projects.append(info)
                except ProjectResolverError:
                    continue

        return projects


# Global resolver instance for convenience
_default_resolver: Optional[ProjectResolver] = None


def get_resolver() -> ProjectResolver:
    """Get or create the default resolver instance."""
    global _default_resolver
    if _default_resolver is None:
        _default_resolver = ProjectResolver()
    return _default_resolver


def resolve_project(project: str) -> ProjectInfo:
    """Convenience function to resolve a project.

    Args:
        project: Project name or path.

    Returns:
        ProjectInfo with resolved paths and metadata.

    Example:
        >>> from shared.pipeline.project_resolver import resolve_project
        >>> info = resolve_project("251222_GKSTCPLK-1996")
        >>> print(info.path)
        D:/1C-Enterprise_Framework/src/projects/configuration/251222_GKSTCPLK-1996
    """
    return get_resolver().resolve(project)
