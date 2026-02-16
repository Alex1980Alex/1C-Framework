# Gap Roadmap: SOTA RAG 2025-2026

**Источник:** [project-gap-analysis.md](../../.claude/skills/tech-research/cache/project-gap-analysis.md)
**Дата:** 2026-02-15
**Версия проекта:** v0.33.1 (Phase 43)

## Структура

| Приоритет | Файл | Задач | Подзадач | Effort | Impact |
|-----------|-------|-------|----------|--------|--------|
| **P0 — Фундамент** | [GAP_P0_FOUNDATION.md](GAP_P0_FOUNDATION.md) | 3 | 38 | 6-10 дней | HIGH |
| **P1 — Качество поиска** | [GAP_P1_SEARCH_QUALITY.md](GAP_P1_SEARCH_QUALITY.md) | 4 | 42 | 7-10 дней | HIGH |
| **P2 — Production** | [GAP_P2_PRODUCTION.md](GAP_P2_PRODUCTION.md) | 4 | 45 | 7-12 дней | HIGH-MED |
| **P3 — Передовые технологии** | [GAP_P3_ADVANCED.md](GAP_P3_ADVANCED.md) | 4 | 36 | 10-18 дней | MED |
| **P4 — Масштабирование** | [GAP_P4_SCALING.md](GAP_P4_SCALING.md) | 3 | 26 | 5-8 дней | MED-LOW |
| **Итого** | | **18** | **187** | **35-58 дней** | |

## Матрица критичности

```
                    HIGH Impact
                        │
           F1(CI/CD)  F3(Langfuse)  Q1(Embedding)
           F2(Tests)               P1(Neo4j)     A2(BGE-M3)
                        │
  LOW Effort ───────────┼──────────── HIGH Effort
                        │
           Q3(SSE)    P4(Routing)   A1(ColPali)
           P2(Docker)  P3(Guards)   A3(Agentic)
                        │
                    LOW Impact
```

## Рекомендованная последовательность

```
МЕСЯЦ 1: P0 — Фундамент
  Неделя 1: F1 (CI/CD) + F2.1-F2.4 (pre-commit, conftest)
  Неделя 2: F2.5-F2.11 (unit tests)
  Неделя 3: F3 (Langfuse) + Quick Wins
  Неделя 4: Buffer + стабилизация

МЕСЯЦ 2: P1 — Качество поиска
  Неделя 1: Q1 (Embedding upgrade)
  Неделя 2: Q3 (LLM Token Streaming)
  Неделя 3: Q4 (Contextual Retrieval)
  Неделя 4: Q2 (Late Chunking)

МЕСЯЦ 3: P2 — Production Readiness
  Неделя 1: P1 (Neo4j graph store)
  Неделя 2: P2 (Docker production) + P4 (Model Routing)
  Неделя 3: P3 (Guardrails)
  Неделя 4: Integration testing

МЕСЯЦ 4: P3+P4 — Инновации + Масштабирование
  Неделя 1-2: A2 (BGE-M3) + A1 (ColPali)
  Неделя 3: A3 (Agentic RAG) + S1 (Async Queue)
  Неделя 4: A4 (Propositions) + S2-S3
```

## Зависимости между задачами

```
F1 (CI/CD) ──┐
F2 (Tests) ──┤
             ├── Все P1 задачи требуют F1+F2 для валидации
F3 (Langfuse)┘
             │
Q1 (Embed) ──┤── A2 (BGE-M3) зависит от Q1
Q3 (SSE) ────┤── Улучшает UX для всех агентов
Q4 (Context) ┘
             │
P1 (Neo4j) ──┤── S3 (Incremental Graph) зависит от P1
P4 (Routing) ┘── Улучшает cost для A3 (Agentic)
```

## Текущие сильные стороны (не трогать)

- Section-First Pipeline (опережает индустрию)
- Ralph Wiggum self-correction (13 точек)
- Hooks+Skills+MCP Triad (уникальная архитектура)
- Hybrid Loader (4 уровня, 100% coverage)
- 14 search strategies (больше чем LlamaIndex/LangChain)
- Qdrant native RRF (на уровне SOTA)
- Semantic Cache (на уровне SOTA)

## Нумерация фаз

| Gap Phase | Framework Phase | Описание |
|-----------|----------------|----------|
| F1 | Phase 44 | CI/CD Pipeline |
| F2 | Phase 45 | Test Suite |
| F3 | Phase 46 | Langfuse Observability |
| Q1 | Phase 47 | Embedding Upgrade |
| Q2 | Phase 48 | Late Chunking |
| Q3 | Phase 49 | LLM Token Streaming |
| Q4 | Phase 50 | Contextual Retrieval |
| P1 | Phase 51 | Neo4j Graph Store |
| P2 | Phase 52 | Docker Production |
| P3 | Phase 53 | Guardrails |
| P4 | Phase 54 | Model Routing |
| A1 | Phase 55 | ColPali Visual Retrieval |
| A2 | Phase 56 | BGE-M3 Unified Model |
| A3 | Phase 57 | Agentic RAG |
| A4 | Phase 58 | Proposition Chunking |
| S1 | Phase 59 | Async Queue |
| S2 | Phase 60 | Multi-tenant Isolation |
| S3 | Phase 61 | Incremental Graph |
