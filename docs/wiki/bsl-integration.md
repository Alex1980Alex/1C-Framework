---
confidence: 0.9
created_at: 2026-04-20 10:00:00+00:00
related:
- '[[_index]]'
- '[[overview]]'
- '[[triad-architecture]]'
- '[[skills-reference]]'
- '[[core-framework-separation]]'
sources:
- '[CLAUDE.md](../../CLAUDE.md) §BSL Development'
- '[16 ПОДКЛЮЧЕНИЕ_1С chapter](../framework documentation/16_ПОДКЛЮЧЕНИЕ_1С/16.1_Обзор_подключения_1С.md)'
- '[17 ТЕСТИРОВАНИЕ_1С chapter](../framework documentation/17_ТЕСТИРОВАНИЕ_1С/17.2_НАСТРОЙКА_VA_BDD.md)'
- '[36 AUTONOMOUS_DEBUG_CONTROL chapter](../framework documentation/36_AUTONOMOUS_DEBUG_CONTROL/36.7_HMR_Subprocess_Wrapper.md)'
status: active
tags:
- 1c
- bsl
- integration
- enterprise
- debug
title: BSL Integration
unified_id: 019e1e30-10a8-7b56-9b33-9abba2cfc457
updated_at: 2026-05-14 23:30:00+00:00
---

# BSL Integration

Подсистема интеграции PDF Framework с **1С:Предприятие 8.3.27**: индексация BSL-кода для семантического поиска, MCP-серверы для работы с данными и метаданными конфигурации, live RDBG debug, BDD-тестирование через Vanessa Automation. Каноническая БД config описаний — `1c-doc-research` skill (8 категорий кеша).

## Подсистемы (`src/bsl/`)

| Модуль | Назначение |
|---|---|
| `semantic_search/` | Vector search по BSL-коду (`bsl_code_v4_late` 24 455 chunks × 4096d Qwen3 Late Chunking; `bsl_code_v4` baseline) |
| `mcp_server/` | MCP-сервер `bsl-semantic-search` (tools: `bsl_search`, `bsl_object_info`, `bsl_coding_context`, `bsl_call_graph`, `bsl_dead_code`, `bsl_impact_analysis`, `bsl_rename_symbol`, `bsl_stats`) |
| `mcp_integration/` | Адаптеры между MCP протоколом и semantic_search |
| `sonar/` | Статический анализ BSL (linting, anti-patterns) |
| `finetuning/` | Тренировочные данные для fine-tune эмбеддеров на BSL-домене |

## Инструменты (`tools/`)

| Инструмент | Stack | Назначение |
|---|---|---|
| `auto-documenter/` | Node.js | BSL doc generator + MCP server (autoreview, autotestplan, generate_documentation) |
| `bsl-debugger/` | Node.js | OneScript-based static debugger (`bsl-debugger` MCP) |
| `bsl-debug-server/` | Python | Live RDBG wrapper (`mcp_debug_server.py`); HMR-вариант через `mcp_hmr_proc.py` |
| `ast-grep-mcp/` | — | AST-grep MCP (structural code search) |
| `bsl-semantic-diff/` | — | Semantic diff для BSL (rename/move detection) |

## MCP-серверы

| Сервер | Назначение |
|---|---|
| `bsl-semantic-search` | Vector search + symbol metadata по BSL |
| `bsl-platform-context` | API платформы 1С:Предприятие 8.3.27 (свойства, методы, типы) |
| `auto-documenter` | Авто-генерация docs/reviews/test-plans |
| `bsl-debugger` | Static debug (OneScript) |
| `1c-debug` | **Live** RDBG debug (production) |
| `1c-debug-hmr` | Live RDBG debug **с HMR**: edit wrapper'а без `/mcp reconnect`, persistent session через `.active.json` (см. [[ralph-wiggum]] — wrapper использует cascade auto-continue) |
| `1c-mcp-crud` | CRUD данных и метаданных: `execute_query`, `get_metadata`, `execute_code`, `get_event_log`, ссылки, права доступа |
| `edt-mcp` | EDT MCP — module structure, metadata details, content_assist, debug_launch |
| `mcp-onec-test-runner` | YaXUnit запуск, syntax check, build_project |

## 1C Pipeline (slash-команды)

Полный цикл разработки задачи в `configuration/<JIRA>/`:

