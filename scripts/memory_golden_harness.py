#!/usr/bin/env python3
"""Section 25 B0 -- memory surfacing golden-set harness.

Measures surfacing quality (hit-rate / precision@k / recall@k / NDCG@k / MRR)
of the memory-first-hook fusion stage against a labelled golden-set, and powers
the offline parameter sweep (B1) and gated promotion (B2).

Architecture -- precompute-then-sweep (AutoRAG-style, roadmap section 2.3/2.4):

  1. CAPTURE (live, needs TEI + Qdrant): for each golden query, run the five
     fusion arms once and store the *raw* per-arm candidates (pre-gating scores +
     effective confidence). This is the only step touching external services.

  2. REPLAY (pure, service-independent): given captured candidates + a config
     (RRF weights, gating thresholds, k), faithfully re-applies the hook's gating
     and rrf_merge to produce the surfaced top-k. Because gating thresholds are
     re-applied here (not baked into capture), a sweep can vary them for free.

The replay re-implements the exact fusion contract of
``.claude/hooks/memory-first-hook.py::search_qdrant`` (the stage whose constants
``surfacing_tuning.json`` tunes). ``rrf_merge`` is a verbatim local copy; a smoke
test asserts it matches the hook (drift guard).

Relevance is labelled by *content hash* -- ``sha1(content[:200])[:16]`` -- which is
the same key rrf_merge dedupes on, so labels align with what actually surfaces.

Usage:
  # capture (writes data/memory/golden/candidates.json)
  python scripts/memory_golden_harness.py capture

  # evaluate current config (reads surfacing_tuning.json) on the held-out split
  python scripts/memory_golden_harness.py evaluate --split heldout --print

Roadmap: docs/roadmap/260601_ROADMAP_MEMORY_EFFECTIVENESS.md (section 5, phase B0).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIR = PROJECT_ROOT / "data" / "memory" / "golden"
GOLDEN_FILE = GOLDEN_DIR / "memory_queries.jsonl"
CANDIDATES_FILE = GOLDEN_DIR / "candidates.json"
TUNING_FILE = PROJECT_ROOT / "data" / "memory" / "surfacing_tuning.json"

# Fixed (non-tuned) fusion constants -- mirror the hook so replay is faithful.
SCORE_THRESHOLD = 0.3   # min lexical token-overlap to keep a learned_patterns hit
LEXICAL_LIMIT = 10      # search_qdrant passes limit=10 to the lexical arm
ARM_KEYS = ("skill", "experience", "conversation", "pattern_dense", "pattern_lexical")

# Default config == current hardcoded hook constants (also the surfacing_tuning.json defaults).
DEFAULT_CONFIG: dict[str, Any] = {
    "surface_rrf_weights": {
        "skill": 0.5,
        "experience": 0.5,
        "conversation": 0.5,
        "pattern_dense": 0.3,
        "pattern_lexical": 0.7,
    },
    "min_surface_conf": 0.15,
    "conf_floor": 0.30,
    "rrf_k": 60,
}


# ---------------------------------------------------------------------------
# Pure fusion contract (verbatim from memory-first-hook.py -- drift-guarded by test)
# ---------------------------------------------------------------------------
def content_hash(content: str) -> str:
    """sha1(content)[:16] -- the rrf_merge dedup key / golden relevance label."""
    return hashlib.sha1(content.encode("utf-8", errors="replace")).hexdigest()[:16]


def rrf_merge(layers: dict, weights: dict, k: int = 60) -> list:
    """Weighted reciprocal-rank fusion, dedup by content hash. Copy of the hook's."""
    scores: dict[str, Any] = {}
    for source, items in layers.items():
        w = weights.get(source, 0.0)
        for rank, item in enumerate(items, start=1):
            chash = content_hash(item["content"])
            rrf = w * (1.0 / (k + rank))
            if chash in scores:
                scores[chash]["fused_score"] += rrf
            else:
                scores[chash] = {"item": item, "fused_score": rrf}
    merged = [{**e["item"], "fused_score": e["fused_score"]} for e in scores.values()]
    merged.sort(key=lambda x: -x["fused_score"])
    return merged


