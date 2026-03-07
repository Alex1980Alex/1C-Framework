"""
PM-SPEC Verifier for Development Pipeline.

Verifies artifacts produced by PM-SPEC agent:
- context.md (INIT mode)
- spec.md (SPEC mode)
- verification.md (VERIFY mode)
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


class PMSpecVerifier(BaseVerifier):
    """Verifier for PM-SPEC agent artifacts."""

    def __init__(self) -> None:
        super().__init__(AgentRole.PM_SPEC, ArtifactType.SPEC)

    def verify(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """
        Verify PM-SPEC artifact based on its type.

        Args:
            artifact: The artifact to verify (context.md, spec.md, or verification.md)
            context: Additional context for verification

        Returns:
            VerificationResult with detailed checks
        """
        artifact_type = artifact.metadata.artifact_type

        if artifact_type == ArtifactType.CONTEXT:
            return self._verify_context(artifact, context)
        elif artifact_type == ArtifactType.SPEC:
            return self._verify_spec(artifact, context)
        elif artifact_type == ArtifactType.VERIFICATION:
            return self._verify_verification(artifact, context)
        else:
            return VerificationResult(
                agent_role=self.agent_role,
                artifact_type=artifact_type,
                status=VerificationStatus.FAILED,
                summary=f"Неподдерживаемый тип артефакта: {artifact_type.value}",
            )

    def _verify_context(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify context.md artifact."""
        checks = []
        recommendations = []

        # 1. Check structure
        checks.append(self.check_structure(artifact))

        # 2. Check project structure section
        checks.append(self._check_project_structure(artifact.content))

        # 3. Check key files section
        checks.append(self._check_key_files(artifact.content))

        # 4. Check patterns section
        checks.append(self._check_patterns(artifact.content))

        # 5. Check relevance section
        checks.append(self._check_relevant_modules(artifact.content))

        # Determine overall status
        failed_critical = any(
            not c.passed and c.severity == "error" for c in checks
        )

        status = (
            VerificationStatus.REVISION_NEEDED
            if failed_critical
            else VerificationStatus.APPROVED
        )

        # Add recommendations
        if not self._has_section(artifact.content, "Зависимости"):
            recommendations.append("Добавить секцию 'Зависимости' для полноты контекста")

        if not self._has_section(artifact.content, "Паттерны"):
            recommendations.append("Документировать существующие паттерны кода")

        return VerificationResult(
            agent_role=self.agent_role,
            artifact_type=ArtifactType.CONTEXT,
            status=status,
            checks=checks,
            summary=self._generate_summary(checks),
            recommendations=recommendations,
        )

    def _verify_spec(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify spec.md artifact."""
        checks = []
        requirements = []
        recommendations = []

        # 1. Check structure
        checks.append(self.check_structure(artifact))

        # 2. Check goal section
        checks.append(self._check_goal_section(artifact.content))

        # 3. Check requirements section
        req_check, extracted_reqs = self._check_requirements_section(artifact.content)
        checks.append(req_check)

        # 4. Check acceptance criteria section
        ac_check, extracted_acs = self._check_acceptance_criteria_section(artifact.content)
        checks.append(ac_check)

        # 5. Check out of scope section
        checks.append(self._check_out_of_scope(artifact.content))

        # 6. Check measurability of requirements
        checks.append(self._check_requirements_measurability(extracted_reqs))

        # Build requirements list
        for req in extracted_reqs:
            requirements.append(RequirementCheck(
                requirement_id=req["id"],
                description=req["description"],
                status=RequirementStatus.NOT_TESTED,
                notes="Ожидает реализации",
            ))

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
        if len(extracted_reqs) == 0:
            recommendations.append("Добавить явные требования в формате REQ-N")

        if len(extracted_acs) == 0:
            recommendations.append("Добавить критерии приёмки в формате AC-N")

        if not self._has_section(artifact.content, "Контекст"):
            recommendations.append("Добавить ссылку на context.md")

        return VerificationResult(
            agent_role=self.agent_role,
            artifact_type=ArtifactType.SPEC,
            status=status,
            checks=checks,
            requirements=requirements,
            summary=self._generate_summary(checks),
            recommendations=recommendations,
        )

    def _verify_verification(
        self,
        artifact: Artifact,
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Verify verification.md artifact."""
        checks = []
        recommendations = []

        # 1. Check structure
        checks.append(self.check_structure(artifact))

        # 2. Check verdict section
        checks.append(self._check_verdict_section(artifact.content))

        # 3. Check requirements table
        checks.append(self._check_requirements_table(artifact.content))

        # 4. Check acceptance criteria table
        checks.append(self._check_acceptance_criteria_table(artifact.content))

        # 5. If context provided with spec, check traceability
        if context and "spec" in context:
            spec_artifact = context["spec"]
            checks.append(self.check_traceability(spec_artifact, artifact))

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
            artifact_type=ArtifactType.VERIFICATION,
            status=status,
            checks=checks,
            summary=self._generate_summary(checks),
            recommendations=recommendations,
        )

    # Helper methods

    def _has_section(self, content: str, section_name: str) -> bool:
        """Check if content has a section with given name."""
        pattern = rf"##?\s*{section_name}"
        return bool(re.search(pattern, content, re.IGNORECASE))

    def _check_project_structure(self, content: str) -> CheckResult:
        """Check for project structure section."""
        if self._has_section(content, "Структура"):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция структуры проекта присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует секция структуры проекта",
            severity="error",
        )

    def _check_key_files(self, content: str) -> CheckResult:
        """Check for key files section."""
        if self._has_section(content, "Ключевые файлы") or self._has_section(content, "Файлы"):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция ключевых файлов присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует секция ключевых файлов",
            severity="warning",
        )

    def _check_patterns(self, content: str) -> CheckResult:
        """Check for patterns section."""
        if self._has_section(content, "Паттерн"):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция паттернов присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует секция паттернов (рекомендуется)",
            severity="info",
        )

    def _check_relevant_modules(self, content: str) -> CheckResult:
        """Check for relevant modules section."""
        if (
            self._has_section(content, "Релевантные")
            or self._has_section(content, "Связанные модули")
            or self._has_section(content, "Затрагиваемые")
        ):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция релевантных модулей присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует секция релевантных модулей",
            severity="warning",
        )

    def _check_goal_section(self, content: str) -> CheckResult:
        """Check for goal section in spec."""
        if self._has_section(content, "Цель"):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция цели присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует секция цели",
            severity="error",
        )

    def _check_requirements_section(self, content: str) -> tuple[CheckResult, List[Dict]]:
        """Check requirements section and extract requirements."""
        requirements = self.extract_requirements(content)

        if requirements:
            return (
                CheckResult(
                    check_type=CheckType.COMPLETENESS,
                    passed=True,
                    message=f"Найдено требований: {len(requirements)}",
                    details={"count": len(requirements)},
                    severity="info",
                ),
                requirements,
            )

        return (
            CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=False,
                message="Требования не найдены",
                severity="error",
            ),
            [],
        )

    def _check_acceptance_criteria_section(self, content: str) -> tuple[CheckResult, List[Dict]]:
        """Check acceptance criteria section and extract criteria."""
        criteria = self.extract_acceptance_criteria(content)

        if criteria:
            return (
                CheckResult(
                    check_type=CheckType.COMPLETENESS,
                    passed=True,
                    message=f"Найдено критериев приёмки: {len(criteria)}",
                    details={"count": len(criteria)},
                    severity="info",
                ),
                criteria,
            )

        return (
            CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=False,
                message="Критерии приёмки не найдены",
                severity="warning",
            ),
            [],
        )

    def _check_out_of_scope(self, content: str) -> CheckResult:
        """Check for out of scope section."""
        if self._has_section(content, "Вне скоупа") or self._has_section(content, "Ограничения"):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Секция ограничений присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Рекомендуется добавить секцию 'Вне скоупа'",
            severity="info",
        )

    def _check_requirements_measurability(self, requirements: List[Dict]) -> CheckResult:
        """Check that requirements are measurable."""
        vague_keywords = [
            "быстро", "хорошо", "удобно", "красиво", "нормально",
            "лучше", "оптимально", "эффективно",
        ]

        vague_reqs = []
        for req in requirements:
            desc_lower = req["description"].lower()
            if any(kw in desc_lower for kw in vague_keywords):
                vague_reqs.append(req["id"])

        if vague_reqs:
            return CheckResult(
                check_type=CheckType.QUALITY,
                passed=False,
                message=f"Нечёткие требования: {', '.join(vague_reqs)}",
                details={"vague_requirements": vague_reqs},
                severity="warning",
            )

        return CheckResult(
            check_type=CheckType.QUALITY,
            passed=True,
            message="Требования измеримы",
            severity="info",
        )

    def _check_verdict_section(self, content: str) -> CheckResult:
        """Check for verdict in verification.md."""
        if "APPROVED" in content or "REVISION_NEEDED" in content:
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Вердикт присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Вердикт отсутствует",
            severity="error",
        )

    def _check_requirements_table(self, content: str) -> CheckResult:
        """Check for requirements verification table."""
        if re.search(r"\|.*REQ.*\|", content, re.IGNORECASE):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Таблица проверки требований присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует таблица проверки требований",
            severity="warning",
        )

    def _check_acceptance_criteria_table(self, content: str) -> CheckResult:
        """Check for acceptance criteria verification table."""
        if re.search(r"\|.*AC.*\|", content, re.IGNORECASE):
            return CheckResult(
                check_type=CheckType.COMPLETENESS,
                passed=True,
                message="Таблица проверки критериев присутствует",
                severity="info",
            )
        return CheckResult(
            check_type=CheckType.COMPLETENESS,
            passed=False,
            message="Отсутствует таблица проверки критериев",
            severity="warning",
        )

    def _generate_summary(self, checks: List[CheckResult]) -> str:
        """Generate summary from checks."""
        passed = sum(1 for c in checks if c.passed)
        total = len(checks)
        errors = [c.message for c in checks if not c.passed and c.severity == "error"]

        if errors:
            return f"Проверка не пройдена ({passed}/{total}). Ошибки: {'; '.join(errors)}"
        return f"Проверка пройдена ({passed}/{total})"
