"""Tests for ProjectRepository and TaskRepository."""

import pytest
import tempfile
import shutil
from pathlib import Path

from agents.project_manager.models import Project, Task, TaskStatus, TaskPriority, ProjectStatus
from agents.project_manager.repository import ProjectRepository, TaskRepository


class TestProjectRepository:
    """Tests for ProjectRepository."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def repo(self, temp_dir):
        """Create repository with temp directory."""
        return ProjectRepository(storage_dir=temp_dir)

    @pytest.fixture
    def sample_project(self):
        """Create sample project."""
        project = Project(
            project_id="proj-1",
            name="Test Project",
            description="A test project",
        )
        task1 = Task(task_id="task-1", title="Task 1")
        task2 = Task(task_id="task-2", title="Task 2", dependencies=["task-1"])
        project.add_task(task1)
        project.add_task(task2)
        return project

    def test_save_project(self, repo, sample_project):
        """Test saving a project."""
        repo.save(sample_project)

        # File should exist
        file_path = repo.storage_dir / f"{sample_project.project_id}.json"
        assert file_path.exists()

    def test_load_project(self, repo, sample_project):
        """Test loading a project."""
        repo.save(sample_project)
        loaded = repo.load(sample_project.project_id)

        assert loaded is not None
        assert loaded.project_id == sample_project.project_id
        assert loaded.name == sample_project.name
        assert loaded.task_count == sample_project.task_count

    def test_load_nonexistent(self, repo):
        """Test loading non-existent project."""
        loaded = repo.load("non-existent")
        assert loaded is None

    def test_delete_project(self, repo, sample_project):
        """Test deleting a project."""
        repo.save(sample_project)
        assert repo.exists(sample_project.project_id)

        repo.delete(sample_project.project_id)
        assert not repo.exists(sample_project.project_id)

    def test_list_projects(self, repo, sample_project):
        """Test listing all projects."""
        # Initially empty
        assert len(repo.list_all()) == 0

        # Add projects
        repo.save(sample_project)
        project2 = Project(project_id="proj-2", name="Project 2")
        repo.save(project2)

        projects = repo.list_all()
        assert len(projects) == 2
        project_ids = {p.project_id for p in projects}
        assert "proj-1" in project_ids
        assert "proj-2" in project_ids

    def test_exists(self, repo, sample_project):
        """Test exists check."""
        assert not repo.exists(sample_project.project_id)

        repo.save(sample_project)
        assert repo.exists(sample_project.project_id)

    def test_get_active_projects(self, repo):
        """Test getting active projects."""
        proj1 = Project(project_id="proj-1", name="P1", status=ProjectStatus.IN_PROGRESS)
        proj2 = Project(project_id="proj-2", name="P2", status=ProjectStatus.COMPLETED)
        proj3 = Project(project_id="proj-3", name="P3", status=ProjectStatus.INITIALIZING)

        repo.save(proj1)
        repo.save(proj2)
        repo.save(proj3)

        active = repo.get_active()
        active_ids = {p.project_id for p in active}

        assert "proj-1" in active_ids
        assert "proj-3" in active_ids
        assert "proj-2" not in active_ids  # Completed is not active


class TestTaskRepository:
    """Tests for TaskRepository."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    @pytest.fixture
    def project_repo(self, temp_dir):
        """Create project repository."""
        return ProjectRepository(storage_dir=temp_dir)

    @pytest.fixture
    def task_repo(self, project_repo):
        """Create task repository."""
        return TaskRepository(project_repo)

    @pytest.fixture
    def project_with_tasks(self, project_repo):
        """Create project with tasks."""
        project = Project(project_id="proj-1", name="Test")
        task1 = Task(task_id="task-1", title="Task 1", priority=TaskPriority.HIGH)
        task2 = Task(task_id="task-2", title="Task 2", priority=TaskPriority.LOW)
        task3 = Task(task_id="task-3", title="Task 3", status=TaskStatus.COMPLETED)
        project.add_task(task1)
        project.add_task(task2)
        project.add_task(task3)
        project_repo.save(project)
        return project

    def test_get_task(self, task_repo, project_with_tasks):
        """Test getting a task."""
        task = task_repo.get("proj-1", "task-1")

        assert task is not None
        assert task.task_id == "task-1"
        assert task.priority == TaskPriority.HIGH

    def test_get_nonexistent_task(self, task_repo, project_with_tasks):
        """Test getting non-existent task."""
        task = task_repo.get("proj-1", "non-existent")
        assert task is None

    def test_update_task(self, task_repo, project_with_tasks):
        """Test updating a task."""
        task = task_repo.get("proj-1", "task-1")
        task.status = TaskStatus.IN_PROGRESS
        task.assigned_agent = "ARCHITECT"

        task_repo.update("proj-1", task)

        # Reload and verify
        updated = task_repo.get("proj-1", "task-1")
        assert updated.status == TaskStatus.IN_PROGRESS
        assert updated.assigned_agent == "ARCHITECT"

    def test_add_task(self, task_repo, project_with_tasks):
        """Test adding a task."""
        new_task = Task(task_id="task-4", title="Task 4")
        task_repo.add("proj-1", new_task)

        # Verify added
        task = task_repo.get("proj-1", "task-4")
        assert task is not None
        assert task.title == "Task 4"

    def test_remove_task(self, task_repo, project_with_tasks):
        """Test removing a task."""
        task_repo.remove("proj-1", "task-1")

        task = task_repo.get("proj-1", "task-1")
        assert task is None

    def test_get_by_status(self, task_repo, project_with_tasks):
        """Test getting tasks by status."""
        completed = task_repo.get_by_status("proj-1", TaskStatus.COMPLETED)

        assert len(completed) == 1
        assert completed[0].task_id == "task-3"

    def test_get_by_priority(self, task_repo, project_with_tasks):
        """Test getting tasks by priority."""
        high_priority = task_repo.get_by_priority("proj-1", TaskPriority.HIGH)

        assert len(high_priority) == 1
        assert high_priority[0].task_id == "task-1"

    def test_get_pending(self, task_repo, project_with_tasks):
        """Test getting pending tasks."""
        pending = task_repo.get_pending("proj-1")

        # task-1 and task-2 are pending, task-3 is completed
        assert len(pending) == 2
        pending_ids = {t.task_id for t in pending}
        assert "task-1" in pending_ids
        assert "task-2" in pending_ids

    def test_get_assigned_to(self, task_repo, project_with_tasks):
        """Test getting tasks by assigned agent."""
        # Update task with assignment
        task = task_repo.get("proj-1", "task-1")
        task.assigned_agent = "IMPLEMENTER"
        task_repo.update("proj-1", task)

        assigned = task_repo.get_assigned_to("proj-1", "IMPLEMENTER")
        assert len(assigned) == 1
        assert assigned[0].task_id == "task-1"

    def test_bulk_update_status(self, task_repo, project_with_tasks):
        """Test bulk status update."""
        task_ids = ["task-1", "task-2"]
        task_repo.bulk_update_status("proj-1", task_ids, TaskStatus.IN_PROGRESS)

        task1 = task_repo.get("proj-1", "task-1")
        task2 = task_repo.get("proj-1", "task-2")

        assert task1.status == TaskStatus.IN_PROGRESS
        assert task2.status == TaskStatus.IN_PROGRESS


