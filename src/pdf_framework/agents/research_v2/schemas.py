"""Schemas for Research Agent v2 (Phase 36).

Defines: research plan tree, evidence graph, quality gates,
session memory, and structured report models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, TypedDict

from pydantic import BaseModel, Field


# ---- Research Plan Tree ----


class ResearchTask(BaseModel):
    """A single task in the research plan DAG."""

    id: str  # e.g. "1", "1.1", "2"
    question: str
    strategy: str = "hybrid"  # search strategy
    parent_id: str | None = None  # dependency
    priority: int = 1  # 1=high, 3=low
    status: str = "pending"  # pending | in_progress | done | skipped


class ResearchPlanTree(BaseModel):
    """Dependency-aware research plan (DAG)."""

    original_question: str
    complexity: str = "moderate"  # simple | moderate | complex
    tasks: list[ResearchTask] = Field(default_factory=list)

    def get_ready_tasks(self) -> list[ResearchTask]:
        """Return tasks whose dependencies are satisfied."""
        done_ids = {t.id for t in self.tasks if t.status == "done"}
        return [
            t for t in self.tasks
            if t.status == "pending"
            and (t.parent_id is None or t.parent_id in done_ids)
        ]

    def mark_done(self, task_id: str) -> None:
        for t in self.tasks:
            if t.id == task_id:
                t.status = "done"
                break

    @property
    def progress(self) -> float:
        if not self.tasks:
            return 1.0
        done = sum(1 for t in self.tasks if t.status in ("done", "skipped"))
        return done / len(self.tasks)


# ---- Evidence Graph ----


class EvidenceFact(BaseModel):
    """A fact node in the evidence graph."""

    id: str  # auto-generated
    fact: str
    source: str = ""
    section: str = ""
    chunk_id: str = ""
    confidence: float = 0.8  # 0-1
    aspect: str = ""
    task_id: str = ""  # which research task produced this


class EvidenceRelation(BaseModel):
    """Relationship between two facts."""

    source_id: str
    target_id: str
    relation_type: str  # supports | contradicts | refines | depends_on


class EvidenceGraph(BaseModel):
    """Graph of collected evidence with relationships."""

    facts: list[EvidenceFact] = Field(default_factory=list)
    relations: list[EvidenceRelation] = Field(default_factory=list)

    def add_fact(self, fact: EvidenceFact) -> None:
        self.facts.append(fact)

    def add_relation(self, rel: EvidenceRelation) -> None:
        self.relations.append(rel)

    def find_contradictions(self) -> list[EvidenceRelation]:
        return [r for r in self.relations if r.relation_type == "contradicts"]

    def get_facts_for_aspect(self, aspect: str) -> list[EvidenceFact]:
        aspect_lower = aspect.lower()
        return [
            f for f in self.facts
            if aspect_lower in f.aspect.lower() or f.aspect.lower() in aspect_lower
        ]

    def strongest_facts(self, top_k: int = 10) -> list[EvidenceFact]:
        return sorted(self.facts, key=lambda f: f.confidence, reverse=True)[:top_k]


# ---- Quality Gates ----


class QualityGateResult(BaseModel):
    """Result of quality gate evaluation."""

    coverage: float = 0.0  # 0-1 (target: >=0.8)
    groundedness: float = 0.0  # 0-1 (target: >=0.9)
    confidence: float = 0.0  # average fact confidence
    passed: bool = False
    uncovered_aspects: list[str] = Field(default_factory=list)
    contradictions: int = 0
    recommendation: str = "continue"  # continue | finalize | backtrack


# ---- Report ----


class ReportSection(BaseModel):
    """A section in the research report."""

    title: str
    content: str
    evidence_ids: list[str] = Field(default_factory=list)


class ResearchReport(BaseModel):
    """Structured research report."""

    question: str
    executive_summary: str = ""
    sections: list[ReportSection] = Field(default_factory=list)
    comparison_table: str = ""  # markdown table
    contradictions: str = ""
    conclusions: str = ""
    sources: list[str] = Field(default_factory=list)
    evidence_count: int = 0
    rounds_used: int = 0
    coverage: float = 0.0
    total_search_queries: int = 0


# ---- Session Memory ----


class ResearchSession(BaseModel):
    """Persistent memory of a research session."""

    session_id: str
    question: str
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    plan: ResearchPlanTree | None = None
    evidence_graph: EvidenceGraph = Field(default_factory=EvidenceGraph)
    report: ResearchReport | None = None
    status: str = "active"  # active | completed | abandoned


# ---- LangGraph State ----


class ResearchV2State(TypedDict, total=False):
    """State for the Research Agent v2 graph."""

    # Input
    question: str
    max_rounds: int

    # Planning
    plan: dict[str, Any]  # ResearchPlanTree as dict

    # Evidence
    evidence_graph: dict[str, Any]  # EvidenceGraph as dict
    current_chunks: list[dict[str, Any]]

    # Quality
    quality: dict[str, Any]  # QualityGateResult as dict

    # Report
    report: dict[str, Any]  # ResearchReport as dict
    answer: str

    # Control
    round: int
    total_queries: int
    error: str
    session_id: str
