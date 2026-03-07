"""
Base Verifier for Development Pipeline.

Provides common verification logic for all agents.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
import re

from constants import (
    AgentRole,
    ArtifactType,
    RequirementStatus,
    VerificationStatus,
)
from models import Artifact


class CheckType(str, Enum):
    """Types of verification checks."""

    STRUCTURE = "structure"      # Required sections present
    COMPLETENESS = "completeness"  # All requirements addressed
    CONSISTENCY = "consistency"   # No contradictions
    QUALITY = "quality"          # Code/design quality
    TRACEABILITY = "traceability"  # Requirements traced to implementation


@dataclass
class CheckResult:
    """Result of a single verification check."""

    check_type: CheckType
    passed: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    severity: str = "error"  # error, warning, info

    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_type": self.check_type.value,
            "passed": self.passed,
            "message": self.message,
            "details": self.details,
            "severity": self.severity,
        }


@dataclass
class RequirementCheck:
    """Result of checking a single requirement."""

    requirement_id: str
    description: str
    status: RequirementStatus
    evidence: str = ""
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requirement_id": self.requirement_id,
            "description": self.description,
            "status": self.status.value,
            "evidence": self.evidence,
            "notes": self.notes,
        }


@dataclass
class VerificationResult:
    """Complete verification result."""

    agent_role: AgentRole
    artifact_type: ArtifactType
    status: VerificationStatus
    checks: List[CheckResult] = field(default_factory=list)
    requirements: List[RequirementCheck] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    summary: str = ""
    recommendations: List[str] = field(default_factory=list)

    @property
    def passed_checks(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def failed_checks(self) -> int:
        return sum(1 for c in self.checks if not c.passed)

    @property
    def passed_requirements(self) -> int:
        return sum(1 for r in self.requirements if r.status == RequirementStatus.PASSED)

    @property
    def failed_requirements(self) -> int:
        return sum(1 for r in self.requirements if r.status == RequirementStatus.FAILED)

    def to_markdown(self) -> str:
        """Generate verification report in Markdown format."""
        lines = [
            "# Отчёт верификации",
            "",
            f"**Агент:** {self.agent_role.value}",
            f"**Артефакт:** {self.artifact_type.value}",
            f"**Статус:** {self.status.value}",
            f"**Дата:** {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
        ]

        # Summary
        if self.summary:
            lines.extend([
                "## Резюме",
                "",
                self.summary,
                "",
            ])

        # Checks table
        if self.checks:
            lines.extend([
                "## Проверки",
                "",
                "| Тип | Статус | Сообщение |",
                "|-----|--------|-----------|",
            ])
            for check in self.checks:
                status_icon = "✅" if check.passed else "❌"
                lines.append(f"| {check.check_type.value} | {status_icon} | {check.message} |")
            lines.append("")

        # Requirements table
        if self.requirements:
            lines.extend([
                "## Требования",
                "",
                "| ID | Описание | Статус | Примечания |",
                "|----|----------|--------|------------|",
            ])
            for req in self.requirements:
                lines.append(
                    f"| {req.requirement_id} | {req.description} | {req.status.value} | {req.notes} |"
                )
            lines.append("")

        # Statistics
        lines.extend([
            "## Статистика",
            "",
            f"- Проверок пройдено: {self.passed_checks}/{len(self.checks)}",
            f"- Требований выполнено: {self.passed_requirements}/{len(self.requirements)}",
            "",
        ])

        # Recommendations
        if self.recommendations:
            lines.extend([
                "## Рекомендации",
                "",
            ])
            for rec in self.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_role": self.agent_role.value,
            "artifact_type": self.artifact_type.value,
            "status": self.status.value,
            "checks": [c.to_dict() for c in self.checks],
            "requirements": [r.to_dict() for r in self.requirements],
            "timestamp": self.timestamp.isoformat(),
            "summary": self.summary,
            "recommendations": self.recommendations,
            "statistics": {
                "passed_checks": self.passed_checks,
                "failed_checks": self.failed_checks,
                "passed_requirements": self.passed_requirements,
                "failed_requirements": self.failed_requirements,
            },
        }


class BaseVerifier(ABC):
    """Abstract base class for artifact verifiers."""

    def __init__(self, agent_role: AgentRole, artifact_type: ArtifactType) -> None:
        self.agent_role = agent_role
        self.artifact_type = artifact_type

    @abstractmethod
    def verify(self, artifact: Artifact, context: Optional[Dict[str, Any]] = None) -> VerificationResult:
        """
        Verify an artifact.

        Args:
            artifact: The artifact to verify
            context: Additional context (e.g., spec.md for verifying result.md)

        Returns:
            VerificationResult with status and details
        """
        pass

    def check_structure(self, artifact: Artifact) -> CheckResult:
        """Check that artifact has required sections."""
        errors = artifact.validate()

        if errors:
            return CheckResult(
                check_type=CheckType.STRUCTURE,
                passed=False,
                message=f"Отсутствуют обязательные секции: {', '.join(errors)}",
                details={"errors": errors},
                severity="error",
            )

        return CheckResult(
            check_type=CheckType.STRUCTURE,
            passed=True,
            message="Все обязательные секции присутствуют",
            severity="info",
        )

    def extract_requirements(self, spec_content: str) -> List[Dict[str, str]]:
        """Extract requirements from spec.md content."""
        requirements = []

        # Pattern for REQ-N format
        req_pattern = r"(?:REQ-\d+|Требование\s+\d+)[:\s]+(.+?)(?=(?:REQ-\d+|Требование\s+\d+|##|$))"
        matches = re.findall(req_pattern, spec_content, re.IGNORECASE | re.DOTALL)

        for i, match in enumerate(matches, 1):
            requirements.append({
                "id": f"REQ-{i}",
                "description": match.strip()[:100],
            })

        # Look for "## Требования" section - use line-by-line approach to capture until next H1
        lines = spec_content.split('\n')
        in_req = False
        req_lines = []
        
        for line in lines:
            if re.match(r'^##\s*Требования', line, re.IGNORECASE):
                in_req = True
                req_lines.append(line)
            elif in_req:
                if re.match(r'^##\s+', line):  # Next H1 (starts with ## followed by non-#)
                    break
                req_lines.append(line)

        if req_lines:
            req_section_text = '\n'.join(req_lines)
            # Find all bullet points in the entire requirements section (including subsections)
            bullets = re.findall(r"[-*]\s+(.+)", req_section_text)
            for bullet in bullets:
                bullet = bullet.strip()
                
                # Try to extract requirement ID from formats like "FR-001:", "NFR-001:", "REQ-001:"
                id_match = re.match(r"^(FR-\d+|NFR-\d+|REQ-\d+|Требование\s+\d+):\s*(.+)$", bullet, re.IGNORECASE)
                
                if id_match:
                    # Has explicit ID - use it
                    req_id = id_match.group(1).replace("Требование ", "Требование-")
                    desc = id_match.group(2).strip()[:100]
                else:
                    # No explicit ID - generate sequential ID
                    req_id = f"REQ-{len(requirements) + 1}"
                    desc = bullet[:100]
                
                requirements.append({
                    "id": req_id,
                    "description": desc,
                })

        return requirements

    def extract_acceptance_criteria(self, spec_content: str) -> List[Dict[str, str]]:
        """Extract acceptance criteria from spec.md content."""
        criteria = []

        # Pattern for AC-N format
        ac_pattern = r"(?:AC-\d+|Критерий\s+\d+)[:\s]+(.+?)(?=(?:AC-\d+|Критерий\s+\d+|##|$))"

        matches = re.findall(ac_pattern, spec_content, re.IGNORECASE | re.DOTALL)

        for i, match in enumerate(matches, 1):
            criteria.append({
                "id": f"AC-{i}",
                "description": match.strip()[:100],
            })

        # Also look for bullet points under "Критерии приёмки" section
        ac_section = re.search(
            r"##\s*Критерии приёмки\s*\n(.*?)(?=##|$)",
            spec_content,
            re.IGNORECASE | re.DOTALL
        )

        if ac_section:
            bullets = re.findall(r"[-*]\s+(.+)", ac_section.group(1))
            for i, bullet in enumerate(bullets, len(criteria) + 1):
                criteria.append({
                    "id": f"AC-{i}",
                    "description": bullet.strip()[:100],
                })

        return criteria

    def check_traceability(
        self,
        source_artifact: Artifact,
        target_artifact: Artifact,
    ) -> CheckResult:
        """Check that target artifact addresses all items from source."""
        # Extract requirements/items from source
        if source_artifact.metadata.artifact_type == ArtifactType.SPEC:
            items = self.extract_requirements(source_artifact.content)
        else:
            items = []

        if not items:
            return CheckResult(
                check_type=CheckType.TRACEABILITY,
                passed=True,
                message="Нет требований для трассировки",
                severity="info",
            )

        # Check each item is mentioned in target
        missing = []
        for item in items:
            # Look for requirement ID or keywords from description
            keywords = item["description"].split()[:3]  # First 3 words
            found = any(
                kw.lower() in target_artifact.content.lower()
                for kw in keywords if len(kw) > 3
            )

            if not found and item["id"] not in target_artifact.content:
                missing.append(item["id"])

        if missing:
            return CheckResult(
                check_type=CheckType.TRACEABILITY,
                passed=False,
                message=f"Не адресованы требования: {', '.join(missing)}",
                details={"missing": missing},
                severity="warning",
            )

        return CheckResult(
            check_type=CheckType.TRACEABILITY,
            passed=True,
            message="Все требования адресованы",
            severity="info",
        )
