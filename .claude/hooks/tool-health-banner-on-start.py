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
VERDICTS = PROJECT_ROOT / "data" / "reports" / "tools" / "verdicts.jsonl"
STATE_FILE = PROJECT_ROOT / ".claude" / "cache" / "tool-health-banner-state.json"
# Cooldown эскалации = окно анализа (14д): broken держится в 14д-окне до 14 дней после
# фикса (старые ошибки не выпали) → 72ч плодило повторные задачи по ОДНОМУ инциденту
# (adversarial-review 260713 #6). Одна задача на инцидент-окно; баннер светит всё время.
ESCALATE_COOLDOWN_HOURS = 336  # 14 дней
STALE_REPORT_DAYS = 7
REPEAT_BROKEN_DAYS = 30  # §6.3: broken того же тула в ≥2 прогонах за 30д → приоритет p1

# N-P1.2: единственный читатель истории verdicts.jsonl (scripts/). Defensive import —
# при недоступности деградируем к «без повтор-детекта» (баннер всё равно работает).
_SCRIPTS = str(PROJECT_ROOT / "scripts")
if _SCRIPTS not in sys.path:
    sys.path.append(_SCRIPTS)  # append (не insert) — не шэдоуить hooks-local shared.*
try:
    from tool_verdict_history import broken_repeat_within, read_verdicts
except Exception:  # pragma: no cover
    read_verdicts = None
    broken_repeat_within = None


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


def _escalate_broken(
    tool: str, reason: str, now: datetime, state: dict, repeat: bool = False
) -> bool:
    """Авто-задача диагностики broken-тула с cooldown на тул. Возвращает True если задача заведена.

    §6.3 (N-P1.2): `repeat=True` (тот же тул broken в ≥2 прогонах за 30д) → приоритет p1
    вместо high + пометка «повтор» (persistent-инцидент важнее нового)."""
    last = state.get(tool)
    if isinstance(last, dict):
        last = last.get("ts")
    if last:
        try:
            if now - datetime.fromisoformat(last) < timedelta(hours=ESCALATE_COOLDOWN_HOURS):
                return False  # уже эскалировали недавно
        except (ValueError, TypeError):
            pass
    tag = " ПОВТОР за 30д" if repeat else ""
    try:
        from shared.task_master import add_task

        add_task(
            title=f"Диагностировать инструмент {tool} (broken{tag})",
            priority="p1" if repeat else "high",
            created_by="tool-health-banner",
            description=(
                f"Вердикт tool-health: broken — {reason}."
                + (" Повторный broken за 30д (persistent) → приоритет p1." if repeat else "")
                + " Evidence: data/reports/tools/_latest.md + verdicts.jsonl. Разобрать "
                "root-cause и починить (стандартный пайплайн), затем re-verify на свежем "
                "окне ПОСЛЕ фикса (analyze_tool_health.py — вердикт снимется, когда чистое "
                "окно вытеснит старые ошибки). НЕ авто-фикс."
            ),
        )
    except Exception:
        return False
    # состояние per-тул: {ts, escalated:true} — для healed-детекта (N-P1.2)
    state[tool] = {"ts": now.isoformat(), "escalated": True}
    return True


