# 03 — Кодирование: Skills-system hardening

## Сделано
| # | Изменение | Проверка |
|---|-----------|----------|
| 1 | pending 78→0: 5 reject + 73 confirm (MCP skill-learning) | stats pending_count=0, rejected_count=5; Qdrant learned_patterns 51→124 |
| 2 | refresh `data/_skill_lint.json` | fresh lint = 0 errors / 2 warnings (BODY500 advisory) |
| 3 | +13 bundles + `_unrouted_intentional` в `skill-router-config.json` | config loads, bundles 53→66, still-unrouted=0, GT-lint OK |
| 4 | CLAUDE.md: 45→66 bundles, skill_library 80→98, learned_patterns 44→124 | grep-verify |
| 5 | +10 evals.yaml (топ-активированные) | 13 evals.yaml, 24 cases, все парсятся |

## Известные ограничения (честно)
- eval live-baseline не прогонялся: project-aware claude-cli → delta=0 (задокументировано в шапке каждого evals.yaml). Кейсы измеримы после фикса project-unaware baseline.
- 2×BODY500 (framework-config, triad-factory) оставлены advisory — сознательно, против FRAGMENTED.
- `data/skill_learning/*` и `data/_skill_lint.json` gitignored → не в коммите (runtime).

## Файлы в коммит
- `.claude/skills/skill-router-config.json`
- `CLAUDE.md`
- `.claude/skills/{1c-doc-research,langgraph-core,langchain-core,doc-to-skill,create-hook,framework-cli,audit-docs,hooks-skills-mcp-triad,doc-to-cache,framework-mcp-ui}/evals.yaml`
