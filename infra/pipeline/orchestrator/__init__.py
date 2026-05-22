"""
Orchestrator Package for Parallel Pipeline Execution.

Sprint 3.2: Parallel Branches - enables parallel execution of independent tasks.
"""

from .models import (
    Conflict,
    ConflictResolution,
    ConflictType,
    DependencyType,
    ExecutionPriority,
    MergeStrategy,
    ParallelGroup,
    TaskDependency,
    TaskGraph,
    TaskNode,
    TaskStatus,
)
from .orchestrator import (
    Checkpoint,
    CheckpointAction,
    OrchestratorState,
    PipelineConfig,
    PipelineOrchestrator,
    PipelineResult,
    create_pipeline,
    run_pipeline_sync,
)
from .parallel_executor import (
    ExecutionProgress,
    ExecutionReport,
    ExecutionState,
    MockTaskExecutor,
    ParallelExecutor,
    TaskExecutorInterface,
    TaskResult,
    execute_graph,
    execute_tasks,
    run_graph_sync,
)
from .task_decomposer import (
    TaskDecomposer,
    build_dependency_graph,
    decompose_task,
    find_parallel_groups,
)

__all__ = [
    # Models
    "TaskNode",
    "TaskGraph",
    "TaskDependency",
    "DependencyType",
    "ExecutionPriority",
    "ParallelGroup",
    "MergeStrategy",
    "ConflictType",
    "ConflictResolution",
    "TaskStatus",
    "Conflict",
    # Task Decomposer
    "TaskDecomposer",
    "decompose_task",
    "find_parallel_groups",
    "build_dependency_graph",
    # Parallel Executor
    "ExecutionState",
    "TaskResult",
    "ExecutionProgress",
    "ExecutionReport",
    "TaskExecutorInterface",
    "MockTaskExecutor",
    "ParallelExecutor",
    "execute_graph",
    "execute_tasks",
    "run_graph_sync",
    # Main Orchestrator (P0)
    "PipelineOrchestrator",
    "OrchestratorState",
    "CheckpointAction",
    "Checkpoint",
    "PipelineConfig",
    "PipelineResult",
    "create_pipeline",
    "run_pipeline_sync",
]
