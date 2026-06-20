# ADR-028: BSL retrieval fusion — DBSF default (supersedes BM25-first)

**Дата:** 2026-06-20
**Статус:** accepted
**Исследование:** [../cache/bsl-embedding-collapse-remediation-2026.md](../cache/bsl-embedding-collapse-remediation-2026.md)

## Контекст

Прежний prod-default BSL retrieval — **pure BM25** (memory `feedback-bsl-sparse-bm25-dominance`, 2026-05-22), на основании realistic eval «dense 18% / BM25 76%». **Phase 0** (2026-06-20, Workflow `bsl-collapse-phase0` + ручная ре-верификация канонического `bench_bsl_realistic_eval.py`) показала: эти числа **НЕ воспроизводятся** — dense здоров (lexical 0.72 / semantic 0.42), «18%» был артефактом устаревшего/багнутого eval; синтетик-анкор «90/17» — отдельный biased бенч (дословные код-подстроки). На семантике (vocab-mismatch) bm25 кратерит (0.16), dense несёт recall, наивный RRF проседает под мёртвым bm25-плечом (dense-only 0.42 > RRF 0.34). «Collapse» (eff_rank 5.5%) реален, но безвреден для retrieval.

## Решение

BSL hybrid-default = **DBSF** (Distribution-Based Score Fusion, native Qdrant ≥1.10), с graceful fallback на RRF. **Phase 2** measurement (recall@10, L+S golden, read-only):

| split | dense | bm25 | RRF | **DBSF** | wrrf 70/30 |
|---|---|---|---|---|---|
| L (lexical) | 0.72 | 0.68 | 0.80 | **0.80** | 0.78 |
| S (semantic) | 0.42 | 0.16 | 0.34 | **0.38** | 0.40 |

DBSF **строго доминирует RRF** (L равно 0.80, S +4pp) без регресса и **без query-классификатора** — z-нормализация скоров каждого плеча сама приглушает мёртвое bm25-плечо на vocab-mismatch. Реализация — `_call_qdrant_search` hybrid-ветка ([src/bsl/semantic_search/services/search.py](../../../../src/bsl/semantic_search/services/search.py)).

## Последствия
### Положительные
- Семантика +4pp над RRF, +22pp над прежним BM25-first (0.16→0.38); лексика без регресса (0.80); query-classifier не нужен.
- Graceful degradation: TEI down → BM25-only (прежний дефолт), BM25/FastEmbed down → dense-only, DBSF unsupported → RRF.
### Отрицательные
- +1 TEI dense embed на дефолтный запрос (latency; цена за recall, fallback при TEI down).
- DBSF не достигает dense-only ceiling на S (0.38 vs 0.42) — остаток за query-adaptive (отклонён — L-регресс).
- Требует `/mcp reconnect` для live-эффекта в MCP `bsl-semantic-search` ([[feedback-mcp-stale-code-reconnect]]).

## Альтернативы
- **pure-BM25** (прежний) — кратерит на семантике (0.16). Отклонён (был основан на артефакт-eval).
- **RRF** — DBSF строго лучше (S +4pp, L равно). Оставлен как fallback.
- **weighted-RRF dense-heavy (70/30)** — S 0.40 (ещё +2pp), но L −2pp (0.78). Отклонён в пользу no-regression DBSF.
- **query-form classifier (NL→dense / id→bm25)** — оба golden = NL, классификатор по форме их не разделяет; на L dense-heavy регрессит. Отклонён.

## Phase 3 addendum (2026-06-20) — confidence-gated fusion измерено и ОТКЛОНЕНО
Остаток на S (DBSF 0.38 → dense-only ceiling 0.42) пытались закрыть **bm25-confidence-gating** (`bm25_top1 < θ → dense-only, иначе DBSF`); построен **identifier-golden** (I, query=имя символа) для контроля регресса. Измерение ([`scripts/bsl_phase3_adaptive_eval.py`](../../../../scripts/bsl_phase3_adaptive_eval.py), L/S/I, θ-свип): bm25_top1 L median 53.5 > S 30.6 (разделимы), **но I перекрывает S** (редкие low-IDF имена символов). В no-regression точке (θ≈26): S +2pp = шум (1 запрос из 50); значимый S-прирост (θ≈46 → S 0.46) **регрессит identifier** (I 0.96→0.90 — gating мис-роутит точные имена в dense-only). θ настроен на тех же 50 запросах → overfit-риск на проде. **Вердикт: не внедрять — DBSF остаётся финальным дефолтом**; deferred-пункт query-adaptive закрыт измерением (не гипотезой). Артефакты: `data/eval/bsl/bsl_identifier_golden.json`, `data/reports/bsl_phase3_adaptive_eval.json`.

## Связанные файлы
- [src/bsl/semantic_search/services/search.py](../../../../src/bsl/semantic_search/services/search.py) `_call_qdrant_search`
- [scripts/bsl_phase2_fusion_eval.py](../../../../scripts/bsl_phase2_fusion_eval.py) · data/eval/bsl/bsl_semantic_golden.json
- memory `feedback-bsl-sparse-bm25-dominance` (СУПЕРСЕДЕД) · cache `bsl-embedding-collapse-remediation-2026`
