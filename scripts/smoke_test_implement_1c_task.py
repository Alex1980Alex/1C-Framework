#!/usr/bin/env python3
"""Smoke-test для /implement-1c-task pipeline.

Проверяет среду, в которой будет запускаться skill `implement-1c-task` v2.3.0+:
  1. Парсит .mcp.json и валидирует пути в `command:` (python.exe / node / java).
  2. TCP-probe для HTTP-bridge серверов (`:8765` edt-mcp, `:6333` qdrant) и debug agent (`:1550`).
  3. MCP-handshake (initialize JSON-RPC) для каждого критичного stdio-сервера.
  4. Определяет режим pipeline по матрице SKILL.md Stage 0 (Full/Code-only/Read-only verify/Read-only research).

Exit codes:
  0 — Full mode
  1 — degraded mode (Code-only / Read-only verify / Read-only research)
  2 — unusable

Usage:
  python scripts/smoke_test_implement_1c_task.py
  python scripts/smoke_test_implement_1c_task.py --json
  python scripts/smoke_test_implement_1c_task.py --config path/to/.mcp.json

Roadmap: docs/roadmap/260505_ROADMAP_IMPLEMENT_1C_TASK_PIPELINE_FIX.md (Phase 5).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shutil
import socket
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = REPO_ROOT / ".mcp.json"

CRITICAL_SERVERS = {
    "edt-mcp": "EDT-MCP — основной инструмент записи кода (Этапы 1/3/5)",
    "1c-mcp-crud": "1c-mcp-crud — верификация на живых данных (Этапы 2/6)",
    "bsl-debugger": "bsl-debugger — статический анализ (Этап 4)",
    "bsl-semantic-search": "bsl-semantic-search — fallback контекста (Этап 1)",
}

# Optional servers — недоступность не блокирует pipeline, но снижает покрытие
# проверки. `1c-debug-hmr` нужен для BP-verification Этапа 5.x; при отсутствии
# pipeline работает в режиме "Full (no-BP)" — BP-verification SKIP.
OPTIONAL_SERVERS = {
    "1c-debug-hmr": "1c-debug-hmr — live BP-verification (Этап 5.x)",
}

PORTS = {
    8765: "edt-mcp HTTP-bridge",
    1550: "1С debug agent",
    6333: "Qdrant",
}

HANDSHAKE_TIMEOUT = 6.0
TCP_TIMEOUT = 1.5


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class McpHealth:
    """Структурированный health-check для всех опрошенных серверов.
    Используется hook'ами (implement-1c-task-preflight) для surface'а на UI."""
    edt_mcp: bool = False
    onec_crud: bool = False
    bsl_debugger: bool = False
    bsl_semantic: bool = False
    debug_hmr: bool = False


@dataclass
class Report:
    config_path: str
    paths: list[CheckResult] = field(default_factory=list)
    ports: list[CheckResult] = field(default_factory=list)
    handshakes: list[CheckResult] = field(default_factory=list)
    edt_mcp: bool = False
    onec_crud: bool = False
    bsl_debugger: bool = False
    bsl_semantic: bool = False
    debug_hmr: bool = False  # опциональный — BP-verification в Этапе 5.x
    mcp_health: McpHealth = field(default_factory=McpHealth)
    mode: str = "Read-only research"
    exit_code: int = 2


def probe_tcp(host: str, port: int, timeout: float = TCP_TIMEOUT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def check_paths(config: dict) -> list[CheckResult]:
    out: list[CheckResult] = []
    for name, cfg in config.get("mcpServers", {}).items():
        cmd = cfg.get("command")
        if not cmd:
            continue
        if cmd in {"npx", "node", "java"}:
            out.append(CheckResult(name=f"{name}: command={cmd}", ok=True, detail="resolved via PATH"))
            continue
        path = Path(cmd)
        if path.is_absolute() and path.exists():
            out.append(CheckResult(name=f"{name}: {path.name}", ok=True, detail=str(path)))
        elif path.is_absolute():
            out.append(CheckResult(name=f"{name}: {path.name}", ok=False, detail=f"NOT FOUND: {path}"))
        else:
            out.append(CheckResult(name=f"{name}: {cmd}", ok=True, detail="relative — assumed on PATH"))
    return out


def resolve_command(cmd: str) -> str:
    """На Windows `npx`/`node` это `.cmd`-обёртки — `asyncio.create_subprocess_exec` их сам не находит."""
    if Path(cmd).is_absolute():
        return cmd
    resolved = shutil.which(cmd)
    return resolved or cmd


def probe_http(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    """GET URL, любой HTTP-ответ (включая 4xx) считается доказательством, что сервер слушает."""
    try:
        with urlopen(Request(url, method="GET"), timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except URLError as exc:
        reason = getattr(exc, "reason", str(exc))
        if hasattr(exc, "code"):
            return True, f"HTTP {exc.code}"
        return False, f"{reason}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {exc}"


async def mcp_handshake(name: str, cfg: dict) -> CheckResult:
    """Запускает stdio MCP-сервер, отправляет initialize и читает первый ответ."""
    cmd = resolve_command(cfg.get("command", ""))
    args = cfg.get("args", [])
    cwd = cfg.get("cwd") or str(REPO_ROOT)
    env = os.environ.copy()
    for k, v in (cfg.get("env") or {}).items():
        if isinstance(v, str):
            env[k] = v

    initialize = json.dumps({
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "smoke-test", "version": "0.1.0"},
        },
    }) + "\n"

    try:
        proc = await asyncio.create_subprocess_exec(
            cmd, *args,
            cwd=cwd,
            env=env,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except FileNotFoundError as exc:
        return CheckResult(name=name, ok=False, detail=f"spawn failed: {exc}")
    except OSError as exc:
        return CheckResult(name=name, ok=False, detail=f"spawn error: {exc}")

    try:
        proc.stdin.write(initialize.encode("utf-8"))
        await proc.stdin.drain()
    except (BrokenPipeError, ConnectionResetError) as exc:
        proc.kill()
        return CheckResult(name=name, ok=False, detail=f"stdin error: {exc}")

    try:
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=HANDSHAKE_TIMEOUT)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return CheckResult(name=name, ok=False, detail=f"handshake timeout >{HANDSHAKE_TIMEOUT}s")

    try:
        proc.kill()
        await proc.wait()
    except ProcessLookupError:
        pass

    if not line:
        return CheckResult(name=name, ok=False, detail="empty response")
    try:
        msg = json.loads(line.decode("utf-8", errors="replace"))
    except json.JSONDecodeError as exc:
        return CheckResult(name=name, ok=False, detail=f"bad JSON: {exc}")

    if "result" in msg:
        proto = msg["result"].get("protocolVersion", "?")
        return CheckResult(name=name, ok=True, detail=f"protocol={proto}")
    err = msg.get("error", {}).get("message", "no result")
    return CheckResult(name=name, ok=False, detail=f"rpc error: {err}")


async def run(config_path: Path) -> Report:
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    rep = Report(config_path=str(config_path))

    rep.paths = check_paths(raw)

    for port, label in PORTS.items():
        ok = probe_tcp("127.0.0.1", port)
        rep.ports.append(CheckResult(name=f":{port} {label}", ok=ok, detail="LISTENING" if ok else "closed"))

    servers = raw.get("mcpServers", {})
    # edt-mcp — HTTP-bridge через `mcp-remote` обёртку: проверяем напрямую HTTP, не stdio.
    edt_url = "http://localhost:8765/mcp"
    edt_ok, edt_detail = probe_http(edt_url) if probe_tcp("127.0.0.1", 8765) else (False, "port closed")
    rep.handshakes.append(CheckResult(name="edt-mcp", ok=edt_ok, detail=f"{edt_url} -> {edt_detail}"))

    # Stdio-серверы: handshake через initialize JSON-RPC.
    # 1c-debug-hmr опциональный — недоступность не меняет mode,
    # только отключает BP-verification в Этапе 5.x (mode "Full (no-BP)").
    stdio_targets = [n for n in ("1c-mcp-crud", "bsl-debugger", "bsl-semantic-search", "1c-debug-hmr") if n in servers]
    coros = [mcp_handshake(n, servers[n]) for n in stdio_targets]
    rep.handshakes.extend(await asyncio.gather(*coros))

    by_name = {h.name: h for h in rep.handshakes}
    rep.edt_mcp = bool(by_name.get("edt-mcp") and by_name["edt-mcp"].ok)
    rep.onec_crud = bool(by_name.get("1c-mcp-crud") and by_name["1c-mcp-crud"].ok)
    rep.bsl_debugger = bool(by_name.get("bsl-debugger") and by_name["bsl-debugger"].ok)
    rep.bsl_semantic = bool(by_name.get("bsl-semantic-search") and by_name["bsl-semantic-search"].ok)
    rep.debug_hmr = bool(by_name.get("1c-debug-hmr") and by_name["1c-debug-hmr"].ok)

    rep.mcp_health = McpHealth(
        edt_mcp=rep.edt_mcp,
        onec_crud=rep.onec_crud,
        bsl_debugger=rep.bsl_debugger,
        bsl_semantic=rep.bsl_semantic,
        debug_hmr=rep.debug_hmr,
    )

    if rep.edt_mcp and rep.onec_crud:
        # Full pipeline; debug-hmr — ортогональная ось (BP-verification в Этапе 5.x)
        rep.mode = "Full" if rep.debug_hmr else "Full (no-BP)"
        rep.exit_code = 0
    elif rep.edt_mcp and not rep.onec_crud:
        rep.mode = "Code-only"
        rep.exit_code = 1
    elif not rep.edt_mcp and rep.onec_crud:
        rep.mode = "Read-only verify"
        rep.exit_code = 1
    elif rep.bsl_semantic or rep.bsl_debugger:
        rep.mode = "Read-only research"
        rep.exit_code = 1
    else:
        rep.mode = "unusable"
        rep.exit_code = 2

    return rep


def render_human(rep: Report) -> str:
    def mark(ok: bool) -> str:
        return "OK " if ok else "FAIL"

    lines = [
        f"Config: {rep.config_path}",
        "",
        "[paths]",
    ]
    for r in rep.paths:
        lines.append(f"  {mark(r.ok)}  {r.name}  — {r.detail}")
    lines += ["", "[ports]"]
    for r in rep.ports:
        lines.append(f"  {mark(r.ok)}  {r.name}  — {r.detail}")
    lines += ["", "[handshakes]"]
    for r in rep.handshakes:
        lines.append(f"  {mark(r.ok)}  {r.name}  — {r.detail}")
    lines += ["", f"Pipeline mode: {rep.mode}", f"Exit code: {rep.exit_code}"]
    if not rep.debug_hmr and rep.mode.startswith("Full"):
        lines.append("  (BP-verification в Этапе 5.x SKIP — 1c-debug-hmr недоступен)")
    return "\n".join(lines)


def main() -> int:
    # Windows консоль по умолчанию cp1251 — UTF-8 для безопасной печати.
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except Exception:
            pass

    p = argparse.ArgumentParser(description="Smoke-test for /implement-1c-task pipeline.")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to .mcp.json")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    args = p.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        return 2

    try:
        rep = asyncio.run(run(config_path))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    if args.json:
        payload = asdict(rep)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_human(rep))
    return rep.exit_code


if __name__ == "__main__":
    sys.exit(main())
