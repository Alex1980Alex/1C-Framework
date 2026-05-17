# Follow-Up TODOs (DEFERRED to separate session, 2026-05-17)

> **Origin:** Subagent code review session 2026-05-17 ([docs/analysis/subagent_code_review_2026_05_17.md](../analysis/subagent_code_review_2026_05_17.md)) + pre-commit mypy ratchet discoveries.
> **Status:** ALL DEFERRED to dedicated session. Current production stable, no urgent action needed.

## Содержание

- [Item 1 — M1+M2 proper fix: alias re-establish after recreate](#item-1--m1m2-proper-fix)
- [Item 2 — Minor improvements from subagent review](#item-2--minor-improvements)
- [Item 3 — mypy baseline gap: chunker_base + embedder type errors](#item-3--mypy-baseline-gap)
- [Combined session plan](#combined-session-plan)
- [Acceptance criteria](#acceptance-criteria)

---

## Item 1 — M1+M2 proper fix

**Bug:** `ensure_collection(recreate=True)` on alias name destroys alias and creates a standalone physical collection under the alias name. Currently mitigated with WARNING docstring only.

**Reproduction (manual):**
```bash
# Сейчас в индексере (если запустить):
python scripts/index_framework.py --recreate --collection framework_code_v1
# → drops framework_code_v1_mrl_1024 (the physical)
# → alias framework_code_v1 → framework_code_v1_mrl_1024 becomes invalid
# → creates new physical "framework_code_v1" (4096d, no alias)
# Result: MRL setup destroyed, alias gone, retrieval breaks until manual recovery
```

**Proper fix (~15 LoC + 1-2 tests):**

```python
# src/framework_search/indexer.py:ensure_collection

def ensure_collection(client, collection, dims, recreate=False):
    """Create collection if missing; drop+create if recreate=True.

    Alias-aware: if `collection` is an alias, recreate operates on underlying
    physical, then re-establishes the alias.
    """
    from qdrant_client.http.models import (
        CreateAlias, CreateAliasOperation, UpdateCollectionsAliases,
    )

    exists = client.collection_exists(collection)
    if exists and recreate:
        physical = resolve_physical_collection(client, collection)
        was_alias = physical != collection
        if was_alias:
            logger.info("indexer: '%s' alias->'%s'; recreating physical", collection, physical)
        client.delete_collection(physical)

        client.create_collection(
            collection_name=physical,
            vectors_config=models.VectorParams(size=dims, distance=models.Distance.COSINE),
        )

        if was_alias:
            # Re-establish alias destroyed by delete_collection
            client.update_collection_aliases(change_aliases_operations=[
                CreateAliasOperation(create_alias=CreateAlias(
                    collection_name=physical, alias_name=collection,
                )),
            ])
            logger.info("indexer: re-established alias '%s' -> '%s'", collection, physical)
        return

    if not exists:
        # Brand new collection: create directly under name (no alias yet)
        client.create_collection(
            collection_name=collection,
            vectors_config=models.VectorParams(size=dims, distance=models.Distance.COSINE),
        )
```

**Affected files (3, same pattern):**
- [src/framework_search/indexer.py](../../src/framework_search/indexer.py) — `ensure_collection()` (primary)
- [scripts/reembed_collection.py](../../scripts/reembed_collection.py) — `client.upsert(collection_name=args.collection, ...)` should use `physical` after recreate, OR alias re-established (preferred)
- [scripts/reindex_pdf_documents.py](../../scripts/reindex_pdf_documents.py) — same pattern as reembed_collection.py

**Tests to add:**
- `tests/test_framework_search/test_indexer_mrl.py::test_ensure_collection_recreates_underlying_physical_when_alias`
- `tests/test_framework_search/test_indexer_mrl.py::test_ensure_collection_reestablishes_alias_after_recreate`
- Both use MagicMock with proper alias setup

**Effort:** ~30 min (code + tests + smoke verification with actual Qdrant alias).

**Risk:** Low — additive change, current WARNING docstring path remains valid for backwards compat.

---

## Item 2 — Minor improvements from subagent review

См. [docs/analysis/subagent_code_review_2026_05_17.md](../analysis/subagent_code_review_2026_05_17.md) MINOR section (9 items, cosmetic).

**Priority order для batch fixing:**

1. **m1:** `resolve_physical_collection` swallows all exceptions silently — add `logger.debug("get_aliases failed: %s", e)` (1 line)
2. **m3:** RAPTOR `_embed_text` creates fresh `FrameworkTEIEmbedder` per call — cache via `self._embedder` lazy attribute (~5 lines + close in `__aexit__` if class is async-context-managed)
3. **m4:** `reembed_collection.py` `effective_dim` warning misleading — split into 2 separate log lines for alias-resolution vs dim-coercion cases (~3 lines)
4. **m5:** `reindex_pdf_documents.py` non-recreate path skips alias check — probe embedder dim before main loop, compare against `target_dim`, fail fast on mismatch (~10 lines)
5. **m9:** `indexer.py:155` comment on assumption that short vectors are pre-normalized (1 line)

**Skip (out of scope или risk-free как есть):**
- m2: `resolve_collection_dim` doesn't catch errors — propagates correctly to callers (current behavior preferred)
- m6: `query_points.points` is correct for qdrant-client >= 1.7 (pinned, no risk)
- m7: test uses `dict` mock — works correctly, real `VectorParamsMap` also matches `isinstance(_, dict)`
- m8: `test_mrl_truncate_zero_vector_no_nan` — current assertions sufficient

**Effort:** ~30 min total (small edits, no new tests required for cosmetic changes).

---

## Item 3 — mypy baseline gap

**Issue:** Pre-commit `mypy` hook fails when editing `src/framework_search/indexer.py` due to transitive type errors in imported modules:
- `src/framework_search/chunker_base.py:38` — `Missing type parameters for generic type "dict"` `[type-arg]`
- `src/framework_search/embedder.py:61` — `Function is missing a type annotation for one or more arguments` `[no-untyped-def]`
- `src/framework_search/embedder.py:85` — `Untyped decorator makes function "_post_embed_sub" untyped` `[misc]`

Hat baseline (`mypy-baseline.txt`) has entries `chunker_base.py:0` and `embedder.py:0` (line-stripped form) — but pre-commit mypy hook **may not be using mypy_baseline filter**. Investigation needed.

**Investigation tasks:**

1. Check `.pre-commit-config.yaml` `mypy` hook command — does it use `mypy --baseline-file ...` or `python -m mypy_baseline filter`?
2. If baseline NOT plugged in: configure pre-commit to filter through mypy_baseline
3. If baseline IS plugged but doesn't match: investigate why line-stripped entries don't suppress

**Alternative (faster but less clean):** Fix the actual type errors:

```python
# chunker_base.py:38 — add type parameters
metadata: dict[str, Any] = field(default_factory=dict)  # was: metadata: dict

# embedder.py:61 — annotate parameters
def _build_post_payload(self, texts: list[str], is_query: bool) -> dict[str, Any]:
    # ...

# embedder.py:85 — add type to decorator's wrapped function
@retry(...)
def _post_embed_sub(self, payload: dict[str, Any]) -> list[list[float]]:
    # ...
```

**Effort:**
- Investigation path: ~15-30 min
- Direct fix path: ~30-45 min (3 file edits + test)

**Risk:** Low — pure type annotation additions, no behavior change.

**Why deferred:** Current commits work via auto-save bypass (auto-save doesn't run pre-commit hooks). Manual commits with edits to indexer.py block until resolved. Pragmatic mitigation = use auto-save for indexer.py changes OR fix baseline plumbing.

---

## Combined session plan

**Recommended order:**
1. Item 3 (mypy baseline) first — unblocks future indexer.py commits
2. Item 1 (M1+M2 fix) — proper bug fix using clean commits
3. Item 2 (minors) — bundle as single commit "subagent review minors"

**Estimated total:** 1.5-2h.

**Skill check before starting:**
- `Skill('qdrant-operations')` — alias API patterns
- `Skill('framework-search')` — indexer.py context
- `Skill('code-verify')` — verify M1+M2 fix via test + smoke

---

## Acceptance criteria

- [ ] Item 1: `ensure_collection(recreate=True)` on alias correctly recreates underlying physical AND re-establishes alias. Smoke verified on real Qdrant.
- [ ] Item 1: 2 new tests in `test_indexer_mrl.py` PASS (mock-based, no real Qdrant required for CI)
- [ ] Item 1: WARNING docstring removed from `ensure_collection` (bug is now fixed)
- [ ] Item 2: 5 minor improvements applied (m1, m3, m4, m5, m9), commit message references which
- [ ] Item 3: Pre-commit `mypy` hook works with mypy_baseline filter OR transitive errors fixed at source
- [ ] All changes pushed to origin

---

## Связанные документы

- [docs/analysis/subagent_code_review_2026_05_17.md](../analysis/subagent_code_review_2026_05_17.md) — full subagent review report
- [src/framework_search/indexer.py](../../src/framework_search/indexer.py) — primary file with M1+M2 + WARNING docstring
- [tests/test_framework_search/test_indexer_mrl.py](../../tests/test_framework_search/test_indexer_mrl.py) — existing tests (9 cases), needs +2 for alias-recreate
- [mypy-baseline.txt](../../mypy-baseline.txt) — current baseline (1920 lines)

---

## Decision (2026-05-17)

**DEFERRED to dedicated follow-up session.** Triggers для re-evaluation:
1. Plan to use `--recreate` against aliased collection manually
2. New mypy ratchet failure blocks unrelated commit work
3. Periodic code-debt cleanup session scheduled
4. Pull Request prep — clean up before merge to main
