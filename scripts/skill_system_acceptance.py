#!/usr/bin/env python3
"""Acceptance-метрики Skill System Full Verification (roadmap 260612 §P4).

Окно наблюдения: 2026-06-13 → 2026-06-27. Критерии приёмки (5-й потребитель
`acceptance_common` после skill-learning / memory-ai / pdf-docs / LinkRegistry):

  1. ghosts==0 & drift==0    — live dry-run `mirror_skill_library` (каталог ==
                               библиотека; ghosts = точки без каталога,
                               drift = SKILL.md без точки; changed-churn не в счёт)
  2. ingest events > 0       — события store=skill_library в memory-ingestion.log
                               в окне (поток виден write-contract'у §26)
  3. router F1 >= 0.75       — POOLED action_f1 последнего eval-отчёта
                               (`--save-report`) в окне (без silence-padding);
                               in-sample legacy macro-F1 и шумный test-сплит
                               НЕ принимаются (260613 F1)
  4. surfacing: floor режет  — gate.skill_below_floor > 0 в surfacing-логе окна
                               (шум отсекается живьём)
  5. surfacing: сигнал жив   — arms.skill > 0 хотя бы в одной инвокации окна
                               (порог не убил полезные подсказки)
  6. review-отчёт в каденсе  — data/reports/skills/skill-health-report.md
                               свежее 7 дней (job skill_review исполняется)
  7. honest-failure guards   — структурный регресс-чек C3/B2: в ci.yml жива
                               exit-1-ветка «нет ground-truth», в
                               code-skill-enforcer.py жив `_skill_exists`

Критерий 1 ходит в локальный Qdrant (остальные — локальные файлы); Qdrant down →
ghosts/drift = None → критерий честно FAIL (не маскируется).

Запуск:
  python scripts/skill_system_acceptance.py [--json] [--final] [--no-report]
--final принудительно считает вердикт (иначе PENDING до конца окна).
Отчёт: data/reports/memory/skill_system_acceptance_<stamp>.md.
"""

from __future__ import annotations

import argparse
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

CACHE_DIR = PROJECT_ROOT / ".claude" / "cache"
INGEST_LOG = CACHE_DIR / "memory-ingestion.log"
SURFACING_LOG = CACHE_DIR / "memory-first-surfacing.log"
ROUTER_REPORT = PROJECT_ROOT / "data" / "reports" / "skills" / "skill-router-eval-latest.json"
HEALTH_REPORT = PROJECT_ROOT / "data" / "reports" / "skills" / "skill-health-report.md"
CI_YML = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
ENFORCER = PROJECT_ROOT / ".claude" / "hooks" / "code-skill-enforcer.py"
GT_PATH = PROJECT_ROOT / "data" / "skill-router-ground-truth.jsonl"

WINDOW_START = datetime(2026, 6, 13)
WINDOW_END = datetime(2026, 6, 27)

F1_TARGET = 0.75
HEALTH_FRESH_DAYS = 7.0


def _mirror_dry_run() -> tuple[int | None, int | None, int | None]:
    """(ghosts, drift, changed) из live dry-run зеркала; Qdrant down → (None,None,None).

    drift   = SKILL.md без точки вовсе (presence-gap).
    changed = точка есть, но content_hash разошёлся с диском (260613 F4 — protux
              по контенту; presence-критерий 1 его не ловил → «зеркало» могло быть
              устаревшим по содержимому при drift=0).
    """
    try:
        shared_dir = str(PROJECT_ROOT / ".claude" / "hooks" / "shared")
        # append, не insert(0): не затенять hooks-local пакеты
        # ([[feedback-hook-src-shared-collision]])
        if shared_dir not in sys.path:
            sys.path.append(shared_dir)
        import skills_harvest

        stats = skills_harvest.mirror_skill_library(apply=False, snapshot=False)
        if stats.get("errors"):
            return None, None, None
        missing = stats.get("missing", [])
        to_upsert = stats.get("to_upsert", [])
        # to_upsert ⊇ missing; changed = present-but-stale = to_upsert \ missing.
        changed = max(0, len(to_upsert) - len(missing))
        return len(stats.get("ghosts", [])), len(missing), changed
    except Exception:
        return None, None, None


