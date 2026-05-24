from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path

from ..types import BackendError
from .ast_grep_backend import AstGrepMatch


class SubprocessAstGrepRunner:
    """Invokes the ast-grep binary as a subprocess and parses --json output.

    Uses a temp file for rules instead of --inline-rules because
    multiline YAML breaks with Windows shell escaping.
    """

    def __init__(
        self,
        binary: str = "ast-grep",
        config_path: Path | None = None,
        rule_template: str | None = None,
        timeout_seconds: float = 60.0,
    ) -> None:
        self._binary = binary
        self._config = config_path
        self._rule_template = rule_template
        self._timeout = timeout_seconds

    def run_rename(self, workspace_root: Path, old_name: str, new_name: str) -> list[AstGrepMatch]:
        """Run ast-grep scan; return matches of `old_name` in workspace_root."""
        args = [self._binary, "scan", "--json=compact"]
        if self._config is not None:
            args += ["-c", str(self._config)]
        inline_rule = f"id: rename-{old_name}\nlanguage: bsl\nrule:\n  pattern: {old_name}\n"
        args += ["--inline-rules", inline_rule, str(workspace_root)]
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yml", delete=False, encoding="utf-8"
            ) as rule_file:
                rule_file.write(inline_rule)
                rule_path = rule_file.name

            args = [self._binary, "scan", "--json=compact"]
            if self._config is not None:
                args += ["-c", str(self._config)]
            args += ["-r", rule_path, str(workspace_root)]

            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=self._timeout,
                check=False,
                cwd=str(workspace_root),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise BackendError(
                f"ast-grep subprocess failed: {exc!r}", code="subprocess_failed"
            ) from exc
        finally:
            if rule_path:
                try:
                    os.unlink(rule_path)
                except OSError:
                    pass

        if proc.returncode != 0:
            raise BackendError(
                f"ast-grep exit {proc.returncode}: {proc.stderr[:200]}",
                code="subprocess_nonzero",
            )

        if not proc.stdout.strip():
            return []
        try:
            raw = json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise BackendError(f"invalid ast-grep JSON: {exc!r}", code="invalid_json") from exc
        if not isinstance(raw, list):
            raise BackendError("expected JSON array of matches", code="invalid_json")
        return [self._parse_match(m) for m in raw]

    @staticmethod
    def _parse_match(m: dict) -> AstGrepMatch:
        try:
            r = m["range"]
            s = r["start"]
            e = r["end"]
            return AstGrepMatch(
                file=Path(m["file"]),
                start_line=s["line"],
                start_character=s.get("column", s.get("character", 0)),
                end_line=e["line"],
                end_character=e.get("column", e.get("character", 0)),
            )
        except (KeyError, TypeError) as exc:
            raise BackendError(
                f"malformed ast-grep match: {exc!r}", code="malformed_match"
            ) from exc
