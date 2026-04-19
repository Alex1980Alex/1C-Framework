from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from time import perf_counter

from .backends.base import RenameBackend
from .classifier import HeuristicClassifier, RouteDecision, RoutingMatrix, SymbolKind
from .driver import RenameDriver
from .telemetry import NullTelemetryWriter, RenameTelemetryEvent, TelemetryWriter
from .types import BackendError, WorkspaceEdit
from .verification import RenameVerifier

_IDENT_RE = re.compile(r"[A-Za-z_\u0400-\u04FF][A-Za-z0-9_\u0400-\u04FF]*")


@dataclass(frozen=True, slots=True)
class ManualFallbackInstruction:
    uri: str
    symbol_kind: SymbolKind
    old_name: str
    new_name: str
    suggested_approach: str
    warnings: list[str]
    rationale: str


@dataclass(slots=True)
class OrchestratorResult:
    applied: bool
    rolled_back: bool
    edit: WorkspaceEdit
    confirm_token: str | None = None
    files_affected: int = 0
    total_edits: int = 0
    symbol_kind: SymbolKind = SymbolKind.UNKNOWN
    primary_backend: str | None = None
    fallback_used: bool = False
    confidence: float = 0.0
    reason: str | None = None
    manual_instruction: ManualFallbackInstruction | None = None
    prefilter_used: bool = False
    prefilter_dropped: int = 0

    @property
    def ok(self) -> bool:
        return self.applied and not self.rolled_back


