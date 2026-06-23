# 02 Дизайн — A/B/C (approved, ADR-038)

**Part A (профилактика).** `--long-batch1-tokens N` + чистый `_long_batch1_buckets(buckets,N)`:
batch=1 для чанков > N токенов (короткие быстрые). Прокидка `__init__`→`make_embedder`→`main`.
Дефолт 0 = поведение прежнее.

**Part B (сетка безопасности).** `scripts/reindex_supervised.py`: resume + парсинг `idle=` из
`[hb]`; `idle>1200с` → kill дерева → перезапуск с меньшим batch (32→8→1). resume сохраняет
прогресс; batch=1 не виснет. Эскалация batch вместо poison-by-path (буфер across-files).

**Part C (no-loss).** `--max-file-bytes` → deferred-list `data/reports/reindex_deferred.txt`;
`--paths-file FILE` → влить в `--paths` (argv-лимит) → retry `--paths-file <list> --batch-size 1`.

**Anti-deadlock/safety:** всё аддитивно, дефолты OFF, behavior-preserving, реверсивно; прод
git-hook (qwen3-tei) не затронут. Решение зафиксировано в **ADR-038** (accepted).

Альтернативы отклонены: expandable_segments (вредит), глобальный batch=1 (×32 медленнее),
poison-by-path (нечёткая атрибуция). → **approved**.
