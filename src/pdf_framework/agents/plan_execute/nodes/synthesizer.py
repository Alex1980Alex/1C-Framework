"""Synthesizer node for Plan-Execute Agent (Phase 57).

Combines results from all steps into a coherent final answer.

Author: Claude Code
Version: 1.0.0 - Phase 57: Agentic RAG Plan-Execute
"""

import logging
from typing import Any

from src.pdf_framework.agents.plan_execute.state import PlanExecuteState

logger = logging.getLogger(__name__)

SYNTHESIZER_PROMPT = """You are a synthesis assistant. Combine the results from multiple steps into a coherent answer.

Original question: {query}

Results from each step:
{results}

Instructions:
- Synthesize a comprehensive answer
- Cite information sources
- If any step failed, note what couldn't be answered
- Be clear and concise

Provide your answer:"""


def synthesize_answer(llm: Any):
    """Create a synthesizer node function.

    Args:
        llm: LLM for synthesis

    Returns:
        Node function for LangGraph
    """

    async def synthesizer_node(state: PlanExecuteState) -> dict[str, Any]:
        """Synthesize final answer from all step results."""
        logger.info("[SYNTHESIZER] Creating final answer")

        # Build results summary
        results_summary = []

        for step in state.plan:
            if step.status == "completed":
                result = state.results.get(step.step_id)
                if result and isinstance(result, dict):
                    content = result.get("result", result.get("results", []))

                    if isinstance(content, list):
                        snippet = ", ".join([
                            r.get("content", str(r))[:50]
                            for r in content[:3]
                        ])
                    else:
                        snippet = str(content)[:200]

                    results_summary.append(
                        f"Step {step.step_id} ({step.tool}): {snippet}"
                    )
                else:
                    results_summary.append(
                        f"Step {step.step_id}: {str(result)[:200] if result else 'No result'}"
                    )

            elif step.status == "failed":
                results_summary.append(
                    f"Step {step.step_id}: FAILED - {step.description}"
                )

        results_text = "\n\n".join(results_summary) if results_summary else "No results"

        # Handle error case
        if state.error:
            error_msg = f"An error occurred: {state.error}"
            if results_text:
                final_prompt = f"{SYNTHESIZER_PROMPT.format(query=state.query, results=results_text)}\n\nNote: {error_msg}"
            else:
                return {"final_answer": f"I encountered an error: {error_msg}"}
        else:
            final_prompt = SYNTHESIZER_PROMPT.format(
                query=state.query,
                results=results_text,
            )

        # Generate final answer
        response = await llm.ainvoke([
            {"role": "user", "content": final_prompt}
        ])

        final_answer = response.content

        logger.info(f"[SYNTHESIZER] Final answer: {len(final_answer)} chars")

        return {
            "final_answer": final_answer,
        }

    return synthesizer_node
