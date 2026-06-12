# 260612 — Roadmap: полная проверка pdf-docs (DOCS, Qdrant) — вход, выход, место в карте памяти

> Статус: PROPOSED · Создан: 2026-06-12 · Источник: анализ блока `pdf-docs` карты
> [27.12 §map](../framework%20documentation/27_UNIFIED_MEMORY/27.12_Memory_Systems_Map.md), по образцу
> [260612 memory-ai full verification](260612_ROADMAP_MEMORY_AI_FULL_VERIFICATION.md) + методика chain-testing
> [260610](260610_ROADMAP_MEMORY_CHAIN_TESTING.md)
> Связанные: [260609 P1 write-contract](260609_ROADMAP_MEMORY_PIPELINE_HARDENING.md), [260611 governance wiring](260611_ROADMAP_MEMORY_GOVERNANCE_WIRING.md), chapter 31 (Qwen3 retrieval), chapter 28_1 (auto-reports)

## 1. Инвентаризация (фактическое состояние 2026-06-12)

**Хранилище** — Qdrant, alias-дисциплина соблюдена (4 alias), физика:

| Alias | Physical | Points | Dim | Sparse | Замечание |
|-------|----------|--------|-----|--------|-----------|
| `pdf_documents` | `pdf_documents_mrl_1024` | 830 | 1024d | нет | продакшн |
| `wiki_pages_v1` | `wiki_pages_v1_mrl_1024` | 3 073 | 1024d | нет | продакшн |
| — | `pdf_documents_mrl_4096` | 830 | 4096d | нет | **orphan** (без alias) |
| — | `pdf_documents_mrl_512` | 830 | 512d | нет | **orphan** (MRL-bench остаток) |
| — | `pdf_documents_4096_backup` | 830 | 4096d | нет | бэкап-источник re-embed |
| — | `wiki_pages_v1_4096_backup` | 3 073 | 4096d | нет | бэкап-источник re-embed |

Итого 5 физических копий pdf-корпуса и 2 wiki-корпуса; sparse/hybrid BM25 для docs
**не внедрён** (alias указывает на dense-only `mrl_1024`; `scripts/bench_hybrid_pdf_documents.py`
§4.1.16 PROOF существует, но swap на `pdf_documents_hybrid` не выполнен/откатан — открытый вопрос).

**Писатели (вход), 5:**
| # | Писатель | Канал | Состояние |
|---|----------|-------|-----------|
| W1 | `index_pdf` / indexing pipeline | `pdf-vector-graph` MCP + CLI (`src.cli`) | живой; `_progress` instrumentation есть (run_end `pdf_documents` 2026-05-22) |
| W2 | `eval_hermes_phase4.py index-wiki` | wiki .md → `wiki_pages_v1` | живой, но **вне `_progress`** (нет run_end → auto-reports 28_1 не генерятся) |
| W3 | миграционные скрипты (`reembed_collection.py`, alias swap, MRL-bench) | ручные | живые, snapshot+alias паттерн |
| W4 | golden-append (`append_golden_v23_pdf.py`, `append_golden_v24.py`) | ручные | живые, уважают alias |
| W5 | `DocsRagSearchAdapter.ingest_document` | `src/memory/ai_memory/adapters/docs_rag.py` | **мёртвый** (см. D1) |

**Читатели (выход), 6:**
| # | Читатель | Канал | Состояние |
|---|----------|-------|-----------|
| R1 | `search_documents` / `ask_question` / `research` / `visual_*` | `pdf-vector-graph` MCP | живой production-RAG |
| R2 | `docs-change-enforcer.py` | wiki_pages_v1 similarity → подсказка главы | живой |
| R3 | wiki-pipeline `HybridSearchService` | `wiki_pages_v1` | живой |
| R4 | golden evals (v23 pdf / v24 wiki) | `scripts/eval_*` | живые, baseline recall |
| R5 | `unified_search` docs-плечо | оркестратор | **ОТСУТСТВУЕТ** (адаптер не зарегистрирован — см. D2) |
| R6 | `memory-first-hook` surfacing | UPS-хук | docs-коллекции **не опрашиваются** (только `learned_patterns` + `skill_library`) |

**Identity / links:** `SourceServer.PDF_DOCS` + `create_doc_id()` существуют в `unified_id.py`,
но **0 production-использований**; link_registry: **0 рёбер `docs:*`**, и вообще **0 рёбер
`based_on`** («Pattern based on documentation» — заявленный link-type ни разу не создан).
`_get_entity` / TTL / versioning не поддерживают PDF_DOCS (honest `unsupported_source`, но
нигде не зафиксировано как решение).

