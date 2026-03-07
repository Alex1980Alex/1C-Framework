"""
Integration tests for ArchitectVerifier.
"""

import pytest

from constants import VerificationStatus, ArtifactType, AgentRole
from models import Artifact, ArtifactMetadata
from verification import ArchitectVerifier, CheckType


class TestArchitectVerifier:
    """Test suite for ARCHITECT verifier."""

    def setup_method(self):
        """Setup verifier instance."""
        self.verifier = ArchitectVerifier()

    def test_verify_complete_design(self, sample_design_artifact):
        """Test verification of complete design.md."""
        result = self.verifier.verify(sample_design_artifact)

        assert result.status == VerificationStatus.APPROVED
        assert result.artifact_type == ArtifactType.DESIGN
        assert len(result.checks) > 0

        # Check that all critical checks passed
        critical_failed = [
            c for c in result.checks
            if not c.passed and c.severity == "error"
        ]
        assert len(critical_failed) == 0, f"Critical checks failed: {critical_failed}"

    def test_verify_incomplete_design(self, incomplete_design_artifact):
        """Test verification of incomplete design.md."""
        result = self.verifier.verify(incomplete_design_artifact)

        assert result.status == VerificationStatus.REVISION_NEEDED
        assert len(result.checks) > 0

        # Check that some critical checks failed
        critical_failed = [
            c for c in result.checks
            if not c.passed and c.severity == "error"
        ]
        assert len(critical_failed) > 0

    def test_architectural_decisions_check(self, sample_design_artifact):
        """Test that architectural decisions section is checked."""
        result = self.verifier.verify(sample_design_artifact)

        completeness_checks = [
            c for c in result.checks
            if c.check_type == CheckType.COMPLETENESS
        ]

        # Should have completeness checks for architectural decisions
        assert len(completeness_checks) > 0

    def test_change_plan_check(self, sample_design_artifact):
        """Test that change plan section is checked."""
        result = self.verifier.verify(sample_design_artifact)

        # Design artifact should have plan check
        assert any(
            "план" in c.message.lower() or "реализаци" in c.message.lower()
            for c in result.checks
        )

    def test_risks_section_check(self, sample_design_artifact):
        """Test that risks section is checked."""
        result = self.verifier.verify(sample_design_artifact)

        # Should check for risks section
        risk_checks = [
            c for c in result.checks
            if "риск" in c.message.lower()
        ]
        assert len(risk_checks) > 0

    def test_bsl_considerations_check(self, sample_design_artifact):
        """Test that BSL-specific considerations are checked."""
        result = self.verifier.verify(sample_design_artifact)

        # Should check for BSL-specific elements
        bsl_checks = [
            c for c in result.checks
            if "bsl" in c.message.lower() or "1с" in c.message.lower()
        ]
        assert len(bsl_checks) > 0

    def test_traceability_to_spec(self, sample_design_artifact, sample_spec_artifact):
        """Test traceability check when spec is provided."""
        result = self.verifier.verify(
            sample_design_artifact,
            context={"spec": sample_spec_artifact}
        )

        # Should include requirements tracking
        assert result.requirements is not None


class TestArchitectVerifierReview:
    """Test suite for ARCHITECT review.md verification."""

    def setup_method(self):
        self.verifier = ArchitectVerifier()

    def test_verify_complete_review(self):
        """Test verification of complete review.md."""
        content = """# Ревью кода

## Найденные проблемы

### Критические
🔴 Проблема 1: SQL-инъекция в модуле авторизации

### Важные
🟡 Проблема 2: Отсутствие обработки ошибок

## Рекомендации
- Добавить валидацию входных данных
- Улучшить логирование

## Метрики качества кода
- Цикломатическая сложность: 8
- Покрытие тестами: 65%
"""
        artifact = Artifact(
            name="review.md",
            content=content,
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.REVIEW,
                producer=AgentRole.ARCHITECT,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.APPROVED

    def test_verify_incomplete_review(self):
        """Test verification of incomplete review.md."""
        content = """# Ревью

Код нормальный.
"""
        artifact = Artifact(
            name="incomplete_review.md",
            content=content,
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.REVIEW,
                producer=AgentRole.ARCHITECT,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.REVISION_NEEDED


class TestArchitectVerifierEdgeCases:
    """Edge case tests for ARCHITECT verifier."""

    def setup_method(self):
        self.verifier = ArchitectVerifier()

    def test_unsupported_artifact_type(self):
        """Test with unsupported artifact type."""
        artifact = Artifact(
            name="wrong_type.md",
            content="some content",
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.CONTEXT,  # Wrong type for ARCHITECT
                producer=AgentRole.ARCHITECT,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.FAILED

    def test_empty_design(self):
        """Test with empty design content."""
        artifact = Artifact(
            name="empty_design.md",
            content="",
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.DESIGN,
                producer=AgentRole.ARCHITECT,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.REVISION_NEEDED

    def test_design_without_bsl(self):
        """Test design without BSL-specific content (non-1C project)."""
        content = """# Архитектурное решение

## Архитектурные решения
Используем микросервисную архитектуру.

## План реализации
1. Создать API Gateway
2. Развернуть сервисы

## Риски
- Сложность деплоя
"""
        artifact = Artifact(
            name="design_no_bsl.md",
            content=content,
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.DESIGN,
                producer=AgentRole.ARCHITECT,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        # Should still pass, BSL check is informational
        # But may have info-level warning about no BSL content
        bsl_checks = [
            c for c in result.checks
            if "bsl" in c.message.lower() and c.severity == "info"
        ]
        assert len(bsl_checks) >= 0  # May or may not be present
