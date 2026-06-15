# 03 — Кодирование

## Изменённые файлы
| Файл | Что |
|---|---|
| `scripts/tool_usage_report.py` | `_load_pipeline_state` + `resolve_task_dir` (override>slug>авто-1С>None); CLI `--slug`; `main` через resolve_task_dir; docstring/usage |
| `.claude/hooks/shared/pipeline_state.py` | `is_registered(slug)` — публичный предикат (reviewer-rec) |
| `.claude/skills/run-1c-task/SKILL.md` | шаг 9 → `--slug <slug>` (было `--task-dir`) |
| `docs/.../43.3_МАРШРУТИЗАЦИЯ…md` | шаг 4 — резолв через реестр |

## Тесты
`tests/unit/test_tool_usage_report.py` +6 (override / slug / авто-1С / generic-авто→None / slug-generic / loader-fail best-effort).

## reviewer-fixes (code-verify a00349718 PASS): is_registered вместо приватного _read_registry + docstring-нота про незарегистрированный --slug.
