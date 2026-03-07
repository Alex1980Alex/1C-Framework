"""
Models for PROJECT-MANAGER Agent.

Defines data structures for multi-project coordination,
task dependencies, and project-level status tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, List, Any


class ProjectStatus(Enum):
    """Status of a managed project."""

    NOT_STARTED = "not_started"
    INITIALIZING = "initializing"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @property
    def is_active(self) -> bool:
        """Check if project is actively being worked on."""
        return self in (self.INITIALIZING, self.IN_PROGRESS)

    @property
    def is_terminal(self) -> bool:
        """Check if project is in terminal state."""
        return self in (self.COMPLETED, self.FAILED, self.CANCELLED)

    @property
    def ru_name(self) -> str:
        """Russian name of status."""
        names = {
            self.NOT_STARTED: "Не начат",
            self.INITIALIZING: "Инициализация",
            self.IN_PROGRESS: "В работе",
            self.BLOCKED: "Заблокирован",
            self.ON_HOLD: "На паузе",
            self.COMPLETED: "Завершён",
            self.FAILED: "Ошибка",
            self.CANCELLED: "Отменён",
        }
        return names.get(self, "Неизвестно")


class TaskPriority(Enum):
    """Priority levels for tasks."""

    CRITICAL = "critical"    # P0 - Must be done immediately
    HIGH = "high"            # P1 - Important
    MEDIUM = "medium"        # P2 - Nice to have
    LOW = "low"              # P3 - Can wait

    @property
    def weight(self) -> int:
        """Numeric weight for sorting (higher = more important)."""
        weights = {
            self.CRITICAL: 100,
            self.HIGH: 75,
            self.MEDIUM: 50,
            self.LOW: 25,
        }
        return weights.get(self, 0)

    @property
    def ru_name(self) -> str:
        """Russian name."""
        names = {
            self.CRITICAL: "Критический",
            self.HIGH: "Высокий",
            self.MEDIUM: "Средний",
            self.LOW: "Низкий",
        }
        return names.get(self, "Неизвестно")


class TaskStatus(Enum):
    """Status of individual task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_DEPENDENCY = "waiting_dependency"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

    @property
    def is_terminal(self) -> bool:
        """Check if task is in terminal state."""
        return self in (self.COMPLETED, self.FAILED, self.SKIPPED)


class DependencyType(Enum):
    """Types of dependencies between tasks."""

    FINISH_TO_START = "finish_to_start"   # B starts after A finishes
    START_TO_START = "start_to_start"     # B starts when A starts
    FINISH_TO_FINISH = "finish_to_finish" # B finishes when A finishes
    BLOCKING = "blocking"                  # A blocks B completely


@dataclass
class TaskDependency:
    """Dependency between two tasks."""

    source_task_id: str
    target_task_id: str
    dependency_type: DependencyType = DependencyType.FINISH_TO_START
    description: Optional[str] = None

    def is_satisfied(self, source_status: TaskStatus) -> bool:
        """Check if dependency is satisfied based on source task status."""
        if self.dependency_type == DependencyType.FINISH_TO_START:
            return source_status == TaskStatus.COMPLETED
        elif self.dependency_type == DependencyType.START_TO_START:
            return source_status != TaskStatus.PENDING
        elif self.dependency_type == DependencyType.FINISH_TO_FINISH:
            return source_status.is_terminal
        elif self.dependency_type == DependencyType.BLOCKING:
            return source_status == TaskStatus.COMPLETED
        return False


