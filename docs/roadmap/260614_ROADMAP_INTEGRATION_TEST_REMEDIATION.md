# 260614 — Integration-Test Remediation (roadmap)

> Status: **OPEN**. Created 2026-06-14 after greening the non-gating `Integration
> Tests` CI badge via interim quarantine (skip-with-reason). This roadmap tracks
> the real rewrites needed to un-skip each quarantined test. Analogous to the
> 260608 unit-test remediation, but for the integration suite.

## Context

`Integration Tests` (in [`ci.yml`](../../.github/workflows/ci.yml)) is
`continue-on-error: true` — **non-gating** (the `ci.yml` run is `success` even
when it fails; merges are never blocked). The suite was **57 passed / 22 failed**:
the 22 are drifted vs current source (removed classes, sync-for-async mocks,
broken MagicMock fixtures, cross-thread SQLite, live-service deps).

Two-round quarantine landed the failing tests as **documented skips** (badge
green, 57 passing preserved, debt tracked here):
- Round 1 (PR #80): `test_indexing.py` (IndexingPipeline removed), `test_search.py`
  (sync-for-async fixture), `test_real_bsl_client.py` (`importorskip("multilspy")`).
- Round 2 (this PR): see clusters below.

## Quarantined clusters (root cause → fix approach)

| Test(s) | Root cause | Fix approach (to un-skip) |
|---|---|---|
| `test_plan_execute.py` (module, 13/14) | mocks return `MagicMock`s the agent `.join()`s (`replanner.py:63`, `synthesizer.py:56/69`) | Rewrite `mock_llm`/`mock_search_manager`/`mock_tools` to feed the executor→state→synthesizer flow proper `str`/dict results matching current `PlanExecuteState`. |
| `test_api.py::TestAPIEndpoints` (7) | TestClient asserts drifted + shared `mock_qdrant_client` fixture is sync-API (`.search`/`.upsert`) for the now-async provider (`AsyncQdrantClient.query_points`); patch target `qdrant.QdrantClient` no longer exists | Rewrite `tests/conftest.py` `mock_qdrant_client` to `AsyncMock` patching `qdrant_client.AsyncQdrantClient` + update endpoint assertions. (High-leverage: this fixture also affected `test_search.py`.) |
| `test_proposition.py::test_end_to_end_proposition_workflow` (1) | references removed `RAGAgent` / `agents.conversation` modules | Re-point to current agent API or delete if the workflow no longer exists. |
| `test_visual.py` (2) | visual model mock passes a `MagicMock` into `torch.Tensor.to(device)` | Mock the ColPali model/device boundary so `.to()` receives a real device/tensor. |
| `test_post_commit_reindex.py::test_core_hooks_path_set_to_scripts_git_hooks` (1) | cross-thread SQLite (`SQLite objects ... same thread`) + git-hooks-path assertion drift; flaky | Use a per-thread connection / `check_same_thread`-safe access; update the hooks-path assertion to current `core.hooksPath`. |
| `test_pdf_docs_chains_live.py::TestA5DimContract::test_alias_query_dim_matches` (1) | requires live TEI + Qdrant, absent in Linux CI | Add a service-availability skip guard (skip when TEI/Qdrant unreachable) so it runs only where services exist. |

## Acceptance (definition of done)

- Each quarantined test is rewritten against current APIs and **un-skipped** (skip
  marker removed), OR converted to a clean service-availability `importorskip`/guard
  where it legitimately needs live infra.
- `pytest tests/integration -m integration` (with services up) → 0 failed, skips
  only for genuine service-gated tests.
- The `mock_qdrant_client` conftest fixture is async-correct (unblocks the API +
  search clusters together — do this first, highest leverage).

## Notes

- Integration stays non-gating (`continue-on-error`) until the suite is reliable;
  flipping it to gating is a separate decision after this remediation.
- `codecov/patch` is unrelated and already green on `master` (it was PR #77's
  historical per-PR diff-coverage status).
