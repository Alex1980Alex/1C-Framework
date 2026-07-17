# 03 — Исполнение

## Сделано

Запущен `dedupe_learned_patterns.py --apply` на живой коллекции `learned_patterns`
(2026-07-17 22:56). Правок кода нет — исполнение уже реализованного и запинтованного
инструмента (link-aware дедуп из среза P1, роадмап 260716 P1.7).

### Результат прогона

```
total=154 -> final count: 151 (3 дубля-зеркала удалены)
survivor stat-merges: 2  (succ/fail/application_count слиты, confidence пересчитан §22)
links: 47 touching -> 1 repointed, 5 dropped
canonical override x2: 1e3e91c8 (mirrors) > 5e88c5a9;  1fec4050 (mirrors) > e30914b1
dangling: 0
```

### Бэкап (откат)

`data/memory/backups/learned_patterns_20260717_225637.json` — 154 точки + векторы +
47 рёбер (проверено чтением: `points=154, links=47, first point has vector=True`).
Откат: `dedupe_learned_patterns.py --restore <файл> --apply` (ре-upsert точек+векторов,
восстановление рёбер по метке `repointed_by`, идемпотентно).

## Ключевое наблюдение

Инструмент выбрал КАНОН из `mirrors`-рёбер, а не эвристику `pick_survivor` — в 2 из 3
групп эвристика удалила бы канон (это и есть дефект, ради которого P1.7 сделал дедуп
link-aware). Рёбра лоузеров репойнтнуты на выжившего → провенанс не потерян,
висячих рёбер 0.

## Эффект на рантайм

MCP-серверы (vector-memory, memory-orchestrator) читают ту же Qdrant вживую → эффект
виден немедленно, `/mcp reconnect` НЕ требовался (правок кода MCP нет). Подтверждено
in-process прогоном: `unified_search` даёт 3 плеча, `sources_failed=[]`.
