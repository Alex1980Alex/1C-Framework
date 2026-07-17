"""
Session State Management for Claude Code Hooks
Provides persistent state storage across hook invocations.

Concurrency contract (v2.1): hook-процессы стартуют ПАРАЛЛЕЛЬНО на одном событии,
поэтому мутации идут через _mutate(): межпроцессный lock-файл + свежее чтение с
диска (мимо процессного кэша) + atomic save с ретраем os.replace (Windows отдаёт
PermissionError, пока другой процесс держит файл открытым на чтение).

Author: Claude Code
Version: 2.1.0
Updated: 2026-07-17 (cross-process _mutate + os.replace retry — потеря активации
    Skill при параллельных хуках на PreToolUse:Skill; см. pipeline
    fix-session-state-skill-race)
"""

import json
import os
import tempfile
import threading
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

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
    _state_cache: dict[str, Any] | None = None

    # os.replace retry (Windows: PermissionError, пока читатель держит файл открытым)
    _REPLACE_RETRIES = 6
    _REPLACE_RETRY_SLEEP = 0.02
    # read retry (симметрично: sharing-violation окно во время чужого os.replace / AV)
    _READ_RETRIES = 3
    # Межпроцессный lock мутаций (бюджет ≪ hook-timeout 3с)
    _LOCK_WAIT_SEC = 0.6
    _LOCK_POLL_SEC = 0.02
    _LOCK_STALE_SEC = 5.0

    @classmethod
    def _empty_state(cls) -> dict[str, Any]:
        """Return initial empty state structure."""
        return {
            "activated_skills": [],
            "recommended_skills": [],
            "pending_learn": None,
            "session_id": None,
            "created_at": None,
            "last_updated": None,
        }

    @classmethod
    def _load_state(cls) -> dict[str, Any]:
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

            for attempt in range(cls._READ_RETRIES):
                try:
                    with open(STATE_FILE, encoding="utf-8") as f:
                        cls._state_cache = json.load(f)
                        return cls._state_cache
                except (json.JSONDecodeError, FileNotFoundError):
                    break  # битый JSON / исчез файл — ретрай не поможет
                except OSError:
                    # транзиентное окно чтения (чужой os.replace / AV держит файл)
                    if attempt < cls._READ_RETRIES - 1:
                        time.sleep(cls._REPLACE_RETRY_SLEEP)
            # Битый/нечитаемый файл: НЕ персистим пустоту — reader-side erase
            # стирал бы чужие activated_skills/task_protocol (review
            # fix-session-state-skill-race №1, тот же инцидент-класс со стороны
            # читателя). Деградация только в памяти; файл вылечит первая
            # мутация (_mutate → _read_disk_fresh → save).
            cls._state_cache = cls._empty_state()
            return cls._state_cache

    @classmethod
    def _save_state(cls, state: dict[str, Any]) -> None:
        """Save state to disk atomically (temp + os.replace — защита от corruption при гонке хуков)."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state["last_updated"] = datetime.now().isoformat()

        fd, tmp_path = tempfile.mkstemp(
            dir=str(STATE_DIR), prefix=".session-skills.", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            for attempt in range(cls._REPLACE_RETRIES):
                try:
                    os.replace(tmp_path, STATE_FILE)
                    break
                except PermissionError:
                    # Windows: replace падает, пока ДРУГОЙ hook-процесс держит
                    # STATE_FILE открытым на чтение (CPython open() — без
                    # FILE_SHARE_DELETE). Окно микросекундное — ретраим, иначе
                    # запись тихо теряется у glotающих исключения вызывателей
                    # (инцидент: активация Skill не попала в state).
                    if attempt == cls._REPLACE_RETRIES - 1:
                        raise
                    time.sleep(cls._REPLACE_RETRY_SLEEP)
        except Exception:
            try:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except OSError:
                pass
            raise

        cls._state_cache = state

    # ===== CROSS-PROCESS MUTATION CORE (v2.1) =====

    @classmethod
    @contextmanager
    def _ipc_lock(cls):
        """Межпроцессный лок мутаций: атомарное создание lock-файла (O_CREAT|O_EXCL).

        threading.Lock не защищает от параллельных hook-ПРОЦЕССОВ (одно событие
        Claude Code запускает несколько хуков одновременно). Ожидание ограничено;
        не взяли лок — работаем без него (fail-open: потеря взаимного исключения
        лучше дедлока хука с timeout 3с). Stale-лок (упавший процесс) взламывается
        по возрасту: хуки живут секунды, порог _LOCK_STALE_SEC.
        """
        lock_path = str(STATE_FILE) + ".lock"
        fd = None
        deadline = time.time() + cls._LOCK_WAIT_SEC
        while True:
            try:
                fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                break
            except FileExistsError:
                try:
                    # Break-in stale-лока намеренно best-effort: TOCTOU двух
                    # взломщиков (getmtime по старому, unlink уже свежего) даёт
                    # деградацию к fail-open — принято. На Windows unlink файла,
                    # который живой держатель держит открытым, отдаёт
                    # PermissionError → живой держатель невзламываем.
                    if time.time() - os.path.getmtime(lock_path) > cls._LOCK_STALE_SEC:
                        os.unlink(lock_path)
                        continue
                except OSError:
                    pass
                if time.time() >= deadline:
                    break  # fail-open
                time.sleep(cls._LOCK_POLL_SEC)
            except OSError:
                break  # каталог недоступен и т.п. — fail-open
        try:
            yield fd is not None
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    pass
                try:
                    os.unlink(lock_path)
                except OSError:
                    pass

    @classmethod
    def _read_disk_fresh(cls) -> dict[str, Any]:
        """Состояние строго с диска, МИМО процессного кэша (только из-под _mutate).

        Кэш к моменту мутации может быть устаревшим: другой hook-процесс успел
        записать своё изменение после нашего _load_state — save по кэшу затёр бы
        его (lost update). Транзиентный OSError ретраится: initial-возврат здесь
        персистится мутатором и стёр бы прежний state.
        """
        for attempt in range(cls._READ_RETRIES):
            try:
                with open(STATE_FILE, encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                break  # реально нет файла / битый JSON — легитимный fresh-start
            except OSError:
                if attempt < cls._READ_RETRIES - 1:
                    time.sleep(cls._REPLACE_RETRY_SLEEP)
        initial = cls._empty_state()
        initial["session_id"] = os.urandom(8).hex()
        initial["created_at"] = datetime.now().isoformat()
        return initial

    @classmethod
    def _mutate(cls, mutator) -> None:
        """Единая точка read-modify-write: lock → свежее чтение → mutator → save.

        mutator(state) правит dict на месте; возврат False = «изменений нет,
        не сохранять» (кэш всё равно обновляется свежим снапшотом).
        """
        with cls._lock, cls._ipc_lock():
            state = cls._read_disk_fresh()
            changed = mutator(state)
            if changed is not False:
                cls._save_state(state)
            else:
                cls._state_cache = state

    @classmethod
    def add_activated_skill(cls, skill_name: str) -> None:
        """
        Record that a skill has been activated in this session.

        Args:
            skill_name: Name of the activated skill
        """

        def _do(state):
            skills = state.setdefault("activated_skills", [])
            if skill_name in skills:
                return False
            skills.append(skill_name)

        cls._mutate(_do)

    @classmethod
    def get_already_activated(cls) -> list[str]:
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

        def _do(state):
            state["activated_skills"] = []

        cls._mutate(_do)

    # ===== RECOMMENDATION TRACKING (Session Dedup) =====

    @classmethod
    def record_recommendation(cls, skills: list[str]) -> None:
        """
        Record that skills were recommended in this session (for dedup).

        Args:
            skills: List of skill names that were recommended
        """

        def _do(state):
            existing = state.setdefault("recommended_skills", [])
            changed = False
            for skill in skills:
                if skill not in existing:
                    existing.append(skill)
                    changed = True
            return changed

        cls._mutate(_do)

    @classmethod
    def get_already_recommended(cls) -> list[str]:
        """
        Get list of skills already recommended in this session.

        Returns:
            List of skill names
        """
        state = cls._load_state()
        return state.get("recommended_skills", [])

    # ===== PENDING LEARN METHODS (Milestone 1.3) =====

    @classmethod
    def set_pending_learn(cls, learn_data: dict[str, Any]) -> None:
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
        # Add timestamp if not provided
        if "detected_at" not in learn_data:
            learn_data["detected_at"] = datetime.now().isoformat()

        def _do(state):
            state["pending_learn"] = learn_data

        cls._mutate(_do)

    @classmethod
    def get_pending_learn(cls) -> dict[str, Any] | None:
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

        def _do(state):
            if state.get("pending_learn") is None:
                return False
            state["pending_learn"] = None

        cls._mutate(_do)

    # ===== TASK PROTOCOL STATE (Mandatory Execution Algorithm) =====

    @classmethod
    def _default_task_protocol(cls) -> dict[str, Any]:
        """Default task protocol state."""
        return {
            "phase": "idle",  # idle | classified | decomposed | skill_checked
            "complexity": None,  # trivial | medium | complex
            "subtask_count": 0,
            "decomposed_at": None,
            "skill_checked_at": None,
        }

    @classmethod
    def record_decomposition(cls) -> None:
        """Called from task-protocol-observer on TaskCreate.

        Sets phase to 'decomposed' and increments subtask_count.
        """

        def _do(state):
            protocol = state.get("task_protocol", cls._default_task_protocol())
            protocol["phase"] = "decomposed"
            protocol["subtask_count"] = protocol.get("subtask_count", 0) + 1
            protocol["decomposed_at"] = datetime.now().isoformat()
            state["task_protocol"] = protocol

        cls._mutate(_do)

    @classmethod
    def set_task_classified(cls, complexity: str) -> None:
        """Called from UserPromptSubmit hook for auto-classification.

        Args:
            complexity: 'trivial', 'medium', or 'complex'
        """

        def _do(state):
            protocol = state.get("task_protocol", cls._default_task_protocol())
            # Don't downgrade from 'decomposed'
            if protocol.get("phase") != "decomposed":
                protocol["phase"] = "classified"
            protocol["complexity"] = complexity
            state["task_protocol"] = protocol

        cls._mutate(_do)

    @classmethod
    def get_task_protocol(cls) -> dict[str, Any]:
        """Get current task protocol state.

        Returns:
            Dict with phase, complexity, subtask_count, decomposed_at.
            Always returns valid dict even if not initialized.
        """
        state = cls._load_state()
        return state.get("task_protocol", cls._default_task_protocol())

    @classmethod
    def reset_task_protocol(cls) -> None:
        """Reset task protocol on new prompt (UserPromptSubmit)."""

        def _do(state):
            state["task_protocol"] = cls._default_task_protocol()

        cls._mutate(_do)

    @classmethod
    def record_skill_checked(cls) -> None:
        """Called from task-protocol-observer on Skill() call.

        Sets phase to 'skill_checked'. This is the only phase that
        allows Write/Edit through the enforcer gate.
        """

        def _do(state):
            protocol = state.get("task_protocol", cls._default_task_protocol())
            protocol["phase"] = "skill_checked"
            protocol["skill_checked_at"] = datetime.now().isoformat()
            state["task_protocol"] = protocol

        cls._mutate(_do)

    # ===== Z.AI DELEGATION TRACKING =====

    @classmethod
    def record_llm_delegation(cls) -> None:
        """Record that mcp__llm-rotation__llm_complete was called in this session."""

        def _do(state):
            state["llm_delegation_count"] = state.get("llm_delegation_count", 0) + 1
            state["llm_delegation_last"] = datetime.now().isoformat()

        cls._mutate(_do)

    @classmethod
    def has_llm_delegation(cls) -> bool:
        """Check if Z.AI delegation was used in this session."""
        state = cls._load_state()
        return state.get("llm_delegation_count", 0) > 0

    # ===== ROUTER FIRED MARKER (Phase 11: enforcer coordination) =====

    @classmethod
    def set_router_fired(cls) -> None:
        """Mark that skill-router output recommendations this prompt."""

        def _do(state):
            state["router_fired_at"] = datetime.now().isoformat()

        cls._mutate(_do)

    @classmethod
    def was_router_fired_recently(cls, seconds: int = 10) -> bool:
        """Check if skill-router fired within last N seconds (for enforcer dedup)."""
        state = cls._load_state()
        fired_at = state.get("router_fired_at")
        if not fired_at:
            return False
        try:
            fired = datetime.fromisoformat(fired_at)
            return (datetime.now() - fired).total_seconds() < seconds
        except (ValueError, TypeError):
            return False

    # ===== PROMPT ID METHODS (Accuracy Tracking) =====

    @classmethod
    def set_prompt_id(cls, prompt_id: str) -> None:
        """
        Store current prompt_id for accuracy correlation.

        Called from skill-router.py after generating a recommendation.
        The prompt_id links a recommend event to a subsequent activate event.

        Args:
            prompt_id: Short hash identifying the prompt (e.g. "abc12345")
        """

        def _do(state):
            state["current_prompt_id"] = prompt_id

        cls._mutate(_do)

    @classmethod
    def get_prompt_id(cls) -> str | None:
        """
        Get current prompt_id for accuracy correlation.

        Called from skill-usage-metrics.py (PostToolUse:Skill) and
        skill-router.py (_detect_skill_activations) to correlate
        activations with prior recommendations.

        Returns:
            prompt_id string, or None if not set
        """
        state = cls._load_state()
        return state.get("current_prompt_id")

    @classmethod
    def clear_prompt_id(cls) -> None:
        """Clear prompt_id after activation is recorded."""

        def _do(state):
            if "current_prompt_id" not in state:
                return False
            state.pop("current_prompt_id", None)

        cls._mutate(_do)

    # ===== METADATA METHODS =====

    @classmethod
    def get_session_id(cls) -> str:
        """Get unique session identifier."""
        state = cls._load_state()
        return state.get("session_id", "unknown")

    @classmethod
    def get_session_age(cls) -> float | None:
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
        with cls._lock, cls._ipc_lock():
            initial_state = cls._empty_state()
            initial_state["session_id"] = os.urandom(8).hex()
            initial_state["created_at"] = datetime.now().isoformat()
            cls._save_state(initial_state)
            cls._state_cache = initial_state

    @classmethod
    def get_stats(cls) -> dict[str, Any]:
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
            "last_updated": state.get("last_updated"),
        }


# ===== MODULE-LEVEL CONVENIENCE FUNCTIONS =====
# These match the import patterns: from shared.session_state import set_prompt_id


def set_prompt_id(prompt_id: str) -> None:
    """Module-level wrapper for SessionState.set_prompt_id()."""
    SessionState.set_prompt_id(prompt_id)


def get_prompt_id() -> str | None:
    """Module-level wrapper for SessionState.get_prompt_id()."""
    return SessionState.get_prompt_id()


def record_recommendation(skills: list[str]) -> None:
    """Module-level wrapper for SessionState.record_recommendation()."""
    SessionState.record_recommendation(skills)


def get_already_recommended() -> list[str]:
    """Module-level wrapper for SessionState.get_already_recommended()."""
    return SessionState.get_already_recommended()


def record_decomposition() -> None:
    """Module-level wrapper for SessionState.record_decomposition()."""
    SessionState.record_decomposition()


def get_task_protocol() -> dict[str, Any]:
    """Module-level wrapper for SessionState.get_task_protocol()."""
    return SessionState.get_task_protocol()


def reset_task_protocol() -> None:
    """Module-level wrapper for SessionState.reset_task_protocol()."""
    SessionState.reset_task_protocol()


def set_task_classified(complexity: str) -> None:
    """Module-level wrapper for SessionState.set_task_classified()."""
    SessionState.set_task_classified(complexity)


def record_skill_checked() -> None:
    """Module-level wrapper for SessionState.record_skill_checked()."""
    SessionState.record_skill_checked()


def reset_session() -> None:
    """Module-level wrapper for SessionState.reset_session()."""
    SessionState.reset_session()


# Export for use in hooks
__all__ = [
    "SessionState",
    "set_prompt_id",
    "get_prompt_id",
    "record_recommendation",
    "get_already_recommended",
    "record_decomposition",
    "get_task_protocol",
    "reset_task_protocol",
    "set_task_classified",
    "record_skill_checked",
    "reset_session",
]
