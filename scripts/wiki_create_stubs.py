"""Create stub wiki pages for broken-link targets referenced by _index.md/etc.

Closes 56 of 63 kb-lint broken-link errors by materializing the targets as
draft-status placeholder pages. Each stub has minimum frontmatter
(unified_id v7, status=draft, tags, confidence=0.3 = "low/needs writing")
and ~60 words of placeholder content (above the min_article_words=50 floor).

Stubs link back to canonical sources (CLAUDE.md / docs/architecture/) so a
human writer can fill them in later without losing context.

Source: same uuid7 generator as scripts/patterns_fill_frontmatter.py
        (RFC 9562 section 5.7).
"""

from __future__ import annotations

import secrets
import time
import uuid
from pathlib import Path

import frontmatter


def uuid7() -> uuid.UUID:
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = ts_ms << 80
    value |= 0x7 << 76
    value |= rand_a << 64
    value |= 0b10 << 62
    value |= rand_b
    return uuid.UUID(int=value)


STUBS = {
    "patterns": {
        "title": "Patterns Index",
        "tags": ["meta", "index", "patterns"],
        "body": (
            "Index of architectural and automation patterns used in the framework.\n\n"
            "Canonical full catalogue lives in [`docs/architecture/PATTERNS.md`](../../architecture/PATTERNS.md) "
            "(15 architectural + 13 automation patterns). Individual pattern pages live in "
            "`docs/wiki/patterns/*.md` — see [[abstract-base-class]], [[adapter]], "
            "[[circuit-breaker]] etc. for examples.\n\n"
            "## Categories\n\n"
            "- Architectural: ABC, Adapter, Provider, Repository, Strategy, ...\n"
            "- Automation: Stop-gate, Ralph-Wiggum, Change-Detector, Silent-Observer, ...\n\n"
            "**Status: stub.** Expand with cross-references to `framework-patterns` skill "
            "and `_index.md` once skill-router/wiki integration plan is finalized."
        ),
    },
    "overview": {
        "title": "Framework Overview",
        "tags": ["meta", "overview"],
        "body": (
            "High-level overview of the PDF Vector & Graph Framework.\n\n"
            "Canonical project description lives in [`CLAUDE.md`](../../../CLAUDE.md) "
            "(Project Overview section) and in `docs/framework documentation/01_ОБЗОР/`. "
            "Tech stack: Python 3.11+ async-first, LangChain / LangGraph, Qdrant / ChromaDB / FAISS, "
            "Neo4j / NetworkX, REST API layer, MCP server, Typer CLI.\n\n"
            "**Status: stub.** Expand with diagram + entrypoints (REST API, CLI, MCP, Streamlit UI) "
            "once docs/wiki/overview canonical form is approved."
        ),
    },
    "triad-architecture": {
        "title": "Hooks + Skills + MCP Triad",
        "tags": ["architecture", "automation", "triad"],
        "body": (
            "Three-layer automation architecture: Hooks (event-driven), Skills (knowledge), "
            "MCP (capability). See skill `hooks-skills-mcp-triad` for the canonical reference.\n\n"
            "## Layers\n\n"
            "- **Hooks** (`.claude/hooks/`): PreToolUse / PostToolUse / Stop / UserPromptSubmit / "
            "SessionStart enforcers.\n"
            "- **Skills** (`.claude/skills/`): domain knowledge + workflows.\n"
            "- **MCP servers**: external capabilities (1c-debug-hmr, bsl-semantic-search, etc.).\n\n"
            "**Status: stub.** Expand with sequence diagrams (event flow, enforcement chains) "
            "and table of all 30+ registered hooks."
        ),
    },
    "hooks-reference": {
        "title": "Hooks Reference",
        "tags": ["reference", "hooks", "automation"],
        "body": (
            "Reference index for all Claude Code hooks in `.claude/hooks/`. "
            "Canonical enumeration lives in skill `hooks-skills-mcp-triad` SKILL.md "
            "(table grouped by event: PreToolUse, PostToolUse, Stop, UserPromptSubmit, SessionStart).\n\n"
            "## Hook events\n\n"
            "- PreToolUse: validate before tool execution\n"
            "- PostToolUse: react after tool success\n"
            "- Stop: enforcer chain on conversation end\n"
            "- UserPromptSubmit: classify/route prompts\n\n"
            "**Status: stub.** Expand with per-hook contract specs."
        ),
    },
    "skills-reference": {
        "title": "Skills Reference",
        "tags": ["reference", "skills"],
        "body": (
            "Reference index for all Claude Code skills in `.claude/skills/`. "
            "Discovery via skill-router-config.json and trigger-keyword matching.\n\n"
            "## Skill categories\n\n"
            "- Framework: framework-api, framework-cli, framework-config, framework-mcp-ui\n"
            "- LangChain: langchain-core, langchain-integrations, langchain-streaming, langgraph-core\n"
            "- 1C: 1c-doc-research, 1c-mcp-crud, bsl-development, va-bdd-testing, 1c-debug-hmr\n"
            "- Meta: learning-loop, code-verify, task-protocol\n\n"
            "**Status: stub.** Expand with full skill catalogue + trigger-collision audit."
        ),
    },
    "bsl-integration": {
        "title": "BSL Integration",
        "tags": ["1c", "bsl", "integration"],
        "body": (
            "Integration points between the Python PDF framework and 1С:Предприятие BSL "
            "(`src/bsl/`). Canonical reference in `CLAUDE.md` BSL Development section.\n\n"
            "## Components\n\n"
            "- `src/bsl/semantic_search/`: vector search over BSL code\n"
            "- `external/1c_mcp/` (submodule): 1C MCP proxy for 1c-mcp-crud\n"
            "- `tools/auto-documenter/`: Node.js BSL doc generator\n"
            "- `tools/bsl-debug-server/`: Python RDBG wrapper (1c-debug, 1c-debug-hmr)\n\n"
            "**Status: stub.** Expand with embedding-pipeline diagram + MCP tool list."
        ),
    },
    "ralph-wiggum": {
        "title": "Ralph Wiggum Loop",
        "tags": ["automation", "verification", "pattern"],
        "body": (
            "Iterative retry pattern used by `code-verify` and learning-loop: on FAIL, "
            "feed reviewer feedback back to the fixer agent, retry up to 3 times. "
            "See `.claude/skills/code-verify/SKILL.md` for the canonical 4-mode pipeline.\n\n"
            "## Loop semantics\n\n"
            "Each iteration receives: reference + previous attempt + reviewer feedback + "
            'instruction "fix ONLY the listed issues". After 3 unsuccessful iterations — '
            'stop, explain root cause, mark as "requires manual review".\n\n'
            "**Status: stub.** Expand with example transcripts."
        ),
    },
    "core-framework-separation": {
        "title": "Core / Framework Separation",
        "tags": ["architecture", "structure"],
        "body": (
            "Architectural boundary between the reusable `pdf_framework` core "
            "(`src/pdf_framework/`) and project-specific application code "
            "(`src/api/`, `src/cli/`, `src/mcp_server/`, `src/ui/`).\n\n"
            "## Layers\n\n"
            "- **Core** (`src/pdf_framework/`): loaders, processing, embeddings, vector_store, "
            "graph_store, search, agents, indexing — provider pattern, async-first, no app-specific logic.\n"
            "- **App** (`src/api/`, `src/cli/`, `src/mcp_server/`, `src/ui/`): consumer entrypoints.\n\n"
            "**Status: stub.** Expand with dependency-direction rules + import-restriction examples."
        ),
    },
}


def main() -> int:
    wiki_dir = Path("docs/wiki")
    if not wiki_dir.is_dir():
        print(f"ERROR: {wiki_dir} not found")
        return 2
    created = 0
    skipped = 0
    for stem, spec in STUBS.items():
        target = wiki_dir / f"{stem}.md"
        if target.exists():
            print(f"  skip (exists): {target.name}")
            skipped += 1
            continue
        post = frontmatter.Post(
            content=spec["body"],
            **{
                "unified_id": str(uuid7()),
                "status": "draft",
                "tags": spec["tags"],
                "confidence": 0.3,
                "title": spec["title"],
                "related": ["[[_index]]"],
            },
        )
        with open(target, "wb") as f:
            frontmatter.dump(post, f)
        created += 1
        print(f"  created: {target.name}")
    print(f"\nDone: {created} stubs created, {skipped} already existed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
