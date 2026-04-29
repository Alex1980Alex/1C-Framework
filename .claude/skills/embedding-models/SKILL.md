---
name: embedding-models
description: "Embedding Models — выбор, настройка и отладка моделей эмбеддингов. ИСПОЛЬЗУЙ когда выбираешь модель embeddings (E5, BGE, Jina, Giga), настраиваешь ONNX backend, исправляешь dimension mismatch, добавляешь prefix query:/passage:. Триггеры: 'embedding', 'E5', 'BGE', 'ONNX', 'dimension mismatch', 'prefix', 'query: passage:', 'модель эмбеддингов', 'Jina', 'Giga-Embeddings'. НЕ для поиска (→ search-pipeline-debug), НЕ для Qdrant (→ qdrant-operations)."
---

# Embedding Models

## Когда использовать
- "какую модель embeddings", "E5 vs BGE", "ONNX backend"
- "dimension mismatch", "prefix", "query: / passage:"
- Смена/сравнение моделей, оптимизация скорости

## Модели

| Модель | Dims | Качество | Скорость | Когда |
|--------|------|----------|----------|-------|
| `Qwen/Qwen3-Embedding-8B` | 4096 (MRL→1024) | SOTA code+text (MTEB-Code 80.68, Multilingual 70.58) | GPU req. | **BSL primary** (Phase 8.12), `bsl_code_v4`, native 32K context |
| `intfloat/multilingual-e5-large` | 1024 | SOTA multilingual | Fast | E5 baseline (Phase 7), legacy `bsl_code_v3` |
| `ai-sage/Giga-Embeddings-instruct` | 1024 | SOTA Russian (69.1 ruMTEB) | Fast | Russian-heavy |
| `BAAI/bge-m3` | 1024 | Good (100+ languages) | Fast | Fallback |
| `jina-embeddings-v3` | 1024 | SOTA (Matryoshka) | API | Multilingual, task prompting (Phase 47) |
| `vidore/colpali-v1.3` | multi-vector | SOTA visual | Slow (GPU) | Visual page retrieval (Phase 55) |
| `all-MiniLM-L6-v2` | 384 | OK | Fastest | **Deprecated!** |

## Prefix Requirements (КРИТИЧНО)

**E5 models** (auto-detected по "e5" в имени):
- Query: `"query: " + text`
- Passage: `"passage: " + text`

**GigaEmbeddings** (instruction family):
- Query: `"Instruct: Given a search query...\nQuery: " + text`
- Passage: без prefix

**Qwen3-Embedding-8B** (Phase 8.12) — instruction family + last-token pooling:
- Query: `"Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: " + text` (через ST `prompt_name="query"` или ручной prepend)
- Passage: без prefix
- FA2 + `tokenizer_kwargs={"padding_side":"left"}` обязательно вместе (C6) — иначе last-token pooling читает padding на коротких чанках
- MAX_INPUT_LENGTH=4096 token cap (8.12 C1+C5)
- Late Chunking pooling-mode (8.12.9): full-document forward + per-chunk mean-pool, требует `--embedder qwen3-st` (TEI не поддерживает — pooled vectors only)
- Sliding-window split в bsl_chunker (8.12.5): window=1024 / overlap=256 для XXL символов

**Jina v3** (Phase 47) — API-based, task prompting, Matryoshka dimensions:
- Provider: `jina` (отдельный, не local)
- API: `https://api.jina.ai/v1/embeddings`
- Поддерживает Late Chunking
- Task: `retrieval.query`, `retrieval.passage`, `text-matching`

**ColPali** (Phase 55) — Visual multi-vector embeddings:
- Не для текста — для **изображений страниц PDF**
- Multi-token embeddings (n_tokens × dim)
- Модели: `vidore/colpali-v1.3`, `vidore/colqwen2-v1.0`
- Требует GPU

## Backends (Phase 43)

| Backend | Скорость (CPU) | Установка |
|---------|----------------|-----------|
| `torch` | 5-10 texts/s | По умолчанию |
| `onnx` | 50-100 texts/s (~7x) | `pip install onnxruntime` |
| `openvino` | 50-100 texts/s (~7x) | `pip install openvino` |
| **TEI HTTP** (Phase 8.12.6) | ~3-5× vs Python ST на 8B моделях | Docker `--profile tei`, image `ghcr.io/huggingface/text-embeddings-inference:1.7.2` (Ampere). Continuous batching + FA2 встроенно. **Caveat**: pooled vectors only — Late Chunking невозможен через TEI. Также enforce `MAX_CLIENT_BATCH_SIZE` (default 32) на стороне сервера → клиенты должны слайсить буфер (см. `Qwen3TEIEmbedder.client_batch_size` в `scripts/reindex_bsl_qwen3.py`) |

## Конфиг

```env
EMBEDDING__PROVIDER=local          # local|giga|tei (Phase 8.12.6)
EMBEDDING__MODEL=intfloat/multilingual-e5-large    # или Qwen/Qwen3-Embedding-8B
EMBEDDING__DIMENSIONS=1024         # 4096 для Qwen3 native; 1024 для MRL-truncated
EMBEDDING__BATCH_SIZE=64
EMBEDDING__BACKEND=torch           # torch|onnx|openvino
EMBEDDING__DEVICE=auto             # auto|cpu|cuda|mps
EMBEDDING__DTYPE=float16           # для Qwen3 на GPU (Phase 8.12)
EMBEDDING__CACHE_ENABLED=true

# TEI (Phase 8.12.6, opt-in для bsl_code reindex)
QWEN3_MODEL_DIR=D:/hf-manual/Qwen3-Embedding-8B   # bind-mount для compose
```

## Диагностика

| Симптом | Причина | Решение |
|---------|---------|---------|
| Dimension mismatch (384 vs 1024) | `.env` переопределяет config | Проверить `EMBEDDING__MODEL` — должен быть E5 large (1024d) |
| E5 prefix не применяется | Model name без "e5" | Проверить что имя модели содержит "e5" (case-insensitive) |
| ONNX runtime error | Не установлен | `pip install onnxruntime` |
| CUDA out of memory | Batch size слишком большой | Уменьшить `batch_size` (32), или `device=cpu` |
| Cache miss на каждый запрос | Cache выключен | `EMBEDDING__CACHE_ENABLED=true`, проверить `cache_dir` |

## Файлы
- Engine interface: `src/pdf_framework/embeddings/engine.py`
- Local provider: `src/pdf_framework/embeddings/providers/local.py`
- Giga provider: `src/pdf_framework/embeddings/providers/giga.py`
- BGE-M3 provider: `src/pdf_framework/embeddings/providers/bgem3.py`
- Jina v3 provider: `src/pdf_framework/embeddings/providers/jina.py`
- ColPali provider: `src/pdf_framework/embeddings/providers/colpali.py`
- Cache: `src/pdf_framework/embeddings/cache/`
- Config: `src/pdf_framework/config/embedding.py`
