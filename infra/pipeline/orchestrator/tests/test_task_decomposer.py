"""Tests for TaskDecomposer."""

import pytest
from .task_decomposer import (
    TaskDecomposer,
    decompose_task,
    find_parallel_groups,
    build_dependency_graph,
    analyze_parallelism,
    ResourcePattern,
    DecompositionPattern,
)
from models import (
    TaskNode,
    TaskGraph,
    TaskDependency,
    DependencyType,
    ExecutionPriority,
    ParallelGroup,
    MergeStrategy,
    TaskStatus,
)
from constants import AgentRole


class TestResourceExtraction:
    """Tests for resource extraction from descriptions."""

    def test_extract_module_read(self):
        """Test extracting module read resource."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Изучить модуль ОбщиеПроцедуры"
        )
        assert "module:ОбщиеПроцедуры" in reads
        assert len(writes) == 0

    def test_extract_module_write(self):
        """Test extracting module write resource."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Изменить модуль ОбработкаДанных"
        )
        assert "module:ОбработкаДанных" in writes

    def test_extract_document_read(self):
        """Test extracting document read resource."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Проанализировать документ ПриходТоваров"
        )
        assert "document:ПриходТоваров" in reads

    def test_extract_document_write(self):
        """Test extracting document write resource."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Создать документ РасходТоваров"
        )
        assert "document:РасходТоваров" in writes

    def test_extract_catalog(self):
        """Test extracting catalog resource."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Добавить справочник Номенклатура"
        )
        assert "catalog:Номенклатура" in writes

    def test_extract_register(self):
        """Test extracting register resource."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Работа с регистр ОстаткиТоваров"
        )
        assert "register:ОстаткиТоваров" in reads

    def test_extract_file(self):
        """Test extracting file resource."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Редактировать файл Module.bsl"
        )
        assert "file:Module.bsl" in writes

    def test_extract_multiple_resources(self):
        """Test extracting multiple resources."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Изучить модуль Общий и изменить документ Заказ"
        )
        assert "module:Общий" in reads
        assert "document:Заказ" in writes

    def test_extract_no_resources(self):
        """Test extraction when no resources found."""
        decomposer = TaskDecomposer(project_id="TEST")
        reads, writes = decomposer._extract_resources(
            "Просто какая-то задача"
        )
        assert len(reads) == 0
        assert len(writes) == 0


class TestTaskTypeDetection:
    """Tests for task type detection."""

    def test_detect_analysis(self):
        """Test detecting analysis task."""
        decomposer = TaskDecomposer(project_id="TEST")
        task_type = decomposer._detect_task_type("Анализ модуля")
        assert task_type == "analysis"

    def test_detect_implementation(self):
        """Test detecting implementation task."""
        decomposer = TaskDecomposer(project_id="TEST")
        task_type = decomposer._detect_task_type("Реализовать функцию")
        assert task_type == "implementation"

    def test_detect_refactoring(self):
        """Test detecting refactoring task."""
        decomposer = TaskDecomposer(project_id="TEST")
        task_type = decomposer._detect_task_type("Рефакторинг кода")
        assert task_type == "refactoring"

    def test_detect_testing(self):
        """Test detecting testing task."""
        decomposer = TaskDecomposer(project_id="TEST")
        task_type = decomposer._detect_task_type("Тестирование модуля")
        assert task_type == "testing"

    def test_detect_documentation(self):
        """Test detecting documentation task."""
        decomposer = TaskDecomposer(project_id="TEST")
        task_type = decomposer._detect_task_type("Документирование API")
        assert task_type == "documentation"

    def test_detect_bugfix(self):
        """Test detecting bugfix task."""
        decomposer = TaskDecomposer(project_id="TEST")
        task_type = decomposer._detect_task_type("Исправить ошибку")
        assert task_type == "bugfix"

    def test_default_implementation(self):
        """Test default task type is implementation."""
        decomposer = TaskDecomposer(project_id="TEST")
        task_type = decomposer._detect_task_type("Сделать что-то")
        assert task_type == "implementation"


