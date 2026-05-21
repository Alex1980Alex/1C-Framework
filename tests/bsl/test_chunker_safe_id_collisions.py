"""Regression tests for `_safe_id()` chunk_id collision (Fix #3, 2026-05-21).

Bug history: `_safe_id(path)[:80]` truncated long Cyrillic paths to identical
80-char prefix, causing UUID5 collisions between sibling files in deep
directories (e.g. multiple `Catalogs/X/Commands/{Y1,Y2}/CommandModule.bsl`).
Result: ~11% coverage gap in `bsl_code_v4_late` Qdrant collection.

Fix: SHA1 hash suffix for strings > 80 chars; identical behavior for shorter.
"""

from __future__ import annotations

from src.bsl.parser.bsl_chunker import _safe_id


CYRILLIC_LONG_PATHS = [
    r"C:\1С-Framework\ИБTransportManagementDevelop\Конфигурация\src\Catalogs\ВариантыОтчетов\Commands\Изменить\CommandModule.bsl",
    r"C:\1С-Framework\ИБTransportManagementDevelop\Конфигурация\src\Catalogs\ВариантыОтчетов\Commands\Открыть\CommandModule.bsl",
    r"C:\1С-Framework\ИБTransportManagementDevelop\Конфигурация\src\Catalogs\ВариантыОтчетов\Commands\РазместитьВРазделах\CommandModule.bsl",
    r"C:\1С-Framework\ИБTransportManagementDevelop\Конфигурация\src\Catalogs\ВариантыОтчетов\Commands\СброситьНастройкиПользователей\CommandModule.bsl",
]


def test_no_collision_on_long_similar_paths() -> None:
    """4 sibling files under same Catalog must produce 4 distinct safe_ids."""
    ids = {_safe_id(p) for p in CYRILLIC_LONG_PATHS}
    assert len(ids) == len(CYRILLIC_LONG_PATHS), (
        f"chunk_id collision: only {len(ids)} unique from {len(CYRILLIC_LONG_PATHS)} paths"
    )


def test_long_path_length_fits_under_80_chars() -> None:
    """Hashed safe_id must stay <= 80 chars for downstream UUID5 derivation."""
    for p in CYRILLIC_LONG_PATHS:
        sid = _safe_id(p)
        assert len(sid) <= 80, f"safe_id too long ({len(sid)} chars): {sid!r}"


def test_short_path_unchanged_behavior() -> None:
    """Strings <= 80 chars must use the legacy regex-only path (backward compat)."""
    assert _safe_id("short_name") == "short_name"
    assert _safe_id("foo/bar.bsl") == "foo_bar_bsl"
    # Strip leading/trailing underscores
    assert _safe_id("/foo/") == "foo"


def test_symbol_name_unchanged() -> None:
    """Cyrillic symbol names < 80 chars must pass through unchanged."""
    assert _safe_id("ПослеЗаписи") == "ПослеЗаписи"
    assert _safe_id("ЭтоПриемкаЖДТранспорта") == "ЭтоПриемкаЖДТранспорта"


def test_deterministic_hash_for_same_input() -> None:
    """Same long input must produce same safe_id on repeated calls (idempotent)."""
    p = CYRILLIC_LONG_PATHS[0]
    assert _safe_id(p) == _safe_id(p)


def test_different_long_strings_get_different_hashes() -> None:
    """Two long strings differing only in tail must differ in hash suffix."""
    long_a = "x" * 100 + "_apple"
    long_b = "x" * 100 + "_banana"
    assert _safe_id(long_a) != _safe_id(long_b)
