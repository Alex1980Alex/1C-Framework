"""Unit tests for Plan-Execute Agent (Phase 57)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.pdf_framework.agents.plan_execute.agent import (
    create_plan_execute_agent,
    run_plan_execute,
    should_continue,
)
from src.pdf_framework.agents.plan_execute.nodes.planner import create_plan
from src.pdf_framework.agents.plan_execute.nodes.executor import execute_step
from src.pdf_framework.agents.plan_execute.nodes.replanner import replan
from src.pdf_framework.agents.plan_execute.nodes.synthesizer import synthesize_answer
from src.pdf_framework.agents.plan_execute.state import PlanExecuteState, PlanStep


# ============================================================================
# State & PlanStep Tests
# ============================================================================


@pytest.mark.unit
class TestPlanStep:
    """Tests for PlanStep dataclass."""

    def test_create_plan_step_minimal(self):
        """Should create plan step with minimal fields."""
        step = PlanStep(
            step_id="1",
            description="Search for info",
            tool="search",
            query="test query",
        )
        assert step.step_id == "1"
        assert step.status == "pending"
        assert step.depends_on == []
        assert step.result is None

    def test_create_plan_step_full(self):
        """Should create plan step with all fields."""
        step = PlanStep(
            step_id="2",
            description="Calculate result",
            tool="calculate",
            query="1 + 1",
            depends_on=["1"],
            status="in_progress",
            result=2,
        )
        assert step.step_id == "2"
        assert step.depends_on == ["1"]
        assert step.status == "in_progress"
        assert step.result == 2


@pytest.mark.unit
class TestPlanExecuteState:
    """Tests for PlanExecuteState dataclass."""

    def test_create_state_minimal(self):
        """Should create state with query only."""
        state = PlanExecuteState(query="test query")
        assert state.query == "test query"
        assert state.plan == []
        assert state.current_step == 0
        assert state.iterations == 0
        assert state.max_iterations == 5
        assert state.error == ""

    def test_create_state_with_plan(self):
        """Should create state with pre-populated plan."""
        steps = [
            PlanStep("1", "Step 1", "search", "q1"),
            PlanStep("2", "Step 2", "calculate", "q2"),
        ]
        state = PlanExecuteState(
            query="complex query",
            plan=steps,
            max_iterations=3,
        )
        assert len(state.plan) == 2
        assert state.max_iterations == 3

    def test_state_with_results(self):
        """Should store execution results."""
        state = PlanExecuteState(
            query="test",
            results={"step_1": "result 1", "step_2": "result 2"},
        )
        assert len(state.results) == 2
        assert state.results["step_1"] == "result 1"


# ============================================================================
# should_continue Tests
# ============================================================================


@pytest.mark.unit
class TestShouldContinue:
    """Tests for should_continue routing logic."""

    def test_continue_when_steps_pending(self):
        """Should return 'execute' when steps are pending."""
        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="pending"),
                PlanStep("2", "Step 2", "search", "q2", status="pending"),
            ],
        )
        result = should_continue(state)
        assert result == "execute"

    def test_continue_when_step_in_progress(self):
        """Should return 'execute' when a step is in progress."""
        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="in_progress"),
            ],
        )
        result = should_continue(state)
        assert result == "execute"

    def test_synthesize_when_all_completed(self):
        """Should return 'synthesize' when all steps completed."""
        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="completed"),
                PlanStep("2", "Step 2", "search", "q2", status="completed"),
            ],
        )
        result = should_continue(state)
        assert result == "synthesize"

    def test_synthesize_on_error(self):
        """Should return 'synthesize' when error is set."""
        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="pending"),
            ],
            error="Something went wrong",
        )
        result = should_continue(state)
        assert result == "synthesize"

    def test_synthesize_on_max_iterations(self):
        """Should return 'synthesize' when max iterations reached."""
        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="pending"),
            ],
            iterations=5,
            max_iterations=5,
        )
        result = should_continue(state)
        assert result == "synthesize"


# ============================================================================
# Planner Node Tests
# ============================================================================


@pytest.mark.unit
class TestPlannerNode:
    """Tests for planner node."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM for planning."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content='{"steps": [{"step_id": "1", "description": "Search", "tool": "search", "query": "test"}]}'
        )
        return llm

    @pytest.mark.asyncio
    async def test_create_plan_basic(self, mock_llm):
        """Should create plan from LLM response."""
        planner = create_plan(mock_llm)
        state = PlanExecuteState(query="test query")

        result = await planner(state)

        assert "plan" in result
        assert len(result["plan"]) == 1
        assert result["plan"][0].step_id == "1"
        assert result["plan"][0].tool == "search"
        assert result["plan"][0].status == "pending"

    @pytest.mark.asyncio
    async def test_create_plan_multiple_steps(self, mock_llm):
        """Should create plan with multiple steps."""
        mock_llm.ainvoke.return_value = MagicMock(
            content='''{"steps": [
                {"step_id": "1", "description": "Step 1", "tool": "search", "query": "q1"},
                {"step_id": "2", "description": "Step 2", "tool": "calculate", "query": "q2"}
            ]}'''
        )

        planner = create_plan(mock_llm)
        state = PlanExecuteState(query="complex query")

        result = await planner(state)

        assert len(result["plan"]) == 2
        assert result["plan"][0].tool == "search"
        assert result["plan"][1].tool == "calculate"

    @pytest.mark.asyncio
    async def test_create_plan_json_error_fallback(self, mock_llm):
        """Should fallback to single step on JSON error."""
        mock_llm.ainvoke.return_value = MagicMock(
            content="This is not valid JSON"
        )

        planner = create_plan(mock_llm)
        state = PlanExecuteState(query="test query")

        result = await planner(state)

        # Should create fallback step
        assert len(result["plan"]) == 1
        assert result["plan"][0].tool == "search"
        assert result["plan"][0].query == "test query"

    @pytest.mark.asyncio
    async def test_create_plan_initializes_counters(self, mock_llm):
        """Should initialize current_step and iterations."""
        planner = create_plan(mock_llm)
        state = PlanExecuteState(query="test", iterations=10, current_step=5)

        result = await planner(state)

        assert result["current_step"] == 0
        assert result["iterations"] == 0


