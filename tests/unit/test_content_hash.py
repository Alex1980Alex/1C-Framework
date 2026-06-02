"""Unit tests for the canonical cross-store content hash (§26 P0, D0.1).

Covers:
- hash_content / content_key determinism + content/description fallback
- MemoryCube auto-derives content_hash and propagates it to all 3 projections
- to_dict/from_dict round-trip; from_dict recomputes when content_hash missing
- parity with the dedupe script's content_key (single source of truth)
"""

from __future__ import annotations

import pytest

from src.memory.orchestrator.content_hash import (
    HASH_WIDTH,
    content_key,
    content_text,
    hash_content,
)
from src.memory.orchestrator.memcube import ContentType, MemoryCube

pytestmark = pytest.mark.unit


# ===== content_hash module =====


class TestContentHash:
    def test_deterministic(self):
        assert hash_content("hello") == hash_content("hello")

    def test_width(self):
        assert len(hash_content("anything")) == HASH_WIDTH

    def test_distinct_content_distinct_hash(self):
        assert hash_content("a") != hash_content("b")

    def test_empty_and_none_safe(self):
        assert len(hash_content("")) == HASH_WIDTH
        assert hash_content(None) == hash_content("")  # type: ignore[arg-type]

    def test_cyrillic_does_not_raise(self):
        h = hash_content("Запись набора записей УК")
        assert len(h) == HASH_WIDTH

    def test_content_text_prefers_content(self):
        assert content_text({"content": "C", "description": "D"}) == "C"

    def test_content_text_falls_back_to_description(self):
        assert content_text({"description": "D"}) == "D"

    def test_content_key_uses_content_text(self):
        assert content_key({"content": "x"}) == hash_content("x")
        # content/description fallback means these two payloads collide on purpose
        assert content_key({"description": "x"}) == hash_content("x")


# ===== MemoryCube integration =====


class TestMemoryCubeContentHash:
    def test_auto_derived_on_init(self):
        cube = MemoryCube(content="some fact")
        assert cube.content_hash == hash_content("some fact")

    def test_explicit_hash_respected(self):
        cube = MemoryCube(content="x", content_hash="deadbeefdeadbeef")
        assert cube.content_hash == "deadbeefdeadbeef"

    def test_refresh_hash_after_content_change(self):
        cube = MemoryCube(content="old")
        old = cube.content_hash
        cube.content = "new"
        assert cube.refresh_hash() != old
        assert cube.content_hash == hash_content("new")

    def test_round_trip_dict_preserves_hash(self):
        cube = MemoryCube(content="round trip")
        restored = MemoryCube.from_dict(cube.to_dict())
        assert restored.content_hash == cube.content_hash

    def test_from_dict_recomputes_when_missing(self):
        data = MemoryCube(content="recompute me").to_dict()
        del data["content_hash"]
        restored = MemoryCube.from_dict(data)
        assert restored.content_hash == hash_content("recompute me")

    @pytest.mark.parametrize(
        "projection",
        ["to_vector_memory_payload", "to_ai_memory_row", "to_skill_learning_record"],
    )
    def test_projection_carries_hash(self, projection: str):
        cube = MemoryCube(content="projected fact", content_type=ContentType.RULE)
        payload = getattr(cube, projection)()
        assert payload["content_hash"] == cube.content_hash

    def test_wiki_round_trip_preserves_hash(self):
        cube = MemoryCube(content="wiki fact")
        restored = MemoryCube.from_wiki_page(cube.to_wiki_page())
        assert restored.content_hash == cube.content_hash

    def test_cross_store_same_fact_same_hash(self):
        """Same content in two different stores must share the join key."""
        episodic = MemoryCube(content="user prefers DD/MM/YYYY")
        semantic = MemoryCube(content="user prefers DD/MM/YYYY")
        assert (
            episodic.to_ai_memory_row()["content_hash"]
            == semantic.to_vector_memory_payload()["content_hash"]
        )


# ===== parity with dedupe script =====


class TestDedupeParity:
    def test_matches_dedupe_content_key(self):
        """The cube payload hash must equal the dedupe script's content_key."""
        from scripts.dedupe_learned_patterns import content_key as dedupe_key

        cube = MemoryCube(content="parity check fact")
        payload = cube.to_vector_memory_payload()
        assert dedupe_key(payload) == cube.content_hash
