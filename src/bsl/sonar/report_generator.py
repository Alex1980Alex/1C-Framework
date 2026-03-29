"""
SonarQube Report Generator

Phase 45: Миграция из 1C-Enterprise_Framework
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Issue:
    """Проблема в коде"""

    rule: str
    file: str
    line: int
    message: str
    severity: str


@dataclass
class AnalysisReport:
    """Отчёт анализа"""

    project_key: str
    timestamp: datetime
    issues: list[Issue]
    metrics: dict[str, Any]
    quality_gate: bool


class ReportGenerator:
    """Генератор отчётов SonarQube"""

    def __init__(self, config=None):
        self.config = config

    def generate(self, issues: list[Issue]) -> AnalysisReport:
        """Генерация отчёта"""
        metrics = self._calculate_metrics(issues)
        quality_gate = self._check_quality_gate(issues)

        return AnalysisReport(
            project_key=self.config.project_key if self.config else "unknown",
            timestamp=datetime.now(),
            issues=issues,
            metrics=metrics,
            quality_gate=quality_gate,
        )

    def _calculate_metrics(self, issues: list[Issue]) -> dict[str, Any]:
        """Расчёт метрик"""
        return {
            "total_issues": len(issues),
            "blocker": len([i for i in issues if i.severity == "BLOCKER"]),
            "critical": len([i for i in issues if i.severity == "CRITICAL"]),
            "major": len([i for i in issues if i.severity == "MAJOR"]),
            "minor": len([i for i in issues if i.severity == "MINOR"]),
            "info": len([i for i in issues if i.severity == "INFO"]),
        }

    def _check_quality_gate(self, issues: list[Issue]) -> bool:
        """Проверка Quality Gate"""
        # Базовое условие: нет blocker и critical
        blocker_count = len([i for i in issues if i.severity == "BLOCKER"])
        critical_count = len([i for i in issues if i.severity == "CRITICAL"])

        return blocker_count == 0 and critical_count == 0

    def export_markdown(self, report: AnalysisReport) -> str:
        """Экспорт в Markdown"""
        lines = [
            "# SonarQube Analysis Report",
            "",
            f"**Project:** {report.project_key}",
            f"**Date:** {report.timestamp.isoformat()}",
            f"**Quality Gate:** {'✅ PASSED' if report.quality_gate else '❌ FAILED'}",
            "",
            "## Metrics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
        ]

        for key, value in report.metrics.items():
            lines.append(f"| {key} | {value} |")

        if report.issues:
            lines.extend(
                [
                    "",
                    f"## Issues ({len(report.issues)})",
                    "",
                ]
            )

            for issue in report.issues[:50]:  # Ограничение
                lines.append(
                    f"- **{issue.severity}** [{issue.rule}] "
                    f"{issue.file}:{issue.line} - {issue.message}"
                )

        return "\n".join(lines)
