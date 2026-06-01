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
| **`Qwen/Qwen3-Embedding-8B`** | **4096** | SOTA code+text (MTEB-Code 80.68, Multilingual 70.58) | TEI Docker | **PRODUCTION DEFAULT** (Phase 8 switchover 2026-04-30). 7 коллекций × 80 793 pts: `bsl_code_v4`, `bsl_code_v4_late`, `framework_code_v1`, `pdf_documents`, `wiki_pages_v1`, `graph_embeddings`, `learned_patterns`. Native 32K context. Backend: `pdf-rag-tei` Docker (`docker compose --profile tei up`) |
| `intfloat/multilingual-e5-large` | 1024 | SOTA multilingual | Fast | **Legacy** (до Phase 8). Может остаться fallback для специфичных кейсов |
| `nomic-embed-text` (Ollama 768d) | 768 | OK | Fast (CPU) | **Misalignment**: используется memory-hooks (`memory-first-hook.py`, `shared/semantic_search.py`), но retrieval-коллекции на Qwen3 4096d. Phase 9 candidate — alignment всей memory-системы на TEI 4096d |
| `ai-sage/Giga-Embeddings-instruct` | 1024 | SOTA Russian (69.1 ruMTEB) | Fast | Path D alternative (не выбрано) |
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

## Провайдер `tei` (Phase 8 default — factory branch добавлен 2026-06-01)

`EMBEDDING__PROVIDER=tei` — **production default**, но до 2026-06-01 фабрика `get_embedding_engine()` падала с `ValueError: Unsupported embedding provider: tei` (не было ветки) → ломала всех потребителей, включая vector-memory MCP (`_get_embedding` → «embedding provider unavailable»). Фикс: [`providers/tei.py`](../../../src/pdf_framework/embeddings/providers/tei.py) `TEIEmbeddingEngine` + ветка в фабрике. Поведение: читает `TEI_URL` env (override) → `settings.tei_base_url` (default `http://localhost:8080`) + `/embed`; sub-batch ≤ `settings.tei_client_batch` (32, TEI 413-cap); **всегда** добавляет Qwen3 `QUERY_INSTRUCTION` (query-side, как `shared/semantic_search.embed_query_tei`) → для passage-индексации нужен отдельный no-prefix путь; `normalize+truncate`; dims=`settings.dimensions` (4096). После правок MCP-сервера нужен `/mcp reconnect` ([[feedback-mcp-stale-code-reconnect]]).

## Файлы
- Engine interface: `src/pdf_framework/embeddings/engine.py`
- TEI provider: `src/pdf_framework/embeddings/providers/tei.py` (Qwen3 4096d, PRODUCTION DEFAULT)
- Local provider: `src/pdf_framework/embeddings/providers/local.py`
- Giga provider: `src/pdf_framework/embeddings/providers/giga.py`
- BGE-M3 provider: `src/pdf_framework/embeddings/providers/bgem3.py`
- Jina v3 provider: `src/pdf_framework/embeddings/providers/jina.py`
- ColPali provider: `src/pdf_framework/embeddings/providers/colpali.py`
- Cache: `src/pdf_framework/embeddings/cache/`
- Config: `src/pdf_framework/config/embedding.py`