# ---------------------------------------------------------------------------
# Replay -- assemble arms under a config, then fuse (pure, service-independent)
# ---------------------------------------------------------------------------
def assemble_arms(capture: dict[str, Any], config: dict[str, Any]) -> dict[str, list]:
    """Reconstruct the five fusion arms from raw captured candidates + config.

    Mirrors search_qdrant exactly:
      - skill/experience/conversation: dense order preserved, no gating.
      - pattern_dense: capture (Qdrant) order preserved, gated (archived/min_conf);
        rrf uses RANK not score, so order matters, the adjusted score does not.
      - pattern_lexical: gated, floored-multiply adj score, re-sorted desc, top-N.
    """
    min_conf = config["min_surface_conf"]
    conf_floor = config["conf_floor"]
    arms: dict[str, list] = {key: [] for key in ARM_KEYS}

    for arm in ("skill", "experience", "conversation"):
        arms[arm] = [{"content": c["content"]} for c in capture.get(arm, [])]

    for c in capture.get("pattern_dense", []):
        if c.get("archived"):
            continue
        if float(c.get("eff_conf", 0.0)) < min_conf:
            continue
        arms["pattern_dense"].append({"content": c["content"]})

    lexical: list[tuple[float, str]] = []
    for c in capture.get("pattern_lexical", []):
        overlap = float(c.get("overlap", 0.0))
        if overlap < SCORE_THRESHOLD:
            continue
        if c.get("archived"):
            continue
        eff = float(c.get("eff_conf", 0.0))
        if eff < min_conf:
            continue
        adj = overlap * max(conf_floor, eff)
        lexical.append((adj, c["content"]))
    lexical.sort(key=lambda x: -x[0])
    arms["pattern_lexical"] = [{"content": ct} for _, ct in lexical[:LEXICAL_LIMIT]]

    return arms


def surfaced_hashes(capture: dict[str, Any], config: dict[str, Any], k: int) -> list[str]:
    """Top-k surfaced content hashes for a query's captured candidates under config."""
    arms = assemble_arms(capture, config)
    fused = rrf_merge(arms, config["surface_rrf_weights"], config["rrf_k"])
    return [content_hash(item["content"]) for item in fused[:k]]


# ---------------------------------------------------------------------------
# Metrics (pure)
# ---------------------------------------------------------------------------
def _rel_map(row: dict[str, Any]) -> dict[str, int]:
    return {r["hash"]: int(r.get("grade", 1)) for r in row.get("relevant", [])}


def hit_at_k(ranked: list[str], rel: dict[str, int], k: int) -> float:
    return 1.0 if any(h in rel for h in ranked[:k]) else 0.0


def precision_at_k(ranked: list[str], rel: dict[str, int], k: int) -> float:
    if k <= 0:
        return 0.0
    return sum(1 for h in ranked[:k] if h in rel) / k


def recall_at_k(ranked: list[str], rel: dict[str, int], k: int) -> float:
    if not rel:
        return 0.0
    return sum(1 for h in ranked[:k] if h in rel) / len(rel)


def mrr(ranked: list[str], rel: dict[str, int]) -> float:
    for i, h in enumerate(ranked, start=1):
        if h in rel:
            return 1.0 / i
    return 0.0


def ndcg_at_k(ranked: list[str], rel: dict[str, int], k: int) -> float:
    dcg = 0.0
    for i, h in enumerate(ranked[:k]):
        g = rel.get(h, 0)
        if g:
            dcg += g / math.log2(i + 2)
    ideal = sorted(rel.values(), reverse=True)[:k]
    idcg = sum(g / math.log2(i + 2) for i, g in enumerate(ideal))
    return dcg / idcg if idcg else 0.0


