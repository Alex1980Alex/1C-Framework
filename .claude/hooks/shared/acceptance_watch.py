"""Reusable SessionStart acceptance-window watcher (roadmap 260612 §P4).

Каркас вынесен из ``skill-learning-acceptance-on-start.py`` (260611 §P4), чтобы
memory-ai-наблюдение переиспользовало его, а не копипастило: дневной sentinel,
самотерминация по маркеру «Acceptance вердикт: PASS|FAIL» в §18 роадмапа,
fail-soft импорт метрик из ``scripts/``.

Контракт metric-модуля: ``collect_metrics() -> dict`` + ``evaluate(m) -> dict[str, bool]``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Callable
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[3]
FINAL_MARKER = "Acceptance вердикт"


def _ran_today(sentinel: Path) -> bool:
    try:
        data = json.loads(sentinel.read_text(encoding="utf-8"))
        return data.get("last_run_date") == date.today().isoformat()
    except Exception:
        return False


def _mark_ran(sentinel: Path) -> None:
    try:
        sentinel.parent.mkdir(parents=True, exist_ok=True)
        sentinel.write_text(
            json.dumps({"last_run_date": date.today().isoformat()}), encoding="utf-8"
        )
    except Exception:
        pass


def _verdict_logged(roadmap: Path) -> bool:
    """Маркер только в форме «Acceptance вердикт: PASS|FAIL» — голая подстрока
    встречается в тексте, описывающем сам механизм; ``(?!/)`` отсекает
    инструкционную форму «PASS/FAIL» (см. fix f08bf8096)."""
    try:
        return (
            re.search(
                rf"{FINAL_MARKER}:\s*(PASS|FAIL)\b(?!/)", roadmap.read_text(encoding="utf-8")
            )
            is not None
        )
    except Exception:
        return False


def acceptance_banner(
    *,
    disable_env: str,
    sentinel_name: str,
    roadmap_rel: str,
    window_end: datetime,
    metrics_module: str,
    script_rel: str,
    banner_tag: str,
    progress_line: Callable[[dict[str, Any], dict[str, bool]], str],
) -> str | None:
    """Вернуть текст баннера для systemMessage или None (молчание)."""
    if os.environ.get(disable_env) == "1":
        return None
    roadmap = PROJECT_ROOT / roadmap_rel
    sentinel = PROJECT_ROOT / ".claude" / "cache" / sentinel_name
    window_closed = datetime.now() >= window_end
    if window_closed and _verdict_logged(roadmap):
        return None  # вердикт уже в §18 — наблюдение завершено
    if not window_closed and _ran_today(sentinel):
        return None  # прогресс — не чаще раза в день

    try:
        # append, не insert(0): не затенять hooks-local пакеты
        # ([[feedback-hook-src-shared-collision]])
        scripts_dir = str(PROJECT_ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.append(scripts_dir)
        import importlib

        mod = importlib.import_module(metrics_module)
        m = mod.collect_metrics()
        crit = mod.evaluate(m)
    except Exception:
        return None  # fail-soft: наблюдение не ломает старт сессии

    _mark_ran(sentinel)
    status = ", ".join(f"{k}={'OK' if ok else 'NO'}" for k, ok in crit.items())
    if window_closed:
        verdict = "PASS" if all(crit.values()) else "FAIL"
        return (
            f"[{banner_tag}] ОКНО ЗАКРЫТО — финальный вердикт: {verdict}. {status}. "
            f"Действие: запустить `python {script_rel} --final`, "
            f"зафиксировать строку «{FINAL_MARKER}: {verdict}» в §18 {roadmap_rel} "
            f"(после этого баннер замолчит)"
        )
    return f"[{banner_tag}] день {m['day']}/14: {progress_line(m, crit)} | {status}"


__all__ = ["FINAL_MARKER", "acceptance_banner"]
