# §4.1.14 — BGE-M3 Alternative Bench (DEFERRED, 2026-05-17)

> **Статус:** ATTEMPTED, DEFERRED — network/CDN issues blocked download. Scripts готовы для повторного запуска когда сеть стабильна.

## Why

Bench §4.1.7/4.1.9/4.1.11 показал что Qwen3-Embedding-8B MRL truncation на BSL (Cyrillic identifier-heavy content) даёт REJECT verdict (−12.8% до −20.4% NDCG). Гипотеза: alternative embedding model с другим training distribution может быть MRL-friendly для Cyrillic кода.

**Кандидат:** BGE-M3 (BAAI) — multilingual (194 languages incl. Russian), native MRL (down to 256d), multi-vector (sparse+dense+ColBERT), 1024d dense output (vs Qwen3 4096d).

## Attempt log (2026-05-17)

1. **Загрузка через FlagEmbedding:** stuck at 47 MB после 14 мин (network rate limit или HF CDN issue)
2. **Резюм через huggingface_hub.snapshot_download:** progressed до 2.4 GB но 2 файла остались `.incomplete`
3. **Manual hf CLI download (`hf download BAAI/bge-m3 pytorch_model.bin`):** progressed до 401 MB, затем stall

Network connectivity verified (`curl https://huggingface.co/` returns 200, 4s), но download throughput неустойчивый.

## Что готово к запуску (когда сеть позволит)

[`scripts/bench_bge_m3_bsl.py`](../../../scripts/bench_bge_m3_bsl.py) — полностью готовый бенч скрипт:

```bash
python scripts/bench_bge_m3_bsl.py --source bsl_code_v4 --sample-fill 2000
```

Pipeline:
1. Load BGE-M3 (1.2 GB FP16 GPU)
2. Sample N chunks from bsl_code_v4 (incl. all mandatory chunk_ids from grounded queries)
3. Re-embed → bsl_code_v4_bgem3 collection (1024d cosine)
4. For each of 15 grounded BSL queries: embed via BGE-M3 → NDCG@10 vs grounded
5. Compare mean NDCG to Qwen3 baseline (0.4436 from §4.1.9)

Verdict:
- mean_NDCG > 0.4436 → BGE-M3 BETTER for BSL → option to swap embedder
- mean_NDCG ≤ 0.4436 → BGE-M3 не помогает → confirm §4.1.12 SQ approach optimal

## Recovery steps когда сеть стабильна

```bash
# 1. Clear stuck downloads
rm "C:/Users/<USER>/.cache/huggingface/hub/models--BAAI--bge-m3/blobs/"*.incomplete

# 2. Retry download (use HF_ENDPOINT mirror если доступен)
export HF_HUB_DOWNLOAD_TIMEOUT=600
.venv/Scripts/hf.exe download BAAI/bge-m3 --include "pytorch_model.bin"

# 3. Verify download
ls "C:/Users/<USER>/.cache/huggingface/hub/models--BAAI--bge-m3/snapshots/*/pytorch_model.bin"
# Должен быть symlink на blob ~2.27 GB

# 4. Run bench
cd C:/1С-Framework
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe scripts/bench_bge_m3_bsl.py \
  --source bsl_code_v4 --sample-fill 2000
```

ETA когда сеть OK: 25-35 мин (~5 min download remaining + ~15 min embed + bench).

## Альтернативные модели для рассмотрения

Если BGE-M3 тоже REJECT при retry:
- **jina-embeddings-v3** (Jina AI) — 1024d, multilingual, MRL native, task prompting
- **Voyage 3.5** (Voyage AI) — paid API, отличный для Russian/code
- **ai-sage/Giga-Embeddings-instruct** — Russian-native (69.1 ruMTEB), instruction-tuned

Все требуют похожего bench цикла (sample → re-embed → 15 queries NDCG).

## Decision

Current state (§4.1.6/8/10 + §4.1.12 + §4.1.15) уже даёт:
- MIGRATE-3 коллекции: 16× RAM compression, p95 < 50 ms
- REJECT-3 коллекции: 4× RAM compression через SQ, p95 < 100 ms, zero quality loss

§4.1.14 — research-only; результат не блокирует production. Retry опционально.
