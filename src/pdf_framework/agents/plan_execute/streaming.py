"""Streaming support for Plan-Execute Agent (Phase 57).

SSE streaming for plan steps, intermediate results, and final answer.

Author: Claude Code
Version: 1.0.0 - Phase 57: Agentic RAG Plan-Execute
"""

import json
import logging
from typing import Any, AsyncGenerator

from src.pdf_framework.agents.plan_execute.state import PlanExecuteState

logger = logging.getLogger(__name__)


async def stream_plan_execute(
    query: str,
    agent: Any,
) -> AsyncGenerator[dict[str, Any], None]:
    """Stream plan-execute execution with SSE events.

    Args:
        query: User query
        agent: Plan-execute agent

    Yields:
        Event dictionaries with type and data
    """
    initial_state = PlanExecuteState(query=query)

    yield {
        "type": "plan_start",
        "data": {"query": query},
    }

    # Run agent with streaming
    async for event in agent.astream(initial_state):
        event_type = event.get("__event__", "unknown")

        if event_type == "on_plan":
            yield {
                "type": "plan_created",
                "data": {
                    "steps": [
                        {
                            "id": s.step_id,
                            "description": s.description,
                            "tool": s.tool,
                        }
                        for s in event.get("plan", [])
                    ],
                },
            }

        elif event_type == "on_step":
            yield {
                "type": "step_executed",
                "data": {
                    "step_id": event.get("step_id"),
                    "status": event.get("status"),
                    "result": event.get("result"),
                },
            }

        elif event_type == "on_complete":
            yield {
                "type": "answer_ready",
                "data": {
                    "answer": event.get("final_answer", ""),
                    "steps_completed": event.get("iterations", 0),
                },
            }

    yield {
        "type": "done",
        "data": {},
    }


def format_sse(event: dict[str, Any]) -> str:
    """Format event as Server-Sent Event.

    Args:
        event: Event dictionary

    Returns:
        SSE formatted string
    """
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
