from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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


class RoutingMatrix:
    """Routing Matrix v2 — maps SymbolKind to backend selection."""

    _ROUTES: dict[SymbolKind, RouteDecision] = {
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
        SymbolKind.LOCAL_VARIABLE: RouteDecision(
            "multilspy", None, 0.70, "local scope, single file"
        ),
        SymbolKind.FORM_HANDLER: RouteDecision(
            "ast-grep", "multilspy", 0.60, "form handlers may have XML-side refs"
        ),
        SymbolKind.UNKNOWN: RouteDecision(
            "ast-grep", None, 0.30, "pattern-based fallback"
        ),
    }

    @classmethod
    def route_for(cls, kind: SymbolKind) -> RouteDecision:
        """Return the routing decision for a given symbol kind."""
        return cls._ROUTES.get(kind, cls._ROUTES[SymbolKind.UNKNOWN])

    @classmethod
    def all_kinds(cls) -> list[SymbolKind]:
        """Return all SymbolKinds defined in the matrix."""
        return list(cls._ROUTES.keys())


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

        target = lines[line]
        is_export = any(marker in target for marker in self._EXPORT_MARKERS)

        if "Процедура" in target or "Procedure" in target:
            return (
                SymbolKind.MODULE_EXPORT_PROC
                if is_export
                else SymbolKind.MODULE_LOCAL_PROC
            )
        if "Функция" in target or "Function" in target:
            return (
                SymbolKind.MODULE_EXPORT_FUNC
                if is_export
                else SymbolKind.MODULE_LOCAL_FUNC
            )
        if target.lstrip().startswith(("Перем ", "Var ")):
            return SymbolKind.LOCAL_VARIABLE

        return SymbolKind.UNKNOWN
