# 01 — План: 260716 §3.3 LOW-хвост

> Триггер: пользователь «сделай» про LOW-хвост §3.3. Каждый пункт СВЕРЕН с реальным
> кодом (роадмап сам документировал перевёрнутые диагнозы — M6, P1.9, P1.3 — поэтому
> verify-before-fix обязателен).

## Пункты и вердикты

| # | Место | Дефект (подтверждён чтением) | Действие |
|---|---|---|---|
| 1 | [`ai_memory/server.py:545`](../../src/memory/ai_memory/server.py) | `round(row[2],2)` где `row[2]=AVG(importance)`; группа со всеми NULL → AVG=NULL → `round(None)` TypeError | coerce None (honest null) |
| 2 | [`ai_memory/server.py:517-523`](../../src/memory/ai_memory/server.py) | post-`commit()` side-effects (`_cleanup_links`/`_record_ingest`) вне try → фейл реестра роняет ВСЮ операцию после успешного delete (клиент видит ошибку на удалённой записи) | best-effort side-effects |
| 3 | [`maintenance/dashboard.py:69-76`](../../src/memory/maintenance/dashboard.py) | naive-`dt` + aware-`now`: `ref.replace(tzinfo=None)` даёт UTC-wall-clock вместо local → age смещён на tz-offset (common path both-naive корректен → latent) | симметричная нормализация обоих операндов |
| 5 | [`orchestrator/memcube.py:213,234`](../../src/memory/orchestrator/memcube.py) | `metadata.get("pattern_type", <default>)` без coerce — произвольная строка проходит (класс P0.3); дефолты РАЗНЫЕ (`code-convention` / `workflow-pattern`); конвертеры orphaned → latent | `normalize_pattern_type` на границе |
| 6 | [`unified_id.py:42,62`](../../src/memory/orchestrator/unified_id.py) + [`link_registry.py:67`](../../src/memory/orchestrator/link_registry.py) | голый `ValueError(value)` без списка валидных | обогатить message (non-breaking, остаётся ValueError) |
| 4 | [`unified_search.py:314`](../../src/memory/orchestrator/unified_search.py) | RRF键 по `unified_id` → кросс-store дубли не суммируют ранги | **DEFER (замерено+обосновано)** |

## Замер по пункту 4 (RRF) — до проектирования, роадмап требует замера для ranking-правок

Прогон 10 разнородных запросов через `unified_search` (scratchpad/measure_rrf_blast.py):
**2 из 93 результатов** (2.2%, 2/10 запросов) имели непустой `duplicate_sources` — оба
`memory-ai`, дублирующиеся в `vector-memory`.

**Решение: НЕ чинить.** Обоснование (root-cause, а не симптом):
- Кросс-store дубли в этой системе — почти всегда **зеркала** (один факт, синхронизированный
  `cross_store_sync` через `MIRRORS`), а НЕ независимое подтверждение.
- Суммирование RRF-рангов зеркал бустило бы **избыточно хранимый один факт**, а не
  корроборированный — это скорее деградация, чем улучшение.
- Валидировать «стало лучше» нечем: golden-set релевантности `unified_search` нет
  (`tune_memory_surfacing.py` — про surfacing-хук, не про этот RRF).
- Роадмап уже держит это в §3.3 LOW. → добавить поясняющий комментарий в код (чтобы
  будущий «фикс» не сломал), зафиксировать замер в §18.

## Тесты (sabotage-check: откат фикса → тест краснеет)

Файл `tests/unit/test_memory_low_tail_260716.py`: NULL-avg importance, delete с падающим
link-cleanup (delete всё равно success), tz naive-dt+aware-now, memcube coerce мусора,
from_string message содержит валидные значения.

## Не-цели

Item 4 (RRF) — не трогаем логику. hard-timeout потолок (§3.3 «вопрос открыт») — design-вопрос,
не код-фикс. `LearnedPattern.from_dict`/`forget_gate._days_idle` — уже закрыты (P0.2/F7).
