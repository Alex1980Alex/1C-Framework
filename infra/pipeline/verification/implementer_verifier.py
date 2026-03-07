"""
IMPLEMENTER Verifier for Development Pipeline.

Verifies artifacts produced by IMPLEMENTER agent:
- result.md (BUILD mode)
- qa_report.md (after QA)
"""

import re
from typing import Any, Dict, List, Optional

from constants import AgentRole, ArtifactType, RequirementStatus, VerificationStatus
from models import Artifact
from .base_verifier import (
    BaseVerifier,
    CheckResult,
    CheckType,
    RequirementCheck,
    VerificationResult,
)


class ImplementerVerifier(BaseVerifier):
    """Verifier for IMPLEMENTER agent artifacts."""

    def __init__(self) -> None:
        super().__init__(AgentRole.IMPLEMENTER, ArtifactType.RESULT)

    def verify(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Verify IMPLEMENTER artifact based on its type.

        Args:
            artifact: The artifact to verify (result.md or qa_report.md)
            context: Additional context (spec.md, design.md for traceability)

        Returns:
            VerificationResult with detailed checks
        """
        artifact_type = artifact.metadata.artifact_type

        if artifact_type == ArtifactType.RESULT:
            return self._verify_result(artifact, context)
        elif artifact_type == ArtifactType.QA_REPORT:
            return self._verify_qa_report(artifact, context)
        else:
            return VerificationResult(
                agent_role=self.agent_role,
                artifact_type=artifact_type,
                status=VerificationStatus.FAILED,
                summary=f"Неподдерживаемый тип артефакта: {artifact_type.value}",
            )

    def _verify_result(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify result.md artifact."""
        checks = []
        requirements = []
        recommendations = []

        # 1. Check structure
        checks.append(self.check_structure(artifact))

        # 2. Check completed steps section
        checks.append(self._check_completed_steps(artifact.content))

        # 3. Check created/modified files section
        checks.append(self._check_files_section(artifact.content))

        # 4. Check code snippets
        checks.append(self._check_code_snippets(artifact.content))

        # 5. Check testing section
        checks.append(self._check_testing_section(artifact.content))

        # 6. Check BSL code quality indicators
        checks.append(self._check_bsl_code_quality(artifact.content))

        # 7. Check documentation updates
        checks.append(self._check_documentation_updates(artifact.content))

        # 8. Check traceability to spec if available
        if context and "spec" in context:
            spec_artifact = context["spec"]
            checks.append(self.check_traceability(spec_artifact, artifact))

            # Check each requirement from spec
            extracted_reqs = self.extract_requirements(spec_artifact.content)
            for req in extracted_reqs:
                status = self._check_requirement_implementation(
                    req, artifact.content
                )
                requirements.append(RequirementCheck(
                    requirement_id=req["id"],
                    description=req["description"],
                    status=status,
                    notes=self._get_requirement_notes(status),
                ))

        # 9. Check traceability to design if available
        if context and "design" in context:
            design_artifact = context["design"]
            checks.append(self._check_design_alignment(artifact.content, design_artifact.content))

        # 10. Check error handling
        checks.append(self._check_error_handling(artifact.content))

        # Determine overall status
        failed_critical = any(
            not c.passed and c.severity == "error" for c in checks
        )

        failed_requirements = any(
            r.status == RequirementStatus.FAILED for r in requirements
        )

        if failed_critical or failed_requirements:
            status = VerificationStatus.REVISION_NEEDED
        else:
            status = VerificationStatus.APPROVED

        # Recommendations
        if not self._has_section(artifact.content, "Тестирован"):
            recommendations.append("Добавить результаты тестирования")

        if not self._has_section(artifact.content, "Документац"):
            recommendations.append("Обновить документацию по изменениям")

        return VerificationResult(
            agent_role=self.agent_role,
            artifact_type=ArtifactType.RESULT,
            status=status,
            checks=checks,
            requirements=requirements,
            summary=self._generate_summary(checks, requirements),
            recommendations=recommendations,
        )

    def _verify_qa_report(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify qa_report.md artifact."""
        checks = []
        recommendations = []

        # 1. Check structure
        checks.append(self.check_structure(artifact))

        # 2. Check test results section
        checks.append(self._check_test_results(artifact.content))

        # 3. Check coverage section
        checks.append(self._check_coverage_section(artifact.content))

        # 4. Check issues found section
        checks.append(self._check_issues_found(artifact.content))

        # 5. Check verdict section
        checks.append(self._check_qa_verdict(artifact.content))

        # Determine overall status
        failed_critical = any(
            not c.passed and c.severity == "error" for c in checks
        )

        status = (
            VerificationStatus.REVISION_NEEDED
            if failed_critical
            else VerificationStatus.APPROVED
        )

        return VerificationResult(
            agent_role=self.agent_role,
            artifact_type=ArtifactType.QA_REPORT,
            status=status,
            checks=checks,
            summary=self._generate_summary(checks),
            recommendations=recommendations,
        )

    # Helper methods

    def _has_section(self, content: str, section_name: str) -> bool:
        """Check if content has a section with given name."""
        pattern = rf"##?\s*.*{section_name}"
        return bool(re.search(pattern, content, re.IGNORECASE))

    def _check_completed_steps(self, content: str) -> CheckResult:
        """Check for completed steps section."""
        if (
            self._has_section(content, "Выполненные шаги")
            or self._has_section(content, "Реализовано")
            or self._has_section(content, "Изменения")
        ):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция выполненных шагов присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует секция выполненных шагов",
            severity="error",
        )

    def _check_files_section(self, content: str) -> CheckResult:
        """Check for created/modified files section."""
        # Look for file paths or file listings
        file_patterns = [
            r"\.bsl", r"\.py", r"\.js", r"\.ts", r"\.md",
            r"Создан", r"Изменён", r"Добавлен", r"Удалён",
        ]

        has_files = any(
            re.search(pattern, content, re.IGNORECASE)
            for pattern in file_patterns
        )

        if has_files:
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Информация о файлах присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует информация об изменённых файлах",
            severity="error",
        )

    def _check_code_snippets(self, content: str) -> CheckResult:
        """Check for code snippets in result."""
        # Look for code blocks
        code_block_pattern = r"```(?:bsl|python|javascript|typescript|1c)?"

        has_code = bool(re.search(code_block_pattern, content, re.IGNORECASE))

        if has_code:
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Примеры кода присутствуют",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Рекомендуется добавить примеры кода",
            severity="info",  # Just a recommendation
        )

    def _check_testing_section(self, content: str) -> CheckResult:
        """Check for testing section."""
        testing_keywords = [
            "тест", "проверк", "валидац", "test",
            "✅", "❌", "пройден", "провален",
        ]

        has_testing = any(
            kw in content.lower()
            for kw in testing_keywords
        )

        if has_testing:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=True,
                message="Информация о тестировании присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=False,
            message="Отсутствует информация о тестировании",
            severity="warning",
        )

    def _check_bsl_code_quality(self, content: str) -> CheckResult:
        """Check BSL code quality indicators in result."""
        quality_indicators = [
            "Попытка", "Исключение",  # Error handling
            "Транзакци",              # Transaction management
            "Запрос",                 # Query optimization
            "Индекс",                 # Index usage
        ]

        mentioned = [
            ind for ind in quality_indicators
            if ind.lower() in content.lower()
        ]

        if len(mentioned) >= 2:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=True,
                message=f"BSL качество учтено: {', '.join(mentioned)}",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=False,
            message="Рекомендуется проверить BSL качество (обработка ошибок, транзакции)",
            severity="info",
        )

    def _check_documentation_updates(self, content: str) -> CheckResult:
        """Check if documentation was updated."""
        doc_keywords = [
            "документац", "readme", "комментар", "описани",
            "docstring", "jsdoc",
        ]

        has_docs = any(
            kw in content.lower()
            for kw in doc_keywords
        )

        if has_docs:
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Документация обновлена",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Нет информации об обновлении документации",
            severity="warning",
        )

    def _check_design_alignment(self, result_content: str, design_content: str) -> CheckResult:
        """Check if result aligns with design."""
        # Extract key terms from design
        design_terms = re.findall(r"[А-Яа-яA-Za-z]{5,}", design_content)
        design_terms = list(set(design_terms))[:20]  # Take first 20 unique terms

        # Check how many are mentioned in result
        mentioned = sum(
            1 for term in design_terms
            if term.lower() in result_content.lower()
        )

        ratio = mentioned / len(design_terms) if design_terms else 0

        if ratio >= 0.3:  # At least 30% of design terms mentioned
            return CheckResult(
                check_type=CheckType.CONSISTENCY,
                passed=True,
                message=f"Результат соответствует дизайну ({mentioned}/{len(design_terms)} терминов)",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.CONSISTENCY,
            passed=False,
            message=f"Возможное расхождение с дизайном ({mentioned}/{len(design_terms)} терминов)",
            severity="warning",
        )

    def _check_error_handling(self, content: str) -> CheckResult:
        """Check if error handling was considered."""
        error_keywords = [
            "ошибк", "исключен", "error", "exception",
            "try", "catch", "попытка",
        ]

        has_error_handling = any(
            kw in content.lower()
            for kw in error_keywords
        )

        if has_error_handling:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=True,
                message="Обработка ошибок учтена",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=False,
            message="Нет информации об обработке ошибок",
            severity="warning",
        )

    def _check_requirement_implementation(
        self,
        requirement: Dict[str, str],
        result_content: str,
    ) -> RequirementStatus:
        """Check if a specific requirement is implemented."""
        req_id = requirement["id"]
        description = requirement["description"]

        # Check if requirement ID is explicitly mentioned
        if req_id in result_content:
            # Check for success indicators
            success_pattern = rf"{req_id}.*(?:✅|выполнен|реализован|готов)"
            failure_pattern = rf"{req_id}.*(?:❌|не выполнен|отложен|пропущен)"

            if re.search(success_pattern, result_content, re.IGNORECASE):
                return RequirementStatus.PASSED
            elif re.search(failure_pattern, result_content, re.IGNORECASE):
                return RequirementStatus.FAILED
            else:
                return RequirementStatus.WARNING  # Mentioned but status unclear

        # Check for keywords from description
        keywords = [
            w for w in description.split()
            if len(w) > 3 and w.isalpha()
        ][:5]  # First 5 significant words

        matched = sum(
            1 for kw in keywords
            if kw.lower() in result_content.lower()
        )

        if matched >= 2:
            return RequirementStatus.PASSED  # Likely addressed
        elif matched == 1:
            return RequirementStatus.WARNING  # Partially addressed
        else:
            return RequirementStatus.NOT_TESTED  # Not clearly addressed

    def _get_requirement_notes(self, status: RequirementStatus) -> str:
        """Get notes for requirement status."""
        notes = {
            RequirementStatus.PASSED: "Реализовано",
            RequirementStatus.FAILED: "Не реализовано",
            RequirementStatus.WARNING: "Требует проверки",
            RequirementStatus.NOT_TESTED: "Не найдено в результате",
        }
        return notes.get(status, "")

    def _check_test_results(self, content: str) -> CheckResult:
        """Check for test results in QA report."""
        if (
            self._has_section(content, "Результаты тест")
            or self._has_section(content, "Тесты")
        ):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Результаты тестов присутствуют",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствуют результаты тестов",
            severity="error",
        )

    def _check_coverage_section(self, content: str) -> CheckResult:
        """Check for coverage section in QA report."""
        coverage_keywords = ["покрыти", "coverage", "%", "процент"]

        has_coverage = any(
            kw in content.lower()
            for kw in coverage_keywords
        )

        if has_coverage:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=True,
                message="Информация о покрытии присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=False,
            message="Нет информации о покрытии тестами",
            severity="warning",
        )

    def _check_issues_found(self, content: str) -> CheckResult:
        """Check for issues section in QA report."""
        if (
            self._has_section(content, "Проблем")
            or self._has_section(content, "Ошибк")
            or self._has_section(content, "Issue")
        ):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция проблем присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует секция найденных проблем",
            severity="warning",
        )

    def _check_qa_verdict(self, content: str) -> CheckResult:
        """Check for QA verdict in report."""
        verdict_keywords = [
            "вердикт", "итог", "заключен", "рекоменд",
            "approved", "rejected", "passed", "failed",
        ]

        has_verdict = any(
            kw in content.lower()
            for kw in verdict_keywords
        )

        if has_verdict:
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Вердикт QA присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует вердикт QA",
            severity="error",
        )

    def _generate_summary(
        self,
        checks: List[CheckResult],
        requirements: Optional[List[RequirementCheck]] = None,
    ) -> str:
        """Generate summary from checks and requirements."""
        passed_checks = sum(1 for c in checks if c.passed)
        total_checks = len(checks)
        errors = [c.message for c in checks if not c.passed and c.severity == "error"]

        summary_parts = [f"Проверок: {passed_checks}/{total_checks}"]

        if requirements:
            passed_reqs = sum(
                1 for r in requirements
                if r.status == RequirementStatus.PASSED
            )
            summary_parts.append(f"Требований: {passed_reqs}/{len(requirements)}")

        if errors:
            summary_parts.append(f"Ошибки: {'; '.join(errors)}")
            return " | ".join(summary_parts)

        return " | ".join(summary_parts) + " ✅"
