"""
Repository for PROJECT-MANAGER Agent.

Handles persistence and retrieval of projects and tasks.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from agents.project_manager.models import (
    Project,
    ProjectStatus,
    Task,
    TaskStatus,
    TaskPriority,
    ProjectManagerConfig,
)


class ProjectRepository:
    """
    Repository for project persistence.

    Stores projects as JSON files in the configured directory.
    """

    def __init__(self, config: Optional[ProjectManagerConfig] = None) -> None:
        """Initialize repository."""
        self.config = config or ProjectManagerConfig()
        self._ensure_dirs()

    def _ensure_dirs(self) -> None:
        """Ensure required directories exist."""
        self.config.projects_dir.mkdir(parents=True, exist_ok=True)

    def _get_project_file(self, project_id: str) -> Path:
        """Get path to project file."""
        return self.config.projects_dir / f"{project_id}.json"

    def save(self, project: Project) -> bool:
        """
        Save project to disk.

        Args:
            project: Project to save

        Returns:
            True if successful
        """
        try:
            file_path = self._get_project_file(project.project_id)
            data = project.to_dict()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False, default=str)

            return True
        except Exception as e:
            print(f"Error saving project {project.project_id}: {e}")
            return False

    def load(self, project_id: str) -> Optional[Project]:
        """
        Load project from disk.

        Args:
            project_id: ID of project to load

        Returns:
            Project if found, None otherwise
        """
        try:
            file_path = self._get_project_file(project_id)
            if not file_path.exists():
                return None

            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            return self._dict_to_project(data)
        except Exception as e:
            print(f"Error loading project {project_id}: {e}")
            return None

    def delete(self, project_id: str) -> bool:
        """
        Delete project from disk.

        Args:
            project_id: ID of project to delete

        Returns:
            True if successful
        """
        try:
            file_path = self._get_project_file(project_id)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            print(f"Error deleting project {project_id}: {e}")
            return False

    def list_all(self) -> List[Project]:
        """
        List all projects.

        Returns:
            List of all projects
        """
        projects = []
        for file_path in self.config.projects_dir.glob("*.json"):
            project_id = file_path.stem
            project = self.load(project_id)
            if project:
                projects.append(project)
        return projects

    def list_active(self) -> List[Project]:
        """
        List active projects.

        Returns:
            List of active projects
        """
        return [p for p in self.list_all() if p.status.is_active]

    def list_by_status(self, status: ProjectStatus) -> List[Project]:
        """
        List projects by status.

        Args:
            status: Status to filter by

        Returns:
            List of matching projects
        """
        return [p for p in self.list_all() if p.status == status]

    def exists(self, project_id: str) -> bool:
        """
        Check if project exists.

        Args:
            project_id: ID to check

        Returns:
            True if exists
        """
        return self._get_project_file(project_id).exists()

    def _dict_to_project(self, data: Dict[str, Any]) -> Project:
        """Convert dictionary to Project object."""
        # Parse tasks
        tasks = []
        for task_data in data.get("tasks", []):
            task = Task(
                task_id=task_data["task_id"],
                title=task_data["title"],
                description=task_data.get("description", ""),
                priority=TaskPriority(task_data.get("priority", "medium")),
                status=TaskStatus(task_data.get("status", "pending")),
                assigned_agent=task_data.get("assigned_agent"),
                created_at=datetime.fromisoformat(task_data["created_at"]),
                started_at=datetime.fromisoformat(task_data["started_at"]) if task_data.get("started_at") else None,
                completed_at=datetime.fromisoformat(task_data["completed_at"]) if task_data.get("completed_at") else None,
                estimated_hours=task_data.get("estimated_hours"),
                dependencies=task_data.get("dependencies", []),
                input_artifacts=task_data.get("input_artifacts", []),
                output_artifacts=task_data.get("output_artifacts", []),
                tags=task_data.get("tags", []),
                metadata=task_data.get("metadata", {}),
            )
            tasks.append(task)

        # Parse project
        project = Project(
            project_id=data["project_id"],
            name=data["name"],
            description=data.get("description", ""),
            status=ProjectStatus(data.get("status", "not_started")),
            project_path=Path(data["project_path"]) if data.get("project_path") else None,
            config_path=Path(data["config_path"]) if data.get("config_path") else None,
            tasks=tasks,
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            current_run_id=data.get("current_run_id"),
            run_history=data.get("run_history", []),
            tags=data.get("tags", []),
            metadata=data.get("metadata", {}),
        )

        return project


class TaskRepository:
    """
    Repository for task operations within projects.

    Provides task-specific operations on top of ProjectRepository.
    """

    def __init__(self, project_repo: ProjectRepository) -> None:
        """Initialize with project repository."""
        self.project_repo = project_repo

    def get_task(self, project_id: str, task_id: str) -> Optional[Task]:
        """
        Get specific task.

        Args:
            project_id: Project containing task
            task_id: Task ID

        Returns:
            Task if found
        """
        project = self.project_repo.load(project_id)
        if project:
            return project.get_task(task_id)
        return None

    def update_task(self, project_id: str, task: Task) -> bool:
        """
        Update task in project.

        Args:
            project_id: Project containing task
            task: Updated task

        Returns:
            True if successful
        """
        project = self.project_repo.load(project_id)
        if not project:
            return False

        # Find and replace task
        for i, t in enumerate(project.tasks):
            if t.task_id == task.task_id:
                project.tasks[i] = task
                return self.project_repo.save(project)

        return False

    def add_task(self, project_id: str, task: Task) -> bool:
        """
        Add task to project.

        Args:
            project_id: Project to add to
            task: Task to add

        Returns:
            True if successful
        """
        project = self.project_repo.load(project_id)
        if not project:
            return False

        project.add_task(task)
        return self.project_repo.save(project)

    def delete_task(self, project_id: str, task_id: str) -> bool:
        """
        Delete task from project.

        Args:
            project_id: Project containing task
            task_id: Task to delete

        Returns:
            True if successful
        """
        project = self.project_repo.load(project_id)
        if not project:
            return False

        project.tasks = [t for t in project.tasks if t.task_id != task_id]
        return self.project_repo.save(project)

    def get_pending_tasks(self, project_id: str) -> List[Task]:
        """
        Get pending tasks for project.

        Args:
            project_id: Project ID

        Returns:
            List of pending tasks
        """
        project = self.project_repo.load(project_id)
        if not project:
            return []

        return [t for t in project.tasks if t.status == TaskStatus.PENDING]

    def get_tasks_by_priority(self, project_id: str, priority: TaskPriority) -> List[Task]:
        """
        Get tasks by priority.

        Args:
            project_id: Project ID
            priority: Priority to filter

        Returns:
            List of matching tasks
        """
        project = self.project_repo.load(project_id)
        if not project:
            return []

        return [t for t in project.tasks if t.priority == priority]

    def get_ready_tasks(self, project_id: str) -> List[Task]:
        """
        Get tasks ready to execute (no unmet dependencies).

        Args:
            project_id: Project ID

        Returns:
            List of ready tasks sorted by priority
        """
        project = self.project_repo.load(project_id)
        if not project:
            return []

        completed_ids = {t.task_id for t in project.tasks if t.status == TaskStatus.COMPLETED}

        ready = []
        for task in project.tasks:
            if task.status != TaskStatus.PENDING:
                continue

            # Check all dependencies are completed
            deps_met = all(dep_id in completed_ids for dep_id in task.dependencies)
            if deps_met:
                ready.append(task)

        # Sort by priority (highest first)
        ready.sort(key=lambda t: t.priority.weight, reverse=True)
        return ready
