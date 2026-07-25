#!/usr/bin/env python3
"""
Hook: memory-maintenance-cadence
Event: Stop
Matcher: (none)
Purpose: §26 P4 D4.1 — run the memory maintenance cadence
         (``scripts/memory_maintenance.py``) once every N distinct sessions, as a
         detached subprocess. Sequences reflect → cross_store_sync → promote →
         ForgetGate and writes the D4.3 dashboard.

Safety: **DRY-RUN by default** (the cadence only plans/reports). Set
        ``MEMORY_MAINTENANCE_APPLY=1`` to let it write (reflect/sync apply,
        promote drafts, ForgetGate archival). Never blocks Stop (exit 0).

State: .claude/cache/memory-maintenance-cadence-state.json
  {"pending_sessions": [...], "first_seen": "<iso>", "last_fire": "<iso>|null"}

Cold start: seed on first invocation (no state), do NOT fire — avoids a cadence
run on the very first Stop after install.

J-P1 (roadmap 260725): on the same fire the hook also spawns the **LLM-judge**
(``scripts/tool_llm_judge.py``) — advisory semantic layer over the rule metrics.
It rides its own 24h cooldown (state key ``last_judge``), NOT the session counter:
the cadence fire is merely an occasion to check, not a command to run.

Env:
  MEMORY_MAINTENANCE_DISABLE=1        opt-out entirely
  MEMORY_MAINTENANCE_EVERY=N          cadence period in distinct sessions (default 10)
  MEMORY_MAINTENANCE_APPLY=1          run with --apply (default dry-run)
  TOOL_LLM_JUDGE_CADENCE_DISABLE=1    opt-out of the LLM-judge spawn only
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "memory-maintenance-cadence-state.json"
SCRIPT = PROJECT_ROOT / "scripts" / "memory_maintenance.py"
# P1.4 (B8, roadmap 260713): observability-отчёт с freshness/regression-детектором —
# «замолчавший sink» (писал и перестал). Раньше запускался ТОЛЬКО вручную. Read-only и
# быстрый (<1с), поэтому дёргаем синхронно при фаере каденса и сюрфейсим regressions в баннер.
OBS_SCRIPT = PROJECT_ROOT / "scripts" / "memory_observability_report.py"
# J-P1 (roadmap 260725): семантический слой оценки инструментов. Rule-слой уже в
# каденсе (regression-маркер выше), LLM-judge запускался ТОЛЬКО вручную и потому не жил.
# Спавн детачем — судья ходит в LLM (десятки секунд), inline-бюджет хука не трогаем.
JUDGE_SCRIPT = PROJECT_ROOT / "scripts" / "tool_llm_judge.py"
JUDGE_LOG = PROJECT_ROOT / "data" / "reports" / "tools" / "_judge.log"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
LOG = PROJECT_ROOT / "data" / "reports" / "memory" / "_maintenance.log"

DEFAULT_EVERY = 10
MAX_PENDING = 200
# Свой cooldown, НЕ общий с memory-джобами (ревью-п.5): каденс памяти фаерит по
# счётчику сессий, судья — не чаще раза в сутки, иначе жжём токены на тех же вызовах.
JUDGE_COOLDOWN_HOURS = 24
JUDGE_CAP = 50


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_state() -> dict[str, Any]:
    if not STATE_FILE.exists():
        return {}
    try:
        data: dict[str, Any] = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: dict[str, Any]) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(STATE_FILE.suffix + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def _every() -> int:
    try:
        n = int(os.environ.get("MEMORY_MAINTENANCE_EVERY", DEFAULT_EVERY))
        return n if n > 0 else DEFAULT_EVERY
    except ValueError:
        return DEFAULT_EVERY


def _dry_run_mode() -> str:
    """Banner label for a run without the global --apply.

    Plain "dry-run" was a lie the moment per-job overrides existed: with
    MEMORY_MAINTENANCE_APPLY_REFLECT=1 the cadence upserts learned_patterns and writes
    link_registry.db while the operator reads "dry-run" — the same report-one-thing-do-
    another defect the per-job flag was added to fix. Names what the operator SET; which
    of those actually take effect is decided by memory_maintenance._job_apply
    (SUBPROCESS_JOBS only — see its docstring).
    """
    prefix = "MEMORY_MAINTENANCE_APPLY_"
    writers = sorted(
        name[len(prefix) :].lower()
        for name, value in os.environ.items()
        if name.startswith(prefix) and value == "1"
    )
    return f"dry-run; per-job APPLY set: {', '.join(writers)}" if writers else "dry-run"


def _launch(apply: bool) -> bool:
    """Detached fire-and-forget cadence run. Returns True on launch success."""
    if not PYTHON_EXE.exists() or not SCRIPT.exists():
        return False
    cmd = [str(PYTHON_EXE), str(SCRIPT)]
    if apply:
        cmd.append("--apply")
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        fh = LOG.open("a", encoding="utf-8")
        try:
            subprocess.Popen(
                cmd,
                stdout=fh,
                stderr=fh,
                cwd=str(PROJECT_ROOT),
                creationflags=creationflags,
                close_fds=True,
            )
        finally:
            fh.close()
        return True
    except OSError:
        return False


def _judge_due(state: dict[str, Any], now: datetime | None = None) -> bool:
    """Пора ли судье: свой ключ `last_judge`, cooldown 24ч (независим от каденса)."""
    if os.environ.get("TOOL_LLM_JUDGE_CADENCE_DISABLE") == "1":
        return False
    last = state.get("last_judge")
    if not last:
        return True
    try:
        delta = (now or datetime.now()) - datetime.fromisoformat(str(last))
    except (TypeError, ValueError):
        return True  # битая отметка не должна выключать судью навсегда
    return delta.total_seconds() >= JUDGE_COOLDOWN_HOURS * 3600


def _provider_down() -> bool:
    """Провайдер LLM недоступен → судью не спавним (fail-soft, не молча)."""
    try:
        from shared.llm_health import is_provider_down

        return bool(is_provider_down())
    except Exception:
        return False  # нет хелпера/ошибка — пусть решает сам судья


def _launch_judge() -> bool:
    """Detached-прогон LLM-судьи по собственным per-call логам (J-P1)."""
    if not PYTHON_EXE.exists() or not JUDGE_SCRIPT.exists():
        return False
    cmd = [
        str(PYTHON_EXE),
        str(JUDGE_SCRIPT),
        "--source",
        "auto",
        "--cap",
        str(JUDGE_CAP),
    ]
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    try:
        JUDGE_LOG.parent.mkdir(parents=True, exist_ok=True)
        fh = JUDGE_LOG.open("a", encoding="utf-8")
        try:
            subprocess.Popen(
                cmd,
                stdout=fh,
                stderr=fh,
                cwd=str(PROJECT_ROOT),
                creationflags=creationflags,
                close_fds=True,
            )
        finally:
            fh.close()
        return True
    except OSError:
        return False


def _check_regressions(timeout: float = 8.0) -> str | None:
    """P1.4 (B8): синхронно прогнать observability-отчёт и вернуть строку
    `[REGRESSION] N stale sink(s): [...]` при замолчавших синках, иначе None.

    `--print --since 14d` (adversarial-review 260713 #2/#5): --print делает вызов
    честно read-only (без записи observability-*.md на каждый фаер), --since 14d
    ограничивает чтение синков окном (без него read_window парсил ВСЮ историю
    каждого jsonl — на разросшемся memory-metrics.jsonl упирался в timeout →
    регрессия молча терялась). Маркер в --print печатается с той же даты (контракт).
    best-effort — таймаут/ошибка/нет скрипта → None (каденс не ломается)."""
    if not PYTHON_EXE.exists() or not OBS_SCRIPT.exists():
        return None
    try:
        r = subprocess.run(
            [str(PYTHON_EXE), str(OBS_SCRIPT), "--print", "--since", "14d"],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            encoding="utf-8",
            errors="replace",
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    for line in (r.stdout or "").splitlines():
        if line.startswith("[REGRESSION]"):
            return line.strip()
    return None


class MemoryMaintenanceCadence(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if inp.detected_event != "Stop":
            return None
        if os.environ.get("MEMORY_MAINTENANCE_DISABLE") == "1":
            return None

        sid = inp.session_id or ""
        state = _load_state()

        # Cold-start: seed without firing (no cadence run on first Stop).
        if not state:
            _save_state(
                {
                    "pending_sessions": [sid] if sid else [],
                    "first_seen": _now(),
                    "last_fire": None,
                }
            )
            return None

        pending: list[str] = list(state.get("pending_sessions") or [])
        if sid and sid not in pending:
            pending.append(sid)

        every = _every()
        if len(pending) >= every:
            apply = os.environ.get("MEMORY_MAINTENANCE_APPLY") == "1"
            ok = _launch(apply)
            state["pending_sessions"] = []
            state["last_fire"] = _now()
            _save_state(state)
            # P1.4 (B8): freshness/regression-детектор синхронно (read-only, <1с) —
            # замолчавшие memory-sinks сюрфейсим сразу в баннере каденса.
            regr = _check_regressions()
            # J-P1: судья на своём cooldown — фаер каденса лишь ПОВОД проверить, не команда.
            judge_note = ""
            if _judge_due(state):
                if _provider_down():
                    judge_note = (
                        "\n• LLM-judge пропущен: провайдер недоступен "
                        "(fail-soft; повтор на следующем фаере)."
                    )
                elif _launch_judge():
                    state["last_judge"] = _now()
                    _save_state(state)
                    judge_note = (
                        "\n• LLM-judge (advisory) запущен → data/reports/tools/llm-judge.jsonl; "
                        "расхождения с rule-слоем появятся в _latest.md."
                    )
                else:
                    judge_note = (
                        "\n⚠ LLM-judge не запустился (spawn failed) — вердикты не обновятся."
                    )
            if ok:
                mode = "APPLY" if apply else _dry_run_mode()
                msg = (
                    f"[MEMORY-MAINTENANCE] Cadence fired ({mode}; every {every} sessions). "
                    f"Dashboard → data/reports/memory/memory_maintenance_*.md в ~10-60с."
                    f"{judge_note}"
                )
                if regr:
                    msg += (
                        f"\n⚠ {regr}\n  → sink(s) перестали писать (>7д, observability-регрессия). "
                        f"Проверь writer'ы; отчёт: data/reports/memory/observability-*.md."
                    )
                return HookOutput().system_message(msg)
            # launch не удался, но регрессию всё равно стоит показать
            if regr:
                return HookOutput().system_message(
                    f"[MEMORY-MAINTENANCE] ⚠ {regr} — sink(s) перестали писать (>7д). "
                    f"Отчёт: data/reports/memory/observability-*.md."
                )
            return None

        state["pending_sessions"] = pending[-MAX_PENDING:]
        _save_state(state)
        return None


if __name__ == "__main__":
    MemoryMaintenanceCadence().run()
