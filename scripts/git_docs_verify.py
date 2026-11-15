"""Verify an explicit Git index or net commit range; emit a v1 JSON report."""
import sys

sys.dont_write_bytecode = True

import argparse
import json
from pathlib import Path


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


_FALLBACK = {
    "schema_version": 1, "policy_version": None, "policy_sha256": None,
    "verdict": "UNKNOWN", "scope": {"mode": None, "paths": [], "exclusions": {}},
    "checked_root": None, "git_dir": None, "git_common_dir": None,
    "base": None, "head": None, "index_fingerprint": None, "index_path": None,
    "range_policy": None, "comparison_policy": None,
    "snapshot": {"id": None, "stable": False}, "changes": [], "findings": [],
    "errors": [], "author": "not_assessed", "adapter_status": "not_used",
}


def main(argv=None):
    try:
        parser = _Parser(description=__doc__)
        parser.add_argument("--root", required=True)
        parser.add_argument("--mode", required=True, choices=("index", "range"))
        parser.add_argument("--base")
        parser.add_argument("--head")
        parser.add_argument("--index-path")
        parser.add_argument("--path", action="append", default=[])
        parser.add_argument("--budget", type=float, default=35)
        args = parser.parse_args(argv)
        helper = Path(__file__).with_name("git_docs_source_loader.py")
        loader = {"__file__": str(helper), "__name__": "_git_docs_source_loader"}
        exec(compile(helper.read_bytes(), str(helper), "exec"), loader)
        runtime, _ = loader["load_runtime"](Path(__file__).resolve().parents[1])
        core = runtime["src.harness.git_docs_boundary"]
        report = core.verify(args.root, args.mode, base=args.base, head=args.head,
                        paths=args.path, budget=args.budget, index_path=args.index_path)
        code = core.EXIT_CODES[report["verdict"]]
    except Exception as exc:
        # An unavailable checker/policy is explicit UNKNOWN, including import failures.
        report = dict(_FALLBACK, errors=[f"{type(exc).__name__}: {exc}"])
        code = 2
    print(json.dumps(report, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
