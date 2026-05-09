#!/usr/bin/env python3
"""Smoke-test для post-BP-fire handshake pipeline (roadmap §13 P3.2).

Проверяет интеграцию `mcp_debug_server.py` (RDBGClient) с running 1С debug
agent (`dbgs.exe` на :1550). Без 1С даёт экологичный exit_code=2 + сообщение.

Режимы:
  --probe-only     — только TCP probe :1550 + RDBGClient.attach() + ping (~3 сек)
  --full           — полный цикл: connect → set_breakpoint → wait → eval → step
                     (требует РУЧНОГО запуска сценария в 1С, который зайдёт в BP)

Exit codes:
  0 — pipeline healthy (probe или full passed)
  1 — degraded (1С запущена, но handshake/BP-fire не отработал)
  2 — 1С не запущена / dbgs.exe недоступен на :1550

Usage:
  python scripts/smoke_test_debug_pipeline.py --probe-only
  python scripts/smoke_test_debug_pipeline.py --full \\
      --infobase TestDB \\
      --object-id 6e1ed9cd-7a2c-4a37-a1be-c6e89f3e12db \\
      --module-type CommonModule \\
      --line 42 \\
      --wait-bp 30

Roadmap: docs/roadmap/260508_ROADMAP_BSL_DEBUG_WRAPPER_POST_BP_HANDSHAKE.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import socket
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WRAPPER_DIR = REPO_ROOT / "tools" / "bsl-debug-server"
sys.path.insert(0, str(WRAPPER_DIR))

import mcp_debug_server as mds  # noqa: E402

DEFAULT_DEBUG_URL = "http://localhost:1550"
DEFAULT_INFOBASE = "TestDB"


def probe_tcp(host: str, port: int, timeout: float = 1.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


async def probe_only(debug_url: str, infobase: str) -> dict:
    """Quick health probe: TCP + attach + ping. ~3 sec end-to-end."""
    report = {
        "mode": "probe-only",
        "tcp_1550": False,
        "api_version": None,
        "attach_result": None,
        "ping_count": None,
        "exit_code": 2,
        "errors": [],
    }
    if not probe_tcp("localhost", 1550):
        report["errors"].append("dbgs.exe TCP :1550 unreachable — 1С Server / debug agent not running")
        return report
    report["tcp_1550"] = True

    client = mds.RDBGClient(debug_url=debug_url, infobase_alias=infobase)
    try:
        report["api_version"] = await client.get_api_version()
        report["attach_result"] = await client.attach()
        # One ping to confirm event-loop wakes up
        await asyncio.sleep(2.5)
        report["ping_count"] = len(client._known_attached_targets)
        report["exit_code"] = 0
    except Exception as e:
        report["errors"].append(f"handshake failed: {e!r}")
        report["exit_code"] = 1
    finally:
        try:
            await client.close()
        except Exception:
            pass
    return report


async def full_cycle(args) -> dict:
    """Full BP-fire cycle: requires interactive 1С user trigger."""
    report = {
        "mode": "full",
        "tcp_1550": False,
        "attach_result": None,
        "bp_set": False,
        "bp_fired": False,
        "stack_frames": None,
        "variables_count": None,
        "eval_result": None,
        "step_continued": False,
        "exit_code": 2,
        "errors": [],
    }
    if not probe_tcp("localhost", 1550):
        report["errors"].append("dbgs.exe TCP :1550 unreachable")
        return report
    report["tcp_1550"] = True

    client = mds.RDBGClient(debug_url=args.debug_url, infobase_alias=args.infobase)
    try:
        report["attach_result"] = await client.attach()
        await client.init_settings()

        # Auto-attach known targets so BP fires deliver
        targets = await client.get_targets()
        ids = [t.get("id") for t in targets if t.get("id")]
        if ids:
            await client.attach_debug_targets(ids)
            client._known_attached_targets.update(ids)

        await client.set_breakpoints(
            module_type="ConfigModule",
            object_id=args.object_id,
            property_id=mds.MODULE_PROPERTY_IDS.get(args.module_type, mds.ZERO_UUID),
            lines=[args.line],
        )
        report["bp_set"] = True
        print(f"[smoke] BP set on {args.module_type} @ line {args.line}. "
              f"Запустите сценарий в 1С (макс {args.wait_bp}с)...", file=sys.stderr)

        # Wait for BP fire — ping_loop dispatches events to client._stopped_targets
        loop = asyncio.get_running_loop()  # py3.12+ forward-compat
        deadline = loop.time() + args.wait_bp
        while loop.time() < deadline:
            if client.last_stopped_target_id:
                break
            await asyncio.sleep(0.5)

        if not client.last_stopped_target_id:
            report["errors"].append(f"BP did not fire within {args.wait_bp}s")
            report["exit_code"] = 1
            return report
        report["bp_fired"] = True

        # P1.3: stack via cache (no pull)
        stack = await client.get_call_stack()
        report["stack_frames"] = len(stack)

        # P1.2: variables via re-attach guard
        variables = await client.eval_local_variables()
        report["variables_count"] = len(variables)

        # P2.3: eval composite expression with 4096 maxTextSize
        eval_res = await client.eval_expression(expression="ТекущаяДата()")
        report["eval_result"] = eval_res[:1] if eval_res else None  # truncate

        # P2.2: Continue resume — drops _stopped_targets
        await client.step(action="Continue")
        report["step_continued"] = client.last_stopped_target_id is None
        report["exit_code"] = 0 if report["step_continued"] else 1
    except Exception as e:
        report["errors"].append(f"full cycle failed: {e!r}")
        report["exit_code"] = 1
    finally:
        try:
            await client.close()
        except Exception:
            pass
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug pipeline smoke test (roadmap §13 P3.2)")
    parser.add_argument("--probe-only", action="store_true", help="Quick TCP+attach probe (default)")
    parser.add_argument("--full", action="store_true", help="Full BP-fire cycle (requires interactive 1С)")
    parser.add_argument("--debug-url", default=DEFAULT_DEBUG_URL)
    parser.add_argument("--infobase", default=DEFAULT_INFOBASE)
    parser.add_argument("--object-id", help="Metadata object UUID (Document, CommonModule, ...) for --full")
    parser.add_argument("--module-type", default="CommonModule", help="BSL module kind for --full")
    parser.add_argument("--line", type=int, default=1, help="Line number for BP in --full")
    parser.add_argument("--wait-bp", type=int, default=30, help="Seconds to wait for BP fire in --full")
    parser.add_argument("--json", action="store_true", help="Emit JSON report")
    args = parser.parse_args()

    if args.full and not args.object_id:
        parser.error("--full requires --object-id")
    if not args.full:
        args.probe_only = True  # default

    if args.full:
        report = asyncio.run(full_cycle(args))
    else:
        report = asyncio.run(probe_only(args.debug_url, args.infobase))

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"\n=== Smoke test ({report['mode']}) ===")
        for k, v in report.items():
            print(f"  {k}: {v}")
        if report["errors"]:
            print(f"\nErrors:\n  " + "\n  ".join(report["errors"]))
        labels = {0: "OK (Full)", 1: "DEGRADED", 2: "UNUSABLE (1С not running)"}
        print(f"\n=> exit_code={report['exit_code']} ({labels.get(report['exit_code'], '?')})")

    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
