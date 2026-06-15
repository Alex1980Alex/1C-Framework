# F-1 — Кодирование (реализовано)

## Сделано (по 02-design)
1. **NEW** [`.claude/hooks/shared/pipeline_1c_bridge.py`](../../.claude/hooks/shared/pipeline_1c_bridge.py) —
   `derive_slug(prompt)` (JIRA `[A-Z]{2,}-\d+` → стабильный slug; fallback ASCII-slug первой строки → `1c-task`) +
   `ensure_pipeline_1c(prompt, command)` (идемпотентный `pipeline_state.init_task`, **best-effort** try/except).
2. **EDIT** [`analyze-1c-task-preflight.py`](../../.claude/hooks/analyze-1c-task-preflight.py) — +вызов `ensure_pipeline_1c` после детект-гарда (до debug-probe → пайплайн заводится даже если probe тормозит/падает).
3. **EDIT** [`implement-1c-task-preflight.py`](../../.claude/hooks/implement-1c-task-preflight.py) — +вызов после детект-гарда (init-or-touch).
4. **NEW** [`tests/unit/test_pipeline_1c_bridge.py`](../../tests/unit/test_pipeline_1c_bridge.py) — 5 тестов, marker `unit`.

## Отклонения от дизайна (и почему)
- **Тесты `ensure` сделаны collision-immune** вместо monkeypatch реального `pipeline_state`: в полном pytest-прогоне
  `from shared import pipeline_state` резолвится в `src/shared` (коллизия имён, memory `feedback-hook-src-shared-collision`)
  → 2 теста падали в suite (в изоляции — ок). Переписал: slug-логика (чистая) + гарантия «один slug на JIRA» +
  best-effort через форсированный пустой `shared`. Реальное создание файла покрыто **live-DoD-2** (синтетический preflight).
  **Продакшен НЕ затронут** — preflight стартует в свежем процессе (path insert → hooks-shared), коллизии нет.

## Соответствие инвариантам (01-architecture)
- Behavior-preserving: helper зовётся только из 2 1С-preflight; generic `pl-*` не тронут (35 pipeline-тестов зелёные).
- Best-effort: try/except → None (тест `test_best_effort_never_raises`).
- Один пайплайн на задачу: JIRA-slug стабилен (тест `test_same_jira_one_slug`).
- Откат: revert 2 строк в preflight + удалить helper + тест.
