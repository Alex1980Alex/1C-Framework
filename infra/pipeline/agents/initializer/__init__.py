"""
INITIALIZER Agent - контекстный анализатор для Development Pipeline.

Агент отвечает за:
- Сканирование codebase для понимания структуры проекта
- Генерацию context.md с релевантной информацией
- Определение файлов, затрагиваемых задачей
- Кеширование контекста для повторного использования

Компоненты:
- CodebaseScanner - сканирует структуру проекта
- ContextGenerator - генерирует context.md
- FileSelector - определяет релевантные файлы
- ContextCache - кеширует контекст
- InitializerAgent - главный оркестратор
"""

from agents.initializer.agent import (
    InitializerAgent,
    create_initializer,
    run_initializer,
)
from agents.initializer.codebase_scanner import (
    CodebaseScanner,
    detect_project_type,
    get_file_stats,
    scan_directory,
)
from agents.initializer.context_cache import (
    CacheEntry,
    ContextCache,
    cache_context,
    get_cached_context,
    invalidate_cache,
)
from agents.initializer.context_generator import (
    ContextGenerator,
    generate_context,
    generate_context_markdown,
)
from agents.initializer.file_selector import (
    FileSelector,
    rank_files_by_relevance,
    select_relevant_files,
)
from agents.initializer.models import (
    ContextReport,
    DependencyInfo,
    DirectoryInfo,
    # Dataclasses
    FileInfo,
    # Enums
    FileType,
    # Config
    InitializerConfig,
    InitializerInput,
    InitializerOutput,
    ModuleInfo,
    PatternInfo,
    ProjectStructure,
    ProjectType,
)

__all__ = [
    # Enums
    "FileType",
    "ProjectType",
    # Dataclasses
    "FileInfo",
    "DirectoryInfo",
    "ModuleInfo",
    "DependencyInfo",
    "PatternInfo",
    "ProjectStructure",
    "ContextReport",
    # Config
    "InitializerConfig",
    "InitializerInput",
    "InitializerOutput",
    # Scanner
    "CodebaseScanner",
    "scan_directory",
    "detect_project_type",
    "get_file_stats",
    # Generator
    "ContextGenerator",
    "generate_context",
    "generate_context_markdown",
    # Selector
    "FileSelector",
    "select_relevant_files",
    "rank_files_by_relevance",
    # Cache
    "ContextCache",
    "CacheEntry",
    "cache_context",
    "get_cached_context",
    "invalidate_cache",
    # Agent
    "InitializerAgent",
    "create_initializer",
    "run_initializer",
]
