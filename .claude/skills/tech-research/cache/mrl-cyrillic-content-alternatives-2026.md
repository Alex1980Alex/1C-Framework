---
topic: mrl-cyrillic-content-alternatives-2026
domain: tech-research
created: 2026-05-17
last_verified: 2026-05-17
version: Qwen3-Embedding-8B, Qdrant 1.17+, qdrant-client 1.13+
sources:
  - https://github.com/QwenLM/Qwen3-Embedding
  - https://github.com/RAIVNLab/MRL
  - https://qdrant.tech/documentation/manage-data/quantization/
  - https://qdrant.tech/articles/product-quantization/
  - https://huggingface.co/blog/embedding-quantization
  - https://blog.vespa.ai/embedding-tradeoffs-quantified/
  - https://towardsdatascience.com/649627-2/
  - https://qdrant.tech/documentation/tutorials-search-engineering/static-embeddings/
keywords: [mrl, matryoshka, cyrillic, bsl, product-quantization, scalar-quantization, fine-tuning, dimension-reduction, qdrant-quantization, code-embeddings, bge-m3, qwen3-embedding, voyage]
---

# Альтернативы MRL truncation для Cyrillic-heavy content (BSL REJECT problem)

Эмпирически (2026-05-17) bsl_code_v4 (std pooling) и bsl_code_v4_late (Late Chunking) показали REJECT на Qwen3-Embedding-8B MRL 4096→1024d (−12.8% и −17.1% NDCG@10 соответственно). Гипотеза: Cyrillic compound identifiers (`ПолучитьВнешниеМодули`) underrepresented в MRL training data; semantic uniqueness пакуется в dims ≥ 1024.

## 1. Решения для немедленной экономии storage (без compute cost)

### A. Scalar Quantization (int8) — Qdrant native, рекомендуется первым

| Свойство | Значение |
|---|---|
| Compression | 4× (float32 → int8) |
| Quality cost | ~0-2% degradation на retrieval |
| SIMD-friendly | Да (faster than PQ для in-RAM search) |
| Setup | `quantization_config={"scalar": {"type": "int8"}}` при `create_collection` |
| Storage для bsl_code_v4_late | 880 MB → 220 MB (−75%, без MRL) |

**Лучшее для BSL** — даёт MRL-эквивалент compression БЕЗ quality loss от dimension truncation.

```python
client.create_collection(
    collection_name="bsl_code_v4_late_sq",
    vectors_config=VectorParams(size=4096, distance=Distance.COSINE),
    quantization_config=ScalarQuantization(
        scalar=ScalarQuantizationConfig(
            type=ScalarType.INT8,
            quantile=0.99,  # клипает outliers
            always_ram=True,  # SIMD-fast если влезает в RAM
        )
    ),
)
```

### B. Binary Quantization — экстремальное сжатие

| Свойство | Значение |
|---|---|
| Compression | 32× (float32 → 1 bit per dim) |
| Quality cost | ~3-10% degradation |
| Speed | Очень быстрый Hamming distance |
| Best for | Качество не критично + max throughput |

### C. Product Quantization — middle ground

| Свойство | Значение |
|---|---|
| Compression | 8-64× (configurable) |
| Quality cost | ~3-15% degradation |
| SIMD-friendly | Нет (медленнее SQ для in-RAM) |
| Best for | Out-of-RAM, очень большие коллекции |

## 2. Решения для quality improvement (compute cost)

### D. MRL fine-tuning на domain-specific data

Train Qwen3-Embedding-8B с MRL loss на BSL/Cyrillic корпусе — push signal в нижние dims:

```python
from sentence_transformers.losses import MatryoshkaLoss, MultipleNegativesRankingLoss

base_loss = MultipleNegativesRankingLoss(model)
mrl_loss = MatryoshkaLoss(
    model=model,
    loss=base_loss,
    matryoshka_dims=[4096, 1024, 512, 256],  # train at multiple granularities
    matryoshka_weights=[1.0, 1.0, 1.0, 1.0],  # weighted equally
)

# Dataset: BSL queries + relevant chunks (positive pairs)
trainer = SentenceTransformerTrainer(
    model=model,
    train_dataset=bsl_pairs_dataset,
    loss=mrl_loss,
)
trainer.train()
```

