"""AutoRAG Analyzer — rank and export results (Phase 20).

Author: Claude Code
Version: 1.0.0 - Phase 20: AutoRAG Optimization
"""

import logging
from pathlib import Path
from typing import Any

from src.pdf_framework.evaluation.autorag_runner import GridResult

logger = logging.getLogger(__name__)


class AutoRAGAnalyzer:
    """Analyze AutoRAG grid search results."""

    def __init__(self, results: list[GridResult] | None = None):
        self._results = results or []

    def best_config(self) -> dict[str, Any] | None:
        """Return config with highest MRR."""
        if not self._results:
            return {}
        best = max(self._results, key=lambda r: r.mrr)
        return best.config

    def comparison_table(self) -> str:
        """Render results as a markdown table."""
        if not self._results:
            return "| Config | MRR | Recall | Precision | Latency |\n|---|---|---|---|---|"

        lines = ["| Config | MRR | Recall | Precision | Latency |", "|---|---|---|---|---|"]
        for r in sorted(self._results, key=lambda x: x.mrr, reverse=True):
            name = str(r.config)[:40]
            lines.append(f"| {name} | {r.mrr:.3f} | {r.recall:.3f} | {r.precision:.3f} | {r.latency_ms:.0f}ms |")
        return "\n".join(lines)

    def export_env(self, config: dict[str, Any] | None, path: str | Path | None = None) -> None:
        """Export config as .env file."""
        path = Path(path) if path else Path(".env.optimal")
        config = config or {}

        lines = ["# AutoRAG Optimal Configuration"]
        for k, v in config.items():
            lines.append(f"{k.upper()}={v}")

        path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"[ANALYZER] Exported config to {path}")

    def sensitivity_analysis(self) -> dict[str, Any]:
        """Analyze which parameters have most impact on MRR."""
        if not self._results:
            return {}

        # Group by each parameter and compute mean MRR
        param_impact: dict[str, dict[str, list[float]]] = {}

        for r in self._results:
            for param, value in r.config.items():
                key = str(param)
                val_key = str(value)
                if key not in param_impact:
                    param_impact[key] = {}
                if val_key not in param_impact[key]:
                    param_impact[key][val_key] = []
                param_impact[key][val_key].append(r.mrr)

        # Compute variance for each parameter
        result: dict[str, Any] = {}
        for param, values in param_impact.items():
            means = {v: sum(scores) / len(scores) for v, scores in values.items()}
            if len(means) > 1:
                mean_vals = list(means.values())
                spread = max(mean_vals) - min(mean_vals)
                result[param] = {"values": means, "spread": round(spread, 4)}

        return result
