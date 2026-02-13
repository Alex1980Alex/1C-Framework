"""Shared utilities for PDF Framework hooks."""
from .task_master import (
    add_task,
    complete_task,
    get_pending_tasks,
    has_recent_completion,
    cleanup_old_completed,
)
from .hook_lock import hook_lock

__all__ = [
    "add_task",
    "complete_task",
    "get_pending_tasks",
    "has_recent_completion",
    "cleanup_old_completed",
    "hook_lock",
]
