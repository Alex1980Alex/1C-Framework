# ADR-039: last30days-skill — частичная адаптация, не full-adopt

**Дата:** 2026-06-24
**Статус:** accepted
**Исследование:** [cache/last30days-skill-tooling-2026.md](../cache/last30days-skill-tooling-2026.md)

## Контекст
Пользователь попросил оценить интеграцию open-source инструмента
[`last30days-skill`](https://github.com/mvanhorn/last30days-skill) (46.2k★, MIT, Claude Code skill)
во фреймворк. Инструмент — **social-trend research** (НЕ git/changelog): опрашивает Reddit/X/YouTube/
HN/Polymarket/TikTok/Instagram/Bluesky + web, ранжирует по реальному engagement, дедуплицирует и
синтезирует бриф. Зависит от cookies (X/Bluesky/YouTube) и платных API (ScrapeCreators/Perplexity/
Brave) для полной мощи; free-tier = Reddit/HN/GitHub/Polymarket.

## Решение
**ADAPT (частично), НЕ full-adopt.** [own]
- **SKIP** marketplace-установку с cookies/платными ключами: (а) доменный промах — ядро фреймворка
  1С BSL (RU, источники its.1c.ru/infostart, покрыты `1c-doc-research`) + PDF RAG (self-search), а
  не англоязычные соцсети [own]; (б) дублирование — уже есть `tech-research`, `architecture-research`
  Фаза 2, `autoresearch`, хуки `prework-github-bp/stackoverflow` [exp]; (в) cookies/токены в
  **public-репо** сразу после ремедиации утечки секретов ([[project-secret-leak-remediation-260614]])
  — недопустимый attack-surface [exp]; (г) cost-conscious-политика ([[feedback-no-paid-anthropic-api]])
  против платных API [exp].
- **ADOPT выборочно** идею (одно из двух, по желанию пользователя):
  1. Opt-in «ecosystem last-30-days» скан **только free-источников (HN+Reddit+GitHub)**, локальная
     конфигурация без cookies в репо, как ускоритель Фазы 2 `architecture-research`/`tech-research`
     и discovery-половины tooling-adoption (ADR-012..015); ИЛИ
  2. Заимствовать **паттерн** (engagement-ранкинг + multi-query expansion + entity-dedup) в
     `prework-github-bp.py` — без новой зависимости и скрапинга (дешевле/безопаснее). [own]

Python-совместимость есть (требует 3.12+, `.venv` = 3.13.13) — не блокер [exp].

## Последствия
### Положительные
- Recency-bounded, engagement-ранжированный ecosystem-скан усиливает research-Фазу 2 и tooling-adoption.
- Нет новой тяжёлой зависимости/скрапинга при выборе варианта 2 (паттерн).
- Решение зафиксировано (не теряется), факты в cache.
### Отрицательные
- Без полной установки не используется кросс-платформенный охват (X/TikTok/YouTube) — но он и не нужен домену.
- Вариант 1 добавляет opt-in внешний инструмент (поверхность поломок 11 платформ; для free-3 — меньше).

## Альтернативы
- **Full-adopt** (marketplace + cookies + платные ключи) — ОТКЛОНЕНО: доменный промах + секрет-риск
  в public-репо + дублирование + платные зависимости.
- **Статус-кво** (только текущие WebSearch/research-скиллы) — приемлемо; last30days даёт лишь
  recency+engagement-ранкинг сверху, маргинальный ROI для нашего домена.

## Реализация (2026-06-24) — V1 done
Реализован **вариант 1** + общий модуль под будущий V2 (по запросу пользователя):
- **NEW** [`.claude/hooks/shared/engagement_rank.py`](../../../hooks/shared/engagement_rank.py) —
  stdlib-only приём (`expand_queries` + `blended_score`/`rank_items` + `dedup_by_entity`),
  переиспользуем и V1, и будущим V2.
- `prework-github-bp.py` — `_build_items` блендит relevance×engagement (веса 0.7/0.3) вместо
  relevance-only сортировки; graceful-fallback при ImportError (== прежнее поведение); фильтры
  (`_has_github_signal`/`_is_fresh`), `MIN_SCORE`, `TOP_K`, форма item сохранены.
- `tests/unit/test_engagement_rank.py` — 8 тестов; code-verify PASS; smoke: high-engagement
  топик (eng=50) встаёт первым (1.0) против relevance-tie.
- **V2** (opt-in free-источники HN/Reddit/GitHub скан) — отложен; модуль готов к переиспользованию.

## Связанные файлы
- **NEW** `.claude/hooks/shared/engagement_rank.py`; **V1** `.claude/hooks/prework-github-bp.py`;
  **NEW** `tests/unit/test_engagement_rank.py`.
- Перекрываемые: skills `tech-research`/`architecture-research`/`autoresearch`; hook `prework-stackoverflow`.
- Паттерн tooling-adoption: ADR-012..015.
