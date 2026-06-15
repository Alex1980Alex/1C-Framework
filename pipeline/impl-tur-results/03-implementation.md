# 03 — Кодирование

## Изменённые файлы
| Файл | Что |
|---|---|
| `scripts/tool_usage_report.py` | `report_md` block-формат + параметр `results`; `load_results` (сайдкар, best-effort, однострочный coerce); CLI `--results`; `main` проводка (target→results→report); удалён `_cell`/таблица |
| `<папка задачи>/TOOL-RESULTS.json` | курируемые результаты gkstcplk-2567 (Подсолнечник: ground-truth, наполнение, render-verify PASS) |
| `run-1c-task/SKILL.md` шаг 9 | Claude пишет TOOL-RESULTS.json перед отчётом |
| `docs/.../43.3` | блок-формат + результат из сайдкара |

## Тесты (`tests/unit/test_tool_usage_report.py`)
обновлены под блок-формат (rollup/grouped); +2 (`test_report_md_results_rendered` результат/«—», `test_load_results` best-effort) = 16.

## reviewer-fixes (code-verify a642c0c7 PASS): стейл-комментарий «в таблице»→«блока»; многострочный результат → coerce `\n`→space; микро Path(p).
