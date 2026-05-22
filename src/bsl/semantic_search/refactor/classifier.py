from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise ImportError(
        "PyYAML is required for routing matrix loading. " "Install it with: pip install pyyaml"
    ) from exc

log = logging.getLogger(__name__)


class SymbolKind(Enum):
    MODULE_EXPORT_PROC = "module_export_proc"
    MODULE_EXPORT_FUNC = "module_export_func"
    MODULE_LOCAL_PROC = "module_local_proc"
    MODULE_LOCAL_FUNC = "module_local_func"
    LOCAL_VARIABLE = "local_variable"
    FORM_HANDLER = "form_handler"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class RouteDecision:
    """Backend routing decision for a symbol."""

    primary: str
    fallback: str | None
    confidence: float
    reason: str
    manual_fallback: bool = False


_DEFAULT_ROUTES: dict[SymbolKind, RouteDecision] = {
    SymbolKind.MODULE_EXPORT_PROC: RouteDecision(
        "multilspy", "ast-grep", 0.95, "cross-file rename via LSP preload"
    ),
    SymbolKind.MODULE_EXPORT_FUNC: RouteDecision(
        "multilspy", "ast-grep", 0.95, "cross-file rename via LSP preload"
    ),
    SymbolKind.MODULE_LOCAL_PROC: RouteDecision(
        "multilspy", "ast-grep", 0.95, "module-scope — calibrated pilot-B 4/4 success"
    ),
    SymbolKind.MODULE_LOCAL_FUNC: RouteDecision(
        "multilspy", "ast-grep", 0.95, "module-scope — calibrated pilot-B 4/4 success"
    ),
    SymbolKind.LOCAL_VARIABLE: RouteDecision(
        "multilspy", None, 0.95, "local scope, single file — calibrated pilot-B 4/4 success"
    ),
    SymbolKind.FORM_HANDLER: RouteDecision(
        "ast-grep",
        "multilspy",
        0.95,
        "form handlers — calibrated pilot-B 4/4 success",
        manual_fallback=True,
    ),
    SymbolKind.UNKNOWN: RouteDecision(
        "ast-grep",
        None,
        0.30,
        "pattern-based fallback",
        manual_fallback=True,
    ),
}


_DEFAULT_AST_GREP_GLOBAL: dict = {
    "use_call_graph_prefilter": False,
    "call_graph_db": "cache/bsl_call_graph.db",
    "graph_stale_threshold_days": 7,
}


