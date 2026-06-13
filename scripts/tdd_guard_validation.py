#!/usr/bin/env python3
"""Авто-валидация tdd-guard (roadmap 260613 Этап 4.3 / ADR-015).

Наблюдает advisory-события `tdd-guard` (`.claude/cache/tdd-guard-events.jsonl`) в окне
2026-06-13 → 2026-06-20 (1 неделя) и **автоматически выдаёт решение** hard-block vs
keep-advisory — без ручного анализа.

Логика решения (на закрытии окна / `--final`):
  - tdd-guard НЕ включён            → recommendation = "not-running" (нужен enable)
  - мало данных (0 событий, <3 дней) → "insufficient-data"
  - шумно (>5 advisory/день)         → "keep-advisory" (блок был бы слишком навязчив)
  - follow_rate >= 0.5 (подсказка уважается: тест появился) → "hard-block" (правило
                                       редко-триггерится и соблюдается → безопасно энфорсить)
  - иначе (в основном игнорируется)  → "keep-advisory"

`followed` = для модуля из advisory сейчас существует `tests/**/test_<mod>.py`
(подсказка сработала). `ignored` = теста всё ещё нет.

Запуск: python scripts/tdd_guard_validation.py [--json] [--final] [--no-report]
Отчёт: data/reports/memory/tdd_guard_validation_<stamp>.md.
Переиспользует общий каркас acceptance_common.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from acceptance_common import emit as _emit
from acceptance_common import parse_dt as _parse_dt
from acceptance_common import read_jsonl as _read_jsonl
from acceptance_common import render_acceptance, window_day

EVENTS_LOG = PROJECT_ROOT / ".claude" / "cache" / "tdd-guard-events.jsonl"
# project + local (enable обычно в local — per-user, gitignored)
SETTINGS_FILES = [
    PROJECT_ROOT / ".claude" / "settings.json",
    PROJECT_ROOT / ".claude" / "settings.local.json",
]

WINDOW_START = datetime(2026, 6, 13)
WINDOW_END = datetime(2026, 6, 20)
NOISE_PER_DAY = 5.0  # > → слишком шумно для hard-block
FOLLOW_OK = 0.5  # follow_rate >= → подсказка уважается


def _tdd_guard_enabled() -> bool:
    """tdd-guard зарегистрирован в PreToolUse И TDD_GUARD_ENABLE=1 в env (project ИЛИ
    local settings — hooks/env мёржатся по областям, enable обычно в local)."""
    env_on = registered = False
    for p in SETTINGS_FILES:
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if (s.get("env") or {}).get("TDD_GUARD_ENABLE") == "1":
            env_on = True
        if "tdd-guard.py" in json.dumps(s.get("hooks", {})):
            registered = True
    return env_on and registered


def _module_has_test(module: str) -> bool:
    for pat in (f"test_{module}.py", f"{module}_test.py"):
        if glob.glob(f"{PROJECT_ROOT}/tests/**/{pat}", recursive=True):
            return True
    return False


def collect_metrics(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    enabled = _tdd_guard_enabled()

    advisories = 0
    modules: set[str] = set()
    for rec in _read_jsonl(EVENTS_LOG):
        dt = _parse_dt(rec.get("ts"))
        if dt is None or dt < WINDOW_START:
            continue
        advisories += 1
        m = rec.get("module")
        if m:
            modules.add(m)

    followed = sum(1 for m in modules if _module_has_test(m))
    ignored = len(modules) - followed
    follow_rate = round(followed / len(modules), 3) if modules else None
    day = window_day(now, WINDOW_START)
    per_day = round(advisories / max(1, day), 2)

    # авто-решение. hard-block — ТОЛЬКО при positive-evidence (правило срабатывало и
    # уважается); 0 advisories = нет сигнала → insufficient-data (не заключаем на пустоте).
    if not enabled:
        rec_decision = "not-running"
    elif advisories == 0:
        rec_decision = "insufficient-data"
    elif per_day > NOISE_PER_DAY:
        rec_decision = "keep-advisory"
    elif follow_rate is not None and follow_rate >= FOLLOW_OK:
        rec_decision = "hard-block"
    else:
        rec_decision = "keep-advisory"

    return {
        "now": now.isoformat(timespec="seconds"),
        "window": f"{WINDOW_START.date()} → {WINDOW_END.date()}",
        "day": day,
        "window_closed": now >= WINDOW_END,
        "enabled": enabled,
        "advisories": advisories,
        "unique_modules": len(modules),
        "followed": followed,
        "ignored": ignored,
        "follow_rate": follow_rate,
        "per_day": per_day,
        "recommendation": rec_decision,
    }


def evaluate(m: dict[str, Any]) -> dict[str, bool]:
    """Критерии готовности к решению (не качество — готовность вердикта)."""
    return {
        "tdd-guard включён (валидация идёт)": m["enabled"],
        "данные/время накоплены": m["advisories"] > 0 or m["day"] >= 7,
        "решение вычислено": m["recommendation"] in ("hard-block", "keep-advisory"),
    }


def render(m: dict[str, Any], crit: dict[str, bool], final: bool) -> str:
    rec = m["recommendation"]
    rec_human = {
        "hard-block": "РЕКОМЕНДАЦИЯ: перевести tdd-guard в hard-block (правило редко-триггерится и соблюдается)",
        "keep-advisory": "РЕКОМЕНДАЦИЯ: оставить advisory (блок был бы навязчив / правило игнорируется)",
        "not-running": "tdd-guard НЕ включён — валидация не идёт (нужен enable: PreToolUse-entry + TDD_GUARD_ENABLE=1)",
        "insufficient-data": "недостаточно данных — продолжить наблюдение",
    }.get(rec, rec)
    detail = [
        f"- Снято: {m['now']}",
        f"- tdd-guard включён: {m['enabled']}",
        f"- advisory за окно: {m['advisories']} ({m['per_day']}/день), уник. модулей: {m['unique_modules']}",
        f"- followed (тест появился): {m['followed']} / ignored: {m['ignored']} / follow_rate: {m['follow_rate']}",
        f"- **{rec_human}**",
    ]
    return render_acceptance(
        f"# tdd-guard validation — день {m['day']}/7 ({m['window']})",
        m,
        crit,
        final=final,
        detail_lines=detail,
        roadmap_rel="docs/roadmap/260613_ROADMAP_TOOLING_ADOPTION.md",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="tdd-guard validation (260613 4.3)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--final", action="store_true", help="принудительный вердикт до конца окна")
    ap.add_argument("--no-report", action="store_true")
    args = ap.parse_args()
    m = collect_metrics()
    crit = evaluate(m)
    if args.json:
        _emit(json.dumps({**m, "criteria": crit, "all_pass": all(crit.values())}, ensure_ascii=False))
        return 0
    _emit(
        render(m, crit, args.final),
        report_name=None if args.no_report else "tdd_guard_validation",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
