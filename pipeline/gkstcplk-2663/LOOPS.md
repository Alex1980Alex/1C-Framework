# LOOPS — обязательные петли задачи `gkstcplk-2663`

| Петля | Статус |
|---|---|
| ПАЙПЛАЙН | ✓ (pipeline-state) |
| RECALL (память) | ✓ |
| CAPTURE (память) | ✓ |
| RESEARCH (Infostart+GitHub) | ✓ |
| SONAR re-scan изменённого/добавленного кода | ✓ |
| SKILL-методика 1С | ✓ |
| T1 impact-анализ перед правкой (advisory) | ⚠ advisory |
| T1 live BP-trace runtime-логики (advisory) | ⚠ advisory |
| T2 поиск эталона на Планировании (advisory) | ⚠ advisory |
| T1 find_callers/call-graph перед [REFACTOR] (advisory) | ⚠ advisory |
| Тир-2 get_form_screenshot (advisory) | ⚠ advisory |
| Тир-2 bsl-platform-context/pdf-vector-graph (advisory) | ⚠ advisory |
| Тир-2 bsl_analyze_method (advisory) | ⚠ advisory |

_T1-T2 — рекомендательно по умолчанию; при ONEC_TOOLGATE_HARD=1 impact (и при ONEC_TOOLGATE_DEBUG_HARD=1 — BP-trace) становятся HARD на правке 1С-кода (ADR-036). find_callers всегда advisory. Блок ядра — RECALL/CAPTURE/RESEARCH._

- opt-out gate: нет
- W per-task (`TOOL-USAGE-REPORT.md`): НЕ запущен (H3)
- tool-effectiveness (cross-task): есть — `tool_usage_report.py --rollup` (H1: отчётный)

_Авто-сводка onec-task-completion-stop на Stop (H2); фактические tool_use транскрипта._