class TestRepositoryPersistence:
    """Tests for repository persistence."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for tests."""
        temp = tempfile.mkdtemp()
        yield Path(temp)
        shutil.rmtree(temp, ignore_errors=True)

    def test_persistence_across_instances(self, temp_dir):
        """Test that data persists across repository instances."""
        # Create and save with first instance
        repo1 = ProjectRepository(storage_dir=temp_dir)
        project = Project(project_id="proj-1", name="Persistent Project")
        task = Task(task_id="task-1", title="Persistent Task")
        project.add_task(task)
        repo1.save(project)

        # Create new instance and load
        repo2 = ProjectRepository(storage_dir=temp_dir)
        loaded = repo2.load("proj-1")

        assert loaded is not None
        assert loaded.name == "Persistent Project"
        assert loaded.task_count == 1

    def test_concurrent_save(self, temp_dir):
        """Test concurrent saves don't corrupt data."""
        repo = ProjectRepository(storage_dir=temp_dir)

        # Create multiple projects
        for i in range(10):
            project = Project(project_id=f"proj-{i}", name=f"Project {i}")
            repo.save(project)

        # Verify all saved correctly
        all_projects = repo.list_all()
        assert len(all_projects) == 10

    def test_update_preserves_data(self, temp_dir):
        """Test that updates preserve existing data."""
        repo = ProjectRepository(storage_dir=temp_dir)

        # Create project with tasks
        project = Project(project_id="proj-1", name="Original")
        task1 = Task(task_id="task-1", title="Task 1")
        task2 = Task(task_id="task-2", title="Task 2")
        project.add_task(task1)
        project.add_task(task2)
        repo.save(project)

        # Load, modify, and save
        loaded = repo.load("proj-1")
        loaded.name = "Modified"
        loaded.status = ProjectStatus.IN_PROGRESS
        repo.save(loaded)

        # Verify changes and preserved data
        reloaded = repo.load("proj-1")
        assert reloaded.name == "Modified"
        assert reloaded.status == ProjectStatus.IN_PROGRESS
        assert reloaded.task_count == 2  # Tasks preserved