class TestPriorityDetermination:
    """Tests for priority determination."""

    def test_bugfix_priority(self):
        """Test bugfix gets critical priority."""
        decomposer = TaskDecomposer(project_id="TEST")
        priority = decomposer._determine_priority("bugfix")
        assert priority == ExecutionPriority.CRITICAL

    def test_testing_priority(self):
        """Test testing gets high priority."""
        decomposer = TaskDecomposer(project_id="TEST")
        priority = decomposer._determine_priority("testing")
        assert priority == ExecutionPriority.HIGH

    def test_implementation_priority(self):
        """Test implementation gets normal priority."""
        decomposer = TaskDecomposer(project_id="TEST")
        priority = decomposer._determine_priority("implementation")
        assert priority == ExecutionPriority.NORMAL

    def test_documentation_priority(self):
        """Test documentation gets background priority."""
        decomposer = TaskDecomposer(project_id="TEST")
        priority = decomposer._determine_priority("documentation")
        assert priority == ExecutionPriority.BACKGROUND


class TestTaskDecomposition:
    """Tests for task decomposition."""

    def test_single_task_no_decomposition(self):
        """Test simple task without decomposition."""
        decomposer = TaskDecomposer(project_id="TEST")
        graph = decomposer.decompose("Простая задача")

        assert len(graph.tasks) == 1
        task = list(graph.tasks.values())[0]
        assert "Простая задача" in task.description

    def test_numbered_list_decomposition(self):
        """Test decomposition of numbered list."""
        decomposer = TaskDecomposer(project_id="TEST")
        description = """
        1. Изучить модуль Общий
        2. Изменить документ Заказ
        3. Протестировать результат
        """
        graph = decomposer.decompose(description)

        assert len(graph.tasks) == 3
        task_names = [t.name for t in graph.tasks.values()]
        assert any("Шаг 1" in name for name in task_names)
        assert any("Шаг 2" in name for name in task_names)
        assert any("Шаг 3" in name for name in task_names)

    def test_bullet_list_decomposition(self):
        """Test decomposition of bullet list."""
        decomposer = TaskDecomposer(project_id="TEST")
        description = """
        - Проанализировать код
        - Написать тесты
        - Обновить документацию
        """
        graph = decomposer.decompose(description)

        assert len(graph.tasks) == 3
        task_names = [t.name for t in graph.tasks.values()]
        assert any("Подзадача 1" in name for name in task_names)

    def test_conjunction_decomposition(self):
        """Test decomposition with conjunction."""
        decomposer = TaskDecomposer(project_id="TEST")
        description = "Изменить модуль Общий и добавить документ Заказ"
        graph = decomposer.decompose(description)

        assert len(graph.tasks) == 2
        task_names = [t.name for t in graph.tasks.values()]
        assert any("Часть 1" in name for name in task_names)
        assert any("Часть 2" in name for name in task_names)

    def test_resource_extraction_in_subtasks(self):
        """Test that resources are extracted for each subtask."""
        decomposer = TaskDecomposer(project_id="TEST")
        description = """
        1. Изучить модуль ОбщийМодуль
        2. Изменить документ ПоступлениеТоваров
        """
        graph = decomposer.decompose(description)

        tasks = list(graph.tasks.values())

        # First task should have module read
        task1 = next(t for t in tasks if "Шаг 1" in t.name)
        assert "module:ОбщийМодуль" in task1.resources_read

        # Second task should have document write
        task2 = next(t for t in tasks if "Шаг 2" in t.name)
        assert "document:ПоступлениеТоваров" in task2.resources_write


