#!/usr/bin/env python3
"""
trigger-reglament.py — Universal 1C scheduled-job trigger via JSON-RPC.

Loads job definitions from `tools/vanessa/jobs/*.yaml` and executes the
configured BSL through the 1C HTTP service `execute_code` tool. Any number of
jobs can be defined without touching this script: drop a new YAML into jobs/
with `name`, `description`, and `bsl` fields.

Kept as a standalone Python script because PowerShell on Windows corrupts
Cyrillic payloads when marshalling through `ConvertTo-Json` or `-c`.

Usage:
    python trigger-reglament.py                          # default job
    python trigger-reglament.py --job table_update       # specific YAML
    python trigger-reglament.py --bsl "Процедура();"     # raw BSL
    python trigger-reglament.py --list                   # list jobs
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx
import yaml

DEFAULT_RPC_URL = os.environ.get("ONEC_RPC_URL", "http://localhost/TestDB/hs/mcp/rpc")
DEFAULT_USERNAME = os.environ.get("ONEC_USERNAME", "a.terletskiy@sodru.com")
DEFAULT_PASSWORD = os.environ.get("ONEC_PASSWORD", "")
DEFAULT_JOB = "table_update"

JOBS_DIR = Path(__file__).resolve().parent / "jobs"


def load_job(job_name: str) -> dict:
    """Load a job definition from jobs/<job_name>.yaml."""
    job_path = JOBS_DIR / f"{job_name}.yaml"
    if not job_path.exists():
        raise FileNotFoundError(
            f"Job not found: {job_path}\n"
            f"Available jobs: {', '.join(p.stem for p in sorted(JOBS_DIR.glob('*.yaml')))}"
        )
    with open(job_path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict) or "bsl" not in data:
        raise ValueError(f"Invalid job file (missing 'bsl' field): {job_path}")
    return data


def list_jobs() -> int:
    """Print all available jobs and exit 0."""
    if not JOBS_DIR.is_dir():
        print(f"[ERROR] Jobs directory not found: {JOBS_DIR}", file=sys.stderr)
        return 2
    print(f"Available jobs in {JOBS_DIR}:")
    for yaml_path in sorted(JOBS_DIR.glob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            name = data.get("name", "?")
            desc = data.get("description", "")
            print(f"  {yaml_path.stem:<20s} {name} — {desc}")
        except yaml.YAMLError as exc:
            print(f"  {yaml_path.stem:<20s} [PARSE ERROR: {exc}]")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Universal 1C scheduled-job trigger via JSON-RPC"
    )
    parser.add_argument(
        "--job",
        default=DEFAULT_JOB,
        help=f"Job name to load from jobs/<name>.yaml (default: {DEFAULT_JOB})",
    )
    parser.add_argument(
        "--bsl",
        default=None,
        help="Raw BSL code to execute (overrides --job)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available jobs and exit",
    )
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument("--user", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    if args.list:
        return list_jobs()

    # Resolve BSL: explicit --bsl wins, else load job YAML
    bsl_code: str
    job_label: str
    if args.bsl:
        bsl_code = args.bsl
        job_label = "<inline-bsl>"
    else:
        try:
            job = load_job(args.job)
        except (FileNotFoundError, ValueError) as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            return 2
        bsl_code = job["bsl"]
        job_label = job.get("name", args.job)

    # Normalise multi-line BSL: collapse newlines to spaces so the 1C
    # execute_code tool parses it as a single statement sequence.
    bsl_code = " ".join(line.strip() for line in bsl_code.strip().splitlines() if line.strip())

    print(f"[trigger-reglament] POST {args.rpc_url} — job: {job_label}", flush=True)

    rpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "execute_code",
            "arguments": {"code": bsl_code},
        },
    }

    started = time.perf_counter()
    try:
        response = httpx.post(
            args.rpc_url,
            auth=(args.user, args.password),
            json=rpc_request,
            timeout=args.timeout,
        )
    except httpx.ConnectError as exc:
        print(f"[ERROR] Cannot reach 1C HTTP service: {exc}", file=sys.stderr)
        return 2
    except httpx.HTTPError as exc:
        print(f"[ERROR] HTTP error: {exc}", file=sys.stderr)
        return 2

    if response.status_code != 200:
        print(
            f"[ERROR] HTTP {response.status_code}: {response.text[:200]}",
            file=sys.stderr,
        )
        return 2

    envelope = response.json()

    if "error" in envelope:
        err = envelope["error"]
        print(f"[FAIL] JSON-RPC {err.get('code')}: {err.get('message')}")
        return 1

    content = (envelope.get("result") or {}).get("content") or []
    if not content:
        print("[FAIL] Empty result from 1C tool")
        return 1

    inner_text = content[0].get("text", "")
    try:
        inner = json.loads(inner_text)
    except json.JSONDecodeError:
        print(f"[FAIL] Cannot parse inner payload: {inner_text[:200]}")
        return 1

    elapsed = round(time.perf_counter() - started, 1)

    if isinstance(inner, dict) and inner.get("success"):
        print(f"[OK] job '{job_label}' выполнен за {elapsed} сек")
        return 0

    error_msg = (
        inner.get("error", "неизвестная ошибка")
        if isinstance(inner, dict)
        else "unexpected payload"
    )
    print(f"[FAIL] {error_msg}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
