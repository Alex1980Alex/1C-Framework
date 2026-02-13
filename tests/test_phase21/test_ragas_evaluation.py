"""Phase 21: RAGAS Evaluation — tests.

Tests for:
  - RAGASAdapter: convert our format to RAGAS Dataset
  - RegressionTester: compare with baseline
  - ErrorAnalyzer: classify error types
  - EvalHistoryStore: store/query metrics over time
"""

import pytest


class TestRAGASAdapter:
    def test_to_ragas_dataset(self):
        from src.pdf_framework.evaluation.ragas_adapter import RAGASAdapter

        adapter = RAGASAdapter()
        dataset = adapter.to_ragas_dataset(
            questions=["Что такое регистр?"],
            answers=["Регистр — прикладной объект."],
            contexts=[["Регистр хранит данные."]],
            ground_truths=["Регистр — объект конфигурации."],
        )
        assert len(dataset) == 1
        assert "question" in dataset.column_names

    @pytest.mark.asyncio
    async def test_evaluate_returns_metrics(self):
        from src.pdf_framework.evaluation.ragas_adapter import RAGASAdapter

        adapter = RAGASAdapter()
        dataset = adapter.to_ragas_dataset(
            questions=["Q?"], answers=["A."],
            contexts=[["C."]], ground_truths=["GT."],
        )
        result = await adapter.evaluate(dataset, metrics=["faithfulness"])
        assert "faithfulness" in result
        assert 0.0 <= result["faithfulness"] <= 1.0


class TestRegressionTester:
    @pytest.mark.asyncio
    async def test_quick_regression_passes(self, tmp_path):
        from src.pdf_framework.evaluation.regression import RegressionTester

        tester = RegressionTester(baseline_path=tmp_path / "baseline.json")
        result = await tester.run_quick(components=None, dataset=None)
        assert isinstance(result.passed, bool)
        assert isinstance(result.summary, str)

    def test_compare_with_baseline_no_degradation(self, tmp_path):
        from src.pdf_framework.evaluation.regression import RegressionTester

        tester = RegressionTester(
            baseline_path=tmp_path / "baseline.json",
            threshold=0.05,
        )
        result = tester.compare_with_baseline(current=None)
        assert result.passed is True
        assert len(result.regressions) == 0

    def test_compare_detects_regression(self, tmp_path):
        import json

        from src.pdf_framework.evaluation.regression import RegressionTester

        baseline_path = tmp_path / "baseline.json"
        baseline_path.write_text(json.dumps({"mrr": 0.8, "recall": 0.7}))

        tester = RegressionTester(
            baseline_path=baseline_path,
            threshold=0.05,
        )
        result = tester.compare_with_baseline(current={"mrr": 0.5, "recall": 0.3})
        assert isinstance(result.regressions, list)
        assert len(result.regressions) > 0
        assert result.passed is False


class TestErrorAnalyzer:
    @pytest.mark.asyncio
    async def test_classify_retrieval_miss(self):
        from src.pdf_framework.evaluation.error_analysis import ErrorAnalyzer, ErrorType

        analyzer = ErrorAnalyzer()
        report = await analyzer.analyze(report=None)
        assert isinstance(report.by_type, dict)

    @pytest.mark.asyncio
    async def test_recommendations_returned(self):
        from src.pdf_framework.evaluation.error_analysis import ErrorAnalyzer

        analyzer = ErrorAnalyzer()
        report = await analyzer.analyze(report=None)
        assert isinstance(report.recommendations, list)
        assert len(report.recommendations) > 0


class TestEvalHistoryStore:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, tmp_path):
        from src.pdf_framework.evaluation.history import EvalHistoryStore

        store = EvalHistoryStore(db_path=tmp_path / "history.db")
        await store.initialize()
        run_id = await store.store(report=None, version="v0.8.0")
        assert run_id

    @pytest.mark.asyncio
    async def test_get_history_returns_points(self, tmp_path):
        from src.pdf_framework.evaluation.history import EvalHistoryStore

        store = EvalHistoryStore(db_path=tmp_path / "history.db")
        await store.initialize()
        history = await store.get_history("mrr", days=30)
        assert isinstance(history, list)
