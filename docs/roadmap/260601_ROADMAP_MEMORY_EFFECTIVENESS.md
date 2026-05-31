# Roadmap — Memory Effectiveness Metrics & Self-Tuning (§25)

> **Дата:** 2026-06-01 · **Статус:** PLANNED (дизайн готов, реализация впереди) · **Родитель:** [260523 §25](260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md)
>
> На основании этой главы выполняется реализация. Части: **A** (read-only analyzer), **B** (self-tuning loop). Research — live WebSearch/WebFetch + source-level (см. §2, цитаты).

## 1. Проблема (verified live, эта сессия)

Глава 27 (Unified Memory) имеет **операционные** метрики ([`MetricsCollector`](../../src/memory/infrastructure/metrics.py): counters/gauges/timers, MCP `memory_metrics`/`get_system_stats`) и **само-коррекцию доверия** (§22 confidence lifecycle: reinforce → Beta-update → decay/forget/revive — замкнутая петля на уровне «каким знаниям доверять»). Свежо добавлена **наблюдаемость качества** — два JSONL-лога:
- `.claude/cache/confidence-lifecycle.log` (§22.4) — мутации доверия;
- `.claude/cache/memory-first-surfacing.log` (§24.4) — стадии каждого surfacing.

**Чего НЕТ (пробел):**

| Пробел | Последствие |
|---|---|
| Метрики **качества** surfacing (precision@k / hit-rate инжектируемого контекста) | меряем латентность/объёмы, не релевантность |
| **Анализатор** логов (по образцу `post-indexing-analyzer.py`) | логи пишутся, но никто не агрегирует → нет отчёта/аномалий |
| **Авто-тюнинг** параметров surfacing | RRF-веса (0.7/0.3), gating-пороги (0.15/0.30), TTL — статические константы; нет петли «деградация → подстрой» |
| Регрессионный **gate / алерты** | нет порога «качество < X → алерт» |

Вывод: петля «измеряю качество → анализирую → чиню параметры» **разомкнута на этапе анализа**. Данные для замыкания (оба лога) уже собираются.

## 2. Research synthesis (live, цитируемый)

### 2.1 Метрики качества retrieval/memory

- **AutoRAG** (Marker-Inc, AutoML-style) — retrieval-метрики `retrieval_f1`, `retrieval_recall`, `retrieval_ndcg`, `retrieval_mrr` + retrieval-token-метрики; node-line (lexical/semantic/hybrid_rrf/prompt_maker/generator); YAML-config → `summary.csv` **авто-выбирает лучший pipeline**. НЕ алгоритмический поиск — exhaustive trial comparison. [GitHub Marker-Inc-Korea/AutoRAG; arxiv 2410.20878]
- **mem0** — сводные KPI памяти: LoCoMo **91.6**, LongMemEval **94.8**, BEAM(1M) **64.1**; **91% ниже latency** vs full-context; eval open-sourced; multi-signal retrieval (semantic+BM25+entity) + temporal reasoning. [GitHub mem0ai/mem0; arxiv 2504.19413]
- **MemMachine** — LoCoMo **0.9169**, LongMemEval **93%**; вывод: **retrieval-stage optimizations дают больше, чем ingestion-stage**. [arxiv 2604.04853]
- **Letta** (MemGPT) — core (in-context) + archival (vector) память; LongMemEval ~**83.2%**. [letta.com blog]
- **Awesome-RAG-Evaluation** (YHPeter) — survey метрик оценки RAG; **NirDiamant/Agent_Memory_Techniques** — LoCoMo/eval notebooks. [GitHub]

### 2.2 Hybrid-fusion + взвешивание

- **WRRF (Weighted Reciprocal Rank Fusion)** — вносит retriever-side confidence в fusion; **MMMORRF** — modality-aware веса по надёжности сигнала. Урок: веса плеч можно делать **адаптивными**, не фиксированными. [emergentmind RRF; uregina WRRF paper]
- ⚠ Предупреждение из источников: **RRF улучшает recall сильнее, чем ranking-fidelity** → мониторить не только recall, но и **NDCG@k**; relevance-drift в fusion-пайплайнах с LLM-reformulation реален. [maxpetrusenko; emergentmind]

### 2.3 Self-tuning стратегии (часть B) — два полюса

