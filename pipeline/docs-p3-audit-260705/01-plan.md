# P3 — Улучшения документации (roadmap 260704) — план

> Волна P3 (8 пунктов) дорожной карты [260704_ROADMAP_DOCS_DEEP_AUDIT.md](../../docs/roadmap/260704_ROADMAP_DOCS_DEEP_AUDIT.md).
> P0/P1/P2 — DONE. Приоритет: код (P3.1 — генератор счётчиков) → контент доков.

## Декомпозиция (file-ownership без пересечений)

| Поток | Пункты | Файлы |
|---|---|---|
| A1 (код) | P3.1 генератор счётчиков | `scripts/docs_counters.py` (новый) + tests; якоря: `.claude/skills/` (101 скилл), `.claude/skills/skill-router-config.json`, `.mcp.json`, `infra/lazy-mcp/config/registry.yaml`, Qdrant (опционально) |
| A2 | P3.2 статус-штампы + P3.4 GLM-бенчи | 46.x, 45.1, 23.1, 23.6 |
| A3 | P3.3 Guardrails + P3.5 KB | 33.1 (+`src/api/middleware/guardrails.py`, `src/pdf_framework/guardrails/`), 34.1 (+`src/pdf_framework/knowledge_base/`) |
| A4 | P3.6 + P3.8 указатели | КОМАНДЫ_CLAUDE_CODE.md, 31.1, 31.2, 24.3, 24.4 |
| A5 | P3.7 заглушки 05.5 | 05.5 (+`src/pdf_framework/agents/`) |

## Решения
- P3.1: отдельный скрипт `scripts/docs_counters.py` (а не врезка в 1300-строчный audit_docs_skills.py) —
  drift-lint режим (`--check`) + JSON-отчёт; авто-подстановку в доки НЕ делаем в первой итерации
  (высокий риск порчи; счётчики видны, правки — руками/агентом по отчёту).
- P3.4: тела 23.1/23.6 переводятся в «проектные оценки, не измерялись» — цифры сохраняются как оценки.
- Верификация: pytest по новому скрипту + адверсариальный ревьюер по итогам.

## Статус
- [x] План
- [ ] Кодирование (5 агентов)
- [ ] Верификация
