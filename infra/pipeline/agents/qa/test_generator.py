"""
Test Generator for QA Agent.

Generates test cases based on spec.md requirements and result.md analysis.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from enum import Enum
import re

from agents.qa.models import TestCase, TestType, TestSuite
from agents.qa.result_analyzer import AnalysisResult, ImplementedFunction


class TestCategory(Enum):
    """Test categories."""
    POSITIVE = "positive"      # Normal flow
    NEGATIVE = "negative"      # Error handling
    BOUNDARY = "boundary"      # Edge cases
    INTEGRATION = "integration"  # Component interaction


@dataclass
class Requirement:
    """Represents a requirement from spec.md."""
    id: str
    description: str
    priority: int = 3
    acceptance_criteria: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "id": self.id,
            "description": self.description,
            "priority": self.priority,
            "acceptance_criteria": self.acceptance_criteria,
        }


class TestGenerator:
    """
    Generates test cases for QA Agent.

    Based on:
    - Requirements from spec.md
    - Implemented functions from result.md analysis

    Usage:
        generator = TestGenerator()
        generator.load_spec(spec_content)
        generator.load_analysis(analysis_result)
        suite = generator.generate()
    """

    # Patterns for parsing spec.md
    REQUIREMENT_PATTERN = re.compile(
        r'[-*]\s*(REQ-\d+|ТРБ-\d+)[:\s]+(.+)',
        re.IGNORECASE
    )

    ACCEPTANCE_CRITERIA_PATTERN = re.compile(
        r'[-*]\s*(?:AC|КП)[-\d]*[:\s]+(.+)',
        re.IGNORECASE
    )

    def __init__(self) -> None:
        """Initialize generator."""
        self.requirements: List[Requirement] = []
        self.analysis: Optional[AnalysisResult] = None
        self._test_counter = 0

    def load_spec(self, content: str) -> List[Requirement]:
        """
        Load and parse spec.md content.

        Args:
            content: Markdown content of spec.md

        Returns:
            List of parsed requirements
        """
        self.requirements = self._parse_requirements(content)
        return self.requirements

    def load_analysis(self, analysis: AnalysisResult) -> None:
        """
        Load analysis result from ResultAnalyzer.

        Args:
            analysis: AnalysisResult from ResultAnalyzer
        """
        self.analysis = analysis

    def generate(self, suite_name: str = "Generated Test Suite") -> TestSuite:
        """
        Generate test suite based on loaded requirements and analysis.

        Args:
            suite_name: Name for the test suite

        Returns:
            TestSuite with generated test cases
        """
        suite = TestSuite(
            name=suite_name,
            description="Автоматически сгенерированный набор тестов",
        )

        # Generate tests for requirements
        for req in self.requirements:
            tests = self._generate_requirement_tests(req)
            for test in tests:
                suite.add_test(test)

        # Generate tests for implemented functions
        if self.analysis:
            for func in self.analysis.functions:
                tests = self._generate_function_tests(func)
                for test in tests:
                    suite.add_test(test)

        return suite

    def generate_for_requirement(self, requirement: Requirement) -> List[TestCase]:
        """
        Generate test cases for a single requirement.

        Args:
            requirement: The requirement to generate tests for

        Returns:
            List of test cases
        """
        return self._generate_requirement_tests(requirement)

    def generate_for_function(self, function: ImplementedFunction) -> List[TestCase]:
        """
        Generate test cases for a single function.

        Args:
            function: The function to generate tests for

        Returns:
            List of test cases
        """
        return self._generate_function_tests(function)

    def _next_id(self) -> str:
        """Generate next test case ID."""
        self._test_counter += 1
        return f"TC-{self._test_counter:03d}"

    def _parse_requirements(self, content: str) -> List[Requirement]:
        """Parse requirements from spec.md content."""
        requirements = []

        for match in self.REQUIREMENT_PATTERN.finditer(content):
            req_id = match.group(1).upper()
            description = match.group(2).strip()

            # Find acceptance criteria after this requirement
            start = match.end()
            end = content.find('\n\n', start)
            if end == -1:
                end = start + 500

            section = content[start:end]
            criteria = []
            for ac_match in self.ACCEPTANCE_CRITERIA_PATTERN.finditer(section):
                criteria.append(ac_match.group(1).strip())

            requirements.append(Requirement(
                id=req_id,
                description=description,
                acceptance_criteria=criteria,
            ))

        return requirements

    def _generate_requirement_tests(self, req: Requirement) -> List[TestCase]:
        """Generate tests for a requirement."""
        tests = []

        # Main positive test
        tests.append(TestCase(
            id=self._next_id(),
            name=f"Проверка {req.id}: {req.description[:50]}",
            description=f"Проверка выполнения требования {req.id}",
            test_type=TestType.FUNCTIONAL,
            requirement_id=req.id,
            preconditions=["Система запущена", "Пользователь авторизован"],
            steps=[
                f"Выполнить действие согласно требованию {req.id}",
                "Проверить результат",
            ],
            expected_result=req.description,
            priority=req.priority,
            tags=["requirement", "functional"],
        ))

        # Generate tests for acceptance criteria
        for i, criterion in enumerate(req.acceptance_criteria, 1):
            tests.append(TestCase(
                id=self._next_id(),
                name=f"КП-{i} для {req.id}",
                description=f"Проверка критерия приёмки: {criterion}",
                test_type=TestType.FUNCTIONAL,
                requirement_id=req.id,
                steps=[
                    f"Проверить критерий: {criterion}",
                ],
                expected_result=criterion,
                priority=req.priority,
                tags=["acceptance_criteria"],
            ))

        # Negative test
        tests.append(TestCase(
            id=self._next_id(),
            name=f"Негативный тест {req.id}",
            description=f"Проверка обработки ошибок для {req.id}",
            test_type=TestType.FUNCTIONAL,
            requirement_id=req.id,
            preconditions=["Система запущена"],
            steps=[
                "Передать некорректные данные",
                "Проверить сообщение об ошибке",
            ],
            expected_result="Система корректно обрабатывает ошибку",
            priority=req.priority + 1,  # Lower priority
            tags=["negative", "error_handling"],
        ))

        return tests

    def _generate_function_tests(self, func: ImplementedFunction) -> List[TestCase]:
        """Generate tests for a function/procedure."""
        tests = []

        # Unit test - positive
        tests.append(TestCase(
            id=self._next_id(),
            name=f"Unit: {func.name} - позитивный",
            description=f"Проверка функции {func.name} с корректными данными",
            test_type=TestType.UNIT,
            preconditions=self._generate_preconditions(func),
            steps=self._generate_positive_steps(func),
            expected_result=func.returns if func.returns else "Функция выполняется без ошибок",
            priority=1 if func.is_export else 2,
            tags=["unit", "positive"],
        ))

        # Unit test - boundary
        if func.parameters:
            tests.append(TestCase(
                id=self._next_id(),
                name=f"Unit: {func.name} - граничные значения",
                description=f"Проверка функции {func.name} с граничными значениями",
                test_type=TestType.UNIT,
                preconditions=self._generate_preconditions(func),
                steps=self._generate_boundary_steps(func),
                expected_result="Функция корректно обрабатывает граничные значения",
                priority=2,
                tags=["unit", "boundary"],
            ))

        # Unit test - negative
        tests.append(TestCase(
            id=self._next_id(),
            name=f"Unit: {func.name} - негативный",
            description=f"Проверка функции {func.name} с некорректными данными",
            test_type=TestType.UNIT,
            preconditions=self._generate_preconditions(func),
            steps=self._generate_negative_steps(func),
            expected_result="Функция выбрасывает исключение или возвращает ошибку",
            priority=2,
            tags=["unit", "negative"],
        ))

        # If export - integration test
        if func.is_export:
            tests.append(TestCase(
                id=self._next_id(),
                name=f"Integration: {func.name}",
                description=f"Интеграционный тест экспортной функции {func.name}",
                test_type=TestType.INTEGRATION,
                preconditions=[
                    "Модуль загружен",
                    "Зависимости доступны",
                ],
                steps=[
                    f"Вызвать {func.name} из внешнего модуля",
                    "Проверить результат",
                    "Проверить побочные эффекты",
                ],
                expected_result="Функция работает корректно при внешнем вызове",
                priority=1,
                tags=["integration", "export"],
            ))

        return tests

    def _generate_preconditions(self, func: ImplementedFunction) -> List[str]:
        """Generate preconditions for function test."""
        preconditions = [
            "Модуль загружен",
        ]

        if func.parameters:
            preconditions.append(f"Подготовлены тестовые данные для {len(func.parameters)} параметров")

        return preconditions

    def _generate_positive_steps(self, func: ImplementedFunction) -> List[str]:
        """Generate positive test steps."""
        steps = []

        if func.parameters:
            steps.append(f"Подготовить корректные значения для: {', '.join(func.parameters)}")

        steps.append(f"Вызвать {func.name}({', '.join(func.parameters) if func.parameters else ''})")
        steps.append("Проверить возвращаемое значение")

        return steps

    def _generate_boundary_steps(self, func: ImplementedFunction) -> List[str]:
        """Generate boundary test steps."""
        steps = [
            "Определить граничные значения параметров",
        ]

        for param in func.parameters:
            steps.append(f"Проверить {param} с минимальным значением")
            steps.append(f"Проверить {param} с максимальным значением")

        steps.append(f"Вызвать {func.name} с граничными значениями")

        return steps

    def _generate_negative_steps(self, func: ImplementedFunction) -> List[str]:
        """Generate negative test steps."""
        steps = [
            "Подготовить некорректные данные",
        ]

        if func.parameters:
            steps.append(f"Передать Неопределено в параметр {func.parameters[0]}")
            if len(func.parameters) > 1:
                steps.append("Передать некорректный тип данных")

        steps.append(f"Вызвать {func.name}")
        steps.append("Проверить обработку исключения")

        return steps


# BSL-specific test templates
class BSLTestTemplates:
    """Templates for generating BSL test code."""

    UNIT_TEST_TEMPLATE = '''
Процедура Тест_{function_name}() Экспорт
    // Arrange
    {arrange_code}

    // Act
    {act_code}

    // Assert
    {assert_code}
КонецПроцедуры
'''

    ARRANGE_TEMPLATE = '''    // Подготовка тестовых данных
    {params_init}'''

    ACT_TEMPLATE = '''    Результат = {module_name}.{function_name}({params});'''

    ASSERT_TEMPLATE = '''    Ожидаем.Что(Результат).{assertion};'''

    @classmethod
    def generate_bsl_test(
        cls,
        func: ImplementedFunction,
        module_name: str = "МойМодуль",
    ) -> str:
        """Generate BSL unit test code."""
        # Generate arrange
        params_init = []
        for i, param in enumerate(func.parameters):
            params_init.append(f"Парам{i + 1} = ; // {param}")

        arrange = cls.ARRANGE_TEMPLATE.format(
            params_init='\n    '.join(params_init) if params_init else "// Нет параметров"
        )

        # Generate act
        params_str = ', '.join([f"Парам{i + 1}" for i in range(len(func.parameters))])
        act = cls.ACT_TEMPLATE.format(
            module_name=module_name,
            function_name=func.name,
            params=params_str,
        )

        # Generate assert
        assert_code = cls.ASSERT_TEMPLATE.format(
            assertion="НеРавно(Неопределено)" if func.returns else "Заполнено()"
        )

        return cls.UNIT_TEST_TEMPLATE.format(
            function_name=func.name,
            arrange_code=arrange,
            act_code=act,
            assert_code=assert_code,
        )


# Convenience function
def generate_tests(
    spec_content: str,
    analysis: Optional[AnalysisResult] = None,
    suite_name: str = "Generated Tests",
) -> TestSuite:
    """
    Convenience function to generate tests.

    Args:
        spec_content: Content of spec.md
        analysis: Optional AnalysisResult from ResultAnalyzer
        suite_name: Name for the test suite

    Returns:
        TestSuite with generated tests
    """
    generator = TestGenerator()
    generator.load_spec(spec_content)

    if analysis:
        generator.load_analysis(analysis)

    return generator.generate(suite_name)
