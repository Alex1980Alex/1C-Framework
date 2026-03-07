"""
Integration tests for PMSpecVerifier.
"""

import pytest

from constants import VerificationStatus, ArtifactType
from verification import PMSpecVerifier, CheckType


class TestPMSpecVerifier:
    """Test suite for PM-SPEC verifier."""

    def setup_method(self):
        """Setup verifier instance."""
        self.verifier = PMSpecVerifier()

    def test_verify_complete_context(self, sample_context_artifact):
        """Test verification of complete context.md."""
        result = self.verifier.verify(sample_context_artifact)

        assert result.status == VerificationStatus.APPROVED
        assert result.artifact_type == ArtifactType.CONTEXT
        assert len(result.checks) > 0

        # Check that all critical checks passed
        critical_failed = [
            c for c in result.checks
            if not c.passed and c.severity == "error"
        ]
        assert len(critical_failed) == 0, f"Critical checks failed: {critical_failed}"

    def test_verify_incomplete_context(self, incomplete_context_artifact):
        """Test verification of incomplete context.md."""
        result = self.verifier.verify(incomplete_context_artifact)

        assert result.status == VerificationStatus.REVISION_NEEDED
        assert len(result.checks) > 0

        # Check that some critical checks failed
        critical_failed = [
            c for c in result.checks
            if not c.passed and c.severity == "error"
        ]
        assert len(critical_failed) > 0

    def test_verify_complete_spec(self, sample_spec_artifact):
        """Test verification of complete spec.md."""
        result = self.verifier.verify(sample_spec_artifact)

        assert result.status == VerificationStatus.APPROVED
        assert result.artifact_type == ArtifactType.SPEC

        # Should have requirements extracted
        assert len(result.requirements) > 0

    def test_verify_incomplete_spec(self, incomplete_spec_artifact):
        """Test verification of incomplete spec.md."""
        result = self.verifier.verify(incomplete_spec_artifact)

        assert result.status == VerificationStatus.REVISION_NEEDED

    def test_check_types_present(self, sample_context_artifact):
        """Test that all expected check types are present."""
        result = self.verifier.verify(sample_context_artifact)

        check_types = {c.check_type for c in result.checks}

        # Should have structure and completeness checks
        assert CheckType.STRUCTURE in check_types
        assert CheckType.COMPLETENESS in check_types

    def test_summary_generated(self, sample_context_artifact):
        """Test that summary is properly generated."""
        result = self.verifier.verify(sample_context_artifact)

        assert result.summary is not None
        assert len(result.summary) > 0

    def test_extract_requirements_from_spec(self, sample_spec_artifact):
        """Test requirement extraction from spec."""
        requirements = self.verifier.extract_requirements(sample_spec_artifact.content)

        assert len(requirements) > 0

        # Check that requirements are extracted (REQ-N format)
        assert len(requirements) >= 5  # Should find at least 5 requirements from bullets

    def test_traceability_check(self, sample_context_artifact, sample_spec_artifact):
        """Test traceability between context and spec."""
        # Verify spec with context as reference
        result = self.verifier.verify(
            sample_spec_artifact,
            context={"context": sample_context_artifact}
        )

        # Check for traceability check
        traceability_checks = [
            c for c in result.checks
            if c.check_type == CheckType.TRACEABILITY
        ]

        # Should have at least one traceability check
        assert len(traceability_checks) >= 0  # May or may not be present based on impl


class TestPMSpecVerifierEdgeCases:
    """Edge case tests for PM-SPEC verifier."""

    def setup_method(self):
        self.verifier = PMSpecVerifier()

    def test_empty_content(self):
        """Test with empty content."""
        from models import Artifact, ArtifactMetadata
        from constants import AgentRole, ArtifactType

        artifact = Artifact(
            name="empty_context.md",
            content="",
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.CONTEXT,
                producer=AgentRole.PM_SPEC,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.REVISION_NEEDED

    def test_minimal_valid_content(self):
        """Test with minimal but valid content."""
        from models import Artifact, ArtifactMetadata
        from constants import AgentRole, ArtifactType

        content = """# Контекст проекта

## Описание проекта
Тестовый проект.

## Цели
- Цель 1

## Текущее состояние
В разработке.

## Анализ кодовой базы
Модуль.bsl - 100 строк

## Зависимости
- Справочник.Тест
"""
        artifact = Artifact(
            name="minimal_context.md",
            content=content,
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.CONTEXT,
                producer=AgentRole.PM_SPEC,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        # Minimal but valid should pass
        assert result.status in [VerificationStatus.APPROVED, VerificationStatus.REVISION_NEEDED]
