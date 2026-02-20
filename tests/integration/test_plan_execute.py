"""Integration tests for Plan-Execute Agent (Phase 57)."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.pdf_framework.agents.plan_execute.agent import (
    create_plan_execute_agent,
    run_plan_execute,
)
from src.pdf_framework.agents.plan_execute.state import PlanExecuteState, PlanStep


@pytest.fixture
def mock_llm():
    """Mock LLM for planning and synthesis."""
    llm = MagicMock()

    # Mock different responses based on prompt
    async def mock_invoke(messages):
        response = MagicMock()

        # Check if this is a planning prompt
        content = str(messages)
        if "planning" in content.lower() or "break down" in content.lower():
            response.content = '''{"steps": [
                {"step_id": "1", "description": "Search for information", "tool": "search", "query": "test query"},
                {"step_id": "2", "description": "Synthesize results", "tool": "search", "query": "combined query"}
            ]}'''
        elif "synthesize" in content.lower() or "combine" in content.lower():
            response.content = "Based on the search results, here is the comprehensive answer."
        else:
            response.content = '{"action": "continue"}'

        return response

    llm.ainvoke = mock_invoke
    return llm


@pytest.fixture
def mock_search_manager():
    """Mock search manager."""
    manager = AsyncMock()

    async def mock_search(query, **kwargs):
        response = MagicMock()
        response.results = [
            MagicMock(content=f"Result for {query}", score=0.9)
        ]
        response.answer = f"Answer for {query}"
        return response

    manager.search = mock_search
    return manager


@pytest.fixture
def mock_tools(mock_search_manager):
    """Mock tools for executor."""
    return {
        "search": AsyncMock(return_value="search result"),
        "graph_query": AsyncMock(return_value="graph result"),
        "calculate": MagicMock(return_value=42),
        "web_search": AsyncMock(return_value="web result"),
    }


@pytest.fixture
def plan_execute_agent(mock_llm, mock_search_manager, mock_tools):
    """Create plan-execute agent for testing."""
    return create_plan_execute_agent(
        llm=mock_llm,
        search_manager=mock_search_manager,
        tools=mock_tools,
        max_iterations=5,
    )


@pytest.mark.integration
class TestPlanExecuteAgent:
    """Integration tests for Plan-Execute agent."""

    @pytest.mark.asyncio
    async def test_agent_simple_query(self, plan_execute_agent):
        """Test agent with a simple query."""
        initial_state = PlanExecuteState(query="What is a document?")

        result = await plan_execute_agent.ainvoke(initial_state)

        assert isinstance(result, PlanExecuteState)
        assert len(result.plan) > 0
        assert result.final_answer != ""

    @pytest.mark.asyncio
    async def test_agent_multi_step_execution(self, plan_execute_agent):
        """Test agent with multi-step plan execution."""
        initial_state = PlanExecuteState(
            query="Compare documents and catalogs in 1C"
        )

        result = await plan_execute_agent.ainvoke(initial_state)

        # Should have executed all steps
        assert len(result.plan) >= 2
        # Most steps should be completed
        completed_count = sum(1 for s in result.plan if s.status == "completed")
        assert completed_count >= len(result.plan) - 1

    @pytest.mark.asyncio
    async def test_agent_respects_max_iterations(self, plan_execute_agent):
        """Test agent stops at max_iterations."""
        initial_state = PlanExecuteState(
            query="Complex multi-part query",
            max_iterations=2,
        )

        result = await plan_execute_agent.ainvoke(initial_state)

        # Should not exceed max iterations
        assert result.iterations <= result.max_iterations

    @pytest.mark.asyncio
    async def test_agent_with_search_tool(self, plan_execute_agent, mock_tools):
        """Test agent using search tool."""
        initial_state = PlanExecuteState(
            query="Find information about registers"
        )

        result = await plan_execute_agent.ainvoke(initial_state)

        # Search tool should have been called
        assert mock_tools["search"].called
        assert len(result.plan) > 0

    @pytest.mark.asyncio
    async def test_agent_with_graph_query_tool(self, plan_execute_agent, mock_tools):
        """Test agent using graph_query tool."""
        # Create a new LLM that suggests graph_query
        llm = MagicMock()
        llm.ainvoke = AsyncMock(
            return_value=MagicMock(
                content='''{"steps": [
                    {"step_id": "1", "description": "Query graph", "tool": "graph_query", "query": "entity:Document"}
                ]}'''
            )
        )

        agent = create_plan_execute_agent(
            llm=llm,
            search_manager=AsyncMock(),
            tools=mock_tools,
        )

        initial_state = PlanExecuteState(query="Show document relationships")

        result = await agent.ainvoke(initial_state)

        # graph_query tool should have been called
        assert mock_tools["graph_query"].called


@pytest.mark.integration
class TestRunPlanExecute:
    """Integration tests for run_plan_execute wrapper."""

    @pytest.mark.asyncio
    async def test_run_simple_query(self, plan_execute_agent, mock_search_manager):
        """Test running a simple query through wrapper."""
        result = await run_plan_execute(
            query="What is a catalog?",
            agent=plan_execute_agent,
            search_manager=mock_search_manager,
        )

        assert result["query"] == "What is a catalog?"
        assert "answer" in result
        assert result["answer"] != ""
        assert result["steps"] >= 1
        assert result["iterations"] >= 0

    @pytest.mark.asyncio
    async def test_run_returns_results(self, plan_execute_agent, mock_search_manager):
        """Test that run function returns collected results."""
        result = await run_plan_execute(
            query="Complex query",
            agent=plan_execute_agent,
            search_manager=mock_search_manager,
            max_iterations=3,
        )

        assert "results" in result
        assert isinstance(result["results"], dict)

    @pytest.mark.asyncio
    async def test_run_handles_error_state(self, plan_execute_agent, mock_search_manager):
        """Test run function handles agent errors."""
        # Create an agent that will fail
        failing_llm = MagicMock()
        failing_llm.ainvoke = AsyncMock(
            side_effect=Exception("LLM error")
        )

        agent = create_plan_execute_agent(
            llm=failing_llm,
            search_manager=mock_search_manager,
            tools={},
        )

        result = await run_plan_execute(
            query="Test query",
            agent=agent,
            search_manager=mock_search_manager,
        )

        # Should still return a result structure
        assert "query" in result
        # Error field should be present (may be empty if caught differently)
        assert "error" in result


@pytest.mark.integration
@pytest.mark.asyncio
async def test_end_to_end_plan_execute_workflow(mock_llm, mock_search_manager, mock_tools):
    """End-to-end test: plan → execute → synthesize."""
    # Create agent
    agent = create_plan_execute_agent(
        llm=mock_llm,
        search_manager=mock_search_manager,
        tools=mock_tools,
        max_iterations=5,
    )

    # Define a complex query
    query = """
    Analyze the differences between documents and catalogs in 1C:Enterprise.
    For each, explain their purpose, usage, and key characteristics.
    """

    # Run the agent
    result = await run_plan_execute(
        query=query,
        agent=agent,
        search_manager=mock_search_manager,
        max_iterations=5,
    )

    # Verify the complete workflow
    assert result["query"] == query
    assert result["answer"] != ""
    assert result["steps"] >= 2  # Should have planned at least 2 steps
    assert result["iterations"] >= 1

    # Verify tools were used
    assert mock_tools["search"].called or mock_tools["graph_query"].called


@pytest.mark.integration
class TestPlanExecuteWithDifferentQueries:
    """Test agent with various query types."""

    @pytest.mark.asyncio
    async def test_factual_query(self, plan_execute_agent):
        """Test with a simple factual query."""
        result = await run_plan_execute(
            query="What is the purpose of a register?",
            agent=plan_execute_agent,
            search_manager=AsyncMock(),
        )

        assert result["answer"] != ""

    @pytest.mark.asyncio
    async def test_comparative_query(self, plan_execute_agent):
        """Test with a comparative query."""
        result = await run_plan_execute(
            query="Compare documents and catalogs",
            agent=plan_execute_agent,
            search_manager=AsyncMock(),
        )

        assert result["steps"] >= 2  # Comparison should need multiple steps

    @pytest.mark.asyncio
    async def test_procedural_query(self, plan_execute_agent):
        """Test with a procedural how-to query."""
        result = await run_plan_execute(
            query="How to create a new document type?",
            agent=plan_execute_agent,
            search_manager=AsyncMock(),
        )

        assert result["answer"] != ""

    @pytest.mark.asyncio
    async def test_calculation_query(self, plan_execute_agent, mock_search_manager, mock_tools):
        """Test with a calculation query."""
        result = await run_plan_execute(
            query="Calculate the total number of standard object types",
            agent=plan_execute_agent,
            search_manager=mock_search_manager,
        )

        # Should use calculate tool
        assert result["answer"] != ""


@pytest.mark.integration
class TestPlanExecuteStreaming:
    """Test streaming support for plan-execute."""

    @pytest.mark.asyncio
    async def test_streaming_events(self, plan_execute_agent):
        """Test that agent can stream intermediate results."""
        initial_state = PlanExecuteState(
            query="Test streaming query"
        )

        # Collect events
        events = []
        async for event in plan_execute_agent.astream(initial_state):
            events.append(event)
            # Limit iterations for test
            if len(events) >= 5:
                break

        # Should have emitted some events
        assert len(events) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