def evaluate_config(
    golden: list[dict[str, Any]],
    captures: dict[str, Any],
    config: dict[str, Any],
    k: int = 5,
) -> dict[str, Any]:
    """Aggregate metrics over every golden query that has captured candidates."""
    per_query: list[dict[str, Any]] = []
    for row in golden:
        qid = row["id"]
        cap = captures.get(qid)
        if cap is None:
            continue
        rel = _rel_map(row)
        ranked = surfaced_hashes(cap, config, k)
        per_query.append(
            {
                "id": qid,
                "kind": row.get("kind"),
                "hit": hit_at_k(ranked, rel, k),
                "precision": precision_at_k(ranked, rel, k),
                "recall": recall_at_k(ranked, rel, k),
                "ndcg": ndcg_at_k(ranked, rel, k),
                "mrr": mrr(ranked, rel),
            }
        )

    n = len(per_query)

    def _mean(key: str) -> float:
        return round(sum(q[key] for q in per_query) / n, 4) if n else 0.0

    return {
        "k": k,
        "n_queries": n,
        "hit_rate": _mean("hit"),
        "precision_at_k": _mean("precision"),
        "recall_at_k": _mean("recall"),
        "ndcg_at_k": _mean("ndcg"),
        "mrr": _mean("mrr"),
        "per_query": per_query,
    }


# ---------------------------------------------------------------------------
# I/O
# ---------------------------------------------------------------------------
def load_golden(path: Path = GOLDEN_FILE, split: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except (ValueError, json.JSONDecodeError):
                continue
            if split and obj.get("split") != split:
                continue
            rows.append(obj)
    return rows


def load_captures(path: Path = CANDIDATES_FILE) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("queries", {}) if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def load_tuning_config(path: Path = TUNING_FILE) -> dict[str, Any]:
    """Read the tunable config from surfacing_tuning.json, fall back to defaults."""
    config = json.loads(json.dumps(DEFAULT_CONFIG))  # deep copy
    if not path.exists():
        return config
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return config
    for key in ("min_surface_conf", "conf_floor", "rrf_k"):
        if key in data:
            config[key] = data[key]
    if isinstance(data.get("surface_rrf_weights"), dict):
        config["surface_rrf_weights"].update(data["surface_rrf_weights"])
    return config


# ---------------------------------------------------------------------------
# Capture (live -- needs TEI + Qdrant)
# ---------------------------------------------------------------------------
def _import_live():
    """Import the hook's helpers + shared semantic search (live capture only)."""
    hooks_dir = PROJECT_ROOT / ".claude" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "mfh", str(hooks_dir / "memory-first-hook.py")
    )
    assert spec and spec.loader
    mfh = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mfh)
    from shared.semantic_search import embed_query_tei, search_qdrant_semantic

    return mfh, embed_query_tei, search_qdrant_semantic


def _vector_db_client():
    """Lazy Qdrant client for the lexical-arm scroll (capture only)."""
    from qdrant_client import QdrantClient

    return QdrantClient(host="127.0.0.1", port=6333, timeout=10)


