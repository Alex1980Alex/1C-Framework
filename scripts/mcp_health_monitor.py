#!/usr/bin/env python3
"""
MCP Server Health Monitor — Phase 12

Monitors health of all MCP servers with parallel async checks,
colored CLI dashboard, and persistent results.

Usage:
    python mcp_health_monitor.py                    # default .mcp.json
    python mcp_health_monitor.py path/to/.mcp.json  # custom config
"""

import asyncio
import json
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


@dataclass
class ServerHealth:
    name: str
    status: str  # ok, error, timeout, disabled
    latency_ms: float
    transport: str  # stdio, http
    last_check: str
    error: str = ""
    tools_count: int = 0


class MCPHealthMonitor:
    TIMEOUT = 5

    def __init__(self, server_configs: dict):
        self.configs = server_configs
        self.results: list[ServerHealth] = []

    async def check_all(self) -> list[ServerHealth]:
        tasks = [self._check(name, cfg) for name, cfg in self.configs.items()]
        self.results = sorted(await asyncio.gather(*tasks), key=lambda h: h.name)
        return self.results

    async def _check(self, name: str, cfg: dict) -> ServerHealth:
        ts = datetime.now(UTC).isoformat()

        if cfg.get("disabled", False):
            return ServerHealth(
                name=name,
                status="disabled",
                latency_ms=0,
                transport="—",
                last_check=ts,
                error="disabled in config",
            )

        transport = "http" if "url" in cfg else "stdio"
        t0 = time.time()
        try:
            result = await asyncio.wait_for(
                self._check_stdio(name, cfg)
                if transport == "stdio"
                else self._check_http(name, cfg),
                timeout=self.TIMEOUT,
            )
            ms = (time.time() - t0) * 1000
            return ServerHealth(
                name=name,
                status="ok",
                latency_ms=round(ms, 1),
                transport=transport,
                last_check=ts,
                tools_count=result.get("tools", 0),
            )
        except TimeoutError:
            return ServerHealth(
                name=name,
                status="timeout",
                latency_ms=0,
                transport=transport,
                last_check=ts,
                error=f">{self.TIMEOUT}s",
            )
        except Exception as e:
            return ServerHealth(
                name=name,
                status="error",
                latency_ms=0,
                transport=transport,
                last_check=ts,
                error=str(e)[:120],
            )

    async def _check_http(self, name: str, cfg: dict) -> dict:
        import urllib.request

        url = cfg["url"].rstrip("/")
        loop = asyncio.get_event_loop()

        def _do():
            urllib.request.urlopen(f"{url}/health", timeout=5)
            return {"tools": 0}

        return await loop.run_in_executor(None, _do)

    async def _check_stdio(self, name: str, cfg: dict) -> dict:
        import os

        cmd = [cfg["command"]] + cfg.get("args", [])
        cwd = cfg.get("cwd")
        env_extra = cfg.get("env", {})
        env = {**os.environ, **env_extra}

        init_msg = (
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "health-check", "version": "1.0"},
                    },
                }
            )
            + "\n"
        )

        loop = asyncio.get_event_loop()

        def _do():
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=env,
                text=True,
            )
            try:
                out, _ = proc.communicate(input=init_msg, timeout=5)
                if "result" in out:
                    data = json.loads(out.strip().split("\n")[0])
                    tools = len(data.get("result", {}).get("capabilities", {}).get("tools", {}))
                    return {"tools": tools}
                return {"tools": 0}
            except subprocess.TimeoutExpired:
                proc.kill()
                raise TimeoutError("stdio timeout")
            except Exception:
                proc.kill()
                raise

        return await loop.run_in_executor(None, _do)

    def print_dashboard(self) -> None:
        if not self.results:
            print("No results. Run check_all() first.")
            return

        symbols = {
            "ok": f"{GREEN}OK{RESET}",
            "error": f"{RED}ERR{RESET}",
            "timeout": f"{YELLOW}TMO{RESET}",
            "disabled": f"{CYAN}DIS{RESET}",
        }

        w_name, w_stat, w_lat, w_tools, w_tr = 28, 6, 8, 5, 8
        sep = f"{'─' * w_name}┼{'─' * w_stat}┼{'─' * w_lat}┼{'─' * w_tools}┼{'─' * w_tr}"

        print(f"\n{BOLD}  MCP Server Health Dashboard{RESET}")
        print(f"  {'─' * (w_name + w_stat + w_lat + w_tools + w_tr + 4)}")
        print(
            f"  {'Server':<{w_name}}│{'Status':^{w_stat}}│{'Latency':^{w_lat}}│{'Tools':^{w_tools}}│{'Type':^{w_tr}}"
        )
        print(f"  {sep}")

        for h in self.results:
            st = symbols.get(h.status, h.status)
            lat = f"{h.latency_ms:.0f}ms" if h.status == "ok" else "—"
            tools = str(h.tools_count) if h.status == "ok" else "—"
            print(
                f"  {h.name:<{w_name}}│{st:^{w_stat + 9}}│{lat:^{w_lat}}│{tools:^{w_tools}}│{h.transport:^{w_tr}}"
            )

        print(f"  {'─' * (w_name + w_stat + w_lat + w_tools + w_tr + 4)}")
        ok = sum(1 for h in self.results if h.status == "ok")
        print(f"  {GREEN}{ok}{RESET}/{len(self.results)} healthy\n")

        errs = [h for h in self.results if h.status in ("error", "timeout")]
        if errs:
            print(f"  {BOLD}Errors:{RESET}")
            for h in errs:
                print(f"    {RED}●{RESET} {h.name}: {h.error}")
            print()


def load_mcp_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    data = json.loads(p.read_text("utf-8"))
    return data.get("mcpServers", {})


async def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else ".mcp.json"
    configs = load_mcp_config(config_path)
    if not configs:
        print("No MCP servers in config.")
        return

    print(f"Checking {len(configs)} MCP server(s)...")
    monitor = MCPHealthMonitor(configs)
    await monitor.check_all()
    monitor.print_dashboard()

    # Save results
    out = Path("cache/mcp-health.json")
    out.parent.mkdir(exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "servers": [asdict(h) for h in monitor.results],
            },
            indent=2,
        ),
        "utf-8",
    )
    print(f"  Saved to {out}")


if __name__ == "__main__":
    asyncio.run(main())
