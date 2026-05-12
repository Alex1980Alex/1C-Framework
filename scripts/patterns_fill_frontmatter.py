"""Fill missing unified_id (UUID v7) and confidence (0.5 default) in patterns/*.md.

Closes kb-lint errors:
- 'Empty required field: unified_id has no value' (28 occurrences)
- 'Empty required field: confidence has no value' (~24 occurrences)

Source: RFC 9562 §5.7 (UUID v7 bit layout — Python 3.13 stdlib has no
`uuid.uuid7()` yet, so implement manually):
  - 48 bits: unix timestamp in milliseconds (most significant)
  - 4 bits:  version (0b0111)
  - 12 bits: rand_a
  - 2 bits:  variant (0b10)
  - 62 bits: rand_b

Source: python-frontmatter PyPI (load() returns Post, dump() writes back).

Confidence default 0.5 = "unverified, written by automation" per
docs/wiki/SCHEMA.md allowed levels (high/medium/low → 0.9/0.6/0.3 by
convention; 0.5 lands between low and medium for "needs manual review").
"""
from __future__ import annotations

import secrets
import time
import uuid
from pathlib import Path

import frontmatter


def uuid7() -> uuid.UUID:
    """Generate a UUID version 7 (RFC 9562 §5.7)."""
    ts_ms = int(time.time() * 1000) & ((1 << 48) - 1)
    rand_a = secrets.randbits(12)
    rand_b = secrets.randbits(62)
    value = ts_ms << 80
    value |= 0x7 << 76          # version 7
    value |= rand_a << 64
    value |= 0b10 << 62         # variant RFC 4122
    value |= rand_b
    return uuid.UUID(int=value)


def main() -> int:
    patterns_dir = Path("docs/wiki/patterns")
    if not patterns_dir.is_dir():
        print(f"ERROR: {patterns_dir} not found (run from repo root)")
        return 2

    changed = 0
    skipped = 0
    for md in sorted(patterns_dir.glob("*.md")):
        post = frontmatter.load(md)
        fm = post.metadata
        before = dict(fm)
        if not fm.get("unified_id"):
            fm["unified_id"] = str(uuid7())
        if fm.get("confidence") is None:
            fm["confidence"] = 0.5
        if fm == before:
            skipped += 1
            continue
        with open(md, "wb") as f:
            frontmatter.dump(post, f)
        changed += 1
        print(f"  fixed: {md.name}")

    print(f"\nDone: {changed} files modified, {skipped} already complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
