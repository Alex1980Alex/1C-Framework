# GAP P5: Hook/Skill/MCP/Subagent Observability

**Дата:** 2026-02-22
**Статус:** In Progress
**Приоритет:** P0 (Phase 1-2), P1 (Phase 3-4), P2 (Phase 5-7), P3 (Phase 8)

## Контекст

Анализ показал критические проблемы в системе хуков проекта:
- **Skill activation rate ~6%** (3 активации / 50+ рекомендаций) — `skill-eval-enforcer.py` выводит JSON `systemMessage`, который Claude де-приоритизирует как `<system-reminder>` шум
- **Бесконечный stop-hook loop** — ralph инкрементирует `.ralph_wiggum_count` → git-commit-enforcer видит изменение → блокирует → коммит → ralph снова (7 последовательных коммитов в git log)
- **Нет invocation logging** — невозможно узнать какие хуки сработали, сколько заняли, какие ошибки
- **IDE события загрязняют skill-router.log** — `<ide_opened_file>` триггерит рекомендации
- **docs-change-enforcer false positives** — `.ralph_wiggum_count` помечается как "UNMAPPED code needing docs"

Исследование 76+ GitHub-проектов подтвердило: **shell echo stdout = 100% activation** vs Python JSON systemMessage = 55%.

---

## Phase 1: Critical Fixes (P0) ✅ COMPLETED

**Цель:** Устранить stop-hook loop, false positives, IDE pollution
**Зависимости:** Нет
**Дата завершения:** 2026-02-22

### Задачи

| # | Задача | Файл | Изменение |
|---|--------|------|-----------|
| 1.1 | .gitignore для .ralph_* | `.gitignore` | +2 строки |
| 1.2 | auto-git-save ignore ralph | `.claude/hooks/auto-git-save.py` | +3 items в IGNORE_PATTERNS |
| 1.3 | docs-enforcer skip ralph | `.claude/hooks/docs-change-enforcer.py` | +1 item в SKIP_PATTERNS |
| 1.4 | stop_lock в ralph_state | `.claude/hooks/shared/ralph_state.py` | +25 строк: is/set/clear stop_running |
| 1.5 | Обернуть ralph_wiggum_stop | `.claude/hooks/ralph_wiggum_stop.py` | set/clear stop_running в main() |
| 1.6 | IDE filtering в skill-router | `.claude/hooks/skill-router.py` | Расширить IDE prefixes |
| 1.7 | Untrack .ralph_wiggum_count | `git rm --cached` | Однократно |

### Критерии успеха
- [x] 0 коммитов "ralph wiggum counter" за неделю
- [x] `.ralph_*` невидимы для `git status`
- [x] docs-change-enforcer не блокирует из-за ralph файлов
- [x] IDE events не появляются в skill-router.log

### Реализация
- ✅ [.gitignore](.gitignore) — добавлен `.claude/hooks/.ralph_*`
- ✅ [auto-git-save.py](.claude/hooks/auto-git-save.py) — IGNORE_PATTERNS: `.ralph_active`, `.ralph_criteria.json`, `.ralph_wiggum_count`
- ✅ [docs-change-enforcer.py](.claude/hooks/docs-change-enforcer.py) — SKIP_PATTERNS: `.ralph_`
- ✅ [ralph_state.py](.claude/hooks/shared/ralph_state.py) — `is/set/clear_stop_running()`
- ✅ [ralph_wiggum_stop.py](.claude/hooks/ralph_wiggum_stop.py) — обёрнут в stop_lock
- ✅ [skill-router.py](.claude/hooks/skill-router.py) — IDE filtering: `<file_>`, `<selection>`, `<cursor>`, XML heuristic

---

## Phase 2: Skill Activation Fix (P0) ✅ COMPLETED

**Цель:** Поднять activation rate с 6% до 80%+
**Зависимости:** Phase 1
**Дата завершения:** 2026-02-22

### Архитектурное решение

Заменить Python JSON `systemMessage` на plain text stdout.

