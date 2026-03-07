"""
Integration tests for RevisionHandler.
"""

import pytest

from constants import VerificationStatus, ArtifactType, AgentRole
from models import Artifact, ArtifactMetadata
from verification import (
    RevisionHandler,
    RevisionAction,
    RevisionHistory,
    RevisionRequest,
    VerificationResult,
    CheckResult,
    CheckType,
)


class TestRevisionHandler:
    """Test suite for RevisionHandler."""

    def setup_method(self):
        """Setup handler instance."""
        self.handler = RevisionHandler(max_attempts=3)

    def test_handle_approved_result(self, sample_context_artifact):
        """Test handling of APPROVED verification result."""
        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.APPROVED,
            checks=[],
            summary="All checks passed",
        )

        action, request = self.handler.handle_verification_result(
            artifact=sample_context_artifact,
            verification_result=verification_result,
            project_id="test-project",
            task_id="test-task",
        )

        assert action == RevisionAction.SKIP
        assert request is None

    def test_handle_revision_needed_first_attempt(self, sample_context_artifact):
        """Test handling of REVISION_NEEDED on first attempt."""
        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.REVISION_NEEDED,
            checks=[
                CheckResult(
                    check_type=CheckType.COMPLETENESS,
                    passed=False,
                    message="Missing goals section",
                    severity="error",
                ),
            ],
            summary="Revision needed",
        )

        action, request = self.handler.handle_verification_result(
            artifact=sample_context_artifact,
            verification_result=verification_result,
            project_id="test-project",
            task_id="test-task",
        )

        assert action == RevisionAction.REVISE
        assert request is not None
        assert request.attempt_number == 1
        assert request.target_agent == AgentRole.PM_SPEC
        assert len(request.failed_checks) == 1

    def test_handle_revision_needed_escalation(self, sample_context_artifact):
        """Test escalation after max attempts."""
        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.REVISION_NEEDED,
            checks=[
                CheckResult(
                    check_type=CheckType.COMPLETENESS,
                    passed=False,
                    message="Missing section",
                    severity="error",
                ),
            ],
            summary="Revision needed",
        )

        # Simulate 3 failed attempts
        for i in range(3):
            action, request = self.handler.handle_verification_result(
                artifact=sample_context_artifact,
                verification_result=verification_result,
                project_id="test-project",
                task_id="test-task",
            )

        # After 3 attempts, should escalate
        assert action == RevisionAction.ESCALATE
        assert request is not None
        assert request.attempt_number == 3

    def test_revision_prompt_generation(self, sample_context_artifact):
        """Test that revision prompt is properly generated."""
        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.REVISION_NEEDED,
            checks=[
                CheckResult(
                    check_type=CheckType.COMPLETENESS,
                    passed=False,
                    message="Отсутствует секция целей",
                    severity="error",
                ),
                CheckResult(
                    check_type=CheckType.QUALITY,
                    passed=False,
                    message="Недостаточно деталей",
                    severity="warning",
                ),
            ],
            summary="Revision needed",
            recommendations=["Добавить секцию целей", "Расширить описание"],
        )

        action, request = self.handler.handle_verification_result(
            artifact=sample_context_artifact,
            verification_result=verification_result,
            project_id="test-project",
            task_id="test-task",
        )

        assert action == RevisionAction.REVISE
        assert request is not None

        # Check prompt content
        prompt = request.revision_prompt
        assert "Запрос на ревизию" in prompt
        assert "Критические ошибки" in prompt
        assert "Предупреждения" in prompt
        assert "Рекомендации" in prompt

    def test_target_agent_routing(self):
        """Test that artifacts are routed to correct agents."""
        handler = RevisionHandler()

        # PM-SPEC artifacts
        for artifact_type in [ArtifactType.CONTEXT, ArtifactType.SPEC]:
            agent = handler._determine_target_agent(artifact_type)
            assert agent == AgentRole.PM_SPEC

        # ARCHITECT artifacts
        for artifact_type in [ArtifactType.DESIGN, ArtifactType.REVIEW]:
            agent = handler._determine_target_agent(artifact_type)
            assert agent == AgentRole.ARCHITECT

        # IMPLEMENTER artifacts
        for artifact_type in [ArtifactType.RESULT, ArtifactType.QA_REPORT]:
            agent = handler._determine_target_agent(artifact_type)
            assert agent == AgentRole.IMPLEMENTER

    def test_history_tracking(self, sample_context_artifact):
        """Test that revision history is properly tracked."""
        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.REVISION_NEEDED,
            checks=[
                CheckResult(
                    check_type=CheckType.COMPLETENESS,
                    passed=False,
                    message="Error",
                    severity="error",
                ),
            ],
            summary="Revision needed",
        )

        # First attempt
        self.handler.handle_verification_result(
            artifact=sample_context_artifact,
            verification_result=verification_result,
            project_id="test-project",
            task_id="test-task",
        )

        # Get history
        histories = self.handler.get_history("test-project", "test-task")
        assert len(histories) == 1

        history = histories[0]
        assert history.current_attempt == 1
        assert history.remaining_attempts == 2
        assert not history.is_exhausted

    def test_history_reset(self, sample_context_artifact):
        """Test history reset functionality."""
        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.REVISION_NEEDED,
            checks=[],
            summary="Revision needed",
        )

        # Create some history
        self.handler.handle_verification_result(
            artifact=sample_context_artifact,
            verification_result=verification_result,
            project_id="test-project",
            task_id="test-task",
        )

        # Reset history
        self.handler.reset_history("test-project", "test-task")

        # History should be empty
        histories = self.handler.get_history("test-project", "test-task")
        assert len(histories) == 0

    def test_statistics(self, sample_context_artifact, sample_design_artifact):
        """Test statistics generation."""
        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.REVISION_NEEDED,
            checks=[],
            summary="Revision needed",
        )

        # Create some revisions
        self.handler.handle_verification_result(
            artifact=sample_context_artifact,
            verification_result=verification_result,
            project_id="project-1",
            task_id="task-1",
        )

        stats = self.handler.get_statistics()

        assert stats["total_histories"] >= 1
        assert stats["total_revisions"] >= 1
        assert "revisions_by_agent" in stats