```
/analyze-1c-task → /implement-1c-task → /write-1c-tests → /run-1c-tests
   │                  │                      │                  │
   ▼                  ▼                      ▼                  ▼
ANALYSIS-          BSL/XML            VA BDD              Resume от
REPORT.md          модификация        scenarios           упавшей секции
(5 фаз)            (8 этапов          с pre-scenario     с переисп.
                   v2.3.0)            TestDB check       артефактов
```

Скиллы цепочки:

- [`analyze-1c-task-v2`](../../.claude/skills/analyze-1c-task-v2/SKILL.md) — 5-фазная методология анализа (Требования → Объекты → Алгоритм → План → Верификация); SDD-интеграция (OpenSpec delta-specs, approval gate, brownfield validation)
- [`implement-1c-task`](../../.claude/skills/implement-1c-task/SKILL.md) — 8-этапный pipeline v2.3.0 (Этап 0 Preflight + EDT-MCP + 1c-mcp-crud + bsl-debug-server). Preflight выбирает один из 4 режимов: Full / Code-only / Read-only verify / Read-only research
- [`va-bdd-testing`](../../.claude/skills/va-bdd-testing/SKILL.md) — Vanessa Automation BDD test authoring. Stage 4a pre-scenario TestDB check
- Цепочный прогон: `tools/vanessa/run-bdd.ps1 -OutputJson -RunId`, изолированные `build/reports/runs/<RunId>/`, `.run-state.json` для resume

## Debug stack (live)

```
Claude Code MCP client
       │
       ▼
1c-debug-hmr MCP server
       │
       ▼
mcp_hmr_proc.py wrapper (Python subprocess, HMR-enabled)
       │
       ▼
RDBG протокол → http://localhost:1550 (ragent -debug -http)
       │
       ▼
1С:Предприятие cluster (localhost:1541)
```

25 debug tools: `debug_connect`, `debug_set_breakpoint`, `debug_set_logpoint` (tracepoint с `{expr}` placeholders → JSONL), `debug_stack_trace`, `debug_variables`, `debug_evaluate`, `debug_step`, `debug_arm_warm_rphosts`, `debug_arm_next_rphost`, `debug_break_on_next`, exception bps, replay session, coverage register/export. См. [§36.7 HMR Subprocess Wrapper](../framework%20documentation/36_AUTONOMOUS_DEBUG_CONTROL/36.7_HMR_Subprocess_Wrapper.md) + skill [`1c-debug-hmr`](../../.claude/skills/1c-debug-hmr/SKILL.md).

## Embedding pipeline (BSL)

```
.bsl/.os файлы → BSL parser (AST extraction)
                     │
                     ▼
              Chunking по методам/процедурам/функциям
              + payload: chunk_id, module_path, name, params,
                calls, signature, region, line_start/end
                     │
                     ▼
              TEI Qwen3-Embedding-8B (4096d, last-token pooling)
                     │
                     ▼
              Qdrant bsl_code_v4_late (Late Chunking pooling, production)
              + bsl_code_v4 (std pooling, research baseline)
                     │
                     ▼
        bsl-semantic-search MCP server (search_code, find_similar)
```

Late Chunking — поздняя агрегация чанков перед embedding'ом, даёт +recall на multi-method вопросах. Production retrieval recall@10 = 0.567 (+26% vs E5 baseline).

## Skills 1С Pipeline (9)

`1c-doc-research`, `1c-mcp-crud`, `bsl-development`, `bsl-refactoring-workflow`, `bsl-symbol-editing`, `va-bdd-testing`, `analyze-1c-task-v2`, `implement-1c-task`, `1c-debug-hmr`. См. [[skills-reference]] для триггеров.

## Тесты

YaXUnit (BSL unit tests) + VA BDD (UI scenarios). Cэтапный пайплайн через [`mcp-onec-test-runner`](../../.claude/skills/run-1c-tests/SKILL.md) MCP — `run_all_tests`, `run_module_tests`, `check_syntax_designer_modules`, `check_syntax_edt`, `build_project`, `dump_config`.

## Связано

- [[overview]] § Memory — wiki entities/ авто-экспортируются из knowledge graph (включая BSL-сущности через `wiki-pipeline`)
- [[triad-architecture]] — 1C-специфичные hooks: `bsl-tool-router.py`, `implement-1c-task-preflight.py`, `analyze-1c-task-preflight.py`
- [[hooks-reference]] § 1С preflight chain
