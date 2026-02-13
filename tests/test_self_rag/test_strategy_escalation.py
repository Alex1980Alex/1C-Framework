"""Unit tests for strategy escalation logic in Query Rewriter."""

from src.pdf_framework.agents.rag.nodes.rewriter import STRATEGY_ESCALATION


class TestStrategyEscalation:
    """Tests for the STRATEGY_ESCALATION mapping."""

    def test_vector_escalates_to_hybrid(self):
        assert STRATEGY_ESCALATION["vector"] == "hybrid"

    def test_hybrid_escalates_to_mmr(self):
        assert STRATEGY_ESCALATION["hybrid"] == "mmr"

    def test_mmr_stays_at_mmr(self):
        """Max level — no further escalation."""
        assert STRATEGY_ESCALATION["mmr"] == "mmr"

    def test_graph_escalates_to_hybrid(self):
        assert STRATEGY_ESCALATION["graph"] == "hybrid"

    def test_two_stage_stays_at_two_stage(self):
        """two_stage stays at two_stage if registered."""
        assert STRATEGY_ESCALATION["two_stage"] == "two_stage"

    def test_all_strategies_have_escalation(self):
        """Every registered strategy should have an escalation target."""
        expected_strategies = {"vector", "hybrid", "two_stage", "mmr", "graph"}
        assert set(STRATEGY_ESCALATION.keys()) == expected_strategies

    def test_escalation_chain_terminates(self):
        """Following escalation chain always terminates at a fixed point."""
        for start in STRATEGY_ESCALATION:
            current = start
            seen = set()
            while current != STRATEGY_ESCALATION[current]:
                assert current not in seen, f"Infinite loop from {start}"
                seen.add(current)
                current = STRATEGY_ESCALATION[current]
            # Must terminate at either mmr or two_stage (self-loops)
            assert current in {"mmr", "two_stage"}
