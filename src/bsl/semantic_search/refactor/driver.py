from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .backends.base import RenameBackend
from .types import BackendError, WorkspaceEdit
from .verification import RenameVerifier


@dataclass(slots=True)
class RenameResult:
    applied: bool
    rolled_back: bool
    edit: WorkspaceEdit
    confirm_token: str | None = None
    files_affected: int = 0
    total_edits: int = 0
    reason: str | None = None

    @property
    def ok(self) -> bool:
        """True iff applied and not rolled back."""
        return self.applied and not self.rolled_back


class RenameDriver:
    """Single entry orchestrating backend + verifier with dry-run/confirm-token contract."""

    def __init__(self, backend: RenameBackend, verifier: RenameVerifier) -> None:
        self._backend = backend
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
    ) -> RenameResult:
        """Plan (dry-run) or apply (with matching token) a rename.

        Note: confirm_token binds the planned WorkspaceEdit, not on-disk file
        state. If files change between dry_run and confirm, positions may drift;
        the verifier's error-count check is the safety net in that case.
        """
        if not self._backend.can_handle(uri):
            raise BackendError(f"backend cannot handle uri: {uri}", code="unsupported_uri")

        edit = self._backend.plan_rename(uri, line, character, new_name)
        token = self._compute_token(edit)
        files, total = self._summarize(edit)

        if dry_run:
            return RenameResult(
                applied=False,
                rolled_back=False,
                edit=edit,
                confirm_token=token,
                files_affected=files,
                total_edits=total,
                reason=None,
            )

        if confirm_token != token:
            raise BackendError(
                "confirm token mismatch; re-run with dry_run=True and use returned token",
                code="token_mismatch",
                details={"expected": token, "got": confirm_token},
            )

        vr = self._verifier.verify_and_apply(edit)
        return RenameResult(
            applied=vr.applied,
            rolled_back=vr.rolled_back,
            edit=edit,
            confirm_token=None,
            files_affected=files,
            total_edits=total,
            reason=vr.reason,
        )

    @staticmethod
    def _compute_token(edit: WorkspaceEdit) -> str:
        """SHA-256 of canonical JSON of the edit; stable across dict insertion order."""
        canonical = json.dumps(_edit_to_dict(edit), sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def _summarize(edit: WorkspaceEdit) -> tuple[int, int]:
        """Return (files_affected, total_edit_count)."""
        files = len(edit.file_edits)
        total = sum(len(fe.edits) for fe in edit.file_edits)
        return files, total


def _edit_to_dict(edit: WorkspaceEdit) -> dict:
    """Convert WorkspaceEdit to a plain dict for canonical JSON serialization."""
    return {
        "file_edits": [
            {
                "uri": fe.uri,
                "edits": [
                    {
                        "range": {
                            "start": {
                                "line": te.range.start.line,
                                "character": te.range.start.character,
                            },
                            "end": {
                                "line": te.range.end.line,
                                "character": te.range.end.character,
                            },
                        },
                        "new_text": te.new_text,
                    }
                    for te in fe.edits
                ],
            }
            for fe in edit.file_edits
        ],
    }
