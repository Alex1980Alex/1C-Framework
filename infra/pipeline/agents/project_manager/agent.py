"""
PROJECT-MANAGER Agent - Main orchestrator for multi-project management.

Coordinates multiple pipelines, tracks project-level status,
manages dependencies between tasks, and provides resource allocation.
"""

import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from uuid import uuid4

from agents.project_manager.models import (
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
    TaskPriority,
    ProjectManagerConfig,
    ProjectManagerInput,
    ProjectManagerOutput,
)
from agents.project_manager.repository import ProjectRepository, TaskRepository
from agents.project_manager.dependency_tracker import DependencyTracker
from agents.project_manager.scheduler import TaskScheduler, SchedulingStrategy, Schedule


@dataclass
class ProjectManagerResult:
    """Result of project manager operation."""

    success: bool
    message: str
    output: Optional[ProjectManagerOutput] = None
    execution_time_ms: float = 0

    @property
    def summary(self) -> str:
        """Get result summary."""
        return f"{'✅' if self.success else '❌'} {self.message}"


class ProjectManagerAgent:
    """
    PROJECT-MANAGER Agent - Multi-project coordinator for Development Pipeline.

    Responsibilities:
    1. Create and manage multiple projects
    2. Track project and task status
    3. Manage task dependencies
    4. Schedule and prioritize work
    5. Coordinate between pipeline runs

    Usage:
        agent = ProjectManagerAgent()

        # Create project
        result = agent.create_project(
            project_id="GKSTCPLK-1996",
            name="Implementation Project",
            tasks=[
                {"title": "Initialize context", "priority": "high"},
                {"title": "Create specification", "dependencies": ["task_1"]},
            ]
        )

        # Get project status
        status = agent.get_project_status("GKSTCPLK-1996")

        # Get next task
        next_task = agent.get_next_task("GKSTCPLK-1996")
    """

    def __init__(self, config: Optional[ProjectManagerConfig] = None) -> None:
        """
        Initialize agent.

        Args:
            config: Agent configuration
        """
        self.config = config or ProjectManagerConfig()
        self.project_repo = ProjectRepository(self.config)
        self.task_repo = TaskRepository(self.project_repo)
        self.dependency_tracker = DependencyTracker()
        self.scheduler = TaskScheduler(self.dependency_tracker)

    # ============ Project Operations ============

    def create_project(
        self,
        project_id: str,
        name: str,
        description: str = "",
        project_path: Optional[Path] = None,
        tasks: Optional[List[Dict[str, Any]]] = None,
        tags: Optional[List[str]] = None,
    ) -> ProjectManagerResult:
        """
        Create new project.

        Args:
            project_id: Unique project identifier
            name: Human-readable project name
            description: Project description
            project_path: Path to project files
            tasks: Initial list of tasks
            tags: Project tags

        Returns:
            Result of operation
        """
        start_time = time.time()

        # Check if already exists
        if self.project_repo.exists(project_id):
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' already exists",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Create project
        project = Project(
            project_id=project_id,
            name=name,
            description=description,
            project_path=project_path,
            tags=tags or [],
        )

        # Add tasks if provided
        if tasks:
            for i, task_data in enumerate(tasks):
                task = self._create_task_from_dict(task_data, i + 1)
                project.add_task(task)

        # Validate dependencies
        is_valid, errors = self.dependency_tracker.validate_dependencies(project)
        if not is_valid:
            return ProjectManagerResult(
                success=False,
                message=f"Invalid dependencies: {'; '.join(errors)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Save project
        if not self.project_repo.save(project):
            return ProjectManagerResult(
                success=False,
                message="Failed to save project",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        return ProjectManagerResult(
            success=True,
            message=f"Project '{name}' created with {len(project.tasks)} tasks",
            output=ProjectManagerOutput(
                success=True,
                action="create_project",
                message=f"Created project {project_id}",
                project=project,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def get_project(self, project_id: str) -> Optional[Project]:
        """
        Get project by ID.

        Args:
            project_id: Project identifier

        Returns:
            Project if found
        """
        return self.project_repo.load(project_id)

    def delete_project(self, project_id: str) -> ProjectManagerResult:
        """
        Delete project.

        Args:
            project_id: Project to delete

        Returns:
            Result of operation
        """
        start_time = time.time()

        if not self.project_repo.exists(project_id):
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if self.project_repo.delete(project_id):
            return ProjectManagerResult(
                success=True,
                message=f"Project '{project_id}' deleted",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        return ProjectManagerResult(
            success=False,
            message="Failed to delete project",
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def list_projects(
        self,
        status: Optional[ProjectStatus] = None,
        active_only: bool = False,
    ) -> List[Project]:
        """
        List projects.

        Args:
            status: Filter by status
            active_only: Only return active projects

        Returns:
            List of projects
        """
        if active_only:
            return self.project_repo.list_active()
        elif status:
            return self.project_repo.list_by_status(status)
        return self.project_repo.list_all()

    # ============ Project Status Operations ============

    def start_project(self, project_id: str) -> ProjectManagerResult:
        """
        Start project execution.

        Args:
            project_id: Project to start

        Returns:
            Result of operation
        """
        start_time = time.time()

        project = self.project_repo.load(project_id)
        if not project:
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if project.status.is_active:
            return ProjectManagerResult(
                success=False,
                message=f"Project already {project.status.ru_name}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        project.status = ProjectStatus.INITIALIZING
        project.started_at = datetime.now()
        project.current_run_id = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        project.run_history.append(project.current_run_id)

        self.project_repo.save(project)

        return ProjectManagerResult(
            success=True,
            message=f"Project '{project.name}' started",
            output=ProjectManagerOutput(
                success=True,
                action="start_project",
                message=f"Started project {project_id}",
                project=project,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def pause_project(self, project_id: str) -> ProjectManagerResult:
        """Pause project execution."""
        start_time = time.time()

        project = self.project_repo.load(project_id)
        if not project:
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if not project.status.is_active:
            return ProjectManagerResult(
                success=False,
                message=f"Project not active (status: {project.status.ru_name})",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        project.status = ProjectStatus.ON_HOLD
        self.project_repo.save(project)

        return ProjectManagerResult(
            success=True,
            message=f"Project '{project.name}' paused",
            output=ProjectManagerOutput(
                success=True,
                action="pause_project",
                message=f"Paused project {project_id}",
                project=project,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def resume_project(self, project_id: str) -> ProjectManagerResult:
        """Resume paused project."""
        start_time = time.time()

        project = self.project_repo.load(project_id)
        if not project:
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        if project.status != ProjectStatus.ON_HOLD:
            return ProjectManagerResult(
                success=False,
                message=f"Project not paused (status: {project.status.ru_name})",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        project.status = ProjectStatus.IN_PROGRESS
        self.project_repo.save(project)

        return ProjectManagerResult(
            success=True,
            message=f"Project '{project.name}' resumed",
            output=ProjectManagerOutput(
                success=True,
                action="resume_project",
                message=f"Resumed project {project_id}",
                project=project,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def complete_project(self, project_id: str) -> ProjectManagerResult:
        """Mark project as completed."""
        start_time = time.time()

        project = self.project_repo.load(project_id)
        if not project:
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        project.status = ProjectStatus.COMPLETED
        project.completed_at = datetime.now()
        self.project_repo.save(project)

        return ProjectManagerResult(
            success=True,
            message=f"Project '{project.name}' completed",
            output=ProjectManagerOutput(
                success=True,
                action="complete_project",
                message=f"Completed project {project_id}",
                project=project,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    # ============ Task Operations ============

    def add_task(
        self,
        project_id: str,
        title: str,
        description: str = "",
        priority: str = "medium",
        dependencies: Optional[List[str]] = None,
        assigned_agent: Optional[str] = None,
        estimated_hours: Optional[float] = None,
    ) -> ProjectManagerResult:
        """
        Add task to project.

        Args:
            project_id: Project to add task to
            title: Task title
            description: Task description
            priority: Priority level (critical/high/medium/low)
            dependencies: List of task IDs this depends on
            assigned_agent: Agent to assign
            estimated_hours: Estimated hours to complete

        Returns:
            Result of operation
        """
        start_time = time.time()

        project = self.project_repo.load(project_id)
        if not project:
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        task_id = f"task_{len(project.tasks) + 1}"
        task = Task(
            task_id=task_id,
            title=title,
            description=description,
            priority=TaskPriority(priority),
            dependencies=dependencies or [],
            assigned_agent=assigned_agent,
            estimated_hours=estimated_hours,
        )

        project.add_task(task)

        # Validate dependencies
        is_valid, errors = self.dependency_tracker.validate_dependencies(project)
        if not is_valid:
            return ProjectManagerResult(
                success=False,
                message=f"Invalid dependencies: {'; '.join(errors)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        self.project_repo.save(project)

        return ProjectManagerResult(
            success=True,
            message=f"Task '{title}' added to project",
            output=ProjectManagerOutput(
                success=True,
                action="add_task",
                message=f"Added task {task_id}",
                task=task,
                project=project,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def start_task(self, project_id: str, task_id: str) -> ProjectManagerResult:
        """Start task execution."""
        start_time = time.time()

        project = self.project_repo.load(project_id)
        if not project:
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        task = project.get_task(task_id)
        if not task:
            return ProjectManagerResult(
                success=False,
                message=f"Task '{task_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        # Check dependencies
        can_start, unmet = self.dependency_tracker.can_start(project, task_id)
        if not can_start:
            return ProjectManagerResult(
                success=False,
                message=f"Cannot start: unmet dependencies: {', '.join(unmet)}",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()

        # Update project status if needed
        if project.status == ProjectStatus.INITIALIZING:
            project.status = ProjectStatus.IN_PROGRESS

        self.project_repo.save(project)

        return ProjectManagerResult(
            success=True,
            message=f"Task '{task.title}' started",
            output=ProjectManagerOutput(
                success=True,
                action="start_task",
                message=f"Started task {task_id}",
                task=task,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def complete_task(self, project_id: str, task_id: str) -> ProjectManagerResult:
        """Complete task."""
        start_time = time.time()

        project = self.project_repo.load(project_id)
        if not project:
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        task = project.get_task(task_id)
        if not task:
            return ProjectManagerResult(
                success=False,
                message=f"Task '{task_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.now()

        # Check if all tasks completed
        all_completed = all(t.status == TaskStatus.COMPLETED for t in project.tasks)
        if all_completed:
            project.status = ProjectStatus.COMPLETED
            project.completed_at = datetime.now()

        self.project_repo.save(project)

        return ProjectManagerResult(
            success=True,
            message=f"Task '{task.title}' completed",
            output=ProjectManagerOutput(
                success=True,
                action="complete_task",
                message=f"Completed task {task_id}",
                task=task,
                project=project,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def fail_task(
        self,
        project_id: str,
        task_id: str,
        error_message: str = "",
    ) -> ProjectManagerResult:
        """Mark task as failed."""
        start_time = time.time()

        project = self.project_repo.load(project_id)
        if not project:
            return ProjectManagerResult(
                success=False,
                message=f"Project '{project_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        task = project.get_task(task_id)
        if not task:
            return ProjectManagerResult(
                success=False,
                message=f"Task '{task_id}' not found",
                execution_time_ms=(time.time() - start_time) * 1000,
            )

        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now()
        task.metadata["error"] = error_message

        # Get impacted tasks
        impacted = self.dependency_tracker.get_impact_of_failure(project, task_id)
        for imp_task in impacted:
            imp_task.status = TaskStatus.WAITING_DEPENDENCY

        self.project_repo.save(project)

        return ProjectManagerResult(
            success=True,
            message=f"Task '{task.title}' failed, {len(impacted)} tasks blocked",
            output=ProjectManagerOutput(
                success=True,
                action="fail_task",
                message=f"Task {task_id} failed",
                task=task,
            ),
            execution_time_ms=(time.time() - start_time) * 1000,
        )

    def get_next_task(self, project_id: str) -> Optional[Task]:
        """
        Get next task to execute.

        Args:
            project_id: Project ID

        Returns:
            Next ready task, or None
        """
        project = self.project_repo.load(project_id)
        if not project:
            return None

        return self.scheduler.get_next_task(project)

    def get_ready_tasks(self, project_id: str) -> List[Task]:
        """
        Get all tasks ready for execution.

        Args:
            project_id: Project ID

        Returns:
            List of ready tasks
        """
        project = self.project_repo.load(project_id)
        if not project:
            return []

        return self.dependency_tracker.get_ready_tasks(project)

    # ============ Scheduling Operations ============

    def create_schedule(
        self,
        project_id: str,
        strategy: str = "priority_first",
    ) -> Optional[Schedule]:
        """
        Create schedule for project.

        Args:
            project_id: Project to schedule
            strategy: Scheduling strategy

        Returns:
            Schedule if successful
        """
        project = self.project_repo.load(project_id)
        if not project:
            return None

        return self.scheduler.create_schedule(
            project,
            SchedulingStrategy(strategy),
        )

    def get_critical_path(self, project_id: str) -> List[Task]:
        """
        Get critical path for project.

        Args:
            project_id: Project ID

        Returns:
            List of tasks on critical path
        """
        project = self.project_repo.load(project_id)
        if not project:
            return []

        return self.scheduler.get_critical_path(project)

    # ============ Status & Reporting ============

    def get_project_status(self, project_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed project status.

        Args:
            project_id: Project ID

        Returns:
            Status dictionary
        """
        project = self.project_repo.load(project_id)
        if not project:
            return None

        ready_tasks = self.dependency_tracker.get_ready_tasks(project)
        blocked_tasks = self.dependency_tracker.get_blocked_tasks(project)

        return {
            "project_id": project.project_id,
            "name": project.name,
            "status": project.status.value,
            "status_ru": project.status.ru_name,
            "progress_percent": project.progress_percent,
            "task_count": project.task_count,
            "completed_tasks": project.completed_task_count,
            "ready_tasks": len(ready_tasks),
            "blocked_tasks": len(blocked_tasks),
            "started_at": project.started_at.isoformat() if project.started_at else None,
            "current_run_id": project.current_run_id,
        }

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all projects.

        Returns:
            Summary dictionary
        """
        projects = self.project_repo.list_all()

        return {
            "total_projects": len(projects),
            "active_projects": sum(1 for p in projects if p.status.is_active),
            "completed_projects": sum(1 for p in projects if p.status == ProjectStatus.COMPLETED),
            "blocked_projects": sum(1 for p in projects if p.status == ProjectStatus.BLOCKED),
            "total_tasks": sum(p.task_count for p in projects),
            "completed_tasks": sum(p.completed_task_count for p in projects),
            "projects": [
                {
                    "id": p.project_id,
                    "name": p.name,
                    "status": p.status.ru_name,
                    "progress": f"{p.progress_percent:.0f}%",
                }
                for p in projects
            ],
        }

    # ============ Helper Methods ============

    def _create_task_from_dict(self, data: Dict[str, Any], index: int) -> Task:
        """Create Task from dictionary."""
        task_id = data.get("task_id", f"task_{index}")
        return Task(
            task_id=task_id,
            title=data.get("title", f"Task {index}"),
            description=data.get("description", ""),
            priority=TaskPriority(data.get("priority", "medium")),
            dependencies=data.get("dependencies", []),
            assigned_agent=data.get("assigned_agent"),
            estimated_hours=data.get("estimated_hours"),
            tags=data.get("tags", []),
        )

    def run(self, input_data: ProjectManagerInput) -> ProjectManagerOutput:
        """
        Execute action based on input.

        Args:
            input_data: Input specifying action and parameters

        Returns:
            Output with results
        """
        start_time = time.time()

        action = input_data.action.lower()

        try:
            if action == "create":
                result = self.create_project(
                    project_id=input_data.project_id or str(uuid4())[:8],
                    name=input_data.project_name or "New Project",
                    project_path=input_data.project_path,
                    tasks=input_data.tasks,
                )
                return result.output or ProjectManagerOutput(
                    success=result.success,
                    action=action,
                    message=result.message,
                )

            elif action == "start":
                result = self.start_project(input_data.project_id)
                return result.output or ProjectManagerOutput(
                    success=result.success,
                    action=action,
                    message=result.message,
                )

            elif action == "status":
                status = self.get_project_status(input_data.project_id)
                return ProjectManagerOutput(
                    success=status is not None,
                    action=action,
                    message="Project status retrieved" if status else "Project not found",
                    project=self.get_project(input_data.project_id),
                )

            elif action == "list":
                projects = self.list_projects()
                return ProjectManagerOutput(
                    success=True,
                    action=action,
                    message=f"Found {len(projects)} projects",
                    projects=projects,
                )

            elif action == "next_task":
                task = self.get_next_task(input_data.project_id)
                return ProjectManagerOutput(
                    success=task is not None,
                    action=action,
                    message="Next task found" if task else "No tasks ready",
                    task=task,
                )

            else:
                return ProjectManagerOutput(
                    success=False,
                    action=action,
                    message=f"Unknown action: {action}",
                    error_code="UNKNOWN_ACTION",
                )

        except Exception as e:
            return ProjectManagerOutput(
                success=False,
                action=action,
                message=str(e),
                error_code="EXCEPTION",
                error_details=str(e),
                execution_time_ms=(time.time() - start_time) * 1000,
            )
