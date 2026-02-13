"""Phase 20: AutoRAG Optimization — tests.

Tests for:
  - ParameterGrid: config generation, smart pruning
  - AutoRAGRunner: grid evaluation
  - AutoRAGAnalyzer: ranking, export
  - BenchmarkDataset: load/save
"""

import pytest


class TestBenchmarkDataset:
    def test_load_from_json(self, tmp_path):
        import json
        from src.pdf_framework.evaluation.benchmark import BenchmarkLoader

        data = {
            "name": "test",
            "questions": [
                {
                    "id": "q001",
                    "question": "Что такое регистр накопления?",
                    "category": "factual",
                    "expected_answer": "Регистр накопления — прикладной объект.",
                    "keywords": ["регистр", "накопления"],
                    "difficulty": "easy",
                }
            ]
        }
        path = tmp_path / "benchmarks" / "test.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        loader = BenchmarkLoader(data_dir=tmp_path / "benchmarks")
        dataset = loader.load_dataset("test")
        assert len(dataset.questions) == 1
        assert dataset.questions[0].category == "factual"

    def test_save_and_reload(self, tmp_path):
        from src.pdf_framework.evaluation.benchmark import (
            BenchmarkDataset,
            BenchmarkLoader,
            BenchmarkQuestion,
        )

        loader = BenchmarkLoader(data_dir=tmp_path / "benchmarks")
        dataset = BenchmarkDataset(
            name="test_ds",
            questions=[
                BenchmarkQuestion(
                    id="q001", question="Test?", category="factual",
                    expected_answer="Answer", difficulty="easy",
                ),
            ],
        )
        loader.save_dataset(dataset)
        reloaded = loader.load_dataset("test_ds")
        assert len(reloaded.questions) == 1
        assert reloaded.questions[0].question == "Test?"


class TestParameterGrid:
    def test_cartesian_product(self):
        from src.pdf_framework.evaluation.autorag import ParameterGrid

        grid = ParameterGrid(
            strategy=["vector", "hybrid"],
            k=[3, 5],
        )
        configs = grid.configs()
        assert len(configs) == 4

    def test_configs_count(self):
        from src.pdf_framework.evaluation.autorag import ParameterGrid

        grid = ParameterGrid(
            strategy=["vector", "hybrid", "bm25"],
            k=[3, 5, 10],
            reranker=["none", "cross_encoder"],
        )
        assert grid.configs_count() == 18

    def test_smart_grid_prunes_redundant(self):
        from src.pdf_framework.evaluation.autorag import SmartGrid

        grid = SmartGrid(
            strategy=["vector", "hybrid", "bm25"],
            reranker=["none", "flashrank"],
        )
        configs = grid.configs()
        # SmartGrid should prune BM25 + flashrank (redundant)
        assert grid.configs_count() < 6


class TestAutoRAGRunner:
    @pytest.mark.asyncio
    async def test_run_grid_collects_results(self):
        from src.pdf_framework.evaluation.autorag import ParameterGrid
        from src.pdf_framework.evaluation.autorag_runner import AutoRAGRunner

        grid = ParameterGrid(strategy=["vector"], k=[5])
        runner = AutoRAGRunner(components=None, benchmark=None)
        results = await runner.run_grid(grid)
        assert len(results) == 1
        assert results[0].mrr >= 0.0


class TestAutoRAGAnalyzer:
    def _make_results(self):
        from src.pdf_framework.evaluation.autorag_runner import GridResult
        return [
            GridResult(config={"strategy": "vector", "k": 5}, mrr=0.6, recall=0.5, precision=0.4),
            GridResult(config={"strategy": "hybrid", "k": 5}, mrr=0.8, recall=0.7, precision=0.6),
        ]

    def test_best_config(self):
        from src.pdf_framework.evaluation.autorag_analyzer import AutoRAGAnalyzer

        analyzer = AutoRAGAnalyzer(results=self._make_results())
        best = analyzer.best_config()
        assert best is not None
        assert best["strategy"] == "hybrid"

    def test_comparison_table_markdown(self):
        from src.pdf_framework.evaluation.autorag_analyzer import AutoRAGAnalyzer

        analyzer = AutoRAGAnalyzer(results=self._make_results())
        table = analyzer.comparison_table()
        assert isinstance(table, str)
        assert "|" in table  # markdown table

    def test_export_env(self, tmp_path):
        from src.pdf_framework.evaluation.autorag_analyzer import AutoRAGAnalyzer

        analyzer = AutoRAGAnalyzer(results=self._make_results())
        path = tmp_path / ".env.optimal"
        analyzer.export_env(analyzer.best_config(), path)
        assert path.exists()

    def test_sensitivity_analysis(self):
        from src.pdf_framework.evaluation.autorag_analyzer import AutoRAGAnalyzer

        analyzer = AutoRAGAnalyzer(results=self._make_results())
        sensitivity = analyzer.sensitivity_analysis()
        assert isinstance(sensitivity, dict)