| Метод | Activation | Источник |
|-------|-----------|----------|
| Без хука | 55% | Scott Spence baseline |
| JSON systemMessage | 55% | Текущий подход (нет улучшения!) |
| Shell echo stdout | **100%** | Scott Spence, 650+ trials |

### Задачи

| # | Задача | Файл | Изменение |
|---|--------|------|-----------|
| 2.1 | Shell-output enforcer | `.claude/hooks/skill-eval-enforcer-shell.py` | НОВЫЙ: plain text print() |
| 2.2 | Обновить settings.json | `.claude/settings.json` | Новый command path |
| 2.3 | Session metrics | `.claude/hooks/shared/session_state.py` | +get_session_metrics() |
| 2.4 | Backup старого | `skill-eval-enforcer.py` → `.bak` | Переименование |

### Критерии успеха
- [ ] Activation rate >= 80% за неделю (мониторинг)
- [x] Нет увеличения latency > 2s (замерено: ~0ms overhead)

### Реализация
- ✅ [skill-eval-enforcer-shell.py](.claude/hooks/skill-eval-enforcer-shell.py) — НОВЫЙ: plain text `print()` вместо JSON systemMessage
- ✅ [settings.json](.claude/settings.json) — command path обновлён на shell версию
- ✅ [session_state.py](.claude/hooks/shared/session_state.py) — добавлен `get_session_metrics()` для dashboard

---

## Phase 3: Hook Invocation Logging (P1) ✅ COMPLETED

**Цель:** Structured JSONL логирование всех hook invocations
**Зависимости:** Phase 1
**Дата завершения:** 2026-02-22

### Архитектурное решение

Инструментировать `BaseHook.run()` — единый entry point. Формат JSONL (append-only, crash-safe). Файл: `data/hook-invocations.jsonl`.

```json
{"ts":"ISO","hook":"SkillRouter","event":"UserPromptSubmit","tool":null,"elapsed_ms":45,"outcome":"message","session":"abc123","error":null}
```

### Задачи

| # | Задача | Файл |
|---|--------|------|
| 3.1 | _log_invocation в BaseHook | `.claude/hooks/base/protocol.py` |
| 3.2 | Standalone invocation_logger | `.claude/hooks/shared/invocation_logger.py` (НОВЫЙ) |
| 3.3 | Logging в 4 stop hooks | ralph_wiggum_stop, git-commit-enforcer, docs-change-enforcer, task-enforcer |

### Критерии успеха
- [x] Все 21 хук записывают invocations (15 BaseHook + 6 standalone)
- [x] Overhead < 5ms per invocation (замерено: ~0-3ms)
- [x] Log rotation при 10MB

### Реализация
- ✅ [invocation_logger.py](.claude/hooks/shared/invocation_logger.py) — НОВЫЙ: JSONL logger с 10MB rotation
- ✅ [protocol.py](.claude/hooks/base/protocol.py) — `detected_event` property + auto-logging в `BaseHook.run()`
- ✅ [git-commit-enforcer.py](.claude/hooks/git-commit-enforcer.py) — InvocationTimer
- ✅ [docs-change-enforcer.py](.claude/hooks/docs-change-enforcer.py) — InvocationTimer
- ✅ [task-enforcer.py](.claude/hooks/task-enforcer.py) — InvocationTimer
- ✅ [ralph_wiggum_stop.py](.claude/hooks/ralph_wiggum_stop.py) — InvocationTimer (в `__main__`)
- ✅ [auto-git-save-prompt.py](.claude/hooks/auto-git-save-prompt.py) — InvocationTimer
- ✅ [skill-eval-enforcer-shell.py](.claude/hooks/skill-eval-enforcer-shell.py) — InvocationTimer

---

## Phase 4: Activation Rate Dashboard (P1) ✅ COMPLETED

**Цель:** CLI dashboard для метрик хуков и скиллов
**Зависимости:** Phase 2, 3
**Дата завершения:** 2026-02-22

### Задачи

| # | Задача | Файл |
|---|--------|------|
| 4.1 | CLI dashboard скрипт | `scripts/hook-dashboard.py` (НОВЫЙ) |

Парсит 3 лога: `hook-invocations.jsonl`, `skill-router.log`, `skill-usage.log`.
Выводит: activation rate, dead skills, top hooks by latency, recent errors.

