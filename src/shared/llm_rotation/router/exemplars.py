"""Canonical exemplar prompts per delegation level.

Source: docs/roadmap/260320_ROADMAP_DELEGATION_LEARNING.md §Iteration 4.1
+ memory note feedback_repo_full_permission.md (architecture/debugging =
Never delegate).

Each level has 5-8 short examples representing the typical surface form
of prompts that should route there. Used by TrainedRouter for cosine
similarity classification against fresh user prompts.

Levels (matching src/shared/delegation_bandit.ACTIONS):
  - Soft   : 1-pass simple tasks, low risk if wrong → DELEGATE TO Z.AI
  - Medium : Multi-step but bounded scope            → DELEGATE TO Z.AI
  - Hard   : Multi-file / cross-module changes       → CLAUDE (with review)
  - Never  : Architecture / debugging / security     → CLAUDE (no delegate)

Update policy: extend lists when new patterns emerge from Langfuse
outcome corpus (§4.5.2 Iter 4 trained-from-outcomes). For now (bootstrap)
these are hand-curated from memory + past sessions.
"""

EXEMPLARS: dict[str, list[str]] = {
    "Soft": [
        "translate text to English",
        "format markdown table",
        "rename variable foo to bar",
        "add docstring to function",
        "fix typo in comment",
        "convert yaml to json",
        "fix indentation in file",
    ],
    "Medium": [
        "draft a roadmap entry for topic X",
        "write user-facing notes for the module",
        "generate unit tests from existing source",
        "produce a README for the project",
        "describe the API endpoint in OpenAPI",
        "extract changelog from git log",
        "explain the pattern in .claude/skills/",
    ],
    "Hard": [
        "implement processing module X with tests",
        "build POST /foo API endpoint",
        "add exponential backoff retry to LLM calls",
        "integrate a new embedding provider",
        "build PostToolUse hook for Y",
        "implement MCP server for Z",
        "build CLI command via Typer",
    ],
    "Never": [
        "debug the hook session-memory-save bug",
        "architectural choice for vector store",
        "review JWT security implications",
        "trace deadlock in orchestrator",
        "decide on the sync versus async migration path",
        "code-verify partial review of subagent output",
        "root-cause analysis for CI failure",
    ],
}
