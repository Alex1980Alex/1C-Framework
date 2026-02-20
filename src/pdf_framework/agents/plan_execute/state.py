"""Plan-Execute Agent State (Phase 57).

State management for plan-execute pattern where complex queries
are broken down into steps and executed sequentially.

Author: Claude Code
Version: 1.0.0 - Phase 57: Agentic RAG Plan-Execute
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PlanStep:
    """A single step in the execution plan.

    Attributes:
        step_id: Unique step identifier
        description: Human-readable step description
        tool: Tool to use for this step
        query: Query/question for this step
        depends_on: List of step IDs this step depends on
        status: Step status (pending/in_progress/completed/failed)
        result: Result from executing this step
    """
    step_id: str
    description: str
    tool: str
    query: str
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None


@dataclass
class PlanExecuteState:
    """State for Plan-Execute agent workflow.

    Attributes:
        query: Original user query
        plan: List of planned steps
        current_step: Index of current step
        results: Collected results from each step
        final_answer: Synthesized final answer
        iterations: Number of iterations (replanning cycles)
        max_iterations: Maximum allowed iterations
        error: Error message if failed
    """
    query: str
    plan: list[PlanStep] = field(default_factory=list)
    current_step: int = 0
    results: dict[str, Any] = field(default_factory=dict)
    final_answer: str = ""
    iterations: int = 0
    max_iterations: int = 5
    error: str = ""
