#!/usr/bin/env python3
"""ADR-025 Этап 3: reproducible bootstrap расширения GT детектора 1С (для обучения гейта).

Два источника кандидатов:
  1. **Майнинг реальных тайтлов задач** — имена папок ``configuration/*/docs/<task>/``
     (реальные 1С-задачи, JIRA-кодированные); дата/JIRA срезаются → описательный тайтл +
     фразы поверх ``гкс_``-объектов. is_1c=True, route_class — детектором (silver).
  2. **Курируемые hard-кейсы** — НЕ хранятся в коде (иначе content-enforcer ложит 1С-токены);
     это РУЧНЫЕ человеческие метки, живут в самом ``data/1c-detector-gt-candidates.json``
     (поля ``source ∈ {hard_fn, near_domain, negative, weak, gks_ref_mined}``). Re-run
     ре-майнит тайтлы и СОХРАНЯЕТ прежние курируемые из этого файла.

``review=True`` там, где regex не согласен с меткой (hard-граница на ревью человеку).
``--merge`` сливает кандидаты в GT (только ``text/is_1c/route_class/source/split``).

Usage:
    python scripts/bootstrap_1c_gt.py            # ре-майн + preserve curated → кандидаты + сводка
    python scripts/bootstrap_1c_gt.py --merge    # слить кандидаты в GT (после ревью)
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GT = ROOT / "data" / "1c-detector-ground-truth.json"
CANDIDATES = ROOT / "data" / "1c-detector-gt-candidates.json"
BRIDGE = ROOT / ".claude" / "hooks" / "shared" / "pipeline_1c_bridge.py"
CURATED_SOURCES = ("hard_fn", "near_domain", "negative", "weak", "gks_ref_mined")

_JIRA = re.compile(r"^(?:\d{6}_)?[A-Z]{2,}[_-]?\d+\s*")
_DATE = re.compile(r"^\d{6}_?")
_SKIP = re.compile(r"встреча|телемост|запись|обсужден|диалог|^\d{4}-\d\d-\d\d|"
                   r"^analysis|^esti|^информаци|^вариант|copy$|^[a-z0-9_]+$", re.I)


def _classify():
    spec = importlib.util.spec_from_file_location("bridge_boot", BRIDGE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.classify_1c_task


def mine_titles() -> list[str]:
    out, seen = [], set()
    for d in sorted(ROOT.glob("configuration/*/docs/*")):
        if not d.is_dir() or d.name.startswith("гкс_") or _SKIP.search(d.name):
            continue
        t = _DATE.sub("", _JIRA.sub("", d.name)).strip()
        t = re.sub(r"^\d+\.\s*", "", t).strip().rstrip(".")
        if len(t) >= 12 and len(t.split()) >= 3 and t.lower() not in seen:
            seen.add(t.lower())
            out.append(t)
    return out


def split_of(text: str) -> str:
    return "test" if int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16) % 5 == 0 else "train"


def _norm(t: str) -> str:
    return " ".join(t.lower().split())


def build() -> list[dict]:
    classify = _classify()
    gt_norm = {_norm(r["text"]) for r in json.loads(GT.read_text(encoding="utf-8"))}
    curated = []
    if CANDIDATES.exists():
        curated = [r for r in json.loads(CANDIDATES.read_text(encoding="utf-8"))
                   if r.get("source") in CURATED_SOURCES]
    rows, seen = [], set(gt_norm)

    def add(text: str, is_1c: bool, source: str) -> None:
        text = text.strip()
        k = _norm(text)
        if not text or k in seen:
            return
        seen.add(k)
        cl = classify(text)
        rx = bool(cl.get("is_1c"))
        route = "none" if not is_1c else ("confident" if cl.get("confidence", 0) >= 0.7 else "ask")
        rows.append({"text": text, "is_1c": is_1c, "route_class": route, "source": source,
                     "split": split_of(text), "regex_is_1c": rx,
                     "regex_conf": cl.get("confidence", 0.0), "review": is_1c != rx})

    for t in mine_titles():               # ре-майн реальных тайтлов
        add(t, True, "tz_title_mined")
    for r in curated:                     # сохранить РУЧНЫЕ курируемые метки
        add(str(r["text"]), bool(r["is_1c"]), str(r["source"]))
    return rows


def merge_into_gt(cands: list[dict]) -> int:
    gt = json.loads(GT.read_text(encoding="utf-8"))
    existing = {_norm(r["text"]) for r in gt}
    added = 0
    for c in cands:
        if _norm(c["text"]) in existing:
            continue
        gt.append({k: c[k] for k in ("text", "is_1c", "route_class", "source", "split")})
        existing.add(_norm(c["text"]))
        added += 1
    lines = ["["] + ["  " + json.dumps(r, ensure_ascii=False) + ("," if i < len(gt) - 1 else "")
                     for i, r in enumerate(gt)] + ["]"]
    GT.write_text("\n".join(lines), encoding="utf-8")
    return added


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Bootstrap 1C-detector GT (ADR-025 Stage 3)")
    ap.add_argument("--merge", action="store_true", help="слить кандидаты в GT после ревью")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    if args.merge:
        n = merge_into_gt(json.loads(CANDIDATES.read_text(encoding="utf-8")))
        print(f"merged +{n} -> GT={len(json.loads(GT.read_text(encoding='utf-8')))}")
        return 0

    rows = build()
    CANDIDATES.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
    pos = sum(1 for r in rows if r["is_1c"])
    rev = [r for r in rows if r["review"]]
    by_src: dict[str, int] = {}
    for r in rows:
        by_src[r["source"]] = by_src.get(r["source"], 0) + 1
    print(f"candidates -> {CANDIDATES.name}: {len(rows)} (pos={pos} neg={len(rows) - pos})")
    print("по источникам:", dict(sorted(by_src.items())))
    print(f"review (regex != метка): {len(rev)}  FN={sum(1 for r in rev if r['is_1c'])} "
          f"FP={sum(1 for r in rev if not r['is_1c'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
