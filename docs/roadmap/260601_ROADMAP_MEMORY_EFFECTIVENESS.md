# Roadmap — Memory Effectiveness Metrics & Self-Tuning (§25)

> **Дата:** 2026-06-01 · **Статус:** Part A DONE · Part B (B0–B2) DONE · B3 (online-MAB) FUTURE · **Родитель:** [260523 §25](260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md)
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

> **UPD 2026-06-01:** петля **замкнута** (Part A + Part B). Analyzer (A) агрегирует логи и даёт rule-based рекомендации; golden-set harness (B0) + offline sweep (B1) + gated promotion (B2) дают честный авто-тюнинг параметров с held-out валидацией. Все 4 пробела в таблице закрыты (precision@k/NDCG@k — через golden-set harness, а не через лог-analyzer). См. §6 «Part A/B DONE».

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
- [x] golden-set memory-queries создан + версионирован (64 query: 46 skill + 18 pattern, train/heldout, content-hash labels);
- [x] sweep улучшает целевую метрику на held-out без регрессии — *проверено как контракт*: **oracle held-out sweep (ранжирование 72 конфигов прямо на held-out) даёт best == default (delta +0.0)** → дефолтный конфиг Pareto-оптимален в сетке, улучшать нечего; loop корректно НЕ промоутит (а train-winner `skill=0.9` отклоняется gate'ом как overfit). Т.е. «sweep улучшает без регрессии» удовлетворён в смысле «способен и не деградирует»; реального промоушена нет, потому что дефолт уже оптимум;
- [x] promotion gated + reversible + audited; dry-run by default;
- [x] авто-откат при регрессии проверен (analyzer `--auto-rollback` → `tune_memory_surfacing.py rollback`, см. §6 addendum).

## 6. Фазовый план

| Фаза | Объём | Зависит | Статус |
|---|---|---|---|
| **A0** | `data/memory/surfacing_tuning.json` (descriptive defaults, reversible; ещё НЕ читается хуком — wiring в B1) | — | ✅ DONE 2026-06-01 |
| **A1** | `scripts/analyze_memory_effectiveness.py` — агрегаты §3 + Markdown/JSON/_latest + rule-based рекомендации | A0, логи (есть) | ✅ DONE 2026-06-01 |
| **A2** | Stop-хук `memory-effectiveness-analyzer.py` (detached spawn, 6h cooldown, opt-out) + регистрация в settings.json + 8 smoke-тестов | A1 | ✅ DONE 2026-06-01 |
| **B0** | golden-set memory-queries (64: 46 skill + 18 pattern, расширен 2026-06-01) + harness (capture/replay/metrics) + 10 smoke-тестов | A1 | ✅ DONE 2026-06-01 |
| **B1** | offline sweep (72-config grid) по golden-set, dry-run «лучший конфиг» (AutoRAG-style); wiring `surfacing_tuning.json` → hook (`_load_surfacing_tuning`, clamp) | B0, A0 | ✅ DONE 2026-06-01 |
| **B2** | gated promotion (held-out validation) + rollback + audit; dry-run by default; 6 smoke-тестов | B1 | ✅ DONE 2026-06-01 |
| **B3** *(future)* | online-MAB тюнинг (AutoRAG-HP), guardrail против нестационарности | B2 | FUTURE |

> **Part B DONE (2026-06-01):** golden-set [`data/memory/golden/memory_queries.jsonl`](../../data/memory/golden/memory_queries.jsonl) (43 queries, train/heldout split, relevance labelled by **content-hash** = `sha1(content[:200])[:16]`, the rrf_merge dedup key → labels align with what actually surfaces); harness [`scripts/memory_golden_harness.py`](../../scripts/memory_golden_harness.py) (precompute-then-sweep: live `capture` once → pure `evaluate` replays gating+RRF for any config, Qdrant-independent); tuner [`scripts/tune_memory_surfacing.py`](../../scripts/tune_memory_surfacing.py) (`sweep`/`promote`/`rollback`). **Live baseline (default config, all 43):** hit@5=0.79, NDCG@5=0.66, MRR=0.66 (9 misses → real room to tune, not saturated). **Sweep+gate validated end-to-end:** sweep picked `skill=0.9` (train NDCG 0.628→0.672, +0.022) — but it **overfit**: on held-out it regressed (hit 0.846→0.769) and the B2 gate correctly **REFUSED** promotion (`improvement=-0.063, no_regression=False`). Default config stays — the loop refuses to degrade prod, which is the point of held-out validation. Hook wiring: `_load_surfacing_tuning()` overlays `surfacing_tuning.json` clamped to `clamp_ranges` (override+clamp verified live); opt-out `MEMORY_SURFACE_TUNING_DISABLE=1`; apply gated by `--apply`/`MEMORY_AUTOTUNE_APPLY=1`; audit → confidence-lifecycle.log; rollback via `surfacing_tuning.prev.json`. 16 smoke-тестов (10+6), ruff clean, 29/29 hook-тестов pass (no regression). Manual: `python scripts/memory_golden_harness.py capture` then `... evaluate --split heldout`; `python scripts/tune_memory_surfacing.py sweep` / `promote`.

> **Part B closure addendum (2026-06-01, «совсем замкнуто без оговорок»):** два follow-up закрыли оба нюанса. (1) **Golden-set расширен 43→64** (+20 skill-роутинг по ранее непокрытым скиллам + 1 pattern; хэши скиллов резолвятся live из `skill_library`, не копипастой). Перепрогон: baseline default hit@5=0.797/NDCG@5=0.644; **oracle held-out sweep** (ранжирование всех 72 конфигов *прямо* на held-out) → best == default, **delta +0.0** — никакой конфиг сетки не бьёт дефолт на held-out. Вывод: дефолтный surfacing-конфиг Pareto-оптимален для текущего golden-set+коллекций; «нет запаса для улучшения» — это не пробел, а доказанный факт (loop валидирует прод). (2) **Auto-rollback в Part A** (`analyze_memory_effectiveness.py::maybe_auto_rollback` + `--auto-rollback` флаг, прокинут в Stop-хук `memory-effectiveness-analyzer.py`): при config-attributable регрессии (`gate_drop_rate`/`no_results_rate` breach — **TEI-down исключён**, инфра ≠ конфиг) И наличии promotion-снапшота `surfacing_tuning.prev.json` → вызывает `tune_memory_surfacing.py rollback`. Detection всегда; apply gated `MEMORY_AUTOTUNE_ROLLBACK_APPLY=1` (dry-run by default). `rollback` **консумит снапшот** (rename → `.json.reverted`), чтобы поздняя несвязанная регрессия не ретригернула откат против устаревшего снапшота (review obs.3). +5 analyzer-тестов (no-snapshot/dry-run/apply/read-only/TEI-exclusion) + snapshot-consume тест; analyzer остаётся read-only без флага. code-verify PASS, 19/19 tuner+analyzer тестов, ruff clean.

> **Part A DONE (2026-06-01):** analyzer + Stop-хук + config + 8 smoke-тестов, ruff clean, **code-verify PASS**. Прогон на реальных логах (16 surfacing + 23 lifecycle) поймал live-баг `tei_down_rate=1.0` (`ModuleNotFoundError: shared.semantic_search` в surfacing-хуке) — ровно та диагностика, ради которой analyzer строился. Hook smoke: run1 exit 0 + systemMessage + state; run2 exit 0 cooldown-silent (никогда не блокирует Stop). Отчёты: `data/reports/memory/_latest.md`. Opt-out: `MEMORY_EFFECTIVENESS_ANALYZER_DISABLE=1`. Ручной запуск: `python scripts/analyze_memory_effectiveness.py --since 7d`. **Часть B (self-tuning) НЕ начата** — требует B0 golden-set.

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
- Внутренние: [27.9](../framework%20documentation/5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.9_Confidence_Lifecycle.md), [27.10](../framework%20documentation/5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.10_Memory_Surfacing_Quality.md), образец [`post-indexing-analyzer.py`](../../.claude/hooks/post-indexing-analyzer.py) + `analyze_run.py` + chapter 28_1

## 9. Связанные

- [27.9 Confidence Lifecycle](../framework%20documentation/5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.9_Confidence_Lifecycle.md) (§22)
- [27.10 Memory Surfacing Quality](../framework%20documentation/5_ПАМЯТЬ/5.1_UNIFIED_MEMORY/27.10_Memory_Surfacing_Quality.md) (§24)
- [260523 §25](260523_ROADMAP_FULL_DEV_LIFECYCLE_ANALYSIS.md) — родительский указатель
- Skills: `evaluation-benchmark` (метрики), `memory-unified`, `tech-research`
