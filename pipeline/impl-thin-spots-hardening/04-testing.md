# Тестирование (DoD пройден)

| Проверка | Результат |
|---|---|
| compile + ruff | OK / All passed (bridge, memory, research, pipeline-protocol-stop, тесты) |
| unit (3 файла) | **51 passed** (вкл. is_1c_task_title paren/lookalike + N6 src/memory-exclusion) |
| collision-immune | **84 passed, 1 skipped** (`-m unit -k "pipeline or protocol_stop or tool_usage"`) |
| live exempt | все 3 Stop-хука на текущей не-1С сессии → **exit 0** (нет false-block) |
| N4 предикат | оба хука грузятся; `is_1c_task_title("1С-задача (x): y")=True`, lookalike=False |
| code-verify | **PASS** (behavior-preservation: N4 сужение только в lookalike; N3 монотонно; N6 точно; N10/N1/N5 без логики) |

**Вердикт: DONE.** 7 genuine-фиксов внесены без false-block; 5 by-design оставлены с обоснованием.
43.5 «Оценка покрытия» обновлена (исправлено / осталось by-design / пробелы). Глубокий анализ N1–N12 — в 01-planning.

**Граница (честно):** research-relevance (N7) и G4-в-AUTO (N9) НЕ ужесточены — это осознанные trade-off'ы (фикс
ввёл бы false-block / противоречит режиму AUTO). Единый task-completion gate + сквозной прогон /run-1c-task —
остаются кандидатами (пробелы, не тонкие места).
