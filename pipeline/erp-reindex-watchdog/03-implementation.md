# 03 Кодирование

## Part A — `scripts/reindex_bsl_qwen3.py`
- `_long_batch1_buckets(buckets, threshold)` — module-level, типизирован, чистый.
- `Qwen3STEmbedder.__init__(... long_batch1_tokens=0)` → зовёт хелпер при >0.
- `make_embedder(... long_batch1_tokens=0)` + `main` прокидка из `args`.
- CLI `--long-batch1-tokens` (default 0).

## Part C — `scripts/reindex_bsl_qwen3.py`
- max-file-bytes блок: `_oversized` → deferred-list `data/reports/reindex_deferred.txt`
  (mkdir + OSError-safe).
- CLI `--paths-file` (default None) + мерж в `args.paths` после `parse_args()` (до валидаций).

## Part B — `scripts/reindex_supervised.py` (новый)
- `_parse_idle` (s/m/h), `_last_idle` (хвост лога), `_kill_tree` (taskkill /T /F + fallback),
  `_build_cmd`, `run_attempt` (ok|wedge|error), `main` (лестница + guard пустой лестницы).

Дисциплина простоты: минимальный аддитивный diff, дефолты = прежнее поведение.