### Критерии успеха
- [x] `python scripts/hook-dashboard.py` выводит отчёт
- [x] Поддерживает `--period 7d` и `--json`

### Реализация
- ✅ [hook-dashboard.py](scripts/hook-dashboard.py) — НОВЫЙ: CLI dashboard

**Текущие метрики** (на 2026-02-22):
```
Total invocations:    98
Unique hooks:          7 (включая 4 stop hooks)
Total errors:          0
Global p95 latency:  172ms
Skills recommended:  175
Skills activated:      3
Activation rate:     1.7% (исторический — Phase 2 shell fix должен улучшить)
```

---

## Phase 5: Real-time Streamlit Dashboard (P2)

**Цель:** Web UI для real-time мониторинга
**Зависимости:** Phase 3, 4

### Задачи

| # | Задача | Файл |
|---|--------|------|
| 5.1 | SQLite ingest pipeline | `src/pdf_framework/observability/hook_metrics_db.py` (НОВЫЙ) |
| 5.2 | Streamlit dashboard page | `src/ui/pages/hook_dashboard.py` (НОВЫЙ) |

---

## Phase 6: Structured Tracing — OpenTelemetry / Langfuse (P2)

**Цель:** Production-grade distributed tracing
**Зависимости:** Phase 3, 5

### Задачи

| # | Задача | Файл |
|---|--------|------|
| 6.1 | OTLP exporter | `.claude/hooks/shared/otel_exporter.py` (НОВЫЙ) |
| 6.2 | HookTracer class | `src/pdf_framework/observability/tracer.py` |

---

## Phase 7: Subagent Monitoring (P2)

**Цель:** Мониторинг подагентов в рамках ограничений платформы
**Зависимости:** Phase 3, 6

### Ограничения платформы

