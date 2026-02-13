"""AutoRAG Runner Script (Phase 20).

Runs automatic RAG parameter optimization via grid search.

Usage:
    python scripts/run_autorag.py --max-experiments 20 --parallel

Author: Claude Code
Version: 1.0.0 - Phase 20: AutoRAG Optimization
"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.pdf_framework.evaluation.autorag import AutoRAGOptimizer, run_autorag
from src.pdf_framework.evaluation.benchmark import BenchmarkLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("autorag.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AutoRAG - Automatic RAG Parameter Optimization"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="1c_enterprise_default",
        help="Benchmark dataset name",
    )
    parser.add_argument(
        "--max-experiments",
        type=int,
        default=20,
        help="Maximum number of experiments to run",
    )
    parser.add_argument(
        "--parallel",
        action="store_true",
        help="Run experiments in parallel",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Output directory for results",
    )
    parser.add_argument(
        "--export-env",
        action="store_true",
        help="Export best config to .env file",
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("AutoRAG - Automatic RAG Parameter Optimization")
    logger.info("=" * 60)
    logger.info(f"Dataset: {args.dataset}")
    logger.info(f"Max experiments: {args.max_experiments}")
    logger.info(f"Parallel: {args.parallel}")
    logger.info("")

    # Load benchmark dataset
    logger.info("Loading benchmark dataset...")
    loader = BenchmarkLoader()
    dataset = loader.load_dataset(args.dataset)

    logger.info(f"Loaded {len(dataset.questions)} questions")

    # Convert to AutoRAG format
    benchmark_data = loader.to_autorag_format(dataset)

    # Run optimization
    logger.info("Starting optimization...")
    logger.info("")

    optimizer = AutoRAGOptimizer(output_dir=Path(args.output_dir) if args.output_dir else None)

    report = await optimizer.optimize(
        benchmark_dataset=benchmark_data,
        max_experiments=args.max_experiments,
        run_parallel=args.parallel,
    )

    # Print results
    logger.info("")
    logger.info("=" * 60)
    logger.info("OPTIMIZATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total experiments: {report.total_experiments}")
    logger.info(f"Successful: {report.successful_experiments}")
    logger.info(f"Duration: {report.duration_seconds:.1f}s")
    logger.info("")
    logger.info(f"BEST CONFIG:")
    logger.info(f"  Name: {report.best_config.name if report.best_config else 'N/A'}")
    logger.info(f"  Score: {report.best_score:.3f}")
    if report.best_config:
        logger.info(f"  {report.best_config.description}")
    logger.info(f"Improvement: {report.improvement:+.3f}")
    logger.info("")

    # Top 5 configs
    logger.info("TOP 5 CONFIGURATIONS:")
    top_results = sorted(report.results, key=lambda r: r.f1, reverse=True)[:5]
    for i, result in enumerate(top_results, 1):
        logger.info(f"  {i}. {result.config.name}")
        logger.info(f"     F1: {result.f1:.3f} | Accuracy: {result.accuracy:.3f}")
        logger.info(f"     {result.config.description}")

    # Export to .env
    if args.export_env:
        logger.info("")
        logger.info("Exporting best config to .env...")
        optimizer.export_best_config(report)

    logger.info("")
    logger.info(f"Report saved to: {optimizer._output_dir}")
    logger.info("")


if __name__ == "__main__":
    asyncio.run(main())
