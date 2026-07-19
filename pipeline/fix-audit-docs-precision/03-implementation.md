# Implementation — 4 фикса точности audit_docs_skills.py

Все правки в [`scripts/audit_docs_skills.py`](../../scripts/audit_docs_skills.py). Генерация делегирована claude-cli-sonnet (Token Economy), ревью — Opus.

| # | Функция | Изменение |
|---|---------|-----------|
| 1 | `_extract_router_prefix` | Приоритет: `APIRouter(prefix=)` из модуля > `include_router(prefix=)` app.py > root `""` при наличии `APIRouter(` > `/{stem}`. |
| 2 | `_class_to_strategy_name` | Акроним-aware camel→snake (2 границы) → `graph_rag_auto`/`light_rag`, не `graph_r_a_g_auto`. |
| 3a | `_all_docs_text` + `_all_skills_text` | Кэш-функции whole-tree; fallback в `run_audit` — фича не gap, если упомянута в ЛЮБОМ .md дерева. |
| 3b | `_feature_documented` (strategy) | +токен-матч `all(tok in text for tok in name.split("_"))`. |
| 4 | `_package_exports` + `extract_memory_subsystems`/`extract_bsl_tools` | Фильтр классов по `__all__` пакета (публичный API); нет `__all__` → no-filter. |

## Результат (было → стало)
- DOC gaps: **89 → 22** (endpoint/hook/strategy → 0; memory 34%→82%, bsl 6%→44% docs-coverage).
- SKILL gaps: **52 → 24** (все 24 — хуки реально нигде в скиллах; совпало с ручной кросс-проверкой).
- features 637 → 617 (20 внутренних классов отфильтрованы).
- Регрессий нет: agent/cli/config/mcp/wiki = 100%; endpoint total=88 неизменно.

## Провенанс
Баг уже успел загрязнить `framework-api/SKILL.md` (секция «Незадокументированные» содержит `/openai_compat/*`, `/websocket/ws/search`) через прошлый `--update`. Чистка таблицы — отдельная задача (НЕ трогал, чтобы не расширять scope).
