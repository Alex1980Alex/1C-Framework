# 260705 — Глубокий аудит главы 5_ПАМЯТЬ (39 файлов) + сверка с GitHub-практиками

> **Метод:** 2 параллельных read-агента прочитали все 39 файлов зоны (20× 27.x, 10× 32.x, 9× 37.x)
> и сверили ~70 ключевых утверждений с кодом (`src/memory/*`, `src/pdf_framework/indexing/wiki_exporter.py`,
> хуки, `.mcp.json`). Отдельно: research ведущих практик memory-систем (mem0, Letta/MemGPT,
> Zep/Graphiti, LangMem) через ecosystem_scan + WebFetch canonical-репо —
> кеш [`llm-agent-memory-best-practices-2026.md`](../../.claude/skills/architecture-research/cache/llm-agent-memory-best-practices-2026.md).
> Рубрика: ОШИБКА (против кода) · УСТАРЕЛО · СЛАБО (структура) · УЛУЧШЕНИЕ.
> Контекст: волны P0–P3 аудита 260704 уже чинили эту зону (веса, sync-оговорки, 27.13, 32.7/32.1
> systemMessage, 37.5 MemoryCube.from_pattern) — здесь то, что ОСТАЛОСЬ после них.

---

## Сводная карта вердиктов

| Подглава | A (ок) | B (точечно) | C (переработка) |
|---|---|---|---|
| 5.1 UNIFIED_MEMORY (27.x) | 27.4, 27.10, 27.11, 27.12.1, 27.12.5, 27.12.6, 27.12.7, 27.13 | 27.1, 27.3, 27.6, 27.8, 27.9, 27.12, 27.12.2–27.12.4 | **27.2**, **27.5**, **27.7** |
| 5.2 WIKI_KNOWLEDGE (32.x) | 32.5, 32.10 | 32.1, 32.2, 32.6, 32.9 | **32.3**, **32.4**, **32.7**, **32.8 (фикция!)** |
| 5.3 HERMES (37.x) | 37.4, 37.6, 37.7 | 37.1, 37.3, 37.5, 37.8, 37.9 | **37.2** → вся 5.3 — кандидат в ARCHIVE |

**Интегрально:** та же болезнь, что нашёл аудит 260704, но в новой форме — **«обзорные» главы несут
конкретику, которая протухает, при живых точных «картах»** (27.12.x писались по коду и точны;
27.2/27.5/27.7 — обзоры с фантомами). Плюс два системных открытия: **32.8 описывает несуществующий
enforcement** (kb-lint НЕ подключён в pre-commit — wiki ничем не гейтится на commit) и
**5.3 Hermes дублирует 5.2 с конфликтующей нумерацией слоёв** (два разных «5-слойных» канона).

---

## P0 — Фикции и copy-paste-опасные ошибки (≤ 0.5 дня)

