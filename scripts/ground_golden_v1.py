"""Ground golden_v1 — populate `expected_chunk_ids` via LLM-assisted relevance judging.

Roadmap 260509 §2.2 v2.0: takes the 40 hand-curated queries from
`data/eval/golden_v1.json` and asks Z.AI (via LLM Rotation) which of the
top-15 retrieved chunks from `framework_code_v1` truly answer each query.

Pipeline per item:
  1. Embed query with Qwen3 instruction prefix via TEI HTTP.
  2. Qdrant top-15 from `framework_code_v1` (single-vector, no `using=` needed).
  3. LLM judges which 0-3 candidates are truly relevant (JSON output).
  4. Write `expected_chunk_ids` back to `golden_v1.json` (atomic, after each item).

Idempotency: items where `expected_chunk_ids` is already populated are
skipped unless `--force` is passed. Saves after every item — resumable.

Usage:
    python scripts/ground_golden_v1.py                # ground all unfilled
    python scripts/ground_golden_v1.py --force        # re-ground all
    python scripts/ground_golden_v1.py --ids gv1-001,gv1-002  # subset
    python scripts/ground_golden_v1.py --dry-run      # print, don't save
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from qdrant_client import QdrantClient  # noqa: E402

GOLDEN_PATH = _REPO_ROOT / "data" / "eval" / "golden_v1.json"
TEI_URL = "http://localhost:8080/embed"
QDRANT_URL = "http://localhost:6333"
DEFAULT_COLLECTION = "framework_code_v1"
TOP_K = 15
QUERY_PREFIX = (
    "Instruct: Given a web search query, retrieve relevant passages that "
    "answer the query\nQuery: "
)

_RELEVANCE_SYSTEM = (
    "You are a strict relevance judge for code documentation retrieval. "
    "Given a question and N numbered candidate chunks from a codebase, "
    "decide which candidates contain the actual answer (implementation, "
    "definition, or substantive explanation). Imports, re-exports, and "
    "marginal mentions are NOT relevant. Return JSON only."
)

_RELEVANCE_USER_TPL = """Question:
{query}

Expected keywords: {keywords}
Expected answer summary: {summary}

Candidate chunks (top-{k}):

{candidates}

Task: return JSON with `relevant_indices` (1-based, 0 to 3 indices),
listing ONLY candidates that contain the actual answer. If none qualify,
return `{{"relevant_indices": []}}`. Imports/re-exports do NOT qualify.

Output format (JSON only, no prose):
{{"relevant_indices": [1, 2]}}
"""


def _embed_query(query: str, http_client: httpx.Client) -> list[float]:
    """Embed query through TEI with Qwen3 instruction prefix."""
    payload = {"inputs": [QUERY_PREFIX + query]}
    resp = http_client.post(TEI_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()[0]


def _retrieve(
    query: str,
    http_client: httpx.Client,
    qclient: QdrantClient,
    collection: str,
) -> list[Any]:
    """Top-K retrieval (single-vector layout, no `using=`)."""
    vec = _embed_query(query, http_client)
    return qclient.query_points(collection_name=collection, query=vec, limit=TOP_K).points


def _format_candidate(idx: int, point: Any) -> str:
    p = point.payload or {}
    # framework_code_v1 uses relative_path / symbol_name / line_start;
    # bsl_code_v4* uses module_path / name / line_start.
    path = p.get("relative_path") or p.get("module_path") or "?"
    line = p.get("line_start", "?")
    name = (
        p.get("symbol_name")
        or p.get("name")
        or p.get("chunk_type")
        or "module"
    )
    content = (p.get("content") or "").strip().replace("\n", " ")
    if len(content) > 240:
        content = content[:240] + "…"
    return f"[{idx}] {path}:{line} :: {name}\n     {content}"


_JSON_FENCE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parse_indices(raw: str, max_idx: int) -> list[int]:
    """Extract `relevant_indices` from LLM output, robust to code fences and prose."""
    text = raw.strip()
    m = _JSON_FENCE.search(text)
    if m:
        text = m.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        return []
    indices = obj.get("relevant_indices") or []
    out: list[int] = []
    for v in indices:
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= max_idx:
            out.append(n)
    seen: set[int] = set()
    uniq: list[int] = []
    for n in out:
        if n not in seen:
            seen.add(n)
            uniq.append(n)
    return uniq[:3]


async def _judge(item: dict, points: list[Any]) -> list[int]:
    """Ask the LLM which candidates truly answer the query. Returns 1-based indices."""
    from src.shared.llm_rotation.adapter import cheap_llm_call

    candidates_block = "\n\n".join(
        _format_candidate(i + 1, pt) for i, pt in enumerate(points)
    )
    user = _RELEVANCE_USER_TPL.format(
        query=item["query"],
        keywords=", ".join(item.get("expected_keywords") or []),
        summary=item.get("expected_answer_summary", ""),
        k=len(points),
        candidates=candidates_block,
    )
    raw = await cheap_llm_call(
        prompt=user,
        system_prompt=_RELEVANCE_SYSTEM,
        component="grounding_judge",
        max_tokens=200,
        temperature=0.0,
    )
    return _parse_indices(raw or "", max_idx=len(points))


def _save(data: Any, path: Path) -> None:
    """Atomic write via tmp + replace."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


