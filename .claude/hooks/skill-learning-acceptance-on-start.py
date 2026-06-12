#!/usr/bin/env python3
"""
Hook: skill-learning-acceptance-on-start
Event: SessionStart
Purpose: Автономное наблюдение acceptance-окна skill-learning revival
  (roadmap 260611 §P4, 2026-06-12 → 2026-06-26). Раз в день (sentinel) считает
  метрики через scripts/skill_learning_acceptance.py (локальные JSONL + логи,
  без сети) и эмитит прогресс-баннер. После закрытия окна эмитит ФИНАЛЬНЫЙ
  вердикт каждый старт сессии, пока вердикт не зафиксирован в §18 роадмапа
  (маркер "Acceptance вердикт") — после этого замолкает навсегда.
Opt-out: SKILL_LEARNING_ACCEPTANCE_DISABLE=1
Timeout: 5s
"""

import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SENTINEL = PROJECT_ROOT / ".claude" / "cache" / "skill-learning-acceptance-state.json"
ROADMAP = PROJECT_ROOT / "docs" / "roadmap" / "260611_ROADMAP_SKILL_LEARNING_REVIVAL.md"
WINDOW_END = datetime(2026, 6, 26)
FINAL_MARKER = "Acceptance вердикт"


def _ran_today() -> bool:
    try:
        data = json.loads(SENTINEL.read_text(encoding="utf-8"))
        return data.get("last_run_date") == date.today().isoformat()
    except Exception:
        return False


def _mark_ran() -> None:
    try:
        SENTINEL.parent.mkdir(parents=True, exist_ok=True)
        SENTINEL.write_text(
            json.dumps({"last_run_date": date.today().isoformat()}), encoding="utf-8"
        )
    except Exception:
        pass


def _verdict_logged() -> bool:
    """Маркер считается только в форме «Acceptance вердикт: PASS|FAIL» — голая
    подстрока встречается в §18 в тексте, описывающем сам механизм (code-verify
    finding: false self-termination до показа вердикта)."""
    try:
        return (
            re.search(
                rf"{FINAL_MARKER}:\s*(PASS|FAIL)", ROADMAP.read_text(encoding="utf-8")
            )
            is not None
        )
    except Exception:
        return False


class SkillLearningAcceptance(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("SKILL_LEARNING_ACCEPTANCE_DISABLE") == "1":
            return None
        window_closed = datetime.now() >= WINDOW_END
        if window_closed and _verdict_logged():
            return None  # вердикт уже в §18 — наблюдение завершено
        if not window_closed and _ran_today():
            return None  # прогресс — не чаще раза в день

        try:
            # append, не insert(0): не затенять hooks-local пакеты ([[feedback-hook-src-shared-collision]])
            scripts_dir = str(PROJECT_ROOT / "scripts")
            if scripts_dir not in sys.path:
                sys.path.append(scripts_dir)
            import skill_learning_acceptance as sla

            m = sla.collect_metrics()
            crit = sla.evaluate(m)
        except Exception:
            return None  # fail-soft: наблюдение не ломает старт сессии

        _mark_ran()
        status = ", ".join(f"{k}={'OK' if ok else 'NO'}" for k, ok in crit.items())
        if window_closed:
            verdict = "PASS" if all(crit.values()) else "FAIL"
            msg = (
                f"[SL-ACCEPTANCE] ОКНО ЗАКРЫТО — финальный вердикт: {verdict}. {status}. "
                f"Действие: запустить `python scripts/skill_learning_acceptance.py --final`, "
                f"зафиксировать строку «{FINAL_MARKER}: {verdict}» в §18 "
                f"docs/roadmap/260611_ROADMAP_SKILL_LEARNING_REVIVAL.md "
                f"(после этого баннер замолчит)"
            )
        else:
            msg = (
                f"[SL-ACCEPTANCE] день {m['day']}/14: captures={m['captures']}/10, "
                f"median_age={m['median_pending_age_days']}d, rejects={m['rejects']}, "
                f"arm_fired={m['surfacing_arm_fired']}, dup={m['dup_events']} | {status}"
            )
        return HookOutput().system_message(msg)


if __name__ == "__main__":
    SkillLearningAcceptance().run()