def capture_query(query: str, mfh, embed_fn, search_fn) -> dict[str, Any]:
    """Run the five fusion arms for one query, storing RAW pre-gating candidates."""
    arms: dict[str, Any] = {key: [] for key in ARM_KEYS}
    query_tokens = set(mfh.tokenize(query))

    # Dense arms (TEI + Qdrant). Mirror search_qdrant's collection->arm routing.
    embedding = embed_fn(query, timeout=8.0)
    if embedding:
        for collection, ctype in mfh.SEMANTIC_COLLECTIONS:
            hits = search_fn(collection, embedding, limit=5, timeout=5.0)
            for hit in hits:
                payload = hit.get("payload", {})
                content = mfh._extract_content(payload, ctype)
                if not content:
                    continue
                content = content[:200]
                if ctype == "pattern":
                    arms["pattern_dense"].append(
                        {
                            "content": content,
                            "dense_score": round(hit.get("score", 0.0), 4),
                            "eff_conf": round(mfh._pattern_effective_confidence(payload), 4),
                            "archived": bool(payload.get("expired_at")),
                        }
                    )
                else:
                    arm = {"skill": "skill", "experience": "experience",
                           "conversation": "conversation"}.get(ctype, "skill")
                    arms[arm].append(
                        {"content": content, "dense_score": round(hit.get("score", 0.0), 4)}
                    )

    # Lexical arm -- token overlap over the WHOLE learned_patterns collection,
    # storing every candidate with overlap>0 (replay applies SCORE_THRESHOLD + gating).
    try:
        client = _vector_db_client()
        # limit=100 mirrors the live hook (_search_learned_patterns scrolls 100); capturing
        # more would let replay see lexical candidates the hook never would once the
        # collection exceeds 100 points (no effect at the current 44).
        points, _ = client.scroll(
            collection_name="learned_patterns", limit=100,
            with_payload=True, with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            content = payload.get("content") or payload.get("description") or ""
            if not content:
                continue
            content = content[:200]
            ctoks = set(mfh.tokenize(content))
            overlap = query_tokens & ctoks
            if not overlap:
                continue
            arms["pattern_lexical"].append(
                {
                    "content": content,
                    "overlap": round(len(overlap) / max(len(query_tokens), 1), 4),
                    "eff_conf": round(mfh._pattern_effective_confidence(payload), 4),
                    "archived": bool(payload.get("expired_at")),
                }
            )
    except Exception as exc:  # noqa: BLE001 -- fail-soft, capture is best-effort
        arms["_lexical_error"] = f"{type(exc).__name__}: {exc}"[:160]

    return arms


def capture_all(golden: list[dict[str, Any]], stamp: str) -> dict[str, Any]:
    mfh, embed_fn, search_fn = _import_live()
    queries: dict[str, Any] = {}
    for row in golden:
        queries[row["id"]] = capture_query(row["query"], mfh, embed_fn, search_fn)
    return {"captured_at": stamp, "n": len(queries), "queries": queries}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _render_eval(report: dict[str, Any], label: str) -> str:
    lines = [
        f"# Memory Golden Harness -- {label}",
        "",
        f"- queries scored: **{report['n_queries']}** (k={report['k']})",
        f"- hit_rate@k:    **{report['hit_rate']:.3f}**",
        f"- precision@k:   **{report['precision_at_k']:.3f}**",
        f"- recall@k:      **{report['recall_at_k']:.3f}**",
        f"- NDCG@k:        **{report['ndcg_at_k']:.3f}**",
        f"- MRR:           **{report['mrr']:.3f}**",
    ]
    misses = [q["id"] for q in report["per_query"] if not q["hit"]]
    if misses:
        lines.append(f"- misses ({len(misses)}): {', '.join(misses)}")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="section 25 memory golden-set harness")
    sub = ap.add_subparsers(dest="cmd", required=True)

    cap = sub.add_parser("capture", help="run arms live + persist raw candidates")
    cap.add_argument("--split", default=None)
    cap.add_argument("--out", default=str(CANDIDATES_FILE))
    cap.add_argument("--stamp", default="unstamped")

    ev = sub.add_parser("evaluate", help="score a config against captured candidates")
    ev.add_argument("--split", default=None, help="train | heldout (default: all)")
    ev.add_argument("--k", type=int, default=5)
    ev.add_argument("--captures", default=str(CANDIDATES_FILE))
    ev.add_argument("--default-config", action="store_true",
                    help="use built-in defaults instead of surfacing_tuning.json")
    ev.add_argument("--print", action="store_true")

    args = ap.parse_args()

    if args.cmd == "capture":
        golden = load_golden(split=args.split)
        if not golden:
            print("No golden queries found.", file=sys.stderr)
            return 1
        bundle = capture_all(golden, args.stamp)
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(
            json.dumps(bundle, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        arms_nonempty = sum(
            1 for q in bundle["queries"].values()
            if any(q.get(a) for a in ARM_KEYS)
        )
        print(f"Captured {bundle['n']} queries ({arms_nonempty} with >=1 arm) -> {args.out}")
        return 0

    if args.cmd == "evaluate":
        golden = load_golden(split=args.split)
        captures = load_captures(Path(args.captures))
        config = DEFAULT_CONFIG if args.default_config else load_tuning_config()
        report = evaluate_config(golden, captures, config, k=args.k)
        label = f"split={args.split or 'all'} config={'default' if args.default_config else 'tuning.json'}"
        print(_render_eval(report, label))
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