class TestDependencyBuilding:
    """Tests for dependency building."""

    def test_write_read_dependency(self):
        """Test dependency created for write-read relationship."""
        decomposer = TaskDecomposer(project_id="TEST")
        description = """
        1. Создать документ Заказ
        2. Проанализировать документ Заказ
        """
        graph = decomposer.decompose(description)

        # Should have 1 dependency (task1 produces for task2)
        assert len(graph.dependencies) >= 1

        tasks = list(graph.tasks.values())
        task1 = next(t for t in tasks if "Шаг 1" in t.name)
        task2 = next(t for t in tasks if "Шаг 2" in t.name)

        deps = graph.get_dependencies(task2.id)
        assert len(deps) >= 1
        # task2 depends on task1, so source_id=task2.id, target_id=task1.id
        assert any(d.target_id == task1.id for d in deps)

    def test_write_write_dependency(self):
        """Test dependency created for write-write conflict."""
        decomposer = TaskDecomposer(project_id="TEST")
        description = """
        1. Изменить модуль Общий
        2. Изменить модуль Общий
        """
        graph = decomposer.decompose(description)

        # Should have dependency to prevent concurrent writes
        assert len(graph.dependencies) >= 1


class TestParallelGroups:
    """Tests for parallel group finding."""

    def test_find_independent_tasks(self):
        """Test finding independent tasks as parallel group."""
        task1 = TaskNode(
            id="T1",
            name="Task 1",
            description="First task",
            resources_read={"file:a.bsl"},
            resources_write=set(),
        )
        task2 = TaskNode(
            id="T2",
            name="Task 2",
            description="Second task",
            resources_read={"file:b.bsl"},
            resources_write=set(),
        )

        graph = build_dependency_graph([task1, task2])
        groups = find_parallel_groups(graph)

        # Both tasks should be in one parallel group
        assert len(groups) >= 1
        group_sizes = [len(g.tasks) for g in groups]
        assert 2 in group_sizes

    def test_dependent_tasks_separate_groups(self):
        """Test dependent tasks go to different groups."""
        task1 = TaskNode(
            id="T1",
            name="Task 1",
            description="First task",
            resources_read=set(),
            resources_write={"file:output.bsl"},
        )
        task2 = TaskNode(
            id="T2",
            name="Task 2",
            description="Second task",
            resources_read={"file:output.bsl"},
            resources_write=set(),
        )

        graph = build_dependency_graph([task1, task2])
        groups = find_parallel_groups(graph)

        # Tasks should be in different groups
        assert len(groups) >= 2


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_decompose_task_function(self):
        """Test decompose_task convenience function."""
        graph = decompose_task(
            task_description="Простая задача",
            project_id="TEST",
        )

        assert isinstance(graph, TaskGraph)
        assert len(graph.tasks) >= 1

    def test_build_dependency_graph_function(self):
        """Test build_dependency_graph convenience function."""
        tasks = [
            TaskNode(id="T1", name="Task 1", description="First"),
            TaskNode(id="T2", name="Task 2", description="Second"),
        ]

        graph = build_dependency_graph(tasks)

        assert isinstance(graph, TaskGraph)
        assert len(graph.tasks) == 2

    def test_build_dependency_graph_empty(self):
        """Test build_dependency_graph with empty list."""
        graph = build_dependency_graph([])

        assert isinstance(graph, TaskGraph)
        assert len(graph.tasks) == 0

    def test_analyze_parallelism(self):
        """Test analyze_parallelism function."""
        tasks = [
            TaskNode(
                id="T1",
                name="Task 1",
                description="First",
                resources_read=set(),
                resources_write={"a"},
            ),
            TaskNode(
                id="T2",
                name="Task 2",
                description="Second",
                resources_read={"a"},
                resources_write=set(),
            ),
        ]
        graph = build_dependency_graph(tasks)

        analysis = analyze_parallelism(graph)

        assert analysis["total_tasks"] == 2
        assert "parallel_groups" in analysis
        assert "max_parallelism" in analysis
        assert "parallelism_ratio" in analysis
        assert "critical_path_length" in analysis

    def test_analyze_parallelism_empty_graph(self):
        """Test analyze_parallelism with empty graph."""
        graph = TaskGraph(id="TEST")

        analysis = analyze_parallelism(graph)

        assert analysis["total_tasks"] == 0
        assert analysis["parallelism_ratio"] == 0.0


