#!/usr/bin/env python3
"""Phase 0 — build a SEMANTIC (vocab-mismatch) BSL golden set.

Purpose
-------
The shipped ``data/bsl_golden_set.json`` is only *mildly* mismatched: its
NL queries paraphrase intent but stay in-vocabulary with the BSL Cyrillic
identifiers, so CamelCase-normalized term overlap survives and BM25 wins
(~90% Hit@10) while dense collapses (~17%). See memory entries
``feedback_bsl_sparse_bm25_dominance`` / ``feedback_bsl_embedding_collapse``.

This script produces a HARDER golden set deliberately engineered for
*vocabulary mismatch* — the regime where lexical BM25 is structurally
disadvantaged and a working dense retriever should help. For each selected
export procedure/function the LLM is asked to describe, in one phrase, WHAT
the procedure does *in essence*, WITHOUT using its name, the names of any
methods/attributes it calls, or literal code tokens.

Pipeline
--------
1. Qdrant ``scroll`` over ``bsl_code_v4_late`` (read-only) filtering for
   SIGNIFICANT export symbols:
     symbol_type in {Function, Procedure}
     is_export = True
     caller_count > 0            (actually used somewhere -> meaningful)
     module_path contains "CommonModules"  (matches bench scope filter so
                                            the positive is reachable)
2. Oversample, then sample ``--count`` unique-by-module candidates for
   variety across modules.
3. For each: call llm-rotation ``complete()`` to produce an RU NL paraphrase
   query with FORCED vocab-mismatch (no symbol/method/attribute names, no
   code tokens). Defensive post-check flags any name leakage.
4. Write ``data/eval/bsl/bsl_semantic_golden.json`` in a schema COMPATIBLE
   with ``scripts/bench_bsl_realistic_eval.py`` (id / query /
   expected[{module_path,line_start,line_end}] / slice) plus a ``positive``
   chunk_id and ``_meta`` block for traceability.

Read-only contract
------------------
Touches the production collection with ``scroll`` only. Writes a brand-new
file under ``data/eval/bsl/``. Nothing in the prod collection is mutated.

Run
---
    .venv\\Scripts\\python.exe scripts\\bsl_phase0_semantic_golden.py
    .venv\\Scripts\\python.exe scripts\\bsl_phase0_semantic_golden.py --count 50 --seed 42
"""

from __future__ import annotations

import argparse
import asyncio
import json
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "eval" / "bsl" / "bsl_semantic_golden.json"

# ---------------------------------------------------------------------------
# Slice bucketing (mirror generate_bsl_golden_set.py for cross-set parity)
# ---------------------------------------------------------------------------


def _slice_for_size(size_bytes: int) -> str:
    if size_bytes < 50_000:
        return "small"
    if size_bytes < 300_000:
        return "medium"
    return "god_object"


def _file_size_safe(path: str) -> int:
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


# ---------------------------------------------------------------------------
# Name-leak detection: split a Cyrillic CamelCase identifier into word stems
# so we can detect if the LLM echoed the symbol name (defeating the mismatch).
# ---------------------------------------------------------------------------

_CAMEL_SPLIT = re.compile(r"(?<=[а-яёa-z])(?=[А-ЯЁA-Z])")


def _name_tokens(name: str) -> list[str]:
    """CamelCase-split a (possibly гкс_-prefixed) identifier into >=4-char words."""
    raw = name.replace("гкс_", "").replace("_", " ")
    parts: list[str] = []
    for chunk in raw.split():
        parts.extend(_CAMEL_SPLIT.split(chunk))
    return [p for p in parts if len(p) >= 4]


def _name_leaked(query: str, name: str) -> bool:
    """True if the verbatim name OR >=2 of its CamelCase word-stems appear."""
    q = query.lower()
    if name.lower() in q:
        return True
    toks = [t.lower() for t in _name_tokens(name)]
    hits = sum(1 for t in toks if t in q)
    return len(toks) >= 2 and hits >= 2


# ---------------------------------------------------------------------------
# LLM prompt — force vocabulary mismatch
# ---------------------------------------------------------------------------


def _build_prompt(payload: dict[str, Any]) -> str:
    symbol_type = payload.get("symbol_type", "?")
    content = (payload.get("content") or "")[:1500]
    return f"""Ты помогаешь собрать поисковый бенчмарк для кода 1С (BSL).

Ниже приведён код {symbol_type.lower()}. Сформулируй ОДИН короткий запрос на
русском языке, который описывает, ЧТО ЭТА процедура делает ПО СУТИ — так,
как сформулировал бы пользователь, который НЕ видел кода и НЕ знает имён в нём.

Код:
```bsl
{content}
```

ЖЁСТКИЕ требования (это самое важное):
1. НЕ используй имя самой процедуры/функции — ни целиком, ни по частям.
2. НЕ используй имена методов, реквизитов, переменных, параметров из кода.
3. НЕ копируй фрагменты кода и литеральные токены (имена объектов, ключей).
4. Опиши намерение/результат своими словами, как бизнес-задачу или цель.
5. По возможности используй СИНОНИМЫ и обобщающие слова вместо терминов кода
   (например, не "ЗавершитьСеанс", а "разлогинить пользователя").
6. Естественная разговорная формулировка, 5-15 слов.
7. Без кавычек, без вступлений и пояснений — ТОЛЬКО сам запрос одной строкой.

Запрос:"""


async def _acomplete(service: Any, prompt: str, provider: str | None) -> str | None:
    result = await service.complete(
        prompt=prompt,
        max_tokens=120,
        temperature=0.4,
        preferred_provider=provider,
    )
    return (result.get("text") or "").strip() or None