def _router_f1() -> dict[str, Any]:
    """Честные числа из последнего eval-отчёта в окне (260613 F1).

    Гейт (`gate`) читает POOLED `honest_metrics.action_f1` (без silence-padding),
    НЕ in-sample legacy macro-F1 и НЕ крошечный test-сплит. Train/test тут
    диагностический: роутер НЕ обучается на GT в eval-time (A2-веса захардкожены
    оффлайн), поэтому сплит не отражает обобщение — лишь подсвечивает шум/малость
    GT (мелкий test инвертирует vs train). Реальный held-out появится, только когда
    A2 переотобран на train-only. Старый отчёт без `honest_metrics` → gate=None →
    критерий 3 честно не проходит.
    """
    out: dict[str, Any] = {"gate": None, "legacy": None, "test": None, "train": None, "ts": None}
    try:
        rep = json.loads(ROUTER_REPORT.read_text(encoding="utf-8"))
    except Exception:
        return out
    out["ts"] = rep.get("ts")
    dt = _parse_dt(out["ts"])
    if dt is None or dt < WINDOW_START:
        return out  # отчёт устарел — число вне окна не принимается (gate=None)

    def _f(v: Any) -> float | None:
        try:
            return float(v) if v is not None else None
        except (TypeError, ValueError):
            return None

    out["legacy"] = _f((rep.get("skill_metrics") or {}).get("f1"))
    hm = rep.get("honest_metrics") or {}
    splits = hm.get("splits") or {}
    out["gate"] = _f(hm.get("action_f1"))  # pooled — стабильное число (gate)
    out["test"] = _f((splits.get("test") or {}).get("action_f1"))
    out["train"] = _f((splits.get("train") or {}).get("action_f1"))
    return out


def _grep(path: Path, needle: str) -> bool:
    try:
        return needle in path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False


def _ci_honest_fail() -> bool:
    """260613 F6: проверяем ФАКТ ветки `exit 1` при отсутствии ground-truth, а не
    текст echo (старый греп `"ground-truth.jsonl missing"` совпадал случайно — по
    хвосту имени файла; перефраз сообщения молча ронял критерий). Ищем guard-условие
    на skill-router-ground-truth.jsonl и `exit 1` в пределах нескольких строк."""
    try:
        lines = CI_YML.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False
    for i, ln in enumerate(lines):
        if "-f data/skill-router-ground-truth.jsonl" in ln:
            if any("exit 1" in x for x in lines[i : i + 5]):
                return True
    return False


def _gt_counts() -> tuple[int, int]:
    """(quarantined, test_action) из GT (260613 A5/A7 honesty-проводка).

    quarantined > 0 → гейт PROVISIONAL: leakage-кандидаты (трудные разговорные
    кейсы) изъяты из train/test, поэтому pooled action_f1 оптимистичен и не
    отражает hard-когорту. Критерий `gate_representative` держит all_pass честным
    (FAIL пока 22 не ре-верифицированы и не возвращены в гейт — A7). Ошибка → (-1,-1).
    """
    quar = test_action = 0
    try:
        for line in GT_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            if r.get("split") == "quarantine":
                quar += 1
            elif r.get("split") == "test" and r.get("expected_skills"):
                test_action += 1
    except (OSError, ValueError):
        return -1, -1
    return quar, test_action


