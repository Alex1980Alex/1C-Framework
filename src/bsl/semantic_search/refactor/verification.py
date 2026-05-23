from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .types import BackendError, WorkspaceEdit
from .workspace_edit import WorkspaceEditApplier

ErrorProvider = Callable[[], list[str]]


@dataclass(slots=True)
class VerifyResult:
    """Outcome of a rename verification attempt."""

    applied: bool
    rolled_back: bool
    baseline_errors: list[str] = field(default_factory=list)
    after_errors: list[str] = field(default_factory=list)
    reason: str | None = None
    prefilter_dropped: int = 0

    @property
    def ok(self) -> bool:
        """True iff applied and not rolled back."""
        return self.applied and not self.rolled_back


class RenameVerifier:
    """Verifies a rename by checking error counts before and after applying."""

    def __init__(
        self,
        applier: WorkspaceEditApplier,
        error_provider: ErrorProvider,
    ) -> None:
        self._applier = applier
        self._error_provider = error_provider

    def verify_and_apply(self, edit: WorkspaceEdit) -> VerifyResult:
        """Apply edit, check for regressions, auto-rollback if errors increased."""
        baseline = list(self._error_provider())
        try:
            self._applier.apply(edit)
        except BackendError as e:
            return VerifyResult(
                applied=False,
                rolled_back=False,
                baseline_errors=baseline,
                reason=f"apply failed: {e}",
            )
        except Exception as e:
            return VerifyResult(
                applied=False,
                rolled_back=False,
                baseline_errors=baseline,
                reason=f"apply raised: {e!r}",
            )

        after = list(self._error_provider())
        if len(after) > len(baseline):
            self._applier.rollback()
            return VerifyResult(
                applied=True,
                rolled_back=True,
                baseline_errors=baseline,
                after_errors=after,
                reason=f"error count rose: {len(baseline)} -> {len(after)}",
            )

        return VerifyResult(
            applied=True,
            rolled_back=False,
            baseline_errors=baseline,
            after_errors=after,
        )
