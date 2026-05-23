"""Retrieval smoke gate (roadmap 260509 §2.1).

Two-tier behaviour:

1. **Schema gate** (ALWAYS runs in CI) — validates `data/eval/golden_v1.json`
   loads, schema is correct, has ≥1 item. Cheap, no external services.

2. **Quality gate** (runs only when dataset size ≥ `MIN_QUALITY_GATE_SIZE`)
   — runs hybrid search per query against `pdf_documents` collection,
   computes NDCG@10, asserts ≥ NDCG_THRESHOLD. Skips when corpus or
   service is unavailable.

The threshold (0.55) is a placeholder pending real ADR; calibrated against
E5 baseline (0.45) — see `docs/framework documentation/08_ОЦЕНКА_КАЧЕСТВА/
08.5_Smoke_Gate.md` for rationale.

When the dataset is small (< 50 items) — typical state at v1 seed — only
the schema gate runs, allowing incremental dataset growth without false
quality alarms.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "eval" / "golden_v1.json"
MIN_QUALITY_GATE_SIZE = 50  # below this — schema gate only
NDCG_THRESHOLD = 0.55       # provisional; lock in via ADR after v2.0 corpus
TOP_K = 10

REQUIRED_FIELDS = {
    "id", "query", "expected_chunk_ids", "expected_keywords",
    "difficulty", "category", "domain",
}
ALLOWED_DIFFICULTY = {"easy", "medium", "hard"}
ALLOWED_CATEGORY = {"factual", "conceptual", "procedural", "analytical", "comparative"}
ALLOWED_DOMAIN = {"rag-framework", "1c", "embeddings", "infra"}


def _load_dataset() -> dict:
    if not DATASET_PATH.is_file():
        pytest.skip(f"Golden dataset not found: {DATASET_PATH}")
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


@pytest.mark.unit
class TestGoldenDatasetSchema:
    """Schema gate — always runs, no external services required."""

    def test_dataset_loads(self):
        ds = _load_dataset()
        assert isinstance(ds, dict)
        assert "items" in ds
        assert isinstance(ds["items"], list)

    def test_dataset_non_empty(self):
        ds = _load_dataset()
        assert len(ds["items"]) >= 1, "Golden dataset must have ≥1 item"

    def test_each_item_has_required_fields(self):
        ds = _load_dataset()
        offenders: list[str] = []
        for item in ds["items"]:
            missing = REQUIRED_FIELDS - set(item.keys())
            if missing:
                offenders.append(f"{item.get('id', '?')}: missing {sorted(missing)}")
        assert not offenders, "Schema violations:\n  - " + "\n  - ".join(offenders)

    def test_difficulty_values_valid(self):
        ds = _load_dataset()
        bad = [it for it in ds["items"] if it["difficulty"] not in ALLOWED_DIFFICULTY]
        assert not bad, f"Invalid difficulty in: {[it['id'] for it in bad]}"

    def test_category_values_valid(self):
        ds = _load_dataset()
        bad = [it for it in ds["items"] if it["category"] not in ALLOWED_CATEGORY]
        assert not bad, f"Invalid category in: {[it['id'] for it in bad]}"

    def test_ids_unique(self):
        ds = _load_dataset()
        ids = [it["id"] for it in ds["items"]]
        dups = {i for i in ids if ids.count(i) > 1}
        assert not dups, f"Duplicate ids: {dups}"

    def test_expected_keywords_non_empty(self):
        """Loose semantic check requires at least one keyword per query."""
        ds = _load_dataset()
        bad = [it["id"] for it in ds["items"] if not it.get("expected_keywords")]
        assert not bad, f"Items without expected_keywords: {bad}"

    def test_domain_values_valid(self):
        ds = _load_dataset()
        bad = [it for it in ds["items"] if it["domain"] not in ALLOWED_DOMAIN]
        assert not bad, f"Invalid domain in: {[it['id'] for it in bad]}"

    def test_expected_chunk_ids_is_list(self):
        ds = _load_dataset()
        bad = [it["id"] for it in ds["items"] if not isinstance(it.get("expected_chunk_ids"), list)]
        assert not bad, f"expected_chunk_ids must be a list, violations: {bad}"


@pytest.mark.integration
class TestRetrievalQualityGate:
    """Quality gate — runs only when dataset is ≥ MIN_QUALITY_GATE_SIZE.

    Requires:
      - Qdrant running with `pdf_documents` collection populated
      - Embedding service reachable (TEI on configured URL)
      - `expected_chunk_ids` populated in dataset items

    All preconditions failing → skip (don't fail the build).
    """

    def test_ndcg_above_threshold(self):
        ds = _load_dataset()
        items = ds["items"]
        if len(items) < MIN_QUALITY_GATE_SIZE:
            pytest.skip(
                f"Dataset has {len(items)} items < {MIN_QUALITY_GATE_SIZE} — "
                f"schema gate only. Expand via scripts/gen_golden_dataset.py."
            )

        items_with_gt = [it for it in items if it.get("expected_chunk_ids")]
        if len(items_with_gt) < MIN_QUALITY_GATE_SIZE:
            pytest.skip(
                f"Only {len(items_with_gt)} items have expected_chunk_ids — "
                f"need ≥{MIN_QUALITY_GATE_SIZE}. Ground truth pass pending."
            )

        try:
            from qdrant_client import QdrantClient
        except ImportError:
            pytest.skip("qdrant-client not installed (test env)")

        import math
        import os

        import httpx

        tei_url = os.environ.get("TEI_URL", "http://localhost:8080") + "/embed"
        qdrant_url = os.environ.get("QDRANT_URL", "http://localhost:6333")
        prefix = (
            "Instruct: Given a web search query, retrieve relevant passages "
            "that answer the query\nQuery: "
        )

        try:
            with httpx.Client(timeout=5.0) as health:
                health.get(f"{qdrant_url}/healthz").raise_for_status()
        except (httpx.HTTPError, OSError):
            pytest.skip(f"Qdrant unreachable at {qdrant_url}")

        try:
            with httpx.Client(timeout=5.0) as health:
                health.get(f"{os.environ.get('TEI_URL', 'http://localhost:8080')}/health").raise_for_status()
        except (httpx.HTTPError, OSError):
            pytest.skip(f"TEI unreachable at {tei_url}")

        client = QdrantClient(url=qdrant_url)

        def _ndcg_at_k(retrieved_ids: list[str], expected_ids: set[str], k: int) -> float:
            dcg = 0.0
            for rank, rid in enumerate(retrieved_ids[:k], start=1):
                if rid in expected_ids:
                    dcg += 1.0 / math.log2(rank + 1)
            ideal_hits = min(len(expected_ids), k)
            idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
            return dcg / idcg if idcg > 0 else 0.0

        scores: list[float] = []
        failures: list[str] = []
        with httpx.Client(timeout=30.0) as http:
            for item in items_with_gt:
                expected = {str(x) for x in item["expected_chunk_ids"]}
                collection = item.get("target_collection") or "framework_code_v1"
                try:
                    resp = http.post(tei_url, json={"inputs": [prefix + item["query"]]})
                    resp.raise_for_status()
                    vec = resp.json()[0]
                    hits = client.query_points(
                        collection_name=collection, query=vec, limit=TOP_K
                    ).points
                except (httpx.HTTPError, ConnectionError, TimeoutError) as e:
                    failures.append(f"{item['id']}: {type(e).__name__}: {e}")
                    continue
                retrieved = [str(h.id) for h in hits]
                scores.append(_ndcg_at_k(retrieved, expected, TOP_K))

        max_failures = max(1, int(len(items_with_gt) * 0.1))
        if len(failures) > max_failures:
            pytest.skip(
                f"Too many retrieval failures ({len(failures)}/{len(items_with_gt)} "
                f"> {max_failures} threshold): {failures[:3]}..."
            )

        mean_ndcg = sum(scores) / len(scores) if scores else 0.0
        assert mean_ndcg >= NDCG_THRESHOLD, (
            f"Mean NDCG@{TOP_K}={mean_ndcg:.3f} < threshold {NDCG_THRESHOLD} "
            f"across {len(scores)} items ({len(failures)} skipped). Retrieval regression."
        )
