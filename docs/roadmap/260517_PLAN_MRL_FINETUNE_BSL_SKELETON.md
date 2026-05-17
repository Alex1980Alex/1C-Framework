# §4.1.13 — MRL Fine-tune Qwen3 на BSL (Plan, Research-Only Skeleton)

> **Статус:** SKELETON ONLY (2026-05-17). Scripts написаны как skeleton без actual training. Real implementation требует существенного compute investment.

## Why

Bench 4.1.7/4.1.9/4.1.11 показал что Qwen3-Embedding-8B MRL truncation 4096→1024d даёт REJECT verdict на BSL/Cyrillic identifier-heavy content:

| Collection | Δ NDCG | Verdict |
|---|---|---|
| bsl_code_v4 | −12.8% | REJECT |
| bsl_code_v4_late | −17.1% | REJECT |
| graph_embeddings | −20.4% | REJECT |

Hypothesis: модель MRL-trained на English/web data; Cyrillic compound identifiers (`ПолучитьВнешниеМодули`) underrepresented → semantic uniqueness пакуется в верхние dims, отбрасываемые при truncate.

Fine-tune с MRL loss на domain-specific BSL corpus может push signal в нижние dims → enable MIGRATE verdict при truncate.

## Expected outcome

Per published research (RAIVNLab/MRL paper + sentence-transformers blog):
- **Lift +5-15% NDCG at 1024d** для domain-fine-tuned MRL
- **Lift +10-25% NDCG at 512d** (more aggressive truncate becomes viable)

Conservative estimate для BSL: bring 1024d delta from −12.8% to +/−2% → MIGRATE.

## Required artefacts

### 1. Training corpus ([scripts/collect_bsl_finetune_pairs.py](../../../scripts/collect_bsl_finetune_pairs.py), SKELETON)

- **Volume target:** ≥10K query-positive pairs (статистическая stability MRL loss)
- **Source:** bsl_code_v4 scroll → for each chunk with `doc_comment > 50` chars, LLM generates 2-3 synthetic queries
- **Quality controls:**
  - Dedupe (Levenshtein > 0.85)
  - Filter boilerplate chunks (`КонецПроцедуры`, `КонецФункции` patterns)
  - 90/10 train/eval split stratified by `chunk_type`
  - Manual review of 100 random samples
- **LLM:** Z.AI via `llm_rotation` service (cheap, Russian-capable)
- **Estimated cost:** 24455 chunks × 2 queries × ~$0.0001 per query ≈ $5

### 2. Fine-tune script ([scripts/finetune_qwen3_bsl_mrl.py](../../../scripts/finetune_qwen3_bsl_mrl.py), SKELETON)

**Library stack:**
- `sentence-transformers>=3.0` — MatryoshkaLoss, SentenceTransformerTrainer
- `peft` — LoRA для memory efficiency
- `accelerate` — mixed precision (fp16 на RTX 3090)

**MRL config:**
```python
matryoshka_dims = [4096, 2048, 1024, 512, 256]
matryoshka_weights = [1.0] * 5  # equal weighting; bias lower dims if priority
```

**LoRA config (recommended):**
- `r=16, alpha=32, target_modules=["q_proj", "v_proj", "o_proj"]`
- VRAM: ~14 GB на RTX 3090 (vs 48+ GB для full fine-tune)
- Train time: 5-10 GPU-hours (vs 10-50 для full)

**Hyperparams:**
- `learning_rate=2e-5` (10× lower than from-scratch)
- `warmup_ratio=0.1`
- `epochs=3`
- `batch_size=16, gradient_accumulation_steps=4` (effective 64)
- `fp16=True`

### 3. Eval pipeline (reuse existing)

- `matryoshka_migrate.py --source bsl_code_v4` after re-embedding с fine-tuned model
- Compare NDCG@10 на 15 grounded BSL queries vs baseline (0.4436 / 0.3870 / 0.3072)
- Verdict: MIGRATE if delta_1024d ≥ −5%

## Required investment

| Item | Estimate |
|---|---|
| Corpus collection compute (LLM calls) | $5 + ~2 hours wall-clock |
| Manual corpus review | 1-2 hours |
| Fine-tune dev/debug | 4-8 hours |
| LoRA fine-tune training | 5-10 GPU-hours (RTX 3090) |
| Re-bench + verdict | 30 min |
| **Total** | ~10-15 hours engineering + 5-10 GPU-hours |

## Risk

- **Synthetic corpus quality** — LLM-generated queries могут быть unrealistic ("Что делает X?" pattern bias). Real user queries более diverse.
- **Overfitting** — 10K pairs vs 24K chunks low ratio; LoRA partially mitigates
- **No guaranteed verdict** — fine-tune может дать +0% lift на BSL; only empirical bench reveals

## Alternative paths considered

1. **§4.1.12 SQ int8 (DONE)** — RAM-only optimization, zero quality loss, 5 min implementation
2. **§4.1.14 BGE-M3 alternative model** — test if different MRL training distribution works on BSL без fine-tune
3. **§4.1.15 MRL + SQ combined (DONE)** — для MIGRATE-3 collections, дополнительный RAM ×4

§4.1.12 + §4.1.15 уже закрыли значительную часть RAM/latency проблем. §4.1.13 fine-tune оправдан только если §4.1.14 (BGE-M3) тоже REJECT и нужен absolute disk savings (требует destructive recreate after fine-tune).

## Decision

**Defer §4.1.13 actual training.** Skeleton scripts документируют workflow и hyperparams; рестарт работы тривиален. Возврат к §4.1.13 оправдан, если:
- §4.1.14 BGE-M3 показывает REJECT (significantly limits alternatives)
- BSL collection растёт > 100K pts (compute cost оправдан размером)
- Появляется reliable user query log для real (non-synthetic) corpus

## Файлы

- [`scripts/collect_bsl_finetune_pairs.py`](../../../scripts/collect_bsl_finetune_pairs.py) — corpus collection SKELETON
- [`scripts/finetune_qwen3_bsl_mrl.py`](../../../scripts/finetune_qwen3_bsl_mrl.py) — training SKELETON

## Источники

- [sentence-transformers MatryoshkaLoss tutorial](https://sbert.net/examples/training/matryoshka/)
- [HuggingFace MRL blog](https://huggingface.co/blog/matryoshka)
- [RAIVNLab/MRL paper code](https://github.com/RAIVNLab/MRL)
- [QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding)
