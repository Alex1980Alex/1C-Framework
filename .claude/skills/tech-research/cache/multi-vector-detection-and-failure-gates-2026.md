---
topic: multi-vector-detection-and-failure-gates-2026
domain: tech-research
created: 2026-05-17
last_verified: 2026-05-17
version: qdrant-client 1.13+, pytest 8.4+, Python 3.11+
sources:
  - https://qdrant.tech/documentation/manage-data/collections/
  - https://docs.pytest.org/en/stable/how-to/failures.html
  - https://github.com/AlmogBaku/pytest-evals
  - https://realpython.com/python-constants/
  - https://discuss.python.org/t/best-practices-for-placing-common-enumeration-constants-in-a-python-package/38519
keywords: [qdrant, multi-vector, named-vectors, vectors_config, isinstance-dict, failure-ratio-gate, eval-abort-threshold, shared-constants, _common-module, DRY, dict-deterministic-key, alphabetical-sort, type-hints, log-cadence]
---

# Three hardening patterns — Qdrant multi-vector, eval failure gates, shared constants

Research для roadmap 260516 review fixes — applied 2026-05-17.

## 1. Multi-vector Qdrant collection detection

**Pattern** (per qdrant-client docs): `vectors_config` is either a single `VectorParams` (unnamed/legacy) OR a `dict` of named `VectorParams`. Detect via `isinstance`.

```python
def detect_vector_config(coll_info, vector_name: str | None = None):
    vectors = coll_info.config.params.vectors
    if vectors is None:
        raise RuntimeError("Collection has no vectors_config (None)")
    if isinstance(vectors, dict):
        # Multi-vector — pick deterministically
        if vector_name and vector_name in vectors:
            return vectors[vector_name].size, vector_name
        first_name = sorted(vectors.keys())[0]  # alphabetical = deterministic
        return vectors[first_name].size, first_name
    return vectors.size, None  # single-vector legacy
```

**Key principles**:
- `sorted(vectors.keys())[0]` for deterministic auto-selection (not `next(iter(...))` which is insertion-order dependent)
- Always allow `--vector-name` CLI override
- Warn (not silent) on auto-pick to avoid surprise

**When upserting to target collections**: must preserve named-vector shape if source was named:
```python
if resolved_name:
    point.vector = {resolved_name: truncated_vec}
else:
    point.vector = truncated_vec
```

## 2. Failure-ratio gate для eval scripts

**Anti-pattern**: silent verdict on partial results when 50%+ items fail (TEI 5xx storm, network blip). Computes mean on degraded sample.

**Pattern** (per pytest-evals + custom eval patterns):
```python
MIN_SUCCESS_RATIO: Final[float] = 0.8

def evaluate(...) -> dict:
    scores = [...]  # collected per-item
    success_ratio = len(scores) / len(items)
    if success_ratio < MIN_SUCCESS_RATIO:
        return {"error": f"failure_ratio_gate: {success_ratio:.2f} < {MIN_SUCCESS_RATIO}"}
    return {"mean_score": sum(scores)/len(scores), ...}
```

**Caller behavior**: don't compute verdict / publish results when `"error" in result`. Skip to next dim or abort batch.

**Threshold tuning**:
- 0.8 (80%) — common default for eval scripts (≥80% of sample valid)
- 0.95 — for strict quality gates (CI regression)
- 0.5 — for exploratory/preview runs

## 3. Shared constants module pattern (DRY)

**Anti-pattern**: same `TEI_URL`/`QUERY_PREFIX`/`MAX_TOKENS` constants duplicated в 3+ files. Drift over time.

**Pattern** (per Real Python "Constants" guide):
- Underscore-prefixed module name (`_eval_common.py`) marks it as internal helper, not public API
- All-caps `UPPER_SNAKE_CASE` for module-level constants
- `Final[T]` type hint via `typing.Final`
- Import: `from _eval_common import TEI_URL, QUERY_PREFIX`

```python
# scripts/_eval_common.py
from typing import Final
import os

TEI_URL: Final[str] = os.environ.get("TEI_URL", "http://localhost:8080") + "/embed"
QUERY_PREFIX: Final[str] = "Instruct: ...\nQuery: "

def embed_query(query: str, http_client) -> list[float]:
    """Shared helper — single source of truth for TEI request shape."""
    payload = {"inputs": [QUERY_PREFIX + query]}
    resp = http_client.post(TEI_URL, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()[0]
```

**File naming convention**: `_` prefix marks internal, `_common.py` / `_helpers.py` / `_shared.py` all acceptable.

## Anti-patterns avoided

| Plохо | Почему |
|---|---|
| `next(iter(dict.values()))` для multi-vector | Insertion-order dependent, non-deterministic across runs |
| Silent partial-result verdict | Publishes MIGRATE/PASS on degraded sample (TEI 5xx storm masks real result) |
| Duplicating `TEI_URL` в 3+ files | Drift over time; one place updates, others stale |
| `total % batch_size_dependent_const == 0` для log cadence | Brittle to batch_size changes; use counter `if batch_idx % N == 0` instead |
| Function без type hints | mypy ratchet gate cannot improve; reviewer cannot verify contracts |

## Source attribution

- **[Docs]** [Qdrant Collections](https://qdrant.tech/documentation/manage-data/collections/) — vectors_config dict vs VectorParams syntax
- **[Docs]** [pytest failure handling](https://docs.pytest.org/en/stable/how-to/failures.html) — pytest_assertrepr_compare hooks, abort patterns
- **[GitHub]** [AlmogBaku/pytest-evals](https://github.com/AlmogBaku/pytest-evals) — production eval framework with threshold gates
- **[Guide]** [Real Python Constants](https://realpython.com/python-constants/) — `Final` type hint, UPPER_SNAKE_CASE, module-level pattern
- **[Discussion]** [Python.org best-practices for constants](https://discuss.python.org/t/best-practices-for-placing-common-enumeration-constants-in-a-python-package/38519) — _common.py convention