# ============================================================================
# Executor Node Tests
# ============================================================================


@pytest.mark.unit
class TestExecutorNode:
    """Tests for executor node."""

    @pytest.fixture
    def mock_search_manager(self):
        """Mock search manager."""
        manager = AsyncMock()
        manager.search = AsyncMock(return_value=MagicMock(
            results=[MagicMock(content="Result 1")],
            answer="Search answer"
        ))
        return manager

    @pytest.fixture
    def mock_tools(self):
        """Mock tools."""
        return {
            "search": AsyncMock(return_value="search result"),
            "graph_query": AsyncMock(return_value="graph result"),
            "calculate": MagicMock(return_value=42),
            "web_search": AsyncMock(return_value="web result"),
        }

    @pytest.mark.asyncio
    async def test_execute_search_step(self, mock_search_manager, mock_tools):
        """Should execute search step."""
        executor = execute_step(mock_search_manager, mock_tools)

        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Search", "search", "search query", status="pending")
            ],
        )

        result = await executor(state)

        assert "plan" in result
        assert result["plan"][0].status == "completed"
        assert result["plan"][0].result is not None

    @pytest.mark.asyncio
    async def test_execute_calculate_step(self, mock_search_manager, mock_tools):
        """Should execute calculate step."""
        executor = execute_step(mock_search_manager, mock_tools)

        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Calc", "calculate", "2 + 2", status="pending")
            ],
        )

        result = await executor(state)

        assert result["plan"][0].status == "completed"
        assert result["plan"][0].result == 4

    @pytest.mark.asyncio
    async def test_execute_graph_query_step(self, mock_search_manager, mock_tools):
        """Should execute graph_query step."""
        executor = execute_step(mock_search_manager, mock_tools)

        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Graph", "graph_query", "entity:Document", status="pending")
            ],
        )

        result = await executor(state)

        assert result["plan"][0].status == "completed"
        mock_tools["graph_query"].assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_skips_completed_steps(self, mock_search_manager, mock_tools):
        """Should skip already completed steps."""
        executor = execute_step(mock_search_manager, mock_tools)

        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Done", "search", "q1", status="completed", result="done"),
                PlanStep("2", "Pending", "search", "q2", status="pending"),
            ],
        )

        result = await executor(state)

        # Should execute step 2, skip step 1
        assert result["plan"][0].status == "completed"  # Already done
        assert result["plan"][1].status == "completed"  # Just executed


# ============================================================================
# Replanner Node Tests
# ============================================================================


