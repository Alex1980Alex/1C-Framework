#!/usr/bin/env python3
"""
Hook: docs-change-enforcer
Event: Stop
Matcher: (none — fires on every stop attempt)
Purpose: Block Claude from stopping if source code changed but corresponding
         documentation wasn't updated in the same session.

         Workaround for docs-change-tracker (PostToolUse) not firing
         due to Claude Code bug #6305.

         Maps code changes → documentation domains and checks for staleness.
         Works alongside git-commit-enforcer (uncommitted files) and
         task-enforcer (pending mandatory tasks).

Timeout: 10s

Exit codes:
  0 = allow stop (docs up to date or no code changes)
  2 = block stop (stale documentation detected)

Pattern: Enforcer (поведенческий подпаттерн триады — Цикл принуждения).

Flow:
  1. Stop fires → hook runs
  2. Collect all files changed in session (uncommitted + recent commits)
  3. Separate code files from doc/skill files
  4. For each code file, find matching domain via CODE_TO_DOMAIN mapping
  5. Check if domain's docs or skills were also updated in the session
  6. If code changed but docs/skills NOT updated → block stop with instructions
  7. If all docs up to date → allow stop
"""

import json
import os
import subprocess
import sys
from pathlib import Path

# Core path resolution for shared modules
_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
_USER_HOOKS = os.path.join(os.path.expanduser("~"), ".claude", "hooks")
if os.path.isdir(os.path.join(_USER_HOOKS, "shared")):
    sys.path.insert(0, _USER_HOOKS)
sys.path.insert(0, _HOOK_DIR)

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
COOLDOWN_FILE = PROJECT_ROOT / "data" / "docs-enforcer-last-block.txt"
COOLDOWN_MINUTES = 30  # After blocking once, allow stop for this duration

# ═══════════════════════════════════════════════════════════════════════════
# DOMAIN MAPPING: code prefix → (docs subdirectory, skill name)
# Compact version of docs-change-tracker.py _CODE_TO_DOCS_SKILLS
# Source of truth for fine-grained mapping: docs-change-tracker.py
# ═══════════════════════════════════════════════════════════════════════════

DOCS_BASE = "docs/framework documentation"

CODE_TO_DOMAIN = [
    # code_prefix                           docs_subdir              skill_name
    ("src/pdf_framework/search/",           "04_ПОИСК",              "search-pipeline-debug"),
    ("src/pdf_framework/agents/",           "05_RAG_АГЕНТЫ",         "agent-orchestration"),
    ("src/pdf_framework/loaders/",          "03_ИНДЕКСАЦИЯ",         "indexing-pipeline"),
    ("src/pdf_framework/processing/",       "03_ИНДЕКСАЦИЯ",         "indexing-pipeline"),
    ("src/pdf_framework/indexing/",         "03_ИНДЕКСАЦИЯ",         "indexing-pipeline"),
    ("src/pdf_framework/graph_store/",      "03_ИНДЕКСАЦИЯ",         "graph-operations"),
    ("src/pdf_framework/embeddings/",       "02_БЫСТРЫЙ_СТАРТ",     "embedding-models"),
    ("src/pdf_framework/vector_store/",     "04_ПОИСК",              "qdrant-operations"),
    ("src/pdf_framework/config/",           "02_БЫСТРЫЙ_СТАРТ",     "framework-config"),
    ("src/pdf_framework/evaluation/",       "08_ОЦЕНКА_КАЧЕСТВА",   "evaluation-benchmark"),
    ("src/pdf_framework/feedback/",         "08_ОЦЕНКА_КАЧЕСТВА",   "evaluation-benchmark"),
    ("src/pdf_framework/optimization/",     "08_ОЦЕНКА_КАЧЕСТВА",   "evaluation-benchmark"),
    ("src/pdf_framework/callbacks/",        "07_КЭШИРОВАНИЕ",       "framework-caching"),
    ("src/pdf_framework/multitenancy/",     "09_АДМИНИСТРИРОВАНИЕ",  "deployment"),
    ("src/pdf_framework/observability/",    "09_АДМИНИСТРИРОВАНИЕ",  "deployment"),
    ("src/pdf_framework/guardrails/",       "10_УСТРАНЕНИЕ_НЕПОЛАДОК", "framework-troubleshooting"),
    ("src/api/routes/",                     "06_ИНТЕРФЕЙСЫ",         "framework-api"),
    ("src/api/middleware/",                 "09_АДМИНИСТРИРОВАНИЕ",  "deployment"),
    ("src/api/app.py",                     "06_ИНТЕРФЕЙСЫ",         "framework-api"),
    ("src/cli/",                           "06_ИНТЕРФЕЙСЫ",         "framework-cli"),
    ("src/mcp_server/",                    "06_ИНТЕРФЕЙСЫ",         "pdf-knowledge"),
    ("src/ui/",                            "06_ИНТЕРФЕЙСЫ",         "pdf-knowledge"),
    ("src/workers/",                       "09_АДМИНИСТРИРОВАНИЕ",  "deployment"),
    ("src/pdf_framework/utils/",           "01_ОБЗОР",              "pdf-knowledge"),
    # BSL (1C Enterprise) modules
    ("src/bsl/",                           "06_ИНТЕРФЕЙСЫ",         "bsl-development"),
    ("src/shared/llm_rotation/",           None,                    "llm-rotation"),
    ("src/shared/",                        "01_ОБЗОР",              "pdf-knowledge"),
    ("src/memory/",                        "01_ОБЗОР",              "pdf-knowledge"),
]

