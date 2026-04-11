#!/usr/bin/env python3
"""
trigger-reglament.py — Triggers 1C scheduled job "Путь Б"
(гкс_ОбновлениеТаблоЭлектроннойОчереди) via the 1C HTTP service JSON-RPC
endpoint.

Bypasses the БСП "infobase moved" guard (testdb1c is a PROD copy and the guard
disables scheduled jobs automatically) and then calls the common-module
procedure synchronously, so VA BDD tests can wait for completion.

Kept as a standalone Python script because PowerShell on Windows corrupts
Cyrillic payloads when marshalling them through `ConvertTo-Json` or `-c`.

Usage:
    python trigger-reglament.py [--rpc-url URL] [--user NAME] [--password PASS] [--timeout 30]

Called from VA BDD feature files via:
    И я запускаю команду операционной системы "powershell -ExecutionPolicy Bypass -File D:\\va-test\\trigger-reglament.ps1"
which in turn invokes this script through the project venv.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time

import httpx

DEFAULT_RPC_URL = os.environ.get("ONEC_RPC_URL", "http://localhost/TestDB/hs/mcp/rpc")
DEFAULT_USERNAME = os.environ.get("ONEC_USERNAME", "a.terletskiy@sodru.com")
DEFAULT_PASSWORD = os.environ.get("ONEC_PASSWORD", "Alex80Alex")

# Two-statement BSL executed as the tool payload:
#   1) allow work with external resources (unblocks the scheduled job guard),
#   2) call the common-module procedure synchronously.
BSL_CODE = (
    "БлокировкаРаботыСВнешнимиРесурсами.РазрешитьРаботуСВнешнимиРесурсами();"
    " гкс_ЭлектроннаяОчередь.ОбновлениеТаблоЭлектроннойОчереди();"
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Trigger 1C scheduled job Путь Б")
    parser.add_argument("--rpc-url", default=DEFAULT_RPC_URL)
    parser.add_argument("--user", default=DEFAULT_USERNAME)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    print(f"[trigger-reglament] POST {args.rpc_url}", flush=True)

    rpc_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "execute_code",
            "arguments": {"code": BSL_CODE},
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
        print(
            f"[OK] регламент гкс_ОбновлениеТаблоЭлектроннойОчереди выполнен за {elapsed} сек"
        )
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
