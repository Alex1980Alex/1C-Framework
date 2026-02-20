"""Plan-Execute Agent (Phase 57).

Implements the plan-execute pattern for complex queries:
1. Planner breaks query into steps
2. Executor performs each step with appropriate tool
3. Replanner adjusts plan based on results
4. Synthesizer combines results into final answer

Author: Claude Code
Version: 1.0.0 - Phase 57: Agentic RAG Plan-Execute
"""

import logging
from typing import Any, Literal

from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

from src.pdf_framework.agents.plan_execute.nodes.executor import execute_step
from src.pdf_framework.agents.plan_execute.nodes.planner import create_plan
from src.pdf_framework.agents.plan_execute.nodes.replanner import replan
from src.pdf_framework.agents.plan_execute.nodes.synthesizer import synthesize_answer
from src.pdf_framework.agents.plan_execute.state import PlanExecuteState

logger = logging.getLogger(__name__)


def should_continue(state: PlanExecuteState) -> Literal["execute", "synthesize", END]:
    """Decide next action based on current state.

    Args:
        state: Current agent state

    Returns:
        Next node name or END
    """
    # Check for errors
    if state.error:
        return "synthesize"

    # Check if all steps completed
    all_done = all(step.status == "completed" for step in state.plan)
    if all_done:
        return "synthesize"

    # Check iteration limit
    if state.iterations >= state.max_iterations:
        logger.warning(f"[PLAN_EXECUTE] Max iterations ({state.max_iterations}) reached")
        return "synthesize"

    # Continue executing
    return "execute"


def create_plan_execute_agent(
    llm: ChatAnthropic,
    search_manager: Any,
    tools: dict[str, Any],
    max_iterations: int = 5,
) -> Any:
    """Create a Plan-Execute agent using LangGraph.

    Args:
        llm: LLM for planning and synthesis
        search_manager: Search manager for queries
        tools: Available tools (search, graph_query, calculate, web_search)
        max_iterations: Maximum replanning iterations

    Returns:
        Compiled LangGraph agent

    Example:
        >>> agent = create_plan_execute_agent(llm, search_manager, tools)
        >>> result = await agent.ainvoke({"query": "Compare X and Y"})
    """
    # Create the graph
    workflow = StateGraph(PlanExecuteState)

    # Add nodes
    workflow.add_node("planner", create_plan(llm))
    workflow.add_node("executor", execute_step(search_manager, tools))
    workflow.add_node("replanner", replan(llm))
    workflow.add_node("synthesizer", synthesize_answer(llm))

    # Set entry point
    workflow.set_entry_point("planner")

    # Add edges
    workflow.add_edge("planner", "execute")
    workflow.add_edge("execute", "replanner")
    workflow.add_conditional_edges(
        "replanner",
        should_continue,
        {
            "execute": "execute",
            "synthesize": "synthesizer",
            END: END,
        },
    )
    workflow.add_edge("synthesizer", END)

    # Compile with checkpointer if needed
    app = workflow.compile()

    logger.info("[PLAN_EXECUTE] Agent created with tools: %s", list(tools.keys()))

    return app


async def run_plan_execute(
    query: str,
    agent: Any,
    search_manager: Any,
    max_iterations: int = 5,
) -> dict[str, Any]:
    """Run plan-execute agent on a query.

    Args:
        query: User query
        agent: Plan-execute agent
        search_manager: Search manager
        max_iterations: Max replanning iterations

    Returns:
        Result dictionary with answer and metadata
    """
    initial_state = PlanExecuteState(
        query=query,
        max_iterations=max_iterations,
    )

    result = await agent.ainvoke(initial_state)

    return {
        "query": query,
        "answer": result.final_answer,
        "steps": len(result.plan),
        "iterations": result.iterations,
        "results": result.results,
        "error": result.error,
    }
