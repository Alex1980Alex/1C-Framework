"""Unit tests for framework_search.embedder.FrameworkTEIEmbedder."""

from __future__ import annotations

from unittest.mock import MagicMock

import httpx
import pytest

from src.framework_search.embedder import QUERY_INSTRUCTION, FrameworkTEIEmbedder

pytestmark = pytest.mark.unit

FAKE_DIM = 4096
_FAKE_VEC: list[float] = [0.0] * FAKE_DIM


def _make_embedder() -> FrameworkTEIEmbedder:
    """Embedder with mocked httpx client — no real network needed."""
    e = FrameworkTEIEmbedder.__new__(FrameworkTEIEmbedder)
    e.base_url = "http://localhost:8080"
    e.client_batch_size = 32
    e.max_chars = 4096
    e._dims = None
    e._client = MagicMock()
    return e


@pytest.fixture()
def fast_retry():
    """Replace tenacity sleep with no-op so retry tests run instantly."""
    retry_obj = FrameworkTEIEmbedder._post_embed_sub.retry
    orig = retry_obj.sleep
    retry_obj.sleep = lambda _: None
    try:
        yield
    finally:
        retry_obj.sleep = orig


class TestEmbedBatchBasic:
    def test_empty_input_returns_empty(self) -> None:
        emb = _make_embedder()
        assert emb.embed_batch([]) == []

    def test_returns_4096d_vectors(self) -> None:
        emb = _make_embedder()
        emb._post_embed_sub = MagicMock(return_value=[_FAKE_VEC])
        result = emb.embed_batch(["hello"])
        assert len(result) == 1
        assert len(result[0]) == FAKE_DIM

    def test_dims_cached_after_first_call(self) -> None:
        emb = _make_embedder()
        emb._post_embed_sub = MagicMock(return_value=[_FAKE_VEC])
        assert emb._dims is None
        emb.embed_batch(["hello"])
        assert emb._dims == FAKE_DIM

    def test_dims_property_default_4096_before_call(self) -> None:
        emb = _make_embedder()
        assert emb.dims == FAKE_DIM

    def test_multiple_texts_count_preserved(self) -> None:
        emb = _make_embedder()
        emb._post_embed_sub = MagicMock(return_value=[_FAKE_VEC, _FAKE_VEC, _FAKE_VEC])
        assert len(emb.embed_batch(["a", "b", "c"])) == 3

    def test_text_truncated_to_max_chars(self) -> None:
        emb = _make_embedder()
        emb.max_chars = 5
        captured: list[str] = []

        def capture(sub: list[str]) -> list[list[float]]:
            captured.extend(sub)
            return [_FAKE_VEC] * len(sub)

        emb._post_embed_sub = capture
        emb.embed_batch(["hello world"])
        assert captured[0] == "hello"


class TestEmbedBatchQueryMode:
    def test_is_query_prepends_instruction(self) -> None:
        emb = _make_embedder()
        captured: list[str] = []

        def capture(sub: list[str]) -> list[list[float]]:
            captured.extend(sub)
            return [_FAKE_VEC] * len(sub)

        emb._post_embed_sub = capture
        emb.embed_batch(["find me"], is_query=True)
        assert captured[0].startswith(QUERY_INSTRUCTION)
        assert captured[0].endswith("find me")

    def test_passage_mode_no_prefix(self) -> None:
        emb = _make_embedder()
        captured: list[str] = []

        def capture(sub: list[str]) -> list[list[float]]:
            captured.extend(sub)
            return [_FAKE_VEC] * len(sub)

        emb._post_embed_sub = capture
        emb.embed_batch(["passage text"], is_query=False)
        assert not captured[0].startswith("Instruct:")

    def test_query_instruction_has_required_markers(self) -> None:
        assert "Instruct:" in QUERY_INSTRUCTION
        assert "Query:" in QUERY_INSTRUCTION


class TestEmbedBatchBatching:
    def test_large_batch_split_into_sub_batches(self) -> None:
        emb = _make_embedder()
        emb.client_batch_size = 2
        call_sizes: list[int] = []

        def capture(sub: list[str]) -> list[list[float]]:
            call_sizes.append(len(sub))
            return [_FAKE_VEC] * len(sub)

        emb._post_embed_sub = capture
        emb.embed_batch(["a", "b", "c", "d", "e"])
        assert call_sizes == [2, 2, 1]

    def test_single_call_when_batch_fits(self) -> None:
        emb = _make_embedder()
        emb.client_batch_size = 10
        call_count = [0]

        def capture(sub: list[str]) -> list[list[float]]:
            call_count[0] += 1
            return [_FAKE_VEC] * len(sub)

        emb._post_embed_sub = capture
        emb.embed_batch(["x", "y", "z"])
        assert call_count[0] == 1


class TestEmbedBatchRetry:
    def test_transport_error_retries_and_recovers(self, fast_retry: None) -> None:
        emb = FrameworkTEIEmbedder.__new__(FrameworkTEIEmbedder)
        emb.base_url = "http://localhost:8080"
        emb.client_batch_size = 32
        emb.max_chars = 4096
        emb._dims = None
        call_count = [0]

        def post_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] < 3:
                raise httpx.TransportError("temporary failure")
            mock_resp = MagicMock()
            mock_resp.json.return_value = [_FAKE_VEC]
            return mock_resp

        emb._client = MagicMock()
        emb._client.post.side_effect = post_side_effect

        result = emb.embed_batch(["text"])
        assert call_count[0] == 3
        assert len(result) == 1

    def test_transport_error_reraises_after_exhausting_attempts(
        self, fast_retry: None
    ) -> None:
        emb = FrameworkTEIEmbedder.__new__(FrameworkTEIEmbedder)
        emb.base_url = "http://localhost:8080"
        emb.client_batch_size = 32
        emb.max_chars = 4096
        emb._dims = None
        emb._client = MagicMock()
        emb._client.post.side_effect = httpx.TransportError("always fails")

        with pytest.raises(httpx.TransportError):
            emb.embed_batch(["text"])


class TestEmbedBatchEdgeCases:
    def test_context_manager_closes_client(self) -> None:
        emb = _make_embedder()
        with emb:
            pass
        emb._client.close.assert_called_once()

    def test_close_closes_client(self) -> None:
        emb = _make_embedder()
        emb.close()
        emb._client.close.assert_called_once()
