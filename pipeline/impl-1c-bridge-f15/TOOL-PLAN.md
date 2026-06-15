# TOOL-PLAN — F-1.5 (impl-1c-bridge-f15)

> Раздел W: инструменты по этапам + quality. Лог — авто `hook-invocations.jsonl` (run_id).

| Этап | Инструменты | Назначение | Quality |
|---|---|---|---|
| **Планирование** | create-hook (skill), Read/Grep (base/protocol.py, pipeline_state) | PostToolUse-payload, точки advance | **✓ хорошо** — `tool_input.file_path` + «PostToolUse рабочий» подтверждено |
| **Дизайн** | create-hook, Read | контракт advance_for_artifact + хук + guard | **✓ хорошо** — guard по title-метке F-1 переиспользован чисто |
| **Кодирование** | create-hook, Write/Edit, ruff/py_compile, json-валидация settings | helper-функция + хук + settings.json + тест | **⚠ частично** — путь 04-testing.md исказился (`C:\1С-框架` вместо Framework) → стрей-файл, поймал+удалил (+1 шаг); skill-gate'ы потребовали 2 активации |
| **Тестирование** | evaluation-benchmark (skill), pytest, синтетический PostToolUse | DoD: regex-маппинг, guard, live-advance, без регрессий | **✓ хорошо** — 38 passed + live (advance + guard) с 1й |

Шкала: ✓ хорошо · ⚠ частично (заметка) · ✗ плохо (заметка).
