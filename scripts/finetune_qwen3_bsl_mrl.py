#!/usr/bin/env python3
"""SKELETON: MRL fine-tune Qwen3-Embedding-8B on BSL pairs (§4.1.13).

NOT EXECUTABLE without:
    1. Training corpus from scripts/collect_bsl_finetune_pairs.py (≥10K pairs)
    2. GPU with ≥24 GB VRAM (LoRA recommended; full fine-tune needs 48+ GB)
    3. ~5-10 GPU-hours (LoRA) or 10-50 (full)

Reference architecture: sentence-transformers MatryoshkaLoss.

Recommended: use LoRA via PEFT to reduce memory + train time.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def build_dataset(pairs_path: Path):
    """Load JSONL pairs into HuggingFace Dataset format.

    Production: use datasets.Dataset.from_generator with deduplication and
    train/eval split (90/10 stratified by chunk_type).
    """
    from datasets import Dataset

    rows: list[dict] = []
    with open(pairs_path, encoding="utf-8") as f:
        for line in f:
            d = json.loads(line)
            rows.append(
                {
                    "anchor": d["query"],
                    "positive": d["source_text"],
                }
            )
    return Dataset.from_list(rows)


def train_with_mrl_loss(
    base_model: str,
    train_dataset,
    eval_dataset,
    output_dir: Path,
    dims: list[int] = [4096, 2048, 1024, 512, 256],
    epochs: int = 3,
    batch_size: int = 16,
    use_lora: bool = True,
) -> None:
    """Fine-tune with MatryoshkaLoss over multiple dim granularities.

    Key hyperparams (per Qwen3 fine-tuning best practices):
        - learning_rate=2e-5 (10x lower than from-scratch)
        - warmup_ratio=0.1
        - fp16=True (bf16 if A100/H100)
        - gradient_accumulation_steps=4 (effective batch=64)

    LoRA config (PEFT):
        r=16, alpha=32, target_modules=["q_proj", "v_proj", "o_proj"]

    Eval metric: NDCG@10 on grounded golden_v1 BSL queries (15 items) — same
    as production bench. Save best checkpoint by eval NDCG.
    """
    raise NotImplementedError(
        "SKELETON ONLY. To implement:\n"
        "  1. Install: pip install sentence-transformers peft accelerate\n"
        "  2. Load Qwen/Qwen3-Embedding-8B with SentenceTransformer\n"
        "  3. Wrap base MultipleNegativesRankingLoss in MatryoshkaLoss(dims=...)\n"
        "  4. Configure SentenceTransformerTrainer + LoRA adapter\n"
        "  5. Train, save adapter, merge for inference\n"
        "  Refs:\n"
        "    https://sbert.net/examples/training/matryoshka/\n"
        "    https://huggingface.co/blog/matryoshka\n"
        "    https://github.com/RAIVNLab/MRL"
    )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pairs", default="data/eval/bsl_pairs_for_finetune.jsonl")
    ap.add_argument("--base-model", default="Qwen/Qwen3-Embedding-8B")
    ap.add_argument("--output-dir", default="models/qwen3-bsl-mrl-lora")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--batch-size", type=int, default=16)
    ap.add_argument("--no-lora", action="store_true")
    args = ap.parse_args()

    pairs_path = Path(args.pairs)
    if not pairs_path.exists():
        print(f"ERROR: {pairs_path} missing. Run scripts/collect_bsl_finetune_pairs.py first.")
        sys.exit(1)

    ds = build_dataset(pairs_path)
    print(f"Loaded {len(ds)} pairs from {pairs_path}")

    # Skeleton call — raises NotImplementedError
    train_with_mrl_loss(
        base_model=args.base_model,
        train_dataset=ds,
        eval_dataset=None,
        output_dir=Path(args.output_dir),
        epochs=args.epochs,
        batch_size=args.batch_size,
        use_lora=not args.no_lora,
    )