class TestRevisionHandlerEdgeCases:
    """Edge case tests for RevisionHandler."""

    def test_custom_max_attempts(self):
        """Test with custom max attempts."""
        handler = RevisionHandler(max_attempts=5)

        artifact = Artifact(
            name="context.md",
            content="test",
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.CONTEXT,
                producer=AgentRole.PM_SPEC,
                version=1,
                tags={"project_id": "test", "task_id": "test"},
            ),
        )

        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.REVISION_NEEDED,
            checks=[],
            summary="Revision needed",
        )

        # Should allow 5 attempts
        for i in range(5):
            action, _ = handler.handle_verification_result(
                artifact=artifact,
                verification_result=verification_result,
                project_id="test",
                task_id="test",
            )

        # 5th attempt should escalate
        assert action == RevisionAction.ESCALATE

    def test_multiple_projects(self):
        """Test handling multiple projects."""
        handler = RevisionHandler()

        artifact = Artifact(
            name="context.md",
            content="test",
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.CONTEXT,
                producer=AgentRole.PM_SPEC,
                version=1,
                tags={"project_id": "test", "task_id": "test"},
            ),
        )

        verification_result = VerificationResult(
            agent_role=AgentRole.PM_SPEC,
            artifact_type=ArtifactType.CONTEXT,
            status=VerificationStatus.REVISION_NEEDED,
            checks=[],
            summary="Revision needed",
        )

        # Create revisions for different projects
        handler.handle_verification_result(
            artifact=artifact,
            verification_result=verification_result,
            project_id="project-1",
            task_id="task-1",
        )

        handler.handle_verification_result(
            artifact=artifact,
            verification_result=verification_result,
            project_id="project-2",
            task_id="task-1",
        )

        # Each project should have its own history
        h1 = handler.get_history("project-1", "task-1")
        h2 = handler.get_history("project-2", "task-1")

        assert len(h1) == 1
        assert len(h2) == 1
        assert h1[0].project_id == "project-1"
        assert h2[0].project_id == "project-2"
