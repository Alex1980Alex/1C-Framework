# Embedding Models

## Когда использовать
- "какую модель embeddings", "E5 vs BGE", "ONNX backend"
- "dimension mismatch", "prefix", "query: / passage:"
- Смена/сравнение моделей, оптимизация скорости

## Модели

| Модель | Dims | Качество | Скорость | Когда |
|--------|------|----------|----------|-------|
| `intfloat/multilingual-e5-large` | 1024 | SOTA multilingual | Fast | **Default** |
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

## Конфиг

```env
EMBEDDING__PROVIDER=local          # local|giga
EMBEDDING__MODEL=intfloat/multilingual-e5-large
EMBEDDING__DIMENSIONS=1024
EMBEDDING__BATCH_SIZE=64
EMBEDDING__BACKEND=torch           # torch|onnx|openvino
EMBEDDING__DEVICE=auto             # auto|cpu|cuda|mps
EMBEDDING__CACHE_ENABLED=true
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
