"""MCP servers smoke check (roadmap 260509 §4.7).

Structural validation для всех серверов в `.mcp.json`:
  1. Command executable resolvable (PATH или absolute) ✓
  2. CWD existed ✓
  3. Args reference existing files (если first arg .js / .py path) ✓
  4. Required env vars присутствуют (если ${VAR} pattern в env) ⚠ warning

NOT covered: full MCP protocol handshake (требует `mcp` package + взаимодействие
с running server). Для protocol-level validation — `npx @modelcontextprotocol/inspector`
интерактивно или dedicated test suite в tests/integration/.

Exit codes:
  0  — all servers structurally valid
  1  — one or more servers have hard errors (missing command/cwd/script)
  2  — invalid `.mcp.json` или file отсутствует

Usage:
    python scripts/mcp_smoke_check.py
    python scripts/mcp_smoke_check.py --json
    python scripts/mcp_smoke_check.py --strict   # warning → error
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path

DEFAULT_CONFIG = Path(".mcp.json")
ENV_VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")


def _resolve_command(command: str, cwd: Path | None) -> Path | None:
    """Найти executable: absolute path → PATH lookup → None."""
    p = Path(command)
    if p.is_absolute():
        return p if p.is_file() else None
    located = shutil.which(command)
    if located:
        return Path(located)
    return None


def _check_args_paths(args: list[str], cwd: Path) -> list[str]:
    """Args обычно содержат `.py` / `.js` файлы. Проверяем их existence."""
    issues: list[str] = []
    for arg in args:
        if not isinstance(arg, str):
            continue
        if arg.startswith("-"):
            continue
        if not arg.endswith((".py", ".js", ".ts", ".mjs")):
            continue
        candidate = Path(arg)
        if not candidate.is_absolute():
            candidate = cwd / arg
        if not candidate.is_file():
            issues.append(f"args path not found: {arg}")
    return issues


def _check_env_vars(env: dict[str, str]) -> list[str]:
    """Find ${VAR} placeholders that aren't set in os.environ."""
    issues: list[str] = []
    for key, val in env.items():
        if not isinstance(val, str):
            continue
        for m in ENV_VAR_RE.finditer(val):
            var_name = m.group(1)
            if var_name not in os.environ:
                issues.append(f"env {key}={val} → ${{{var_name}}} not set in os.environ")
    return issues


def check_server(name: str, spec: dict) -> dict:
    """Validate single server spec. Returns {name, status, errors, warnings}."""
    errors: list[str] = []
    warnings: list[str] = []

    command = spec.get("command")
    if not command:
        errors.append("'command' field missing")
        return {"name": name, "status": "error", "errors": errors, "warnings": warnings}

    cwd_str = spec.get("cwd")
    cwd = Path(cwd_str) if cwd_str else Path.cwd()
    if cwd_str and not cwd.is_dir():
        errors.append(f"cwd not found: {cwd_str}")

    resolved = _resolve_command(command, cwd if cwd.is_dir() else None)
    if resolved is None:
        errors.append(f"command not resolvable: {command}")

    args = spec.get("args", []) or []
    if cwd.is_dir():
        errors.extend(_check_args_paths(args, cwd))

    env = spec.get("env", {}) or {}
    warnings.extend(_check_env_vars(env))

    status = "error" if errors else ("warning" if warnings else "ok")
    return {
        "name": name,
        "status": status,
        "command": str(resolved) if resolved else command,
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (AttributeError, OSError):
            pass

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, help=".mcp.json path")
    parser.add_argument("--json", dest="as_json", action="store_true", help="JSON output for CI")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Warnings (missing env vars) промоутятся до errors",
    )
    args = parser.parse_args()

    if not args.config.is_file():
        print(f"ERROR: config not found: {args.config}", file=sys.stderr)
        return 2

    try:
        cfg = json.loads(args.config.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {args.config}: {e}", file=sys.stderr)
        return 2

    servers = cfg.get("mcpServers") or {}
    if not servers:
        print("WARN: no mcpServers in config", file=sys.stderr)
        return 0

    results = [check_server(name, spec) for name, spec in sorted(servers.items())]

    has_error = any(r["status"] == "error" for r in results)
    has_warning = any(r["status"] == "warning" for r in results)

    if args.as_json:
        print(
            json.dumps(
                {
                    "results": results,
                    "summary": {
                        "total": len(results),
                        "ok": sum(1 for r in results if r["status"] == "ok"),
                        "warning": sum(1 for r in results if r["status"] == "warning"),
                        "error": sum(1 for r in results if r["status"] == "error"),
                    },
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        ok = sum(1 for r in results if r["status"] == "ok")
        wn = sum(1 for r in results if r["status"] == "warning")
        er = sum(1 for r in results if r["status"] == "error")
        print(f"MCP smoke: {ok}/{len(results)} ok, {wn} warning, {er} error")
        for r in results:
            if r["status"] != "ok":
                marker = "ERROR" if r["status"] == "error" else "WARN"
                print(f"  [{marker}] {r['name']}")
                for issue in r["errors"]:
                    print(f"      x {issue}")
                for issue in r["warnings"]:
                    print(f"      ! {issue}")

    if has_error:
        return 1
    if args.strict and has_warning:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
