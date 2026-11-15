# CI dependency compatibility

The MCP requirement is `mcp>=1.26.0,<2`: existing servers use the SDK v1 API. Version 1.26.0 is the selected tested support floor, matching the historical `requirements.lock` version and a runtime qualification; the lock alone is not compatibility evidence. Versions 1.2 through 1.25 were not qualified. Upstream [documents the v1 maintenance line](https://py.sdk.modelcontextprotocol.io/v1/) and recommends an upper bound below v2 for applications awaiting migration.

Endpoint qualification on 2026-11-15 used these minimal SDK environments:

| Python | MCP SDK |
| --- | --- |
| 3.11.18 | 1.26.0, 1.30.0 |
| 3.12.16 | 1.26.0, 1.30.0 |

The six tests in `tests/bsl/refactor/test_mcp_rename.py` passed for each listed Python/MCP pairing. Separate SDK probes exercised FastMCP, low-level Server list/call handlers, and Tool `inputSchema` responses. MCP 2.3.0 reproduced the targeted collection failure in both interpreters. Environments were updated across versions and retained MCP 2 transitive packages; freezes capture final states. These endpoint checks do not certify clean CI resolution, every intervening SDK version, or the full framework test suite.

CI continues to install `uv pip install --system -e ".[dev,qdrant,morphology]"` on its Python 3.11/3.12 runners. It does not consume `requirements.lock`; retain the resolved package freeze and exact source SHA with each acceptance run. Full CI validation remains required. Migration to MCP v2 is a separate change.