# ═══════════════════════════════════════════════════════════════════════════
# SKIP_PATTERNS: files that NEVER need documentation tracking.
# Gitignore-first: .gitignore handles build artifacts, venvs, data/.
# These patterns handle semantic exclusions git can't know about.
# ═══════════════════════════════════════════════════════════════════════════
SKIP_PATTERNS = [
    # Documentation itself (editing docs doesn't require more docs)
    "docs/",
    "claude.md",
    "memory.md",
    "skill.md",
    "readme.md",
    "changelog.md",
    # Internal hook/cache state
    "/cache/",
    "/__pycache__/",
    "hook-todos",
    "active-todos",
    "auto-git-save",
    "_index.json",
    ".lock",
    # Git/env internals
    ".gitignore",
    ".git/",
    ".env",
    # Local permissions (per-user runtime, not project code)
    "settings.local.json",
    # Ralph state files (runtime, not code)
    ".ralph_",
    # Scripts, batch files, and tests (utility, not core product code)
    "scripts/",
    ".bat",
    ".sh",
    "tests/",
    # Agent configs and subagent settings
    ".claude/agents/",
    ".claude/settings-subagent",
    # Hook configs (documented in CLAUDE.md Hooks Infrastructure)
    "code-skill-patterns.json",
    # CI/CD workflows (documented in CLAUDE.md Skill Router Eval)
    ".github/",
    # MCP configs, tooling, docker, infra (infrastructure, not product code)
    ".mcp/",
    ".mcp.json",
    "tools/",
    "docker/",
    "infra/",
    "pyproject.toml",
    ".env.example",
    "mcp-server.log",
    # Root-level infra files (Dockerfiles, compose, logs)
    "dockerfile",
    "docker-compose",
    ".log",
    # Empty module markers (no logic to document)
    "__init__.py",
    # 1C project task folders (separate repos, not framework code)
    "src/projects/",
    # BSL infrastructure (separate from PDF framework, documented in bsl-development skill)
    "src/bsl/",
    # Claude Code commands (slash commands, not product code)
    ".claude/commands/",
    # Temporary helper scripts (prefixed with underscore, auto-deleted)
    "_write_test",
    "_gen_test",
    "_gen_eval",
]


def _is_infra_file(filepath: str) -> bool:
    """Check if file is a hook, skill config, or settings file."""
    fp = filepath.replace("\\", "/").lower()
    if fp.startswith(".claude/hooks/") and fp.endswith(".py"):
        # Skip cache, __pycache__ (framework internals)
        if any(s in fp for s in ["/cache/", "/__pycache__/"]):
            return False
        return True
    # settings.json is project infra; settings.local.json is per-user
    # runtime permissions that change on every permission grant — skip it
    if fp == ".claude/settings.json":
        return True
    # Skill config files (not SKILL.md itself — that IS the doc)
    if fp.startswith(".claude/skills/") and not fp.endswith("/skill.md"):
        if fp.endswith((".json", ".py")):
            return True
        # ADR and cache .md files are internal knowledge, not user-facing docs
        if "/adr/" in fp or "/cache/" in fp:
            return True
    return False


