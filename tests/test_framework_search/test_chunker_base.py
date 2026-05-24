"""Unit tests for framework_search.chunker_base.Chunk."""

from __future__ import annotations

import hashlib
import uuid

import pytest

from src.framework_search.chunker_base import Chunk

pytestmark = pytest.mark.unit


def _make(**kwargs) -> Chunk:
    defaults = dict(
        relative_path="src/foo.py",
        content="def foo(): pass",
        language="python",
        chunk_type="function",
        line_start=1,
        line_end=1,
        mtime=1.0,
    )
    defaults.update(kwargs)
    return Chunk(**defaults)


class TestChunkIdempotency:
    def test_same_input_same_id(self) -> None:
        c1 = _make()
        c2 = _make()
        assert c1.chunk_id == c2.chunk_id

    def test_different_path_different_id(self) -> None:
        c1 = _make(relative_path="src/a.py")
        c2 = _make(relative_path="src/b.py")
        assert c1.chunk_id != c2.chunk_id

    def test_different_line_start_different_id(self) -> None:
        c1 = _make(line_start=1)
        c2 = _make(line_start=10)
        assert c1.chunk_id != c2.chunk_id

    def test_different_content_different_id(self) -> None:
        c1 = _make(content="def foo(): pass")
        c2 = _make(content="def bar(): pass")
        assert c1.chunk_id != c2.chunk_id

    def test_chunk_id_is_uuid5(self) -> None:
        c = _make()
        parsed = uuid.UUID(c.chunk_id)
        assert parsed.version == 5

    def test_chunk_id_is_string(self) -> None:
        c = _make()
        assert isinstance(c.chunk_id, str)


class TestChunkSha1:
    def test_sha1_auto_filled(self) -> None:
        content = "hello world"
        c = _make(content=content)
        expected = hashlib.sha1(content.encode("utf-8")).hexdigest()
        assert c.sha1 == expected

    def test_sha1_is_40_hex_chars(self) -> None:
        c = _make()
        assert len(c.sha1) == 40
        assert all(ch in "0123456789abcdef" for ch in c.sha1)

    def test_explicit_sha1_preserved(self) -> None:
        custom = "a" * 40
        c = _make(sha1=custom)
        assert c.sha1 == custom

    def test_explicit_chunk_id_preserved(self) -> None:
        custom_id = str(uuid.uuid4())
        c = _make(chunk_id=custom_id)
        assert c.chunk_id == custom_id


class TestChunkPayload:
    _EXPECTED_KEYS = {
        "relative_path",
        "content",
        "language",
        "chunk_type",
        "symbol_name",
        "line_start",
        "line_end",
        "mtime",
        "sha1",
    }

    def test_payload_keys(self) -> None:
        c = _make()
        assert set(c.to_payload().keys()) == self._EXPECTED_KEYS

    def test_payload_exactly_9_keys(self) -> None:
        c = _make()
        assert len(c.to_payload()) == 9

    def test_payload_values_match(self) -> None:
        c = _make(relative_path="src/x.py", content="x=1", line_start=5, line_end=5)
        p = c.to_payload()
        assert p["relative_path"] == "src/x.py"
        assert p["content"] == "x=1"
        assert p["line_start"] == 5
        assert p["sha1"] == c.sha1

    def test_payload_symbol_name_none(self) -> None:
        c = _make(symbol_name=None)
        assert c.to_payload()["symbol_name"] is None

    def test_payload_no_chunk_id(self) -> None:
        c = _make()
        assert "chunk_id" not in c.to_payload()


class TestChunkEdgeCases:
    def test_empty_content_sha1_filled(self) -> None:
        c = _make(content="")
        expected = hashlib.sha1(b"").hexdigest()
        assert c.sha1 == expected

    def test_empty_content_chunk_id_filled(self) -> None:
        c = _make(content="")
        assert len(c.chunk_id) > 0
        uuid.UUID(c.chunk_id)  # must not raise

    def test_unicode_content_sha1(self) -> None:
        content = "привет мир"
        c = _make(content=content)
        expected = hashlib.sha1(content.encode("utf-8")).hexdigest()
        assert c.sha1 == expected

    def test_expected_dims_constant(self) -> None:
        assert Chunk.EXPECTED_DIMS == 4096
