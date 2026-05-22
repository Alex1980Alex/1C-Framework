"""Common abstractions for run analyzers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ReportSpec:
    """Structured report payload — rendered to Markdown + JSON by report_writer."""

    mode: str  # "indexing" | "graph"
    subject: str  # collection name / graph name
    run_id: str
    generated_at: str  # ISO timestamp (local TZ)
    indexer_script: str
    duration_sec: float | None
    sections: list[tuple[str, str]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)
    anomalies: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


class AnalyzerBase(ABC):
    """One analyzer per ``--mode``. Returns a fully populated ReportSpec."""

    @abstractmethod
    def analyze(self) -> ReportSpec: ...
