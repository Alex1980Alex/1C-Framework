# F-1 — Тестирование (DoD пройден)

| DoD | Метод | Результат |
|---|---|---|
| **1. unit зелёный** | `pytest tests/unit/test_pipeline_1c_bridge.py -m unit` | **5 passed** (изоляция) |
| **2. live preflight создаёт пайплайн** | синтетика `printf '{"prompt":"/analyze-1c-task GKSTCPLK-77777 …"}' \| python analyze-1c-task-preflight.py` | **OK** — создан `pipeline/GKSTCPLK-77777/.pipeline-state.json` (свежий `updated_at`), затем вычищен |
| **3. Stop-предикат удовлетворён (G3 закрыт)** | свежий `.pipeline-state.json` (DoD-2) → `pipeline-protocol-stop._pipeline_used_since(start)` True по построению | **OK** (механизм: fresh state ≥ session start) |
| **4. без регрессий + lint** | `pytest tests/unit -m unit -k pipeline` (35 passed) + `ruff check` (all passed) + `py_compile` (OK) | **OK** |

## Найденная и устранённая проблема (Тестирование)
Первая версия unit-тестов (monkeypatch реального `pipeline_state`) проходила в изоляции, но **падала 2/5 в полном
прогоне** — `src/shared`↔`.claude/hooks/shared` коллизия имён в общем pytest-процессе (memory
`feedback-hook-src-shared-collision`). Переписано на collision-immune (см. 03-implementation). **Продакшен не затронут**
(preflight = свежий процесс). После — **35 passed** в полном pipeline-наборе.

## Вердикт
**F-1 (ядро G3) — DONE.** 1С-слэш-маршрут `/analyze-1c-task`→`/implement-1c-task` теперь сам заводит
`pipeline/<slug>/.pipeline-state.json` → Stop-хук ADR-018 доволен без ручного пайплайна. Обратимо (revert 2 строк + helper).

**Следующие срезы:** F-1.5 (stage-advancement по ANALYSIS-REPORT/IMPLEMENTATION-PROGRESS), F-2 (гейт G4 на /implement-1c-task), F-3/W (relabel + TOOL-PLAN-шаблон + отчёт-скрипт).
