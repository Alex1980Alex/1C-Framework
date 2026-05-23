"""Shared utilities for PDF Framework hooks."""

from .hook_lock import hook_lock
from .task_master import (
    add_task,
    cleanup_old_completed,
    complete_task,
    get_pending_tasks,
    has_recent_completion,
)

__all__ = [
    "add_task",
    "complete_task",
    "get_pending_tasks",
    "has_recent_completion",
    "cleanup_old_completed",
    "hook_lock",
]
