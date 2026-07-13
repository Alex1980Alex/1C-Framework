#!/usr/bin/env python3
"""
Hook: tool-health-analyzer-stop
Event: Stop
Matcher: (none)
Purpose: Раз в сутки (cooldown 24ч) спавнит detached `scripts/analyze_tool_health.py`
         → отчёт о здоровье инструментов + вердикты §6 в data/reports/tools/.
         Замыкает «лог → анализ» над hook-invocations.jsonl (roadmap 260713 P1.1).
         Паттерн — post-indexing-analyzer (Stop → detached analyzer), но по расписанию,
         а не по событию: анализ идёт над накопленным окном, не привязан к run_end.

Timeout: 5s. Exit: всегда 0 (informational, никогда не блокирует Stop).
Opt-out: TOOL_HEALTH_ANALYZER_DISABLE=1.
State: .claude/cache/tool-health-analyzer-state.json {"last_fire": "<iso>"}
"""

import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "tool-health-analyzer-state.json"
ANALYZER = PROJECT_ROOT / "scripts" / "analyze_tool_health.py"
PYTHON_EXE = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
REPORTS_DIR = PROJECT_ROOT / "data" / "reports" / "tools"
COOLDOWN_HOURS = 24


def _load_last_fire() -> datetime | None:
    import json

    if not STATE_FILE.exists():
        return None
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return datetime.fromisoformat(data.get("last_fire", ""))
    except (OSError, ValueError, TypeError):
        return None


def _save_last_fire(now: datetime) -> None:
    import json

    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps({"last_fire": now.isoformat()}), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def _spawn() -> bool:
    if not PYTHON_EXE.exists() or not ANALYZER.exists():
        return False
    creationflags = 0
    if sys.platform == "win32":
        creationflags = 0x00000008 | 0x08000000  # DETACHED_PROCESS | CREATE_NO_WINDOW
    try:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        log_fh = (REPORTS_DIR / "_analyzer.log").open("a", encoding="utf-8")
        try:
            subprocess.Popen(
                [str(PYTHON_EXE), str(ANALYZER), "--window-days", "14"],
                stdout=log_fh,
                stderr=log_fh,
                cwd=str(PROJECT_ROOT),
                creationflags=creationflags,
                close_fds=True,
            )
        finally:
            log_fh.close()
        return True
    except OSError:
        return False


class ToolHealthAnalyzerStop(BaseHook):
    HOOK_NAME = "ToolHealthAnalyzerStop"

    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("TOOL_HEALTH_ANALYZER_DISABLE") == "1":
            return None
        if inp.detected_event != "Stop":
            return None

        now = datetime.now()
        last = _load_last_fire()
        if last is not None and now - last < timedelta(hours=COOLDOWN_HOURS):
            return None  # cooldown — раз в сутки достаточно

        ok = _spawn()
        if not ok:
            # НЕ сохраняем last_fire: контур не должен умирать тихо на 24ч-циклы
            # (adversarial-review 260713 #5a). Проверка exists() дешёвая — ретрай
            # на каждом Stop приемлем, а предупреждение делает поломку видимой.
            missing = (
                PYTHON_EXE.name
                if not PYTHON_EXE.exists()
                else (ANALYZER.name if not ANALYZER.exists() else "ошибка запуска (OSError)")
            )
            return HookOutput().system_message(
                "[TOOL-HEALTH] ⚠ Не удалось запустить анализ здоровья инструментов "
                f"({missing}). Контур tool-health не обновляется."
            )
        _save_last_fire(now)
        return HookOutput().system_message(
            "[TOOL-HEALTH] Запущен анализ здоровья инструментов (окно 14д). "
            "Отчёт: `data/reports/tools/_latest.md`; вердикты/alerts всплывут в баннере "
            "следующей сессии."
        )


if __name__ == "__main__":
    ToolHealthAnalyzerStop().run()
