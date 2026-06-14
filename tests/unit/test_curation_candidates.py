"""R1 (ADR-007): отбор кандидатов из learned_patterns в курируемую память.

Канон (memory/*.md) — ручной write-gate; хук только показывает зрелые
паттерны, ещё не покрытые каноном.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOK = (
    Path(__file__).resolve().parents[2]
    / ".claude"
    / "hooks"
    / "memory-curation-candidates-on-start.py"
)
_spec = importlib.util.spec_from_file_location("curation_hook", _HOOK)
mod = importlib.util.module_from_spec(_spec)
sys.modules["curation_hook"] = mod
_spec.loader.exec_module(mod)


def _p(**kw) -> dict:
    base = {
        "id": "pid-1",
        "name": "qdrant collection alias swap pattern",
        "effective_confidence": 0.9,
        "application_count": 7,
        "archived": False,
        "content_hash": "abc123hash",
    }
    base.update(kw)
    return base


def test_mature_uncovered_pattern_is_candidate() -> None:
    out = mod.select_candidates([_p()], corpus="", slug_token_sets=[])
    assert len(out) == 1


def test_thresholds_filter() -> None:
    assert not mod.select_candidates([_p(effective_confidence=0.7)], "", [])
    assert not mod.select_candidates([_p(application_count=2)], "", [])
    assert not mod.select_candidates([_p(archived=True)], "", [])


def test_covered_by_id_or_hash_in_corpus() -> None:
    assert not mod.select_candidates([_p()], corpus="... pid-1 упомянут ...", slug_token_sets=[])
    assert not mod.select_candidates([_p()], corpus="... abc123hash ...", slug_token_sets=[])


def test_covered_by_slug_overlap() -> None:
    # существующая запись reference_qdrant_collection_aliases покрывает паттерн
    slug = mod._tokens("reference_qdrant_collection_aliases_swap")
    assert not mod.select_candidates([_p()], corpus="", slug_token_sets=[slug])


def test_unrelated_slug_does_not_cover() -> None:
    slug = mod._tokens("feedback_bsp_print_empty_layout")
    out = mod.select_candidates([_p()], corpus="", slug_token_sets=[slug])
    assert len(out) == 1


def test_none_payload_values_do_not_crash() -> None:
    # review a6c1c581: payload с явным null не должен ронять отбор (fail-soft)
    out = mod.select_candidates([_p(effective_confidence=None, application_count=None)], "", [])
    assert out == []  # None → 0 → отфильтрован порогами, не TypeError


def test_sorted_by_confidence() -> None:
    out = mod.select_candidates(
        [
            _p(id="a", name="alpha pattern unique tokens", effective_confidence=0.86),
            _p(id="b", name="beta pattern unique tokens", effective_confidence=0.95),
        ],
        "",
        [],
    )
    assert [c["id"] for c in out] == ["b", "a"]
