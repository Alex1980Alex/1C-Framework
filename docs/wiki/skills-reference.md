---
confidence: 0.9
created_at: 2026-04-20 10:00:00+00:00
related:
- '[[_index]]'
- '[[overview]]'
- '[[triad-architecture]]'
- '[[hooks-reference]]'
- '[[bsl-integration]]'
- '[[patterns]]'
sources:
- '[.claude/skills/](../../.claude/skills/)'
- '[.claude/skills/skill-router-config.json](../../.claude/skills/skill-router-config.json)'
- '[11.6 Каталог скиллов](../framework documentation/11_СИСТЕМА_СКИЛЛОВ/11.6_Каталог_скиллов.md)'
status: active
tags:
- reference
- skills
- discovery
- triggers
title: Skills Reference
unified_id: 019e1e30-10a8-704c-927a-3bca7a6d7e54
updated_at: 2026-05-14 23:30:00+00:00
---

# Skills Reference

**86 skills** в [`.claude/skills/`](../../.claude/skills/). Каждый — это `SKILL.md` с YAML frontmatter (`description`, `triggers`) + workflow / commands / антипаттерны. Discovery через [`skill-router.py`](../../.claude/hooks/skill-router.py) hook (UPS) — Layer A keyword + Layer B fuzzy + Layer C TF-IDF scoring, конфиг [`skill-router-config.json`](../../.claude/skills/skill-router-config.json) (16 bundles v9).

Каноническая deep enumeration — [11.6 Каталог скиллов](../framework%20documentation/11_СИСТЕМА_СКИЛЛОВ/11.6_Каталог_скиллов.md).

## Категории

### 1С Development (9)

| Skill | Триггеры |
|---|---|
| [`1c-doc-research`](../../.claude/skills/1c-doc-research/SKILL.md) | '1С', '1C', 'справочник', 'BSL', 'реквизит', 'модуль' |
| [`1c-mcp-crud`](../../.claude/skills/1c-mcp-crud/SKILL.md) | 'запрос к базе 1С', 'execute_query', 'get_metadata', 'журнал регистрации' |
| [`bsl-development`](../../.claude/skills/bsl-development/SKILL.md) | 'BSL', 'модуль 1С', 'процедура BSL', 'обработка проведения' |
| [`bsl-refactoring-workflow`](../../.claude/skills/bsl-refactoring-workflow/SKILL.md) | 'symbol-first', 'BSL refactor', 'rename symbol', 'EDT refactoring' |
| [`bsl-symbol-editing`](../../.claude/skills/bsl-symbol-editing/SKILL.md) | 'symbol edit', 'replace method body', 'BSL метод' |
| [`va-bdd-testing`](../../.claude/skills/va-bdd-testing/SKILL.md) | 'BDD', 'Vanessa Automation', 'тест 1С', 'сценарий VA' |
| [`analyze-1c-task-v2`](../../.claude/skills/analyze-1c-task-v2/SKILL.md) | '/analyze-1c-task', '5 фаз', 'анализ задачи 1С' |
| [`implement-1c-task`](../../.claude/skills/implement-1c-task/SKILL.md) | '/implement-1c-task', 'реализация 1С', 'BSL pipeline' |
| [`1c-debug-hmr`](../../.claude/skills/1c-debug-hmr/SKILL.md) | 'отладка 1С', 'breakpoint BSL', 'RDBG', 'debug rphost' |

Pipeline: [[bsl-integration]] → `/analyze-1c-task` → `/implement-1c-task` → `/write-1c-tests` → `/run-1c-tests`.

### Framework Operations (12)

| Skill | Триггеры |
|---|---|
| `framework-api` | 'REST API pdf-framework', '/search/', 'FastAPI endpoints' |
| `framework-cli` | 'python -m src.cli', 'pdf-framework CLI' |
| `framework-config` | '.env pdf-framework', 'pydantic-settings', 'EMBEDDING__MODEL' |
| `framework-mcp-ui` | 'Gradio', 'Streamlit', 'QuickRAG', 'Components API' |
| `framework-caching` | 'семантический кэш', 'embedding cache', 'cache stats' |
| `framework-quickstart` | 'pip install pdf-framework', 'установка' |
| `framework-troubleshooting` | 'ConnectionError Qdrant', 'BM25 not found', 'ChromaDB corruption' |
| `framework-search` | 'найди в фреймворке', 'framework_code_v1', 'index_status' |
| `framework-patterns` | '15 архитектурных + 13 автоматизации', 'pattern catalogue' |
| `qdrant-operations` | 'qdrant collection', 'sparse vectors', 'snapshot', 'named vectors' |
| `embedding-models` | 'E5', 'BGE', 'ONNX', 'Qwen3', 'Giga-Embeddings' |
| `deployment` | 'deploy', 'docker', 'production', 'мультитенантность', 'JWT' |

