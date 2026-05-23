from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise ImportError(
        "PyYAML is required for routing matrix loading. Install it with: pip install pyyaml"
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
        "multilspy", "ast-grep", 0.85, "module-scope LSP rename"
    ),
    SymbolKind.MODULE_LOCAL_FUNC: RouteDecision(
        "multilspy", "ast-grep", 0.85, "module-scope LSP rename"
    ),
    SymbolKind.LOCAL_VARIABLE: RouteDecision("multilspy", None, 0.70, "local scope, single file"),
    SymbolKind.FORM_HANDLER: RouteDecision(
        "ast-grep",
        "multilspy",
        0.60,
        "form handlers may have XML-side refs",
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


class RoutingMatrix:
    """Routing Matrix v2 — maps SymbolKind to backend selection."""

    _ROUTES: dict[SymbolKind, RouteDecision] = dict(_DEFAULT_ROUTES)

    @classmethod
    def route_for(cls, kind: SymbolKind) -> RouteDecision:
        """Return the routing decision for a given symbol kind."""
        return cls._ROUTES.get(kind, cls._ROUTES[SymbolKind.UNKNOWN])

    @classmethod
    def all_kinds(cls) -> list[SymbolKind]:
        """Return all SymbolKinds defined in the matrix."""
        return list(cls._ROUTES.keys())

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
                f"Unsupported routing matrix version {version!r} (expected 2) in {path}"
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
        log.info("Loaded %d routes from %s", len(new_routes), path)

    @classmethod
    def reset(cls) -> None:
        """Reset routes to bundled defaults (useful in tests)."""
        cls._ROUTES = dict(_DEFAULT_ROUTES)


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
