#!/usr/bin/env python3
"""Adaptive 3-tier retention orchestrator (§15 P3 item 14).

Ties together the P0/P1 caching primitives into a single hot/warm/cold
retention policy, closing the §15 "Process Caching" lifecycle loop:

    HOT  (0 .. HOT_DAYS=7d)        live  data/hook-invocations.jsonl
                                    fully readable, queryable by DuckDB.
    WARM (HOT_DAYS .. WARM_DAYS=90d) dated Parquet archives in data/archive/
                                    ZSTD-compressed, queryable via read_parquet().
    COLD (> WARM_DAYS .. ∞)         Parquets retained forever, but the per-session
                                    AES keys are GC'd → encrypted PII (`error_enc`)
                                    becomes permanently unreadable (GDPR erasure,
                                    §15.2 item 7 crypto-shredding). Cold = ∞ retention.

This is an *orchestrator*, not a reimplementation: the actual archival is
delegated to `archive_jsonl_to_parquet.cmd_archive` and the key erasure to
`shared.session_keys.gc_old_keys`. Net-new value = tier-state reporting +
threshold-driven transition decisions + a safe dry-run plan.

Actions per run (idempotent):
  1. hot→warm: if the live JSONL exceeds the hot tier (size >= HOT_MAX_MB *or*
     oldest entry age >= HOT_DAYS) → archive + rotate (fresh JSONL tomorrow).
  2. cold crypto-shred: delete session keys older than WARM_DAYS. Parquets are
     never deleted (cold tier = ∞ retention by design).

CLI:
    python scripts/retention_policy.py             # dry-run: status + plan (SAFE default)
    python scripts/retention_policy.py --apply      # execute transitions + shred
    python scripts/retention_policy.py --status      # tier report only, no plan
    python scripts/retention_policy.py --hot-days 7 --warm-days 90 --hot-max-mb 50

Env overrides: RETENTION_HOT_DAYS (7), RETENTION_WARM_DAYS (90),
RETENTION_HOT_MAX_MB (50).

Why default dry-run: cold-tier shredding is irreversible. `--apply` is opt-in.

Per roadmap 260523 §15.6 P3 item 14. Items 12 (Vector.dev) + 13 (Grafana Tempo)
remain deferred — gated behind LGTM migration / jsonl growth >5GB (§15.4 P1);
current jsonl ~2MB makes them premature.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except (AttributeError, OSError):
    pass

PROJECT_ROOT = Path(__file__).resolve().parent.parent
JSONL_PATH = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
ARCHIVE_DIR = PROJECT_ROOT / "data" / "archive"

DEFAULT_HOT_DAYS = 7
DEFAULT_WARM_DAYS = 90
DEFAULT_HOT_MAX_MB = 50

# Timestamp fields seen across CloudEvents envelope + legacy flat entries.
_TS_KEYS = ("time", "timestamp", "ts", "datetime")


@dataclass
class RetentionConfig:
    """Tier thresholds. Read from env via `from_env`, overridable by CLI."""

    hot_days: int = DEFAULT_HOT_DAYS
    warm_days: int = DEFAULT_WARM_DAYS
    hot_max_mb: float = DEFAULT_HOT_MAX_MB

    @classmethod
    def from_env(cls) -> RetentionConfig:
        def _int(name: str, default: int) -> int:
            try:
                return int(os.environ.get(name, default))
            except (ValueError, TypeError):
                return default

        def _float(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, default))
            except (ValueError, TypeError):
                return default

        return cls(
            hot_days=_int("RETENTION_HOT_DAYS", DEFAULT_HOT_DAYS),
            warm_days=_int("RETENTION_WARM_DAYS", DEFAULT_WARM_DAYS),
            hot_max_mb=_float("RETENTION_HOT_MAX_MB", DEFAULT_HOT_MAX_MB),
        )


def _parse_ts(value: object) -> dt.datetime | None:
    """Best-effort parse of an entry timestamp into a naive local datetime."""
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.fromtimestamp(float(value))
        except (ValueError, OSError, OverflowError):
            return None
    if isinstance(value, str) and value:
        s = value.strip().replace("Z", "+00:00")
        try:
            parsed = dt.datetime.fromisoformat(s)
        except ValueError:
            return None
        # Normalise tz-aware → naive local for uniform age math.
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone().replace(tzinfo=None)
        return parsed
    return None


def _oldest_entry_age_days(path: Path, now: dt.datetime | None = None) -> float | None:
    """Age (days) of the first valid entry's timestamp. None if undeterminable.

    Reads only the first non-empty valid JSON line — the JSONL is append-only,
    so the first line is the oldest. Falls back to file mtime if no parseable
    timestamp field is present.
    """
    now = now or dt.datetime.now()
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except (ValueError, json.JSONDecodeError):
                    continue
                if not isinstance(obj, dict):
                    break
                for key in _TS_KEYS:
                    if key in obj:
                        parsed = _parse_ts(obj[key])
                        if parsed is not None:
                            return max(0.0, (now - parsed).total_seconds() / 86400.0)
                break  # first valid line had no usable timestamp → fall through
    except OSError:
        return None
    # Fallback: file mtime age.
    try:
        mtime = dt.datetime.fromtimestamp(path.stat().st_mtime)
        return max(0.0, (now - mtime).total_seconds() / 86400.0)
    except OSError:
        return None


def jsonl_stats(path: Path = JSONL_PATH, now: dt.datetime | None = None) -> dict[str, Any]:
    """HOT tier snapshot: existence, size, line count, oldest entry age."""
    if not path.exists():
        return {
            "exists": False,
            "size_bytes": 0,
            "size_mb": 0.0,
            "lines": 0,
            "oldest_age_days": None,
        }
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    lines = 0
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for line in f:
                if line.strip():
                    lines += 1
    except OSError:
        pass
    return {
        "exists": True,
        "size_bytes": size,
        "size_mb": round(size / 1024 / 1024, 3),
        "lines": lines,
        "oldest_age_days": _oldest_entry_age_days(path, now=now),
    }


def parquet_stats(
    archive_dir: Path = ARCHIVE_DIR, now: dt.datetime | None = None
) -> dict[str, Any]:
    """WARM/COLD tier snapshot: parquet count, total size, age range."""
    now = now or dt.datetime.now()
    if not archive_dir.exists():
        return {"count": 0, "total_bytes": 0, "min_age_days": None, "max_age_days": None}
    count = 0
    total = 0
    ages: list[float] = []
    try:
        for p in archive_dir.iterdir():
            if not p.is_file() or p.suffix != ".parquet":
                continue
            try:
                st = p.stat()
            except OSError:
                continue
            count += 1
            total += st.st_size
            ages.append(max(0.0, (now.timestamp() - st.st_mtime) / 86400.0))
    except OSError:
        pass
    return {
        "count": count,
        "total_bytes": total,
        "min_age_days": round(min(ages), 1) if ages else None,
        "max_age_days": round(max(ages), 1) if ages else None,
    }


def key_stats(
    cfg: RetentionConfig,
    list_keys_fn: Callable[[], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """COLD tier key snapshot. `list_keys_fn` injectable for tests.

    Returns total key count and how many exceed the warm window (shred
    candidates). Degrades to zeros if session_keys is unavailable.

    Comparison is `>=` (not `>`) on purpose: `list_keys()` truncates
    `age_days` to whole days, while the actual `gc_old_keys(warm_days)`
    deletes on sub-day (seconds) resolution. Using `>=` guarantees the
    dry-run preview never *under-reports* what `--apply` will erase (it may
    over-estimate by at most the keys sitting exactly on the day boundary) —
    the safe direction for an irreversible operation.
    """
    if list_keys_fn is None:
        list_keys_fn = _import_list_keys()
    if list_keys_fn is None:
        return {"available": False, "total": 0, "shred_candidates": 0}
    try:
        keys = list_keys_fn()
    except Exception:  # noqa: BLE001 — best-effort introspection, never block
        return {"available": False, "total": 0, "shred_candidates": 0}
    candidates = sum(1 for k in keys if k.get("age_days", 0) >= cfg.warm_days)
    return {"available": True, "total": len(keys), "shred_candidates": candidates}


def build_plan(
    jstats: dict[str, Any], kstats: dict[str, Any], cfg: RetentionConfig
) -> dict[str, Any]:
    """Pure decision: given tier stats + thresholds → actions to take.

    hot→warm fires if JSONL size >= hot_max_mb OR oldest entry age >= hot_days.
    cold shred count = keys older than warm_days.
    """
    reasons: list[str] = []
    if jstats.get("exists"):
        size_mb = jstats.get("size_mb", 0.0)
        if size_mb >= cfg.hot_max_mb:
            reasons.append(f"size {size_mb}MB >= {cfg.hot_max_mb}MB")
        age = jstats.get("oldest_age_days")
        if age is not None and age >= cfg.hot_days:
            reasons.append(f"oldest entry {age:.1f}d >= {cfg.hot_days}d")
    return {
        "hot_to_warm": bool(reasons),
        "hot_to_warm_reasons": reasons,
        "cold_shred_keys": kstats.get("shred_candidates", 0),
    }


def _load_session_keys() -> Any:
    """Lazy cross-tree import of the session_keys module (.claude/hooks/shared).

    Uses importlib so mypy does not statically resolve the out-of-tree module.
    Returns the module or None if unavailable.
    """
    hooks_dir = PROJECT_ROOT / ".claude" / "hooks"
    if str(hooks_dir) not in sys.path:
        sys.path.insert(0, str(hooks_dir))
    try:
        import importlib  # noqa: PLC0415

        return importlib.import_module("shared.session_keys")
    except Exception:  # noqa: BLE001 — optional dependency, degrade gracefully
        return None


def _import_list_keys() -> Callable[[], list[dict[str, Any]]] | None:
    """Resolve session_keys.list_keys, or None if module unavailable."""
    mod = _load_session_keys()
    if mod is None:
        return None
    return cast("Callable[[], list[dict[str, Any]]]", mod.list_keys)


def _import_gc_old_keys() -> Callable[[int], int] | None:
    """Resolve session_keys.gc_old_keys, or None if module unavailable."""
    mod = _load_session_keys()
    if mod is None:
        return None
    return cast("Callable[[int], int]", mod.gc_old_keys)


def _print_status(
    jstats: dict[str, Any],
    pstats: dict[str, Any],
    kstats: dict[str, Any],
    cfg: RetentionConfig,
) -> None:
    print("=== Adaptive Retention — tier status ===")
    print(f"Config: hot<{cfg.hot_days}d  warm<{cfg.warm_days}d  hot_max={cfg.hot_max_mb}MB\n")
    age = jstats.get("oldest_age_days")
    age_s = f"{age:.1f}d" if age is not None else "n/a"
    print("HOT  (live jsonl):")
    print(
        f"  exists={jstats['exists']}  size={jstats['size_mb']}MB  "
        f"lines={jstats['lines']}  oldest={age_s}"
    )
    print("WARM/COLD (parquet archives):")
    print(
        f"  count={pstats['count']}  total={pstats['total_bytes']:,}B  "
        f"age {pstats['min_age_days']}..{pstats['max_age_days']}d"
    )
    print("COLD keys (crypto-shred):")
    if kstats.get("available"):
        print(
            f"  total={kstats['total']}  "
            f"shred_candidates(>{cfg.warm_days}d)={kstats['shred_candidates']}"
        )
    else:
        print("  session_keys unavailable (no keys dir or import failed)")
    print()


def cmd_run(apply: bool, status_only: bool, cfg: RetentionConfig) -> int:
    """Report tiers, build plan, and (if --apply) execute transitions."""
    jstats = jsonl_stats()
    pstats = parquet_stats()
    kstats = key_stats(cfg)
    _print_status(jstats, pstats, kstats, cfg)

    if status_only:
        return 0

    plan = build_plan(jstats, kstats, cfg)
    print("=== Plan ===")
    if plan["hot_to_warm"]:
        print(f"  hot→warm: archive + rotate jsonl  ({'; '.join(plan['hot_to_warm_reasons'])})")
    else:
        print("  hot→warm: skip (within hot tier)")
    print(f"  cold shred: {plan['cold_shred_keys']} session key(s) older than {cfg.warm_days}d")
    print()

    if not apply:
        print("(dry-run — pass --apply to execute)")
        return 0

    rc = 0
    # 1. hot→warm transition
    if plan["hot_to_warm"]:
        scripts_dir = str(PROJECT_ROOT / "scripts")
        if scripts_dir not in sys.path:
            sys.path.insert(0, scripts_dir)
        try:
            from archive_jsonl_to_parquet import cmd_archive  # noqa: PLC0415

            print("Executing hot→warm archive (rotate=True)...")
            arc_rc = cmd_archive(rotate=True, dry_run=False)
            if arc_rc != 0:
                print(f"  archive returned {arc_rc} (non-fatal)", file=sys.stderr)
                rc = rc or arc_rc
        except Exception as e:  # noqa: BLE001 — archive failure must not block shred
            print(f"  archive step failed: {e}", file=sys.stderr)
            rc = rc or 1

    # 2. cold crypto-shred
    if plan["cold_shred_keys"] > 0:
        gc = _import_gc_old_keys()
        if gc is None:
            print("  cold shred: session_keys unavailable, skipped", file=sys.stderr)
        else:
            deleted = gc(cfg.warm_days)
            print(f"Cold shred: deleted {deleted} session key(s) older than {cfg.warm_days}d.")
    else:
        print("Cold shred: nothing to erase.")

    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply", action="store_true", help="Execute transitions (default: dry-run)"
    )
    parser.add_argument("--status", action="store_true", help="Tier report only, skip plan")
    parser.add_argument(
        "--hot-days", type=int, help=f"Hot tier window (default {DEFAULT_HOT_DAYS})"
    )
    parser.add_argument(
        "--warm-days", type=int, help=f"Warm tier window (default {DEFAULT_WARM_DAYS})"
    )
    parser.add_argument(
        "--hot-max-mb", type=float, help=f"Hot size trigger MB (default {DEFAULT_HOT_MAX_MB})"
    )
    args = parser.parse_args()

    cfg = RetentionConfig.from_env()
    if args.hot_days is not None:
        cfg.hot_days = args.hot_days
    if args.warm_days is not None:
        cfg.warm_days = args.warm_days
    if args.hot_max_mb is not None:
        cfg.hot_max_mb = args.hot_max_mb

    return cmd_run(apply=args.apply, status_only=args.status, cfg=cfg)


if __name__ == "__main__":
    sys.exit(main())