**Freshness:** `pdf_documents` — последний run_end **2026-05-22** (3 недели);
`wiki_pages_v1` — run_end в `data/indexing-progress.jsonl` отсутствует вовсе;
эталон каденса — `framework_code_v1` (auto-reindex on commit, последний 2026-06-12).

## 2. Проблема (что нашла инвентаризация)

- **D1 — мёртвый и вводящий в заблуждение контур** `DocsRagSearchAdapter` (P3-миграция
  2026-04-04): собственная SQLite chunks-БД (default `chunks_db_path=""`!), Qdrant-коллекция
  `docs_chunks` (**не существует**), эмбеддер заимствован у vector_memory (Qwen3 **4096d**)
  против собственного дизайна — `_vector_search` тихо глотает всё (`except: return []`),
  `ingest_document` при включённом vector-флаге писал бы 4096d-точки в несуществующую/чужую
  коллекцию. Используется ТОЛЬКО `tests/integration/test_memory_p3_deferred.py` — зелёные
  тесты создают иллюзию живого контура. Прямой аналог G1 из 260612 memory-ai.
- **D2 — federated-слепота**: карта 27.12 рисует `pdf-docs` 4-й колонкой хранилищ, но
  `unified_search` не имеет docs-плеча (зарегистрированы только Ai/Vector/SkillLearning
  адаптеры) — «документация в памяти» фактически отдельная вселенная, достижимая только
  через `pdf-vector-graph` MCP. Либо плечо, либо ADR-фиксация non-goal — сейчас ни того ни другого.
- **D3 — гигиена коллекций**: 2 orphan-копии pdf-корпуса (`_mrl_4096`, `_mrl_512` — остатки
  MRL-бенчей) без alias и без политики; бэкапы `*_4096_backup` бессрочные и нигде не
  описаны как канонический источник re-embed. Риск не столько RAM (корпуса маленькие),
  сколько путаница physical/alias при ручных операциях (`--recreate` caveat из
  [[reference-qdrant-collection-aliases]]).
- **D4 — identity и связи мертвы**: ни один паттерн/wiki-страница не ссылается на
  документ-источник (`based_on` = 0); `docs:pdf-docs:*` не существует как класс сущностей →
  `get_full_context`/`get_related` никогда не приведут к документации.
- **D5 — freshness не управляем**: документация (`docs/framework documentation/*`) меняется
  ежедневно, индекс pdf от 22 мая; wiki-индексация вне instrumentation (нет run_end → нет
  auto-report → дрейф невидим); reindex-каденса нет ни у pdf, ни у wiki
  (у `framework_code_v1` есть — эталон).
- **D6 — наблюдаемость**: docs-писатели не эмитят `record_ingest`/`record_store_size`
  (maintenance-dashboard `store_sizes` считает только wiki **drafts** на диске — 0, при
  3 073 живых точках в Qdrant); fact-trace не тредит документы.
- **D7 — document_registry пуст при живой коллекции** (найден 2026-06-12 post-P4, при
  живой проверке `list_documents`): `data/document_registry.db` (Phase 32 Multi-Document KB)
  имеет 0 строк при 830 точках в `pdf_documents` — единственный писатель реестра =
  REST API routes (`src/api/routes/documents.py`, 4 вызова `register()`), а production-путь
  (W1 CLI/MCP `index_chunks`, W3 `reindex_pdf_documents.py`) реестр обходит. Читатель
  `list_documents` (MCP `server.py:502`) при этом молча отдаёт `[]` — расхождение невидимо
  (анти-паттерн honest-failure 260611). Класс D1: заявленный контур, который production
  обходит; реестр не числился даже в инвентаризации W1-W5/R1-R6 этого роадмапа.
- **Тестовое покрытие**: e2e index→search цепочек нет; golden evals есть (v23/v24), но
  гоняются вручную; контракт payload и alias-резолюции не закреплён тестами.

Целевая модель: **каждый вход и выход pdf-docs покрыт исполняемой цепочкой, место блока
в карте памяти зафиксировано ADR'ом (плечо или non-goal), физические коллекции — под
политикой, freshness виден и управляем.**

## 3. Тест-карта цепочек вход→выход (ядро роадмапа)

Методика 260610: цепочка = вход → store-инвариант → выход(ы); unit где возможно
(payload/alias-логика без Qdrant), live — против локального Qdrant. Вердикты в §18.

