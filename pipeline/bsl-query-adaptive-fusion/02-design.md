# 02 — Дизайн (approved) — ADR-028

Measurement (scripts/bsl_phase2_fusion_eval.py, read-only, L+S × 6 вариантов) → выбор fusion. Кандидаты: RRF (baseline), **DBSF** (score-distribution, native), weighted-RRF 70/30 & 60/40, dense_only, bm25_only. Критерий: лучший на S без регресса L. Победитель — **DBSF** (L 0.80=RRF, S 0.38 vs 0.34, строго доминирует, без классификатора). Реализация: `_call_qdrant_search` hybrid both-arms ветка → `FusionQuery(DBSF)` + RRF-fallback. weighted-RRF (S 0.40, L −2pp) отклонён — компромисс.