class RoutingMatrix:
    """Routing Matrix v2 — maps SymbolKind to backend selection."""

    _ROUTES: dict[SymbolKind, RouteDecision] = dict(_DEFAULT_ROUTES)
    _DENYLIST: frozenset[str] = frozenset()
    _AST_GREP_GLOBAL: dict = dict(_DEFAULT_AST_GREP_GLOBAL)

    @classmethod
    def route_for(cls, kind: SymbolKind) -> RouteDecision:
        """Return the routing decision for a given symbol kind."""
        return cls._ROUTES.get(kind, cls._ROUTES[SymbolKind.UNKNOWN])

    @classmethod
    def all_kinds(cls) -> list[SymbolKind]:
        """Return all SymbolKinds defined in the matrix."""
        return list(cls._ROUTES.keys())

    @classmethod
    def is_denied(cls, name: str | None) -> bool:
        """True if name is in the over-match denylist (ast-grep should skip it)."""
        return bool(name) and name in cls._DENYLIST

    @classmethod
    def ast_grep_global(cls) -> dict:
        """Return the global ast-grep tuning block (copy)."""
        return dict(cls._AST_GREP_GLOBAL)

    @classmethod
    def load(cls, path: Path | None = None) -> None:
        """Load routing matrix from YAML, updating the class-level routes."""
        if path is None:
            path = Path(__file__).parent / "routing_matrix.yaml"

        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if data is None:
            raise ValueError(f"Routing matrix file is empty: {path}")

        version = data.get("version")
        if version != 2:
            raise ValueError(
                f"Unsupported routing matrix version {version!r} " f"(expected 2) in {path}"
            )

        raw_routes: dict[str, dict] = data.get("routes")
        if not isinstance(raw_routes, dict):
            raise ValueError(f"Missing or invalid 'routes' section in {path}")

        new_routes: dict[SymbolKind, RouteDecision] = {}
        for name, entry in raw_routes.items():
            try:
                kind = SymbolKind(name)
            except ValueError:
                log.warning("Skipping unknown route name %r in %s", name, path)
                continue
            new_routes[kind] = RouteDecision(
                primary=entry["primary"],
                fallback=entry.get("fallback"),
                confidence=float(entry["confidence"]),
                reason=entry["reason"],
                manual_fallback=entry.get("manual_fallback", False),
            )

        if SymbolKind.UNKNOWN not in new_routes and SymbolKind.UNKNOWN in _DEFAULT_ROUTES:
            new_routes[SymbolKind.UNKNOWN] = _DEFAULT_ROUTES[SymbolKind.UNKNOWN]
            log.warning("YAML missing 'unknown' route; using default")
        cls._ROUTES = new_routes

        raw_denylist = data.get("denylist") or []
        if not isinstance(raw_denylist, list):
            raise ValueError(f"'denylist' must be a list in {path}")
        cls._DENYLIST = frozenset(str(n) for n in raw_denylist if n)

        global_block = data.get("global") or {}
        ast_block = global_block.get("ast_grep") or {}
        merged = dict(_DEFAULT_AST_GREP_GLOBAL)
        for key, value in ast_block.items():
            if key in merged:
                merged[key] = value
        cls._AST_GREP_GLOBAL = merged

        log.info(
            "Loaded %d routes, %d denylist entries, ast-grep prefilter=%s from %s",
            len(new_routes),
            len(cls._DENYLIST),
            cls._AST_GREP_GLOBAL["use_call_graph_prefilter"],
            path,
        )

    @classmethod
    def reset(cls) -> None:
        """Reset routes to bundled defaults (useful in tests)."""
        cls._ROUTES = dict(_DEFAULT_ROUTES)
        cls._DENYLIST = frozenset()
        cls._AST_GREP_GLOBAL = dict(_DEFAULT_AST_GREP_GLOBAL)


class HeuristicClassifier:
    """Pattern-based classifier using URI + optional file content."""

    _FORM_PATH_MARKERS = ("/forms/", "\\forms\\")
    _EXPORT_MARKERS = ("Экспорт", "Export")

    def classify(
        self,
        uri: str,
        line: int,
        character: int,
        content: str | None = None,
    ) -> SymbolKind:
        """Classify the symbol at (line, character) in file at uri."""
        uri_lower = uri.lower()
        if any(m in uri_lower for m in self._FORM_PATH_MARKERS):
            return SymbolKind.FORM_HANDLER

        if content is None:
            return SymbolKind.UNKNOWN

        lines = content.splitlines()
        if line < 0 or line >= len(lines):
            return SymbolKind.UNKNOWN

        # Strip trailing `// ...` line comment so "Экспорт" in a comment
        # doesn't flip a local proc to export.
        code = lines[line].split("//", 1)[0]
        is_export = any(marker in code for marker in self._EXPORT_MARKERS)

        if "Процедура" in code or "Procedure" in code:
            return SymbolKind.MODULE_EXPORT_PROC if is_export else SymbolKind.MODULE_LOCAL_PROC
        if "Функция" in code or "Function" in code:
            return SymbolKind.MODULE_EXPORT_FUNC if is_export else SymbolKind.MODULE_LOCAL_FUNC
        # First token check — tolerates tabs / multiple spaces after `Перем`/`Var`.
        first_token = code.split(maxsplit=1)[0] if code.strip() else ""
        if first_token in ("Перем", "Var"):
            return SymbolKind.LOCAL_VARIABLE

        return SymbolKind.UNKNOWN
