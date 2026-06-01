#!/usr/bin/env python3
"""View the content of `learned_patterns` (or any pattern collection), readably.

Scroll-based (no embedding, no TEI cold-start) dump of pattern content with
filters by type / effective-confidence / text. Writes a Markdown report by
default (UTF-8) rather than stdout, because Cyrillic content crashes on a
Windows cp1251 console pipe (UnicodeEncodeError) — see memory
feedback_windows_hook_stdout_cp1251. A compact ASCII summary still prints to
stdout so the run is observable.

Usage:
  python scripts/view_learned_patterns.py                       # all -> report file
  python scripts/view_learned_patterns.py --type code-convention
  python scripts/view_learned_patterns.py --grep rrf --full
  python scripts/view_learned_patterns.py --min-confidence 0.6
  python scripts/view_learned_patterns.py --stdout              # print (ASCII-escaped)

Companion to scripts/dedupe_learned_patterns.py. MCP equivalent: the
`list_patterns` tool on the vector-memory server (same filters).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_COLLECTION = "learned_patterns"
DEFAULT_OUT = PROJECT_ROOT / "data" / "reports" / "memory" / "learned_patterns_view.md"


def pattern_content(payload: dict[str, Any]) -> str:
    return payload.get("content") or payload.get("description") or ""


def pattern_type(payload: dict[str, Any]) -> str:
    return payload.get("pattern_type") or payload.get("category") or "?"


def effective_confidence(payload: dict[str, Any]) -> float | None:
    """§22 lazy decay-on-read effective confidence; fall back to stored / None."""
    try:
        src = str(PROJECT_ROOT / "src")
        if src not in sys.path:
            sys.path.insert(0, src)
        from memory.vector_memory.confidence import payload_effective_confidence

        return float(payload_effective_confidence(payload))
    except Exception:
        c = payload.get("confidence")
        return float(c) if isinstance(c, (int, float)) else None


def matches(
    payload: dict[str, Any],
    *,
    type_filter: str | None,
    min_conf: float,
    grep: str | None,
) -> bool:
    if type_filter and pattern_type(payload) != type_filter:
        return False
    if grep and grep.lower() not in pattern_content(payload).lower():
        return False
    if min_conf > 0.0:
        eff = effective_confidence(payload)
        if eff is None or eff < min_conf:
            return False
    return True


def build_rows(points: list[Any], *, type_filter, min_conf, grep) -> list[dict[str, Any]]:
    rows = []
    for p in points:
        pl = p.payload or {}
        if not matches(pl, type_filter=type_filter, min_conf=min_conf, grep=grep):
            continue
        rows.append(
            {
                "id": str(p.id),
                "type": pattern_type(pl),
                "confidence": pl.get("confidence"),
                "effective_confidence": effective_confidence(pl),
                "application_count": pl.get("application_count"),
                "created_at": pl.get("created_at", ""),
                "archived": bool(pl.get("expired_at")),
                "content": pattern_content(pl),
            }
        )
    rows.sort(key=lambda r: r["created_at"])
    return rows


def render(rows: list[dict[str, Any]], total: int, *, full: bool, label: str) -> str:
    lines = [
        f"# learned_patterns — {len(rows)} / {total} паттернов  ({label})",
        "",
    ]
    for i, r in enumerate(rows, 1):
        eff = r["effective_confidence"]
        eff_s = f"{eff:.3f}" if isinstance(eff, float) else "—"
        flag = " [ARCHIVED]" if r["archived"] else ""
        lines.append(
            f"## {i}. [{r['type']}] eff_conf={eff_s} appc={r['application_count']} "
            f"id={r['id'][:8]}{flag}"
        )
        body = r["content"] if full else r["content"][:300]
        if not full and len(r["content"]) > 300:
            body += " …"
        lines.append(body)
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description="readable dump of learned_patterns content")
    ap.add_argument("--collection", default=DEFAULT_COLLECTION)
    ap.add_argument("--type", dest="type_filter", default=None, help="exact pattern_type/category")
    ap.add_argument("--min-confidence", type=float, default=0.0, help="min effective confidence")
    ap.add_argument("--grep", default=None, help="case-insensitive substring in content")
    ap.add_argument("--limit", type=int, default=1000)
    ap.add_argument("--full", action="store_true", help="full content (default: 300-char preview)")
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    ap.add_argument("--stdout", action="store_true", help="write to stdout as UTF-8 bytes")
    args = ap.parse_args()

    try:
        from qdrant_client import QdrantClient

        client = QdrantClient(host="127.0.0.1", port=6333, timeout=30)
        points, _ = client.scroll(
            collection_name=args.collection, limit=args.limit,
            with_payload=True, with_vectors=False,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"Qdrant unavailable ({args.collection}): {exc}", file=sys.stderr)
        return 1

    rows = build_rows(
        points, type_filter=args.type_filter, min_conf=args.min_confidence, grep=args.grep
    )
    label = (
        f"type={args.type_filter or 'all'} min_conf={args.min_confidence} "
        f"grep={args.grep or '-'} {'full' if args.full else 'preview'}"
    )
    md = render(rows, len(points), full=args.full, label=label)

    if args.stdout:
        # Write raw UTF-8 bytes via the buffer to survive a cp1251 console pipe on
        # Windows (print() would raise UnicodeEncodeError on Cyrillic content).
        sys.stdout.buffer.write(md.encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
        return 0

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    print(f"{len(rows)}/{len(points)} patterns -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
