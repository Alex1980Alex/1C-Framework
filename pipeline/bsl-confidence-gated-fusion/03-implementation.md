# 03 — Реализация (measurement; код search.py НЕ менялся)

- [`scripts/bsl_phase3_adaptive_eval.py`](../../scripts/bsl_phase3_adaptive_eval.py) — генератор identifier-golden (из `_meta.name`) + eval gated-fusion + θ-свип + распределения bm25_top1 (read-only к Qdrant/TEI).
- `data/eval/bsl/bsl_identifier_golden.json` — 50 identifier-запросов (query = имя символа).
- `data/reports/bsl_phase3_adaptive_eval.json` — baseline + bm25_top1.
- **`src/bsl/.../search.py` НЕ изменён** — measurement отклонил gating (см. 04 + ADR-028 addendum). DBSF остаётся.