### Search & Indexing (5)

`search-pipeline-debug`, `indexing-pipeline`, `graph-operations` (LightRAG/GraphRAG), `evaluation-benchmark` (RAGAS, NDCG), `agent-orchestration` (RAG/Self-RAG/research agents, LangGraph nodes).

### LangChain / LangGraph (8)

`langchain-core`, `langchain-integrations`, `langchain-streaming`, `langchain-tutorials`, `langchain-mcp-tools`, `langchain-multiagent`, `langgraph-core`, `langgraph-memory-persistence`, `langgraph-production`.

### Claude Code (10)

`claude-code-cli-interactive`, `claude-code-settings`, `claude-code-vscode`, `claude-code-terminal-ux`, `claude-code-subagents`, `claude-code-plugins`, `claude-code-programmatic`, `claude-code-admin`, `claude-code-github-actions`, `claude-code-hooks-bugs`.

### Hook Engineering (6)

`create-hook`, `hook-debugging`, `hook-enforcement-pattern`, `multi-level-hook-architecture`, `windows-hooks-paths`, `auto-git-save`.

### Memory & Learning (5)

`memory-unified`, `learning-loop`, `task-protocol`, `auto-memory` (instinctive — нет separate skill, см. system prompt), `skill-learning` (через MCP `skill-learning` server).

### Research & Verification (6)

`tech-research`, `1c-doc-research` (1С vertical), `architecture-research`, `code-verify`, `audit-docs`, `delegation-classifier`.

### Token Economy (3)

`z-ai-delegation`, `llm-rotation`, `tenacity-retry`.

### Wiki & Knowledge (4)

`wiki-pipeline` (export + sync), `obsidian-vault` (navigation), `doc-to-skill`, `doc-to-cache`.

### Misc / Specialized (~18)

`autoresearch`, `analyze-1c-research`, `triad-factory`, `hooks-skills-mcp-triad` (meta), `pdf-knowledge` (MCP), `prompt-engineering` (DSPy), `sandbox-execution`, `task-evaluation`, `brownfield-validate`, `git-commit-message`, `git-porcelain-parsing`, `openspec-*` (5: propose/apply/archive/explore/opsx-approve), `agent-orchestration`, ... — full inventory: `ls .claude/skills/`.

## Discovery (Skill Router)

```
USER PROMPT
   │
   ▼
Layer A: keyword match (substring on description + frontmatter triggers)
   │ score >= 1.0?  → recommend
   ▼
Layer B: fuzzy match (RapidFuzz token-set ratio) для опечаток
   │ score >= 0.7?  → recommend
   ▼
Layer C: TF-IDF cosine на bag-of-keywords из skill bundles
   │ top-3
   ▼
[SKILL-ROUTER] systemMessage → пользователю / Claude видны
```

Bundles в [`skill-router-config.json`](../../.claude/skills/skill-router-config.json) v9: 16 групп с weighted_keywords. Регулярная проверка через `framework-search` или `framework-patterns`.

## Skill format

```yaml
---
name: skill-slug
description: "Use this skill when ... Triggers: 'word1', 'word2'."
---

# Title

## Overview (2-4 sentences)

## Quick Reference / Table

## Commands / Workflow

## Antipatterns

## Files / Links
```

Limit: ≤ 500 lines. Min 3 antipatterns, 5 triggers, 1 non-redirect cross-link. Создание через `doc-to-skill`.

## Enforcement

Skill-First: [`code-skill-enforcer.py`](../../.claude/hooks/code-skill-enforcer.py) PreToolUse:Write|Edit|Bash блокирует пока `Skill()` не вызван. Конфиг [`shared/code-skill-patterns.json`](../../.claude/hooks/shared/code-skill-patterns.json) — pattern → required skill. Phantom-skill cleanup (2026-05-14, `784e1a57b`) убрал 9 ссылок на несуществующие skills.

Связано:

- [[triad-architecture]] § Skills section
- [[hooks-reference]] § Skill Router
- [[patterns]] → [[config-driven-routing]], [[router-classifier]], [[fuzzy-intent-detection]]