@pytest.mark.unit
class TestReplannerNode:
    """Tests for replanner node."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM for replanning."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content='{"action": "continue"}'
        )
        return llm

    @pytest.mark.asyncio
    async def test_replan_continue(self, mock_llm):
        """Should continue when plan is working."""
        replanner = replan(mock_llm)

        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="completed", result="found"),
                PlanStep("2", "Step 2", "search", "q2", status="pending"),
            ],
            iterations=1,
        )

        result = await replanner(state)

        assert "iterations" in result
        assert result["iterations"] >= 1

    @pytest.mark.asyncio
    async def test_replan_adjusts_on_partial_failure(self, mock_llm):
        """Should adjust plan when step fails."""
        mock_llm.ainvoke.return_value = MagicMock(
            content='{"action": "adjust", "new_query": "adjusted query"}'
        )

        replanner = replan(mock_llm)

        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="completed", result="not found"),
                PlanStep("2", "Step 2", "search", "q2", status="pending"),
            ],
        )

        result = await replanner(state)

        # Should increment iterations
        assert result["iterations"] >= 1


# ============================================================================
# Synthesizer Node Tests
# ============================================================================


@pytest.mark.unit
class TestSynthesizerNode:
    """Tests for synthesizer node."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM for synthesis."""
        llm = AsyncMock()
        llm.ainvoke.return_value = MagicMock(
            content="Final synthesized answer based on all steps."
        )
        return llm

    @pytest.mark.asyncio
    async def test_synthesize_answer(self, mock_llm):
        """Should synthesize final answer from step results."""
        synthesizer = synthesize_answer(mock_llm)

        state = PlanExecuteState(
            query="original query",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="completed", result="result 1"),
                PlanStep("2", "Step 2", "search", "q2", status="completed", result="result 2"),
            ],
            results={"1": "result 1", "2": "result 2"},
        )

        result = await synthesizer(state)

        assert "final_answer" in result
        assert "synthesized" in result["final_answer"].lower()

    @pytest.mark.asyncio
    async def test_synthesize_with_error(self, mock_llm):
        """Should handle synthesis when some steps failed."""
        synthesizer = synthesize_answer(mock_llm)

        state = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="completed", result="partial"),
                PlanStep("2", "Step 2", "search", "q2", status="failed", result="error"),
            ],
            error="Step 2 failed",
        )

        result = await synthesizer(state)

        # Should still generate answer
        assert "final_answer" in result


# ============================================================================
# Agent Creation Tests
# ============================================================================


@pytest.mark.unit
class TestAgentCreation:
    """Tests for agent creation and compilation."""

    @pytest.fixture
    def mock_llm(self):
        """Mock LLM."""
        return MagicMock()

    @pytest.fixture
    def mock_search_manager(self):
        """Mock search manager."""
        return AsyncMock()

    @pytest.fixture
    def mock_tools(self):
        """Mock tools."""
        return {
            "search": AsyncMock(),
            "graph_query": AsyncMock(),
        }

    def test_create_plan_execute_agent(self, mock_llm, mock_search_manager, mock_tools):
        """Should create compiled agent."""
        agent = create_plan_execute_agent(
            llm=mock_llm,
            search_manager=mock_search_manager,
            tools=mock_tools,
            max_iterations=5,
        )

        assert agent is not None
        # Compiled agent should have invoke methods
        assert hasattr(agent, "ainvoke")

    def test_create_agent_with_custom_max_iterations(self, mock_llm, mock_search_manager, mock_tools):
        """Should respect custom max_iterations."""
        agent = create_plan_execute_agent(
            llm=mock_llm,
            search_manager=mock_search_manager,
            tools=mock_tools,
            max_iterations=10,
        )

        assert agent is not None


# ============================================================================
# Run Agent Tests
# ============================================================================


@pytest.mark.unit
class TestRunPlanExecute:
    """Tests for run_plan_execute function."""

    @pytest.mark.asyncio
    async def test_run_plan_execute_basic(self):
        """Should run agent and return results."""
        # Create mock agent
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = PlanExecuteState(
            query="test",
            plan=[
                PlanStep("1", "Step 1", "search", "q1", status="completed"),
            ],
            final_answer="Test answer",
            iterations=1,
        )

        mock_search_manager = AsyncMock()

        result = await run_plan_execute(
            query="test query",
            agent=mock_agent,
            search_manager=mock_search_manager,
            max_iterations=5,
        )

        assert result["query"] == "test query"
        assert result["answer"] == "Test answer"
        assert result["steps"] == 1
        assert result["iterations"] == 1

    @pytest.mark.asyncio
    async def test_run_plan_execute_with_error(self):
        """Should handle agent errors."""
        mock_agent = AsyncMock()
        mock_agent.ainvoke.return_value = PlanExecuteState(
            query="test",
            plan=[],
            final_answer="Partial answer",
            error="Step failed",
        )

        mock_search_manager = AsyncMock()

        result = await run_plan_execute(
            query="test query",
            agent=mock_agent,
            search_manager=mock_search_manager,
        )

        assert result["error"] == "Step failed"