### Блок A — входы

| # | Цепочка | Шаги | Критерий приёмки |
|---|---------|------|------------------|
| A1 | W1 index happy | `index_pdf` тестового PDF → точки в `pdf_documents` | payload-контракт (source/page/content), точки видны `search_documents`, run_end в progress-логе, повторная индексация не плодит дубли |
| A2 | W2 wiki index | `index-wiki` → upsert в `wiki_pages_v1` | идемпотентность (re-run = upsert, не дубль), run_end появляется в `_progress` (после P3.1) |
| A3 | W3 alias swap | snapshot → re-embed → alias switch (методика [[reference-qdrant-collection-aliases]]) | читатели R1-R3 не ломаются в момент свопа; `resolve_physical_collection` отрабатывает |
| A4 | W4 golden append | append-скрипт → `target_collection` через alias | точки легли в актуальный physical, recall-наборы валидны |
| A5 | dim-контракт | запросный путь (TEI 4096d → MRL truncate 1024d) vs коллекция | запрос в `pdf_documents` (1024d) работает; запрос тем же вектором в `*_4096_backup` — честная ошибка размерности (защита от регресса G1-класса) |

### Блок B — выходы

| # | Цепочка | Шаги | Критерий приёмки |
|---|---------|------|------------------|
| B1 | R1 search smoke | известный факт из проиндексированного PDF → `search_documents` | релевантный чанк в top-5; и для RU-морфоформы запроса |
| B2 | R1 RAG e2e | `ask_question` по тому же факту | ответ с атрибуцией на документ |
| B3 | R2 enforcer suggestion | правка файла с известной главой → docs-change-enforcer | подсказка указывает верную главу из `wiki_pages_v1` |
| B4 | R5 docs-плечо | (после D2-решения) `unified_search` по доке | либо `docs:pdf-docs:<id>` в results + `sources_failed` честный при TEI/Qdrant-down, либо ADR non-goal в §18 и карте 27.12 |
| B5 | R4 golden baseline | прогон golden v23 (pdf) + v24 (wiki) | recall не ниже зафиксированного baseline (замерить ДО любых миграций P0) |

### Блок C — отказы (honest-failure, контракт 260611)

| # | Цепочка | Критерий |
|---|---------|----------|
| C1 | Qdrant down при R1 | MCP-tool отдаёт честную ошибку, не виснет (S1-S3 warmup уже в server.py) |
| C2 | alias → отсутствующий physical | читатель честно фейлится с понятным сообщением, не пустым результатом |
| C3 | TEI down при поиске | `search_documents` — честный fail/fallback; docs-плечо (если будет) → `sources_failed:["pdf-docs"]` |

## 4. Фазы

### P0 — Обезвреживание + гигиена коллекций (фундамент)

| # | Задача | Файлы | Критерий |
|---|--------|-------|----------|
| P0.1 | **D1**: `DocsRagSearchAdapter` — ретирование в attic вместе с `test_memory_p3_deferred.py` (его docs-частью) ИЛИ rewire на production `pdf_documents` + общий MRL-путь; решение зафиксировать ADR-строкой в §18. Дефолт — ретирование: production-RAG уже есть в `pdf_framework`, дублирующая SQLite-вселенная не нужна | `src/memory/ai_memory/adapters/docs_rag.py`, тест | запуск контура не может породить мусорные точки; зелёных тестов мёртвого кода нет |
| P0.2 | **B5-baseline ДО миграций**: прогнать golden v23/v24, зафиксировать recall в §18 | `scripts/eval_*` | числа в §18 |
| P0.3 | **D3**: политика физических коллекций — verify (counts/выборочные id vs alias-таргет) → drop orphans `pdf_documents_mrl_4096`, `pdf_documents_mrl_512` (snapshot перед drop); `*_4096_backup` объявить каноническим источником re-embed (зафиксировать в skill `qdrant-operations`) | Qdrant + skill | physical-коллекций без роли нет; политика записана |
| P0.4 | **D4-фиксация**: PDF_DOCS в `_get_entity`/TTL/versioning — задокументировать `unsupported_source` как осознанное решение (docs immutable со стороны памяти) | 27.12 / ADR-строка | карта не обещает того, чего нет |

### P1 — ВХОД: цепочки A1-A5 исполняемы

- Unit-слой: payload-контракт точки, alias-резолюция, MRL truncate (детерминированные
  функции без Qdrant) — `tests/unit/test_pdf_docs_chains.py`.
