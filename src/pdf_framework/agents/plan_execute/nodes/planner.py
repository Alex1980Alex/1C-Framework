"""Planner node for Plan-Execute Agent (Phase 57).

Breaks down complex queries into executable steps using LLM.

Author: Claude Code
Version: 1.0.0 - Phase 57: Agentic RAG Plan-Execute
"""

import logging
import json
from typing import Any

from src.pdf_framework.agents.plan_execute.state import PlanExecuteState, PlanStep

logger = logging.getLogger(__name__)

PLANNER_PROMPT = """You are a planning assistant. Break down the user's query into 2-5 executable steps.

Available tools:
- search: Search document collection (for questions about documents)
- graph_query: Query knowledge graph (for entity/relation questions)
- calculate: Perform calculations (for numerical questions)
- web_search: Search the web (for external information, if enabled)

Return a JSON plan with this structure:
{
  "steps": [
    {
      "step_id": "1",
      "description": "What this step does",
      "tool": "search|graph_query|calculate|web_search",
      "query": "Specific query for this step"
    }
  ]
}

User query: {query}

Think step by step:
1. What information is needed?
2. Which tool can get each piece?
3. What should each query be?

Provide your plan as JSON:"""


def create_plan(llm: Any):
    """Create a planner node function.

    Args:
        llm: LLM for generating plans

    Returns:
        Node function for LangGraph
    """

    async def plan_node(state: PlanExecuteState) -> dict[str, Any]:
        """Generate initial execution plan."""
        logger.info(f"[PLANNER] Creating plan for: {state.query[:50]}...")

        # Generate plan
        response = await llm.ainvoke([
            {"role": "user", "content": PLANNER_PROMPT.format(query=state.query)}
        ])

        # Parse JSON response
        try:
            plan_data = json.loads(response.content)
            steps = []

            for i, step_data in enumerate(plan_data.get("steps", [])):
                step = PlanStep(
                    step_id=step_data.get("step_id", str(i + 1)),
                    description=step_data.get("description", ""),
                    tool=step_data.get("tool", "search"),
                    query=step_data.get("query", ""),
                    status="pending",
                )
                steps.append(step)

            logger.info(f"[PLANNER] Created plan with {len(steps)} steps")

            return {
                "plan": steps,
                "current_step": 0,
                "iterations": 0,
            }

        except json.JSONDecodeError as e:
            logger.error(f"[PLANNER] Failed to parse plan: {e}")
            # Fallback: single search step
            fallback_step = PlanStep(
                step_id="1",
                description="Search for relevant information",
                tool="search",
                query=state.query,
                status="pending",
            )

            return {
                "plan": [fallback_step],
                "current_step": 0,
                "iterations": 0,
            }

    return plan_node
