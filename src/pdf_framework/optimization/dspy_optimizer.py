"""DSPy GEPA optimizer runner (Phase 34, migrated to GEPA per roadmap 260509 §3.4).

Handles:
- Loading/saving evaluation datasets
- Running GEPA optimization (Generative Evolutionary Prompt Adaptation,
  DSPy ≥3.0; supersedes MIPROv2 deprecated in DSPy 3.x)
- Saving/loading optimized modules
- A/B comparison between original and optimized prompts

Migration note: prior MIPROv2 → dspy.GEPA via reflection-based optimization.
2-arg CompositeMetric wrapped via _gepa_metric adapter to satisfy the
GEPAFeedbackMetric Protocol (gold, pred, trace, pred_name, pred_trace).
"""

import json
import logging
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class OptimizationResult(BaseModel):
    """Result of an optimization run."""

    status: str = "pending"  # pending | running | completed | failed
    started_at: float = 0.0
    completed_at: float = 0.0
    modules_optimized: list[str] = Field(default_factory=list)
    metrics_before: dict[str, float] = Field(default_factory=dict)
    metrics_after: dict[str, float] = Field(default_factory=dict)
    improvement_pct: float = 0.0
    dataset_size: int = 0
    error: str = ""


class EvaluationPair(BaseModel):
    """A single question-answer pair for evaluation."""

    question: str
    answer: str
    question_type: str = "factual"  # factual | comparative | analytical | overview
    context: str = ""  # Optional reference context
    source: str = ""


