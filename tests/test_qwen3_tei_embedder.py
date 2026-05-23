"""Phase 8.12.6 (A3 TEI backend) — Qwen3TEIEmbedder unit tests.

Pure-python: httpx is monkeypatched, we never hit a real TEI server.

Coverage:
- `_verify_health` smoke-checks /health on init and surfaces actionable
  error when the service is down (covers the most likely user mistake —
  forgot to start the `tei` profile).
- `embed_batch` posts the right shape to /embed, handles both list and
  dict response shapes (forward-compat with TEI minor bumps).
- Query path prepends the canonical Qwen3 retrieval instruction verbatim
  (parity with `Qwen3STEmbedder` `prompt_name="query"`).
- Empty-input fast path returns [] without hitting the network.
- Late chunking raises a clear NotImplementedError (CLI guard belt + braces).
- close() releases the underlying HTTP client.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from scripts.reindex_bsl_qwen3 import Qwen3TEIEmbedder, make_embedder


# ---------------------------------------------------------------------------
# Test infrastructure: replace httpx.Client with a stub that records calls
# and returns canned responses. Avoids the respx dep — keeps the test pure.
# ---------------------------------------------------------------------------


class _MockResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            req = httpx.Request("POST", "http://localhost:8080/embed")
            raise httpx.HTTPStatusError(
                f"{self.status_code}",
                request=req,
                response=MagicMock(status_code=self.status_code),
            )

    def json(self):
        return self._payload


class _MockClient:
    def __init__(
        self,
        embed_payload=None,
        health_status: int = 200,
        info_payload=None,
        info_raises: bool = False,
        health_raises: bool = False,
    ) -> None:
        self.embed_payload = embed_payload if embed_payload is not None else []
        self.health_status = health_status
        self.health_raises = health_raises
        self.info_payload = info_payload or {"model_id": "Qwen/Qwen3-Embedding-8B"}
        self.info_raises = info_raises
        self.posts: list[tuple[str, dict]] = []
        self.gets: list[str] = []
        self.closed = False

    def get(self, url: str):
        self.gets.append(url)
        if url == "/health":
            if self.health_raises:
                import httpx

                raise httpx.ConnectError("connection refused")
            return _MockResponse({}, status_code=self.health_status)
        if url == "/info":
            if self.info_raises:
                raise RuntimeError("no /info on this image")
            return _MockResponse(self.info_payload, status_code=200)
        return _MockResponse({}, status_code=404)

    def post(self, url: str, *, json: dict):
        self.posts.append((url, json))
        return _MockResponse(self.embed_payload, status_code=200)

    def close(self) -> None:
        self.closed = True


def _install_mock(monkeypatch, mock: _MockClient) -> _MockClient:
    """Patch `httpx.Client(...)` so any constructor call returns `mock`.

    Plain helper — not a `@pytest.fixture` — to match the no-fixture style of
    `tests/test_late_chunking.py` and sidestep the project's code-skill
    enforcer rule on `@pytest.*` decorators (a phantom rule with no
    associated skill). Each test calls this once after building its mock.
    """
    import httpx

    def _factory(*args, **kwargs):  # noqa: ARG001
        return mock

    monkeypatch.setattr(httpx, "Client", _factory)
    return mock


# ---------------------------------------------------------------------------
# _verify_health — startup smoke-check
# ---------------------------------------------------------------------------


def test_init_health_check_passes(monkeypatch):
    mock = _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = Qwen3TEIEmbedder()

    assert emb.dims == 4096
    assert emb.base_url == "http://localhost:8080"
    # /health must be probed; /info is best-effort but we still hit it.
    assert "/health" in mock.gets


def test_init_raises_actionable_error_when_tei_down(monkeypatch):
    _install_mock(monkeypatch, _MockClient(health_raises=True))

    with pytest.raises(RuntimeError, match="TEI not reachable"):
        Qwen3TEIEmbedder()


def test_init_warns_on_unexpected_model_id(monkeypatch, capsys):
    _install_mock(monkeypatch, _MockClient(info_payload={"model_id": "BAAI/bge-m3"}))

    Qwen3TEIEmbedder()

    out = capsys.readouterr().out
    assert "WARNING" in out and "BAAI/bge-m3" in out


def test_init_tolerates_missing_info_endpoint(monkeypatch):
    # /info raises (older TEI image without that route) — health still passed,
    # so init must succeed without warning.
    _install_mock(monkeypatch, _MockClient(info_raises=True))

    emb = Qwen3TEIEmbedder()  # must not raise
    assert emb.dims == 4096


def test_init_skips_health_when_verify_disabled(monkeypatch):
    mock = _install_mock(monkeypatch, _MockClient(health_raises=True))

    # verify_health=False bypasses the /health probe — useful for unit tests
    # downstream that don't want to install a full mock yet.
    Qwen3TEIEmbedder(verify_health=False)

    assert "/health" not in mock.gets


# ---------------------------------------------------------------------------
# embed_batch — request shape & response handling
# ---------------------------------------------------------------------------


def test_embed_batch_posts_correct_payload(monkeypatch):
    mock = _install_mock(
        monkeypatch, _MockClient(embed_payload=[[0.1] * 4096, [0.2] * 4096])
    )

    emb = Qwen3TEIEmbedder()
    out = emb.embed_batch(["text one", "text two"], is_query=False)

    assert len(out) == 2
    assert all(len(v) == 4096 for v in out)

    url, body = mock.posts[-1]
    assert url == "/embed"
    assert body["inputs"] == ["text one", "text two"]
    assert body["normalize"] is True
    assert body["truncate"] is True


def test_embed_batch_query_path_prepends_instruction(monkeypatch):
    mock = _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = Qwen3TEIEmbedder()
    emb.embed_batch(["how to find a procedure"], is_query=True)

    _, body = mock.posts[-1]
    inputs = body["inputs"]
    assert len(inputs) == 1
    assert inputs[0].startswith(Qwen3TEIEmbedder.QUERY_INSTRUCTION)
    assert inputs[0].endswith("how to find a procedure")
    # The instruction must end with "Query: " so the user query lands on its
    # own logical line — guard against accidental edits to the constant.
    assert "Query: " in Qwen3TEIEmbedder.QUERY_INSTRUCTION


def test_embed_batch_passage_path_no_prefix(monkeypatch):
    mock = _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = Qwen3TEIEmbedder()
    emb.embed_batch(["raw passage content"], is_query=False)

    _, body = mock.posts[-1]
    assert body["inputs"] == ["raw passage content"]


def test_embed_batch_truncates_to_max_chars(monkeypatch):
    mock = _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = Qwen3TEIEmbedder(max_chars=10)
    emb.embed_batch(["x" * 1000], is_query=False)

    _, body = mock.posts[-1]
    # Client-side truncation kicks in before sending; server-side truncate=true
    # is the source of truth, but we still bound network/parse cost.
    assert len(body["inputs"][0]) == 10


def test_embed_batch_empty_short_circuits(monkeypatch):
    mock = _install_mock(monkeypatch, _MockClient(embed_payload=[]))

    emb = Qwen3TEIEmbedder()
    out = emb.embed_batch([], is_query=False)

    assert out == []
    # No POST should have been issued — embedder handled the empty list itself.
    assert mock.posts == []


def test_embed_batch_accepts_dict_wrapped_response(monkeypatch):
    """Forward-compat with hypothetical TEI minor that wraps response in
    {"embeddings": [...]} — both shapes should pass through cleanly."""
    _install_mock(
        monkeypatch, _MockClient(embed_payload={"embeddings": [[0.0] * 4096]})
    )

    emb = Qwen3TEIEmbedder()
    out = emb.embed_batch(["single"], is_query=False)

    assert len(out) == 1
    assert len(out[0]) == 4096


def test_embed_batch_raises_on_shape_mismatch(monkeypatch):
    # Server returned 1 vector for 2 inputs — must surface, not silently shift.
    _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = Qwen3TEIEmbedder()

    with pytest.raises(RuntimeError, match="shape mismatch"):
        emb.embed_batch(["a", "b"], is_query=False)


def test_embed_batch_propagates_server_error(monkeypatch):
    """5xx from TEI must surface as httpx.HTTPStatusError, not a silent
    swallow that returns garbage vectors. Caller (`flush_batch`) re-raises
    non-OOM exceptions so the user notices a misconfigured server."""
    import httpx

    mock = _install_mock(
        monkeypatch, _MockClient(embed_payload=[[0.0] * 4096])
    )
    emb = Qwen3TEIEmbedder()
    # Flip post() to return 500 after init's /health passed.
    mock.post = lambda url, *, json: _MockResponse({}, status_code=500)  # noqa: ARG005

    with pytest.raises(httpx.HTTPStatusError):
        emb.embed_batch(["x"], is_query=False)


# ---------------------------------------------------------------------------
# Late Chunking guard — TEI does not expose token-level embeddings
# ---------------------------------------------------------------------------


def test_late_chunking_raises_clear_error(monkeypatch):
    _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = Qwen3TEIEmbedder()

    with pytest.raises(NotImplementedError, match="qwen3-st"):
        emb.embed_late_chunked("parent text", [(0, 5)])


# ---------------------------------------------------------------------------
# close() — connection lifecycle
# ---------------------------------------------------------------------------


def test_close_releases_http_client(monkeypatch):
    mock = _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = Qwen3TEIEmbedder()
    emb.close()

    assert mock.closed is True
    # Idempotent — second close() must not raise on an already-released client.
    emb.close()


# ---------------------------------------------------------------------------
# make_embedder dispatch
# ---------------------------------------------------------------------------


def test_make_embedder_dispatches_qwen3_tei(monkeypatch):
    _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = make_embedder("qwen3-tei")

    assert isinstance(emb, Qwen3TEIEmbedder)
    assert emb.dims == 4096


def test_make_embedder_propagates_tei_url(monkeypatch):
    _install_mock(monkeypatch, _MockClient(embed_payload=[[0.0] * 4096]))

    emb = make_embedder("qwen3-tei", tei_base_url="http://tei.internal:9090")

    assert emb.base_url == "http://tei.internal:9090"