class RefactorOrchestrator:
    """Multi-backend rename orchestrator with automatic fallback routing."""

    def __init__(
        self,
        backends: dict[str, RenameBackend],
        classifier: HeuristicClassifier,
        verifier: RenameVerifier,
        telemetry: TelemetryWriter | None = None,
    ) -> None:
        self._backends = backends
        self._classifier = classifier
        self._verifier = verifier
        self._telemetry = telemetry or NullTelemetryWriter()

    def rename(
        self,
        uri: str,
        line: int,
        character: int,
        new_name: str,
        *,
        dry_run: bool = True,
        confirm_token: str | None = None,
        content: str | None = None,
    ) -> OrchestratorResult:
        t0 = perf_counter()
        error_code: str | None = None
        result: OrchestratorResult | None = None
        ctx: dict = {
            "classifier_confidence": 0.0,
            "matrix_confidence": 0.0,
            "old_name": _extract_identifier(content, line, character),
        }

        try:
            result = self._rename_inner(
                uri, line, character, new_name,
                dry_run=dry_run,
                confirm_token=confirm_token,
                content=content,
                ctx=ctx,
            )
            return result
        except BackendError as exc:
            error_code = exc.code
            raise
        finally:
            duration_ms = int((perf_counter() - t0) * 1000)
            event = self._build_event(
                uri=uri,
                new_name=new_name,
                dry_run=dry_run,
                duration_ms=duration_ms,
                result=result,
                error_code=error_code,
                ctx=ctx,
            )
            self._telemetry.write(event)

    def _rename_inner(
        self,
        uri: str,
        line: int,
        character: int,
        new_name: str,
        *,
        dry_run: bool = True,
        confirm_token: str | None = None,
        content: str | None = None,
        ctx: dict,
    ) -> OrchestratorResult:
        kind = self._classifier.classify(uri, line, character, content)
        decision = RoutingMatrix.route_for(kind)
        ctx["classifier_confidence"] = _classifier_confidence(kind, content)
        ctx["matrix_confidence"] = decision.confidence

        old_name = ctx.get("old_name")
        name_denied = RoutingMatrix.is_denied(old_name)

        primary_name = decision.primary
        primary_backend = self._backends.get(primary_name)
        if primary_backend is None:
            raise BackendError(
                f"backend '{primary_name}' is not registered",
                code="backend_missing",
            )

        edit: WorkspaceEdit | None = None
        backend_used: str | None = None

        # Skip ast-grep entirely when name is denylisted (over-match risk).
        # Multilspy is scope-aware and stays in play.
        primary_skipped_by_denylist = name_denied and primary_name == "ast-grep"
        if not primary_skipped_by_denylist:
            try:
                if primary_backend.can_handle(uri):
                    edit = primary_backend.plan_rename(
                        uri, line, character, new_name
                    )
                    backend_used = primary_name
            except BackendError:
                edit = None

        fallback_used = False
        fallback_skipped_by_denylist = (
            name_denied and decision.fallback == "ast-grep"
        )
        if (
            (edit is None or not edit.file_edits)
            and decision.fallback is not None
            and not fallback_skipped_by_denylist
        ):
            fallback_name = decision.fallback
            fallback_backend = self._backends.get(fallback_name)
            if fallback_backend is not None:
                try:
                    if fallback_backend.can_handle(uri):
                        fallback_edit = fallback_backend.plan_rename(
                            uri, line, character, new_name
                        )
                        if fallback_edit.file_edits:
                            edit = fallback_edit
                            backend_used = fallback_name
                            fallback_used = True
                except BackendError:
                    pass

        if edit is None or not edit.file_edits:
            denied_chain = (
                primary_skipped_by_denylist or fallback_skipped_by_denylist
            )
            if decision.manual_fallback or denied_chain:
                return OrchestratorResult(
                    applied=False,
                    rolled_back=False,
                    edit=WorkspaceEdit(),
                    symbol_kind=kind,
                    confidence=decision.confidence,
                    reason="manual_required",
                    manual_instruction=self._build_manual_instruction(
                        uri, kind, new_name, decision,
                        old_name=old_name,
                        denied=denied_chain,
                    ),
                )
            raise BackendError(
                "all backends failed to produce edits",
                code="all_backends_failed",
            )

        token = RenameDriver._compute_token(edit)
        files_affected, total_edits = RenameDriver._summarize(edit)

        if dry_run:
            return OrchestratorResult(
                applied=False,
                rolled_back=False,
                edit=edit,
                confirm_token=token,
                files_affected=files_affected,
                total_edits=total_edits,
                symbol_kind=kind,
                primary_backend=backend_used,
                fallback_used=fallback_used,
                confidence=decision.confidence,
                reason=decision.reason,
            )

        if confirm_token != token:
            raise BackendError(
                "confirm token mismatch; re-run with dry_run=True",
                code="token_mismatch",
                details={"expected": token, "got": confirm_token},
            )

        vr = self._verifier.verify_and_apply(edit)
        return OrchestratorResult(
            applied=vr.applied,
            rolled_back=vr.rolled_back,
            edit=edit,
            confirm_token=None,
            files_affected=files_affected,
            total_edits=total_edits,
            symbol_kind=kind,
            primary_backend=backend_used,
            fallback_used=fallback_used,
            confidence=decision.confidence,
            reason=vr.reason,
        )

    @staticmethod
    def _build_manual_instruction(
        uri: str,
        kind: SymbolKind,
        new_name: str,
        decision: RouteDecision,
        *,
        old_name: str | None = None,
        denied: bool = False,
    ) -> ManualFallbackInstruction:
        approach_map: dict[SymbolKind, str] = {
            SymbolKind.FORM_HANDLER: "Grep+Edit or EDT GUI refactor F2",
            SymbolKind.UNKNOWN: "ast-grep --interactive or Grep+Edit",
        }
        warnings_map: dict[SymbolKind, list[str]] = {
            SymbolKind.FORM_HANDLER: [
                "Form handlers may have XML-side references not visible to text tools",
                "Check form property bindings after manual rename",
            ],
            SymbolKind.UNKNOWN: [
                "Symbol type unknown — rename may miss references",
                "Verify with Grep after manual rename",
            ],
        }
        approach = approach_map.get(kind, "Grep+Edit")
        warnings = list(warnings_map.get(kind, []))
        if denied:
            warnings.insert(
                0,
                f"Name {old_name!r} is in the over-match denylist "
                "(too common for ast-grep). Use EDT GUI F2 or scope-aware Edit.",
            )
            rationale = (
                f"ast-grep skipped: {old_name!r} appears in many unrelated "
                f"files (over-match risk). No scope-aware backend available "
                f"for {kind.value}."
            )
        else:
            rationale = (
                f"Primary={decision.primary}, fallback={decision.fallback} "
                f"both failed for {kind.value}"
            )
        return ManualFallbackInstruction(
            uri=uri,
            symbol_kind=kind,
            old_name=old_name or "<unknown>",
            new_name=new_name,
            suggested_approach=approach,
            warnings=warnings,
            rationale=rationale,
        )

    @staticmethod
    def _build_event(
        *,
        uri: str,
        new_name: str,
        dry_run: bool,
        duration_ms: int,
        result: OrchestratorResult | None,
        error_code: str | None,
        ctx: dict,
    ) -> RenameTelemetryEvent:
        return RenameTelemetryEvent(
            timestamp=datetime.now(tz=timezone.utc).isoformat(),  # noqa: UP017
            uri=uri,
            symbol_kind=result.symbol_kind.value if result else "unknown",
            old_name=ctx.get("old_name"),
            new_name=new_name,
            primary_backend=result.primary_backend if result else None,
            fallback_used=result.fallback_used if result else False,
            applied=result.applied if result else False,
            rolled_back=result.rolled_back if result else False,
            duration_ms=duration_ms,
            error_code=error_code,
            classifier_confidence=ctx.get("classifier_confidence", 0.0),
            matrix_confidence=ctx.get("matrix_confidence", 0.0),
            token_matched=None if dry_run else (result is not None and result.ok),
        )


def _extract_identifier(content: str | None, line: int, character: int) -> str | None:
    """Return the identifier under (line, character) in content, or None."""
    if content is None:
        return None
    lines = content.splitlines()
    if line < 0 or line >= len(lines):
        return None
    text = lines[line]
    if character < 0 or character >= len(text):
        return None
    for m in _IDENT_RE.finditer(text):
        if m.start() <= character < m.end():
            return m.group(0)
    return None


def _classifier_confidence(kind: SymbolKind, content: str | None) -> float:
    """Heuristic confidence that the classifier correctly determined `kind`."""
    if content is None:
        return 0.8 if kind == SymbolKind.FORM_HANDLER else 0.2
    return 0.3 if kind == SymbolKind.UNKNOWN else 1.0
