"""Lightweight TF-IDF scorer for skill-router Layer C.

Uses pre-computed vocabulary, IDF weights, and bundle centroids
from data/route-tfidf/. Runtime dependencies: numpy, json, os, re only.

sklearn is used ONLY at build time (scripts/build-route-embeddings.py).
This module uses pure numpy for scoring (~75ms vs ~1100ms with sklearn).

Usage:
    from shared.tfidf_scorer import TfidfScorer

    scorer = TfidfScorer("data/route-tfidf")
    scores = scorer.score("help me index documents")
    # -> {"indexing": 0.72, "search": 0.31, ...}
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Dict, Optional

# Lazy-loaded numpy
_np = None


def _get_numpy():
    global _np
    if _np is None:
        import numpy as np
        _np = np
    return _np


class TfidfScorer:
    """Pure-numpy TF-IDF scorer with pre-computed centroids.

    Loads artifacts from data/route-tfidf/:
      - vocabulary.json: n-gram to index mapping
      - idf_weights.npy: IDF weight vector
      - centroids_normalized.npy: L2-normalized bundle centroids
      - metadata.json: bundle names, config hash, build timestamp
    """

    def __init__(self, artifacts_dir: str):
        self._dir = artifacts_dir
        self._loaded = False
        self._vocab: Dict[str, int] = {}
        self._idf: Optional[object] = None  # numpy array
        self._centroids: Optional[object] = None  # numpy array
        self._bundle_names: list[str] = []
        self._ngram_range = (2, 4)  # char_wb n-gram range (matches sklearn build)

    def _load(self) -> bool:
        """Load pre-computed artifacts. Returns False if unavailable."""
        if self._loaded:
            return True
        try:
            np = _get_numpy()

            vocab_path = os.path.join(self._dir, "vocabulary.json")
            idf_path = os.path.join(self._dir, "idf_weights.npy")
            centroids_path = os.path.join(self._dir, "centroids_normalized.npy")
            meta_path = os.path.join(self._dir, "metadata.json")

            for p in (vocab_path, idf_path, centroids_path, meta_path):
                if not os.path.isfile(p):
                    return False

            with open(vocab_path, "r", encoding="utf-8") as f:
                self._vocab = json.load(f)

            self._idf = np.load(idf_path)
            self._centroids = np.load(centroids_path)

            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            self._bundle_names = meta.get("bundle_names", [])

            if len(self._bundle_names) != self._centroids.shape[0]:
                return False

            self._loaded = True
            return True
        except Exception:
            return False

    def _extract_char_ngrams(self, text: str) -> list[str]:
        """Extract char_wb n-grams matching sklearn's char_wb analyzer.

        char_wb = character n-grams within word boundaries.
        Each word is padded with spaces: " word " then n-grams extracted.
        """
        text = text.lower().strip()
        # Tokenize on whitespace (matching sklearn word boundary behavior)
        words = re.split(r'\s+', text)
        ngrams = []
        min_n, max_n = self._ngram_range
        for word in words:
            if not word:
                continue
            padded = f" {word} "
            for n in range(min_n, max_n + 1):
                for i in range(len(padded) - n + 1):
                    ngrams.append(padded[i:i + n])
        return ngrams

    def _text_to_tfidf_vector(self, text: str):
        """Convert text to TF-IDF vector using pre-computed vocabulary and IDF."""
        np = _get_numpy()
        ngrams = self._extract_char_ngrams(text)
        if not ngrams:
            return np.zeros(len(self._vocab), dtype=np.float64)

        # Term frequency (sublinear: 1 + log(tf))
        tf_counts: Dict[int, int] = {}
        for ng in ngrams:
            idx = self._vocab.get(ng)
            if idx is not None:
                tf_counts[idx] = tf_counts.get(idx, 0) + 1

        vec = np.zeros(len(self._vocab), dtype=np.float64)
        for idx, count in tf_counts.items():
            # sublinear_tf: 1 + log(count)
            tf = 1.0 + math.log(count) if count > 0 else 0.0
            vec[idx] = tf * self._idf[idx]

        # L2 normalize
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec /= norm

        return vec

    def score(self, text: str) -> Dict[str, float]:
        """Score text against all bundle centroids.

        Returns dict of {bundle_name: cosine_similarity}.
        Returns empty dict if artifacts not available.
        """
        if not self._load():
            return {}

        np = _get_numpy()
        vec = self._text_to_tfidf_vector(text)

        # Cosine similarity: dot product with L2-normalized centroids
        # (input vec is already L2-normalized)
        similarities = self._centroids @ vec

        return {
            name: float(sim)
            for name, sim in zip(self._bundle_names, similarities)
        }

    @property
    def available(self) -> bool:
        """Check if artifacts are loadable."""
        return self._load()
