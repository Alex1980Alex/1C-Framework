"""Executor node for Plan-Execute Agent (Phase 57).

Executes individual plan steps using appropriate tools.

Author: Claude Code
Version: 1.0.0 - Phase 57: Agentic RAG Plan-Execute
"""

import logging
from typing import Any

from src.pdf_framework.agents.plan_execute.state import PlanExecuteState, PlanStep

logger = logging.getLogger(__name__)


def execute_step(search_manager: Any, tools: dict[str, Any]):
    """Create an executor node function.

    Args:
        search_manager: Search manager for queries
        tools: Available tools

    Returns:
        Node function for LangGraph
    """

    async def executor_node(state: PlanExecuteState) -> dict[str, Any]:
        """Execute the current step in the plan."""
        # Find next pending step
        current_idx = state.current_step
        plan = state.plan

        if current_idx >= len(plan):
            return {"error": "No more steps to execute"}

        # Find next pending step
        step_to_execute = None
        step_idx = None

        for i in range(current_idx, len(plan)):
            if plan[i].status == "pending":
                # Check dependencies
                deps_met = all(
                    plan[j].status == "completed"
                    for j in range(i)
                    if plan[j].step_id in plan[i].depends_on
                )
                if deps_met:
                    step_to_execute = plan[i]
                    step_idx = i
                    break

        if step_to_execute is None:
            return {"error": "No executable step found (dependencies not met)"}

        logger.info(
            f"[EXECUTOR] Executing step {step_to_execute.step_id}: "
            f"{step_to_execute.description[:50]}"
        )

        # Execute based on tool
        try:
            result = await _execute_tool(
                step_to_execute,
                search_manager,
                tools,
            )

            # Update step status
            updated_plan = plan.copy()
            updated_plan[step_idx] = PlanStep(
                **{**step_to_execute.__dict__, "status": "completed", "result": result}
            )

            # Update results
            updated_results = state.results.copy()
            updated_results[step_to_execute.step_id] = result

            return {
                "plan": updated_plan,
                "current_step": step_idx + 1,
                "results": updated_results,
            }

        except Exception as e:
            logger.error(f"[EXECUTOR] Step failed: {e}")
            updated_plan = plan.copy()
            updated_plan[step_idx] = PlanStep(
                **{**step_to_execute.__dict__, "status": "failed"}
            )

            return {
                "plan": updated_plan,
                "error": str(e),
            }

    return executor_node


async def _execute_tool(
    step: PlanStep,
    search_manager: Any,
    tools: dict[str, Any],
) -> Any:
    """Execute a step using its designated tool.

    Args:
        step: Plan step to execute
        search_manager: Search manager
        tools: Available tools

    Returns:
        Tool execution result
    """
    tool = step.tool
    query = step.query

    if tool == "search":
        response = await search_manager.search(
            query=query,
            strategy="hybrid",
            k=5,
        )
        return {
            "tool": "search",
            "query": query,
            "results": [
                {"content": r.chunk.content, "score": r.score}
                for r in response.results
            ],
        }

    elif tool == "graph_query":
        if "graph_query" not in tools:
            raise ValueError("graph_query tool not available")
        graph_tool = tools["graph_query"]
        result = await graph_tool.ainvoke({"query": query})
        return {
            "tool": "graph_query",
            "query": query,
            "result": result,
        }

    elif tool == "calculate":
        if "calculate" not in tools:
            # Simple eval for basic math
            try:
                result = eval(query, {"__builtins__": {}}, {})
            except Exception as e:
                result = f"Calculation error: {e}"
        else:
            calc_tool = tools["calculate"]
            result = await calc_tool.ainvoke({"expression": query})

        return {
            "tool": "calculate",
            "query": query,
            "result": result,
        }

    elif tool == "web_search":
        if "web_search" not in tools:
            raise ValueError("web_search tool not available")
        web_tool = tools["web_search"]
        result = await web_tool.ainvoke({"query": query})
        return {
            "tool": "web_search",
            "query": query,
            "result": result,
        }

    else:
        raise ValueError(f"Unknown tool: {tool}")
