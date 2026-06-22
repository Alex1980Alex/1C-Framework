# 03 — Реализация

Файл: [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py)

- `_existing_module_paths()` — scroll-helper (qdrant-operations skill).
- `--skip-indexed` argparse + 2 гейта несовместимости.
- file_scan: фильтр по normpath-diff + `_evt("skip_indexed", ...)` + NOTE про module-level гранулярность (R2).
- цикл: периодический `torch.cuda.empty_cache()` (R1+R2 ревью применены).

Auto-save коммит: `fbfa4e7e7` + последующие правки R1/R2.

ruff: 2 предсуществующих замечания (side-effect import torch/ST, unused `step`) — вне области задачи.