def collect_metrics(now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now()
    ghosts, drift, changed = _mirror_dry_run()

    ingest_events = 0
    for rec in _read_jsonl(INGEST_LOG):
        if rec.get("store") != "skill_library":
            continue
        dt = _parse_dt(rec.get("ts") or rec.get("timestamp"))
        if dt is not None and dt >= WINDOW_START:
            ingest_events += 1

    floor_gated = 0
    arm_fired = 0
    invocations = 0
    for rec in _read_jsonl(SURFACING_LOG):
        dt = _parse_dt(rec.get("ts"))
        if dt is None or dt < WINDOW_START:
            continue
        invocations += 1
        gate = rec.get("gate") or {}
        floor_gated += gate.get("skill_below_floor", 0)
        arms = rec.get("arms") or {}
        if arms.get("skill", 0) > 0:
            arm_fired += 1

    rf = _router_f1()
    quarantined, gt_test_action = _gt_counts()

    health_age_days: float | None = None
    if HEALTH_REPORT.exists():
        health_age_days = round((now.timestamp() - HEALTH_REPORT.stat().st_mtime) / 86400, 1)

    return {
        "now": now.isoformat(timespec="seconds"),
        "window": f"{WINDOW_START.date()} → {WINDOW_END.date()}",
        "day": window_day(now, WINDOW_START),
        "window_closed": now >= WINDOW_END,
        "ghosts": ghosts,
        "drift": drift,
        "changed": changed,
        "ingest_events": ingest_events,
        "router_f1": rf["gate"],
        "router_f1_legacy": rf["legacy"],
        "router_f1_test": rf["test"],
        "router_f1_train": rf["train"],
        "router_f1_ts": rf["ts"],
        "quarantined": quarantined,
        "gt_test_action": gt_test_action,
        "floor_gated": floor_gated,
        "arm_fired": arm_fired,
        "invocations": invocations,
        "health_age_days": health_age_days,
        "ci_honest_fail": _ci_honest_fail(),
        "phantom_guard": _grep(ENFORCER, "_skill_exists"),
    }


def evaluate(m: dict[str, Any]) -> dict[str, bool]:
    return {
        "ghosts==0 & drift==0": m["ghosts"] == 0 and m["drift"] == 0,
        "library_content_fresh": m["changed"] == 0,  # 260613 F4: точки не устарели по контенту
        "ingest_events>0": m["ingest_events"] > 0,
        f"router_f1>={F1_TARGET}": m["router_f1"] is not None and m["router_f1"] >= F1_TARGET,
        # 260613 A5/A7 honesty: пока leakage-кандидаты в карантине, гейт меряет
        # designed-subset → action_f1 оптимистичен. all_pass честно FAIL, пока 22
        # не ре-верифицированы и не возвращены в гейт (A7). quarantined==0 → закрыто.
        "gate_representative": m["quarantined"] == 0,
        "floor_gates_noise": m["floor_gated"] > 0,
        "skill_arm_alive": m["arm_fired"] > 0,
        f"health_report<{HEALTH_FRESH_DAYS:.0f}d": (
            m["health_age_days"] is not None and m["health_age_days"] < HEALTH_FRESH_DAYS
        ),
        "honest_failure_guards": m["ci_honest_fail"] and m["phantom_guard"],
    }


def render(m: dict[str, Any], crit: dict[str, bool], final: bool) -> str:
    detail = [
        f"- Снято: {m['now']}",
        f"- зеркало (live dry-run): ghosts={m['ghosts']}, drift={m['drift']},"
        f" changed={m['changed']} — цель 0/0/0 (None = Qdrant недоступен)",
        f"- ingestion-события skill_library в окне: {m['ingest_events']} — цель >0",
        f"- router action F1 (gate, pooled): {m['router_f1']} — цель >={F1_TARGET}"
        f" | train {m['router_f1_train']} / test {m['router_f1_test']} (диагностика,"
        f" малый GT, не held-out) | legacy padded {m['router_f1_legacy']}"
        f" (отчёт {m['router_f1_ts']})",
        f"- gate representativeness: quarantined={m['quarantined']} (leakage-кандидаты"
        f" вне гейта), test action={m['gt_test_action']} — пока quarantined>0 гейт"
        f" PROVISIONAL (designed-subset, hard 1С-когорта изъята; вернуть через A7)",
        f"- surfacing: floor отрезал {m['floor_gated']} skill-хитов,"
        f" arm fired {m['arm_fired']}/{m['invocations']} инвокаций — цель >0 и >0",
        f"- skill-health-report возраст: {m['health_age_days']}d — цель <{HEALTH_FRESH_DAYS:.0f}d",
        f"- guards: ci_honest_fail={m['ci_honest_fail']}, phantom_guard={m['phantom_guard']}",
    ]
    return render_acceptance(
        f"# skill-system acceptance — день {m['day']}/14 ({m['window']})",
        m,
        crit,
        final=final,
        detail_lines=detail,
        roadmap_rel="docs/roadmap/260612_ROADMAP_SKILL_SYSTEM_FULL_VERIFICATION.md",
    )


def main() -> int:
    ap = argparse.ArgumentParser(description="skill-system acceptance (roadmap 260612 §P4)")
    ap.add_argument("--json", action="store_true", help="JSON output вместо markdown")
    ap.add_argument("--final", action="store_true", help="принудительный вердикт до конца окна")
    ap.add_argument("--no-report", action="store_true", help="не писать файл отчёта")
    args = ap.parse_args()

    m = collect_metrics()
    crit = evaluate(m)
    if args.json:
        _emit(
            json.dumps({**m, "criteria": crit, "all_pass": all(crit.values())}, ensure_ascii=False)
        )
        return 0
    _emit(
        render(m, crit, args.final),
        report_name=None if args.no_report else "skill_system_acceptance",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
