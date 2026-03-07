"""
Orchestrator Package for Parallel Pipeline Execution.

Sprint 3.2: Parallel Branches - enables parallel execution of independent tasks.
"""

from .models import (
    TaskNode,
    TaskGraph,
    TaskDependency,
    DependencyType,
    ExecutionPriority,
    ParallelGroup,
    MergeStrategy,
    ConflictType,
    ConflictResolution,
    TaskStatus,
    Conflict,
)

from .task_decomposer import (
    TaskDecomposer,
    decompose_task,
    find_parallel_groups,
    build_dependency_graph,
)

from .parallel_executor import (
    ExecutionState,
    TaskResult,
    ExecutionProgress,
    ExecutionReport,
    TaskExecutorInterface,
    MockTaskExecutor,
    ParallelExecutor,
    execute_graph,
    execute_tasks,
    run_graph_sync,
)

from .orchestrator import (
    PipelineOrchestrator,
    OrchestratorState,
    CheckpointAction,
    Checkpoint,
    PipelineConfig,
    PipelineResult,
    create_pipeline,
    run_pipeline_sync,
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
