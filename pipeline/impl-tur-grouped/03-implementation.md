# 03 — Кодирование

## Изменённые файлы
| Файл | Что |
|---|---|
| `scripts/tool_usage_report.py` | `_CATEGORIES`/`_CATEGORY_SUMMARY`/`_IMPL_WRITE_OPS`/`_TOOL_SUMMARY`; `classify_tool`/`tool_summary`/`_suffix`/`_q`/`_cell`; `report_md` rewrite (чеклист петель + секции по категориям) |
| `docs/.../43.3` | описание нового формата отчёта (группировка + петли + назначение) |

## Тесты (`tests/unit/test_tool_usage_report.py` +6)
classify_tool (memory/skills/config/research/impl/testing/infra + read/write split + неизвестное), tool_summary,
report_md grouped (чеклист + секции + назначение + err%→✗), missing-mandatory→✗, empty, pipe-escape.

## reviewer-fixes (code-verify a1f534b5 PARTIAL→addressed): удалён мёртвый `_CONFIG_READ_OPS` (denylist достаточен); `_cell()` экранирует `|` в ячейках + тест.
