# TOOL-PLAN — F-2 (impl-1c-bridge-f2)

| Этап | Инструменты | Quality |
|---|---|---|
| Планирование | architecture-research, Read (pipeline-gate.py) | ✓ хорошо — гейт прост, расширение точечное |
| Дизайн | architecture-research | ✓ хорошо — реюз gate-паттерна + derive_slug |
| Кодирование | create-hook, Write/Edit, ruff/py_compile | ✓ хорошо — bridge-функция + 1 ветка в gate, чисто |
| Тестирование | evaluation-benchmark, pytest, синтетический UPS gate | ✓ хорошо — 10 passed + live (block/allow/no-op) с 1й |

Лог — авто `hook-invocations.jsonl`. Шкала: ✓/⚠/✗.
