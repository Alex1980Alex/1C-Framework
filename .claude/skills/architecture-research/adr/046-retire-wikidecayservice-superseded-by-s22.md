# ADR-046: Ретайр WikiDecayService — вытеснен §22 Beta-count-decay

**Дата:** 2026-07-05
**Статус:** accepted
**Исследование:** находка P3 аудита [260705](../../../../docs/roadmap/260705_ROADMAP_MEMORY_DOCS_AUDIT.md) (документирование WikiDecayService в 27.12.6 §7.1 вскрыло перекрытие с §22)
**Родственные:** §22 confidence lifecycle (roadmap 260523), ADR-L1 (ретайр неиспользуемых link-типов — тот же паттерн «0 авторитетных потребителей → удалить»)

## Контекст

`src/memory/librarian/wiki_decay.py::WikiDecayService` применял **линейный** time-decay к денорм-полю
`confidence` точек `learned_patterns`: `decay = decay_rate·(days_idle/30)`, `new_conf = max(min_conf, old−decay)`.
Единственный вызыватель — ручная CLI-субкоманда `python -m scripts.export_graph_to_wiki decay-confidence`
(НЕ в maintenance-каденсе, запускалась вручную/никогда). [own: grep всех usages]

Заявленная в docstring цель — **«counter-balance the asymmetric +0.02/-0.01 update in
`handle_apply_pattern`»** — относилась к наивному confidence-апдейту, который **§22 удалил 2026-05-31**
(commit `c8409e30b`), заменив на Beta(7,3)-posterior над time-decayed счётчиками succ/fail.

### Почему линейные writes WikiDecayService не авторитетны под §22

§22 (P2, `b05d1081d`) деривит confidence **из счётчиков succ/fail НА ЧТЕНИИ**
(`confidence.payload_effective_confidence`), а не из хранимого денорм-`confidence`:
- `search_patterns` — drop server-prefilter, client-side effective filter/rank; [own: server.py]
- `WikiPromoter` gate — на effective;
- `list_patterns` `min_confidence` — на effective;
- хранимый `confidence` перезаписывается на следующем `apply_pattern` (derive из счётчиков).

Итог: линейный write WikiDecayService в денорм-`confidence` **не читается ни одним авторитетным путём**
и стирается ближайшим apply. Хуже — для **legacy**-точек без succ/fail `seed_counts_from_legacy`
(server.py:383) деривит счётчики из уже-децэйнутого stored conf, после чего §22 децэйит счётчики
повторно на чтении → **двойной decay**. [own: server.py:378-409]

## Решение

**Удалить (retire) WikiDecayService** целиком: класс + 14 тестов + CLI-субкоманду `decay-confidence`.

Взвешены 3 опции:

| Опция | Оценка |
|---|---|
| **A. DELETE** (выбрана) | Убирает dead-effect код; §22 — единственный авторитет decay (lazy on-read + apply-time + MCP `decay_confidence` sweep). Обратимо через git + этот ADR. |
| B. Deprecate + neuter (no-op + лог) | Оставляет ровно тот dead-code смелл, что удаляем; API-поверхность зря живёт. |
| C. Repurpose — децэить счётчики succ/fail (питать §22) | Дублирует lazy on-read count-decay §22 (тот уже децэит счётчики от `last_decay_at`); нулевая добавленная ценность. |

**Инвариант безопасности:** §22 `decay_confidence` MCP-tool (`vector_memory/server.py:handle_decay_confidence`)
— **независимый** механизм (использует `confidence.py`, не WikiDecayService), НЕ тронут. Idle-decay
паттернов сохранён полностью (lazy on-read из счётчиков + явный MCP sweep).

## Последствия

- **Удалено:** `src/memory/librarian/wiki_decay.py`, `tests/unit/memory/librarian/test_wiki_decay.py` (14 тестов),
  субкоманда `decay-confidence` в `scripts/export_graph_to_wiki.py` (docstring/argparse/handler/dispatch).
- **Поведение:** без изменений для всех авторитетных путей (ранжирование/gate/фильтр на effective);
  устранён потенциальный двойной-decay legacy-точек. CLI `export_graph_to_wiki` теперь несёт
  `promote-patterns`/`archive-stale` (без `decay-confidence`).
- **Доки:** 27.12.6 §7.1 переписан на «RETIRED, decay-авторитет = §22»; wiki-pipeline / memory-unified
  skill очищены от WikiDecayService.
- **Обратимость:** восстановление из git + revert этого ADR.

## Проверка

30 wiki-pipeline тестов PASS, compile+ruff clean, 0 остаточных код-ссылок (`grep wiki_decay/WikiDecayService`),
`handle_decay_confidence` §22 импортируется, CLI-help без `decay-confidence`. Commit `03115c43b`.
