"""Run analyzers — post-run reporting for indexing and graph-build scripts.

Used by ``scripts/analyze_run.py`` and the Stop-hook
``.claude/hooks/post-indexing-analyzer.py``. Reads progress events from
``data/indexing-progress.jsonl`` and (optionally) introspects Qdrant /
Neo4j / NetworkX artefacts to produce a Markdown + JSON report under
``data/reports/<mode>/``.
"""

from .base import AnalyzerBase, ReportSpec
from .graph import GraphAnalyzer
from .indexing import IndexingAnalyzer
from .report_writer import write_report

__all__ = ["AnalyzerBase", "ReportSpec", "IndexingAnalyzer", "GraphAnalyzer", "write_report"]
