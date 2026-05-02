"""Defaults for framework_search indexer."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Roots to walk. Repo-relative POSIX paths.
DEFAULT_INDEX_ROOTS: list[str] = [
    "src",
    "scripts",
    ".claude/hooks",
    ".claude/skills",
    "tools",
    "tests",
    "docs/architecture",
    "docs/framework documentation",
    "docs/roadmap",
    ".mcp",
]

# Single-file roots at repo root.
DEFAULT_INDEX_FILES: list[str] = [
    "CLAUDE.md",
    "AGENTS.md",
    ".mcp.json",
    "pyproject.toml",
    "README.md",
]

# File extension -> language label.
EXT_TO_LANGUAGE: dict[str, str] = {
    ".py": "python",
    ".md": "markdown",
    ".json": "json",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".ts": "typescript",
    ".toml": "text",
    ".yaml": "text",
    ".yml": "text",
    ".cfg": "text",
    ".ini": "text",
}

# Skip patterns (case-insensitive substring match against POSIX path).
SKIP_PATTERNS: list[str] = [
    "/__pycache__/",
    "/.venv/",
    "/venv/",
    "/node_modules/",
    "/.git/",
    "/dist/",
    "/build/",
    "/.pytest_cache/",
    "/.mypy_cache/",
    "/.ruff_cache/",
    "/data/",
    "/cache/",
    "/tmp/",
    "/logs/",
    "/.obsidian/",
    "/configuration/",                    # BSL projects -> bsl_code_v4_late
    # Imported third-party reference docs (huge, not "framework code")
    "/docs/documentation/Lang Chain Docs/",
    "/docs/documentation/Claude Code Docs/",
    "/docs/documentation/Протокол контекста модели/",
    "/docs/documentation/Language Server Protocol/",
    # Vendored third-party tools — not our framework code.
    # NB: dirname pruning sees repo-relative POSIX paths WITHOUT leading slash,
    # so top-level dir patterns must NOT start with `/` (otherwise `/tools/X/`
    # won't match the actual probe value `tools/X/`).
    "tools/serena/",                      # vendored Serena agent toolkit
    "tools/multilspy-fork/",              # vendored microsoft/multilspy fork
    "tools/sonar-scanner",                # vendored binary distribution
    "tools/coverage41c/",                 # vendored Java coverage tool
    "package-lock.json",                  # auto-generated, no semantic value
]

# Max bytes per file (skip giant generated/binary-ish files).
MAX_FILE_BYTES: int = 512 * 1024  # 512 KB

# Defaults for embedder + collection.
DEFAULT_COLLECTION: str = "framework_code_v1"
DEFAULT_TEI_URL: str = "http://localhost:8080"
DEFAULT_QDRANT_URL: str = "http://localhost:6333"
DEFAULT_BATCH_SIZE: int = 16          # framework chunks heterogeneous; smaller batch = lower OOM risk
DEFAULT_TEI_CLIENT_BATCH: int = 32    # TEI MAX_CLIENT_BATCH_SIZE default
MAX_CHUNK_CHARS: int = 8000           # ~2k tokens, well under MAX_INPUT_LENGTH=4096
