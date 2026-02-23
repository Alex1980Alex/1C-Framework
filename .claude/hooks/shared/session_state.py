"""
Session State Management for Claude Code Hooks
Provides persistent state storage across hook invocations.

Author: Claude Code
Version: 2.0.0
Updated: 2026-02-23 (Added pending_learn support for Skill-First Enforcement)
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
import threading


# State file location (overridable via SESSION_STATE_PATH env var for testing)
_env_state_path = os.environ.get("SESSION_STATE_PATH")
if _env_state_path:
    STATE_DIR = Path(_env_state_path)
else:
    STATE_DIR = Path(__file__).parent.parent.parent / "data"
STATE_FILE = STATE_DIR / "session-skills.json"


class SessionState:
    """
    Thread-safe session state manager with support for:
    - Activated skills tracking
    - Pending learn notifications (for LEARN phase)
    - Session metadata
    """

    _lock = threading.Lock()
    _state_cache: Optional[Dict[str, Any]] = None

    @classmethod
    def _empty_state(cls) -> Dict[str, Any]:
        """Return initial empty state structure."""
        return {
            "activated_skills": [],
            "pending_learn": None,
            "session_id": None,
            "created_at": None,
            "last_updated": None
        }

    @classmethod
    def _load_state(cls) -> Dict[str, Any]:
        """Load state from disk, with caching."""
        with cls._lock:
            if cls._state_cache is not None:
                return cls._state_cache

            if not STATE_FILE.exists():
                STATE_DIR.mkdir(parents=True, exist_ok=True)
                initial_state = cls._empty_state()
                initial_state["session_id"] = os.urandom(8).hex()
                initial_state["created_at"] = datetime.now().isoformat()
                cls._save_state(initial_state)
                cls._state_cache = initial_state
                return initial_state

            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    cls._state_cache = json.load(f)
                    return cls._state_cache
            except (json.JSONDecodeError, IOError):
                # Corrupted file - start fresh
                cls._state_cache = cls._empty_state()
                cls._save_state(cls._state_cache)
                return cls._state_cache

    @classmethod
    def _save_state(cls, state: Dict[str, Any]) -> None:
        """Save state to disk."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state["last_updated"] = datetime.now().isoformat()

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        cls._state_cache = state

    @classmethod
    def add_activated_skill(cls, skill_name: str) -> None:
        """
        Record that a skill has been activated in this session.

        Args:
            skill_name: Name of the activated skill
        """
        state = cls._load_state()

        if skill_name not in state["activated_skills"]:
            state["activated_skills"].append(skill_name)
            cls._save_state(state)

    @classmethod
    def get_already_activated(cls) -> List[str]:
        """
        Get list of skills already activated in this session.

        Returns:
            List of skill names
        """
        state = cls._load_state()
        return state.get("activated_skills", [])

    @classmethod
    def is_skill_activated(cls, skill_name: str) -> bool:
        """
        Check if a specific skill has been activated.

        Args:
            skill_name: Name of the skill to check

        Returns:
            True if skill is in activated list
        """
        return skill_name in cls.get_already_activated()

    @classmethod
    def clear_activated_skills(cls) -> None:
        """Clear all activated skills (e.g., for new session)."""
        state = cls._load_state()
        state["activated_skills"] = []
        cls._save_state(state)

    # ===== PENDING LEARN METHODS (Milestone 1.3) =====

    @classmethod
    def set_pending_learn(cls, learn_data: Dict[str, Any]) -> None:
        """
        Record pending learning task for LEARN phase.

        Args:
            learn_data: Dictionary with keys:
                - label: str - Topic label (e.g., "FastAPI Framework")
                - domain: str - Domain ("tech" or "1c")
                - pattern: str - The matched regex pattern
                - detected_at: str (optional) - ISO timestamp

        Example:
            >>> SessionState.set_pending_learn({
            ...     "label": "FastAPI Framework",
            ...     "domain": "tech",
            ...     "pattern": "FastAPI|APIRouter"
            ... })
        """
        state = cls._load_state()

        # Add timestamp if not provided
        if "detected_at" not in learn_data:
            learn_data["detected_at"] = datetime.now().isoformat()

        state["pending_learn"] = learn_data
        cls._save_state(state)

    @classmethod
    def get_pending_learn(cls) -> Optional[Dict[str, Any]]:
        """
        Retrieve and clear pending learning task.

        Returns:
            Dictionary with pending learn data, or None if no pending task

        Example:
            >>> pending = SessionState.get_pending_learn()
            >>> if pending:
            ...     print(f"Create skill for: {pending['label']}")
        """
        state = cls._load_state()
        return state.get("pending_learn")

    @classmethod
    def has_pending_learn(cls) -> bool:
        """
        Check if there is a pending learning task.

        Returns:
            True if pending_learn exists and is not None
        """
        state = cls._load_state()
        return state.get("pending_learn") is not None

    @classmethod
    def clear_pending_learn(cls) -> None:
        """
        Clear pending learning task after creating tasks.

        Call this after creating LEARN tasks to prevent duplicate task creation.
        """
        state = cls._load_state()
        state["pending_learn"] = None
        cls._save_state(state)

    # ===== METADATA METHODS =====

    @classmethod
    def get_session_id(cls) -> str:
        """Get unique session identifier."""
        state = cls._load_state()
        return state.get("session_id", "unknown")

    @classmethod
    def get_session_age(cls) -> Optional[float]:
        """
        Get session age in hours.

        Returns:
            Age in hours, or None if created_at is missing
        """
        state = cls._load_state()
        created_str = state.get("created_at")
        if not created_str:
            return None

        try:
            created = datetime.fromisoformat(created_str)
            age = (datetime.now() - created).total_seconds() / 3600
            return round(age, 2)
        except (ValueError, TypeError):
            return None

    @classmethod
    def reset_session(cls) -> None:
        """Reset entire session state (fresh start)."""
        with cls._lock:
            initial_state = cls._empty_state()
            initial_state["session_id"] = os.urandom(8).hex()
            initial_state["created_at"] = datetime.now().isoformat()
            cls._save_state(initial_state)
            cls._state_cache = initial_state

    @classmethod
    def get_stats(cls) -> Dict[str, Any]:
        """
        Get session statistics.

        Returns:
            Dict with session_id, age, activated_skills_count, has_pending_learn
        """
        state = cls._load_state()
        return {
            "session_id": state.get("session_id"),
            "age_hours": cls.get_session_age(),
            "activated_skills_count": len(state.get("activated_skills", [])),
            "has_pending_learn": state.get("pending_learn") is not None,
            "last_updated": state.get("last_updated")
        }


# Export for use in hooks
__all__ = ["SessionState"]
