# F-1 — Планирование архитектуры: автопроводка pipeline-state из 1С-preflight (ядро G3)

**Срез роадмапа:** [260614](../../docs/roadmap/260614_ROADMAP_1C_COMMANDS_4STAGE_ALIGNMENT.md) → B′ F-1 (раздел «Финальное решение F.5»).
**Решение:** [ADR-019 accepted](../../.claude/skills/architecture-research/adr/019-1c-commands-4stage-pipeline-alignment.md) (B′ «мост через хуки»).

## Цель (что закрываем)
**G3** (главная боль): `/implement-1c-task` правит BSL, но не обновляет `pipeline/<slug>/.pipeline-state.json` →
ADR-018 `pipeline-protocol-stop.py` hard-блокирует завершение сессии (нужен ручной пайплайн). F-1 делает так, что
**слэш-маршрут `/analyze-1c-task`→`/implement-1c-task` сам заводит/трогает pipeline-state** → Stop-хук доволен без ручного пайплайна.

## Подход (B′ — мост через ХУКИ, методику не трогаем)
Проводка состояния — в **существующих preflight-хуках** (детерминированно), НЕ правкой команд/скиллов:
- [`analyze-1c-task-preflight.py`](../../.claude/hooks/analyze-1c-task-preflight.py) — UPS на `/analyze-1c-task` (`detect_slash_command`), уже логирует, не блокирует.
- [`implement-1c-task-preflight.py`](../../.claude/hooks/implement-1c-task-preflight.py) — UPS на `/implement-1c-task`, аналогично.
Оба → вызвать `pipeline_state.init_task(<slug>)` (идемпотентно: повторный init не затирает прогресс, ставит `CURRENT`,
обновляет `.pipeline-state.json` `updated_at`). Этого достаточно: `pipeline-protocol-stop._pipeline_used_since(start)`
проверяет любой `*/.pipeline-state.json` с `updated_at >= старт сессии` → preflight (ранний UPS) удовлетворяет инвариант.

## Точки интеграции (что уже существует — переиспользуем)
- `pipeline_state.init_task(slug, title)` — **идемпотентен** (verified, строки 132–162): existing → возвращает, ставит CURRENT.
- `pipeline_state.resolve_current()`, `mark_done()` — для будущей stage-проводки (F-1.5).
- `detect_slash_command(prompt)` — общий детектор (используется обоими preflight + slash-tracker).
- `pipeline-protocol-stop._pipeline_used_since()` — **потребитель** (его инвариант и закрываем).

## Граница F-1 (минимальный обратимый срез)
- **В F-1:** `ensure_pipeline` (init/touch) в ОБОИХ preflight + slug-деривация из prompt (JIRA `[A-Z]{2,}-\d+` → fallback slug). → закрывает G3-блок.
- **НЕ в F-1 (следующие срезы):** stage-advancement 1→2→3→4 по записи `ANALYSIS-REPORT`/`IMPLEMENTATION-PROGRESS` (PostToolUse done-детектор) = **F-1.5**; гейт G4 (`pipeline-gate` на `/implement-1c-task`) = **F-2**; relabel + TOOL-PLAN-шаблон = **F-3/W**.

## Инварианты / риски
- **Behavior-preserving для не-1С пайплайна:** helper зовётся ТОЛЬКО из 1С-preflight; generic `pl-*` не затронут.
- **Никогда не ломать preflight:** вызов best-effort (`try/except` → pass); если pipeline_state упал — preflight продолжает (debug-probe + systemMessage без изменений).
- **Кириллица/slug:** slug — ASCII (JIRA-код или транслит/`YYMMDD`), `pipeline/<slug>` остаётся ASCII (инвариант ADR-017).
- **Откат:** снять 2 вызова из preflight + удалить helper. Single rollback.

## DoD этапа (проверяется на Тестировании)
Прогон `/analyze-1c-task <…>` (или синтетический preflight) оставляет `pipeline/<slug>/.pipeline-state.json`;
`pipeline-protocol-stop` на 1С-сессии с правками → exit 0 без ручного пайплайна; generic-пайплайн без регрессий; unit-тест зелёный.
