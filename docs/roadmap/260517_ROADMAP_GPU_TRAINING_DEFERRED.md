# ROADMAP: GPU-Training Tasks (DEFERRED)

> **Дата:** 2026-05-17
> **Статус:** ALL DEFERRED — все training-tasks ожидают bandwidth/GPU/cloud budget decision
> **Master plan:** consolidates §4.1.13 + future LoRA fine-tunes + custom embedder training
> **Last bench:** Qwen3-Embedding-8B MRL REJECT verdict на BSL (§4.1.9: -12.8%, §4.1.11: -20.4%) — root motivator всех GPU-tasks тут

## Содержание

- [Why these tasks exist](#why-these-tasks-exist)
- [Phase 1 — §4.1.13: MRL fine-tune Qwen3 на BSL](#phase-1--4113-mrl-fine-tune-qwen3-на-bsl)
- [Phase 2 — Hyperparameter/dataset experiments](#phase-2--hyperparameterdataset-experiments)
- [Phase 3 — Production deployment of fine-tuned model](#phase-3--production-deployment-of-fine-tuned-model)
- [Hardware / cloud options](#hardware--cloud-options)
- [Decision tree: когда запустить](#decision-tree-когда-запустить)
- [Acceptance criteria](#acceptance-criteria)
- [Связанные документы](#связанные-документы)

---

## Why these tasks exist

Bench 2026-05-17 (§4.1.6-15) показал что **Qwen3-Embedding-8B MRL truncation REJECT на BSL/Cyrillic identifier-heavy content**:

| Collection | Pooling | Δ NDCG @ 1024d | Verdict |
|---|---|---|---|
| bsl_code_v4 | std | −12.8% | REJECT |
| bsl_code_v4_late | Late Chunking | −17.1% | REJECT |
| graph_embeddings | std (BSL symbols) | −20.4% | REJECT |

**Текущее workaround:** Scalar Quantization int8 (§4.1.12) — 4× RAM compression, zero quality loss, sub-100ms p95. Production-acceptable.

**Что fine-tune может улучшить:**
- MRL truncation 4096d→1024d начнёт работать → дополнительные 4× disk savings
- Lift +5-15% NDCG@10 на BSL queries (literature estimate)
- Domain adaptation: модель лучше понимает Cyrillic compound identifiers (`ПолучитьВнешниеМодули`)

**Hypothesis:** Qwen3-Embedding-8B MRL-trained primarily на English/web data. Cyrillic technical identifiers underrepresented → semantic uniqueness пакуется в верхние dims (≥ 1024), отбрасываемые при truncate. Fine-tune с MRL loss на domain corpus может push signal в нижние dims.

---

## Phase 1 — §4.1.13: MRL fine-tune Qwen3 на BSL

**Цель:** Получить MIGRATE verdict для `bsl_code_v4_late` truncation 4096d→1024d через domain-specific MRL fine-tuning.

### 1.1 Подготовка training corpus (skeleton ready)

**Скрипт:** [`scripts/collect_bsl_finetune_pairs.py`](../../scripts/collect_bsl_finetune_pairs.py) — SKELETON, нужен replace dummy queries с LLM calls.

**Workflow:**
1. Scroll `bsl_code_v4` (24 455 chunks) — оригинальные std-pooling chunks
2. Для каждого chunk с `doc_comment > 50` chars или meaningful `name`:
   - LLM (Z.AI/claude-cli) generates 2-3 synthetic Russian queries
   - Queries diverse: factual ("Что делает X"), procedural ("Как использовать X"), error ("Ошибка при X")
3. Output: JSONL `{query, positive_chunk_id, source_text}`
4. Target volume: **≥10 000 pairs** (статистическая stability для MRL loss)

**Quality controls (must implement):**
- Levenshtein dedup (threshold > 0.85) — избежать quasi-duplicate queries
- Filter boilerplate chunks (`КонецПроцедуры`, `КонецФункции`)
- 90/10 train/eval split, stratified by `chunk_type`
- Manual review 100 random samples

**Estimated effort:** ~$5 LLM cost + 2-3h wall-clock generation + 1-2h manual review.

### 1.2 Fine-tune execution (skeleton ready)

**Скрипт:** [`scripts/finetune_qwen3_bsl_mrl.py`](../../scripts/finetune_qwen3_bsl_mrl.py) — SKELETON, `train_with_mrl_loss()` raises `NotImplementedError`.

**Stack:**
- `sentence-transformers>=3.0` — `MatryoshkaLoss`, `SentenceTransformerTrainer`
- `peft` — LoRA для memory efficiency
- `accelerate` — mixed precision (fp16 на RTX 3090)

**Recommended config:**

```python
# MRL config
matryoshka_dims = [4096, 2048, 1024, 512, 256]
matryoshka_weights = [1.0] * 5  # equal weighting

# LoRA config (PEFT)
peft_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj", "o_proj"],
    bias="none",
    task_type="FEATURE_EXTRACTION",
)

# Training hyperparams
learning_rate = 2e-5      # 10× lower than from-scratch
warmup_ratio = 0.1
epochs = 3
batch_size = 16
gradient_accumulation_steps = 4  # effective 64
fp16 = True
```

**Resource budget:**
- LoRA: ~14 GB VRAM на RTX 3090 (vs 48+ GB для full fine-tune)
- Train wall-clock: 5-10 GPU-hours
- Disk: adapter weights ~100-500 MB

### 1.3 Eval + verdict (reuse existing pipeline)

```bash
# Re-embed bsl_code_v4 with fine-tuned model → new test collection
python scripts/finetune_qwen3_bsl_mrl.py --bench-after

# Use existing bench script
python scripts/matryoshka_migrate.py --source bsl_code_v4_finetuned
```

**Target metrics:**
- NDCG@10 baseline (Qwen3 stock 4096d): **0.4436** (recorded §4.1.9)
- NDCG@10 fine-tuned 1024d: **target ≥ 0.4214** (within -5% MIGRATE threshold)
- Lift hypothesis: +5-15% absolute

### 1.4 Acceptance gates

- [ ] Training corpus: ≥10K pairs, manual review passed
- [ ] Fine-tune completes без OOM/divergence
- [ ] eval NDCG@10 ≥ 0.4214 (MIGRATE threshold)
- [ ] No regression на других golden_v1 subsets (PDF, wiki, framework)

---

## Phase 2 — Hyperparameter/dataset experiments

**Conditional:** запускается только если Phase 1 не достигает acceptance gate (NDCG lift < +5%).

### 2.1 Dataset variations
- Real user queries (если есть лог retrieval queries) vs synthetic LLM-generated
- Hard negatives mining (BM25-retrieved non-relevant chunks)
- Multi-positive pairs (chunk variants для одного query)

### 2.2 Hyperparameter sweep
- Learning rate: [1e-5, 2e-5, 5e-5]
- LoRA rank: [8, 16, 32, 64]
- Matryoshka weights: equal vs [0.5, 0.7, 1.0, 1.0, 1.0] (bias lower dims)
- Epochs: [3, 5, 7]

### 2.3 Alternative architectures
- Full fine-tune (no LoRA) если 48+ GB GPU доступен
- QLoRA (4-bit base + LoRA) — больший batch size

---

## Phase 3 — Production deployment of fine-tuned model

**Conditional:** запускается после Phase 1/2 acceptance gate met.

### 3.1 Inference setup
- Convert PEFT adapter → merged model (single .safetensors)
- Deploy as TEI variant: `BAAI/bge-m3` slot replaced custom `qwen3-bsl-mrl`
- OR: keep parallel — stock Qwen3 для общего retrieval, fine-tuned только для BSL
- Update [`scripts/reindex_bsl_qwen3.py`](../../scripts/reindex_bsl_qwen3.py) → use fine-tuned model для bsl_code_v4_late
- Update [`src/framework_search/embedder.py`](../../src/framework_search/embedder.py) если общий стек

### 3.2 Re-index BSL collections
- `bsl_code_v4` + `bsl_code_v4_late` re-embed через fine-tuned model
- Snapshot existing 4096d collections as `*_qwen3_stock_backup`
- Truncate fine-tuned 4096d → 1024d MRL, swap via alias (same pattern as §4.1.6/8/10)

### 3.3 Production validation
- Re-run §4.1.9 bench (15 BSL grounded queries) → confirm MIGRATE persists
- Production traffic shadowing (если есть feedback loop)
- Rollback plan: alias revert to stock backup

---

## Hardware / cloud options

| Option | Cost | Pros | Cons |
|---|---|---|---|
| **Local RTX 3090 (24 GB)** | $0 + 5-10h wall-clock | Free, full control, instant iteration | Blocks GPU for other work, fp16 only (не bf16) |
| **Cloud GPU rental (vast.ai/RunPod)** | $1-5/h × 5-10h = $5-50 | Faster cards (A100/H100), bf16, parallel runs | Setup overhead, data egress concerns |
| **Google Colab Pro** | $10/month | Browser-based, no local setup | 12h session cap, queue waits |
| **HuggingFace AutoTrain** | $0.50-2/h | Zero infra, push-button | Less control over training loop |
| **Lambda Labs** | $1-2/h | Reliable H100 access | Subscription model |

**Recommendation для bootstrap:** vast.ai с RTX 4090 / A6000 за $1-2/h. 5-10h × $1.50 = ~$10 total. Setup 30 min (SSH + git clone + venv setup).

---

## Decision tree: когда запустить

```
START
  │
  ├── Question 1: §4.1.14 BGE-M3 bench выполнен и REJECT?
  │     ├── NO → выполнить §4.1.14 FIRST (no GPU needed, only network)
  │     │       Если BGE-M3 MIGRATE → use that, SKIP this roadmap
  │     │       Если BGE-M3 REJECT → продолжить decision tree
  │     └── YES, REJECT → продолжить
  │
  ├── Question 2: BSL collection растёт > 100k pts?
  │     ├── NO (текущие 54k) → fine-tune ROI marginal — DEFER
  │     └── YES → продолжить
  │
  ├── Question 3: Имеется ≥5 GPU-h compute budget (local OR ~$20 cloud)?
  │     ├── NO → DEFER до budget allocated
  │     └── YES → продолжить
  │
  ├── Question 4: Есть >1K REAL user queries (не synthetic)?
  │     ├── NO → проверить если synthetic corpus enough (Phase 2.1 test)
  │     └── YES → продолжить с real queries
  │
  └── EXECUTE: Phase 1
```

**Текущий статус 2026-05-17:** Q1=NO (BGE-M3 download stalled, retry pending). Q3+Q4 пока не оценены. Roadmap waits.

---

## Acceptance criteria (overall)

Roadmap считается выполненным когда:

- [ ] §4.1.14 BGE-M3 bench выполнен и verdict документирован
- [ ] (Conditional on BGE-M3 REJECT) Phase 1 §4.1.13 fine-tune executed
- [ ] (Conditional on Phase 1 success) Phase 3 production deployment
- [ ] BSL retrieval p95 < 100ms (already achieved через SQ int8)
- [ ] BSL NDCG@10 ≥ 0.50 (current 0.44 stock; fine-tune target +12%)

**Если §4.1.14 → MIGRATE:** перерабатывать всю стратегию, fine-tune не нужен.

**Если §4.1.14 → REJECT + Phase 1 → REJECT:** документировать как hard ceiling Qwen3 на Cyrillic, оставаться на SQ int8.

---

## Связанные документы

- [`260517_PLAN_MRL_FINETUNE_BSL_SKELETON.md`](260517_PLAN_MRL_FINETUNE_BSL_SKELETON.md) — детальный план Phase 1.1/1.2 (corpus + training)
- [`260517_PLAN_BGE_M3_BENCH_DEFERRED.md`](260517_PLAN_BGE_M3_BENCH_DEFERRED.md) — §4.1.14 retry instructions
- [`260517_PLAN_HYBRID_BM25_REJECT.md`](260517_PLAN_HYBRID_BM25_REJECT.md) — alternative retrieval path tested (REJECT)
- [04.9_Matryoshka_Embeddings.md](../framework%20documentation/2_КОНТЕКСТ/2.2_ПОИСК/04.9_Matryoshka_Embeddings.md) — full empirical matrix §4.1.6-16
- [`scripts/collect_bsl_finetune_pairs.py`](../../scripts/collect_bsl_finetune_pairs.py) — corpus skeleton
- [`scripts/finetune_qwen3_bsl_mrl.py`](../../scripts/finetune_qwen3_bsl_mrl.py) — training skeleton
- Memory: [`feedback_mrl_content_matters.md`](../../.claude/projects/C--1--Framework/memory/feedback_mrl_content_matters.md) — refined hypothesis why BSL REJECT

---

## Decision (2026-05-17)

**ALL TASKS DEFERRED.** Triggers для re-evaluation:
1. BSL collection growth > 100k pts (currently 54.8k)
2. User reports actual NDCG-bound problem in BSL retrieval (не текущие p95-bound issues, которые SQ уже решил)
3. §4.1.14 BGE-M3 bench complete с REJECT verdict
4. Allocated $20-50 cloud budget OR 1 weekend RTX 3090 downtime

Возврат к работе тривиален — skeletons готовы, план structured.
