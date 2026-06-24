# Pipeline: ecosystem-scan-engagement (ADR-039)

Ретро-оформление 4-этапного пайплайна для реализации ADR-039 (engagement-aware ранжирование +
on-demand ecosystem-скан). Артефакты-первоисточники — ADR-039 + глава 44.

## 1. Планирование
Оценка open-source `last30days-skill` (46k★, MIT) → вердикт **ADAPT частично** (не full-adopt:
доменный промах 1С/RU + дублирование research-механик + секрет-риск public-репо + платные API).
Источник: [ADR-039](../../.claude/skills/architecture-research/adr/039-last30days-skill-adopt-evaluation.md),
cache `architecture-research/cache/last30days-skill-tooling-2026.md`.

## 2. Дизайн (approved)
Извлечь полезное ядро в безопасный stdlib-модуль; 2 потребителя на одном модуле:
- общий приём `engagement_rank` (expand_queries + blended_score/rank_items + dedup_by_entity);
- V1 — блендинг в авто-хуке `prework-github-bp`;
- V2 — on-demand CLI `ecosystem_scan.py` (free HN/StackOverflow/GitHub).
Док: [гл. 44](../../docs/framework%20documentation/44_ECOSYSTEM_SCAN/44.1_Обзор.md).

## 3. Кодирование
- `.claude/hooks/shared/engagement_rank.py` (NEW), `prework-github-bp.py` (V1),
  `scripts/ecosystem_scan.py` (V2; Reddit мёртв → StackOverflow; per-source нормировка),
  `factory-enforcer.py` (skip hooks/shared|base — побочный фикс фантомных ШАГ 4/5).
- Дисциплина простоты; graceful; reuse > duplication.

## 4. Тестирование
- unit: `test_engagement_rank.py` (8) + `test_ecosystem_scan.py` (7) + `test_factory_enforcer_skip.py` (4).
- ruff/compile PASS; code-verify reviewer PASS (все срезы); LIVE: SO=17 items, кросс-источниковая выдача.

**Коммиты:** d2cea2a56 (V1) · 1fb7e55c5 (V2) · bcffd5932 (factory-fix) · 57f72ccfd (гл.44) · 8ac0e2f8d (V2-hardening).
