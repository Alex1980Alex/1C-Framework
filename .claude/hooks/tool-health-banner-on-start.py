#!/usr/bin/env python3
"""
Hook: tool-health-banner-on-start
Event: SessionStart
Matcher: (none)
Purpose: Сюрфейсит вердикты здоровья инструментов (roadmap 260713 §6.2 decision layer).
         Читает data/reports/tools/_latest.json (пишет analyze_tool_health.py) и:
           - broken/degraded → баннер с alert'ами (иначе МОЛЧИТ — quiet wakeups rare);
           - broken → ЭСКАЛАЦИЯ: авто-заводит mandatory-задачу «диагностировать инструмент X»
             (cooldown 72ч на тул, чтобы не плодить дубли). Молчаливого авто-фикса нет —
             исправление идёт стандартным пайплайном, решение по degraded за человеком.

Timeout: 5s. Exit: всегда 0 (informational). Opt-out: TOOL_HEALTH_BANNER_DISABLE=1.
State: .claude/cache/tool-health-banner-state.json {"<tool>": "<iso последней эскалации>"}
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SIDECAR = PROJECT_ROOT / "data" / "reports" / "tools" / "_latest.json"
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "tool-health-banner-state.json"
# Cooldown эскалации = окно анализа (14д): broken держится в 14д-окне до 14 дней после
# фикса (старые ошибки не выпали) → 72ч плодило повторные задачи по ОДНОМУ инциденту
# (adversarial-review 260713 #6). Одна задача на инцидент-окно; баннер светит всё время.
ESCALATE_COOLDOWN_HOURS = 336  # 14 дней
STALE_REPORT_DAYS = 7


def _load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _save_state(state: dict) -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, STATE_FILE)
    except OSError:
        pass


def _escalate_broken(tool: str, reason: str, now: datetime, state: dict) -> bool:
    """Авто-задача диагностики broken-тула с cooldown на тул. Возвращает True если задача заведена."""
    last = state.get(tool)
    if last:
        try:
            if now - datetime.fromisoformat(last) < timedelta(hours=ESCALATE_COOLDOWN_HOURS):
                return False  # уже эскалировали недавно
        except (ValueError, TypeError):
            pass
    try:
        from shared.task_master import add_task

        add_task(
            title=f"Диагностировать инструмент {tool} (broken)",
            priority="high",
            created_by="tool-health-banner",
            description=(
                f"Вердикт tool-health: broken — {reason}. Evidence: data/reports/tools/_latest.md "
                f"+ verdicts.jsonl. Разобрать root-cause и починить (стандартный пайплайн), "
                f"затем re-verify на свежем окне (analyze_tool_health.py). НЕ авто-фикс."
            ),
        )
    except Exception:
        return False
    state[tool] = now.isoformat()
    return True


class ToolHealthBanner(BaseHook):
    HOOK_NAME = "ToolHealthBanner"

    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("TOOL_HEALTH_BANNER_DISABLE") == "1":
            return None
        sidecar = _load_json(SIDECAR, None)
        if not sidecar:
            return None  # отчёта ещё нет — молчим
        alerts = sidecar.get("alerts") or []
        now = datetime.now()
        if not alerts:
            # healthy → тихо, НО протухший отчёт = мёртвый контур, о нём молчать нельзя
            # (adversarial-review 260713 #5a: тихая смерть анализатора была невидима)
            gen = sidecar.get("generated")
            try:
                if gen and now - datetime.fromisoformat(gen) > timedelta(days=STALE_REPORT_DAYS):
                    return HookOutput().system_message(
                        f"[TOOL-HEALTH] ⚠ Отчёт здоровья инструментов устарел ({gen}) — "
                        "анализатор не отрабатывает. Проверить: "
                        "`python scripts/analyze_tool_health.py` + `_analyzer.log`."
                    )
            except (ValueError, TypeError):
                pass
            return None  # всё healthy и отчёт свежий — тихо (quiet wakeups rare)
        broken = [a for a in alerts if a.get("verdict") == "broken"]
        degraded = [a for a in alerts if a.get("verdict") == "degraded"]

        # эскалация broken (авто-задача, cooldown на тул)
        state = _load_json(STATE_FILE, {})
        escalated: list[str] = []
        for a in broken:
            if _escalate_broken(a["tool"], a.get("reason", ""), now, state):
                escalated.append(a["tool"])
        if escalated:
            _save_state(state)

        inc = " ⚠ окно неполное" if sidecar.get("window_incomplete") else ""
        lines = [
            "[TOOL-HEALTH] Обнаружены проблемные инструменты (окно "
            f"{sidecar.get('window_days', '?')}д{inc}):"
        ]
        for a in broken:
            lines.append(f"  🔴 broken `{a['tool']}` — {a.get('reason', '')}")
        for a in degraded:
            lines.append(f"  🟠 degraded `{a['tool']}` — {a.get('reason', '')}")
        if escalated:
            lines.append(
                f"  → заведена(ы) задача(и) диагностики: {', '.join(escalated)} "
                "(broken; решение по degraded — за тобой)."
            )
        # предупредить если отчёт устарел
        gen = sidecar.get("generated")
        try:
            if gen and now - datetime.fromisoformat(gen) > timedelta(days=STALE_REPORT_DAYS):
                lines.append(f"  ⚠ отчёт устарел ({gen}) — прогнать analyze_tool_health.py.")
        except (ValueError, TypeError):
            pass
        lines.append("  Детали: `data/reports/tools/_latest.md`.")
        return HookOutput().system_message("\n".join(lines))


if __name__ == "__main__":
    ToolHealthBanner().run()
