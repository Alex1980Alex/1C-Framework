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

SUBMODULE_ROOT = Path(__file__).resolve().parent.parent / "external" / "1c_mcp"
os.chdir(SUBMODULE_ROOT)
sys.path.insert(0, str(SUBMODULE_ROOT))

from src.py_server.main import main

if __name__ == "__main__":
    asyncio.run(main())
