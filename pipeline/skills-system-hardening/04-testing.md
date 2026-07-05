# 04 — Тестирование/Верификация: Skills-system hardening

## Прогнанные проверки (все PASS)
| Проверка | Результат |
|----------|-----------|
| skill-learning stats | pending_count 78→0, rejected_count 0→5, saved-total 3→76 |
| Qdrant learned_patterns | 51→124 points (+73 harvested) |
| fresh skill-lint | 0 errors / 2 warnings (BODY500 advisory, сознательно) |
| `data/_skill_lint.json` refresh | errors 48(stale)→0 |
| router-config JSON | валиден, грузится, bundles 53→66 |
| **keyword-коллизии от новых бандлов** | 0 (после дедупа: убраны триггеры, принадлежащие чужим бандлам) |
| все 13 новых скиллов в своём `skills` | да |
| still-unrouted (не bundle и не doc) | 0 |
| GT-lint (lint_skill_router_gt.py) | OK — schema valid, no leakage |
| eval-skill-router FP от моих бандлов | 0 (ни один не в FP-списке) |
| evals.yaml | 13 файлов, 24 кейса, все парсятся |
| CLAUDE.md числа | 66 bundles / skill_library 98 / learned_patterns 124 — grep-verify |

## Регресс-заметка
Дедуп keywords (итерация 2): первая версия новых бандлов продублировала триггеры существующих
(`hooks`/`creation`/`framework-use`/`langchain-infra`/`edt-mcp`). Исправлено детерминированным
скриптом: из каждого нового бандла удалены keywords, уже принадлежащие чужим бандлам; у всех 13
осталось ≥2 уникальных триггера → сворачивать в `optional` не потребовалось.

## Не прогонялось (обосновано)
- `eval_skills.py` live-baseline: project-aware claude-cli → delta=0 (задокументировано). Кейсы — durable-актив.
