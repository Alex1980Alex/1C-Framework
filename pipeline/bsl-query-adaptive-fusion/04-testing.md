# 04 — Тестирование

- **Measurement** (recall@10): DBSF L 0.80 / S 0.38 — строго ≥ RRF (0.80 / 0.34) на обоих сплитах; data/reports/bsl_phase2_fusion_eval.json.
- `py_compile` → 0; `ruff check` (search.py + eval) → clean.
- **Smoke прод-пути** (`_call_qdrant_search`, 2 семантич. запроса) → 2/2 hits=10 через DBSF, без fallback-warn (native DBSF исполняется), exit 0.
- Wiring (Prefetch/Fusion/fallback-каскад) — reviewer-PASS в предыдущей правке (hybrid), DBSF = замена enum + try/except RRF.

**Вердикт: PASS** (DBSF строго доминирует RRF, без регресса).
