"""Wrap long lines in docs/wiki/*.md to fit markdownlint MD013 (default 120 cols).

Closes pre-commit MD013 errors for `docs/wiki/patterns/*.md` and 8 stub pages
created during the kb-lint recovery session (commit `4287b8a9c`):
  patterns.md, overview.md, triad-architecture.md, hooks-reference.md,
  skills-reference.md, bsl-integration.md, ralph-wiggum.md,
  core-framework-separation.md

Without this, every wiki commit needs `--no-verify` to bypass markdownlint-cli2.

Markdown-aware:
- Skip YAML frontmatter (first `---` to matching `---`)
- Skip fenced code blocks (` ``` ` to matching ` ``` `)
- Skip table rows (lines starting with `|`)
- Skip HTML comments (`<!-- ... -->`)
- Preserve leading indent (list continuations stay aligned)

Source: stdlib `textwrap.wrap()` with `break_long_words=False,
break_on_hyphens=False` — preserves `[text](url)`, `[[wiki-link]]`,
`**bold**`, `` `inline_code` `` as single tokens (no internal whitespace).

Delegation note: initial draft via mcp__llm-rotation__llm_complete
(ollama-local qwen2.5-coder:7b, 28.9s) had 6 bugs (no frontmatter handling,
broken table state machine on multi-row tables, missing `sys` import, no
leading-indent preservation). Corrected to project standards before commit.
"""
from __future__ import annotations

import re
import sys
import textwrap
from pathlib import Path

WIDTH = 120
FENCE_RE = re.compile(r"^\s*```")


def wrap_md(text: str, width: int = WIDTH) -> str:
    """Wrap prose lines in a markdown document, preserving structure."""
    lines = text.split("\n")
    out: list[str] = []
    in_frontmatter = False
    in_fence = False

    for i, line in enumerate(lines):
        # YAML frontmatter: starts at line 0 with `---`, ends at next `---`.
        if i == 0 and line.strip() == "---":
            in_frontmatter = True
            out.append(line)
            continue
        if in_frontmatter:
            out.append(line)
            if line.strip() == "---":
                in_frontmatter = False
            continue

        # Fenced code blocks.
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue

        # Tables — leave intact (column widths matter for readability).
        if line.lstrip().startswith("|"):
            out.append(line)
            continue

        # HTML comments — preserve as-is.
        if line.strip().startswith("<!--"):
            out.append(line)
            continue

        # Already short enough.
        if len(line) <= width:
            out.append(line)
            continue

        # Wrap long prose; preserve leading indent.
        leading = len(line) - len(line.lstrip())
        prefix = line[:leading]
        wrapped = textwrap.wrap(
            line[leading:],
            width=width - leading,
            break_long_words=False,
            break_on_hyphens=False,
            replace_whitespace=False,
            drop_whitespace=True,
        )
        if not wrapped:
            out.append(line)
            continue
        out.extend(prefix + w for w in wrapped)

    return "\n".join(out)


def main() -> int:
    wiki = Path("docs/wiki")
    if not wiki.is_dir():
        print(f"ERROR: {wiki} not found (run from repo root)", file=sys.stderr)
        return 2

    targets: list[Path] = list(wiki.glob("patterns/*.md"))
    stub_names = [
        "patterns", "overview", "triad-architecture", "hooks-reference",
        "skills-reference", "bsl-integration", "ralph-wiggum",
        "core-framework-separation",
    ]
    for stem in stub_names:
        p = wiki / f"{stem}.md"
        if p.exists():
            targets.append(p)

    changed = 0
    for md in sorted(targets):
        text = md.read_text(encoding="utf-8")
        new_text = wrap_md(text)
        if text != new_text:
            md.write_text(new_text, encoding="utf-8")
            changed += 1
            print(f"  wrapped: {md.as_posix()}")
    print(f"\nDone: {changed} files wrapped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
