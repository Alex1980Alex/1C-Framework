"""
BSL Call Graph Store — Phase 61

SQLite-based call graph for 1C Enterprise BSL code.
Stores symbols, calls, module metadata. Supports callers/callees queries,
transitive impact analysis (BFS), and dead code detection.
"""

from __future__ import annotations

import json
import sqlite3
from collections import deque
from pathlib import Path
from typing import Any

from src.bsl.parser.models import BSLModule


class CallGraphStore:
    """SQLite-based call graph storage for BSL code analysis."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._connect()
        self._init_schema()

    def _connect(self) -> None:
        self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

    def _init_schema(self) -> None:
        c = self._conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS symbols (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                module_path TEXT NOT NULL,
                line_start INTEGER,
                line_end INTEGER,
                is_export INTEGER NOT NULL DEFAULT 0,
                params TEXT,
                doc_comment TEXT
            );

            CREATE TABLE IF NOT EXISTS calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                caller_id TEXT NOT NULL,
                callee_name TEXT NOT NULL,
                callee_module TEXT,
                line_number INTEGER,
                call_type TEXT NOT NULL DEFAULT 'direct',
                FOREIGN KEY (caller_id) REFERENCES symbols(id)
            );

            CREATE TABLE IF NOT EXISTS module_metadata (
                path TEXT PRIMARY KEY,
                module_type TEXT,
                subsystem TEXT,
                object_type TEXT,
                object_name TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(name);
            CREATE INDEX IF NOT EXISTS idx_symbols_module ON symbols(module_path);
            CREATE INDEX IF NOT EXISTS idx_symbols_export ON symbols(is_export);
            CREATE INDEX IF NOT EXISTS idx_calls_caller ON calls(caller_id);
            CREATE INDEX IF NOT EXISTS idx_calls_callee ON calls(callee_name);
            CREATE INDEX IF NOT EXISTS idx_calls_callee_mod ON calls(callee_module);
        """)
        self._conn.commit()

    def __enter__(self) -> CallGraphStore:
        if self._conn is None:
            self._connect()
        return self

    def __exit__(self, *args: Any) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _symbol_id(self, module_path: str, symbol_name: str) -> str:
        return f"{module_path}::{symbol_name}"

    def _extract_object_info(self, file_path: str) -> tuple[str, str]:
        """Extract object_type and object_name from BSL file path."""
        parts = file_path.replace("\\", "/").split("/")
        # Pattern: .../Catalogs/ObjectName/Ext/Module.bsl
        type_folders = {
            "catalogs": "Catalog", "справочники": "Catalog",
            "documents": "Document", "документы": "Document",
            "informationregisters": "InformationRegister",
            "регистрысведений": "InformationRegister",
            "accumulationregisters": "AccumulationRegister",
            "регистрынакопления": "AccumulationRegister",
            "dataprocessors": "DataProcessor",
            "обработки": "DataProcessor",
            "commonmodules": "CommonModule",
            "общиемодули": "CommonModule",
            "reports": "Report", "отчёты": "Report",
        }
        for i, part in enumerate(parts):
            key = part.lower()
            if key in type_folders and i + 1 < len(parts):
                return type_folders[key], parts[i + 1]
        return "", ""

    def add_module(self, module: BSLModule) -> None:
        """Insert all symbols and calls from a parsed BSL module."""
        c = self._conn.cursor()
        fp = module.file_path

        # Module metadata
        obj_type, obj_name = self._extract_object_info(fp)
        c.execute(
            "INSERT OR REPLACE INTO module_metadata "
            "(path, module_type, subsystem, object_type, object_name) "
            "VALUES (?, ?, ?, ?, ?)",
            (fp, module.module_type.value, "", obj_type, obj_name),
        )

        # Symbols
        if module.symbols:
            symbol_rows = []
            call_rows = []
            for sym in module.symbols:
                sid = self._symbol_id(fp, sym.name)
                params_json = json.dumps(
                    [{"name": p.name, "by_val": p.by_val, "default": p.default_value}
                     for p in sym.params],
                    ensure_ascii=False,
                ) if sym.params else None

                symbol_rows.append((
                    sid,
                    sym.name,
                    sym.symbol_type.value,
                    fp,
                    sym.line_start,
                    sym.line_end,
                    1 if sym.is_export else 0,
                    params_json,
                    sym.comment or None,
                ))

                # Calls from this symbol
                for call in sym.calls:
                    call_type = "direct"
                    if call.callee_module:
                        call_type = "cross-module"
                    call_rows.append((
                        sid,
                        call.callee_method,
                        call.callee_module,
                        call.line,
                        call_type,
                    ))

            c.executemany(
                "INSERT OR REPLACE INTO symbols "
                "(id, name, type, module_path, line_start, line_end, is_export, params, doc_comment) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                symbol_rows,
            )
            if call_rows:
                c.executemany(
                    "INSERT INTO calls "
                    "(caller_id, callee_name, callee_module, line_number, call_type) "
                    "VALUES (?, ?, ?, ?, ?)",
                    call_rows,
                )

        self._conn.commit()

    def clear(self) -> None:
        """Drop and recreate all tables."""
        c = self._conn.cursor()
        c.execute("DROP TABLE IF EXISTS calls")
        c.execute("DROP TABLE IF EXISTS symbols")
        c.execute("DROP TABLE IF EXISTS module_metadata")
        self._conn.commit()
        self._init_schema()

    def get_symbol(self, symbol_id: str) -> dict | None:
        c = self._conn.cursor()
        c.execute("SELECT * FROM symbols WHERE id = ?", (symbol_id,))
        row = c.fetchone()
        return dict(row) if row else None

    def callers_of(self, name: str, module: str | None = None) -> list[dict]:
        """Find all symbols that call the given name."""
        c = self._conn.cursor()
        if module:
            c.execute(
                "SELECT DISTINCT s.*, c.line_number as call_line, c.call_type "
                "FROM symbols s JOIN calls c ON s.id = c.caller_id "
                "WHERE c.callee_name = ? AND c.callee_module = ?",
                (name, module),
            )
        else:
            c.execute(
                "SELECT DISTINCT s.*, c.line_number as call_line, c.call_type, c.callee_module "
                "FROM symbols s JOIN calls c ON s.id = c.caller_id "
                "WHERE c.callee_name = ?",
                (name,),
            )
        return [dict(row) for row in c.fetchall()]

    def callees_of(self, symbol_id: str) -> list[dict]:
        """Find all calls made by the given symbol."""
        c = self._conn.cursor()
        c.execute(
            "SELECT c.callee_name, c.callee_module, c.line_number, c.call_type "
            "FROM calls c WHERE c.caller_id = ?",
            (symbol_id,),
        )
        return [dict(row) for row in c.fetchall()]

    def impact_analysis(
        self, name: str, module: str | None = None, depth: int = 3
    ) -> list[dict]:
        """Transitive callers via BFS up to given depth."""
        visited: set[str] = set()
        result: list[dict] = []
        queue: deque[tuple[str, str, int]] = deque()

        for caller in self.callers_of(name, module):
            cid = caller["id"]
            if cid not in visited:
                caller["_depth"] = 0
                result.append(caller)
                visited.add(cid)
                queue.append((cid, caller["name"], 0))

        while queue:
            _, cur_name, cur_depth = queue.popleft()
            if cur_depth >= depth:
                continue
            for caller in self.callers_of(cur_name):
                cid = caller["id"]
                if cid not in visited:
                    caller["_depth"] = cur_depth + 1
                    result.append(caller)
                    visited.add(cid)
                    queue.append((cid, caller["name"], cur_depth + 1))

        return result

    def dead_code(self) -> list[dict]:
        """Find exported symbols that are never called anywhere."""
        c = self._conn.cursor()
        c.execute(
            "SELECT s.* FROM symbols s "
            "WHERE s.is_export = 1 "
            "AND s.name NOT IN (SELECT DISTINCT callee_name FROM calls)"
        )
        return [dict(row) for row in c.fetchall()]

    def stats(self) -> dict:
        """Return call graph statistics."""
        c = self._conn.cursor()
        c.execute("SELECT COUNT(*) FROM symbols")
        symbols = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM calls")
        calls = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM module_metadata")
        modules = c.fetchone()[0]
        c.execute("SELECT COUNT(*) FROM symbols WHERE is_export = 1")
        exports = c.fetchone()[0]
        c.execute("SELECT type, COUNT(*) FROM symbols GROUP BY type")
        by_type = {row[0]: row[1] for row in c.fetchall()}
        c.execute("SELECT call_type, COUNT(*) FROM calls GROUP BY call_type")
        by_call_type = {row[0]: row[1] for row in c.fetchall()}
        return {
            "symbols": symbols,
            "calls": calls,
            "modules": modules,
            "exports": exports,
            "by_type": by_type,
            "by_call_type": by_call_type,
        }
