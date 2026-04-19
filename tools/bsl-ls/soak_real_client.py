"""R1.3 Phase B soak test — RealBSLClient against 2027 .bsl files.

DoD: open 2027 BSL files in <60s without OOM via the production sync client.

Usage:
    python tools/bsl-ls/soak_real_client.py

Writes:
    tools/bsl-ls/soak-logs/summary.json — metrics (timings, memory)
    tools/bsl-ls/soak-logs/run.log      — stderr trace
"""

from __future__ import annotations

import json
import os
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]

# Make `src.bsl...` importable when run outside pytest.
sys.path.insert(0, str(REPO_ROOT))

import psutil  # noqa: E402

from src.bsl.semantic_search.refactor.backends.real_bsl_client import (  # noqa: E402
    RealBSLClient,
)

PROJECT_ROOT = (
    REPO_ROOT
    / "src"
    / "projects"
    / "configuration"
    / "260304_GKSTCPLK-2182 Доработать создание Направление на разгрузку для заблокированных ТС"
    / "src"
)
JAR = HERE / "bsl-language-server.jar"
LOGDIR = HERE / "soak-logs"
LOGDIR.mkdir(exist_ok=True)

# DoD thresholds
DOD_MAX_OPEN_SECS = 60.0
DOD_MAX_RSS_MB = 4096  # 4 GB soft ceiling — OOM check


def _rss_mb() -> float:
    """Resident set size of this Python process in MiB."""
    return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)


def main() -> int:
    if not PROJECT_ROOT.exists():
        print(f"FAIL: project not found: {PROJECT_ROOT}")
        return 2
    if not JAR.exists():
        print(f"FAIL: JAR not found: {JAR}")
        return 2

    bsl_files = sorted(PROJECT_ROOT.rglob("*.bsl"))
    print(f"=== R1.3 Phase B Soak ===")
    print(f"Workspace: {PROJECT_ROOT}")
    print(f"BSL files: {len(bsl_files)}")

    metrics: dict = {
        "file_count": len(bsl_files),
        "python_version": sys.version.split()[0],
        "dod_max_open_secs": DOD_MAX_OPEN_SECS,
        "dod_max_rss_mb": DOD_MAX_RSS_MB,
    }

    rss_before = _rss_mb()
    metrics["rss_before_start_mb"] = round(rss_before, 1)
    print(f"RSS before start: {rss_before:.1f} MB")

    tracemalloc.start()
    client = RealBSLClient(
        workspace_root=PROJECT_ROOT,
        jar_path=JAR,
        start_timeout=90.0,
        request_timeout=60.0,
    )

    try:
        t0 = time.perf_counter()
        client.start()
        metrics["start_ms"] = round((time.perf_counter() - t0) * 1000, 1)
        print(f"Client started in {metrics['start_ms']} ms")

        rss_after_start = _rss_mb()
        metrics["rss_after_start_mb"] = round(rss_after_start, 1)
        print(f"RSS after start: {rss_after_start:.1f} MB (+{rss_after_start - rss_before:+.1f})")

        # The DoD metric
        t1 = time.perf_counter()
        open_metrics = client.open_workspace(
            bsl_files, throttle_fps=400.0, batch_size=50
        )
        open_secs = time.perf_counter() - t1
        metrics["open_secs"] = round(open_secs, 2)
        metrics["open_workspace"] = open_metrics
        print(
            f"Bulk open: {open_metrics['opened']} files in {open_secs:.2f}s "
            f"({open_metrics['files_per_sec']} files/s)"
        )

        rss_after_open = _rss_mb()
        metrics["rss_after_open_mb"] = round(rss_after_open, 1)
        print(
            f"RSS after open: {rss_after_open:.1f} MB "
            f"(+{rss_after_open - rss_after_start:+.1f} from start)"
        )

        current, peak = tracemalloc.get_traced_memory()
        metrics["tracemalloc_current_mb"] = round(current / (1024 * 1024), 1)
        metrics["tracemalloc_peak_mb"] = round(peak / (1024 * 1024), 1)
        tracemalloc.stop()

        # DoD evaluation
        dod_time_ok = open_secs < DOD_MAX_OPEN_SECS
        dod_oom_ok = rss_after_open < DOD_MAX_RSS_MB
        dod_opened_ok = open_metrics["opened"] == len(bsl_files)
        metrics["dod_time_ok"] = dod_time_ok
        metrics["dod_oom_ok"] = dod_oom_ok
        metrics["dod_opened_all_files"] = dod_opened_ok
        metrics["dod_pass"] = dod_time_ok and dod_oom_ok and dod_opened_ok

        print(f"\n=== DoD ===")
        print(f"  open_secs < {DOD_MAX_OPEN_SECS:.0f}:  {dod_time_ok}  ({open_secs:.2f}s)")
        print(f"  rss < {DOD_MAX_RSS_MB} MB:          {dod_oom_ok}  ({rss_after_open:.1f} MB)")
        print(f"  all files opened:             {dod_opened_ok}  ({open_metrics['opened']}/{len(bsl_files)})")
        print(f"  OVERALL:                      {'PASS' if metrics['dod_pass'] else 'FAIL'}")

    except Exception as exc:
        metrics["error"] = f"{type(exc).__name__}: {exc}"
        print(f"ERROR: {metrics['error']}")
        return 1
    finally:
        try:
            client.stop()
        except Exception:
            pass
        summary_path = LOGDIR / "summary.json"
        summary_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nWrote {summary_path}")

    return 0 if metrics.get("dod_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