> **✅ DONE 2026-07-05** (commit `10633f4ee` + хвосты ревью). **R1 решён кодом (выбор пользователя):**
> kb-lint + markdownlint-cli2 восстановлены в pre-commit (scoped `^docs/wiki/`, entities/ исключены,
> `ci.skip: [kb-lint]`). По пути найдено и исправлено 3 код-бага: (1) upstream kb-lint scanner
> читал .gitignore без encoding → cp1251-крэш (3-й safety-патч wrapper'а); (2) документированный
> hook-entry с голым `--ci` линтил бы от корня репо; (3) **писатели drafts нарушали собственный
> lint-контракт** — `to_wiki_page(status=)` + непустые tags + MD047 newline (+6 тест-пинов),
> 11 drafts мигрированы, kb-lint EXIT 1→0. Доки P0.2–P0.6 переписаны по коду (file:line).
> Адверсариальный ревьюер PASS; его рекомендации (32.3 content_hash-строка, ci.skip, пин
> default-пути) применены. ⚠ `/mcp reconnect` нужен (memory_orchestrator).
> **Находка P0 РАЗРЕШЕНА в P1 (ложная тревога):** «WikiPromoter недо-промоутит» — оказалось
> **test debt, не прод-баг**. 5 красных тестов `test_wiki_promoter.py` использовали ретированное
> поле `usage_count` без `succ/fail` → `_resolve_state` (confidence.py:194 читает `application_count`)
> сидил через legacy n=0 → effective→prior 0.70 < 0.8. Прод-точки несут реальный `application_count`
> + succ/fail (Beta-posterior кэш = stored `confidence`), промоутятся корректно. Фикс — фикстура
> `_make_point` под §22-контракт (succ/fail из инварианта `(7+succ)/(10+succ+fail)=confidence`); 15/15 green.
> Остаточные фантомы нетронутых секций 32.3 (_sanitize_filename, SHA1) и 32.4 (backoff) — в R2.

| # | Файл(ы) | Проблема | Действие |
|---|---|---|---|
| P0.1 | **32.8 целиком** (+32.1:15, 32.3:3, 37.3) | kb-lint и markdownlint-cli2 **отсутствуют в `.pre-commit-config.yaml`** — цитируемый YAML-фрагмент (32.8:15-34) в файле не существует. Инфраструктура (`scripts/kb_lint_ci.py`, `.kblintrc.yml`) есть, проводки нет. Wiki сейчас не гейтится на commit вообще | **Решение**: (a) восстановить проводку в pre-commit ИЛИ (b) переписать 32.8 в честное «enforcement отключён с <дата>». Выбор — за пользователем (см. §Рекомендации R1) |
| P0.2 | 27.7:139-162 | Сниппет `.mcp.json` с фантомным `-m src.memory.orchestrator.server` — команда из доки **не запустится** (реально: `-m src.memory.orchestrator.memory_orchestrator` через `.venv\Scripts\python.exe`). Прямой copy-paste-риск | Заменить сниппет фактическим блоком из `.mcp.json:117-122`; заголовок «vector-memory (7 tools)» → 8 |
| P0.3 | 27.2:128-144 | Фантомный класс `UnifiedSearch` + метод `.query()` — не существуют (реально `UnifiedSearchEngine.search()` / `federated_search()`). Пример кода из доки упадёт на импорте | Переписать пример по unified_search.py |
| P0.4 | 27.5:120-139 | TTL-пресеты врут (`long=30 дней` → в коде LONG=7d, EXTENDED=30d, NEVER; «permanent» не существует) + фантомные API `ttl.extend/record_access/cleanup_expired` (реально `extend_ttl`) | Переписать по ttl_service.py:25-42; 27.12.6 — канон, сослаться |
| P0.5 | 37.2:14-16,127-128 | `experience_embeddings`/`conversation_memory` «ready for auto-populate» — коллекции **дропнуты 2026-06-03** (ADR Q1); `scripts/reindex_wiki.py` — фантом; «auto-reindex via docs-change-tracker» — ложь | Вычистить в рамках R2 (ARCHIVE 5.3) |
| P0.6 | 32.3:56-93 / 32.4:58-99 | Frontmatter/body-контракт фабрикован: реальные 2823 файла `entities/*.md` несут MemoryCube-формат (`## What/Why/Where/Content`, `unified_id=semantic:memory-ai:<uuid4>`), а не описанные `## Properties/Source chunks/Connections` + `related` (поля нет). Правда уже есть в 32.10 — не перенесена в канон | Перенести фактический контракт из 32.10/кода в 32.3; 32.4 псевдокод → реальный экспорт через MemoryCube |

## P1 — Устаревшее и внутренние противоречия (1 день)

> **✅ DONE 2026-07-05** (commits `1b6bfd812`…`c5ee8edcf` + хвосты; 2 параллельных агента + сам).
> **Code-first (2 реальных бага найдено):** (1) `test_wiki_promoter` — 5 красных тестов = test-debt
> (фикстура на ретированном `usage_count`), НЕ прод-баг (см. баннер P0-раздела); фикс под §22-контракт,
> 15/15. (2) **Латентный прод-баг** `WikiSearchIndexer.index_page` — `await hybrid_search.index_document(doc_id=, content=, metadata=)` при **sync** 2-арг сигнатуре → `index-search` CLI молча индексировал 0 страниц
> (каждая падала в per-page `except`); фикс `wiki_exporter.py:772` (+ `remove_page` тот же класс) +3 регресс-теста;
> флагнут агентом-B при сверке доков. **Доки:** «10 link-типов»→8 (27.12 ×3, 27.12.3 ×2), cap 50→10 (27.9),
> P5.3 RETIRED-консистентность (27.8), dead test path (27.3), протухшие мета-⚠ сняты (27.12.2/27.12.4 + top-200→500),
> promotion detached-Popen + F13 (32.6/32.9/37.5), WikiSearchIndexer листинги по коду (32.7/32.2),
> RRF-веса L3/L4 (37.3/37.8: md=0.15/wiki=0.20), CLI 8→9 (promote-openspec), LoC 692→802, skill wiki-pipeline
> якоря+test-count. **Открытый флаг:** `HybridSearchService.index_document` sync-без-metadata — 32.7 несёт ноту
> о расхождении с историческим 4-полевым payload `wiki_pages_v1` (три формата — см. P1-строку 32.7).

- **«10 link-типов» → 8** (ADR-L1): 27.12 ×3 места (167-168, 268, 410) + 27.12.3 ×2 (14, 135) — файл противоречит собственной легенде §10 («8 типов»).
- **27.2**: фантомные поля MemCube `quality_score`/`access_count`/`last_accessed` (в коде нет); `ContentType` 6 → **7** (есть `WIKI`; 27.1:14 тоже); RRF-веса `{1.0/0.9/0.7}` поданы как дефолты — в коде default `None` → все 1.0.
- **27.9:69**: reinforcement «cap 50» → в проде **cap 10** (`pattern-reinforce-stop.py:44,105`; 50 — лишь DEFAULT_CAP библиотеки); сам хук `pattern-reinforce-stop.py` в главе не назван.
- **27.8**: внутреннее противоречие P5.3 «RETIRED 2026-06-12» (шапка) vs «DONE / ALL DONE» (итоговая таблица :288-294).
- **27.3:24**: мёртвый путь тестов `scripts/claude-backend/tests/...` → `tests/integration/test_memory_first_hook.py`.
- **Протухшие мета-⚠**: 27.12.2:78 и 27.12.4:151-153 предупреждают об ошибках в 27.2/27.3/27.10, которые уже починены — пометы ложно дискредитируют исправленные главы. + 27.12.4:59 «top-200» → 500.
- **32.6/32.9/37.5**: Stop-hook promotion — уже НЕ `subprocess.run(timeout=4)`, а detached `Popen` + лог `session-promote.log`; F13-идемпотентность (`promoted_to`-skip + штамп) не описана; тестов промоутера 15→19; субкоманд CLI 8→**9** (`promote-openspec` не описан нигде, каталог `docs/wiki/openspec/` отсутствует в layout 32.3).
- **32.7/32.2**: листинги `WikiSearchIndexer` фабрикованы (реально `index_page()->None`, нет `_extract_metadata`, есть недокументированный `remove_page()`); **три несовпадающих формата payload** `wiki_pages_v1` (док / код / live-точки) — разобраться, каким путём писался live.
- **37.8:57 / 37.3:59**: RRF-веса «L3=0.15, L4=0.20» перепутаны местами (код: md=0.15, wiki=0.20); wiki_exporter «692 LoC» → 802; путь `tests/unit/test_memcube_wiki.py` → `tests/integration/`.
- Мелочь: 32.9:106 typo «In obstetric состоянии»; 37.9 «export --all» → `export-all`; якоря классов 32.2 съехали (~8 строк); снапшоты (drafts 0→7, entities 2822→2823).
- **Skill `wiki-pipeline` тоже дрейфанул**: якорь `WikiSearchIndexer:643` → :753; счётчик тестов не включает `test_incremental_wiki_sync.py` (5).

## P2 — Структура (по мере прохода)

> **✅ DONE 2026-07-05** (3 параллельных агента + сам; адверсариальный ревьюер PASS — потерь факта НЕТ).
> Приём «обзор→указатель на карту-канон» (как 43.5 §0 в 260704). Свёртка: 27.2 (219→158), 27.4 (226→162),
> 27.5 (246→216), 27.6 (170→103), 27.8 (295→178) — глубокие дубли констант/формул заменены указателями
> на каноны 27.12.2/27.12.5/27.12.6/27.3/27.12.1; уникальные код-примеры и single-source-компоненты сохранены
> (**ConflictResolver** проверен — 27.12.5 его НЕ описывает → оставлен развёрнутым в 27.4, 27.6 шлёт туда).
> **P2.4/R2:** глава 5.3 Hermes → ARCHIVE-баннер на все 9 файлов (канон = 32.x; конфликт нумерации слоёв
> L0..L4↔L1..L5 снят), 37.2/37.5 свёрнуты (история в `<details>`), merge-ноты на уникальных 37.4/37.6/37.7
> (Sandbox/OAuth — реальный код, при реорганизации перенести в 05.6/админ; физически НЕ двигал — риск).
> **P2.3:** план-эпоха «Embedding A/B/C» из 27.8 удалена. **P2.5:** date→topic индекс в 27.13.
> **Хвост (pre-existing, в P3):** 27.3 migration-note всё ещё поминает дропнутые `experience_embeddings`/
> `conversation_memory` (ADR Q1 260603) — не этой волной, поправить при следующем проходе 27.3.

| # | Что | Действие |
|---|---|---|
| P2.1 | **Пары «обзор ↔ карта»**: 27.2↔27.12.2, 27.5↔27.12.6 — карта точна, обзор фантомит | Санировать обзоры до навигационного уровня, конкретика — ссылкой на 27.12.x как канон (тот же приём, что 43.5 §0 в P2 260704) |
| P2.2 | Тройной дубль EventBus/EventStore/ConflictResolver: 27.4 + 27.6 + 27.12.5 | 27.12.5 — канон; 27.4/27.6 сжать до указателей |
| P2.3 | 27.8 дублирует 27.3 (recall) + 27.12.1 (save) + несёт план-эпоху «Embedding варианты A/B/C» | Сжать до указателей + краткая история моста |
| P2.4 | **5.3 Hermes**: 37.2 ≈70% дубль 32.x с КОНФЛИКТУЮЩЕЙ нумерацией слоёв (32.1: L1..L5 vs 37.2: L0..L4), 37.5 ≈80%, 37.3 ≈50% | **ARCHIVE с merge** (см. R2) |
| P2.5 | 27.13 — простыня без индекса (194 строки) | Оглавление дат/тем в шапку |

## P3 — Пробелы покрытия (код без доков)

> **✅ DONE 2026-07-05** (2 агента; facts сверены с кодом, link-sweep 6 файлов PASS). Задокументированы:
> **retention.py** (27.12.3 §1 «TTL нет» ИСПРАВЛЕНО — есть lazy importance-decay half-life 90д для
> `session_summary`/`general` + age-archive `archive_episodic` 90д/imp<0.8; `effective_importance`
> используется в ai-адаптере) · **WikiDecayService** (27.12.6 §7.1 — линейный `decay_rate·days/30` decay
> `learned_patterns.confidence`, CLI-only из `export_graph_to_wiki`) · **merge-консолидация** (27.12.6 §8,
> из G2) · **два писателя drafts/** (32.6/37.5 — WikiPromoter batch vs `route_and_save._save_to_target("wiki")`
> де-факто основной синхронный) · **wiki-tooling пласт** (32.9 — 5 скриптов + `_is_noise_entity_name` +
> test_incremental_wiki_sync). promote-openspec/openspec/ уже были (P0/P1); merge_patterns — G2.
> **⚠ КОД-НАХОДКА (не docs, → решение):** WikiDecayService (линейный) и §22 (Beta) ОБА пишут
> `learned_patterns.confidence` без определённого приоритета. Но §22 деривит confidence из succ/fail
> **на чтении** → линейные writes WikiDecayService не авторитетны (перезаписываются на след. apply) —
> вероятно **legacy/superseded**. Кандидат в ADR: ретайр WikiDecayService или явно развести роли.
> **✅ РЕШЕНО 2026-07-05 ([ADR-046](../../.claude/skills/architecture-research/adr/046-retire-wikidecayservice-superseded-by-s22.md)):** РЕТАЙР (удалён класс + 14 тестов + CLI-субкоманда `decay-confidence`). Behavior-preservation reviewer PASS — 0 живых импортёров, §22 decay независим/цел, все 3 утверждения ADR (effective-не-stored / overwrite-on-apply / двойной-decay legacy) сверены с кодом. Доки: 27.12.6 §7.1 + 32.6/32.10/37.8/01.2 + 2 skill. **Follow-up (не блокер, из ревью):** `WikiPromoter` Qdrant-prefilter (`wiki_promoter.py:57`) всё ещё Range-gte по stored `confidence` (паттерн, снятый в `search_patterns`); post-filter re-gates на effective → под-гейтинга нет, но over-exclusion до пост-фильтра теоретически возможен — отдельная тема.

- `WikiDecayService` (`librarian/wiki_decay.py`) — не упомянут ни в одном 27.x; в карте governance 27.12.6 wiki-decay отсутствует как механизм забывания.
- `ai_memory/retention.py` (importance-decay half-life 90d + `archive_episodic`) — 27.12.3 §1 утверждает «TTL нет», живой retention не отражён.
- `skill_learning/merge_patterns.py` — что мержит, кто зовёт — нигде.
- **Второй наполнитель `drafts/`** (route_and_save / memory-router `_save_to_target("wiki")`) — де-факто основной, не описан ни в 32.6, ни в 37.5.
- Пласт wiki-tooling вне глав: `wiki_cleanup_noise_entities`, `wiki_entity_merge_apply`, `wiki_create_stubs`, `wiki_backlink_walker`, `wiki_confidence_status_sync`, `_is_noise_entity_name`-фильтр, `test_incremental_wiki_sync.py`.
- `promote-openspec` (9-я субкоманда CLI) + `docs/wiki/openspec/`.

---

## §БП — Сверка с ведущими GitHub-практиками (mem0 / Letta / Zep-Graphiti / LangMem)

Полный research-кеш: [`llm-agent-memory-best-practices-2026.md`](../../.claude/skills/architecture-research/cache/llm-agent-memory-best-practices-2026.md).

### Где мы УЖЕ соответствуем лидерам

| Практика лидеров | Наш аналог | Статус |
|---|---|---|
| Hybrid retrieval ≥3 сигналов + fusion (mem0, Graphiti) | 4 arms + RRF k=60 в memory-first-hook | ✅ |
| Confidence как вероятностная модель | Beta(7,3) posterior + decay (§22) | ✅ (у лидеров зачастую проще) |
| Карантин/подтверждение знаний (LangMem agent-autonomy) | skill-learning pending/confirm конвейер | ✅ |
| Provenance/citations (Graphiti episodes) | ADR-011 citations `file:line` в курируемой памяти | ✅ частично (только curated-слой) |
| Git-tracked память (Letta MemFS) | `docs/wiki/` + auto-git-save | ✅ по форме |
| Event-log/audit | event_store, memory_audit_log, honest-failure контракт | ✅ |

### Разрывы с практиками лидеров (кандидаты в улучшения)

| # | Разрыв | Практика лидера | У нас | Оценка |
|---|---|---|---|---|
| G1 | **Би-темпоральность** | Graphiti: у факта `valid_from/invalid_at`, инвалидация вместо удаления, запрос «что было истинно в T» | `archived` = hard-exclude, без временных окон; конфликт-резолюция без датировки фактов | Сложность High, ценность Mid — **отложить** до реального кейса темпоральных запросов |
| G2 ✅ **DONE 2026-07-05** | **Hot-path vs background консолидация** | mem0 ADD-only hot-path; Letta «dreaming»; LangMem background manager | ~~`merge_patterns.py` есть, но не в каденсе~~ → **job `merge`** в `memory_maintenance.py` (`run_merge_patterns`): `PatternMerger` (был orphaned, 0 вызовов) над SAVED-силосом skill_learning; дедуп по нормализованному содержимому (by_name-индекс в PatternMerger — dead code, не потребляется), dry-run default, `.bak`-снапшот, fail-soft. Hot-path оставлен O(1) `content_hash`; дорогой similarity-дедуп ушёл в фон. Тесты `TestMergeJob`(3). Commit — этой сессии | Сложность Low-Mid, ценность High — ✅ closed |
| G3 | **Entity linking между записями** | mem0: сущности извлекаются/линкуются → retrieval boost | link_registry (8 типов) связывает ЗАПИСИ, но нет автоматического entity-linking по содержимому | Сложность Mid, ценность Mid |
| G4 ✅ **DONE 2026-07-05** | **Memory-бенчмарк end-to-end** | Zep: LongMemEval, LoCoMo как gate | ~~только surfacing-слой~~ → [`scripts/memory_e2e_benchmark.py`](../../scripts/memory_e2e_benchmark.py): пишет факты РЕАЛЬНЫМ эмбеддером в ИЗОЛИРОВАННУЮ коллекцию (`memory_e2e_eval`, prod не трогает) → recall перефраз-запросами → hit/recall/mrr/ndcg. Метрики reuse из `memory_golden_harness` (single source). Ловит класс бага, невидимый surfacing-харнессу (write-path пишет 0). Датасет 10 фактов, 11 unit + живой прогон hit_rate=1.0. Graceful (TEI/Qdrant down → exit 0) + prod-guard. Адверсариальный ревью поймал P1 (Qdrant-down не обрабатывался) → фикс. **Ограничение:** факты различны → потолок метрики, ловит катастрофу write-path, не тонкие ранжир-регрессии (harden = near-dup дистракторы) | Сложность Mid, ценность High — ✅ closed |
| G5 | **Time-aware retrieval** | mem0: ранжирование правильного датированного экземпляра | recency-буст есть в decay, но запрос «текущее vs прошлое состояние» не различается | Сложность Mid, ценность Low-Mid — после G4 |

### Evaluation Matrix (что делать первым)

| Критерий | G2 background-консолидация | G4 memory-бенчмарк | G1 би-темпоральность | G3 entity linking |
|---|---|---|---|---|
| Сложность | Low-Mid | Mid | High | Mid |
| Трудозатраты | дни | дни | недели | дни-недели |
| Ценность сейчас | High (Stop-хуки разгружаются, дедуп системный) | High (объективация качества) | Mid | Mid |
| Совместимость с кодом | High (каденс уже есть) | High (golden-set расширить) | Low (схема хранилищ) | Mid |
| Обратимость | Да | Да | Частично | Да |

**Рекомендация:** G2 → G4 (в этом порядке); G1/G3/G5 — в backlog до появления кейса.

---

## Рекомендации (порядок исполнения)

1. **R1 (решение пользователя)**: судьба kb-lint enforcement — восстановить проводку в `.pre-commit-config.yaml` или честно задокументировать отключение (P0.1). Восстановление затронет скорость коммитов — нужен выбор.
2. **R2**: 5.3 Hermes → **ARCHIVE-баннер на всю подглаву** + merge живого: 37.4 (лучший read-path) → в 32.7/27.3; 37.6 Sandbox → гл. 05.6; 37.7 OAuth → в администрирование; 37.2/37.5 → указатели. Устраняет худший вид дрейфа — два конфликтующих канона слоёв.
3. **R3**: волна P0 (6 пунктов) — фикции/copy-paste-риски, один проход.
4. **R4**: волна P1 — построчные правки по списку выше (переиспользовать паттерн параллельных агентов с file-ownership).
5. **R5**: P2-санация «обзор→указатель на карту» — тот же приём, что 43.5 §0.
6. **R6 (код, по матрице)**: G2 — консолидация в maintenance-каденс; затем G4 — end-to-end memory-бенчмарк.
7. После волн — прогон `scripts/docs_counters.py --check` и re-verify агентом.

> ⚠ Roadmap-оценки исторически завышены 1.5–3×; объёмы сверять с фактом (инвентарь тут точный: 39/39 файлов прочитано, ~70 фактов сверено).

---

## §18 Прогресс

> Append-only, новые записи сверху.

### 2026-07-05 — WikiDecayService РЕТИРОВАН (ADR-046, code-first) + docs_counters --check
- Код-находка P3 закрыта решением: DELETE WikiDecayService (3 опции взвешены — не deprecate/repurpose). Удалён класс+14 тестов+CLI-субкоманда; §22 = единый авторитет decay. Behavior-preservation reviewer PASS. ADR-046 accepted. Доки: 27.12.6 §7.1 + 4 secondary + 2 skill; 0 битых ссылок.
- п.4 `docs_counters --check` прогнан (RC=0): хиты — глобальный counter-дрейф в ДРУГИХ скиллах (hooks-skills-mcp-triad bundle/hook-счётчики, learning-loop size), в основном regex-FP; вне зоны 260705 (память), не трогал.
- Follow-up (не блокер): WikiPromoter Qdrant-prefilter stored-conf Range-gte — отдельная тема.

### 2026-07-05 — §БП G4 end-to-end memory-бенчмарк (code-first)
- `scripts/memory_e2e_benchmark.py` — write→recall над изолированной коллекцией; метрики reuse из memory_golden_harness; 11 unit + живой прогон (n=10, hit_rate=1.0 через реальный TEI+Qdrant).
- Адверсариальный ревьюер PARTIAL→FAIL поймал P1 (seed_live не обрабатывал Qdrant-down → traceback вместо exit 0) + prod-guard + honesty-нота → всё исправлено, runtime-проверено (bad-port → live-deps-unavailable; learned_patterns → refused).
- Датасет data/memory/e2e/dataset.jsonl force-add (data/ gitignored, конвенция data/eval).

### 2026-07-05 — R2 физперенос устаревших Hermes-глав (3/3 ✅)
- 37.6 Sandbox → 05.6 Sandbox_исполнения (SandboxBackend/E2B/LangSmith/Security); 37.7 OAuth → 09.2 Авторизация (mcp_oauth/*). Оба сведены к redirect-стубам (баннер+указатель), −742 строки дублей, link-sweep PASS, факты сверены с кодом.
- 37.4 Read-Path → 27.3 Memory_First_Hook: перенесены direct-query MCP-инструменты + antipatterns (остальное 27.3 уже покрывал полнее). R2 ✅ 3/3.

### 2026-07-05 — P3 пробелы покрытия закрыты (2 агента)
- retention.py / WikiDecayService / два-писателя-drafts / wiki-tooling пласт — задокументированы с file:line; 27.12.3 «TTL нет» исправлено.
- Код-находка (→ ADR-кандидат): WikiDecayService (линейный decay) vs §22 (Beta on-read) на одном поле `learned_patterns.confidence` — §22 деривит из счётчиков на чтении → WikiDecayService-writes не авторитетны, вероятно legacy.
- merge_patterns (G2) + promote-openspec/openspec (P0/P1) — уже закрыты ранее. Link-sweep 6 файлов PASS.
- Осталось из 260705: R2-физперенос 37.4/37.6/37.7; §БП G4 (memory-бенчмарк).

### 2026-07-05 — Runtime-верификация G2: PASS (все слои)
- E2E `--apply` на КОПИИ продакшн-силоса: синтетический near-дубль (case/whitespace-вариация) корректно слит (winner=higher-confidence, `.bak` создан), повторный прогон **идемпотентен** (0 merged).
- Полный CLI-прогон каденса (merge+forget+review_pending+archive+link_stats живьём, Qdrant): дашборд несёт строку `merge: {...}` (:42), RC ok; Stop-хук-спавнер зовёт скрипт без арг-конфликтов — новый job подхватывается автоматически.
- 20 тестов (TestMergeJob+TestPatternMerger+Dashboard+ForgetGate) passed.
- Ops-заметка (не G2): дашборд алертит `pdf_documents` STALE (44.6 дн. без run_end) — pre-existing, кандидат на переиндексацию.

### 2026-07-05 — §БП G2 исполнен (background-консолидация, code-first)
- `merge_patterns.py::PatternMerger` был **orphaned** (0 вызовов) — вскрыто investigation'ом; wired в maintenance-каденс как job `merge` (`run_merge_patterns`, dry-run default, `.bak`-снапшот, fail-soft).
- Паттерн лидеров (mem0 ADD-only / Letta dreaming): дорогой similarity-дедуп SAVED-силоса skill_learning ушёл из hot-path Stop-хуков в фон-каденс; hot-path оставлен O(1) `content_hash`.
- Найдено по пути: `PatternMerger.similarity_threshold` — мёртвый параметр (реализация делает exact-normalized+name grouping, не fuzzy-cosine) — не трогал (out of scope, поведение корректно).
- Тесты: `TestMergeJob`(3, wiring) + `TestPatternMerger` (логика, была) — 14 passed в test_memory_maintenance, ruff clean, cadence-smoke dry-run OK (силос 3 паттерна, 0 дублей сейчас — job ловит будущее накопление).
- Осталось из §БП: G4 (end-to-end memory-бенчмарк типа LongMemEval) — следующий по матрице.

### 2026-07-05 — P2 исполнен (docs-консолидация), 3 агента
- Свёртка «обзор→указатель на карту-канон»: 27.2/27.4/27.5/27.6/27.8 (суммарно −327 строк дублей), каноны 27.12.x.
- P2.4/R2: ARCHIVE-баннер на всю 5.3 Hermes (9 файлов) + свёртка 37.2/37.5 → снят конфликт нумерации слоёв с 32.x; уникальные 37.4/37.6/37.7 помечены merge-нотами (не двигал физически).
- P2.3 план-эпоха убрана из 27.8; P2.5 индекс в 27.13.
- Адверсариальный ревьюер: PASS, потерь уникального факта нет; ConflictResolver single-source сохранён.
- Осталось: R2-физ-перенос 37.4/37.6/37.7 (tech-debt, помечен), P3-пробелы (WikiDecay/retention/merge_patterns без доков), §БП G2/G4.

### 2026-07-05 — Runtime-верификация P1 поймала ТРЕТИЙ латентный баг, commit `5c81ab395`
- По запросу «проверь реализацию» прогнан runtime-слой верификации (e2e на РЕАЛЬНЫХ классах — обязанность оркестратора по контракту code-verify, статический ревьюер это не покрывает).
- **Пойман баг №3:** `HybridSearchService` не имел `remove_document` вовсе — метод жил только на внутреннем `BM25Index` (ревьюер сверил имя по :157, но не класс-владельца); `remove_page` падал AttributeError. MagicMock фабрикует любой атрибут → mock-тест проходил. Фикс: делегат на сервисе + **anti-mock регресс** `test_real_hybrid_search_roundtrip` (реальные классы: index→search→remove→re-search).
- e2e живьём: 11 drafts проиндексировано, 0 warnings, BM25-hit, remove OK; регресс потребителей hybrid_search — 156 passed.
- Урок в копилку: mock-тесты не ловят несуществующие атрибуты; runtime-слой верификации обязателен для fixes «интерфейсного шва».

### 2026-07-05 — P1 исполнен (code-first), commits `1b6bfd812`…`c5ee8edcf`
- 2 реальных code-fix: test-debt в test_wiki_promoter (не прод-баг) + латентный прод-баг index_page (await на sync index_document → index-search индексировал 0).
- ~20 doc-правок дрейфа (link-types 8, cap 10, RRF-веса, promotion Popen+F13, WikiSearchIndexer, CLI 9) — 2 агента, file-ownership.
- Тесты: 44 passed (wiki_exporter +3 регресс) + 15/15 promoter; skill wiki-pipeline синхронизирован.
- Осталось: P2 (обзор→указатель), R2 (ARCHIVE 5.3), P3-пробелы, §БП G2/G4.

### 2026-07-05 — P0 исполнен (code-first), commit `10633f4ee`
- R1 решён восстановлением проводки (не переписыванием доки); wiki снова гейтится на commit.
- 3 код-бага по пути: encoding-крэш kb-lint scanner, bare-`--ci` root-линт, писатели drafts без status/tags/MD047.
- Оба хука Passed на 21 файлах; тесты 36/36; адверсариальный ревьюер PASS, рекомендации применены.
- Находка → P1: WikiPromoter under-promotion после §22 P2 (eff-conf гейт), 5 красных pre-existing тестов.
- Осталось: P1, P2, R2 (ARCHIVE 5.3), P3-пробелы, §БП G2/G4.

### 2026-07-05 — Аудит выполнен, дорожная карта создана
- 2 read-агента: 39/39 файлов, ~70 утверждений сверено с кодом; research лидеров (mem0/Letta/Zep-Graphiti/LangMem) закеширован.
- Ключевые открытия: 32.8 — глава-фикция (kb-lint не в pre-commit); 5.3 — дубль 5.2 с конфликтующей нумерацией слоёв; паттерн «обзор фантомит при точной карте» (27.2/27.5/27.7 vs 27.12.x).
- Волны P0 (6) / P1 / P2 (5) / P3 (пробелы) / §БП (5 разрывов с лидерами, матрица) сформированы.
- Статус: **pending** (не начато); R1 требует решения пользователя.