- **AutoRAG-HP** (arxiv 2406.19251) — online hyper-parameter tuning как **multi-armed bandit (MAB)** + Hierarchical-MAB; тюнит top-k, compression-ratio, embedding; **Recall@5 ≈ 0.8 при ~20% LLM-вызовов** относительно Grid Search. Вывод: **online-bandit ВИАБЕЛЕН и дёшев** (рефайнит исходную осторожность «только offline»). [aka.ms/autorag]
- **AutoRAG (offline sweep)** — детерминированный перебор конфигов на golden-set, промоушен по `summary.csv`. Безопасен, откатываем, не дёргает hot-path.
- **Risk-sensitive contextual bandit для memory-retrieval** (arxiv 2604.27283) — abstention-aware: bandit решает *когда вообще доставать память*, конвертит relevance/uncertainty в contextual state. **PURPLE** — bandit-оптимизация user-profile под reward. [arxiv 2601.12078]
- **self-improving-rag** (tonumayworkspace) — практический образец замкнутой петли: Hybrid BM25+Vector + LLM query-rewrite + **RAGAS eval + feedback loop**. **RAGTune** / **Hybrid-Search-RAG** — automated tuning пакеты. [GitHub]
- **Образец репозитория:** `post-indexing-analyzer.py` (Stop-хук → детач `analyze_run.py` → отчёт в `data/reports/`) — **прямой архитектурный образец части A**. §22 Beta-posterior — образец статистически-обоснованного обновления (не дёргать параметр на каждом наблюдении).

### 2.4 Решение по части B (с учётом research)

Источники дают два жизнеспособных пути: **offline sweep** (AutoRAG, детерминизм) и **online MAB** (AutoRAG-HP, дёшево/адаптивно). Для **hot-path memory-hook** выбираем **offline sweep + gated promotion как базу** (безопасность, откат, аудит), а **online-MAB документируем как future-вариант B3** после валидации golden-set и метрик — он подтверждённо работает, но требует guardrail против нестационарности.

## 3. Метрики (что меряем)

| Метрика | Источник | Тип |
|---|---|---|
| `surfacing_hit_rate` | applied pids / surfaced pids (reinforcement) | online proxy |
| `no_results_rate` | outcome=no-results / всего | online |
| `cache_hit_rate` | cache=hit / всего | operational |
| `tei_down_rate` | tei=down / всего | health |
| `gate_drop_rate` | gate.archived+below_floor / candidates | quality |
| `arm_contribution` | доля fused по плечам (dense vs lexical) | diagnostic |
| `confidence_drift` | средний old→new по lifecycle-log за окно | §22 health |
| `precision@k` / `NDCG@k` (offline) | golden-set memory-queries | quality (нужен датасет) |
| `latency p50/p95` | surfacing duration_ms | operational |

> NDCG@k включён осознанно — research (§2.2) предупреждает, что recall обманчив в RRF-пайплайнах.

## 4. Часть A — read-only analyzer

**Компонент:** `scripts/analyze_memory_effectiveness.py` + Stop-хук-триггер (по образцу [`post-indexing-analyzer.py`](../../.claude/hooks/post-indexing-analyzer.py)).

- **Вход:** `memory-first-surfacing.log` + `confidence-lifecycle.log` (построчный `json.loads`, окно `--since`).
- **Считает:** агрегаты §3.
- **Выход:** Markdown-отчёт в `data/reports/memory/` + JSON sidecar + `_latest.md` (формат как у indexing-отчётов).
- **Рекомендации (без применения):** rule-based — `tei_down_rate>0.3 → поднять lexical-вес`; `gate_drop_rate>0.5 → пересмотреть MIN_SURFACE_CONF`; `no_results_rate>0.4 → проверить покрытие коллекций`; `cache_hit_rate≈0 → проверить epoch-инвалидацию`.
- **Свойства:** read-only, fail-soft, idempotent (FIFO-state как у analyzer), opt-out env, cold-start seed, учитывает `cache=hit` отдельно (не считает как pipeline-run).

**Acceptance A:**
- [ ] отчёт из обоих логов, корректные агрегаты на синтетике;
- [ ] рекомендации rule-based, без побочных эффектов;
- [ ] smoke-тест (Qdrant-independent), как `test_analyze_run.py`.

## 5. Часть B — self-tuning loop

**Механизм (база): offline sweep + gated promotion** (AutoRAG-style); **online-MAB — future B3** (AutoRAG-HP).

- **Параметры под тюнинг:** `SURFACE_RRF_WEIGHTS` (lexical/dense), `MIN_SURFACE_CONF`, `CONF_FLOOR`, `MEMORY_SURFACE_CACHE_TTL`.
- **Хранилище конфига:** вынести константы из `memory-first-hook.py` в `data/memory/surfacing_tuning.json` (overridable; default = текущие значения) — реверсивно.
- **Цикл:** analyzer (A) детектит деградацию → sweep кандидатов на golden-set → промоушен **только** при улучшении целевой метрики (NDCG@k + hit-rate) ≥ threshold → запись в tuning.json + audit в lifecycle-log.
- **Guardrails:** clamp диапазонов, dry-run by default (`MEMORY_AUTOTUNE_APPLY=1`), авто-откат при регрессии на следующем окне, полный audit.
- **Зависимость:** golden-set memory-queries (≥30 размеченных) — **prerequisite (B0)**.

