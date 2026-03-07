"""
Revision Limiter for Development Pipeline.

Provides centralized limit management and escalation logic.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from constants import AgentRole, ArtifactType, MAX_REVISION_ATTEMPTS


class EscalationLevel(str, Enum):
    """Escalation levels when limits are exceeded."""

    NONE = "none"                  # No escalation needed
    AGENT_SWITCH = "agent_switch"  # Try different agent approach
    HUMAN_REVIEW = "human_review"  # Escalate to human
    PIPELINE_ABORT = "pipeline_abort"  # Abort entire pipeline


@dataclass
class LimitConfig:
    """Configuration for revision limits."""

    max_attempts: int = MAX_REVISION_ATTEMPTS
    escalation_level: EscalationLevel = EscalationLevel.HUMAN_REVIEW
    allow_agent_switch: bool = True
    timeout_minutes: int = 30
    custom_message: str = ""

    @classmethod
    def strict(cls) -> "LimitConfig":
        """Strict config - fewer attempts, abort on failure."""
        return cls(
            max_attempts=2,
            escalation_level=EscalationLevel.PIPELINE_ABORT,
            allow_agent_switch=False,
        )

    @classmethod
    def lenient(cls) -> "LimitConfig":
        """Lenient config - more attempts, human review."""
        return cls(
            max_attempts=5,
            escalation_level=EscalationLevel.HUMAN_REVIEW,
            allow_agent_switch=True,
        )

    @classmethod
    def default(cls) -> "LimitConfig":
        """Default config."""
        return cls()


@dataclass
class EscalationEvent:
    """Record of an escalation event."""

    project_id: str
    task_id: str
    artifact_type: ArtifactType
    agent_role: AgentRole
    escalation_level: EscalationLevel
    reason: str
    attempts_made: int
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolution: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_id": self.project_id,
            "task_id": self.task_id,
            "artifact_type": self.artifact_type.value,
            "agent_role": self.agent_role.value,
            "escalation_level": self.escalation_level.value,
            "reason": self.reason,
            "attempts_made": self.attempts_made,
            "timestamp": self.timestamp.isoformat(),
            "resolved": self.resolved,
            "resolution": self.resolution,
        }


class RevisionLimiter:
    """
    Centralized revision limit management.

    Features:
    - Configurable limits per artifact type
    - Escalation handling
    - Event logging
    - Timeout management
    """

    def __init__(self, default_config: Optional[LimitConfig] = None) -> None:
        self.default_config = default_config or LimitConfig.default()
        self._configs: Dict[ArtifactType, LimitConfig] = {}
        self._escalations: List[EscalationEvent] = []
        self._callbacks: Dict[EscalationLevel, List[Callable]] = {
            level: [] for level in EscalationLevel
        }

    def set_config(self, artifact_type: ArtifactType, config: LimitConfig) -> None:
        """Set custom config for artifact type."""
        self._configs[artifact_type] = config

    def get_config(self, artifact_type: ArtifactType) -> LimitConfig:
        """Get config for artifact type."""
        return self._configs.get(artifact_type, self.default_config)

    def check_limit(
        self,
        artifact_type: ArtifactType,
        current_attempt: int,
    ) -> tuple[bool, Optional[EscalationLevel]]:
        """
        Check if revision limit is exceeded.

        Args:
            artifact_type: Type of artifact
            current_attempt: Current attempt number (1-based)

        Returns:
            Tuple of (within_limit, escalation_level if exceeded)
        """
        config = self.get_config(artifact_type)

        if current_attempt < config.max_attempts:
            return True, None

        return False, config.escalation_level

    def handle_escalation(
        self,
        project_id: str,
        task_id: str,
        artifact_type: ArtifactType,
        agent_role: AgentRole,
        reason: str,
        attempts_made: int,
    ) -> EscalationEvent:
        """
        Handle an escalation when limits are exceeded.

        Args:
            project_id: Project identifier
            task_id: Task identifier
            artifact_type: Type of artifact
            agent_role: Agent that failed
            reason: Reason for escalation
            attempts_made: Number of attempts made

        Returns:
            EscalationEvent record
        """
        config = self.get_config(artifact_type)

        event = EscalationEvent(
            project_id=project_id,
            task_id=task_id,
            artifact_type=artifact_type,
            agent_role=agent_role,
            escalation_level=config.escalation_level,
            reason=reason,
            attempts_made=attempts_made,
        )

        self._escalations.append(event)

        # Trigger callbacks
        for callback in self._callbacks.get(config.escalation_level, []):
            try:
                callback(event)
            except Exception:
                pass  # Don't let callbacks break the flow

        return event

    def register_callback(
        self,
        level: EscalationLevel,
        callback: Callable[[EscalationEvent], None],
    ) -> None:
        """Register callback for escalation level."""
        self._callbacks[level].append(callback)

    def resolve_escalation(
        self,
        event: EscalationEvent,
        resolution: str,
    ) -> None:
        """Mark escalation as resolved."""
        event.resolved = True
        event.resolution = resolution

    def get_pending_escalations(
        self,
        project_id: Optional[str] = None,
    ) -> List[EscalationEvent]:
        """Get unresolved escalations."""
        results = [e for e in self._escalations if not e.resolved]

        if project_id:
            results = [e for e in results if e.project_id == project_id]

        return results

    def get_escalation_summary(self) -> Dict[str, Any]:
        """Get summary of escalations."""
        total = len(self._escalations)
        pending = sum(1 for e in self._escalations if not e.resolved)
        resolved = total - pending

        by_level: Dict[str, int] = {}
        by_agent: Dict[str, int] = {}
        by_artifact: Dict[str, int] = {}

        for e in self._escalations:
            level = e.escalation_level.value
            by_level[level] = by_level.get(level, 0) + 1

            agent = e.agent_role.value
            by_agent[agent] = by_agent.get(agent, 0) + 1

            artifact = e.artifact_type.value
            by_artifact[artifact] = by_artifact.get(artifact, 0) + 1

        return {
            "total": total,
            "pending": pending,
            "resolved": resolved,
            "by_level": by_level,
            "by_agent": by_agent,
            "by_artifact": by_artifact,
        }

    def generate_escalation_message(
        self,
        event: EscalationEvent,
    ) -> str:
        """Generate human-readable escalation message."""
        lines = [
            "# ⚠️ Эскалация: Превышен лимит ревизий",
            "",
            "## Детали",
            "",
            f"| Параметр | Значение |",
            f"|----------|----------|",
            f"| Проект | {event.project_id} |",
            f"| Задача | {event.task_id} |",
            f"| Артефакт | {event.artifact_type.value} |",
            f"| Агент | {event.agent_role.value} |",
            f"| Попыток | {event.attempts_made} |",
            f"| Уровень | {event.escalation_level.value} |",
            "",
            "## Причина",
            "",
            event.reason,
            "",
        ]

        # Add action based on escalation level
        if event.escalation_level == EscalationLevel.HUMAN_REVIEW:
            lines.extend([
                "## Требуемые действия",
                "",
                "Требуется ручная проверка и исправление:",
                "",
                "1. Изучите историю ревизий",
                "2. Определите корневую причину проблемы",
                "3. Внесите исправления вручную или измените требования",
                "4. Перезапустите верификацию",
                "",
            ])
        elif event.escalation_level == EscalationLevel.PIPELINE_ABORT:
            lines.extend([
                "## ⛔ Pipeline остановлен",
                "",
                "Выполнение pipeline прервано из-за критической ошибки.",
                "Требуется ручное вмешательство перед продолжением.",
                "",
            ])
        elif event.escalation_level == EscalationLevel.AGENT_SWITCH:
            lines.extend([
                "## Переключение агента",
                "",
                "Будет предпринята попытка с другим подходом агента.",
                "",
            ])

        return "\n".join(lines)


# Factory functions for common configurations
def create_strict_limiter() -> RevisionLimiter:
    """Create limiter with strict limits."""
    limiter = RevisionLimiter(LimitConfig.strict())
    return limiter


def create_lenient_limiter() -> RevisionLimiter:
    """Create limiter with lenient limits."""
    limiter = RevisionLimiter(LimitConfig.lenient())
    return limiter


def create_default_limiter() -> RevisionLimiter:
    """Create limiter with default config."""
    return RevisionLimiter()