- Live-слой: A1 (тестовый PDF через `index_pdf`), A2 (index-wiki), A5 (dim-проба);
  A3/A4 — процедурные прогоны при ближайшей реальной миграции (не форсить ради галочки).

### P2 — ВЫХОД: цепочки B1-B5 + D2-решение

| # | Задача | Механизм |
|---|--------|----------|
| P2.D2 | **ADR**: docs-плечо в `unified_search` — Option A: тонкий `PdfDocsSearchAdapter` поверх `pdf_documents`+`wiki_pages_v1` (переиспользовать query-вектор vector-плеча, НЕ второй TEI-embed на hot path; честный `sources_failed`); Option B: non-goal — docs читаются только через `pdf-vector-graph`, карта 27.12 корректируется. Решение по результатам B1-B3: если production-RAG закрывает все сценарии — Option B дешевле и честнее | `memory_orchestrator.py` или 27.12 |
| P2.D4 | Если Option A: результаты несут `docs:pdf-docs:<id>` (create_doc_id наконец живой); `based_on`-рёбра — опционально из WikiPromoter (wiki-страница → документ-источник), НЕ массовый backfill | orchestrator, librarian |
| P2.B3 | B3-цепочка тестом: фиктивный файл с известным маппингом → suggestion | `docs-change-enforcer.py` тест |

### P3 — Freshness (индекс не должен дрейфовать молча)

| # | Задача | Механизм |
|---|--------|----------|
| P3.1 | W2 в `_progress` instrumentation: index-wiki эмитит run_start/run_end → auto-reports 28_1 покрывают wiki | `eval_hermes_phase4.py`, `scripts/_progress.py` |
| P3.2 | Staleness-метрика в maintenance-dashboard: points_count + возраст последнего run_end per docs-коллекция (из progress-лога); алерт-строка при возрасте > N дней (default 30) | `src/memory/maintenance/dashboard.py`, `scripts/memory_maintenance.py` |
| P3.3 | Reindex-каденс: job `reindex_wiki` в maintenance-каденсе (после export_graph_to_wiki — генерация и индексация в одном пайплайне, иначе drift wiki .md ↔ wiki_pages_v1); pdf — ручной триггер достаточен (корпус статичный), зафиксировать | `scripts/memory_maintenance.py` |

### P4 — Наблюдаемость и приёмка

- D6: `collect_store_sizes` считает `pdf_documents`/`wiki_pages_v1` points (сейчас только
  drafts на диске) → `record_store_size` → bounded-growth tracking; `record_ingest` для
  index-ранов — опционально (run_end в progress-логе уже даёт событие, не дублировать без нужды).
- **Acceptance-окно 2 недели** (каркас 260612 переиспользовать: `acceptance_common.py` +
  `acceptance_watch.py` — третий потребитель, не копипастить):
  0 orphan-коллекций вне политики; wiki run_end присутствует в progress-логе; staleness-метрика
  в дашборде и возраст обоих индексов < 30d (или каденс-решение в §18); B1/B3 smoke зелёные;
  golden recall ≥ baseline из P0.2; D2-решение зафиксировано (плечо отдаёт хиты ИЛИ ADR non-goal).

## 5. Порядок и оценка

P0 (0.5-1d: D1 решение + verify/drop + baseline) → P1 unit+live (0.5-1d) →
P2 (0.5-1.5d: **ADR прежде кода** — Option B может закрыть фазу без строчки кода) →
P3 (0.5-1d) → P4 (0.5d каркас + 2 недели наблюдения). Учитывать
[[project-roadmap-audit-pattern]]: перед каждой фазой — повторная инвентаризация
(alias-состояние могло измениться смежными работами; hybrid-вопрос §1 проверить первым).

## 6. Риски

- **Drop физических коллекций необратим**: перед удалением orphans — verify counts +
  выборка точек vs alias-таргет + snapshot (методика [[reference-qdrant-collection-aliases]]);
  `*_4096_backup` НЕ трогать — единственный источник re-embed без повторного прогона эмбеддера.
- **D2 Option A — латентность hot-path**: federated search уже платит за TEI-embed
  vector-плеча; docs-плечо обязано переиспользовать готовый вектор (второй embed = ×2 латентность);
  замер `sources`-таймингов до/после, бюджет как у остальных плеч.
- **MRL и модельные свопы**: per-corpus bench mandatory ([[feedback-mrl-content-matters]]) —
  любые изменения эмбеддинг-пути docs только через golden v23/v24 (поэтому baseline в P0.2,
  ДО любых действий).
