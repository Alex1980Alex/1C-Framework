from pathlib import Path

import pytest

from src.bsl.call_graph.store import CallGraphStore
from src.bsl.semantic_search.refactor.backends.call_graph_prefilter import (
    CallGraphPreFilter,
)


@pytest.fixture
def prefilter(tmp_path):
    db_path = tmp_path / "cg.db"
    store = CallGraphStore(str(db_path))
    return CallGraphPreFilter(store)


def _insert(pf, symbols, calls):
    conn = pf._store._conn
    conn.executemany("INSERT INTO symbols VALUES(?,?,?,?,?,?,?,?,?)", symbols)
    conn.executemany(
        "INSERT INTO calls(caller_id,callee_name,callee_module,line_number,call_type) VALUES(?,?,?,?,?)",
        calls,
    )
    conn.commit()


def test_unknown_symbol_returns_none(prefilter):
    assert prefilter.allowed_files("absent") is None


def test_known_no_callers_returns_defining_module_only(prefilter):
    _insert(prefilter, [("m::f", "f", "func", "m", 1, 1, 0, None, None)], [])
    # Symbol known, 0 callers → only defining module returned
    assert prefilter.allowed_files("f") == {Path("m")}


def test_one_caller_returns_caller_and_defining(prefilter):
    _insert(
        prefilter,
        [
            ("m::f", "f", "func", "m", 1, 1, 0, None, None),
            ("a::g", "g", "func", "a", 1, 1, 0, None, None),
        ],
        [("a::g", "f", "m", 5, "direct")],
    )
    assert prefilter.allowed_files("f") == {Path("m"), Path("a")}


def test_multiple_callers_across_modules(prefilter):
    _insert(
        prefilter,
        [
            ("m::f", "f", "func", "m", 1, 1, 0, None, None),
            ("a::g", "g", "func", "a", 1, 1, 0, None, None),
            ("b::h", "h", "func", "b", 1, 1, 0, None, None),
            ("c::i", "i", "func", "c", 1, 1, 0, None, None),
        ],
        [
            ("a::g", "f", "m", 3, "direct"),
            ("b::h", "f", "m", 4, "direct"),
            ("c::i", "f", "m", 5, "direct"),
        ],
    )
    assert prefilter.allowed_files("f") == {Path("m"), Path("a"), Path("b"), Path("c")}


def test_module_hint_exact_lookup(prefilter):
    _insert(
        prefilter,
        [("m::f", "f", "func", "m", 1, 1, 0, None, None)],
        [],
    )
    result = prefilter.allowed_files("f", module_hint="m")
    assert result is not None
    assert Path("m") in result


def test_wrong_module_hint_still_finds_defining(prefilter):
    _insert(
        prefilter,
        [
            ("m::f", "f", "func", "m", 1, 1, 0, None, None),
            ("a::g", "g", "func", "a", 1, 1, 0, None, None),
        ],
        [("a::g", "f", "m", 3, "direct")],
    )
    # Wrong hint: callers_of with module filter finds no callers,
    # but defining module still found via SQL fallback.
    result = prefilter.allowed_files("f", module_hint="other")
    assert result == {Path("m")}


def test_conn_none_returns_none(prefilter):
    store = prefilter._store
    store._conn.close()
    store._conn = None
    assert CallGraphPreFilter(store).allowed_files("x") is None


def test_duplicate_paths_deduplicated(prefilter):
    _insert(
        prefilter,
        [
            ("m::f", "f", "func", "m", 1, 1, 0, None, None),
            ("m::g", "g", "func", "m", 5, 5, 0, None, None),
        ],
        [("m::g", "f", "m", 6, "direct")],
    )
    assert prefilter.allowed_files("f") == {Path("m")}