**Acceptance B:**
- [ ] golden-set memory-queries создан + версионирован;
- [ ] sweep улучшает целевую метрику на held-out без регрессии;
- [ ] promotion gated + reversible + audited; dry-run by default;
- [ ] авто-откат при регрессии проверен.

## 6. Фазовый план

| Фаза | Объём | Зависит |
|---|---|---|
| **A0** | вынести surfacing-константы в `surfacing_tuning.json` (reversible) | — |
| **A1** | `analyze_memory_effectiveness.py` — агрегаты + Markdown/JSON отчёт | A0, логи (есть) |
| **A2** | Stop-хук-триггер + rule-based рекомендации + smoke-тест | A1 |
| **B0** | golden-set memory-queries (≥30) + harness | A1 |
| **B1** | offline sweep по golden-set, dry-run «лучший конфиг» (AutoRAG-style) | B0, A0 |
| **B2** | gated promotion + auto-rollback + audit (self-tuning замкнут) | B1 |
| **B3** *(future)* | online-MAB тюнинг (AutoRAG-HP), guardrail против нестационарности | B2 |

A0–A2 — самостоятельная ценность (наблюдаемость) без рисков B. B — отдельный заход после golden-set.

## 7. Риски

| Риск | Митигация |
|---|---|
| Online-тюнинг нестабилен | база = offline sweep; online-MAB только B3 с guardrail |
| Нет golden-set → нельзя мерить precision честно | B0 prerequisite; до него — online-proxy метрики |
| recall обманчив в RRF (research §2.2) | целевая метрика = NDCG@k + hit-rate, не recall в одиночку |
| Авто-тюнинг ухудшит prod | dry-run by default + clamp + auto-rollback + audit |
| Логи неполны (cache-hit пропускает стадии) | analyzer считает `cache=hit` отдельно |

## 8. Источники (live research 2026-06-01)

- [AutoRAG (Marker-Inc-Korea)](https://github.com/Marker-Inc-Korea/AutoRAG) — AutoML retrieval-метрики + auto-select pipeline; [arxiv 2410.20878](https://arxiv.org/abs/2410.20878)
- [AutoRAG-HP](https://arxiv.org/pdf/2406.19251) — online MAB hyper-parameter tuning, Recall@5≈0.8 при ~20% cost
- [mem0](https://github.com/mem0ai/mem0) — KPI памяти (LoCoMo/LongMemEval/BEAM), multi-signal retrieval; [arxiv 2504.19413](https://arxiv.org/pdf/2504.19413)
- [MemMachine](https://arxiv.org/pdf/2604.04853) — retrieval-stage > ingestion-stage
- [self-improving-rag](https://github.com/tonumayworkspace-creator/self-improving-rag) — RAGAS eval + feedback loop образец
- [RAGTune](https://github.com/misbahsy/RAGTune), [Hybrid-Search-RAG](https://github.com/kolhesamiksha/Hybrid-Search-RAG) — automated tuning пакеты
- [Awesome-RAG-Evaluation](https://github.com/YHPeter/Awesome-RAG-Evaluation), [Agent_Memory_Techniques](https://github.com/NirDiamant/Agent_Memory_Techniques) — метрики/benchmarks
- Risk-sensitive contextual bandit для memory-retrieval: [arxiv 2604.27283](https://arxiv.org/html/2604.27283); PURPLE: [arxiv 2601.12078](https://arxiv.org/pdf/2601.12078)
- WRRF: [uregina paper](https://uregina.ca/~nss373/papers/Rag-CCNC2026.pdf); RRF overview: [emergentmind](https://www.emergentmind.com/topics/reciprocal-rank-fusion-rrf)
- Внутренние: [27.9](../framework%20documentation/27_UNIFIED_MEMORY/27.9_Confidence_Lifecycle.md), [27.10](../framework%20documentation/27_UNIFIED_MEMORY/27.10_Memory_Surfacing_Quality.md), образец [`post-indexing-analyzer.py`](../../.claude/hooks/post-indexing-analyzer.py) + `analyze_run.py` + chapter 28_1

## 9. Связанные

- [27.9 Confidence Lifecycle](../framework%20documentation/27_UNIFIED_MEMORY/27.9_Confidence_Lifecycle.md) (§22)
- [27.10 Memory Surfacing Quality](../framework%20documentation/27_UNIFIED_MEMORY/27.10_Memory_Surfacing_Quality.md) (§24)
- [260523 §25](260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md) — родительский указатель
- Skills: `evaluation-benchmark` (метрики), `memory-unified`, `tech-research`