def _should_skip(filepath: str) -> bool:
    """Check if file should be skipped from CODE_TO_DOMAIN staleness check.

    Infrastructure files (.claude/hooks/, .claude/skills/) are skipped here
    because they are handled separately by find_stale_infra().
    """
    fp = filepath.replace("\\", "/").lower()
    if any(s.lower() in fp for s in SKIP_PATTERNS):
        return True
    # Infrastructure files handled by find_stale_infra()
    if _is_infra_file(filepath):
        return True
    return False


def _is_doc_file(filepath: str) -> bool:
    """Check if file is in docs/framework documentation/."""
    return "docs/framework documentation/" in filepath.replace("\\", "/").lower()


def _is_skill_file(filepath: str) -> bool:
    """Check if file is a SKILL.md file."""
    return ".claude/skills/" in filepath.replace("\\", "/").lower()


def get_session_files() -> set:
    """Get all files changed in this session (uncommitted + recent commits).

    Uses 6-hour window to approximate session duration.
    Combines working tree changes with recently committed files.
    """
    files = set()

    # 1. Uncommitted changes (working tree + staged)
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain"],
            capture_output=True, text=True, encoding="utf-8", timeout=3,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                if not line or len(line) < 2:
                    continue
                fp = line[2:].lstrip().strip('"').replace("\\", "/")
                if fp:
                    files.add(fp)
    except Exception:
        pass

    # 2. Recently committed files (last 6 hours ≈ session window)
    try:
        r = subprocess.run(
            ["git", "log", "--since=6 hours ago", "--name-only", "--pretty="],
            capture_output=True, text=True, encoding="utf-8", timeout=5,
            cwd=str(PROJECT_ROOT),
        )
        if r.returncode == 0:
            for line in r.stdout.strip().splitlines():
                fp = line.strip().replace("\\", "/")
                if fp:
                    files.add(fp)
    except Exception:
        pass

    return files


def find_stale_infra(session_files: set) -> list:
    """Check if infrastructure changes (hooks/skills/settings) need CLAUDE.md update.

    Infrastructure = .claude/hooks/*.py, .claude/settings.json,
                     .claude/skills/*.(json|py)
    Documentation = CLAUDE.md at project root

    Returns list of stale entries (same format as find_stale_domains).
    """
    infra_changes = []
    claude_md_updated = False

    for fp in session_files:
        fp_norm = fp.replace("\\", "/").lower()
        if fp_norm == "claude.md" or fp_norm.endswith("/claude.md"):
            claude_md_updated = True
        if _is_infra_file(fp):
            infra_changes.append(fp)

    if infra_changes and not claude_md_updated:
        return [{
            "subdir": "CLAUDE.md (инфраструктура)",
            "skill": "hooks-skills-mcp-triad",
            "files": infra_changes,
        }]
    return []


def find_unmapped_changes(session_files: set) -> list:
    """Catch-all: files that passed skip check but don't match CODE_TO_DOMAIN or infra.

    These are files the system can't auto-route (e.g., tests/, scripts/,
    pyproject.toml, new top-level modules). Suggests /audit-docs skill.

    Returns list of stale entries (same format as find_stale_domains).
    """
    unmapped = []
    for fp in session_files:
        if _should_skip(fp):
            continue
        if _is_infra_file(fp):
            continue
        fp_lower = fp.replace("\\", "/").lower()
        matched = any(
            fp_lower.startswith(prefix.lower())
            for prefix, _, _ in CODE_TO_DOMAIN
        )
        if not matched:
            unmapped.append(fp)

    if unmapped:
        return [{
            "subdir": "UNMAPPED (используй /audit-docs)",
            "skill": "audit-docs",
            "files": unmapped,
        }]
    return []


