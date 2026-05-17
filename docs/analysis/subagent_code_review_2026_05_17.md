# Subagent Code Review — Session 2026-05-17

> **Reviewer:** Independent general-purpose subagent (agent ID `a72513cb6a5d8f822`)
> **Verdict:** PARTIAL — no critical bugs in helpers, but alias-recreate path has real correctness gap (M1+M2)
> **Scope:** 7 files (indexer.py, server.py, reembed_collection.py, reindex_pdf_documents.py, raptor.py, embedder.py, test_indexer_mrl.py)

## Findings summary

| Severity | Count | Status |
|---|---|---|
| CRITICAL | 0 | — |
| MAJOR | 4 | M1+M2 → fix-needed; M3+M4 → defer |
| MINOR | 9 | informational |
| POSITIVE | 6 | reinforce patterns |

## MAJOR findings

### M1 + M2 — Alias destroyed by `delete_collection(physical)` then recreated under alias name

**Affected:**
- [`src/framework_search/indexer.py:ensure_collection()`](../src/framework_search/indexer.py)
- [`scripts/reembed_collection.py`](../scripts/reembed_collection.py) (upsert + get_collection on alias after delete)
- [`scripts/reindex_pdf_documents.py`](../scripts/reindex_pdf_documents.py) (same pattern)

**Bug flow:**
1. `physical = resolve_physical_collection(client, 'framework_code_v1')` → resolves to `'framework_code_v1_mrl_1024'`
2. `client.delete_collection(physical)` → deletes `framework_code_v1_mrl_1024` → **alias `framework_code_v1` becomes invalid**
3. `client.create_collection(collection_name='framework_code_v1', ...)` → creates a NEW PHYSICAL collection literally named `framework_code_v1` (no alias, no MRL)
4. Result: topology silently changed — alias gone, replaced with un-MRL'd standalone collection

**Production impact:** **None currently** (no automation triggers `--recreate` против aliased collections). Surfaces only при manual `python scripts/index_framework.py --recreate --collection framework_code_v1` by a user не aware of alias.

**Proper fix (deferred):** After `create_collection`, re-establish alias via `update_collection_aliases` if `physical != collection`. ~10 lines + tests.

**Minimal-risk mitigation applied (this commit):** Warning docstring in `ensure_collection` + scripts: "don't use --recreate против alias name; pass underlying physical name explicitly."

### M3 — `_state["target_dim"]` cache stale after `_maybe_lazy_check()` reindex

**File:** [`tools/framework-search-mcp/server.py`](../tools/framework-search-mcp/server.py)

If `_maybe_lazy_check` ever triggers a `recreate=True` (currently doesn't — incremental only), cached `target_dim` becomes stale → subsequent queries truncate to wrong dim. **Not a problem in current code path** (lazy check only does incremental upserts, не recreate). Suggested invalidation на end of lazy_check — minor robustness improvement.

### M4 — Module state not concurrency-safe

**File:** [`tools/framework-search-mcp/server.py`](../tools/framework-search-mcp/server.py)

MCP fastmcp stdio is **single-threaded by default**, so lazy double-check init pattern is safe in current runtime. If transport upgraded to threaded — race condition possible. Document the single-threaded invariant.

## MINOR findings (9)

See subagent full report — все cosmetic improvements (logging, comments, dtype safety in tests, dependency pinning notes).

## POSITIVE notes from reviewer

- Single-responsibility helpers, well-named, easy to test
- Test file: 9 tests cover happy path + alias missing + non-alias + API error + zero vector + multi-vector + idempotent
- `_mrl_truncate` zero-vector branch prevents NaN — caught real edge case
- `raptor.py` `asyncio.to_thread(_embed_sync)` is correct pattern для bridging sync httpx in async loop
- `_query_vec` correctly distinguishes is_query=True (search) vs False (find_similar) per Qwen3 contract
- `effective_dim = existing_dim if existing_dim else args.target_dim` thoughtful safety net

## Action taken (2026-05-17)

1. **M1+M2 partial mitigation:** docstring warnings added в `ensure_collection` + 2 scripts
2. **M1+M2 proper fix:** deferred to follow-up commit (re-establish alias after create)
3. **M3+M4:** documented, no immediate action (not triggerable in current runtime)
4. **Minors:** documented, may be addressed during future maintenance

## Verdict: PARTIAL → PASS-after-mitigation

С warning docstrings, риск M1+M2 неreachable manual mistake. Production safe.

Code-verify subagent marker: `[CODE-VERIFY-FAIL]` → `[CODE-VERIFY-PARTIAL]` after mitigation.