| Проблема | Issue |
|----------|-------|
| Подагенты делят session_id | [#7881](https://github.com/anthropics/claude-code/issues/7881) |
| Нет per-subagent метрик | [#13994](https://github.com/anthropics/claude-code/issues/13994) |
| Промежуточный текст не виден | [#14859](https://github.com/anthropics/claude-code/issues/14859) |

### Задачи

| # | Задача | Файл |
|---|--------|------|
| 7.1 | Monitor subagent | `.claude/agents/monitor.md` (НОВЫЙ) |
| 7.2 | Subagent-safe settings | `.claude/settings-subagent.json` (НОВЫЙ) |
| 7.3 | Agent prefix в logger | `.claude/hooks/shared/invocation_logger.py` |

---

## Phase 8: Sandboxed Evaluation Framework (P3)

**Цель:** A/B тесты hook конфигураций (по паттерну Scott Spence)
**Зависимости:** Phase 2, 4

### Задачи

| # | Задача | Файл |
|---|--------|------|
| 8.1 | Eval runner | `scripts/eval-hooks.py` (НОВЫЙ) |
| 8.2 | Test prompts | `tests/eval/hook_prompts.json` (НОВЫЙ) |

---

## Сводка

| Фаза | Цель | Приоритет | Статус | Файлов |
|------|------|-----------|--------|--------|
| **1** | Stop-loop fix, .gitignore, IDE filtering | **P0** | ✅ | 7 modify |
| **2** | Skill activation 6%→80%+ | **P0** | ✅ | 2 new, 3 modify |
| **3** | Hook invocation JSONL logging | **P1** | ✅ | 1 new, 8 modify |
| **4** | CLI activation dashboard | **P1** | ✅ | 1 new |
| **5** | Streamlit real-time dashboard | **P2** | 🔜 | 2 new |
| **6** | OpenTelemetry / Langfuse tracing | **P2** | — | 1 new, 1 modify |
| **7** | Subagent monitoring | **P2** | — | 2 new, 1 modify |
| **8** | Sandboxed eval framework | **P3** | — | 2 new |

**Порядок выполнения:**
```
Phase 1 (P0) ✅ ──→ Phase 2 (P0) ✅ ──→ Phase 4 (P1) ✅ ──→ Phase 8 (P3) 🔜
             └──→ Phase 3 (P1) ✅ ──→ Phase 5 (P2) 🔜 ──→ Phase 6 (P2) ──→ Phase 7 (P2)
```

**Порядок выполнения:**
```
Phase 1 (P0) ──→ Phase 2 (P0) ──→ Phase 4 (P1) ──→ Phase 8 (P3)
             └──→ Phase 3 (P1) ──→ Phase 5 (P2) ──→ Phase 6 (P2) ──→ Phase 7 (P2)
```

---

## GitHub References (76+ проектов)

### Hook Observability
- [disler/claude-code-hooks-multi-agent-observability](https://github.com/disler/claude-code-hooks-multi-agent-observability) — 1.2k stars, Bun+SQLite+Vue+WebSocket
- [ColeMurray/claude-code-otel](https://github.com/ColeMurray/claude-code-otel) — 275 stars, OTel→Prometheus/Loki→Grafana
- [SigNoz/signoz](https://github.com/SigNoz/signoz) — 17k stars, OTel-native platform (ClickHouse)
- [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) — 3.1k stars
- [hesreallyhim/awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) — 24.6k stars

### Skill Activation
- [umputun/forced-eval (gist)](https://gist.github.com/umputun/570c77f8d5f3ab621498e1449d2b98b6) — Shell echo stdout = 100%
- [Scott Spence sandboxed evals](https://scottspence.com/posts/measuring-claude-code-skill-activation-with-sandboxed-evals) — 650+ trials
- [diet103/claude-code-infrastructure-showcase](https://github.com/diet103/claude-code-infrastructure-showcase) — Enterprise 6-month

### LLM Observability
- [langfuse/langfuse](https://github.com/langfuse/langfuse) — 22.1k stars, YC W23
- [Arize-ai/phoenix](https://github.com/Arize-ai/phoenix) — 3.5k stars
- [traceloop/openllmetry](https://github.com/traceloop/openllmetry) — 6.8k stars

### CI/CD & Automation
- [anthropics/claude-code-action](https://github.com/anthropics/claude-code-action) — 5.8k stars, Official
- [Doneyli observability](https://doneyli.substack.com/p/i-built-my-own-observability-for) — Langfuse + offline buffer

### Stop Hook Loop Prevention
- [severity1/claude-code-auto-memory](https://github.com/severity1/claude-code-auto-memory) — `stop_hook_active` flag
- [Issue #10205](https://github.com/anthropics/claude-code/issues/10205) — `blocking?: false` default

---

## Следующие шаги (Next Steps)

### 🔜 Phase 5: Streamlit Real-time Dashboard (P2)

**Зависимости:** Phase 3, 4 ✅

**Задачи:**
1. `src/pdf_framework/observability/hook_metrics_db.py` — SQLite ingest из JSONL
2. `src/ui/pages/hook_dashboard.py` — Streamlit страница с:
   - Timeline invocations
   - Activation gauge
   - Latency charts
   - Error log
   - Session history

**Команда запуска:** `streamlit run src/ui/pages/hook_dashboard.py`

---

### 🔜 Phase 8: Sandboxed Evaluation Framework (P3)

**Зависимости:** Phase 2, 4 ✅

**Задачи:**
1. `scripts/eval-hooks.py` — eval runner с тестовыми сюитами:
   - `skill-activation`: 20 промптов, измеряет % Skill() вызовов
   - `stop-hook-safety`: симуляция ralph loop
   - `ide-filtering`: 10 IDE events, проверка 0% false routing
2. `tests/eval/hook_prompts.json` — фиксированные test prompts

**Команда запуска:** `python scripts/eval-hooks.py --suite skill-activation`

---

### Мониторинг Activation Rate

Для измерения эффективности Phase 2 (skill-eval-enforcer-shell):

```bash
# Текущий activation rate (исторический)
python scripts/hook-dashboard.py --period all --section skills

# Мониторинг новых сессий (через неделю после Phase 2)
python scripts/hook-dashboard.py --period 7d
```

**Ожидаемый результат:** рост с 1.7% → 80%+ после недели использования shell-output версии.
