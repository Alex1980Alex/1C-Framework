from __future__ import annotations

from dataclasses import dataclass

from .classifier import HeuristicClassifier, RouteDecision, RoutingMatrix, SymbolKind
from .driver import RenameDriver
from .types import BackendError, WorkspaceEdit
from .verification import RenameVerifier


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

    @property
    def ok(self) -> bool:
        return self.applied and not self.rolled_back


class RefactorOrchestrator:
    """Multi-backend rename orchestrator with automatic fallback routing.

    Classifies the symbol, routes to primary/fallback backend via
    RoutingMatrix, and falls back on primary failure or empty edit.
    """

    def __init__(
        self,
        backends: dict[str, RenameBackend],
        classifier: HeuristicClassifier,
        verifier: RenameVerifier,
    ) -> None:
        self._backends = backends
        self._classifier = classifier
        self._verifier = verifier

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
        # 1. Classify symbol kind
        kind = self._classifier.classify(uri, line, character, content)

        # 2. Get routing decision
        decision = RoutingMatrix.route_for(kind)

        # 3. Try primary backend
        primary_name = decision.primary
        primary_backend = self._backends.get(primary_name)
        if primary_backend is None:
            raise BackendError(
                f"backend '{primary_name}' is not registered",
                code="backend_missing",
            )

        edit: WorkspaceEdit | None = None
        backend_used: str | None = None

        try:
            if primary_backend.can_handle(uri):
                edit = primary_backend.plan_rename(uri, line, character, new_name)
                backend_used = primary_name
        except BackendError:
            edit = None

        # 4. If primary failed or returned empty, try fallback
        fallback_used = False
        if (edit is None or not edit.file_edits) and decision.fallback is not None:
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

        # 5. Both failed
        if edit is None or not edit.file_edits:
            raise BackendError(
                "all backends failed to produce edits",
                code="all_backends_failed",
            )

        # 6. Compute token and summary
        token = RenameDriver._compute_token(edit)
        files_affected, total_edits = RenameDriver._summarize(edit)

        # 7. Dry run — return plan
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

        # 8. Apply — verify token first
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
