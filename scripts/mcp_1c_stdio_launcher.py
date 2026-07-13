"""Stdio launcher for 1c-mcp-crud MCP server.

Lives in parent repo (scripts/) so the external/1c_mcp/ submodule stays
pristine and syncable from upstream vladimir-kharin/1c_mcp without
carrying a downstream integration shim.

The shim solves a `src/` namespace collision: parent repo has
`C:\\1С-Framework\\src/`, the submodule has `external/1c_mcp/src/`.
Without chdir + sys.path manipulation, `from src.py_server.main` resolves
to the parent's `src/` and the MCP server can't find its own modules.

Wired in .mcp.json as the entry point of the 1c-mcp-crud server
(replacing the previous external/1c_mcp/mcp_stdio.py).
"""

import asyncio
import os
import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SUBMODULE_ROOT = _PROJECT_ROOT / "external" / "1c_mcp"
os.chdir(SUBMODULE_ROOT)
sys.path.insert(0, str(SUBMODULE_ROOT))
# Put the `scripts/` DIR on path (not the project root): `import mcp_call_log`
# resolves the shared helper WITHOUT dragging the parent's `src/` package into
# the import scan — the parent `src` is a regular package and would shadow the
# submodule's `src` namespace, breaking `from src.py_server...`.
sys.path.append(str(_PROJECT_ROOT / "scripts"))


def _instrument_call_tool() -> None:
    """Wrap OneCClient.call_tool with a per-call JSONL log (roadmap 260713 P2.3 / B9).

    Instruments the 1c-mcp-crud server WITHOUT touching the vendored submodule:
    the launcher (parent-repo code) monkeypatches the client method. Fully
    fail-soft — any wiring failure leaves the server unchanged.
    """
    try:
        import mcp_call_log
        from src.py_server.onec_client import OneCClient

        track_call = mcp_call_log.track_call
    except Exception:
        return  # log helper / client unavailable → run uninstrumented

    if getattr(OneCClient.call_tool, "_mcp_call_logged", False):
        return  # idempotent

    _orig_call_tool = OneCClient.call_tool

    async def call_tool(self, name, arguments):
        with track_call("1c-mcp-crud", name) as st:
            result = await _orig_call_tool(self, name, arguments)
            if getattr(result, "isError", False):
                st["ok"] = False
                st["error_type"] = "tool_error"
            return result

    call_tool._mcp_call_logged = True
    OneCClient.call_tool = call_tool


from src.py_server.main import main

if __name__ == "__main__":
    _instrument_call_tool()
    asyncio.run(main())
