"""Replanner node for Plan-Execute Agent (Phase 57).

Adjusts the execution plan based on results from completed steps.

Author: Claude Code
Version: 1.0.0 - Phase 57: Agentic RAG Plan-Execute
"""

import logging
import json
from typing import Any

from src.pdf_framework.agents.plan_execute.state import PlanExecuteState, PlanStep

logger = logging.getLogger(__name__)

REPLANNER_PROMPT = """You are a replanner. Review the execution status and adjust if needed.

Original query: {query}

Current plan status:
{plan_status}

Recent results:
{recent_results}

Instructions:
- If all steps completed successfully, respond with {{"continue": "complete"}}
- If a step failed but information was gathered, respond with {{"continue": "complete"}}
- If critical information is missing, respond with {{"continue": "replan", "new_steps": [...]}}
- new_steps should follow the same format as the original plan

Provide your decision as JSON:"""


def replan(llm: Any):
    """Create a replanner node function.

    Args:
        llm: LLM for replanning decisions

    Returns:
        Node function for LangGraph
    """

    async def replanner_node(state: PlanExecuteState) -> dict[str, Any]:
        """Evaluate results and decide whether to continue or replan."""
        logger.info(f"[REPLANNER] Evaluating plan (iteration {state.iterations})")

        # Build status summary
        plan_status = "\n".join([
            f"- {s.step_id}: {s.status} - {s.description}"
            for s in state.plan
        ])

        # Get recent results
        recent_results = []
        for step_id, result in state.results.items():
            if isinstance(result, dict) and "results" in result:
                recent_results.append(
                    f"{step_id}: {len(result['results'])} results found"
                )
            else:
                recent_results.append(f"{step_id}: {str(result)[:100]}")

        results_str = "\n".join(recent_results) if recent_results else "No results yet"

        # Get replanning decision
        response = await llm.ainvoke([
            {"role": "user", "content": REPLANNER_PROMPT.format(
                query=state.query,
                plan_status=plan_status,
                recent_results=results_str,
            )}
        ])

        try:
            decision = json.loads(response.content)

            if decision.get("continue") == "complete":
                logger.info("[REPLANNER] Plan complete, proceeding to synthesis")
                return {}

            elif decision.get("continue") == "replan":
                new_steps_data = decision.get("new_steps", [])
                new_steps = []

                for i, step_data in enumerate(new_steps_data):
                    new_steps.append(PlanStep(
                        step_id=f"new_{state.iterations}_{i}",
                        description=step_data.get("description", ""),
                        tool=step_data.get("tool", "search"),
                        query=step_data.get("query", ""),
                        status="pending",
                    ))

                logger.info(f"[REPLANNER] Added {len(new_steps)} new steps")
                updated_plan = state.plan + new_steps

                return {
                    "plan": updated_plan,
                    "iterations": state.iterations + 1,
                }

        except json.JSONDecodeError:
            logger.warning("[REPLANNER] Failed to parse decision, continuing")

        # Default: increment iteration and continue
        return {
            "iterations": state.iterations + 1,
        }

    return replanner_node
