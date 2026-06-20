# 02 — Дизайн (approved)

1. Построить **identifier-golden** (I): query = имя символа (из `_meta.name` semantic-golden), expected тот же → BM25-сильный класс для контроля регресса.
2. Eval gated-fusion `bm25_top1 < θ → dense-only, иначе DBSF` на L (NL in-vocab) / S (NL out-vocab) / I (identifier), свип θ по перцентилям распределения bm25_top1.
3. **Критерий внедрения:** S↑ к 0.42 БЕЗ регресса L и I. Иначе — отклонить, DBSF остаётся.
Скрипт: `scripts/bsl_phase3_adaptive_eval.py` (read-only).
