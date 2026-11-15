# CI dependency compatibility

The MCP requirement is `mcp>=1.26.0,<2`: existing servers use the SDK v1 API. Version 1.26.0 is the selected tested support floor, matching the historical `requirements.lock` version and a runtime qualification; the lock alone is not compatibility evidence. Versions 1.2 through 1.25 were not qualified. Upstream [documents the v1 maintenance line](https://py.sdk.modelcontextprotocol.io/v1/) and recommends an upper bound below v2 for applications awaiting migration.

Endpoint qualification on 2026-11-15 used these minimal SDK environments:

| Python | MCP SDK |
| --- | --- |
| 3.11.18 | 1.26.0, 1.30.0 |
| 3.12.16 | 1.26.0, 1.30.0 |

The six tests in `tests/bsl/refactor/test_mcp_rename.py` passed for each listed Python/MCP pairing. Separate SDK probes exercised FastMCP, low-level Server list/call handlers, and Tool `inputSchema` responses. MCP 2.3.0 reproduced the targeted collection failure in both interpreters. Environments were updated across versions and retained MCP 2 transitive packages; freezes capture final states. These endpoint checks do not certify clean CI resolution, every intervening SDK version, or the full framework test suite.

CI continues to install `uv pip install --system -e ".[dev,qdrant,morphology]"` on its Python 3.11/3.12 runners. It does not consume `requirements.lock`; retain the resolved package freeze and exact source SHA with each acceptance run. Full CI validation remains required. Migration to MCP v2 is a separate change.

The requirement `sentence-transformers>=3.0,<5.4` preserves the optional inline Qwen3 constructor's `tokenizer_kwargs` for left padding. Primary [PyPI wheel sources](https://pypi.org/project/sentence-transformers/) were inspected without importing the SDK or downloading models: 3.0.0, 5.1.2 and 5.3.0 accept that argument; 5.4.0, 5.4.1, 5.5.0, 5.6.0, 5.7.0, 6.0.0 and 6.3.0 reject it. Constructor API compatibility is separate from embedding inference quality and full dependency-resolution acceptance.

Local/Giga `encode(list[str])` retains its default float32 NumPy sentence output; the typed `tolist()` result assumes the SDK's batch sentence-vector contract. Claude Vision now validates the four SDK image MIME literals before constructing its image block, using the existing failure response for unsupported formats. LLM Rotation typing separates provider-test text from batch JSON and names telemetry counters explicitly; routing and result payloads retain their existing behavior.

A subsequent MCP qualification used four fresh isolated environments: Python 3.11.18 and 3.12.16, each with MCP 1.26.0 and 1.30.0. Each passed the same six rename tests and the SDK dispatch probe. Distribution ownership was exclusively `mcp`; `mcp-types` was absent. This removes the mixed-installation limitation for those endpoint checks; the earlier results above remain their historical record. It does not establish full CI or every intervening version's compatibility.

Ten ChatAnthropic callers now describe only their actual input keys with `AnthropicModelKwargs` and submit the unchanged raw mapping to Pydantic `model_validate`. The `model`/`model_name` aliases, omitted credentials, explicit `None`, empty strings, and optional base URLs retain their original caller inputs. Primary wheel sources for langchain-anthropic 1.7.10, langchain-core 1.8.1, and Pydantic 2.14.3 establish the fields and validation entry point. Acceptance additionally requires constructor-versus-validation parity for these callers; this is not a guarantee for arbitrary future subclasses.

The Qdrant baseline refresh is limited to seven existing `Filter.must` diagnostics (six provider sites and one BSL search site). Each new diagnostic differs only by the two `SliceCondition` members in the SDK's expected union; diagnostic multiplicity remains 1122. ChatAnthropic baseline entries were not replaced.
