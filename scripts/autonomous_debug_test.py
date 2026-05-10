#!/usr/bin/env python3
"""Roadmap §12.2 Level 2 — autonomous E2E debug test runner.

Drives the entire debug workflow без user interaction:
    1. health_check → auto-prepare если нужно
    2. debug_connect (с force_recycle если scenario так указывает)
    3. Set BPs from scenario JSON
    4. Trigger BSL execution via IIS /hs/mcp/rpc (1c-mcp-crud equivalent)
    5. Poll for stop events; at each stop — stack_trace + inspect + Continue
    6. debug_session_summary в конце
    7. Exit 0 если все expected BPs fired + inspections passed

Usage:
    python scripts/autonomous_debug_test.py <scenario.json>

Scenario JSON example (scripts/scenarios/post_lab_doc.json):
    {
      "alias": "ИБTransportManagementDevelop",
      "iis": {
        "url": "http://localhost/transport/hs/mcp/rpc",
        "auth_user_env": "MCP_ONEC_USERNAME",
        "auth_pwd_env": "MCP_ONEC_PASSWORD"
      },
      "force_recycle": false,
      "bsl_trigger": "Документы.гкс_ЛабораторныйАнализ.НайтиПоНомеру(\\"ТМУТ-000006\\").ПолучитьОбъект().Записать(РежимЗаписиДокумента.Проведение)",
      "breakpoints": [
        {
          "object_id": "9c496dda-a7d1-463a-945d-1916088f7b61",
          "line": 141, "module_type": "ObjectModule",
          "inspections": [
            {"expr": "ТипЗнч(ДопПараметры).ПолноеИмя()",
             "expect_substring": "Тип"}
          ]
        }
      ],
      "stop_timeout_sec": 15
    }
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

# Wrapper module is in tools/bsl-debug-server/ (sibling of scripts/)
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT / "tools" / "bsl-debug-server"))

import httpx  # noqa: E402
import mcp_debug_server as mds  # noqa: E402

# Exit codes
EXIT_OK = 0
EXIT_SCHEMA_INVALID = 9
EXIT_HEALTH_FAILED = 10
EXIT_CONNECT_FAILED = 11
EXIT_BP_TIMEOUT = 12
EXIT_INSPECTION_FAILED = 13
EXIT_BSL_TRIGGER_FAILED = 14


def validate_scenario(scenario: dict) -> list:
    """Pure-Python scenario JSON schema validator (no jsonschema dep).

    Returns: list of error strings (empty list если scenario валиден).
    """
    errors: list = []

    def require(obj: dict, path: str, key: str, types: tuple) -> None:
        if key not in obj:
            errors.append(f"{path}.{key} is required")
            return
        val = obj[key]
        if not isinstance(val, types):
            type_names = " | ".join(t.__name__ for t in types)
            errors.append(f"{path}.{key} must be {type_names}, got {type(val).__name__}")

    if not isinstance(scenario, dict):
        return ["scenario root must be object"]

    require(scenario, "$", "alias", (str,))
    require(scenario, "$", "bsl_trigger", (str,))
    require(scenario, "$", "breakpoints", (list,))

    if "iis" in scenario:
        iis = scenario["iis"]
        if isinstance(iis, dict):
            require(iis, "$.iis", "url", (str,))
        else:
            errors.append("$.iis must be object")

    if "force_recycle" in scenario and not isinstance(scenario["force_recycle"], bool):
        errors.append("$.force_recycle must be bool")

    if "stop_timeout_sec" in scenario and not isinstance(
            scenario["stop_timeout_sec"], (int, float)):
        errors.append("$.stop_timeout_sec must be number")

    if "pre_trigger_wait_sec" in scenario and not isinstance(
            scenario["pre_trigger_wait_sec"], (int, float)):
        errors.append("$.pre_trigger_wait_sec must be number")

    bps = scenario.get("breakpoints", [])
    if isinstance(bps, list):
        for i, bp in enumerate(bps):
            path = f"$.breakpoints[{i}]"
            if not isinstance(bp, dict):
                errors.append(f"{path} must be object")
                continue
            require(bp, path, "object_id", (str,))
            require(bp, path, "line", (int,))
            if "module_type" in bp and not isinstance(bp["module_type"], str):
                errors.append(f"{path}.module_type must be string")
            if "inspections" in bp:
                insps = bp["inspections"]
                if not isinstance(insps, list):
                    errors.append(f"{path}.inspections must be array")
                    continue
                for j, insp in enumerate(insps):
                    if not isinstance(insp, dict):
                        errors.append(f"{path}.inspections[{j}] must be object")
                        continue
                    require(insp, f"{path}.inspections[{j}]", "expr", (str,))

    return errors


def _print_section(title: str) -> None:
    print(f"\n=== {title} ===", flush=True)


async def _trigger_bsl_via_iis(scenario: dict) -> tuple[int, str]:
    """POST execute_code BSL код к IIS /hs/mcp/rpc endpoint.

    Returns (exit_code, message). Exit 0 если HTTP 200.
    Run as background task — wrapper параллельно ловит stop events.
    """
    iis = scenario.get("iis", {})
    url = iis.get("url")
    user = os.environ.get(iis.get("auth_user_env", ""), "")
    pwd = os.environ.get(iis.get("auth_pwd_env", ""), "")
    if not url:
        return EXIT_BSL_TRIGGER_FAILED, "scenario.iis.url not set"
    body = {"jsonrpc": "2.0", "id": 1, "method": "execute_code",
            "params": {"code": scenario.get("bsl_trigger", "")}}
    auth = httpx.BasicAuth(user, pwd) if user else None
    try:
        async with httpx.AsyncClient(timeout=120.0) as cli:
            resp = await cli.post(url, json=body, auth=auth)
        if resp.status_code != 200:
            return EXIT_BSL_TRIGGER_FAILED, \
                f"IIS POST {resp.status_code}: {resp.text[:300]}"
        return EXIT_OK, f"BSL OK ({len(resp.text)} bytes)"
    except (httpx.HTTPError, OSError) as e:
        return EXIT_BSL_TRIGGER_FAILED, f"trigger exception: {e}"


def _format_inspection_result(eval_resp: list, expr: str) -> tuple[bool, str]:
    """Extract presentation/value from RDBG eval response."""
    if not eval_resp:
        return False, f"eval `{expr}` returned empty"
    first = eval_resp[0]
    if first.get("evalResultState") == "withErrors":
        return False, f"eval error: {first.get('exceptionStr', '')[:200]}"
    info = first.get("resultValueInfo", {})
    return True, json.dumps({
        "type": info.get("typeName"),
        "value": info.get("valueString") or info.get("valueDecimal")
                 or info.get("valueBoolean"),
        "presentation_b64": info.get("pres", "")[:80],
    }, ensure_ascii=False)


async def _check_inspections(inspections: list, target_id: str) -> tuple[bool, list]:
    """Run all inspections at current stop. Returns (all_passed, results)."""
    results = []
    all_passed = True
    for insp in inspections:
        expr = insp["expr"]
        try:
            raw = await mds.debug_evaluate(expression=expr,
                                            target_id=target_id)
            eval_resp = json.loads(raw).get("result", [])
            ok, detail = _format_inspection_result(eval_resp, expr)
            if "expect_substring" in insp:
                if insp["expect_substring"] not in detail:
                    ok = False
                    detail += f" | missing '{insp['expect_substring']}'"
            results.append({"expr": expr, "passed": ok, "detail": detail})
            if not ok:
                all_passed = False
        except Exception as e:
            results.append({"expr": expr, "passed": False, "detail": str(e)})
            all_passed = False
    return all_passed, results


async def _wait_for_stop(deadline_sec: float) -> str | None:
    """Poll debug_targets until stopped_target appears OR deadline."""
    loop = asyncio.get_event_loop()
    deadline = loop.time() + deadline_sec
    while loop.time() < deadline:
        targets_raw = await mds.debug_targets()
        stopped = json.loads(targets_raw).get("stopped_target")
        if stopped:
            return stopped
        await asyncio.sleep(0.3)
    return None


async def run_scenario(scenario: dict) -> int:
    """Execute scenario end-to-end. Returns exit code."""
    _print_section("Phase 1 — Health check")
    health_raw = await mds.debug_health_check()
    health = json.loads(health_raw)
    print(f"ready={health['ready']}, "
          f"workflow={health['recommended_workflow']}")
    if not health["ready"]:
        if health.get("auto_prepare_available"):
            print(f"auto-prepare: {health['auto_prepare_available']}")
            prep_raw = await mds.debug_health_check(
                mode="prepare", actions=health["auto_prepare_available"])
            prep = json.loads(prep_raw)
            print(f"prepare result: ready={prep.get('ready')}")
            if not prep.get("ready"):
                print("[FAIL] env not ready после auto-prepare")
                return EXIT_HEALTH_FAILED
        else:
            print("[FAIL] env not ready, no auto-prepare available")
            return EXIT_HEALTH_FAILED

    _print_section("Phase 2 — Connect debug")
    connect_raw = await mds.debug_connect(
        infobase_alias=scenario["alias"],
        force_recycle_rphost=scenario.get("force_recycle", False),
    )
    connect = json.loads(connect_raw)
    if connect.get("status") != "connected":
        print(f"[FAIL] connect: {connect}")
        return EXIT_CONNECT_FAILED
    print(f"session={connect['attach']['session_id'][:8]}…, "
          f"targets={len(connect.get('targets', []))}")

    _print_section("Phase 3 — Set breakpoints")
    bps = scenario.get("breakpoints", [])
    for i, bp in enumerate(bps, 1):
        await mds.debug_set_breakpoint(
            object_id=bp["object_id"],
            line=bp["line"],
            module_type=bp.get("module_type", "CommonModule"),
        )
        print(f"  BP{i}: {bp.get('module_type')} obj={bp['object_id'][:8]}… "
              f"line={bp['line']}")

    _print_section("Phase 4 — Trigger BSL + capture stops")
    trigger_task = asyncio.create_task(_trigger_bsl_via_iis(scenario))
    timeout_per_stop = scenario.get("stop_timeout_sec", 15)
    expected_stops = len(bps)
    fired = 0
    inspection_failures = []
    for i, bp in enumerate(bps, 1):
        print(f"\n  Waiting for BP{i} (timeout {timeout_per_stop}s)…",
              flush=True)
        target_id = await _wait_for_stop(timeout_per_stop)
        if not target_id:
            print(f"[FAIL] BP{i} timeout — got {fired}/{expected_stops}")
            trigger_task.cancel()
            await mds.debug_disconnect()
            return EXIT_BP_TIMEOUT
        fired += 1
        # Stack trace для diagnostics
        stack_raw = await mds.debug_stack_trace(target_id=target_id)
        stack = json.loads(stack_raw).get("stack", [])
        top = stack[0] if stack else {}
        print(f"  BP{i} fired @ line={top.get('lineNo', '?')} "
              f"depth={len(stack)}")
        # Run inspections
        if bp.get("inspections"):
            ok, results = await _check_inspections(bp["inspections"], target_id)
            for r in results:
                marker = "✓" if r["passed"] else "✗"
                print(f"    {marker} `{r['expr']}` → {r['detail']}")
            if not ok:
                inspection_failures.append({"bp_index": i, "results": results})
        await mds.debug_step(action="Continue")

    # Wait for trigger to complete
    trigger_exit, trigger_msg = await trigger_task
    print(f"\n  BSL trigger: {trigger_msg}")

    _print_section("Phase 5 — Session summary")
    summary_md = await mds.debug_session_summary(format="markdown")
    print(summary_md)

    await mds.debug_disconnect()

    if inspection_failures:
        print(f"\n[FAIL] {len(inspection_failures)} BP(s) had inspection failures")
        return EXIT_INSPECTION_FAILED
    if fired != expected_stops:
        print(f"\n[FAIL] {fired}/{expected_stops} BPs fired")
        return EXIT_BP_TIMEOUT
    print(f"\n[OK] All {expected_stops} BPs fired + all inspections passed")
    return EXIT_OK


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                      formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("scenario", type=Path,
                        help="Path to scenario JSON file")
    args = parser.parse_args()

    if not args.scenario.is_file():
        print(f"[FAIL] scenario file not found: {args.scenario}",
              file=sys.stderr)
        return 2

    scenario = json.loads(args.scenario.read_text(encoding="utf-8"))
    print(f"=== Autonomous debug test runner — {args.scenario.name} ===")
    print(f"Alias: {scenario.get('alias')}")
    print(f"BPs: {len(scenario.get('breakpoints', []))}")
    return asyncio.run(run_scenario(scenario))


if __name__ == "__main__":
    sys.exit(main())
