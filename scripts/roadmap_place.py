#!/usr/bin/env python3
"""
roadmap_place.py - helper to answer "which roadmap does a deferred task belong to?"

Greps docs/roadmap/*.md for given terms, ranks candidate roadmap files by
topical overlap, and suggests whether a new task should be ATTACHed to an
existing roadmap (as a subsection) or whether a CREATE (new roadmap file)
is warranted. Makes the placement heuristic reproducible instead of ad-hoc.

Usage:
    python scripts/roadmap_place.py "<term>" ["<term2>" ...] [--top N] [--json]
"""

import argparse
import json
import re
import sys
from pathlib import Path

ROADMAP_DIR = Path(__file__).resolve().parent.parent / "docs" / "roadmap"


def _date_key(name: str) -> int:
    m = re.match(r"(\d{6})", name)
    return int(m.group(1)) if m else 0


def rank(files: dict, terms: list[str]) -> list[dict]:
    results = []
    for name, text in files.items():
        low = text.lower()
        matched = [t for t in terms if t.lower() in low]
        hits = sum(low.count(t.lower()) for t in terms)
        if len(matched) > 0:
            results.append(
                {
                    "name": name,
                    "matched": matched,
                    "n_matched": len(matched),
                    "hits": hits,
                    "date": _date_key(name),
                }
            )
    results.sort(key=lambda r: (r["n_matched"], r["hits"], r["date"]), reverse=True)
    return results


def best_sections(text: str, terms: list[str], k: int = 3) -> list[str]:
    lower_terms = [t.lower() for t in terms]
    heading = None
    found: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip()
            continue
        low_line = line.lower()
        if any(t in low_line for t in lower_terms):
            if heading and heading not in found:
                found.append(heading)
                if len(found) >= k:
                    break
    return found


def suggest(candidates: list[dict], terms: list[str]) -> dict:
    if not candidates:
        return {
            "action": "create",
            "reason": "нет топикального совпадения в docs/roadmap/ - новый роадмап",
        }

    top = candidates[0]
    if top["n_matched"] >= 2 or (len(terms) == 1 and top["n_matched"] == 1 and top["hits"] >= 2):
        return {
            "action": "attach",
            "target": top["name"],
            "reason": "сильная связь (subject уже имеет нить)",
        }

    return {
        "action": "attach_or_create",
        "target": top["name"],
        "reason": (
            "слабая связь - привязать как подсекцию ЛИБО новый роадмап; "
            "решай по СУБЪЕКТУ задачи, не по механизму"
        ),
    }


def main():
    parser = argparse.ArgumentParser(
        description="Определяет, к какому роадмапу привязать отложенную задачу."
    )
    parser.add_argument("terms", nargs="+", help="термины для поиска")
    parser.add_argument("--top", type=int, default=5, help="сколько кандидатов показать")
    parser.add_argument("--json", action="store_true", help="вывод в JSON")
    args = parser.parse_args()

    if not ROADMAP_DIR.is_dir():
        print(f"Ошибка: директория не найдена: {ROADMAP_DIR}", file=sys.stderr)
        sys.exit(1)

    files = {
        p.name: p.read_text(encoding="utf-8", errors="replace") for p in ROADMAP_DIR.glob("*.md")
    }

    cands = rank(files, args.terms)
    sug = suggest(cands, args.terms)

    if args.json:
        print(
            json.dumps(
                {"terms": args.terms, "suggestion": sug, "candidates": cands[: args.top]},
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    print(f"# Roadmap placement для: {', '.join(args.terms)}")
    for i, c in enumerate(cands[: args.top], 1):
        print(
            f"  {i}. {c['name']}  (терминов: {c['n_matched']}/{len(args.terms)}, hits: {c['hits']})"
        )
        sections = best_sections(files[c["name"]], args.terms)
        if sections:
            print(f"      секции: {', '.join(sections)}")

    print()
    action = sug["action"]
    if action == "attach":
        print(f"→ ATTACH к {sug['target']} ({sug['reason']}) - как подсекцию NEXT/раздел")
    elif action == "attach_or_create":
        print(f"→ ATTACH к {sug['target']} ЛИБО новый ({sug['reason']})")
    else:
        print(f"→ CREATE новый: docs/roadmap/<YYMMDD>_ROADMAP_<ТЕМА>.md ({sug['reason']})")

    print(
        "Правило: привязка по СУБЪЕКТУ задачи, не по инструменту-обходу; "
        "малый follow-up → подсекция, крупная новая тема → новый файл + кросс-линк."
    )


if __name__ == "__main__":
    main()
