# 02 — Дизайн

## Категории (classify_tool) → artifact + обязательность
| key | категория | artifact/этап | обязат. |
|---|---|---|---|
| memory | Память (recall/capture) | сквозной | ✓ |
| skills | Скилы (методики 1С) | сквозной | ✓ |
| config | Анализ конфигурации 1С | ANALYSIS-REPORT | ✓ |
| research | Внешний анализ (Infostart+GitHub) | ANALYSIS-REPORT | ✓ |
| impl | Кодирование | IMPLEMENTATION-PROGRESS | — |
| testing | Тестирование | .run-state.json | — |
| infra | Инфраструктура | сквозной | — |

## Классификация
- prefix-правила: memory (memory-orchestrator/vector-memory/skill-learning/memory-ai), skills (Skill),
  research (WebSearch/WebFetch), config (bsl-semantic-search/bsl-platform-context/…), impl (debuggers/1c-debug),
  testing (mcp-onec-test-runner).
- 1c-mcp-crud / edt-mcp: **read/write split** по суффиксу — denylist `_IMPL_WRITE_OPS`→impl, остальное→config
  (новые read-инструменты авто-в-анализ без правки кода). Неизвестный сервер→infra.

## Формат отчёта
Чеклист обязательных петель (✓/✗ по использованию) + секции по категориям (только непустые): заголовок с
artifact+саммари+агрегат, per-tool строка `tool | назначение | calls | errors | err% | avg_ms | quality`.
`_cell()` экранирует `|`. report_md сигнатура `(by_tool, key)` сохранена (rollup/пустой-кейс не задеты).

## Approved: пользователь (требования прямо заданы).
