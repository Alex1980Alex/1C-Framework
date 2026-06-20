# 02 — Дизайн (approved)

В `_call_qdrant_search` (src/bsl/semantic_search/services/search.py) hybrid-ветка: **pure BM25 → hybrid RRF** — Prefetch dense(`using=dense`) + bm25(`using=bm25`, filter внутри каждого) → `FusionQuery(Fusion.RRF)`, зеркало проверенного `bench_bsl_realistic_eval.py`. Graceful degradation: TEI down → bm25-only (прежний дефолт), bm25/FastEmbed down → dense-only, оба down → []. `dense_only` legacy-ветка не тронута. query-adaptive fusion (dense-heavy для NL; S dense-only 0.42 > hybrid 0.34) — следующий шаг.
