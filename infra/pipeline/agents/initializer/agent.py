"""
INITIALIZER Agent - Main orchestrator.

Coordinates codebase scanning, file selection, context generation, and caching.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from agents.initializer.models import (
    InitializerConfig,
    InitializerInput,
    InitializerOutput,
    ProjectStructure,
    ContextReport,
    RelevantFile,
)
from agents.initializer.codebase_scanner import CodebaseScanner, scan_directory
from agents.initializer.file_selector import FileSelector, select_relevant_files
from agents.initializer.context_generator import ContextGenerator, generate_context
from agents.initializer.context_cache import (
    ContextCache,
    CacheEntry,
    get_cache,
    cache_context,
    get_cached_context,
    is_cache_valid,
)


@dataclass
class InitializerResult:
    """Result of initialization process."""

    success: bool
    context_report: Optional[ContextReport] = None
    cache_hit: bool = False
    scan_time_ms: float = 0
    total_time_ms: float = 0
    error_message: Optional[str] = None

    @property
    def summary(self) -> str:
        """Get result summary."""
        if not self.success:
            return f"Error: {self.error_message}"

        return (
            f"Success: {self.context_report.project_structure.total_files} files, "
            f"{len(self.context_report.relevant_files)} relevant, "
            f"{'cached' if self.cache_hit else 'scanned'} in {self.total_time_ms:.0f}ms"
        )


class InitializerAgent:
    """
    INITIALIZER Agent - Context analyzer for Development Pipeline.

    Responsibilities:
    1. Scan codebase to understand project structure
    2. Generate context.md for other agents
    3. Select relevant files for task
    4. Cache context for reuse

    Usage:
        agent = InitializerAgent()
        result = agent.run(
            project_id="GKSTCPLK-1996",
            project_path="src/projects/configuration/...",
            task_description="Добавить регистр накопления"
        )
    """

    def __init__(self, config: Optional[InitializerConfig] = None) -> None:
        """
        Initialize agent.

        Args:
            config: Agent configuration
        """
        self.config = config or InitializerConfig()
        self.scanner = CodebaseScanner(self.config)
        self.selector = FileSelector(self.config)
        self.generator = ContextGenerator(self.config)
        self.cache = get_cache(config=self.config)

    def run(
        self,
        project_id: str,
        project_path: str,
        task_description: str,
        force_rescan: bool = False,
        output_dir: Optional[str] = None,
    ) -> InitializerResult:
        """
        Run initialization process.

        Args:
            project_id: Project identifier
            project_path: Path to project root
            task_description: Task description for file selection
            force_rescan: Force rescan ignoring cache
            output_dir: Directory to save context.md

        Returns:
            InitializerResult with context report
        """
        start_time = datetime.now()

        try:
            # Check cache
            if not force_rescan and is_cache_valid(project_path):
                cached = get_cached_context(project_path)
                if cached:
                    # Create minimal result from cache
                    end_time = datetime.now()
                    total_ms = (end_time - start_time).total_seconds() * 1000

                    # We need to recreate ContextReport from cached data
                    # For now, return cached markdown
                    return InitializerResult(
                        success=True,
                        context_report=None,  # Would need full reconstruction
                        cache_hit=True,
                        scan_time_ms=0,
                        total_time_ms=total_ms,
                    )

            # Scan codebase
            scan_start = datetime.now()
            structure = self.scanner.scan(project_path)
            scan_end = datetime.now()
            scan_ms = (scan_end - scan_start).total_seconds() * 1000

            # Select relevant files
            relevant_files = self.selector.select(
                structure=structure,
                task_description=task_description,
                limit=self.config.max_relevant_files,
            )

            # Generate context report
            context_report = self.generator.generate(
                project_id=project_id,
                structure=structure,
                task_description=task_description,
                relevant_files=relevant_files,
            )

            # Save to file if output_dir specified
            if output_dir:
                output_path = Path(output_dir)
                self.generator.save_to_file(context_report, output_path)

            # Cache result
            cache_context(project_path, context_report)

            end_time = datetime.now()
            total_ms = (end_time - start_time).total_seconds() * 1000

            return InitializerResult(
                success=True,
                context_report=context_report,
                cache_hit=False,
                scan_time_ms=scan_ms,
                total_time_ms=total_ms,
            )

        except FileNotFoundError as e:
            return InitializerResult(
                success=False,
                error_message=f"Project path not found: {e}",
            )
        except PermissionError as e:
            return InitializerResult(
                success=False,
                error_message=f"Permission denied: {e}",
            )
        except Exception as e:
            return InitializerResult(
                success=False,
                error_message=f"Unexpected error: {e}",
            )

    def run_from_input(self, input_data: InitializerInput) -> InitializerOutput:
        """
        Run from structured input.

        Args:
            input_data: InitializerInput with all parameters

        Returns:
            InitializerOutput with results
        """
        result = self.run(
            project_id=input_data.project_id,
            project_path=input_data.project_path,
            task_description=input_data.task_description,
            force_rescan=input_data.force_rescan,
            output_dir=input_data.output_dir,
        )

        return InitializerOutput(
            success=result.success,
            context_report=result.context_report,
            context_markdown=(
                result.context_report.markdown_content
                if result.context_report else ""
            ),
            relevant_files=(
                result.context_report.relevant_files
                if result.context_report else []
            ),
            project_structure=(
                result.context_report.project_structure
                if result.context_report else None
            ),
            cache_hit=result.cache_hit,
            processing_time_ms=result.total_time_ms,
            error_message=result.error_message,
        )

    def invalidate_cache(self, project_path: str) -> bool:
        """
        Invalidate cache for project.

        Args:
            project_path: Path to project

        Returns:
            True if cache was invalidated
        """
        return self.cache.invalidate(project_path)

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        return self.cache.get_stats()


def create_initializer(
    config: Optional[InitializerConfig] = None
) -> InitializerAgent:
    """
    Create INITIALIZER agent instance.

    Args:
        config: Optional configuration

    Returns:
        Configured InitializerAgent
    """
    return InitializerAgent(config)


def run_initializer(
    project_id: str,
    project_path: str,
    task_description: str,
    force_rescan: bool = False,
    output_dir: Optional[str] = None,
    config: Optional[InitializerConfig] = None,
) -> InitializerResult:
    """
    Run INITIALIZER agent.

    Convenience function for quick initialization.

    Args:
        project_id: Project identifier
        project_path: Path to project root
        task_description: Task description
        force_rescan: Force rescan ignoring cache
        output_dir: Directory for context.md
        config: Optional configuration

    Returns:
        InitializerResult with context report
    """
    agent = InitializerAgent(config)
    return agent.run(
        project_id=project_id,
        project_path=project_path,
        task_description=task_description,
        force_rescan=force_rescan,
        output_dir=output_dir,
    )


def initialize_project(
    project_path: str,
    task_description: str = "",
    output_dir: Optional[str] = None,
) -> Optional[ContextReport]:
    """
    Initialize project and get context report.

    Simplest interface for INITIALIZER.

    Args:
        project_path: Path to project
        task_description: Optional task description
        output_dir: Optional output directory

    Returns:
        ContextReport if successful, None otherwise
    """
    # Extract project_id from path
    project_id = Path(project_path).name

    result = run_initializer(
        project_id=project_id,
        project_path=project_path,
        task_description=task_description or "общий анализ проекта",
        output_dir=output_dir,
    )

    return result.context_report if result.success else None


def get_project_context(
    project_path: str,
    task_description: str = "",
) -> str:
    """
    Get project context as markdown string.

    Args:
        project_path: Path to project
        task_description: Optional task description

    Returns:
        Markdown content or error message
    """
    report = initialize_project(project_path, task_description)

    if report:
        return report.markdown_content
    else:
        return f"# Error\n\nCould not initialize project: {project_path}"
