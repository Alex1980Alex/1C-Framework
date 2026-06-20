# 01 — Планирование

Закрыть остаток семантики (DBSF 0.38 → dense-only ceiling 0.42 на S) через **bm25-confidence-gated fusion** (если bm25_top1 < θ → запрос out-of-vocab → dense-only; иначе DBSF). ADR-028 deferred-причина: query-form classifier регрессит L (оба golden NL); нужен identifier-golden + механизм, не регрессящий L/identifier. Measure-first, без подтверждений.
