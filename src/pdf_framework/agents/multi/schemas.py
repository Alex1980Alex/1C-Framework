"""Schemas for Multi-Agent Orchestration (Phase 39)."""

from typing import Any, TypedDict

from pydantic import BaseModel, Field


class AgentMessage(BaseModel):
    """Message passed between agents."""

    from_agent: str
    to_agent: str
    content: str
    data: dict[str, Any] = Field(default_factory=dict)


class RetrievalResult(BaseModel):
    """Output from the Retrieval Agent."""

    chunks: list[dict[str, Any]] = Field(default_factory=list)
    strategies_used: list[str] = Field(default_factory=list)
    total_found: int = 0


class AnalysisResult(BaseModel):
    """Output from the Analysis Agent."""

    findings: list[str] = Field(default_factory=list)
    comparison_table: str = ""  # markdown
    contradictions: list[str] = Field(default_factory=list)
    conclusions: list[str] = Field(default_factory=list)


class WritingResult(BaseModel):
    """Output from the Writing Agent."""

    report: str = ""
    sections: list[dict[str, str]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    """Output from the Verification Agent."""

    passed: bool = False
    issues: list[str] = Field(default_factory=list)
    corrections: list[str] = Field(default_factory=list)
    groundedness: float = 0.0
    completeness: float = 0.0


class OrchestratorState(TypedDict, total=False):
    """State for the Multi-Agent Orchestrator graph."""

    # Input
    question: str

    # Agent outputs
    retrieval: dict[str, Any]
    analysis: dict[str, Any]
    draft: dict[str, Any]
    verification: dict[str, Any]

    # Final output
    answer: str
    report: dict[str, Any]
    messages: list[dict[str, Any]]  # communication log

    # Control
    phase: str  # retrieve | analyze | write | verify | done
    iteration: int
    max_iterations: int
    error: str