Cost: 1 GPU × ~10-50 GPU-hours. Quality lift: empirically +5-15% NDCG at 1024d after MRL fine-tune on domain.

### E. Alternative models — try BGE-M3 / Voyage

| Model | MRL native | Multi-vec | Russian | Code | License |
|---|---|---|---|---|---|
| Qwen3-Embedding-8B | Yes | No | OK | OK | Apache 2.0 |
| **BGE-M3** | Yes | Yes (sparse+dense+ColBERT) | Good | Good | MIT |
| Voyage 3.5 | Yes | No | Excellent | Excellent | Paid API |
| jina-embeddings-v3 | Yes | No | Good | OK | Apache 2.0 |

BGE-M3 specifically: trained on 194 languages including Russian, native MRL, multi-vector. Может лучше подходить для Cyrillic identifier-heavy content. Worth benching.

## 3. Hybrid подход (combine MRL + Quantization)

PQ и MRL ортогональны — комбинируются:

```
4096d float32  →  1024d float32  →  1024d int8
   (16KB)         (4KB, -75%)        (1KB, -94%)
   baseline        MIGRATE collec     +SQ
```

Для MIGRATE-friendly корпусов (framework_code, pdf_documents) — добавить SQ поверх MRL для дополнительных −75%. Для REJECT корпусов (BSL) — только SQ (без MRL), сохраняет full quality.

## 4. Static embeddings — экстремальный baseline

Qdrant支持 static embeddings (Model2vec-style): sub-millisecond search, без GPU. Quality ~50-70% relative to Qwen3 — НЕ для production retrieval, но для quick prefilter.

## 5. Combined PQ + MRL — economic frontier

Source: Towards Data Science анализ показывает: PQ over MRL может дать −95% storage (32× MRL × 8× SQ) при ~10% quality loss. Pareto-optimal point — индивидуален per use-case.

## Приоритеты для BSL REJECT

1. **Quick win:** Scalar Quantization int8 на bsl_code_v4_late → 220 MB (−75%), zero quality loss. **Реализуется за 5 мин через recreate с quantization_config.**
2. **Mid-term:** Bench BGE-M3 на 20 grounded BSL queries — может показать MIGRATE
3. **Long-term:** MRL fine-tune Qwen3 на BSL pairs — compute-heavy, оправдан если коллекция растёт > 100K pts

## Антипаттерны

| Плохо | Почему | Как правильно |
|---|---|---|
| Применять MRL ко всем коллекциям одинаково | Verdict зависит от content type (REJECT для Cyrillic identifiers) | Per-corpus bench mandatory |
| PQ на маленьких коллекциях (<10K pts) | Overhead PQ index > storage saving | Scalar Quantization для small, PQ для large |
| Binary Quantization без rescoring | 3-10% quality loss необратима | Включить `rescore=True` для recovery |
| MRL fine-tune на small dataset (<10K pairs) | Overfits, no gain | Минимум 100K pairs для надёжного MRL training |

## Источники

- **[Docs]** [Qdrant Quantization](https://qdrant.tech/documentation/manage-data/quantization/) — SQ/BQ/PQ config + tradeoffs
- **[Docs]** [Qdrant Product Quantization](https://qdrant.tech/articles/product-quantization/) — deep dive on PQ
- **[Repo]** [QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding) — official Qwen3 embedding code
- **[Repo]** [RAIVNLab/MRL](https://github.com/RAIVNLab/MRL) — original MRL paper code
- **[Blog]** [HF Embedding Quantization](https://huggingface.co/blog/embedding-quantization) — SQ/BQ practical guide
- **[Blog]** [Vespa Embedding Tradeoffs](https://blog.vespa.ai/embedding-tradeoffs-quantified/) — empirical quality/cost
- **[Article]** [Towards Data Science: PQ vs MRL 80% Cost Reduction](https://towardsdatascience.com/649627-2/) — combined approaches
