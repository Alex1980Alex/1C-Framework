#!/usr/bin/env python3
"""Build TF-IDF artifacts for skill-router Layer C.

Reads skill-router-config.json, extracts keywords + utterances per bundle,
fits sklearn TfidfVectorizer, and exports artifacts to data/route-tfidf/.

Output files:
  - vocabulary.json: n-gram to index mapping
  - idf_weights.npy: IDF weight vector
  - centroids_normalized.npy: L2-normalized bundle centroids
  - metadata.json: bundle names, config hash, build timestamp

Usage:
    python scripts/build-route-embeddings.py
    python scripts/build-route-embeddings.py --validate  # also validates pure-Python vs sklearn
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

PROJECT_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_DIR / ".claude" / "skills" / "skill-router-config.json"
OUTPUT_DIR = PROJECT_DIR / "data" / "route-tfidf"


def load_config() -> dict:
    """Load skill-router-config.json."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_bundle_texts(config: dict) -> dict[str, list[str]]:
    """Extract all text examples per bundle (keywords + weighted_keywords + utterances)."""
    bundles = config.get("bundles", {})
    result = {}
    for name, bundle in bundles.items():
        texts = []
        # Keywords (weight 1)
        texts.extend(bundle.get("keywords", []))
        # Weighted keywords (their text, not weight)
        texts.extend(bundle.get("weighted_keywords", {}).keys())
        # Utterances (paraphrases)
        texts.extend(bundle.get("utterances", []))
        result[name] = texts
    return result


