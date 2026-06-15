# F-2 — Тестирование (DoD пройден)

| DoD | Результат |
|---|---|
| unit | **10 passed** (`test_pipeline_1c_bridge` — +2 gate) |
| ruff / compile | All passed / OK |
| live: дизайн НЕ approved | `/implement-1c-task` → **block** (decision:block + reason «одобри…») |
| live: дизайн approved | → **allow** (нет вывода, exit 0) |
| live: нет 1С-пайплайна | → **allow** (no-op, не блокируем нормальный поток) |

**Вердикт: F-2 DONE.** Хард-гейт G4 «Дизайн→Кодирование» для 1С-маршрута: `/implement-1c-task` блокируется, пока
дизайн (этап 2) задачи не одобрен человеком. Generic pl-* гейт не затронут; opt-out `PIPELINE_GATE_DISABLE=1`. Обратимо.