- **Hybrid BM25 вопрос**: для BSL sparse доминирует ([[feedback-bsl-sparse-bm25-dominance]]),
  но docs — RU/EN проза, dense работает; НЕ тащить hybrid в docs без отдельного bench
  (скрипт §4.1.16 есть — но это отдельное решение, не побочный эффект этого роадмапа).
- **Каденс wiki**: реиндексация без регенерации (или наоборот) создаёт расщеплённый мозг
  wiki .md ↔ wiki_pages_v1 — P3.3 связывает их в один пайплайн принципиально.

## §18 Progress Log

| Дата | Событие | Детали |
|------|---------|--------|
| 2026-06-12 | **D7 найден и закрыт** (registry-разрыв) | Post-P4 живая проверка `list_documents` → `[]` при 830 pts. Корень: единственный писатель `document_registry.db` = REST routes; production-писатели (W1 `index_chunks`, W3 `reindex_pdf_documents.py`) реестр обходили; `list_documents` молча отдавал `[]`. **Fix 3 слоя**: (1) backfill [`scripts/backfill_document_registry.py`](../../scripts/backfill_document_registry.py) (scroll → агрегаты per source, оба payload-диалекта `page`/`page_number`, идемпотентный INSERT OR REPLACE, `--dry-run`) — прогнан: 830 pts → 1 документ (`d71a6f4f4202c243`, Глава 5 8.3.27, 830 chunks / 218 pages), `list_documents` живой БЕЗ reconnect (реестр читается из SQLite per-call); (2) проводка `DocumentIndexer.document_registry` + register() в шаге 7 `index_chunks` (best-effort, никогда не роняет индексацию) + attach в `Components` → покрыты ВСЕ точки входа CLI/MCP/API; (3) `reindex_pdf_documents.py` зеркалит upsert в реестр (`_register_documents`). Регресс закреплён [`tests/unit/test_indexer_registry_wiring.py`](../../tests/unit/test_indexer_registry_wiring.py) (3 PASS: register-агрегаты, registry-down не валит индексацию, no-registry noop). Остаточное: honest-marker в `list_documents` при пустом реестре×непустой коллекции — кандидат в acceptance-критерий, не блокер |
| 2026-06-12 | **P1-P4 DONE** + ADR-D2 (non-goal), acceptance-окно открыто | **P1 (A-цепочки)**: unit `tests/unit/test_pdf_docs_chains.py` (18 PASS: payload-контракт, alias-резолюция, MRL truncate query/passage паритет, freshness). Live A1 вскрыл **3 реальных бага W1**: (1) `pymupdf4llm` объявлен в pyproject, отсутствовал в .venv → установлен 1.27.2.3; (2) pymupdf4llm ≥1.0 переименовал metadata `page`→`page_number` → KeyError в 2 loader'ах, починено толерантным чтением; (3) qdrant provider слал named `{dense:...}` в unnamed `pdf_documents_mrl_1024` → 400, добавлен `_has_named_dense` layout-маркер. A1 PASS: payload source/page_number/content, маркер top-1 (0.826), re-index = upsert (830→831→830 после cleanup). **A2 переписан** (W2 был опаснее заявленного: E5-large вместо Qwen3 + delete/create по ИМЕНИ ALIAS'а): теперь TEI Qwen3 → MRL truncate → alias-safe upsert + `--prune` + `_progress` (=P3.1); live: 2822 pages / 252 stale pruned / 58s / run_end в логе. A5 PASS (честный 400 dimension error, кодифицирован integration-тестом). A3/A4 — процедурные при ближайшей миграции (не форсились). **P2 (B-цепочки)**: B1 PASS (§5.13 в top-5 hybrid); B2 — retrieval жив, LLM-плечо honest-fail 429 (баланс провайдера, внешнее); **B3 был тихо сломан** (suggest слал 4096d в 1024d MRL `framework_code_v1` → except → "(no confident match)" на ЛЮБОЙ файл) — починен MRL-truncate, PASS (`unified_search.py`→27_UNIFIED_MEMORY), закреплён `tests/integration/test_pdf_docs_chains_live.py`. **ADR-D2 = Option B (non-goal)**: docs-плечо в `unified_search` НЕ создаётся — production-RAG закрывает сценарии (B1-B3), docs immutable (ADR P0.4), 0 спроса за всю историю (0 рёбер docs:*/based_on), плечо = лишняя hot-path латентность; карта 27.12 §легенда + 27.12.4 диаграмма/таблица исправлены (больше не обещают pdf-docs в federated). P2.D4 (create_doc_id жив) отпал вместе с Option A. **C-блок**: C1 наблюдён живьём (honest `No module named pymupdf4llm` от MCP-tool); C2 PASS (dangling alias → честный 404, изолированная проба); C3 PASS (TEI down → все 42 item'а в `errors[]`, не пустые результаты). **P3**: P3.1 done (index-wiki эмитит run_start/run_end); P3.2 `compute_docs_freshness` (pure, dashboard) + `collect_docs_freshness` (maintenance) + секция «Docs freshness» с ⚠ STALE-алертом (порог `DOCS_STALE_DAYS=30`); P3.3 job `reindex_wiki` в каденсе СРАЗУ после `promote` (apply-only), pdf — ручной триггер (корпус статичный, ad-hoc CLI-индексация интерактивна и run_end не требует). **P4**: store_sizes считает точки обеих коллекций (`{pdf_documents: 830, wiki_pages_v1: 2822}` в дашборде + `record_store_size`); acceptance `scripts/pdf_docs_acceptance.py` (3-й потребитель `acceptance_common`), **день 1/14: все 6 критериев PASS**, вердикт PENDING. **Eval после A2-prune**: pdf идентичен baseline (0.4205/0.6481); wiki 0.6877/0.8125 vs P0.2 0.7142/0.8646 — дельта объяснена: 3 из 34 GT-id ушли вместе с удалёнными wiki-страницами (честный freshness-sync, не регресс retrieval); acceptance-baseline = post-A2 (`pdf_docs_golden_acceptance_baseline.json`), P0.2-числа остаются pre-migration записью |
| 2026-06-12 | **P0 DONE** + ADR-D1 + ADR-P0.4 | Re-inventory: alias-состояние не изменилось, `pdf_documents_hybrid` НЕ существует (свопа §4.1.16 не было — открытый вопрос §1 закрыт: hybrid отдельным решением, не здесь). **ADR-D1**: `DocsRagSearchAdapter` ретирован (`scripts/attic/docs_rag.py`), НЕ rewire — production-RAG полностью закрыт `pdf_framework`, дублирующая SQLite-вселенная не нужна; docs-часть `test_memory_p3_deferred.py` удалена (33→27 тестов, все PASS), 6 stale-строк mypy-baseline вычищено. **P0.2 baseline (TEI Qwen3 → MRL 1024d truncate+renorm → top-10)**: `pdf_documents` NDCG@10 **0.4205** / chunk-recall@10 **0.6481** / kw-recall **0.447** (18 GT items из 22); `wiki_pages_v1` NDCG@10 **0.7142** / chunk-recall@10 **0.8646** / kw-recall **0.275** (16 GT из 20); runner `scripts/eval_pdf_docs_golden.py`, отчёт `data/eval/pdf_docs_golden_baseline_260612.json`. **P0.3**: verify orphans (830/830 pts, 5/5 sample ids = alias-таргет) → snapshots (`pdf_documents_mrl_{4096,512}-*-2026-06-12-*.snapshot`) → drop обоих; алиасы живы (830/3073 pts); политика physical-коллекций записана в skill `qdrant-operations` (`*_4096_backup` = канонический re-embed источник). **ADR-P0.4**: PDF_DOCS в governance = осознанный `unsupported_source` — docs immutable со стороны памяти (мутации только через indexing pipeline, freshness = reindex-каденс P3); зафиксировано в 27.12.3 §4 + 27.12 §карта/легенда; 27.6 DocsRag-секция переписана на retirement-notice |
| 2026-06-12 | Roadmap создан | Инвентаризация: 2 production-alias (830 + 3 073 pts, 1024d MRL, dense-only) / 5 писателей / 6 читателей; D1 (мёртвый DocsRagSearchAdapter: пустой default-путь БД, несуществующая `docs_chunks`, 4096d-эмбеддер — живёт только в integration-тестах), D2 (unified_search без docs-плеча — 4-я колонка карты не опрашивается), D3 (2 orphan + 2 бессрочных бэкапа без политики), D4 (0 рёбер `docs:*`, 0 `based_on` вообще; PDF_DOCS unsupported в governance), D5 (pdf-индекс от 2026-05-22, wiki вне `_progress`-инструментации, каденса нет), D6 (store_sizes считает drafts вместо точек, fact-trace слеп к docs); тест-карта A1-A5 / B1-B5 / C1-C3 |