class DSPyOptimizer:
    """Manages DSPy prompt optimization lifecycle.

    Provides:
    - Dataset management (load, add, export)
    - Module optimization via GEPA (migrated from MIPROv2 per roadmap 260509 §3.4)
    - Optimized module persistence
    - Before/after metric comparison
    """

    def __init__(
        self,
        dataset_path: str | Path = "data/dspy_evaluation_dataset.json",
        optimized_dir: str | Path = "data/dspy_optimized",
        api_key: str = "",
        base_url: str = "",
        model: str = "claude-sonnet-4-5-20250929",
    ):
        self._dataset_path = Path(dataset_path)
        self._optimized_dir = Path(optimized_dir)
        self._optimized_dir.mkdir(parents=True, exist_ok=True)
        self._api_key = api_key
        self._base_url = base_url
        self._model = model
        self._dataset: list[EvaluationPair] = []
        self._last_result: OptimizationResult | None = None

    def load_dataset(self) -> list[EvaluationPair]:
        """Load evaluation dataset from JSON file."""
        if self._dataset_path.exists():
            with open(self._dataset_path) as f:
                data = json.load(f)
            self._dataset = [EvaluationPair(**item) for item in data]
            logger.info("[DSPY] Loaded %d evaluation pairs", len(self._dataset))
        else:
            self._dataset = []
            logger.info("[DSPY] No dataset found at %s", self._dataset_path)
        return self._dataset

    def save_dataset(self) -> None:
        """Save evaluation dataset to JSON file."""
        self._dataset_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self._dataset_path, "w", encoding="utf-8") as f:
            json.dump(
                [p.model_dump() for p in self._dataset],
                f,
                ensure_ascii=False,
                indent=2,
            )
        logger.info("[DSPY] Saved %d evaluation pairs", len(self._dataset))

    def add_pair(self, pair: EvaluationPair) -> None:
        """Add a new evaluation pair to the dataset."""
        self._dataset.append(pair)

    async def add_pairs_from_feedback(self, feedback_store: Any) -> int:
        """Import positive Q&A pairs from FeedbackStore (score=1).

        Loads up to 100 most recent positive feedback entries and adds
        them to the evaluation dataset as EvaluationPair objects.

        Returns number of pairs added.
        """
        try:
            positive_entries = await feedback_store.get_positive(limit=100)
            count = 0
            for entry in positive_entries:
                self.add_pair(
                    EvaluationPair(
                        question=entry.question,
                        answer=entry.answer,
                        source="feedback",
                    )
                )
                count += 1
            if count:
                logger.info("[DSPY] Imported %d positive feedback pairs", count)
            return count
        except AttributeError:
            raise  # feedback_store missing get_positive — programming error, re-raise
        except Exception as e:
            logger.warning("[DSPY] Failed to import from feedback store: %s", e)
            return 0

    @property
    def dataset_size(self) -> int:
        return len(self._dataset)

    @property
    def last_result(self) -> OptimizationResult | None:
        return self._last_result

    async def optimize(
        self,
        max_trials: int = 50,
        module_names: list[str] | None = None,
    ) -> OptimizationResult:
        """Run GEPA optimization on specified modules (roadmap 260509 §3.4).

        Source: dspy 3.2.1 — `dspy.GEPA` (Generative Evolutionary Prompt
        Adaptation). Replaces MIPROv2 per upstream deprecation. Uses
        reflection-based optimization with explicit feedback metric.

        Args:
            max_trials: Used as `max_full_evals` budget for GEPA. Legacy
                arg name kept for API back-compat with MIPROv2 callers.
            module_names: Which modules to optimize (default: all).

        Returns:
            OptimizationResult with before/after metrics.
        """
        from src.pdf_framework.optimization.dspy_modules import is_dspy_available

        if not is_dspy_available():
            return OptimizationResult(
                status="failed",
                error="dspy-ai not installed. Run: pip install dspy-ai",
            )

        if not self._dataset:
            self.load_dataset()

        if len(self._dataset) < 10:
            return OptimizationResult(
                status="failed",
                error=f"Need at least 10 evaluation pairs, have {len(self._dataset)}",
                dataset_size=len(self._dataset),
            )

        import dspy

        from src.pdf_framework.optimization.dspy_metrics import CompositeMetric
        from src.pdf_framework.optimization.dspy_modules import (
            AnalyzerModule,
            GraderModule,
            RewriterModule,
        )

        result = OptimizationResult(
            status="running",
            started_at=time.time(),
            dataset_size=len(self._dataset),
        )

        try:
            # Configure DSPy LM
            lm = dspy.LM(
                model=f"anthropic/{self._model}",
                api_key=self._api_key,
                api_base=self._base_url or None,
            )
            dspy.configure(lm=lm)

            # Convert dataset to DSPy examples
            trainset = [
                dspy.Example(
                    question=p.question,
                    answer=p.answer,
                    question_type=p.question_type,
                ).with_inputs("question")
                for p in self._dataset
            ]

            metric = CompositeMetric()

            # Determine which modules to optimize
            available_modules = {
                "grader": GraderModule,
                "rewriter": RewriterModule,
                "analyzer": AnalyzerModule,
            }
            targets = module_names or list(available_modules.keys())

            # Run optimization for each module
            for name in targets:
                if name not in available_modules:
                    logger.warning("[DSPY] Unknown module: %s", name)
                    continue

                logger.info("[DSPY] Optimizing module: %s", name)

                module_cls = available_modules[name]
                module = module_cls()

                # Evaluate before
                before_scores = []
                for ex in trainset[:20]:  # Sample for pre-evaluation
                    try:
                        pred = module.forward(
                            question=ex.question,
                            **({"document": "", "context": ""}.get(name, {})),
                        )
                        score = metric(ex.toDict(), pred)
                        before_scores.append(score)
                    except Exception:
                        before_scores.append(0.0)

                avg_before = sum(before_scores) / len(before_scores) if before_scores else 0.0
                result.metrics_before[name] = round(avg_before, 3)

                # GEPA optimization (Source: dspy 3.2.1 inspect.signature(dspy.GEPA))
                try:
                    # GEPA expects GEPAFeedbackMetric Protocol:
                    #   metric(gold, pred, trace, pred_name, pred_trace) -> float
                    # Adapter wraps the existing 2-arg CompositeMetric.
                    def _gepa_metric(
                        gold: Any,
                        pred: Any,
                        trace: Any = None,
                        pred_name: str | None = None,
                        pred_trace: Any = None,
                    ) -> float:
                        try:
                            return float(
                                metric(gold.toDict() if hasattr(gold, "toDict") else gold, pred)
                            )
                        except Exception:
                            return 0.0

                    optimizer = dspy.GEPA(
                        metric=_gepa_metric,
                        max_full_evals=max_trials,
                        reflection_lm=lm,  # reuse configured LM for reflection step
                        skip_perfect_score=True,
                        track_stats=False,
                    )
                    optimized = optimizer.compile(
                        module,
                        trainset=trainset,
                    )

                    # Save optimized module
                    save_path = self._optimized_dir / f"{name}_optimized.json"
                    optimized.save(str(save_path))
                    result.modules_optimized.append(name)

                    # Evaluate after
                    after_scores = []
                    for ex in trainset[:20]:
                        try:
                            pred = optimized.forward(
                                question=ex.question,
                                **({"document": "", "context": ""}.get(name, {})),
                            )
                            score = metric(ex.toDict(), pred)
                            after_scores.append(score)
                        except Exception:
                            after_scores.append(0.0)

                    avg_after = sum(after_scores) / len(after_scores) if after_scores else 0.0
                    result.metrics_after[name] = round(avg_after, 3)

                    logger.info(
                        "[DSPY] %s: %.3f -> %.3f (%.1f%% improvement)",
                        name,
                        avg_before,
                        avg_after,
                        (avg_after - avg_before) / max(avg_before, 0.001) * 100,
                    )

                except Exception as e:
                    logger.error("[DSPY] Optimization of %s failed: %s", name, e)
                    result.metrics_after[name] = avg_before

            # Calculate overall improvement
            if result.metrics_before and result.metrics_after:
                before_avg = sum(result.metrics_before.values()) / len(result.metrics_before)
                after_avg = sum(result.metrics_after.values()) / len(result.metrics_after)
                result.improvement_pct = round(
                    (after_avg - before_avg) / max(before_avg, 0.001) * 100, 1
                )

            result.status = "completed"
            result.completed_at = time.time()

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            result.completed_at = time.time()
            logger.error("[DSPY] Optimization failed: %s", e)

        self._last_result = result
        return result

    def load_optimized_module(self, name: str) -> Any:
        """Load an optimized module from disk (if available).

        Returns the optimized module or None if not found.
        """
        from src.pdf_framework.optimization.dspy_modules import is_dspy_available

        if not is_dspy_available():
            return None

        save_path = self._optimized_dir / f"{name}_optimized.json"
        if not save_path.exists():
            return None

        from src.pdf_framework.optimization.dspy_modules import (
            AnalyzerModule,
            GraderModule,
            RewriterModule,
        )

        module_map = {
            "grader": GraderModule,
            "rewriter": RewriterModule,
            "analyzer": AnalyzerModule,
        }

        cls = module_map.get(name)
        if cls is None:
            return None

        try:
            module = cls()
            module.load(str(save_path))
            logger.info("[DSPY] Loaded optimized module: %s", name)
            return module
        except Exception as e:
            logger.warning("[DSPY] Failed to load optimized %s: %s", name, e)
            return None

    def get_stats(self) -> dict[str, Any]:
        """Get optimizer statistics."""
        optimized_files = list(self._optimized_dir.glob("*_optimized.json"))
        return {
            "dataset_size": len(self._dataset),
            "dataset_path": str(self._dataset_path),
            "optimized_modules": [f.stem.replace("_optimized", "") for f in optimized_files],
            "last_result": self._last_result.model_dump() if self._last_result else None,
        }
