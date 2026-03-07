"""
Integration tests for ImplementerVerifier.
"""

import pytest

from constants import VerificationStatus, ArtifactType, AgentRole
from models import Artifact, ArtifactMetadata
from verification import ImplementerVerifier, CheckType


class TestImplementerVerifier:
    """Test suite for IMPLEMENTER verifier."""

    def setup_method(self):
        """Setup verifier instance."""
        self.verifier = ImplementerVerifier()

    def test_verify_complete_result(self, sample_result_artifact):
        """Test verification of complete result.md."""
        result = self.verifier.verify(sample_result_artifact)

        assert result.status == VerificationStatus.APPROVED
        assert result.artifact_type == ArtifactType.RESULT
        assert len(result.checks) > 0

        # Check that all critical checks passed
        critical_failed = [
            c for c in result.checks
            if not c.passed and c.severity == "error"
        ]
        assert len(critical_failed) == 0, f"Critical checks failed: {critical_failed}"

    def test_verify_incomplete_result(self):
        """Test verification of incomplete result.md."""
        content = """# Результат

Сделал какие-то изменения.
"""
        artifact = Artifact(
            name="incomplete_result.md",
            content=content,
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.RESULT,
                producer=AgentRole.IMPLEMENTER,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.REVISION_NEEDED

    def test_changed_files_check(self, sample_result_artifact):
        """Test that changed files section is checked."""
        result = self.verifier.verify(sample_result_artifact)

        # Should have check for changed files
        file_checks = [
            c for c in result.checks
            if "файл" in c.message.lower() or "изменен" in c.message.lower()
        ]
        assert len(file_checks) > 0

    def test_code_implementation_check(self, sample_result_artifact):
        """Test that code implementation is checked."""
        result = self.verifier.verify(sample_result_artifact)

        # Should check for code blocks
        code_checks = [
            c for c in result.checks
            if "код" in c.message.lower() or "реализаци" in c.message.lower()
        ]
        assert len(code_checks) > 0

    def test_requirements_fulfillment_check(self, sample_result_artifact, sample_spec_artifact):
        """Test requirements fulfillment when spec is provided."""
        result = self.verifier.verify(
            sample_result_artifact,
            context={"spec": sample_spec_artifact}
        )

        # Should track requirements
        assert result.requirements is not None

    def test_testing_evidence_check(self, sample_result_artifact):
        """Test that testing evidence is checked."""
        result = self.verifier.verify(sample_result_artifact)

        # Should check for testing section
        test_checks = [
            c for c in result.checks
            if "тест" in c.message.lower()
        ]
        assert len(test_checks) > 0


class TestImplementerVerifierQAReport:
    """Test suite for IMPLEMENTER qa_report.md verification."""

    def setup_method(self):
        self.verifier = ImplementerVerifier()

    def test_verify_complete_qa_report(self):
        """Test verification of complete qa_report.md."""
        content = """# QA Отчёт

## Результаты тестирования

### Unit-тесты
- Всего: 25
- Пройдено: 24
- Провалено: 1

### Интеграционные тесты
- Всего: 10
- Пройдено: 10

## Покрытие кода
- Общее покрытие: 78%
- Критические модули: 95%

## Найденные дефекты
- BUG-001: Некорректная валидация (Исправлено)

## Рекомендации
Готово к релизу после исправления BUG-001.
"""
        artifact = Artifact(
            name="qa_report.md",
            content=content,
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.QA_REPORT,
                producer=AgentRole.IMPLEMENTER,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.APPROVED

    def test_verify_incomplete_qa_report(self):
        """Test verification of incomplete qa_report.md."""
        content = """# QA

Тесты прошли.
"""
        artifact = Artifact(
            name="incomplete_qa_report.md",
            content=content,
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.QA_REPORT,
                producer=AgentRole.IMPLEMENTER,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.REVISION_NEEDED


class TestImplementerVerifierEdgeCases:
    """Edge case tests for IMPLEMENTER verifier."""

    def setup_method(self):
        self.verifier = ImplementerVerifier()

    def test_result_without_code(self):
        """Test result without code blocks."""
        content = """# Результат реализации

## Изменённые файлы
- Module.bsl

## Описание изменений
Добавлена новая функциональность.

## Тестирование
Протестировано вручную.
"""
        artifact = Artifact(
            name="result_no_code.md",
            content=content,
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.RESULT,
                producer=AgentRole.IMPLEMENTER,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        # Should warn about missing code but may still pass
        code_warning = any(
            "код" in c.message.lower() and c.severity == "warning"
            for c in result.checks
        )
        # Either warning present or status is revision_needed
        assert code_warning or result.status == VerificationStatus.REVISION_NEEDED

    def test_result_with_bsl_code(self, sample_result_artifact):
        """Test result with BSL code blocks."""
        result = self.verifier.verify(sample_result_artifact)

        # Should detect BSL code
        bsl_checks = [
            c for c in result.checks
            if "bsl" in c.message.lower() or "процедур" in c.message.lower()
        ]
        assert len(bsl_checks) > 0

    def test_empty_result(self):
        """Test with empty result content."""
        artifact = Artifact(
            name="empty_result.md",
            content="",
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.RESULT,
                producer=AgentRole.IMPLEMENTER,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.REVISION_NEEDED

    def test_unsupported_artifact_type(self):
        """Test with unsupported artifact type."""
        artifact = Artifact(
            name="wrong_type.md",
            content="some content",
            metadata=ArtifactMetadata(
                artifact_type=ArtifactType.DESIGN,  # Wrong type for IMPLEMENTER
                producer=AgentRole.IMPLEMENTER,
                tags={"project_id": "test", "task_id": "test"},
                version=1,
            ),
        )

        result = self.verifier.verify(artifact)
        assert result.status == VerificationStatus.FAILED