async def _run(args: argparse.Namespace) -> int:
    raw = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
    is_wrapped = isinstance(raw, dict) and "items" in raw
    items: list[dict] = raw["items"] if is_wrapped else raw
    id_filter = set(args.ids.split(",")) if args.ids else None
    domain_filter = set(args.domains.split(",")) if args.domains else None

    qclient = QdrantClient(url=QDRANT_URL)
    grounded = 0
    skipped = 0
    failed = 0
    no_relevant = 0

    with httpx.Client() as http:
        for item in items:
            iid = item.get("id", "?")
            if id_filter and iid not in id_filter:
                continue
            if domain_filter and item.get("domain") not in domain_filter:
                continue
            if not args.force and item.get("expected_chunk_ids"):
                skipped += 1
                continue
            try:
                t0 = time.time()
                collection = args.collection or DEFAULT_COLLECTION
                points = _retrieve(item["query"], http, qclient, collection)
                if not points:
                    print(f"[WARN] {iid}: no Qdrant results, skipping", flush=True)
                    failed += 1
                    continue
                indices = await _judge(item, points)
                chunk_ids = [str(points[i - 1].id) for i in indices]
                tag = "OK" if chunk_ids else "EMPTY"
                if not chunk_ids:
                    no_relevant += 1
                print(
                    f"[{tag}] {iid} ({time.time() - t0:.1f}s): "
                    f"{len(chunk_ids)}/{len(points)} relevant → "
                    f"{[c[:8] for c in chunk_ids]}",
                    flush=True,
                )
                if not args.dry_run:
                    item["expected_chunk_ids"] = chunk_ids
                    item["target_collection"] = collection
                    _save(raw, GOLDEN_PATH)
                grounded += 1
            except (httpx.HTTPError, RuntimeError, ValueError) as e:
                print(f"[FAIL] {iid}: {type(e).__name__}: {e}", flush=True)
                failed += 1

    print(
        f"\nDone. grounded={grounded} (of which {no_relevant} empty), "
        f"skipped={skipped}, failed={failed}, path={GOLDEN_PATH}",
        flush=True,
    )
    return 0 if failed == 0 else 1


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--force", action="store_true", help="Re-ground even populated items")
    p.add_argument("--ids", default="", help="Comma-separated subset of item IDs")
    p.add_argument("--domains", default="", help="Comma-separated domains (e.g. 1c,infra)")
    p.add_argument(
        "--collection",
        default="",
        help=f"Qdrant collection (default: {DEFAULT_COLLECTION}). Tested: framework_code_v1, bsl_code_v4_late",
    )
    p.add_argument("--dry-run", action="store_true", help="Print verdicts, don't save")
    args = p.parse_args()

    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    return asyncio.run(_run(args))


if __name__ == "__main__":
    sys.exit(main())
