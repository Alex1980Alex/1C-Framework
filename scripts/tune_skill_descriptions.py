"""BP G3 (audit 260705) — description tuning: self-recall описаний через роутер.

Практика лидеров (agentskills.io skill-creator, description tuning): описание
скилла должно НАДЁЖНО активировать его на релевантных промптах. Здесь —
детерминированная (без LLM) диагностика: прогоняем СОБСТВЕННЫЕ триггер-ключи
бандла через реальный skill-router и смотрим, роутится ли бандл обратно к своему
скиллу. Низкий self-recall = слабое/неоднозначное описание (собственные триггеры
не активируют скилл → пользователь не найдёт его). Опционально: cross-activation
(чужие ключи ложно активируют скилл → описание слишком широкое).

Метрика на бандл:
  self_recall = доля собственных keywords, при которых router рекомендует
                хотя бы один skill бандла.

Report сортирован по self_recall ↑ (слабейшие описания сверху) — кандидаты на
переформулировку триггеров.

Live: вызывает `.claude/hooks/skill-router.py` как subprocess (переиспользует
`run_router` из `eval-skill-router.py`). Медленно (1 subprocess/ключ); `--limit`
ограничивает число ключей на бандл, `--skill` — один бандл.

Usage:
  python scripts/tune_skill_descriptions.py --limit 4          # быстрый прогон
  python scripts/tune_skill_descriptions.py --skill bsl-dev
  python scripts/tune_skill_descriptions.py --json
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Callable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG = PROJECT_ROOT / ".claude" / "skills" / "skill-router-config.json"
REPORT_DIR = PROJECT_ROOT / "data" / "reports" / "skills"
WEAK_THRESHOLD = 0.5  # self_recall < этого → флаг «слабое описание»


def _load_run_router() -> Callable[[str], dict]:
    spec = importlib.util.spec_from_file_location(
        "eval_skill_router", str(PROJECT_ROOT / "scripts" / "eval-skill-router.py")
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.run_router


# ============================ pure logic (testable) ==========================


def load_bundles(config: Path = CONFIG) -> dict[str, dict[str, Any]]:
    return json.loads(config.read_text(encoding="utf-8")).get("bundles", {})


def bundle_keywords(bundle: dict[str, Any], limit: int = 0) -> list[str]:
    """Триггер-ключи бандла (keywords + ключи weighted_keywords), уникальные."""
    kws: list[str] = list(bundle.get("keywords", []))
    for k in bundle.get("weighted_keywords", {}):
        if k not in kws:
            kws.append(k)
    return kws[:limit] if limit else kws


def score_bundle(bundle_skills: list[str], per_keyword_recos: list[list[str]]) -> dict[str, Any]:
    """self_recall = доля keywords, где рекомендация пересеклась со skills бандла.

    Pure: per_keyword_recos[i] = список рекомендованных skills для keyword i.
    """
    target = set(bundle_skills)
    n = len(per_keyword_recos)
    if not n or not target:
        return {"n": n, "self_recall": 0.0, "misses": []}
    hits = 0
    misses = []
    for i, recos in enumerate(per_keyword_recos):
        if target & set(recos):
            hits += 1
        else:
            misses.append(i)
    return {"n": n, "self_recall": round(hits / n, 4), "miss_idx": misses}


# ============================ live (router subprocess) ======================


def run_live(
    bundles: dict[str, dict[str, Any]], limit: int, run_router: Callable
) -> dict[str, Any]:
    results = {}
    for name, bundle in bundles.items():
        skills = bundle.get("skills", [])
        if not skills:
            continue
        kws = bundle_keywords(bundle, limit)
        per_kw: list[list[str]] = []
        miss_kws: list[str] = []
        for kw in kws:
            try:
                r = run_router(kw)
            except Exception:
                r = {"skills": []}
            recos = r.get("skills", []) or []
            per_kw.append(recos)
            if not (set(skills) & set(recos)):
                miss_kws.append(kw)
        sc = score_bundle(skills, per_kw)
        sc["skills"] = skills
        sc["weak"] = sc["self_recall"] < WEAK_THRESHOLD
        sc["miss_keywords"] = miss_kws
        results[name] = sc
    return results


def _print_utf8(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Skill description tuning via router self-recall (BP G3)"
    )
    ap.add_argument("--skill", default=None, help="один бандл")
    ap.add_argument("--limit", type=int, default=0, help="макс keywords на бандл (0=все)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    bundles = load_bundles()
    if args.skill:
        bundles = {k: v for k, v in bundles.items() if k == args.skill}
    if not bundles:
        _print_utf8(json.dumps({"status": "no-bundles"}))
        return 0

    run_router = _load_run_router()
    results = run_live(bundles, args.limit, run_router)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    (REPORT_DIR / "skill-description-tuning.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    if args.json:
        _print_utf8(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    ranked = sorted(results.items(), key=lambda kv: kv[1]["self_recall"])
    weak = [n for n, r in ranked if r["weak"]]
    _print_utf8(
        f"# description-tuning (BP G3): {len(results)} бандлов, слабых (self_recall<{WEAK_THRESHOLD}): {len(weak)}"
    )
    for name, r in ranked:
        flag = "⚠ СЛАБОЕ" if r["weak"] else "ok"
        _print_utf8(f"  {name}: self_recall={r['self_recall']} (n={r['n']}) {flag}")
        if r["weak"] and r["miss_keywords"]:
            _print_utf8(f"    не роутятся: {', '.join(r['miss_keywords'][:5])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
