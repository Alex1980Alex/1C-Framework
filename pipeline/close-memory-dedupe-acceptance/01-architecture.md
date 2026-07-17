# 01 — План: закрыть §5.3 роадмапа 260716 (dedupe --apply на живой learned_patterns)

> Дизайн этого среза целиком в роадмапе [260716](../../docs/roadmap/260716_ROADMAP_MEMORY_PAYLOAD_HARDENING.md)
> (P1.7 + §5 критерий 3). Здесь — только исполнение уже спроектированного и
> сухо-верифицированного шага. Инструмент [`scripts/dedupe_learned_patterns.py`](../../scripts/dedupe_learned_patterns.py)
> реализован и запинен в срезе P1 (link-aware, fail-closed, 7/7 тестов).

## Контекст

Единственный незакрытый acceptance-пункт роадмапа 260716 — §5.3 «0 дублей hash».
P0/P1/CircuitBreaker закрыты и верифицированы (§18). 3 пары дублей избыточны, но не
вредны; запрет `--apply` снят в P1.7, но на живой коллекции инструмент не запускался
(memory `reference_dedupe_learned_patterns_unsafe`).

## Сухой прогон (подтверждён 2026-07-17, совпал с §18)

```
total=154 unique_content_groups=151 dup_groups=3
dup copies to delete: 3
survivor stat-merges: 2
links: 47 touching -> 1 repointed, 5 dropped
canonical override x2 (mirrors > эвристика), dangling=0
```

## Шаги исполнения

1. **Бэкап + apply** — `dedupe_learned_patterns.py --apply` (бэкап точки+векторы+рёбра
   пишется ДО мутации в `data/memory/backups/`; инструмент fail-closed по dangling).
2. **Верификация акцептанса** (live, in-process):
   - §5.3 — повторный dry-run: `dup_groups=0`, `content_hash` дублей нет, `final_count=151`.
   - §5.5 — `unified_search` → `sources_failed=[]`, 3 плеча (регрессия исходного инцидента).
   - Плечо == тул: `search_patterns` и vector-плечо отдают одни точки в одном порядке.
   - `link_registry`: 0 висячих рёбер после репойнта.
3. **Регресс** — `pytest tests/unit/test_dedupe_learned_patterns.py` + memory-сьют P0/P1.
4. **Док** — роадмап §18 (запись сверху) + §5 критерий 3 → закрыт; память
   `reference_dedupe_learned_patterns_unsafe` → «запущен на живой, N точек».

## Откат

`dedupe_learned_patterns.py --restore <backup>.json --apply` — ре-upsert точек+векторов
и восстановление рёбер (снятие созданных прогоном по метке `repointed_by`). Идемпотентно.

## Риск

Мутация обратима через бэкап. MCP-серверы читают ту же Qdrant вживую → данные-эффект
виден сразу, `/mcp reconnect` НЕ требуется (правок кода MCP нет).
