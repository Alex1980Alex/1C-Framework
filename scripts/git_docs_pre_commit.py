"""Check Git's selected commit index against current HEAD, including amend deltas.

Run this final in a pre-commit chain, after any handler that changes the index.
This does not attest an amended commit against its parent; CI checks its net range.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.dont_write_bytecode = True
_helper = Path(__file__).with_name("git_docs_source_loader.py")
_loader = {"__file__": str(_helper), "__name__": "_git_docs_source_loader"}
exec(compile(_helper.read_bytes(), str(_helper), "exec"), _loader)
_runtime, _ = _loader["load_runtime"](Path(__file__).resolve().parents[1])
_core = _runtime["src.harness.git_docs_boundary"]
EXIT_CODES, Git = _core.EXIT_CODES, _core.Git
empty_report, verify = _core.empty_report, _core.verify
validate_report = _runtime["src.harness.git_docs_report"].validate_report


def _context(root, index_path):
    git = Git(root, index_path=index_path)
    private, common = git.locations()
    context = empty_report(str(git.root), "index", (), None, git.current_head())
    context.update(
        git_dir=private,
        git_common_dir=common,
        index_path=str(git.index_path),
        index_fingerprint=git.index_state()[0],
    )
    return {
        key: context[key]
        for key in (
            "checked_root",
            "git_dir",
            "git_common_dir",
            "base",
            "head",
            "scope",
            "policy_sha256",
            "policy_version",
            "index_path",
            "index_fingerprint",
            "comparison_policy",
        )
    }


def check_commit(root, *, index_path=None):
    """Bind PASS to the selected index before and after checking; never switch inputs."""
    report = empty_report(str(root), "index", (), None, None)
    try:
        expected = _context(root, index_path)
        report = verify(root, "index", index_path=index_path)
        code = EXIT_CODES.get(report.get("verdict"), 2)
        if code:
            return report, code
        errors = validate_report(report, expected, code)
        if _context(root, index_path) != expected:
            errors.append("selected commit state changed before report acceptance; retry")
        if errors:
            report["verdict"] = "UNKNOWN"
            report["errors"] = list(report.get("errors", [])) + errors
            return report, 2
        return report, 0
    except Exception as exc:
        report["verdict"] = "UNKNOWN"
        report["errors"] = list(report.get("errors", [])) + [f"{type(exc).__name__}: {exc}"]
        return report, 2


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(Path.cwd()))
    args = parser.parse_args(argv)
    # This hook bridge is the only entry that intentionally reads GIT_INDEX_FILE.
    # Direct checker API/CLI ignore every inherited GIT_* selector.
    inherited = os.environ.get("GIT_INDEX_FILE")
    index_path = str(Path(inherited).absolute()) if inherited else None
    report, code = check_commit(args.root, index_path=index_path)
    print(json.dumps(report, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
