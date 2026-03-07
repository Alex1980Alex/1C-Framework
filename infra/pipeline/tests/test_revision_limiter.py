"""
Integration tests for RevisionLimiter.
"""

import pytest

from constants import ArtifactType, AgentRole
from verification import (
    RevisionLimiter,
    LimitConfig,
    EscalationLevel,
    EscalationEvent,
    create_default_limiter,
    create_strict_limiter,
    create_lenient_limiter,
)


class TestRevisionLimiter:
    """Test suite for RevisionLimiter."""

    def setup_method(self):
        """Setup limiter instance."""
        self.limiter = RevisionLimiter()

    def test_check_limit_within(self):
        """Test check when within limit."""
        within_limit, escalation = self.limiter.check_limit(
            artifact_type=ArtifactType.CONTEXT,
            current_attempt=1,
        )

        assert within_limit is True
        assert escalation is None

    def test_check_limit_exceeded(self):
        """Test check when limit is exceeded."""
        within_limit, escalation = self.limiter.check_limit(
            artifact_type=ArtifactType.CONTEXT,
            current_attempt=3,  # Default max is 3
        )

        assert within_limit is False
        assert escalation == EscalationLevel.HUMAN_REVIEW

    def test_custom_config_per_artifact(self):
        """Test custom config for specific artifact type."""
        self.limiter.set_config(
            ArtifactType.SPEC,
            LimitConfig(max_attempts=5, escalation_level=EscalationLevel.PIPELINE_ABORT)
        )

        # SPEC should have custom config
        config = self.limiter.get_config(ArtifactType.SPEC)
        assert config.max_attempts == 5
        assert config.escalation_level == EscalationLevel.PIPELINE_ABORT

        # Other types should use default
        default_config = self.limiter.get_config(ArtifactType.CONTEXT)
        assert default_config.max_attempts == 3

    def test_handle_escalation(self):
        """Test escalation event handling."""
        event = self.limiter.handle_escalation(
            project_id="test-project",
            task_id="test-task",
            artifact_type=ArtifactType.CONTEXT,
            agent_role=AgentRole.PM_SPEC,
            reason="Too many failed attempts",
            attempts_made=3,
        )

        assert isinstance(event, EscalationEvent)
        assert event.project_id == "test-project"
        assert event.attempts_made == 3
        assert event.escalation_level == EscalationLevel.HUMAN_REVIEW
        assert not event.resolved

    def test_escalation_callback(self):
        """Test escalation callback registration."""
        callback_called = []

        def on_escalation(event: EscalationEvent):
            callback_called.append(event)

        self.limiter.register_callback(EscalationLevel.HUMAN_REVIEW, on_escalation)

        self.limiter.handle_escalation(
            project_id="test",
            task_id="test",
            artifact_type=ArtifactType.CONTEXT,
            agent_role=AgentRole.PM_SPEC,
            reason="Test",
            attempts_made=3,
        )

        assert len(callback_called) == 1
        assert callback_called[0].project_id == "test"

    def test_resolve_escalation(self):
        """Test resolving an escalation."""
        event = self.limiter.handle_escalation(
            project_id="test",
            task_id="test",
            artifact_type=ArtifactType.CONTEXT,
            agent_role=AgentRole.PM_SPEC,
            reason="Test",
            attempts_made=3,
        )

        assert not event.resolved

        self.limiter.resolve_escalation(event, "Fixed manually")

        assert event.resolved
        assert event.resolution == "Fixed manually"

    def test_get_pending_escalations(self):
        """Test getting pending escalations."""
        # Create some escalations
        self.limiter.handle_escalation(
            project_id="project-1",
            task_id="task-1",
            artifact_type=ArtifactType.CONTEXT,
            agent_role=AgentRole.PM_SPEC,
            reason="Test 1",
            attempts_made=3,
        )

        event2 = self.limiter.handle_escalation(
            project_id="project-1",
            task_id="task-2",
            artifact_type=ArtifactType.SPEC,
            agent_role=AgentRole.PM_SPEC,
            reason="Test 2",
            attempts_made=3,
        )

        # Resolve one
        self.limiter.resolve_escalation(event2, "Resolved")

        # Get pending
        pending = self.limiter.get_pending_escalations()
        assert len(pending) == 1

        # Filter by project
        pending_project = self.limiter.get_pending_escalations("project-1")
        assert len(pending_project) == 1

    def test_escalation_summary(self):
        """Test escalation summary generation."""
        # Create escalations for different agents
        self.limiter.handle_escalation(
            project_id="test",
            task_id="task-1",
            artifact_type=ArtifactType.CONTEXT,
            agent_role=AgentRole.PM_SPEC,
            reason="Test",
            attempts_made=3,
        )

        self.limiter.handle_escalation(
            project_id="test",
            task_id="task-2",
            artifact_type=ArtifactType.DESIGN,
            agent_role=AgentRole.ARCHITECT,
            reason="Test",
            attempts_made=3,
        )

        summary = self.limiter.get_escalation_summary()

        assert summary["total"] == 2
        assert summary["pending"] == 2
        assert summary["resolved"] == 0
        assert AgentRole.PM_SPEC.value in summary["by_agent"]
        assert AgentRole.ARCHITECT.value in summary["by_agent"]

    def test_generate_escalation_message(self):
        """Test human-readable escalation message generation."""
        event = self.limiter.handle_escalation(
            project_id="test-project",
            task_id="test-task",
            artifact_type=ArtifactType.CONTEXT,
            agent_role=AgentRole.PM_SPEC,
            reason="Не удалось исправить структуру документа",
            attempts_made=3,
        )

        message = self.limiter.generate_escalation_message(event)

        # Check message content
        assert "Эскалация" in message
        assert "test-project" in message
        assert "PM-SPEC" in message or "pm-spec" in message.lower() or "PM_SPEC" in message
        assert "3" in message  # attempts
        assert "Требуемые действия" in message or "ручная проверка" in message.lower()


