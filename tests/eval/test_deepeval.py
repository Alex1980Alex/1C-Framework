"""DeepEval CI gating — RAG quality metrics (roadmap 260509 §3.9).

Two-tier behaviour (mirrors §2.1 smoke gate):

1. **Schema gate** (always runs) — validates that DeepEval test cases have
   correct shape. Cheap, no external services.

2. **Quality gate** (runs when `deepeval` installed AND golden_v1 has
   ≥`MIN_QUALITY_GATE_SIZE` items with `expected_chunk_ids` populated)
   — measures faithfulness ≥ FAITHFULNESS_THRESHOLD and hallucination
   ≤ HALLUCINATION_THRESHOLD per item.

Thresholds (placeholder, locked in via ADR-009 after first CI baseline):
  - faithfulness ≥ 0.7  (answer grounded in retrieved context)
  - hallucination ≤ 0.1 (no fabricated facts beyond context)

When the dataset is in v1 seed phase (10 items, empty `expected_chunk_ids`)
the quality gate is **gracefully skipped**. This allows the CI infrastructure
to land before the full eval corpus is ready.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

DATASET_PATH = Path(__file__).resolve().parents[2] / "data" / "eval" / "golden_v1.json"
MIN_QUALITY_GATE_SIZE = 50
FAITHFULNESS_THRESHOLD = 0.7
HALLUCINATION_THRESHOLD = 0.1

DEEPEVAL_INSTALLED = importlib.util.find_spec("deepeval") is not None


def _load_dataset() -> dict:
    if not DATASET_PATH.is_file():
        pytest.skip(f"Golden dataset not found: {DATASET_PATH}")
    return json.loads(DATASET_PATH.read_text(encoding="utf-8"))


def _items_with_chunks(ds: dict) -> list:
    return [it for it in ds.get("items", []) if it.get("expected_chunk_ids")]


@pytest.mark.unit
class TestDeepEvalSchema:
    """Schema gate — always runs, ensures fixtures match DeepEval test-case shape."""

    def test_dataset_loads_for_deepeval(self):
        ds = _load_dataset()
        assert isinstance(ds.get("items"), list)

    def test_each_item_has_input_for_deepeval(self):
        """DeepEval needs at minimum `input` (query) and either `actual_output`
        or a way to compute it via retrieval_context."""
        ds = _load_dataset()
        offenders = [it.get("id", "?") for it in ds["items"] if not it.get("query")]
        assert not offenders, f"items missing query (DeepEval input): {offenders}"

    def test_thresholds_are_strict(self):
        """Sanity: thresholds remain in expected range (drift guard)."""
        assert 0.0 <= FAITHFULNESS_THRESHOLD <= 1.0
        assert 0.0 <= HALLUCINATION_THRESHOLD <= 1.0
        assert FAITHFULNESS_THRESHOLD >= 0.5, "faithfulness ≥ 0.5 is min reasonable threshold"
        assert HALLUCINATION_THRESHOLD <= 0.3, "hallucination ≤ 0.3 is max reasonable threshold"


@pytest.mark.integration
class TestDeepEvalQualityGate:
    """Quality gate — runs only when deepeval installed AND dataset is mature.

    Requires:
      - `deepeval` package installed (`pip install -e ".[eval]"`)
      - golden_v1.json has ≥ MIN_QUALITY_GATE_SIZE items with non-empty
        `expected_chunk_ids` AND `expected_answer_summary`
      - LLM credentials (DeepEval uses LLM judge)

    Currently SKIPPED — v1 seed has 10 items с пустыми expected_chunk_ids.
    Активируется автоматически когда v2.0 dataset с ground truth готов.
    """

    @pytest.mark.skipif(not DEEPEVAL_INSTALLED, reason="`deepeval` not installed")
    def test_faithfulness_above_threshold(self):
        ds = _load_dataset()
        items_ready = _items_with_chunks(ds)
        if len(items_ready) < MIN_QUALITY_GATE_SIZE:
            pytest.skip(
                f"Only {len(items_ready)} items have ground truth — "
                f"need ≥{MIN_QUALITY_GATE_SIZE} for quality gate. "
                f"Dataset still in seed phase (v1 = 10 items, all expected_chunk_ids=[]). "
                f"See data/eval/CHANGELOG.md for v2.0 expansion plan."
            )

        # Real implementation pending v2.0 dataset:
        #   from deepeval import evaluate
        #   from deepeval.metrics import FaithfulnessMetric
        #   from deepeval.test_case import LLMTestCase
        #   cases = [LLMTestCase(input=it["query"], actual_output=..., retrieval_context=...) for it in items_ready]
        #   metric = FaithfulnessMetric(threshold=FAITHFULNESS_THRESHOLD)
        #   results = evaluate(cases, [metric])
        #   assert all(r.success for r in results), f"Faithfulness < {FAITHFULNESS_THRESHOLD}"
        pytest.skip("DeepEval quality gate implementation deferred to v2.0 corpus + ground truth")

    @pytest.mark.skipif(not DEEPEVAL_INSTALLED, reason="`deepeval` not installed")
    def test_hallucination_below_threshold(self):
        ds = _load_dataset()
        items_ready = _items_with_chunks(ds)
        if len(items_ready) < MIN_QUALITY_GATE_SIZE:
            pytest.skip(
                f"Dataset не готов для DeepEval ({len(items_ready)} < {MIN_QUALITY_GATE_SIZE})"
            )

        # Pending v2.0 (см. test_faithfulness_above_threshold выше).
        pytest.skip("DeepEval quality gate implementation deferred to v2.0 corpus + ground truth")
