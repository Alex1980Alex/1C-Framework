# 04 — Тестирование

- `py_compile` → 0; `ruff check` → clean.
- **Smoke прод-пути:** `SearchManager._call_qdrant_search` на 3 семантич. запросах → **3/3 hits=10** через RRF, exit 0 (TEI dense + FastEmbed bm25 + Qdrant RRF исполняются).
- **code-verify reviewer** (bug-fix-validation + behavior-preservation) → **PASS**: RRF-вызов побитово = bench-эталон; имена параметров qdrant верны (`Prefetch.filter`); fallback-каскад полон, без UnboundLocalError; маппинг универсален; `dense_only` legacy цел; нет двойного filter; instruct-prefix + sparse-нормализация в паритете с bench.
- Числовой acceptance (hybrid recall@10 L 0.78 / S 0.34 vs BM25-first 0.68/0.16) — verified на уровне коллекции в Phase 0 (тот же харнесс/коллекция, что зовёт сервис).

**Вердикт: PASS.**
