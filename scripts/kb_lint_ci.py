"""Wrapper for kb-lint --ci to force UTF-8 stdout + Cyrillic-safe filenames.

Pre-commit local hook entry. Two responsibilities:

1. **UTF-8 stdout reconfiguration** — so `rich.Console` can render Unicode
   glyphs (e.g. '↔') without crashing on charmap-encoded Windows terminals
   (the original failure was `UnicodeEncodeError '↔' ... cp1251`).

2. **Cyrillic-safety monkey-patch for `kb_lint.fixer.fix_filename_casing`** —
   upstream kb-lint 0.1.1 renames non-kebab filenames via
   `re.sub(r"[^a-z0-9]+", "-", stem.lower())` which **destroys Cyrillic and
   other non-ASCII characters**. Real incident: `kb-lint --fix docs/wiki`
   on this repo deleted/renamed 1131 entity files in a single pass, including
   a file with empty stem (`docs/wiki/entities/.md`). Patch skips rename for
   any stem containing non-ASCII characters and emits a one-line warning to
   stderr per affected file.

Production pre-commit hook calls `--ci` (not `--fix`) so the rename codepath
is dormant in CI. The patch protects manual `python scripts/kb_lint_ci.py
--fix` invocations.

Roadmap: closes encoding + Cyrillic-rename legs of `kb-lint` hook recovery —
see commits `c46d49487` (install/--fix story) and the SKIP_PATTERNS update
in `.claude/hooks/docs-change-enforcer.py` for the docs-enforcer side.
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


def _install_cyrillic_safety_patch() -> None:
    """Replace `kb_lint.fixer.fix_filename_casing` with a non-ASCII-safe variant.

    Upstream (kb_lint 0.1.1 fixer.py:62-77) uses
    `re.sub(r"[^a-z0-9]+", "-", stem.lower())` which collapses any non-ASCII
    character to '-'. For Cyrillic stems this produces garbage (`1сenterprise`
    → `1-enterprise`) or empty stems (`точек` → empty → `.md`). The patched
    variant short-circuits to a no-op when the original stem contains ANY
    non-ASCII character and logs the skip to stderr.

    ASCII-only stems (including ones that need genuine casing/space → kebab
    fixes) fall through to the upstream implementation unchanged.

    Note: patch does not survive `importlib.reload(kb_lint.fixer)` — fine for
    one-shot CLI use (pre-commit subprocess); minor caveat in pytest reload
    fixtures.
    """
    from kb_lint import fixer

    _original = fixer.fix_filename_casing

    def _safe_fix_filename_casing(article):  # type: ignore[no-untyped-def]
        stem = article.path.stem
        if not stem.isascii():
            sys.stderr.write(
                f"[kb_lint_ci] WARN: skip rename of '{article.path.name}' "
                f"(non-ASCII stem — upstream regex would destroy Unicode)\n"
            )
            return False, "skipped: non-ASCII stem (safety patch)"
        return _original(article)

    fixer.fix_filename_casing = _safe_fix_filename_casing


def _install_ignore_spec_encoding_patch() -> None:
    """Make `kb_lint.scanner._build_ignore_spec` read .gitignore as UTF-8.

    Upstream (kb_lint 0.1.x scanner.py:39-44) opens `<wiki_path>/.gitignore`
    without an explicit encoding → on Windows (cp1251 locale) any UTF-8
    content crashes the whole lint run with UnicodeDecodeError BEFORE a
    single article is scanned. Observed live 2026-07-05: bare `--ci` made
    wiki_path default to the repo root, whose Cyrillic-commented .gitignore
    killed the run at scanner.py:41.

    The patched variant reproduces upstream logic with
    `encoding="utf-8", errors="replace"` (ignore patterns are ASCII-ish;
    replacement chars in comments are harmless).
    """
    from kb_lint import scanner

    def _safe_build_ignore_spec(wiki_path, config):  # type: ignore[no-untyped-def]
        patterns = list(config.ignore_patterns)
        gitignore = wiki_path / ".gitignore"
        if gitignore.is_file():
            with open(gitignore, encoding="utf-8", errors="replace") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        patterns.append(line)
        return scanner.pathspec.PathSpec.from_lines("gitignore", patterns)

    scanner._build_ignore_spec = _safe_build_ignore_spec


if __name__ == "__main__":
    _reconfigure_utf8()
    # Install patch BEFORE importing cli (which imports fixer). The patch
    # mutates fixer module attribute, so cli's apply_fixes() will pick up
    # the safe variant via fixer.fix_filename_casing lookup at call time.
    _install_cyrillic_safety_patch()
    _install_ignore_spec_encoding_patch()
    # Forward all argv past argv[0] to kb-lint's main; default to --ci docs/wiki
    # when invoked bare from pre-commit (which passes no extra args because we
    # set pass_filenames: false in .pre-commit-config.yaml).
    from kb_lint.cli import main

    argv = sys.argv[1:] or ["--ci", "docs/wiki"]
    main(argv)