def find_stale_domains(session_files: set) -> list:
    """Find code domains where docs weren't updated in the same session.

    Logic:
    - For each changed source code file, find its documentation domain
    - Check if ANY doc or skill in that domain was also changed in the session
    - If code changed but neither docs nor skills updated → domain is stale

    Returns list of dicts: {"subdir", "skill", "files"}.
    """
    # Collect doc/skill files from session for fast lookup
    doc_files = {f for f in session_files if _is_doc_file(f)}
    skill_files = {f for f in session_files if _is_skill_file(f)}

    # Track stale domains (deduped by doc_subdir)
    stale = {}  # doc_subdir → {"subdir": str, "skill": str, "files": [str]}

    for fp in session_files:
        if _should_skip(fp):
            continue

        fp_lower = fp.replace("\\", "/").lower()

        for code_prefix, doc_subdir, skill in CODE_TO_DOMAIN:
            if fp_lower.startswith(code_prefix.lower()):
                # Check if this domain's docs were also updated in session
                if doc_subdir is not None:
                    doc_dir_prefix = f"{DOCS_BASE}/{doc_subdir}/".lower()
                    has_doc_update = any(
                        d.replace("\\", "/").lower().startswith(doc_dir_prefix)
                        for d in doc_files
                    )
                else:
                    has_doc_update = True  # No docs required for this domain

                # Also check if the matching skill was updated
                skill_prefix = f".claude/skills/{skill}/".lower()
                has_skill_update = any(
                    s.replace("\\", "/").lower().startswith(skill_prefix)
                    for s in skill_files
                )

                if not has_doc_update and not has_skill_update:
                    if doc_subdir not in stale:
                        stale[doc_subdir] = {
                            "subdir": doc_subdir,
                            "skill": skill,
                            "files": [],
                        }
                    stale[doc_subdir]["files"].append(fp)

                break  # Only match first domain per file

    return list(stale.values())


def main():
    """Check for stale documentation. Block stop if found."""
    # Invocation timer
    try:
        from shared.invocation_logger import InvocationTimer
        timer = InvocationTimer("docs-change-enforcer", event="Stop").start()
    except Exception:
        timer = None

    try:
        # Read stdin (required by Claude Code hook protocol)
        try:
            sys.stdin.buffer.read()
        except Exception:
            pass

        # Cooldown: if we already blocked recently, allow stop (prevents infinite loop)
        if COOLDOWN_FILE.exists():
            try:
                import time
                mtime = COOLDOWN_FILE.stat().st_mtime
                age_min = (time.time() - mtime) / 60
                if age_min < COOLDOWN_MINUTES:
                    if timer:
                        timer.log(outcome="allow-cooldown")
                    sys.exit(0)
            except Exception:
                pass

        session_files = get_session_files()
        if not session_files:
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        stale = find_stale_domains(session_files)
        stale += find_stale_infra(session_files)
        stale += find_unmapped_changes(session_files)
        if not stale:
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        # Build reason message
        items = []
        total_code_files = 0
        for entry in stale[:8]:
            doc_subdir = entry["subdir"]
            skill = entry["skill"]
            code_files = entry["files"]
            total_code_files += len(code_files)

            cf_names = ", ".join(Path(f).name for f in code_files[:3])
            if len(code_files) > 3:
                cf_names += f" (+{len(code_files) - 3})"

            items.append(
                f"  📄 {DOCS_BASE}/{doc_subdir}/\n"
                f"     Skill: {skill}\n"
                f"     Код: {cf_names}"
            )

        items_str = "\n".join(items)
        extra = len(stale) - 8
        if extra > 0:
            items_str += f"\n  ... и ещё {extra} область(ей)"

        reason = (
            f"[DOCS-ENFORCER] Документация не обновлена для {len(stale)} области(ей)!\n"
            f"Изменено {total_code_files} файл(ов) кода без обновления документации.\n\n"
            f"{items_str}\n\n"
            "Действия:\n"
            "1. Используй скилл /audit-docs для автоматического обновления\n"
            "2. Или вручную обнови документацию в указанных разделах\n"
            "3. Обнови SKILL.md если изменился API/конфиг\n"
            "4. После обновления можешь завершить."
        )

        # Write cooldown marker so next Stop attempt passes
        try:
            COOLDOWN_FILE.parent.mkdir(parents=True, exist_ok=True)
            COOLDOWN_FILE.write_text(
                f"blocked at session with {len(stale)} stale domain(s)",
                encoding="utf-8",
            )
        except Exception:
            pass

        output = {"decision": "block", "reason": reason}
        out_bytes = json.dumps(output, ensure_ascii=False).encode("utf-8")
        sys.stdout.buffer.write(out_bytes + b"\n")
        sys.stdout.buffer.flush()
        if timer:
            timer.log(outcome="block")
        sys.exit(2)  # Block stop

    except Exception as e:
        # Graceful degradation: allow stop on any error
        if timer:
            timer.log(outcome="error", error=f"{type(e).__name__}: {e}")
        sys.exit(0)


if __name__ == "__main__":
    main()