class TestLimitConfig:
    """Test suite for LimitConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = LimitConfig.default()

        assert config.max_attempts == 3
        assert config.escalation_level == EscalationLevel.HUMAN_REVIEW
        assert config.allow_agent_switch is True

    def test_strict_config(self):
        """Test strict configuration."""
        config = LimitConfig.strict()

        assert config.max_attempts == 2
        assert config.escalation_level == EscalationLevel.PIPELINE_ABORT
        assert config.allow_agent_switch is False

    def test_lenient_config(self):
        """Test lenient configuration."""
        config = LimitConfig.lenient()

        assert config.max_attempts == 5
        assert config.escalation_level == EscalationLevel.HUMAN_REVIEW
        assert config.allow_agent_switch is True


class TestFactoryFunctions:
    """Test suite for factory functions."""

    def test_create_default_limiter(self):
        """Test default limiter creation."""
        limiter = create_default_limiter()

        assert isinstance(limiter, RevisionLimiter)
        config = limiter.get_config(ArtifactType.CONTEXT)
        assert config.max_attempts == 3

    def test_create_strict_limiter(self):
        """Test strict limiter creation."""
        limiter = create_strict_limiter()

        assert isinstance(limiter, RevisionLimiter)
        config = limiter.get_config(ArtifactType.CONTEXT)
        assert config.max_attempts == 2
        assert config.escalation_level == EscalationLevel.PIPELINE_ABORT

    def test_create_lenient_limiter(self):
        """Test lenient limiter creation."""
        limiter = create_lenient_limiter()

        assert isinstance(limiter, RevisionLimiter)
        config = limiter.get_config(ArtifactType.CONTEXT)
        assert config.max_attempts == 5


class TestEscalationEvent:
    """Test suite for EscalationEvent."""

    def test_to_dict(self):
        """Test serialization to dict."""
        event = EscalationEvent(
            project_id="test-project",
            task_id="test-task",
            artifact_type=ArtifactType.CONTEXT,
            agent_role=AgentRole.PM_SPEC,
            escalation_level=EscalationLevel.HUMAN_REVIEW,
            reason="Test reason",
            attempts_made=3,
        )

        data = event.to_dict()

        assert data["project_id"] == "test-project"
        assert data["artifact_type"] == "context.md"
        assert data["agent_role"] in ["pm_spec", "PM-SPEC", "PM_SPEC"]
        assert data["escalation_level"] == "human_review"
        assert data["attempts_made"] == 3
        assert "timestamp" in data


class TestEscalationLevels:
    """Test different escalation levels."""

    def test_agent_switch_escalation(self):
        """Test agent switch escalation level."""
        limiter = RevisionLimiter(
            LimitConfig(
                max_attempts=2,
                escalation_level=EscalationLevel.AGENT_SWITCH,
            )
        )

        within, level = limiter.check_limit(ArtifactType.CONTEXT, 2)
        assert within is False
        assert level == EscalationLevel.AGENT_SWITCH

    def test_pipeline_abort_escalation(self):
        """Test pipeline abort escalation level."""
        limiter = RevisionLimiter(
            LimitConfig(
                max_attempts=1,
                escalation_level=EscalationLevel.PIPELINE_ABORT,
            )
        )

        within, level = limiter.check_limit(ArtifactType.CONTEXT, 1)
        assert within is False
        assert level == EscalationLevel.PIPELINE_ABORT

        # Generate message
        event = limiter.handle_escalation(
            project_id="test",
            task_id="test",
            artifact_type=ArtifactType.CONTEXT,
            agent_role=AgentRole.PM_SPEC,
            reason="Critical failure",
            attempts_made=1,
        )

        message = limiter.generate_escalation_message(event)
        assert "Pipeline остановлен" in message or "прервано" in message.lower()
