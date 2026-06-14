"""Unit tests for the §24 surfacing-cache redesign (roadmap 260609 P1.2).

Verifies the mechanism (not the production hit-rate, which needs accumulation):
  - relaxed cache key collides on the top-K salient tokens despite differing filler
  - disjoint salient tokens → distinct keys
  - empty ("no results") entries expire on the shorter EMPTY_TTL while populated
    entries of the same age survive on the longer TTL
  - put/get round-trip stamps the ``empty`` flag

The hook filename is hyphenated, so it's loaded via importlib (same as the
integration suite). conftest sink isolation keeps writes off production paths.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location(
    "memory_first_hook_cache_test", str(_HOOKS_DIR / "memory-first-hook.py")
)
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def test_cache_key_collides_on_salient_tokens(monkeypatch):
    monkeypatch.setattr(mod, "_confidence_epoch", lambda: 1.0)
    monkeypatch.setattr(mod, "SURFACE_CACHE_KEY_TOPK", 8)
    # 8 long (salient) tokens shared; short filler differs → must collapse to same key.
    core = {
        "configuration",
        "direction",
        "unloading",
        "blocked",
        "vehicle",
        "semantic",
        "retrieval",
        "embedding",
    }
    a = core | {"is", "of"}
    b = core | {"to", "by"}
    assert mod._surface_cache_key(a) == mod._surface_cache_key(b)

    # Disjoint salient tokens → different key.
    c = {
        "completely",
        "different",
        "subject",
        "matter",
        "unrelated",
        "kittens",
        "sunshine",
        "rainbow",
    }
    assert mod._surface_cache_key(a) != mod._surface_cache_key(c)


def test_cache_key_short_prompt_is_exact(monkeypatch):
    monkeypatch.setattr(mod, "_confidence_epoch", lambda: 1.0)
    monkeypatch.setattr(mod, "SURFACE_CACHE_KEY_TOPK", 8)
    # <=K tokens → full set used → differing filler DOES change the key (exact).
    a = {"alpha", "beta", "gamma"}
    b = {"alpha", "beta", "delta"}
    assert mod._surface_cache_key(a) != mod._surface_cache_key(b)


def test_empty_entries_expire_faster(monkeypatch, tmp_path):
    cache = tmp_path / "surf-cache.json"
    monkeypatch.setattr(mod, "SURFACE_CACHE_FILE", cache)
    monkeypatch.setattr(mod, "SURFACE_CACHE_ENABLED", True)
    monkeypatch.setattr(mod, "SURFACE_CACHE_TTL", 900.0)
    monkeypatch.setattr(mod, "SURFACE_CACHE_EMPTY_TTL", 100.0)

    now = time.time()
    entries = {
        "empty_old": {"ts": now - 200, "results": [], "pids": [], "empty": True},
        "popul_old": {"ts": now - 200, "results": [{"x": 1}], "pids": [], "empty": False},
    }
    cache.write_text(json.dumps({"entries": entries}), encoding="utf-8")

    # 200s old: past the 100s empty TTL → miss; within 900s populated TTL → hit.
    assert mod._surface_cache_get("empty_old") is None
    got = mod._surface_cache_get("popul_old")
    assert got is not None and got["results"] == [{"x": 1}]


def test_put_get_roundtrip_stamps_empty(monkeypatch, tmp_path):
    cache = tmp_path / "surf-cache.json"
    monkeypatch.setattr(mod, "SURFACE_CACHE_FILE", cache)
    monkeypatch.setattr(mod, "SURFACE_CACHE_ENABLED", True)

    mod._surface_cache_put("k_pop", [{"a": 1}], [("pid", 0.5)])
    e = mod._surface_cache_get("k_pop")
    assert e is not None and e["results"] == [{"a": 1}] and e["empty"] is False

    mod._surface_cache_put("k_empty", [], [])
    e2 = mod._surface_cache_get("k_empty")
    assert e2 is not None and e2["empty"] is True
