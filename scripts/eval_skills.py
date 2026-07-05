"""BP G2 (audit 260705) — per-skill eval harness с baseline (with vs without).

Мы меряли только РОУТИНГ (активируется ли нужный навык), но никогда — ЦЕННОСТЬ
СОДЕРЖИМОГО: улучшает ли загруженный навык ответ ПО СРАВНЕНИЮ с baseline (без него)?
Практика лидеров (agentskills.io skill-creator, caliper): evals ЛЕЖАТ в каталоге +
обязательное сравнение с baseline.

Схема: для каждого eval-кейса гоняем LLM ДВАЖДЫ — без навыка (baseline) и с его телом
в system_prompt (with) — и считаем детерминированные ассерты (caliper assert — дешевле
LLM-judge): expect (regex, должны присутствовать) + must_not (regex, не должны).
delta = with_pass - baseline_pass — если >0, навык добавляет ценность.

Формат opt-in: .claude/skills/<name>/evals.yaml
    cases:
      - id: read-attribute
        prompt: "..."
        expect: ["regex1"]
        must_not: ["regex2"]

Live-путь (LLM) gated: провайдеры недоступны -> status skipped, exit 0.
Pure-логика (load/score/aggregate) отделена -> unit-тесты без LLM.

Usage:
  python scripts/eval_skills.py
  python scripts/eval_skills.py --skill code-verify
  python scripts/eval_skills.py --json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
REPORT_DIR = PROJECT_ROOT / "data" / "eval" / "skills"

BASE_SYS = (
    "Ты — ассистент по разработке в проекте PDF/1С-фреймворка. "
    "Отвечай кратко, конкретно, по существу вопроса."
)
MAX_TOKENS = 400
TEMPERATURE = 0.0


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    return text[end + 4 :] if end != -1 else text


def load_evals(skills_dir: Path = SKILLS_DIR) -> dict[str, dict[str, Any]]:
    """Каталоги с evals.yaml -> {name: {cases, body}}."""
    import yaml

    out: dict[str, dict[str, Any]] = {}
    for d in sorted(skills_dir.iterdir()):
        if not d.is_dir() or d.name.startswith((".", "_")):
            continue
        ev = d / "evals.yaml"
        smd = d / "SKILL.md"
        if not ev.exists() or not smd.exists():
            continue
        spec = yaml.safe_load(ev.read_text(encoding="utf-8")) or {}
        cases = spec.get("cases", [])
        if not cases:
            continue
        out[d.name] = {"cases": cases, "body": _strip_frontmatter(smd.read_text(encoding="utf-8"))}
    return out


def score_output(text: str, expect: list[str], must_not: list[str]) -> dict[str, Any]:
    """passed = (все expect матчатся, regex i) AND (ни один must_not)."""
    text = text or ""
    expect = expect or []
    must_not = must_not or []
    hits = sum(1 for p in expect if re.search(p, text, re.IGNORECASE | re.UNICODE))
    viol = [p for p in must_not if re.search(p, text, re.IGNORECASE | re.UNICODE)]
    return {
        "passed": (hits == len(expect)) and not viol,
        "expect_hits": hits,
        "expect_total": len(expect),
        "violations": viol,
    }


def aggregate(per_case: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(per_case)
    if not n:
        return {"n": 0, "baseline_pass": 0.0, "skill_pass": 0.0, "delta": 0.0, "regressions": []}
    base = sum(1 for c in per_case if c["baseline"]["passed"]) / n
    skl = sum(1 for c in per_case if c["with_skill"]["passed"]) / n
    return {
        "n": n,
        "baseline_pass": round(base, 4),
        "skill_pass": round(skl, 4),
        "delta": round(skl - base, 4),
        "regressions": [
            c["id"] for c in per_case if c["baseline"]["passed"] and not c["with_skill"]["passed"]
        ],
    }


def evaluate_offline(
    body: str, cases: list[dict[str, Any]], completions: dict[str, dict[str, str]]
) -> dict[str, Any]:
    """Pure: given precomputed completions {id: {baseline, with_skill}}, score."""
    per_case = []
    for case in cases:
        cid = case["id"]
        comp = completions.get(cid, {"baseline": "", "with_skill": ""})
        exp, mn = case.get("expect", []), case.get("must_not", [])
        per_case.append(
            {
                "id": cid,
                "baseline": score_output(comp.get("baseline", ""), exp, mn),
                "with_skill": score_output(comp.get("with_skill", ""), exp, mn),
            }
        )
    return {"per_case": per_case, "aggregate": aggregate(per_case)}


def _service():
    from src.shared.llm_rotation import get_service

    return get_service()


async def _complete(service: Any, prompt: str, system_prompt: str) -> str:
    res = await service.complete(
        prompt=prompt,
        system_prompt=system_prompt,
        temperature=TEMPERATURE,
        max_tokens=MAX_TOKENS,
        timeout=60,
    )
    if isinstance(res, dict):
        return res.get("content") or res.get("text") or ""
    return str(res or "")


def run_live(skills: dict[str, dict[str, Any]]) -> dict[str, Any]:
    import asyncio

    try:
        service = _service()
    except Exception as exc:
        return {"status": "live-deps-unavailable", "reason": f"{type(exc).__name__}: {exc}"}

    async def _all():
        out: dict[str, dict[str, dict[str, str]]] = {}
        for name, spec in skills.items():
            with_sys = BASE_SYS + "\n\n[АКТИВИРОВАН НАВЫК]\n" + spec["body"][:8000]
            comps: dict[str, dict[str, str]] = {}
            for case in spec["cases"]:
                base = await _complete(service, case["prompt"], BASE_SYS)
                skl = await _complete(service, case["prompt"], with_sys)
                comps[case["id"]] = {"baseline": base, "with_skill": skl}
            out[name] = comps
        return out

    try:
        completions = asyncio.run(_all())
    except Exception as exc:
        return {"status": "live-deps-unavailable", "reason": f"{type(exc).__name__}: {exc}"}

    results = {}
    for name, spec in skills.items():
        results[name] = evaluate_offline(spec["body"], spec["cases"], completions.get(name, {}))
    return {"status": "ok", "results": results}


def _print_utf8(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Per-skill eval harness (audit 260705 BP G2)")
    ap.add_argument("--skill", default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    skills = load_evals()
    if args.skill:
        skills = {k: v for k, v in skills.items() if k == args.skill}
    if not skills:
        _print_utf8(json.dumps({"status": "no-evals", "reason": "нет каталогов с evals.yaml"}))
        return 0

    report = run_live(skills)
    if report.get("status") != "ok":
        _print_utf8(json.dumps(report, ensure_ascii=False))
        return 0

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "skill_evals.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.json:
        _print_utf8(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    _print_utf8("# Per-skill eval (BP G2) — baseline vs with")
    for name, res in report["results"].items():
        agg = res["aggregate"]
        verdict = (
            "ADD-VALUE" if agg["delta"] > 0 else ("NEUTRAL" if agg["delta"] == 0 else "REGRESS")
        )
        _print_utf8(
            "  {}: baseline={} with={} delta={:+} (n={}) {}".format(
                name, agg["baseline_pass"], agg["skill_pass"], agg["delta"], agg["n"], verdict
            )
        )
        if agg["regressions"]:
            _print_utf8("    регрессии: " + ", ".join(agg["regressions"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