def _clean(text: str) -> str:
    """Strip wrapping quotes / leading bullet noise from an LLM one-liner."""
    t = text.strip().strip("`").strip()
    t = t.strip('"').strip("«»").strip()
    # collapse to first line
    t = t.splitlines()[0].strip() if t else t
    return t


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass

    ap = argparse.ArgumentParser(description="Build semantic (vocab-mismatch) BSL golden set")
    ap.add_argument("--collection", default="bsl_code_v4_late")
    ap.add_argument("--count", type=int, default=50)
    ap.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--qdrant-url", default="http://localhost:6333")
    ap.add_argument(
        "--provider",
        default=None,
        help="Preferred llm-rotation provider (default: rotation's own order)",
    )
    ap.add_argument(
        "--min-content",
        type=int,
        default=120,
        help="Skip symbols whose indexed content is shorter than this (too thin to paraphrase)",
    )
    args = ap.parse_args()

    random.seed(args.seed)

    from qdrant_client import QdrantClient, models

    qdrant = QdrantClient(url=args.qdrant_url, timeout=120)

    scroll_filter = models.Filter(
        must=[
            models.FieldCondition(
                key="symbol_type",
                match=models.MatchAny(any=["Function", "Procedure"]),
            ),
            models.FieldCondition(key="is_export", match=models.MatchValue(value=True)),
            models.FieldCondition(key="caller_count", range=models.Range(gt=0)),
            models.FieldCondition(
                key="module_path",
                match=models.MatchText(text="CommonModules"),
            ),
        ]
    )

    oversample_target = max(args.count * 12, 600)
    print(f"[scroll] up to {oversample_target} export symbols from {args.collection} ...")
    candidates: list[dict[str, Any]] = []
    offset = None
    while len(candidates) < oversample_target:
        pts, offset = qdrant.scroll(
            collection_name=args.collection,
            limit=256,
            with_payload=True,
            with_vectors=False,
            scroll_filter=scroll_filter,
            offset=offset,
        )
        for p in pts:
            pl = p.payload or {}
            if not pl.get("name") or not pl.get("module_path"):
                continue
            content = pl.get("content") or ""
            if len(content) < args.min_content:
                continue
            pl["_point_id"] = p.id
            candidates.append(pl)
        if offset is None:
            break
    print(f"[scroll] {len(candidates)} candidate export symbols")

    # Dedup by module_path so a god-object module can't dominate, then sample.
    by_module: dict[str, list[dict[str, Any]]] = {}
    for pl in candidates:
        by_module.setdefault(pl["module_path"], []).append(pl)
    one_per_module = [random.choice(v) for v in by_module.values()]
    random.shuffle(one_per_module)
    print(f"[sample] {len(by_module)} distinct modules -> picking {args.count}")

    if len(one_per_module) < args.count:
        # not enough distinct modules: fall back to allowing repeats across modules
        pool = list(candidates)
        random.shuffle(pool)
        sampled = pool[: args.count]
    else:
        sampled = one_per_module[: args.count]

    from src.shared.llm_rotation import get_service

    service = get_service()

    print(f"[llm] generating {len(sampled)} vocab-mismatch queries (sequential) ...")
    golden: list[dict[str, Any]] = []
    failures = 0
    leaked = 0
    t_start = time.time()

    for idx, pl in enumerate(sampled, 1):
        name = pl["name"]
        prompt = _build_prompt(pl)
        query: str | None = None
        leak = False
        # up to 2 attempts to dodge a name leak
        for attempt in range(2):
            t_call = time.perf_counter()
            try:
                raw = asyncio.run(_acomplete(service, prompt, args.provider))
            except Exception as e:  # bulk batch generation — keep going on any error
                print(f"  [{idx}/{len(sampled)}] WARN llm err {type(e).__name__}: {e}")
                raw = None
            dt = time.perf_counter() - t_call
            if not raw:
                continue
            cand = _clean(raw)
            leak = _name_leaked(cand, name)
            query = cand
            if not leak:
                break
            if attempt == 0:
                print(f"  [{idx}/{len(sampled)}] name leaked, retrying ({dt:.1f}s)")

        if not query:
            failures += 1
            print(f"  [{idx}/{len(sampled)}] FAIL - skipped")
            continue
        if leak:
            leaked += 1

        size = _file_size_safe(pl["module_path"])
        slc = _slice_for_size(size)
        line_start = int(pl.get("line_start") or 0)
        item = {
            "id": f"SEM-{idx:03d}",
            "query": query,
            # bench-compatible ground truth (matched on module_path:line_start)
            "expected": [
                {
                    "module_path": pl["module_path"],
                    "line_start": line_start,
                    "line_end": int(pl.get("line_end") or 0),
                }
            ],
            "slice": slc,
            # task-requested positive identifier
            "positive": pl.get("chunk_id"),
            "_meta": {
                "name": name,
                "symbol_type": pl.get("symbol_type"),
                "caller_count": int(pl.get("caller_count") or 0),
                "module_size_bytes": size,
                "name_leaked": leak,
                "point_id": str(pl.get("_point_id")),
            },
        }
        golden.append(item)
        if idx % 5 == 0 or idx == len(sampled):
            elapsed = time.time() - t_start
            print(f"  [{idx}/{len(sampled)}] OK slice={slc} ({elapsed:.0f}s total)")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(golden, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    by_slice: dict[str, int] = {}
    for item in golden:
        by_slice[item["slice"]] = by_slice.get(item["slice"], 0) + 1

    print(f"\n[out] {args.output}")
    print(f"[out] wrote {len(golden)} items (failures={failures}, name_leaked={leaked})")
    print(f"[out] slice distribution: {by_slice}")
    return 0 if golden else 1


if __name__ == "__main__":
    sys.exit(main())
