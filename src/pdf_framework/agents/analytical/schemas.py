"""Schemas for the Analytical RAG Agent (Phase 33).

Defines the state machine, evidence structures, and structured output formats.
"""

from typing import Any, TypedDict

from pydantic import BaseModel, Field

from src.pdf_framework.schemas.documents import SearchResponse


# ---- Evidence & Analysis Models ----


class Evidence(BaseModel):
    """A single piece of evidence collected during analysis."""

    fact: str
    source: str = ""  # e.g. "Chapter 5, p.170"
    section: str = ""  # e.g. "5.14.3. Registers"
    chunk_id: str = ""
    relevance: float = 0.0  # 0-1, how relevant to the question
    aspect: str = ""  # Which aspect of the question this addresses


class ComparisonRow(BaseModel):
    """A single row in a comparison table."""

    criterion: str  # e.g. "Purpose", "Data types", "Movement types"
    values: dict[str, str] = Field(default_factory=dict)  # {entity: description}


class ComparisonTable(BaseModel):
    """Structured comparison between entities/concepts."""

    entities: list[str] = Field(default_factory=list)  # Columns
    rows: list[ComparisonRow] = Field(default_factory=list)  # Criteria rows

    def to_markdown(self) -> str:
        """Render as markdown table."""
        if not self.entities or not self.rows:
            return ""
        header = "| Критерий | " + " | ".join(self.entities) + " |"
        sep = "|" + "|".join(["---"] * (len(self.entities) + 1)) + "|"
        lines = [header, sep]
        for row in self.rows:
            cells = [row.values.get(e, "-") for e in self.entities]
            lines.append(f"| {row.criterion} | " + " | ".join(cells) + " |")
        return "\n".join(lines)


class AnalysisPlan(BaseModel):
    """Plan produced by the Analytical Planner."""

    question_type: str = "factual"  # factual | comparative | analytical | overview
    aspects: list[str] = Field(default_factory=list)  # What aspects to investigate
    search_queries: list[str] = Field(default_factory=list)  # Queries to execute
    entities_to_compare: list[str] = Field(default_factory=list)  # For comparative


class StructuredAnswer(BaseModel):
    """Final structured output from the Analytical Agent."""

    summary: str = ""  # 2-3 sentence summary
    detailed_analysis: str = ""  # Full analysis text
    comparison_table: ComparisonTable | None = None  # For comparative questions
    evidence: list[Evidence] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    coverage: float = 0.0  # 0-1, how many aspects were covered
    rounds_used: int = 0


# ---- LangGraph State ----


class AnalyticalState(TypedDict, total=False):
    """State for the Analytical RAG agent graph."""

    # Input
    question: str
    search_strategy: str

    # Planning
    plan: dict[str, Any]  # AnalysisPlan as dict

    # Evidence collection
    evidence: list[dict[str, Any]]  # List of Evidence as dicts
    search_responses: list[dict[str, Any]]  # SearchResponses from each round

    # Analysis
    comparison_table: dict[str, Any] | None  # ComparisonTable as dict
    analysis_text: str
    coverage: float  # 0-1

    # Output
    answer: str
    structured_answer: dict[str, Any]  # StructuredAnswer as dict
    sources: list[str]

    # Control flow
    round: int
    max_rounds: int
    uncovered_aspects: list[str]
    error: str
