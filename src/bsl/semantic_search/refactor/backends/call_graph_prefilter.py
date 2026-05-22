"""Pre-filter ast-grep matches using BSL call graph (Option A)."""

from __future__ import annotations

import logging
from pathlib import Path

from src.bsl.call_graph.store import CallGraphStore

logger = logging.getLogger(__name__)


class CallGraphPreFilter:
    """Scope-aware file filter backed by the BSL SQLite call graph."""

    def __init__(self, store: CallGraphStore) -> None:
        self._store = store

    def allowed_files(self, old_name: str, module_hint: str | None = None) -> set[Path] | None:
        """Return files where edits are expected, or None for fallback."""
        if self._store._conn is None:
            return None
        callers = self._store.callers_of(old_name, module=module_hint)
        defining = self._defining_modules(old_name, module_hint)

        if not defining and not callers:
            if not self._is_known(old_name):
                return None
            return set()

        allowed: set[Path] = set()
        for c in callers:
            allowed.add(Path(c["module_path"]))
        allowed.update(defining)
        return allowed

    def _defining_modules(self, name: str, module_hint: str | None) -> set[Path]:
        if module_hint is not None:
            sid = self._store._symbol_id(module_hint, name)
            sym = self._store.get_symbol(sid)
            if sym is not None:
                return {Path(sym["module_path"])}

        conn = self._store._conn
        if conn is None:
            return set()
        rows = conn.execute(
            "SELECT DISTINCT module_path FROM symbols WHERE name = ?",
            (name,),
        ).fetchall()
        return {Path(r["module_path"]) for r in rows}

    def _is_known(self, name: str) -> bool:
        conn = self._store._conn
        if conn is None:
            return False
        row = conn.execute(
            "SELECT 1 FROM symbols WHERE name = ? LIMIT 1",
            (name,),
        ).fetchone()
        return row is not None
