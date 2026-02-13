"""Evaluation Framework for PDF Vector & Graph Framework (Phases 4, 20, 21).

Phase 4:  EvalRunner, EvalReport, metrics
Phase 20: AutoRAG — ParameterGrid, SmartGrid, Runner, Analyzer
Phase 21: RAGAS — Adapter, Regression, ErrorAnalysis, History
"""

# Phase 20: AutoRAG Optimization
from src.pdf_framework.evaluation.autorag import ParameterGrid, SmartGrid
from src.pdf_framework.evaluation.autorag_analyzer import AutoRAGAnalyzer
from src.pdf_framework.evaluation.autorag_runner import AutoRAGRunner, GridResult
from src.pdf_framework.evaluation.benchmark import BenchmarkDataset, BenchmarkLoader

# Phase 21: RAGAS Evaluation
from src.pdf_framework.evaluation.error_analysis import ErrorAnalyzer
from src.pdf_framework.evaluation.history import EvalHistoryStore
from src.pdf_framework.evaluation.ragas_adapter import RAGASAdapter
from src.pdf_framework.evaluation.regression import RegressionTester

__all__ = [
    # Phase 20
    "ParameterGrid",
    "SmartGrid",
    "AutoRAGRunner",
    "GridResult",
    "AutoRAGAnalyzer",
    "BenchmarkLoader",
    "BenchmarkDataset",
    # Phase 21
    "RAGASAdapter",
    "RegressionTester",
    "ErrorAnalyzer",
    "EvalHistoryStore",
]
