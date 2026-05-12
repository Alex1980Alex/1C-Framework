"""Wrapper for kb-lint --ci to force UTF-8 stdout on Windows cp1251 consoles.

Pre-commit local hook entry. Calls kb-lint with UTF-8 stdout reconfiguration
so rich.Console can render Unicode glyphs (e.g. '↔') without crashing
on charmap-encoded Windows terminals.

Roadmap: closes encoding leg of `kb-lint` hook recovery — see commit
`c46d49487` for the install/--fix story.
"""
from __future__ import annotations

import sys


def _reconfigure_utf8() -> None:
    """Force stdout/stderr to UTF-8 (Python 3.7+ supports reconfigure)."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


if __name__ == "__main__":
    _reconfigure_utf8()
    # Forward all argv past argv[0] to kb-lint's main; default to --ci docs/wiki
    # when invoked bare from pre-commit (which passes no extra args because we
    # set pass_filenames: false in .pre-commit-config.yaml).
    from kb_lint.cli import main

    argv = sys.argv[1:] or ["--ci", "docs/wiki"]
    main(argv)
