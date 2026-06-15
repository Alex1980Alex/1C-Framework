# F-1.5 — Тестирование (DoD пройден)

| DoD | Результат |
|---|---|
| unit (мои + регрессия) | **38 passed** (`pytest tests/unit -m unit -k pipeline`) — 8 в test_pipeline_1c_bridge + 30 регресс |
| ruff / compile | All checks passed / compile OK |
| settings.json валиден + Write\|Edit зарегистрирован | OK (9 PostToolUse-групп) |
| live: 1С-пайплайн двигается | advance(ANALYSIS-REPORT) → этапы 1,2 **done done** + systemMessage |
| live: guard не-1С | не-1С пайплайн → этапы **pending pending (НЕ тронут)** |

**Вердикт: F-1.5 DONE.** Запись ANALYSIS-REPORT/IMPLEMENTATION-PROGRESS в 1С-CURRENT-пайплайне авто-двигает этапы;
framework-dev пайплайны защищены guard'ом по title-метке F-1. Обратимо. Этап 4 (Тестирование) и гейт G4 — следующие срезы.
