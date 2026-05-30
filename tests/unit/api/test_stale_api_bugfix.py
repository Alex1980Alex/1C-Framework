"""Regression tests for the stale-API bugfix (roadmap §21.4 / срез G finding).

Covers two routers whose endpoints called APIs that no longer exist:

- `graph.py` Phase 61 endpoints (`/graph/incremental-update`, `/graph/incremental/detect-changes`)
  were dead-on-arrival (called `vector_store.get_chunks`, `IncrementalGraphUpdater.update_document`,
  an `entity_extractor` kwarg — none of which exist). They now return an explicit HTTP 501
  instead of crashing with AttributeError.
- `jobs.py` used the old aioredis API (`iscan`, `hgetall(encoding=...)`) and treated
  `enqueue_job()`'s `Job | None` result as the id string. Fixed to `scan_iter`, manual
  decode (`_decode_hash`), and `job.job_id` with a None-guard.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.auth.dependencies import get_current_role, get_current_tenant


# --------------------------------------------------------------------------- #
# graph.py — incremental endpoints now return 501 instead of crashing
# --------------------------------------------------------------------------- #


@pytest.fixture
def graph_client() -> TestClient:
    from src.api.routes import graph

    app = FastAPI()
    app.include_router(graph.router)
    # incremental-update runs the IDOR guard via Depends; make it pass.
    app.dependency_overrides[get_current_tenant] = lambda: "default"
    app.dependency_overrides[get_current_role] = lambda: "admin"
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_incremental_update_returns_501(graph_client: TestClient) -> None:
    resp = graph_client.post("/graph/incremental-update", params={"document_id": "doc-1"})
    assert resp.status_code == 501
    assert "not implemented" in resp.json()["detail"].lower()


@pytest.mark.unit
def test_detect_changes_returns_501(graph_client: TestClient) -> None:
    resp = graph_client.get("/graph/incremental/detect-changes", params={"document_id": "doc-1"})
    assert resp.status_code == 501
    assert "not implemented" in resp.json()["detail"].lower()


# --------------------------------------------------------------------------- #
# jobs.py — _decode_hash handles bytes/str/mixed (arq does not decode_responses)
# --------------------------------------------------------------------------- #


@pytest.mark.unit
def test_decode_hash_bytes() -> None:
    from src.api.routes.jobs import _decode_hash

    assert _decode_hash({b"status": b"pending", b"progress": b"50"}) == {
        "status": "pending",
        "progress": "50",
    }


@pytest.mark.unit
def test_decode_hash_str_passthrough() -> None:
    from src.api.routes.jobs import _decode_hash

    assert _decode_hash({"status": "complete"}) == {"status": "complete"}


@pytest.mark.unit
def test_decode_hash_mixed_and_nonstr_values() -> None:
    from src.api.routes.jobs import _decode_hash

    assert _decode_hash({b"k": 5, "x": b"y"}) == {"k": "5", "x": "y"}


@pytest.mark.unit
def test_decode_hash_empty() -> None:
    from src.api.routes.jobs import _decode_hash

    assert _decode_hash({}) == {}


# --------------------------------------------------------------------------- #
# jobs.py — enqueue uses job.job_id (not the Job object) and guards None
# --------------------------------------------------------------------------- #


class _FakeJob:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id


def _enqueue_client(monkeypatch: pytest.MonkeyPatch, enqueue_return: object) -> TestClient:
    from src.api.routes import jobs

    monkeypatch.setattr(jobs.settings.queue, "enabled", True, raising=False)

    fake_redis = AsyncMock()
    fake_redis.enqueue_job = AsyncMock(return_value=enqueue_return)
    fake_redis.hset = AsyncMock()
    fake_redis.expire = AsyncMock()

    async def _fake_get_redis() -> object:
        return fake_redis

    monkeypatch.setattr(jobs, "get_redis", _fake_get_redis)

    app = FastAPI()
    app.include_router(jobs.router)
    app.dependency_overrides[get_current_tenant] = lambda: "default"
    app.dependency_overrides[get_current_role] = lambda: "admin"
    return TestClient(app, raise_server_exceptions=False)


@pytest.mark.unit
def test_enqueue_returns_job_id_string(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: previously returned the Job object (repr), not job.job_id."""
    client = _enqueue_client(monkeypatch, _FakeJob("job-abc123"))
    resp = client.post(
        "/jobs/enqueue",
        json={"task_name": "index_document", "task_kwargs": {}, "tenant_id": "default"},
    )
    assert resp.status_code == 200
    assert resp.json()["job_id"] == "job-abc123"


@pytest.mark.unit
def test_enqueue_none_job_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    """Regression: enqueue_job() -> None must not be used as an id (now 409)."""
    client = _enqueue_client(monkeypatch, None)
    resp = client.post(
        "/jobs/enqueue",
        json={"task_name": "index_document", "task_kwargs": {}, "tenant_id": "default"},
    )
    assert resp.status_code == 409
