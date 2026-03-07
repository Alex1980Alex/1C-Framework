"""
PROJECT-MANAGER Agent Module.

Multi-project coordinator for the Development Pipeline.
Manages task dependencies, scheduling, and project status tracking.
"""

from agents.project_manager.models import (
    ProjectStatus,
    TaskStatus,
    TaskPriority,
    DependencyType,
    Task,
    TaskDependency,
    Project,
    ProjectManagerConfig,
    ProjectManagerInput,
    ProjectManagerOutput,
)

from agents.project_manager.repository import (
    ProjectRepository,
    TaskRepository,
)

from agents.project_manager.dependency_tracker import (
    DependencyGraph,
    DependencyTracker,
)

from agents.project_manager.scheduler import (
    SchedulingStrategy,
    ScheduledTask,
    Schedule,
    TaskScheduler,
)

from agents.project_manager.agent import (
    ProjectManagerResult,
    ProjectManagerAgent,
)


__all__ = [
    # Enums
    "ProjectStatus",
    "TaskStatus",
    "TaskPriority",
    "DependencyType",
    "SchedulingStrategy",
    # Data classes
    "Task",
    "TaskDependency",
    "Project",
    "ProjectManagerConfig",
    "ProjectManagerInput",
    "ProjectManagerOutput",
    "ScheduledTask",
    "Schedule",
    "DependencyGraph",
    # Classes
    "ProjectRepository",
    "TaskRepository",
    "DependencyTracker",
    "TaskScheduler",
    "ProjectManagerResult",
    "ProjectManagerAgent",
]
