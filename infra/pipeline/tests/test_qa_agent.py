"""
Integration tests for QA Agent.
"""

import pytest

from agents.qa import (
    QAAgent,
    QAAgentConfig,
    QAContext,
    ResultAnalyzer,
    TestGenerator,
    TestRunner,
    ReportGenerator,
    create_qa_agent,
    run_qa,
)
from agents.qa.models import (
    TestCase,
    TestResult,
    TestStatus,
    TestType,
    TestSuite,
    Defect,
    Severity,
    QAReport,
)
from agents.qa.result_analyzer import (
    ChangeType,
    FileChange,
    ImplementedFunction,
    CodeBlock,
    AnalysisResult,
    analyze_result,
)
from agents.qa.test_generator import (
    TestCategory,
    Requirement,
    generate_tests,
    BSLTestTemplates,
)
from agents.qa.test_runner import (
    RunConfig,
    RunSummary,
    create_runner,
    create_dry_runner,
)
from agents.qa.report_generator import (
    generate_report,
    write_qa_report,
    ExtendedReportGenerator,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def sample_result_md():
    """Sample result.md content for testing."""
    return """# Результат реализации

## Изменённые файлы

| Файл | Статус | Описание |
|------|--------|----------|
| CommonModules/ПриемкаТоваров/Ext/Module.bsl | Добавлен | Модуль приёмки товаров |
| DataProcessors/АРМПриемка/Ext/ObjectModule.bsl | Изменен | Обновлена логика |

## Код реализации

### Функция ПолучитьДанныеТовара

**Назначение:** Получает данные товара по штрих-коду
**Параметры:** ШтрихКод, ПараметрыПоиска
**Возвращает:** Структура с данными товара

```bsl
Функция ПолучитьДанныеТовара(ШтрихКод, ПараметрыПоиска = Неопределено) Экспорт
    Результат = Новый Структура;

    Запрос = Новый Запрос;
    Запрос.Текст = "
        |ВЫБРАТЬ
        |   Номенклатура.Ссылка,
        |   Номенклатура.Наименование
        |ИЗ
        |   Справочник.Номенклатура КАК Номенклатура
        |ГДЕ
        |   Номенклатура.ШтрихКод = &ШтрихКод";

    Запрос.УстановитьПараметр("ШтрихКод", ШтрихКод);

    Возврат Результат;
КонецФункции
```

### Процедура ОбработатьПриемку

```bsl
Процедура ОбработатьПриемку(ДокументСсылка) Экспорт
    // Обработка документа приёмки
    ДокументОбъект = ДокументСсылка.ПолучитьОбъект();
    ДокументОбъект.Записать();
КонецПроцедуры
```

## Выполненные требования
- REQ-001: Реализовано получение данных товара
- REQ-002: Реализована обработка приёмки
- ТРБ-003: Добавлена валидация штрих-кода

## Тестирование
Проведено модульное тестирование основных функций.
"""


@pytest.fixture
def sample_spec_md():
    """Sample spec.md content for testing."""
    return """# Техническое задание

## Функциональные требования

- REQ-001: Получение данных товара по штрих-коду
  - AC: Функция возвращает структуру с данными
  - AC: При отсутствии товара возвращает пустую структуру

- REQ-002: Обработка документа приёмки
  - AC: Документ записывается без ошибок
  - AC: Проставляется статус "Обработан"

- ТРБ-003: Валидация входных данных
  - КП: Проверка формата штрих-кода
  - КП: Проверка на дубликаты

## Нефункциональные требования
- NFR-001: Время отклика < 1 сек
- NFR-002: Логирование операций

## Критерии приёмки
1. Все тесты пройдены
2. Документация обновлена
"""


@pytest.fixture
def sample_design_md():
    """Sample design.md content for testing."""
    return """# Архитектурное решение

## Структура

### Общие модули
- ПриемкаТоваров - основная логика

### Обработки
- АРМПриемка - интерфейс пользователя

## Функции
- ПолучитьДанныеТовара
- ОбработатьПриемку
"""


@pytest.fixture
def analyzer():
    """ResultAnalyzer instance."""
    return ResultAnalyzer()


@pytest.fixture
def generator():
    """TestGenerator instance."""
    return TestGenerator()


@pytest.fixture
def runner():
    """TestRunner instance."""
    return TestRunner()


@pytest.fixture
def reporter():
    """ReportGenerator instance."""
    return ReportGenerator()


@pytest.fixture
def qa_agent():
    """QAAgent instance."""
    return QAAgent()


# =============================================================================
# ResultAnalyzer Tests
# =============================================================================

class TestResultAnalyzer:
    """Test suite for ResultAnalyzer."""

    def test_analyze_extracts_files(self, analyzer, sample_result_md):
        """Test that file changes are extracted."""
        result = analyzer.analyze(sample_result_md)

        assert len(result.file_changes) >= 1
        assert any('Module.bsl' in f.path for f in result.file_changes)

    def test_analyze_extracts_functions(self, analyzer, sample_result_md):
        """Test that functions are extracted from code blocks."""
        result = analyzer.analyze(sample_result_md)

        assert len(result.functions) >= 1
        func_names = [f.name for f in result.functions]
        assert 'ПолучитьДанныеТовара' in func_names or 'ОбработатьПриемку' in func_names

    def test_analyze_extracts_code_blocks(self, analyzer, sample_result_md):
        """Test that code blocks are extracted."""
        result = analyzer.analyze(sample_result_md)

        assert len(result.code_blocks) >= 1
        bsl_blocks = [b for b in result.code_blocks if b.language == 'bsl']
        assert len(bsl_blocks) >= 1

    def test_analyze_extracts_requirements(self, analyzer, sample_result_md):
        """Test that requirement IDs are extracted."""
        result = analyzer.analyze(sample_result_md)

        assert len(result.requirements_covered) >= 1
        assert 'REQ-001' in result.requirements_covered or 'ТРБ-003' in result.requirements_covered

    def test_analyze_result_properties(self, analyzer, sample_result_md):
        """Test AnalysisResult properties."""
        result = analyzer.analyze(sample_result_md)

        assert result.total_files >= 0
        assert result.total_functions >= 0
        assert isinstance(result.bsl_files, list)

    def test_analyze_to_dict(self, analyzer, sample_result_md):
        """Test AnalysisResult serialization."""
        result = analyzer.analyze(sample_result_md)
        data = result.to_dict()

        assert 'total_files' in data
        assert 'total_functions' in data
        assert 'file_changes' in data
        assert 'functions' in data

    def test_analyze_empty_content(self, analyzer):
        """Test analysis of empty content."""
        result = analyzer.analyze("")

        assert result.total_files == 0
        assert result.total_functions == 0

    def test_get_test_points(self, analyzer, sample_result_md):
        """Test getting test points from analysis."""
        analyzer.analyze(sample_result_md)
        test_points = analyzer.get_test_points()

        assert isinstance(test_points, list)

    def test_convenience_function(self, sample_result_md):
        """Test analyze_result convenience function."""
        result = analyze_result(sample_result_md)

        assert isinstance(result, AnalysisResult)


# =============================================================================
# TestGenerator Tests
# =============================================================================

class TestTestGenerator:
    """Test suite for TestGenerator."""

    def test_load_spec(self, generator, sample_spec_md):
        """Test loading spec content."""
        requirements = generator.load_spec(sample_spec_md)

        assert len(requirements) >= 1
        assert any(r.id.startswith('REQ') or r.id.startswith('ТРБ') for r in requirements)

    def test_load_analysis(self, generator, analyzer, sample_result_md):
        """Test loading analysis result."""
        analysis = analyzer.analyze(sample_result_md)
        generator.load_analysis(analysis)

        assert generator.analysis is not None

    def test_generate_creates_suite(self, generator, sample_spec_md):
        """Test that generate creates a test suite."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate("Test Suite")

        assert isinstance(suite, TestSuite)
        assert suite.name == "Test Suite"
        assert len(suite.test_cases) > 0

    def test_generate_creates_positive_tests(self, generator, sample_spec_md):
        """Test that positive tests are generated."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()

        positive_tests = [
            tc for tc in suite.test_cases
            if 'negative' not in tc.tags
        ]
        assert len(positive_tests) > 0

    def test_generate_creates_negative_tests(self, generator, sample_spec_md):
        """Test that negative tests are generated."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()

        negative_tests = [
            tc for tc in suite.test_cases
            if 'negative' in tc.tags
        ]
        assert len(negative_tests) > 0

    def test_generate_for_function(self, generator, analyzer, sample_result_md):
        """Test generating tests for a function."""
        analysis = analyzer.analyze(sample_result_md)

        if analysis.functions:
            tests = generator.generate_for_function(analysis.functions[0])
            assert len(tests) > 0
            assert all(isinstance(t, TestCase) for t in tests)

    def test_convenience_function(self, sample_spec_md):
        """Test generate_tests convenience function."""
        suite = generate_tests(sample_spec_md, suite_name="Conv Test")

        assert isinstance(suite, TestSuite)
        assert len(suite.test_cases) > 0

    def test_bsl_test_template(self):
        """Test BSL test code generation."""
        func = ImplementedFunction(
            name="ТестоваяФункция",
            parameters=["Параметр1", "Параметр2"],
            returns="Структура",
            is_export=True,
        )

        bsl_code = BSLTestTemplates.generate_bsl_test(func, "МойМодуль")

        assert 'Процедура Тест_ТестоваяФункция' in bsl_code
        assert 'МойМодуль.ТестоваяФункция' in bsl_code


# =============================================================================
# TestRunner Tests
# =============================================================================

class TestTestRunner:
    """Test suite for TestRunner."""

    def test_run_executes_tests(self, runner, generator, sample_spec_md):
        """Test that runner executes tests."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()

        results = runner.run(suite)

        assert len(results) > 0
        assert all(isinstance(r, TestResult) for r in results)

    def test_run_updates_summary(self, runner, generator, sample_spec_md):
        """Test that summary is updated after run."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()

        runner.run(suite)

        assert runner.summary.total > 0
        assert runner.summary.passed + runner.summary.failed + runner.summary.skipped == runner.summary.total

    def test_run_creates_defects(self, runner, generator, sample_spec_md):
        """Test that defects are created for failures."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()

        runner.run(suite)

        # Defects should match failed tests
        assert len(runner.defects) == runner.summary.failed

    def test_run_single(self, runner):
        """Test running a single test case."""
        test_case = TestCase(
            id="TC-001",
            name="Single Test",
            description="Test description",
            test_type=TestType.UNIT,
            steps=["Step 1"],
            expected_result="Success",
        )

        result = runner.run_single(test_case)

        assert isinstance(result, TestResult)
        assert result.test_case == test_case

    def test_dry_run(self):
        """Test dry run mode."""
        runner = create_dry_runner()

        test_case = TestCase(
            id="TC-001",
            name="Dry Run Test",
            description="Test",
            test_type=TestType.UNIT,
            steps=["Step"],
            expected_result="Result",
        )

        result = runner.run_single(test_case)

        assert result.status == TestStatus.SKIPPED

    def test_stop_on_failure(self, generator, sample_spec_md):
        """Test stop on failure configuration."""
        runner = TestRunner(RunConfig(stop_on_failure=True))
        generator.load_spec(sample_spec_md)
        suite = generator.generate()

        runner.run(suite)

        # If stopped on failure, remaining should be skipped
        if runner.summary.failed > 0:
            assert runner.summary.skipped > 0 or runner.summary.failed == runner.summary.total

    def test_get_coverage(self, runner, generator, sample_spec_md):
        """Test coverage calculation."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()

        runner.run(suite)
        coverage = runner.get_coverage(['REQ-001', 'REQ-002'])

        assert 'total' in coverage
        assert 'covered' in coverage
        assert 'percentage' in coverage

    def test_callbacks(self, runner):
        """Test callback registration."""
        started = []
        ended = []

        runner.on_test_start(lambda tc: started.append(tc))
        runner.on_test_end(lambda tr: ended.append(tr))

        test_case = TestCase(
            id="TC-001",
            name="Callback Test",
            description="Test",
            test_type=TestType.UNIT,
            steps=["Step"],
            expected_result="Result",
        )

        suite = TestSuite(name="Test")
        suite.add_test(test_case)
        runner.run(suite)

        assert len(started) == 1
        assert len(ended) == 1

    def test_factory_functions(self):
        """Test runner factory functions."""
        runner1 = create_runner(timeout_ms=5000, stop_on_failure=True)
        runner2 = create_dry_runner()

        assert runner1.config.timeout_ms == 5000
        assert runner1.config.stop_on_failure == True
        assert runner2.config.dry_run == True


# =============================================================================
# ReportGenerator Tests
# =============================================================================

class TestReportGenerator:
    """Test suite for ReportGenerator."""

    def test_generate_creates_report(self, reporter, runner, generator, sample_spec_md):
        """Test that report is generated."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()
        runner.run(suite)

        report = reporter.generate(
            project_id="TEST",
            task_id="TASK-001",
            test_suite=suite,
            results=runner.results,
            defects=runner.defects,
        )

        assert isinstance(report, QAReport)
        assert report.project_id == "TEST"
        assert report.task_id == "TASK-001"

    def test_generate_determines_verdict(self, reporter, runner, generator, sample_spec_md):
        """Test that verdict is determined."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()
        runner.run(suite)

        report = reporter.generate(
            project_id="TEST",
            task_id="TASK-001",
            test_suite=suite,
            results=runner.results,
            defects=runner.defects,
        )

        assert report.verdict is not None
        assert any(v in report.verdict for v in ['PASSED', 'FAILED', 'WARNING'])

    def test_generate_creates_recommendations(self, reporter, runner, generator, sample_spec_md):
        """Test that recommendations are generated."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()
        runner.run(suite)

        report = reporter.generate(
            project_id="TEST",
            task_id="TASK-001",
            test_suite=suite,
            results=runner.results,
            defects=runner.defects,
        )

        assert len(report.recommendations) > 0

    def test_report_to_markdown(self, reporter, runner, generator, sample_spec_md):
        """Test markdown generation."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()
        runner.run(suite)

        report = reporter.generate(
            project_id="TEST",
            task_id="TASK-001",
            test_suite=suite,
            results=runner.results,
            defects=runner.defects,
        )

        markdown = report.to_markdown()

        assert '# QA Report' in markdown or '# Отчёт QA' in markdown
        assert 'TEST' in markdown
        assert 'TASK-001' in markdown

    def test_extended_report_generator(self, runner, generator, sample_spec_md):
        """Test extended report generator."""
        ext_reporter = ExtendedReportGenerator()
        generator.load_spec(sample_spec_md)
        suite = generator.generate()
        runner.run(suite)

        markdown = ext_reporter.generate_extended(
            project_id="TEST",
            task_id="TASK-001",
            test_suite=suite,
            results=runner.results,
            defects=runner.defects,
            bsl_analysis={"functions_count": 5, "issues": []},
        )

        assert isinstance(markdown, str)
        assert 'BSL' in markdown or 'Метрики' in markdown

    def test_convenience_function(self, runner, generator, sample_spec_md):
        """Test generate_report convenience function."""
        generator.load_spec(sample_spec_md)
        suite = generator.generate()
        runner.run(suite)

        report = generate_report(
            project_id="TEST",
            task_id="TASK-001",
            test_suite=suite,
            results=runner.results,
            defects=runner.defects,
        )

        assert isinstance(report, QAReport)


# =============================================================================
# QAAgent Tests
# =============================================================================

class TestQAAgent:
    """Test suite for QAAgent."""

    def test_run_completes_workflow(self, qa_agent, sample_result_md, sample_spec_md):
        """Test that full QA workflow completes."""
        report = qa_agent.run(
            project_id="TEST",
            task_id="TASK-001",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        assert isinstance(report, QAReport)
        assert report.project_id == "TEST"
        assert report.task_id == "TASK-001"

    def test_run_with_context(self, qa_agent, sample_result_md, sample_spec_md, sample_design_md):
        """Test running with QAContext."""
        context = QAContext(
            project_id="CTX-TEST",
            task_id="CTX-TASK",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
            design_content=sample_design_md,
        )

        report = qa_agent.run_with_context(context)

        assert report.project_id == "CTX-TEST"
        assert report.task_id == "CTX-TASK"

    def test_agent_stores_analysis(self, qa_agent, sample_result_md, sample_spec_md):
        """Test that analysis is stored."""
        qa_agent.run(
            project_id="TEST",
            task_id="TASK-001",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        assert qa_agent.analysis is not None
        assert isinstance(qa_agent.analysis, AnalysisResult)

    def test_agent_stores_test_suite(self, qa_agent, sample_result_md, sample_spec_md):
        """Test that test suite is stored."""
        qa_agent.run(
            project_id="TEST",
            task_id="TASK-001",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        assert qa_agent.test_suite is not None
        assert isinstance(qa_agent.test_suite, TestSuite)

    def test_agent_stores_report(self, qa_agent, sample_result_md, sample_spec_md):
        """Test that report is stored."""
        qa_agent.run(
            project_id="TEST",
            task_id="TASK-001",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        assert qa_agent.report is not None
        assert isinstance(qa_agent.report, QAReport)

    def test_passed_property(self, qa_agent, sample_result_md, sample_spec_md):
        """Test passed property."""
        qa_agent.run(
            project_id="TEST",
            task_id="TASK-001",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        # passed should be boolean based on verdict
        assert isinstance(qa_agent.passed, bool)

    def test_pass_rate_property(self, qa_agent, sample_result_md, sample_spec_md):
        """Test pass_rate property."""
        qa_agent.run(
            project_id="TEST",
            task_id="TASK-001",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        assert isinstance(qa_agent.pass_rate, float)
        assert 0 <= qa_agent.pass_rate <= 100

    def test_get_summary(self, qa_agent, sample_result_md, sample_spec_md):
        """Test get_summary method."""
        qa_agent.run(
            project_id="TEST",
            task_id="TASK-001",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        summary = qa_agent.get_summary()

        assert 'project_id' in summary
        assert 'task_id' in summary
        assert 'verdict' in summary
        assert 'total_tests' in summary
        assert 'pass_rate' in summary

    def test_get_defects_markdown(self, qa_agent, sample_result_md, sample_spec_md):
        """Test get_defects_markdown method."""
        qa_agent.run(
            project_id="TEST",
            task_id="TASK-001",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        defects_md = qa_agent.get_defects_markdown()

        assert isinstance(defects_md, str)

    def test_config_applied(self, sample_result_md, sample_spec_md):
        """Test that config is applied."""
        config = QAAgentConfig(
            stop_on_failure=True,
            timeout_ms=5000,
            min_pass_rate=80.0,
        )
        agent = QAAgent(config)

        assert agent.config.stop_on_failure == True
        assert agent.config.timeout_ms == 5000
        assert agent.config.min_pass_rate == 80.0

    def test_factory_function(self):
        """Test create_qa_agent factory function."""
        agent = create_qa_agent(
            stop_on_failure=True,
            min_pass_rate=90.0,
        )

        assert isinstance(agent, QAAgent)
        assert agent.config.stop_on_failure == True
        assert agent.config.min_pass_rate == 90.0

    def test_run_qa_convenience(self, sample_result_md, sample_spec_md):
        """Test run_qa convenience function."""
        report = run_qa(
            project_id="CONV-TEST",
            task_id="CONV-TASK",
            result_content=sample_result_md,
            spec_content=sample_spec_md,
        )

        assert isinstance(report, QAReport)
        assert report.project_id == "CONV-TEST"


# =============================================================================
# Model Tests
# =============================================================================

class TestModels:
    """Test suite for QA models."""

    def test_test_case_creation(self):
        """Test TestCase creation."""
        tc = TestCase(
            id="TC-001",
            name="Test Name",
            description="Description",
            test_type=TestType.UNIT,
            steps=["Step 1", "Step 2"],
            expected_result="Expected",
        )

        assert tc.id == "TC-001"
        assert tc.name == "Test Name"
        assert len(tc.steps) == 2

    def test_test_case_to_dict(self):
        """Test TestCase serialization."""
        tc = TestCase(
            id="TC-001",
            name="Test",
            description="Desc",
            test_type=TestType.FUNCTIONAL,
            steps=["Step"],
            expected_result="Result",
        )

        data = tc.to_dict()
        assert data['id'] == "TC-001"
        assert data['test_type'] == "functional"

    def test_test_result_creation(self):
        """Test TestResult creation."""
        tc = TestCase(
            id="TC-001",
            name="Test",
            description="Desc",
            test_type=TestType.UNIT,
            steps=["Step"],
            expected_result="Result",
        )

        result = TestResult(
            test_case=tc,
            status=TestStatus.PASSED,
            actual_result="Result",
        )

        assert result.status == TestStatus.PASSED

    def test_test_suite_operations(self):
        """Test TestSuite operations."""
        suite = TestSuite(name="Suite", description="Description")

        tc1 = TestCase(
            id="TC-001",
            name="Test 1",
            description="Desc",
            test_type=TestType.UNIT,
            steps=["Step"],
            expected_result="Result",
        )
        tc2 = TestCase(
            id="TC-002",
            name="Test 2",
            description="Desc",
            test_type=TestType.UNIT,
            steps=["Step"],
            expected_result="Result",
        )

        suite.add_test(tc1)
        suite.add_test(tc2)

        assert suite.total_tests == 2
        assert suite.get_test("TC-001") == tc1

    def test_defect_creation(self):
        """Test Defect creation."""
        defect = Defect(
            id="BUG-001",
            title="Bug Title",
            description="Bug description",
            severity=Severity.MAJOR,
            test_case_id="TC-001",
        )

        assert defect.id == "BUG-001"
        assert defect.severity == Severity.MAJOR

    def test_defect_to_markdown(self):
        """Test Defect markdown generation."""
        defect = Defect(
            id="BUG-001",
            title="Bug Title",
            description="Bug description",
            severity=Severity.CRITICAL,
            test_case_id="TC-001",
        )

        markdown = defect.to_markdown()

        assert 'BUG-001' in markdown
        assert 'Bug Title' in markdown
        assert 'CRITICAL' in markdown.upper()

    def test_qa_report_metrics(self):
        """Test QAReport metrics."""
        suite = TestSuite(name="Test Suite")

        # Create some test results
        passed_result = TestResult(
            test_case=TestCase(
                id="TC-001", name="Test 1", description="D",
                test_type=TestType.UNIT, steps=["S"], expected_result="R"
            ),
            status=TestStatus.PASSED,
            actual_result="OK",
        )
        failed_result = TestResult(
            test_case=TestCase(
                id="TC-002", name="Test 2", description="D",
                test_type=TestType.UNIT, steps=["S"], expected_result="R"
            ),
            status=TestStatus.FAILED,
            actual_result="Failed",
            error_message="Error",
        )

        report = QAReport(
            project_id="P",
            task_id="T",
            test_suite=suite,
            results=[passed_result, failed_result],
            defects=[],
            coverage={},
            recommendations=["Rec"],
            verdict="⚠️ PASSED WITH WARNINGS",
        )

        assert report.total_tests == 2
        assert report.passed_tests == 1
        assert report.failed_tests == 1
        assert report.pass_rate == 50.0


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_spec(self, generator):
        """Test with empty spec content."""
        requirements = generator.load_spec("")
        assert len(requirements) == 0

    def test_empty_result(self, analyzer):
        """Test with empty result content."""
        result = analyzer.analyze("")
        assert result.total_files == 0
        assert result.total_functions == 0

    def test_malformed_content(self, analyzer):
        """Test with malformed markdown content."""
        content = "This is not valid markdown structure"
        result = analyzer.analyze(content)
        # Should not crash
        assert isinstance(result, AnalysisResult)

    def test_no_code_blocks(self, analyzer):
        """Test result without code blocks."""
        content = """# Result

Some text without code blocks.
"""
        result = analyzer.analyze(content)
        assert len(result.code_blocks) == 0

    def test_agent_no_report_before_run(self):
        """Test agent properties before run."""
        agent = QAAgent()

        assert agent.analysis is None
        assert agent.test_suite is None
        assert agent.report is None
        assert agent.passed == False
        assert agent.pass_rate == 0.0

    def test_summary_before_run(self):
        """Test get_summary before run."""
        agent = QAAgent()
        summary = agent.get_summary()

        assert 'error' in summary
