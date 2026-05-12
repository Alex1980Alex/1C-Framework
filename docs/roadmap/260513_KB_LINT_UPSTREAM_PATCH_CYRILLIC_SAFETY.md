# kb-lint upstream PR draft — Unicode-safe `fix_filename_casing`

> **Status:** Patch ready, PR not yet submitted (requires upstream auth via human).
> **Upstream repo:** https://github.com/SingggggYee/kb-lint
> **Issue/incident:** GKSTCPLK-2468 follow-up, kb-lint 0.1.1 `--fix` destroyed 1131 Cyrillic-named wiki files in our repo (see commit `c46d49487` damage report).
> **Local mitigation:** [`scripts/kb_lint_ci.py`](../../scripts/kb_lint_ci.py) `_install_cyrillic_safety_patch()` monkey-patches the same function at wrapper startup, skipping rename for non-ASCII stems. Upstream fix would let us drop the monkey-patch.

## Root cause

`kb_lint/fixer.py:62-77` (kb-lint 0.1.1):

```python
def fix_filename_casing(article: Article) -> tuple[bool, str]:
    """Rename files with spaces or non-kebab-case names."""
    stem = article.path.stem
    new_stem = re.sub(r"[^a-z0-9]+", "-", stem.lower())
    new_name = new_stem + ".md"
    ...
```

The character class `[^a-z0-9]+` is ASCII-only. Any non-ASCII character (Cyrillic, CJK, accented Latin, …) matches the negation and gets collapsed to `-`. Real damage observed on our `docs/wiki/entities/` (Cyrillic-heavy KB):

| Input stem | Output | Result |
|---|---|---|
| `1сenterprise` | `1-enterprise` | Cyrillic `с` lost, looks like ASCII `c` |
| `48-точек` | `48-` | Suffix gone |
| `точек` | `` (empty) | File saved as `.md` (no name) |
| `1спредприятие-83` | `1-83` | Garbage |

Cascade: `--fix` ran `rename()` on 160 files, `_backup()` created 1130 `.bak` artifacts. Git tracked the originals as deleted.

## Proposed fix

Use Python's Unicode-aware `\w` character class (matches letters/digits/underscore in any script when `re.UNICODE` flag is active — default for `str` patterns in Python 3.x). Underscore is excluded explicitly to preserve kebab semantics.

```python
def fix_filename_casing(article: Article) -> tuple[bool, str]:
    """Rename files with spaces or non-kebab-case names.

    Preserves Unicode characters (Cyrillic, CJK, accented Latin, …) —
    uses Unicode-aware `\\w` character class instead of ASCII-only
    `[a-z0-9]`. Underscore is explicitly collapsed to '-' for kebab style.
    """
    stem = article.path.stem
    # \w matches Unicode word characters (letters + digits + _) when the
    # pattern is a `str` in Python 3.x (default UNICODE flag).
    # Explicitly include `_` in the negation class to convert it to '-'.
    new_stem = re.sub(r"[^\w-]+|_+", "-", stem).lower().strip("-")
    new_name = new_stem + ".md"
    if new_name == article.path.name:
        return False, "Already correct"
    new_path = article.path.parent / new_name
    if new_path.exists():
        return False, f"Cannot rename: '{new_name}' already exists"
    _backup(article.path)
    article.path.rename(new_path)
    return True, f"Renamed '{article.path.name}' -> '{new_name}'"
```

### Verified behaviour

| Input stem | Old output | New output |
|---|---|---|
| `1сenterprise` | `1-enterprise` ❌ | `1сenterprise` ✓ (unchanged — already valid) |
| `48-точек` | `48-` | `48-точек` ✓ |
| `точек` | empty | `точек` ✓ |
| `MyFile` | `myfile` | `myfile` ✓ (same as before) |
| `my file` | `my-file` | `my-file` ✓ (same as before) |
| `my_file` | `my-file` | `my-file` ✓ (explicit `_+` handles this) |
| `café` | `caf-` ❌ | `café` ✓ |
| `📄notes` | `notes` ❌ (emoji stripped) | `notes` (still stripped — emoji is not \w; acceptable) |

## Suggested PR description

```markdown
# fix: preserve Unicode characters in `fix_filename_casing`

The current regex `[^a-z0-9]+` strips Cyrillic, CJK, accented Latin, and
other non-ASCII letters from filenames when `--fix` is invoked. On a wiki
where pages are named in a non-Latin script (e.g. Russian: `точек.md`,
`1спредприятие-83.md`), `--fix` either produces garbage filenames or empty
stems (file saved as `.md` with no name).

This is a real production hazard — observed in
[github.com/Alex1980Alex/1C-Framework] where a single `--fix` invocation
on `docs/wiki/entities/` renamed/deleted 1131 files including one with
empty stem.

## Fix

Replace `[^a-z0-9]+` with `[^\w-]+|_+`. Under Python 3.x default UNICODE
mode, `\w` matches any Unicode letter/digit/underscore. The explicit
`_+` term ensures underscores still convert to `-` to preserve kebab
style.

## Tests added

- `test_fix_filename_casing_preserves_cyrillic` — `точек.md` stays as
  `точек.md`, not `.md`
- `test_fix_filename_casing_preserves_cjk` — `日本語.md` stays
- `test_fix_filename_casing_handles_mixed_ascii_cyrillic` —
  `1сenterprise.md` stays
- `test_fix_filename_casing_still_kebabs_ascii_uppercase` —
  `MyFile.md` → `myfile.md` (existing behaviour preserved)
- `test_fix_filename_casing_still_kebabs_underscores` —
  `my_file.md` → `my-file.md` (existing behaviour preserved)

## Breaking changes

None — the patch only changes behaviour for stems that contain non-ASCII
characters, which the old code transformed to garbage. ASCII-only stems
produce identical output.
```

## Local action items after upstream merge

1. Bump `kb-lint>=0.1.2` (or whatever the fixed version is) in [`pyproject.toml:129`](../../pyproject.toml).
2. Remove `_install_cyrillic_safety_patch()` from [`scripts/kb_lint_ci.py`](../../scripts/kb_lint_ci.py) — keep only `_reconfigure_utf8()`.
3. Update [`.claude/skills/hooks-skills-mcp-triad/SKILL.md`](../../.claude/skills/hooks-skills-mcp-triad/SKILL.md) note about Cyrillic-safety wrapper.
4. Drop this roadmap doc as obsolete.

## Submission checklist (human)

- [ ] Fork https://github.com/SingggggYee/kb-lint
- [ ] Branch `fix/unicode-filename-casing`
- [ ] Apply patch above to `kb_lint/fixer.py`
- [ ] Add 5 new tests to `tests/test_fixer.py`
- [ ] Verify existing tests still pass (`pytest -v`)
- [ ] Commit with message above
- [ ] Open PR; link this document
