"""Unit tests for the TEI embedding provider (Qwen3-Embedding-8B 4096d).

No live TEI server: the HTTP POST is mocked. Verifies factory dispatch, the
QUERY_INSTRUCTION calibration prefix, and sub-batching at TEI's 32-input cap
(batch>32 -> HTTP 413, see memory feedback_tei_batch_size_limit).
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from src.pdf_framework.config import EmbeddingSettings

pytestmark = pytest.mark.unit


def _settings(**overrides) -> EmbeddingSettings:
    defaults = {"provider": "tei", "model": "Qwen/Qwen3-Embedding-8B", "dimensions": 4096}
    defaults.update(overrides)
    return EmbeddingSettings(**defaults)


class _FakeResp:
    def __init__(self, n: int, dims: int):
        self._n, self._dims = n, dims

    def raise_for_status(self):
        return None

    def json(self):
        return [[0.01 * (i + 1)] * self._dims for i in range(self._n)]


def _engine_with_mock(settings, recorder):
    from src.pdf_framework.embeddings.providers.tei import TEIEmbeddingEngine

    eng = TEIEmbeddingEngine(settings)

    async def fake_post(url, json):  # noqa: A002 -- mirrors httpx.post(json=...) kw
        recorder.append(json["inputs"])
        return _FakeResp(len(json["inputs"]), eng.get_dimensions())

    eng._client.post = AsyncMock(side_effect=fake_post)
    return eng


def test_factory_dispatches_tei():
    from src.pdf_framework.embeddings import get_embedding_engine
    from src.pdf_framework.embeddings.providers.tei import TEIEmbeddingEngine

    eng = get_embedding_engine(_settings())
    assert isinstance(eng, TEIEmbeddingEngine)
    assert eng.get_dimensions() == 4096
    assert eng.get_model_name() == "Qwen/Qwen3-Embedding-8B"


def test_embed_batch_prefix_and_dims():
    calls: list = []
    eng = _engine_with_mock(_settings(), calls)
    out = asyncio.run(eng.embed_batch(["alpha", "beta"]))
    assert len(out) == 2 and len(out[0]) == 4096
    # Every input carries the Qwen3 QUERY_INSTRUCTION prefix.
    from src.pdf_framework.embeddings.providers.tei import QUERY_INSTRUCTION

    assert all(s.startswith(QUERY_INSTRUCTION) for s in calls[0])
    assert calls[0][0].endswith("alpha")


def test_embed_batch_subbatches_at_32():
    calls: list = []
    eng = _engine_with_mock(_settings(), calls)
    out = asyncio.run(eng.embed_batch([f"t{i}" for i in range(70)]))
    assert len(out) == 70
    # 70 inputs -> 32 + 32 + 6 (never a single request over the TEI cap).
    assert [len(batch) for batch in calls] == [32, 32, 6]
    assert all(len(batch) <= 32 for batch in calls)


def test_embed_empty():
    eng = _engine_with_mock(_settings(), [])
    assert asyncio.run(eng.embed_batch([])) == []