def build_artifacts(config: dict, validate: bool = False) -> None:
    """Build TF-IDF artifacts using sklearn."""
    from sklearn.feature_extraction.text import TfidfVectorizer

    bundle_texts = extract_bundle_texts(config)
    bundle_names = sorted(bundle_texts.keys())

    # Flatten all texts for fitting the vectorizer
    all_texts = []
    text_to_bundle = []
    for name in bundle_names:
        for text in bundle_texts[name]:
            all_texts.append(text.lower())
            text_to_bundle.append(name)

    print(f"Total bundles: {len(bundle_names)}")
    print(f"Total texts: {len(all_texts)}")

    # Fit TF-IDF vectorizer
    vectorizer = TfidfVectorizer(
        analyzer="char_wb",
        ngram_range=(2, 4),
        sublinear_tf=True,
        dtype=np.float64,
    )
    tfidf_matrix = vectorizer.fit_transform(all_texts)

    # Extract vocabulary and IDF
    vocab = vectorizer.vocabulary_  # {ngram: index}
    idf = vectorizer.idf_  # numpy array

    print(f"Vocabulary size: {len(vocab)}")
    print(f"IDF shape: {idf.shape}")

    # Compute bundle centroids (average of all text vectors per bundle)
    centroids = np.zeros((len(bundle_names), len(vocab)), dtype=np.float64)
    for i, name in enumerate(bundle_names):
        indices = [j for j, bn in enumerate(text_to_bundle) if bn == name]
        if indices:
            bundle_vectors = tfidf_matrix[indices].toarray()
            centroid = bundle_vectors.mean(axis=0)
            # L2 normalize
            norm = np.linalg.norm(centroid)
            if norm > 0:
                centroid /= norm
            centroids[i] = centroid

    # Save artifacts
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # vocabulary.json
    vocab_path = OUTPUT_DIR / "vocabulary.json"
    with open(vocab_path, "w", encoding="utf-8") as f:
        json.dump(vocab, f, ensure_ascii=False, indent=None)
    print(f"Saved: {vocab_path} ({os.path.getsize(vocab_path):,} bytes)")

    # idf_weights.npy
    idf_path = OUTPUT_DIR / "idf_weights.npy"
    np.save(idf_path, idf)
    print(f"Saved: {idf_path} ({os.path.getsize(idf_path):,} bytes)")

    # centroids_normalized.npy
    centroids_path = OUTPUT_DIR / "centroids_normalized.npy"
    np.save(centroids_path, centroids)
    print(f"Saved: {centroids_path} ({os.path.getsize(centroids_path):,} bytes)")

    # metadata.json
    config_hash = hashlib.md5(
        json.dumps(config, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()[:12]
    metadata = {
        "bundle_names": bundle_names,
        "config_version": config.get("version", "?"),
        "config_hash": config_hash,
        "build_timestamp": datetime.now().isoformat(),
        "vocabulary_size": len(vocab),
        "num_bundles": len(bundle_names),
        "total_texts": len(all_texts),
        "ngram_range": [2, 4],
        "texts_per_bundle": {
            name: len(bundle_texts[name]) for name in bundle_names
        },
    }
    meta_path = OUTPUT_DIR / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    print(f"Saved: {meta_path}")

    print(f"\nBuild complete. Config hash: {config_hash}")
    print(f"Texts per bundle:")
    for name in bundle_names:
        print(f"  {name:25s}: {len(bundle_texts[name]):3d} texts")

    # Validation: compare pure-Python n-gram extraction vs sklearn
    if validate:
        _validate_ngrams(vectorizer, all_texts[:10])

    # Quick sanity check: score a test prompt
    _sanity_check(centroids, bundle_names, vocab, idf)


def _validate_ngrams(vectorizer, sample_texts: list[str]) -> None:
    """Validate pure-Python char_wb n-gram extraction matches sklearn."""
    print("\n--- N-gram Validation ---")

    def pure_python_ngrams(text: str, ngram_range=(2, 4)) -> set[str]:
        """Pure-Python char_wb n-gram extraction (matches tfidf_scorer.py)."""
        text = text.lower().strip()
        words = re.split(r'\s+', text)
        ngrams = set()
        min_n, max_n = ngram_range
        for word in words:
            if not word:
                continue
            padded = f" {word} "
            for n in range(min_n, max_n + 1):
                for i in range(len(padded) - n + 1):
                    ngrams.add(padded[i:i + n])
        return ngrams

    # sklearn's char_wb analyzer
    sklearn_analyzer = vectorizer.build_analyzer()

    mismatches = 0
    for text in sample_texts:
        py_ngrams = pure_python_ngrams(text)
        sk_ngrams = set(sklearn_analyzer(text))
        if py_ngrams != sk_ngrams:
            mismatches += 1
            only_py = py_ngrams - sk_ngrams
            only_sk = sk_ngrams - py_ngrams
            print(f"  MISMATCH: '{text[:40]}...'")
            if only_py:
                print(f"    Only in Python ({len(only_py)}): {list(only_py)[:5]}")
            if only_sk:
                print(f"    Only in sklearn ({len(only_sk)}): {list(only_sk)[:5]}")

    if mismatches == 0:
        print(f"  All {len(sample_texts)} samples match!")
    else:
        print(f"  {mismatches}/{len(sample_texts)} mismatches")


def _sanity_check(centroids, bundle_names, vocab, idf):
    """Quick sanity check: score a few test prompts."""
    print("\n--- Sanity Check ---")

    test_prompts = [
        "help me index documents for search",
        "build a graph of related entities",
        "the hook is not working correctly",
        "create a new plugin for the assistant",
        "retry failed API calls with backoff",
    ]

    for prompt in test_prompts:
        # Compute TF-IDF vector (pure-Python style)
        text = prompt.lower().strip()
        words = re.split(r'\s+', text)
        ngrams = []
        for word in words:
            padded = f" {word} "
            for n in range(2, 5):
                for i in range(len(padded) - n + 1):
                    ngrams.append(padded[i:i + n])

        tf_counts = {}
        for ng in ngrams:
            idx = vocab.get(ng)
            if idx is not None:
                tf_counts[idx] = tf_counts.get(idx, 0) + 1

        vec = np.zeros(len(vocab), dtype=np.float64)
        for idx, count in tf_counts.items():
            tf = 1.0 + math.log(count) if count > 0 else 0.0
            vec[idx] = tf * idf[idx]

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm

        sims = centroids @ vec
        top_idx = np.argsort(sims)[::-1][:3]

        matches = [(bundle_names[i], f"{sims[i]:.3f}") for i in top_idx if sims[i] > 0.05]
        print(f"  '{prompt[:50]}' -> {matches}")


def main():
    parser = argparse.ArgumentParser(description="Build TF-IDF artifacts for skill-router")
    parser.add_argument("--validate", action="store_true", help="Validate Python vs sklearn n-gram extraction")
    args = parser.parse_args()

    if not CONFIG_PATH.exists():
        print(f"ERROR: Config not found: {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)

    config = load_config()
    print(f"Config version: {config.get('version')}")
    print(f"Output dir: {OUTPUT_DIR}")
    print()

    build_artifacts(config, validate=args.validate)


if __name__ == "__main__":
    main()