@dataclass
class Task:
    """Individual task within a project."""

    task_id: str
    title: str
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    assigned_agent: Optional[str] = None  # PM-SPEC, ARCHITECT, IMPLEMENTER, etc.

    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    estimated_hours: Optional[float] = None

    # Dependencies
    dependencies: List[str] = field(default_factory=list)  # List of task_ids

    # Artifacts
    input_artifacts: List[str] = field(default_factory=list)
    output_artifacts: List[str] = field(default_factory=list)

    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_hours(self) -> Optional[float]:
        """Calculate actual duration in hours."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return delta.total_seconds() / 3600
        return None

    @property
    def is_blocked(self) -> bool:
        """Check if task has unresolved dependencies."""
        return self.status == TaskStatus.WAITING_DEPENDENCY

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "assigned_agent": self.assigned_agent,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "estimated_hours": self.estimated_hours,
            "dependencies": self.dependencies,
            "input_artifacts": self.input_artifacts,
            "output_artifacts": self.output_artifacts,
            "tags": self.tags,
            "metadata": self.metadata,
        }


@dataclass
class Project:
    """Managed project with tasks and metadata."""

    project_id: str
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.NOT_STARTED

    # Path information
    project_path: Optional[Path] = None
    config_path: Optional[Path] = None

    # Tasks
    tasks: List[Task] = field(default_factory=list)

    # Timing
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Pipeline runs
    current_run_id: Optional[str] = None
    run_history: List[str] = field(default_factory=list)

    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def task_count(self) -> int:
        """Total number of tasks."""
        return len(self.tasks)

    @property
    def completed_task_count(self) -> int:
        """Number of completed tasks."""
        return sum(1 for t in self.tasks if t.status == TaskStatus.COMPLETED)

    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if not self.tasks:
            return 0.0
        return (self.completed_task_count / self.task_count) * 100

    @property
    def blocked_tasks(self) -> List[Task]:
        """Get list of blocked tasks."""
        return [t for t in self.tasks if t.is_blocked]

    @property
    def next_tasks(self) -> List[Task]:
        """Get tasks that are ready to be worked on."""
        return [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING and not t.dependencies
        ]

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID."""
        for task in self.tasks:
            if task.task_id == task_id:
                return task
        return None

    def add_task(self, task: Task) -> None:
        """Add task to project."""
        self.tasks.append(task)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "project_id": self.project_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "project_path": str(self.project_path) if self.project_path else None,
            "config_path": str(self.config_path) if self.config_path else None,
            "tasks": [t.to_dict() for t in self.tasks],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "current_run_id": self.current_run_id,
            "run_history": self.run_history,
            "tags": self.tags,
            "metadata": self.metadata,
            "progress_percent": self.progress_percent,
        }


@dataclass
class ProjectManagerConfig:
    """Configuration for PROJECT-MANAGER Agent."""

    # Paths
    projects_dir: Path = field(default_factory=lambda: Path("cache/projects"))
    state_file: Path = field(default_factory=lambda: Path("cache/project_manager_state.json"))

    # Limits
    max_concurrent_projects: int = 5
    max_tasks_per_project: int = 100

    # Timeouts (seconds)
    project_timeout: int = 3600  # 1 hour
    task_timeout: int = 600      # 10 minutes

    # Auto-save
    auto_save_interval: int = 60  # seconds

    # Notifications
    notify_on_completion: bool = True
    notify_on_failure: bool = True

    def __post_init__(self):
        """Ensure directories exist."""
        self.projects_dir.mkdir(parents=True, exist_ok=True)


@dataclass
class ProjectManagerInput:
    """Input for PROJECT-MANAGER Agent."""

    action: str  # create, start, pause, resume, cancel, status, list
    project_id: Optional[str] = None
    task_id: Optional[str] = None

    # For create action
    project_name: Optional[str] = None
    project_path: Optional[Path] = None
    tasks: Optional[List[Dict[str, Any]]] = None

    # Additional options
    options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectManagerOutput:
    """Output from PROJECT-MANAGER Agent."""

    success: bool
    action: str
    message: str

    # Data
    project: Optional[Project] = None
    projects: Optional[List[Project]] = None
    task: Optional[Task] = None

    # Errors
    error_code: Optional[str] = None
    error_details: Optional[str] = None

    # Metadata
    execution_time_ms: float = 0
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "success": self.success,
            "action": self.action,
            "message": self.message,
            "project": self.project.to_dict() if self.project else None,
            "projects": [p.to_dict() for p in self.projects] if self.projects else None,
            "task": self.task.to_dict() if self.task else None,
            "error_code": self.error_code,
            "error_details": self.error_details,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
        }
