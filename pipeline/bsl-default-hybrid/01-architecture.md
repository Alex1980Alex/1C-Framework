# 01 — Планирование

Переключить BSL retrieval default `using="bm25"` → **hybrid RRF**. Основание — Phase 0 (Workflow `bsl-collapse-phase0` + ручная ре-верификация канонического харнесса): прежний вердикт «dense сломан 18% / BM25-first» НЕ воспроизвёлся (артефакт), dense здоров (L 0.72 / S 0.42), hybrid бьёт BM25-first на ОБОИХ сплитах (L +10pp, S +18pp recall@10).
