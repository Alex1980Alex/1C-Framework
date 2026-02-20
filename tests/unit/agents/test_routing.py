"""Unit tests for Model Routing (Phase 54)."""

import pytest

from src.pdf_framework.agents.routing.classifier import (
    ComplexityLevel,
    ModelRoutingClassifier,
)
from src.pdf_framework.agents.routing.budget import CostBudget


# ============================================================================
# Classifier Tests
# ============================================================================


class TestModelRoutingClassifier:
    """Test query complexity classification."""

    @pytest.fixture
    def classifier(self):
        return ModelRoutingClassifier()

    def test_simple_factual_query(self, classifier):
        result = classifier.classify("Что такое ИНН?")
        assert result.level == ComplexityLevel.SIMPLE
        assert "haiku" in result.model.lower()

    def test_simple_short_query(self, classifier):
        result = classifier.classify("Версия платформы")
        assert result.level == ComplexityLevel.SIMPLE

    def test_moderate_how_to(self, classifier):
        result = classifier.classify("Как создать справочник в конфигураторе?")
        assert result.level == ComplexityLevel.MODERATE
        assert "sonnet" in result.model.lower()

    def test_moderate_code_request(self, classifier):
        result = classifier.classify("Напиши код обработки проведения документа")
        assert result.level == ComplexityLevel.MODERATE

    def test_moderate_example(self, classifier):
        result = classifier.classify("Покажи пример запроса к регистру сведений")
        assert result.level == ComplexityLevel.MODERATE

    def test_moderate_enumeration(self, classifier):
        result = classifier.classify("Перечисли все типы регистров в 1С")
        assert result.level == ComplexityLevel.MODERATE

    def test_complex_comparison(self, classifier):
        result = classifier.classify("Сравни справочники и перечисления — в чём различия между ними?")
        assert result.level == ComplexityLevel.COMPLEX
        assert "opus" in result.model.lower()

    def test_complex_analysis(self, classifier):
        result = classifier.classify("Проанализируй архитектуру регистров накопления и объясни подробно")
        assert result.level == ComplexityLevel.COMPLEX

    def test_complex_multi_question(self, classifier):
        result = classifier.classify(
            "Что такое документ в 1С? Как он связан со справочником? "
            "Какие есть ограничения при проведении?"
        )
        assert result.level == ComplexityLevel.COMPLEX

    def test_custom_model_map(self):
        custom_map = {
            ComplexityLevel.SIMPLE: "gpt-4o-mini",
            ComplexityLevel.MODERATE: "gpt-4o",
            ComplexityLevel.COMPLEX: "gpt-4o",
        }
        classifier = ModelRoutingClassifier(model_map=custom_map)
        result = classifier.classify("Что такое ИНН?")
        assert result.model == "gpt-4o-mini"

    def test_classification_returns_features(self, classifier):
        result = classifier.classify("Как создать справочник?")
        assert "word_count" in result.features
        assert "moderate_hits" in result.features
        assert isinstance(result.reason, str)
        assert len(result.reason) > 0


# ============================================================================
# Budget Tests
# ============================================================================


class TestCostBudget:
    """Test cost budget enforcement."""

    def test_initial_status(self):
        budget = CostBudget(per_query_limit=0.10, daily_limit=50.0)
        status = budget.get_status()
        assert status.daily_spent == 0.0
        assert status.remaining_daily == 50.0
        assert not status.is_over_budget

    def test_record_usage(self):
        budget = CostBudget(per_query_limit=0.10, daily_limit=50.0)
        cost = budget.record_usage("claude-sonnet-4-5-20250929", 1000, 500)
        assert cost > 0
        assert budget.daily_spent > 0

    def test_estimate_cost(self):
        budget = CostBudget()
        cost = budget.estimate_cost("claude-haiku-3-5", 1_000_000, 1_000_000)
        # Haiku: $0.25/1M input + $1.25/1M output
        assert abs(cost - 1.50) < 0.01

    def test_estimate_cost_opus(self):
        budget = CostBudget()
        cost = budget.estimate_cost("claude-opus-4-6", 1_000_000, 1_000_000)
        # Opus: $15/1M input + $75/1M output
        assert abs(cost - 90.0) < 0.01

    def test_check_budget_allows_within_limit(self):
        budget = CostBudget(per_query_limit=1.0, daily_limit=100.0)
        model = budget.check_budget("claude-sonnet-4-5-20250929")
        assert model == "claude-sonnet-4-5-20250929"

    def test_check_budget_downgrades_expensive(self):
        budget = CostBudget(per_query_limit=0.001, daily_limit=100.0)
        model = budget.check_budget("claude-opus-4-6")
        assert "haiku" in model.lower()

    def test_daily_budget_exhausted(self):
        budget = CostBudget(per_query_limit=1.0, daily_limit=0.001)
        # Record some usage to exhaust budget
        budget.record_usage("claude-sonnet-4-5-20250929", 100_000, 50_000)
        model = budget.check_budget("claude-opus-4-6")
        assert "haiku" in model.lower()

    def test_status_over_budget(self):
        budget = CostBudget(daily_limit=0.001)
        budget.record_usage("claude-sonnet-4-5-20250929", 100_000, 50_000)
        status = budget.get_status()
        assert status.is_over_budget

    def test_downgrade_when_low_budget(self):
        budget = CostBudget(per_query_limit=1.0, daily_limit=1.0)
        # Spend 95% of daily budget (~$0.975)
        budget.record_usage("claude-opus-4-6", 60_000, 500)
        budget.record_usage("claude-opus-4-6", 60_000, 500)
        # Now remaining should be < 10%
        status = budget.get_status()
        if status.remaining_daily < budget.daily_limit * 0.1:
            model = budget.check_budget("claude-opus-4-6")
            assert model != "claude-opus-4-6"
        else:
            # If still above 10%, record more to push below
            budget.record_usage("claude-opus-4-6", 500_000, 5_000)
            model = budget.check_budget("claude-opus-4-6")
            # Either downgraded or budget exhausted → cheapest
            assert "haiku" in model.lower() or model == "claude-sonnet-4-5-20250929"