class ToolHealthBanner(BaseHook):
    HOOK_NAME = "ToolHealthBanner"

    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("TOOL_HEALTH_BANNER_DISABLE") == "1":
            return None
        sidecar = _load_json(SIDECAR, None)
        if not sidecar:
            return None  # отчёта ещё нет — молчим
        now = datetime.now()
        alerts = sidecar.get("alerts") or []
        infra = sidecar.get("infra_alerts") or []  # N-P1.1: MCP-down + stale-sink
        broken = [a for a in alerts if a.get("verdict") == "broken"]
        degraded = [a for a in alerts if a.get("verdict") == "degraded"]
        infra_broken = [a for a in infra if a.get("level") == "broken"]
        infra_degraded = [a for a in infra if a.get("level") == "degraded"]

        state = _load_json(STATE_FILE, {})
        rows = read_verdicts(VERDICTS) if read_verdicts else []  # N-P1.2: история вердиктов

        # ── эскалация broken (тулы + инфра). Повтор за 30д → p1 (§6.3) ──
        escalated: list[str] = []
        current_broken: set[str] = set()
        for a in broken:
            tool = a["tool"]
            current_broken.add(tool)
            repeat = bool(
                broken_repeat_within and broken_repeat_within(tool, now, REPEAT_BROKEN_DAYS, rows)
            )
            if _escalate_broken(tool, a.get("reason", ""), now, state, repeat=repeat):
                escalated.append(f"{tool}{' (p1/повтор)' if repeat else ''}")
        for a in infra_broken:
            key = f"{a.get('source', 'infra')}:{a.get('key', '')}"
            current_broken.add(key)
            if _escalate_broken(key, a.get("reason", ""), now, state):
                escalated.append(key)

        # ── healed (N-P1.2 §6.3): ранее эскалированный тул ПОЛНОСТЬЮ восстановился →
        # петля закрыта. Считаем «активным» и broken, И degraded (code-verify #1): переход
        # broken→degraded — НЕ вылечен; снятие cooldown-записи на degraded позволило бы
        # обойти 336ч-cooldown при обратном флапе degraded→broken. ──
        current_active = set(current_broken)
        for a in degraded:
            current_active.add(a["tool"])
        for a in infra_degraded:
            current_active.add(f"{a.get('source', 'infra')}:{a.get('key', '')}")
        healed: list[str] = []
        for k in list(state.keys()):
            v = state.get(k)
            if isinstance(v, dict) and v.get("escalated") and k not in current_active:
                healed.append(k)
                del state[k]

        if escalated or healed:
            _save_state(state)

        gen = sidecar.get("generated")
        stale = False
        try:
            stale = bool(
                gen and now - datetime.fromisoformat(gen) > timedelta(days=STALE_REPORT_DAYS)
            )
        except (ValueError, TypeError):
            pass

        # ── тихо только когда РОВНО ничего: нет alert'ов/инфры/healed, отчёт свежий ──
        if not (broken or degraded or infra_broken or infra_degraded or healed):
            if stale:
                return HookOutput().system_message(
                    f"[TOOL-HEALTH] ⚠ Отчёт здоровья инструментов устарел ({gen}) — "
                    "анализатор не отрабатывает. Проверить: "
                    "`python scripts/analyze_tool_health.py` + `_analyzer.log`."
                )
            return None  # всё healthy и свежо — тихо (quiet wakeups rare)

        inc = " ⚠ окно неполное" if sidecar.get("window_incomplete") else ""
        lines = [
            "[TOOL-HEALTH] Обнаружены проблемные инструменты (окно "
            f"{sidecar.get('window_days', '?')}д{inc}):"
        ]
        for a in infra_broken:
            lines.append(f"  🔴 infra `{a.get('source', '')}` — {a.get('reason', '')}")
        for a in broken:
            lines.append(f"  🔴 broken `{a['tool']}` — {a.get('reason', '')}")
        for a in degraded:
            lines.append(f"  🟠 degraded `{a['tool']}` — {a.get('reason', '')}")
        for a in infra_degraded:
            lines.append(f"  🟠 infra `{a.get('source', '')}` — {a.get('reason', '')}")
        if healed:
            lines.append(f"  ✅ вылечено (петля закрыта): {', '.join(healed)}")
        if escalated:
            lines.append(
                f"  → заведена(ы) задача(и) диагностики: {', '.join(escalated)} "
                "(broken; решение по degraded — за тобой)."
            )
        if stale:
            lines.append(f"  ⚠ отчёт устарел ({gen}) — прогнать analyze_tool_health.py.")
        lines.append("  Детали: `data/reports/tools/_latest.md`.")
        return HookOutput().system_message("\n".join(lines))


if __name__ == "__main__":
    ToolHealthBanner().run()
