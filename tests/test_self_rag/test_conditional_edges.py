"""Unit tests for Self-RAG conditional edge functions.

Tests should_rewrite_or_generate and should_regenerate_or_end logic
without requiring LLM or SearchManager.
"""

import pytest

from src.pdf_framework.config import SelfRAGSettings


def _make_agent_edge_functions(self_rag_settings: SelfRAGSettings):
    """Create edge functions with the given settings.

    Mirrors the closure logic in create_rag_agent without building the full graph.
    """

    def should_rewrite_or_generate(state: dict) -> str:
        if not self_rag_settings.enabled:
            if state.get("needs_more_context") and state.get("search_strategy") != "hybrid":
                return "retry"
            return "generate"

        retry_count = state.get("retry_count", 0)
        max_retries = state.get("max_retries", self_rag_settings.max_retries)
        relevance_ratio = state.get("relevance_ratio", 0.0)

        if relevance_ratio < self_rag_settings.relevance_threshold and retry_count < max_retries:
            return "rewrite"
        return "generate"

    def should_regenerate_or_end(state: dict) -> str:
        if not self_rag_settings.enabled or not self_rag_settings.hallucination_check_enabled:
            return "end"

        is_hallucinated = state.get("is_hallucinated", False)
        attempts = state.get("generation_attempts", 0)
        max_attempts = self_rag_settings.max_generation_attempts

        if is_hallucinated and attempts < max_attempts:
            return "regenerate"
        return "end"

    return should_rewrite_or_generate, should_regenerate_or_end


# ============================================================
# should_rewrite_or_generate
# ============================================================


class TestShouldRewriteOrGenerate:
    """Tests for the grade → rewrite/generate conditional edge."""

    def setup_method(self):
        self.settings = SelfRAGSettings(enabled=True, relevance_threshold=0.5, max_retries=2)
        self.rewrite_or_gen, _ = _make_agent_edge_functions(self.settings)

    def test_high_relevance_generates(self):
        """Above threshold → generate."""
        state = {"relevance_ratio": 0.8, "retry_count": 0}
        assert self.rewrite_or_gen(state) == "generate"

    def test_exact_threshold_generates(self):
        """At threshold → generate (not strictly less than)."""
        state = {"relevance_ratio": 0.5, "retry_count": 0}
        assert self.rewrite_or_gen(state) == "generate"

    def test_low_relevance_rewrites(self):
        """Below threshold with retries left → rewrite."""
        state = {"relevance_ratio": 0.2, "retry_count": 0}
        assert self.rewrite_or_gen(state) == "rewrite"

    def test_low_relevance_max_retries_generates(self):
        """Below threshold but no retries left → generate anyway."""
        state = {"relevance_ratio": 0.2, "retry_count": 2}
        assert self.rewrite_or_gen(state) == "generate"

    def test_zero_relevance_first_retry(self):
        """Zero relevance on first try → rewrite."""
        state = {"relevance_ratio": 0.0, "retry_count": 0}
        assert self.rewrite_or_gen(state) == "rewrite"

    def test_zero_relevance_last_retry(self):
        """Zero relevance but retries exhausted → generate."""
        state = {"relevance_ratio": 0.0, "retry_count": 2}
        assert self.rewrite_or_gen(state) == "generate"

    def test_missing_fields_defaults(self):
        """Missing state fields should use safe defaults."""
        state = {}
        # relevance_ratio defaults to 0.0, retry_count to 0
        # 0.0 < 0.5 and 0 < 2 → rewrite
        assert self.rewrite_or_gen(state) == "rewrite"

    def test_custom_max_retries_in_state(self):
        """State-level max_retries overrides settings."""
        state = {"relevance_ratio": 0.2, "retry_count": 1, "max_retries": 1}
        assert self.rewrite_or_gen(state) == "generate"

    def test_high_threshold_setting(self):
        """Higher threshold means more rewrites."""
        settings = SelfRAGSettings(enabled=True, relevance_threshold=0.9, max_retries=3)
        rewrite_or_gen, _ = _make_agent_edge_functions(settings)
        state = {"relevance_ratio": 0.85, "retry_count": 0}
        assert rewrite_or_gen(state) == "rewrite"


class TestShouldRewriteOrGenerateLegacy:
    """Tests for legacy (Self-RAG disabled) edge behavior."""

    def setup_method(self):
        self.settings = SelfRAGSettings(enabled=False)
        self.rewrite_or_gen, _ = _make_agent_edge_functions(self.settings)

    def test_legacy_needs_context_retries(self):
        state = {"needs_more_context": True, "search_strategy": "vector"}
        assert self.rewrite_or_gen(state) == "retry"

    def test_legacy_hybrid_no_retry(self):
        """Already at hybrid → don't retry."""
        state = {"needs_more_context": True, "search_strategy": "hybrid"}
        assert self.rewrite_or_gen(state) == "generate"

    def test_legacy_no_need_for_context(self):
        state = {"needs_more_context": False, "search_strategy": "vector"}
        assert self.rewrite_or_gen(state) == "generate"

    def test_legacy_missing_fields(self):
        state = {}
        assert self.rewrite_or_gen(state) == "generate"


# ============================================================
# should_regenerate_or_end
# ============================================================


class TestShouldRegenerateOrEnd:
    """Tests for the hallucination_check → regenerate/end conditional edge."""

    def setup_method(self):
        self.settings = SelfRAGSettings(
            enabled=True,
            hallucination_check_enabled=True,
            max_generation_attempts=2,
        )
        _, self.regen_or_end = _make_agent_edge_functions(self.settings)

    def test_grounded_ends(self):
        state = {"is_hallucinated": False, "generation_attempts": 0}
        assert self.regen_or_end(state) == "end"

    def test_hallucinated_regenerates(self):
        state = {"is_hallucinated": True, "generation_attempts": 0}
        assert self.regen_or_end(state) == "regenerate"

    def test_hallucinated_max_attempts_ends(self):
        """Exhausted attempts → end even if hallucinated."""
        state = {"is_hallucinated": True, "generation_attempts": 2}
        assert self.regen_or_end(state) == "end"

    def test_hallucinated_one_attempt_left(self):
        state = {"is_hallucinated": True, "generation_attempts": 1}
        assert self.regen_or_end(state) == "regenerate"

    def test_missing_fields_defaults_to_end(self):
        """Missing hallucination fields → defaults to not hallucinated → end."""
        state = {}
        assert self.regen_or_end(state) == "end"

    def test_disabled_self_rag_always_ends(self):
        settings = SelfRAGSettings(enabled=False)
        _, regen_or_end = _make_agent_edge_functions(settings)
        state = {"is_hallucinated": True, "generation_attempts": 0}
        assert regen_or_end(state) == "end"

    def test_disabled_hallucination_check_always_ends(self):
        settings = SelfRAGSettings(enabled=True, hallucination_check_enabled=False)
        _, regen_or_end = _make_agent_edge_functions(settings)
        state = {"is_hallucinated": True, "generation_attempts": 0}
        assert regen_or_end(state) == "end"
