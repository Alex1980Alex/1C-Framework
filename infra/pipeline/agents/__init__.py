"""
Pipeline Agents.

This package contains specialized agents for the development pipeline:
- QA Agent - testing and quality assurance
- Reviewer Agent - code review (Sprint 2.3)
- Initializer Agent - context initialization (Sprint 3.1)
- PROJECT-MANAGER Agent - multi-project coordination (Sprint 4.4)
"""

from agents.project_manager import (
    DependencyGraph,
    DependencyTracker,
    DependencyType,
    Project,
    ProjectManagerAgent,
    ProjectManagerConfig,
    ProjectManagerInput,
    ProjectManagerOutput,
    ProjectManagerResult,
    # Classes
    ProjectRepository,
    # Enums
    ProjectStatus,
    Schedule,
    ScheduledTask,
    SchedulingStrategy,
    # Data classes
    Task,
    TaskDependency,
    TaskPriority,
    TaskRepository,
    TaskScheduler,
    TaskStatus,
)
from agents.qa import (
    QAAgent,
    QAReport,
    ReportGenerator,
    ResultAnalyzer,
    TestCase,
    TestGenerator,
    TestResult,
    TestRunner,
    TestSuite,
)

__all__ = [
    # QA Agent
    "QAAgent",
    "ResultAnalyzer",
    "TestGenerator",
    "TestRunner",
    "ReportGenerator",
    "TestCase",
    "TestResult",
    "TestSuite",
    "QAReport",
    # PROJECT-MANAGER Agent
    "ProjectStatus",
    "TaskStatus",
    "TaskPriority",
    "DependencyType",
    "SchedulingStrategy",
    "Task",
    "TaskDependency",
    "Project",
    "ProjectManagerConfig",
    "ProjectManagerInput",
    "ProjectManagerOutput",
    "ScheduledTask",
    "Schedule",
    "DependencyGraph",
    "ProjectRepository",
    "TaskRepository",
    "DependencyTracker",
    "TaskScheduler",
    "ProjectManagerResult",
    "ProjectManagerAgent",
]
