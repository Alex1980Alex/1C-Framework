"""
ARCHITECT Verifier for Development Pipeline.

Verifies artifacts produced by ARCHITECT agent:
- design.md (DESIGN mode)
- review.md (REVIEW mode)
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


class ArchitectVerifier(BaseVerifier):
    """Verifier for ARCHITECT agent artifacts."""

    def __init__(self) -> None:
        super().__init__(AgentRole.ARCHITECT, ArtifactType.DESIGN)

    def verify(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Verify ARCHITECT artifact based on its type.

        Args:
            artifact: The artifact to verify (design.md or review.md)
            context: Additional context (spec.md for traceability)

        Returns:
            VerificationResult with detailed checks
        """
        artifact_type = artifact.metadata.artifact_type

        if artifact_type == ArtifactType.DESIGN:
            return self._verify_design(artifact, context)
        elif artifact_type == ArtifactType.REVIEW:
            return self._verify_review(artifact, context)
        else:
            return VerificationResult(
                agent_role=self.agent_role,
                artifact_type=artifact_type,
                status=VerificationStatus.FAILED,
                summary=f"Неподдерживаемый тип артефакта: {artifact_type.value}",
            )

    def _verify_design(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify design.md artifact."""
        checks = []
        requirements = []
        recommendations = []

        # 1. Check structure
        checks.append(self.check_structure(artifact))

        # 2. Check architectural decisions section
        checks.append(self._check_architectural_decisions(artifact.content))

        # 3. Check change plan section
        checks.append(self._check_change_plan(artifact.content))

        # 4. Check risks section
        checks.append(self._check_risks_section(artifact.content))

        # 5. Check patterns alignment
        checks.append(self._check_patterns_alignment(artifact.content))

        # 6. Check BSL-specific considerations (for 1C projects)
        checks.append(self._check_bsl_considerations(artifact.content))

        # 7. Check traceability to spec if available
        if context and "spec" in context:
            spec_artifact = context["spec"]
            checks.append(self.check_traceability(spec_artifact, artifact))

            # Extract requirements from spec for requirement tracking
            extracted_reqs = self.extract_requirements(spec_artifact.content)
            for req in extracted_reqs:
                # Check if requirement is addressed in design
                is_addressed = (
                    req["id"] in artifact.content
                    or any(
                        kw.lower() in artifact.content.lower()
                        for kw in req["description"].split()[:3]
                        if len(kw) > 3
                    )
                )
                requirements.append(RequirementCheck(
                    requirement_id=req["id"],
                    description=req["description"],
                    status=(
                        RequirementStatus.PASSED
                        if is_addressed
                        else RequirementStatus.NOT_TESTED
                    ),
                    notes="Адресовано в дизайне" if is_addressed else "Ожидает реализации",
                ))

        # 8. Check implementation guidelines
        checks.append(self._check_implementation_guidelines(artifact.content))

        # Determine overall status
        failed_critical = any(
            not c.passed and c.severity == "error" for c in checks
        )

        status = (
            VerificationStatus.REVISION_NEEDED
            if failed_critical
            else VerificationStatus.APPROVED
        )

        # Recommendations
        if not self._has_section(artifact.content, "Альтернатив"):
            recommendations.append("Документировать рассмотренные альтернативы")

        if not self._has_section(artifact.content, "Зависимост"):
            recommendations.append("Указать зависимости между компонентами")

        return VerificationResult(
            agent_role=self.agent_role,
            artifact_type=ArtifactType.DESIGN,
            status=status,
            checks=checks,
            requirements=requirements,
            summary=self._generate_summary(checks),
            recommendations=recommendations,
        )

    def _verify_review(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify review.md artifact."""
        checks = []
        recommendations = []

        # 1. Check structure
        checks.append(self.check_structure(artifact))

        # 2. Check review findings section
        checks.append(self._check_review_findings(artifact.content))

        # 3. Check severity classification
        checks.append(self._check_severity_classification(artifact.content))

        # 4. Check recommendations section
        checks.append(self._check_recommendations_section(artifact.content))

        # 5. Check code quality metrics
        checks.append(self._check_code_quality_metrics(artifact.content))

        # 6. Check BSL-specific issues
        checks.append(self._check_bsl_issues(artifact.content))

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
            artifact_type=ArtifactType.REVIEW,
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

    def _check_architectural_decisions(self, content: str) -> CheckResult:
        """Check for architectural decisions section."""
        if self._has_section(content, "Архитектур"):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция архитектурных решений присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует секция архитектурных решений",
            severity="error",
        )

    def _check_change_plan(self, content: str) -> CheckResult:
        """Check for change plan section."""
        if (
            self._has_section(content, "План изменений")
            or self._has_section(content, "План реализации")
            or self._has_section(content, "Шаги реализации")
        ):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="План изменений присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует план изменений",
            severity="error",
        )

    def _check_risks_section(self, content: str) -> CheckResult:
        """Check for risks section."""
        if self._has_section(content, "Риск"):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция рисков присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Рекомендуется добавить секцию рисков",
            severity="warning",
        )

    def _check_patterns_alignment(self, content: str) -> CheckResult:
        """Check if design aligns with existing patterns."""
        pattern_indicators = [
            "паттерн", "шаблон", "стандарт", "подход",
            "существующ", "аналогичн", "как в",
        ]

        aligned = any(
            indicator in content.lower()
            for indicator in pattern_indicators
        )

        if aligned:
            return CheckResult(
                check_type=CheckType.CONSISTENCY,
                passed=True,
                message="Дизайн учитывает существующие паттерны",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.CONSISTENCY,
            passed=False,
            message="Не указано соответствие существующим паттернам",
            severity="warning",
        )

    def _check_bsl_considerations(self, content: str) -> CheckResult:
        """Check for BSL/1C-specific considerations."""
        bsl_keywords = [
            "модуль", "процедура", "функция", "запрос",
            "регистр", "справочник", "документ", "обработка",
            "1С", "1C", "BSL", "конфигурация",
        ]

        has_bsl = any(
            kw.lower() in content.lower()
            for kw in bsl_keywords
        )

        if has_bsl:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=True,
                message="BSL/1С аспекты учтены",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=False,
            message="Не найдены BSL/1С специфичные элементы (возможно не 1С проект)",
            severity="info",  # Info, not error, as project might not be 1C
        )

    def _check_implementation_guidelines(self, content: str) -> CheckResult:
        """Check for implementation guidelines."""
        guideline_indicators = [
            "реализац", "implement", "создать", "добавить",
            "изменить", "обновить", "модифициров",
        ]

        has_guidelines = any(
            indicator in content.lower()
            for indicator in guideline_indicators
        )

        if has_guidelines:
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Указания по реализации присутствуют",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствуют конкретные указания по реализации",
            severity="warning",
        )

    def _check_review_findings(self, content: str) -> CheckResult:
        """Check for review findings in review.md."""
        if (
            self._has_section(content, "Найден")
            or self._has_section(content, "Замечан")
            or self._has_section(content, "Проблем")
            or self._has_section(content, "Finding")
        ):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция результатов ревью присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствуют результаты ревью",
            severity="error",
        )

    def _check_severity_classification(self, content: str) -> CheckResult:
        """Check for severity classification in findings."""
        severity_indicators = [
            "критич", "важн", "minor", "major", "blocker",
            "высок", "средн", "низк", "🔴", "🟡", "🟢",
        ]

        has_severity = any(
            indicator in content.lower()
            for indicator in severity_indicators
        )

        if has_severity:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=True,
                message="Классификация по серьёзности присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=False,
            message="Рекомендуется классифицировать замечания по серьёзности",
            severity="warning",
        )

    def _check_recommendations_section(self, content: str) -> CheckResult:
        """Check for recommendations in review."""
        if self._has_section(content, "Рекомендац"):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция рекомендаций присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствуют рекомендации по улучшению",
            severity="warning",
        )

    def _check_code_quality_metrics(self, content: str) -> CheckResult:
        """Check for code quality metrics in review."""
        metric_keywords = [
            "сложност", "покрыти", "дублирован",
            "качеств", "метрик", "оценк",
        ]

        has_metrics = any(
            kw in content.lower()
            for kw in metric_keywords
        )

        if has_metrics:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=True,
                message="Метрики качества кода присутствуют",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=False,
            message="Рекомендуется добавить метрики качества кода",
            severity="info",
        )

    def _check_bsl_issues(self, content: str) -> CheckResult:
        """Check for BSL-specific issues in review."""
        bsl_issue_keywords = [
            "запрос", "индекс", "блокировк", "транзакци",
            "регистр", "права", "производительност",
        ]

        has_bsl_issues = any(
            kw in content.lower()
            for kw in bsl_issue_keywords
        )

        if has_bsl_issues:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=True,
                message="BSL-специфичные проблемы рассмотрены",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=False,
            message="Не найдены BSL-специфичные проверки",
            severity="info",  # Info, not error
        )

    def _generate_summary(self, checks: List[CheckResult]) -> str:
        """Generate summary from checks."""
        passed = sum(1 for c in checks if c.passed)
        total = len(checks)
        errors = [c.message for c in checks if not c.passed and c.severity == "error"]

        if errors:
            return f"Проверка не пройдена ({passed}/{total}). Ошибки: {'; '.join(errors)}"
        return f"Проверка пройдена ({passed}/{total})"
