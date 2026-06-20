# 03 — Реализация

- [`scripts/bsl_phase2_fusion_eval.py`](../../scripts/bsl_phase2_fusion_eval.py) — measurement 6 fusion-вариантов на L+S (read-only).
- [`src/bsl/semantic_search/services/search.py`](../../src/bsl/semantic_search/services/search.py) `_call_qdrant_search` both-arms: `FusionQuery(RRF)` → **`FusionQuery(DBSF)`** + try/except RRF-fallback; docstring обновлён.
- [ADR-028](../../.claude/skills/architecture-research/adr/028-bsl-fusion-dbsf-default.md) + adr/_index.json.
- Fallback-каскад (TEI down→bm25, bm25 down→dense) не тронут.
