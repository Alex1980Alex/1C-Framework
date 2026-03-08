# Миграция 1C-Enterprise_Framework -> 1С-Framework

**Дата:** 2026-03-06 | **Статус:** ПЛАНИРОВАНИЕ | **Версия:** v1.0

## Источник

- **Проект:** `D:\1C-Enterprise_Framework`
- **Launcher:** `scripts\claude.bat` → профиль #7 (lazy-mcp)
- **Команда:** `claude --strict-mcp-config --mcp-config ".mcp\lazy-mcp.json"`
- **Экономия:** ~5k токенов вместо ~372k = **95%**

## Целевой проект

- **Проект:** `D:\1С-Framework` (PDF Vector & Graph Framework, v0.33+)
- **Инфраструктура:** Hooks + Skills + MCP триада, Task Protocol, Ralph Wiggum

---

## Карта фаз

| Tier | Фаза | Файл | Статус | Описание |
|------|-------|------|--------|----------|
| **1** | [44](PHASE_44_INFRASTRUCTURE.md) | PHASE_44_INFRASTRUCTURE.md | DONE | Инфраструктура: директории, deps, MCP, hooks, skills |
| **1** | [45](PHASE_45_BSL_SEMANTIC_SEARCH.md) | PHASE_45_BSL_SEMANTIC_SEARCH.md | DONE | BSL Semantic Search + SonarQube |
| **2** | [46](PHASE_46_MCP_1C_INTEGRATION.md) | PHASE_46_MCP_1C_INTEGRATION.md | DONE | MCP 1C Integration + Server |
| **2** | [47](PHASE_47_AUTO_DOCUMENTER.md) | PHASE_47_AUTO_DOCUMENTER.md | DONE | Auto-Documenter (Profile #7) |
| **2** | [48](PHASE_48_BSL_DEBUGGER.md) | PHASE_48_BSL_DEBUGGER.md | DONE | BSL Debugger (10 tools) |
| **3** | [49](PHASE_49_UNIFIED_MEMORY.md) | PHASE_49_UNIFIED_MEMORY.md | DONE | Unified Memory System (4 системы) |
| **3** | [50](PHASE_50_LLM_ROTATION.md) | PHASE_50_LLM_ROTATION.md | DONE | LLM Rotation Service |
| **3** | [51](PHASE_51_TASK_PIPELINE.md) | PHASE_51_TASK_PIPELINE.md | DONE | Task Master + Dev Pipeline |
| **4** | [52](PHASE_52_SERENA_LSP.md) | PHASE_52_SERENA_LSP.md | DONE | Serena LSP Integration |
| **4** | [53](PHASE_53_BSL_FINETUNING.md) | PHASE_53_BSL_FINETUNING.md | DONE | BSL Fine-tuning (Qwen2.5-Coder) |
| **4** | [54](PHASE_54_INFRASTRUCTURE_TOOLS.md) | PHASE_54_INFRASTRUCTURE_TOOLS.md | DONE | Lazy MCP + Docker + AST Grep |
| **5** | [55](PHASE_55_INTEGRATION_CLEANUP.md) | PHASE_55_INTEGRATION_CLEANUP.md | DONE | E2E тесты, docs, cleanup |

## Аналитика

- [TECHNOLOGY_COMPARISON.md](TECHNOLOGY_COMPARISON.md) — Сравнение технологий: миграция vs текущий фреймворк + лучшие GitHub решения (ТОП-10)

## Сводка

- **Компоненты:** 18 модулей
- **MCP серверы:** 15 native + 20+ on-demand = 34 total
- **Трудозатраты:** ~57 часов → **~44 часов** (с учётом замен на готовые решения)
- **Основной документ:** [MIGRATION_1C_ENTERPRISE_FRAMEWORK.md](MIGRATION_1C_ENTERPRISE_FRAMEWORK.md)

## Граф зависимостей

```
Фаза 44 (Infrastructure)
  ├── Фаза 45 (BSL Search + Sonar)
  │     └── Фаза 53 (Fine-tuning)
  ├── Фаза 46 (MCP 1C) ─────┐
  ├── Фаза 47 (Auto-Doc) ───┤
  ├── Фаза 48 (Debugger) ───┤── Фаза 54 (Infra Tools)
  ├── Фаза 49 (Memory) ─────┤
  │     └── Фаза 51 (Task+Pipeline)
  ├── Фаза 50 (LLM Rotation)│
  ├── Фаза 52 (Serena) ─────┘
  └── ВСЕ → Фаза 55 (Integration)
```

## Профиль #7: lazy-mcp

### 15 Native серверов

| # | Сервер | Runtime | Timeout |
|---|--------|---------|---------|
| 1 | `serena` | Python venv | 180s |
| 2 | `ast-grep-mcp` | Python venv | 60s |
| 3 | `bsl-platform-context` | Java (Zulu-17) | 30s |
| 4 | `1c-docs-rag` | Python | 7200s |
| 5 | `memory-ai` | Python 3.13 | 60s |
| 6 | `bsl-semantic-search` | Python FastMCP | 60s |
| 7 | **`auto-documenter`** | **Node.js** | **180s** |
| 8 | `ripgrep` | Node.js | 30s |
| 9 | `deep-code-reasoning` | Node.js | 180s |
| 10 | `conversation-memory` | Python 3.13 | 60s |
| 11 | `task-master-ai` | npx | 180s |
| 12 | `markitdown` | npx | 120s |
| 13 | `vector-memory` | Python venv | 60s |
| 14 | `skill-learning` | Python venv | 60s |
| 15 | `lazy-mcp` | Python venv | 30s |

### 9 On-demand категорий

`/1c-development` `/documentation` `/memory` `/learning` `/file-operations` `/reasoning` `/web` `/utils` `/routing` `/browser` `/bridges`
