# Этап 1 — Планирование архитектуры

## Проблема
ERP full-реиндекс через `scripts/reindex_bsl_qwen3.py` (embedder=qwen3-st,
`--pooling-mode standard`, max_seq_length=8192, Qwen3-Embedding-8B, RTX 3090 24GB)
упал в CUDA OOM на god-object-чанке. Прогон `...ab7ba7` завис с `gpu_vram_mb ~24204`
из 24576 (потолок), `idle_s` рос → процесс умер.

## Корневая причина
Без FlashAttention-2 self-attention материализует O(n²) матрицу скоров
`[batch, heads, seq, seq]` в HBM. В бакете XXL_8K (batch=2, seq=8192) эти скоры —
многогигабайтная статья на слой → пик VRAM упирается в 24GB и процесс умирает.

Структурная дыра: существующий гейт, требующий FA2
([reindex_bsl_qwen3.py:1698](../../scripts/reindex_bsl_qwen3.py#L1698)), срабатывал
**только** для `--pooling-mode late-chunking` на кириллице. Для `standard` pooling
(как у ERP) гейта на FA2 не было → god-object без FA2 уходил в OOM.

## Проверка применимости FA2 на этой машине
- flash-attn 2.8.3 / torch 2.10.0+cu128 / RTX 3090 (compute capability 8.6, Ampere).
- `import flash_attn` ≠ работающие ядра (ABI-дрифт 2.8.3 × torch 2.10 может segfault exit 139).
- Авторитетная проба проекта `_fa2_preflight_ok()` (изолированный subprocess,
  `flash_attn_func`) → **exit 0 (PASS)**. FA2 безопасен к включению.

## Решение (направление)
Включить FA2 для qwen3-st full-реиндекса. FA2 делает attention-память линейной
(tiling + online softmax, без материализации n×n) и численно **точен** → качество
эмбеддингов не меняется. Не снижать seq/batch (это лечение симптома).

Связано: [[feedback-bsl-reindex-segfault-torch210]], [[feedback-bsl-indexer-backend-choice]].