class TestExecutionPlan:
    """Tests for execution plan building."""

    def test_build_execution_plan_sequential(self):
        """Test execution plan for sequential tasks."""
        decomposer = TaskDecomposer(project_id="TEST")

        task1 = TaskNode(
            id="T1",
            name="Task 1",
            resources_write={"file:a"},
        )
        task2 = TaskNode(
            id="T2",
            name="Task 2",
            resources_read={"file:a"},
        )

        graph = TaskGraph(id="TEST")
        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_dependency(TaskDependency(
            source_id="T2",
            target_id="T1",
            dependency_type=DependencyType.PRODUCES,
        ))

        plan = decomposer.build_execution_plan(graph)

        assert len(plan) == 2
        assert task1 in plan[0]
        assert task2 in plan[1]

    def test_build_execution_plan_parallel(self):
        """Test execution plan for parallel tasks."""
        decomposer = TaskDecomposer(project_id="TEST")

        task1 = TaskNode(id="T1", name="Task 1")
        task2 = TaskNode(id="T2", name="Task 2")
        task3 = TaskNode(id="T3", name="Task 3")

        graph = TaskGraph(id="TEST")
        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)

        plan = decomposer.build_execution_plan(graph)

        # All tasks should be in first wave
        assert len(plan) == 1
        assert len(plan[0]) == 3

    def test_build_execution_plan_respects_max_parallel(self):
        """Test execution plan respects max parallel limit."""
        decomposer = TaskDecomposer(project_id="TEST", max_parallel_tasks=2)

        tasks = [
            TaskNode(id=f"T{i}", name=f"Task {i}")
            for i in range(5)
        ]

        graph = TaskGraph(id="TEST")
        for task in tasks:
            graph.add_task(task)

        plan = decomposer.build_execution_plan(graph)

        # Each wave should have at most 2 tasks
        for wave in plan:
            assert len(wave) <= 2


class TestTaskIdGeneration:
    """Tests for task ID generation."""

    def test_task_id_format(self):
        """Test task ID format."""
        decomposer = TaskDecomposer(project_id="PROJ")
        task_id = decomposer._generate_task_id()

        assert task_id.startswith("PROJ-T")
        assert task_id == "PROJ-T001"

    def test_task_id_increment(self):
        """Test task ID increment."""
        decomposer = TaskDecomposer(project_id="PROJ")
        id1 = decomposer._generate_task_id()
        id2 = decomposer._generate_task_id()
        id3 = decomposer._generate_task_id()

        assert id1 == "PROJ-T001"
        assert id2 == "PROJ-T002"
        assert id3 == "PROJ-T003"


class TestIntegration:
    """Integration tests for task decomposer."""

    def test_full_workflow(self):
        """Test full workflow: decompose -> analyze -> plan."""
        decomposer = TaskDecomposer(
            project_id="INTEG-TEST",
            max_parallel_tasks=3,
        )

        description = """
        1. Проанализировать модуль ОбщийМодуль
        2. Изменить документ Заказ на основе анализа
        3. Добавить справочник Клиенты
        4. Написать тесты
        """

        # Decompose
        graph = decomposer.decompose(description)
        assert len(graph.tasks) == 4

        # Analyze
        analysis = analyze_parallelism(graph)
        assert analysis["total_tasks"] == 4

        # Plan
        plan = decomposer.build_execution_plan(graph)
        assert len(plan) >= 1

        # All tasks should be executed
        executed = set()
        for wave in plan:
            for task in wave:
                executed.add(task.id)

        assert len(executed) == 4

    def test_complex_dependencies(self):
        """Test complex dependency scenario."""
        decomposer = TaskDecomposer(project_id="COMPLEX")

        # Task with shared resource
        description = """
        1. Создать модуль Общий
        2. Использовать модуль Общий для документа
        3. Использовать модуль Общий для отчёта
        4. Изменить модуль Общий
        """

        graph = decomposer.decompose(description)

        # Should have proper ordering
        plan = decomposer.build_execution_plan(graph)

        # Task 4 (modify) should come after tasks that read
        assert len(plan) >= 2
