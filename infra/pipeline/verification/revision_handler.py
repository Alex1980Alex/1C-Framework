"""
Revision Handler for Development Pipeline.

Handles REVISION_NEEDED status from verification:
- Routes artifacts back to appropriate agent
- Tracks revision history
- Enforces revision limits
- Generates revision prompts
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from constants import (
    AgentRole,
    ArtifactType,
    MAX_REVISION_ATTEMPTS,
    VerificationStatus,
)
from models import Artifact
from .base_verifier import CheckResult, VerificationResult


class RevisionAction(str, Enum):
    """Actions for revision handling."""

    REVISE = "revise"           # Send back to agent for revision
    ESCALATE = "escalate"       # Escalate to human
    ABORT = "abort"             # Abort pipeline
    SKIP = "skip"               # Skip verification (with warning)


@dataclass
class RevisionRequest:
    """Request for artifact revision."""

    artifact: Artifact
    verification_result: VerificationResult
    target_agent: AgentRole
    attempt_number: int
    failed_checks: List[CheckResult]
    revision_prompt: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact.metadata.artifact_type.value,
            "target_agent": self.target_agent.value,
            "attempt_number": self.attempt_number,
            "failed_checks_count": len(self.failed_checks),
            "timestamp": self.timestamp.isoformat(),
            "revision_prompt": self.revision_prompt,
            "metadata": self.metadata,
        }


@dataclass
class RevisionHistory:
    """History of revisions for an artifact."""

    artifact_type: ArtifactType
    project_id: str
    task_id: str
    revisions: List[RevisionRequest] = field(default_factory=list)
    current_attempt: int = 0
    max_attempts: int = MAX_REVISION_ATTEMPTS
    is_exhausted: bool = False

    def add_revision(self, request: RevisionRequest) -> None:
        """Add a revision to history."""
        self.revisions.append(request)
        self.current_attempt = request.attempt_number
        if self.current_attempt >= self.max_attempts:
            self.is_exhausted = True

    @property
    def remaining_attempts(self) -> int:
        return max(0, self.max_attempts - self.current_attempt)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_type": self.artifact_type.value,
            "project_id": self.project_id,
            "task_id": self.task_id,
            "current_attempt": self.current_attempt,
            "max_attempts": self.max_attempts,
            "remaining_attempts": self.remaining_attempts,
            "is_exhausted": self.is_exhausted,
            "revisions": [r.to_dict() for r in self.revisions],
        }


class RevisionHandler:
    """
    Handles revision workflow when verification fails.

    Responsibilities:
    - Determine appropriate action based on verification result
    - Generate revision prompts for agents
    - Track revision attempts
    - Enforce revision limits
    """

    def __init__(self, max_attempts: int = MAX_REVISION_ATTEMPTS) -> None:
        self.max_attempts = max_attempts
        self._histories: Dict[str, RevisionHistory] = {}  # key: "{project_id}:{task_id}:{artifact_type}"

    def handle_verification_result(
        self,
        artifact: Artifact,
        verification_result: VerificationResult,
        project_id: str,
        task_id: str,
    ) -> tuple[RevisionAction, Optional[RevisionRequest]]:
        """
        Handle verification result and determine next action.

        Args:
            artifact: The artifact that was verified
            verification_result: Result from verifier
            project_id: Project identifier
            task_id: Task identifier

        Returns:
            Tuple of (action to take, revision request if applicable)
        """
        # If approved, no revision needed
        if verification_result.status == VerificationStatus.APPROVED:
            return RevisionAction.SKIP, None

        # Get or create history
        history = self._get_or_create_history(
            artifact.metadata.artifact_type,
            project_id,
            task_id,
        )

        # Check if exhausted
        if history.is_exhausted:
            return RevisionAction.ESCALATE, None

        # Determine target agent
        target_agent = self._determine_target_agent(artifact.metadata.artifact_type)

        # Get failed checks
        failed_checks = [c for c in verification_result.checks if not c.passed]

        # Generate revision prompt
        revision_prompt = self._generate_revision_prompt(
            artifact,
            verification_result,
            failed_checks,
            history.current_attempt + 1,
        )

        # Create revision request
        request = RevisionRequest(
            artifact=artifact,
            verification_result=verification_result,
            target_agent=target_agent,
            attempt_number=history.current_attempt + 1,
            failed_checks=failed_checks,
            revision_prompt=revision_prompt,
            metadata={
                "project_id": project_id,
                "task_id": task_id,
                "remaining_attempts": history.remaining_attempts - 1,
            },
        )

        # Add to history
        history.add_revision(request)

        # Check if this was the last attempt
        if history.is_exhausted:
            return RevisionAction.ESCALATE, request

        return RevisionAction.REVISE, request

    def _get_or_create_history(
        self,
        artifact_type: ArtifactType,
        project_id: str,
        task_id: str,
    ) -> RevisionHistory:
        """Get or create revision history for artifact."""
        key = f"{project_id}:{task_id}:{artifact_type.value}"

        if key not in self._histories:
            self._histories[key] = RevisionHistory(
                artifact_type=artifact_type,
                project_id=project_id,
                task_id=task_id,
                max_attempts=self.max_attempts,
            )

        return self._histories[key]

    def _determine_target_agent(self, artifact_type: ArtifactType) -> AgentRole:
        """Determine which agent should handle the revision."""
        mapping = {
            # PM-SPEC artifacts
            ArtifactType.CONTEXT: AgentRole.PM_SPEC,
            ArtifactType.SPEC: AgentRole.PM_SPEC,
            ArtifactType.VERIFICATION: AgentRole.PM_SPEC,
            # ARCHITECT artifacts
            ArtifactType.DESIGN: AgentRole.ARCHITECT,
            ArtifactType.REVIEW: AgentRole.ARCHITECT,
            # IMPLEMENTER artifacts
            ArtifactType.RESULT: AgentRole.IMPLEMENTER,
            ArtifactType.QA_REPORT: AgentRole.IMPLEMENTER,
        }

        return mapping.get(artifact_type, AgentRole.PM_SPEC)

    def _generate_revision_prompt(
        self,
        artifact: Artifact,
        verification_result: VerificationResult,
        failed_checks: List[CheckResult],
        attempt_number: int,
    ) -> str:
        """Generate a detailed revision prompt for the agent."""
        lines = [
            f"# Запрос на ревизию (попытка {attempt_number}/{self.max_attempts})",
            "",
            f"## Артефакт: {artifact.metadata.artifact_type.value}",
            f"**Статус верификации:** {verification_result.status.value}",
            "",
            "## Проблемы для исправления",
            "",
        ]

        # Group failed checks by severity
        errors = [c for c in failed_checks if c.severity == "error"]
        warnings = [c for c in failed_checks if c.severity == "warning"]

        if errors:
            lines.append("### 🔴 Критические ошибки (обязательно исправить)")
            lines.append("")
            for i, check in enumerate(errors, 1):
                lines.append(f"{i}. **{check.check_type.value}**: {check.message}")
            lines.append("")

        if warnings:
            lines.append("### 🟡 Предупреждения (рекомендуется исправить)")
            lines.append("")
            for i, check in enumerate(warnings, 1):
                lines.append(f"{i}. **{check.check_type.value}**: {check.message}")
            lines.append("")

        # Add recommendations if any
        if verification_result.recommendations:
            lines.append("## Рекомендации")
            lines.append("")
            for rec in verification_result.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        # Add instructions
        lines.extend([
            "## Инструкции",
            "",
            "1. Внимательно изучите указанные проблемы",
            "2. Исправьте все критические ошибки",
            "3. По возможности устраните предупреждения",
            "4. Повторно сгенерируйте артефакт",
            "",
        ])

        # Add remaining attempts warning
        remaining = self.max_attempts - attempt_number
        if remaining <= 1:
            lines.extend([
                "⚠️ **ВНИМАНИЕ**: Это последняя попытка!",
                "При неуспешной верификации задача будет эскалирована.",
                "",
            ])
        else:
            lines.append(f"ℹ️ Осталось попыток: {remaining}")
            lines.append("")

        return "\n".join(lines)

    def get_history(
        self,
        project_id: str,
        task_id: str,
        artifact_type: Optional[ArtifactType] = None,
    ) -> List[RevisionHistory]:
        """
        Get revision history for a task.

        Args:
            project_id: Project identifier
            task_id: Task identifier
            artifact_type: Optional filter by artifact type

        Returns:
            List of revision histories
        """
        results = []
        prefix = f"{project_id}:{task_id}:"

        for key, history in self._histories.items():
            if key.startswith(prefix):
                if artifact_type is None or history.artifact_type == artifact_type:
                    results.append(history)

        return results

    def reset_history(
        self,
        project_id: str,
        task_id: str,
        artifact_type: Optional[ArtifactType] = None,
    ) -> None:
        """
        Reset revision history for a task.

        Args:
            project_id: Project identifier
            task_id: Task identifier
            artifact_type: Optional filter by artifact type
        """
        prefix = f"{project_id}:{task_id}:"
        keys_to_remove = []

        for key in self._histories:
            if key.startswith(prefix):
                if artifact_type is None:
                    keys_to_remove.append(key)
                elif key.endswith(f":{artifact_type.value}"):
                    keys_to_remove.append(key)

        for key in keys_to_remove:
            del self._histories[key]

    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about revision handling."""
        total_revisions = sum(len(h.revisions) for h in self._histories.values())
        exhausted_count = sum(1 for h in self._histories.values() if h.is_exhausted)

        # Count by agent
        by_agent: Dict[str, int] = {}
        for history in self._histories.values():
            for revision in history.revisions:
                agent = revision.target_agent.value
                by_agent[agent] = by_agent.get(agent, 0) + 1

        return {
            "total_histories": len(self._histories),
            "total_revisions": total_revisions,
            "exhausted_count": exhausted_count,
            "revisions_by_agent": by_agent,
        }
