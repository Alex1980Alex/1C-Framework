"""Trusted Git/docs CI receiver. Target repositories supply Git objects, never Python."""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
import os
import re
import subprocess
import time
from pathlib import Path

TRUSTED_ROOT = Path(__file__).resolve().parents[1]


def event_inputs(name, event):
    if type(event) is not dict:
        raise ValueError("event must be an object")
    if name in {"pull_request", "pull_request_target"}:
        pr = event.get("pull_request")
        if type(pr) is not dict:
            raise ValueError("missing pull_request")
        base, head = pr.get("base"), pr.get("head")
        if type(base) is not dict or type(head) is not dict:
            raise ValueError("missing PR endpoints")
        base, head = base.get("sha"), head.get("sha")
    elif name == "push":
        if event.get("deleted") is not False or event.get("created") is not False:
            raise ValueError("created/deleted push is unsupported")
        base, head = event.get("before"), event.get("after")
    else:
        raise ValueError("unsupported event")
    for value in (base, head):
        if (
            not isinstance(value, str)
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", value)
            or set(value) == {"0"}
        ):
            raise ValueError("full nonzero event SHA required")
    return base, head


def check(
    root, event_name, event, *, base=None, head=None, budget=35, fetch_pr=False, runtime=None
):
    if runtime is None:
        from src.harness import git_docs_boundary as core
        from src.harness.git_docs_report import validate_report
    else:
        core = runtime["src.harness.git_docs_boundary"]
        validate_report = runtime["src.harness.git_docs_report"].validate_report

    result = {
        "schema_version": 1,
        "verdict": "UNKNOWN",
        "event": event_name,
        "requested_target": None,
        "requested_head": None,
        "comparison_base": None,
        "report": None,
        "errors": [],
    }
    try:
        requested_base, requested_head = event_inputs(event_name, event)
        result.update(requested_target=requested_base, requested_head=requested_head)
        if (base is None) != (head is None):
            raise ValueError("explicit base and head must be supplied together")
        if base is not None and (base != requested_base or head != requested_head):
            raise ValueError("explicit endpoints differ from event")
        git = core.Git(root, budget)
        if fetch_pr:
            number = event.get("number")
            if (
                event_name not in {"pull_request", "pull_request_target"}
                or type(number) is not int
                or number <= 0
            ):
                raise ValueError("explicit PR fetch requires a positive PR number")
            # Only an explicit flag enables network; fixed origin and numeric ref, no URL from PR.
            git.run(
                "-c",
                "core.hooksPath=" + os.devnull,
                "-c",
                "gc.auto=0",
                "-c",
                "maintenance.auto=false",
                "fetch",
                "--quiet",
                "--no-progress",
                "--no-tags",
                "--no-recurse-submodules",
                "origin",
                f"+refs/pull/{number}/head:refs/git-docs/head",
            )
            if git.line("rev-parse", "--verify", "refs/git-docs/head^{commit}") != requested_head:
                raise ValueError("fetched PR head differs from event")
        git.commit(requested_base)
        git.commit(requested_head)
        if event_name in {"pull_request", "pull_request_target"}:
            candidates = (
                git.run("merge-base", "--all", requested_base, requested_head)
                .decode("ascii")
                .splitlines()
            )
            if len(candidates) != 1:
                raise ValueError("PR requires exactly one merge-base")
            comparison = git.commit(candidates[0])
        else:
            git.run("merge-base", "--is-ancestor", requested_base, requested_head)
            comparison = requested_base
        result["comparison_base"] = comparison
        private, common = git.locations()
        expected = {
            "checked_root": str(git.root),
            "git_dir": private,
            "git_common_dir": common,
            "base": comparison,
            "head": requested_head,
            "index_fingerprint": None,
            "index_path": None,
            "policy_sha256": core.policy.POLICY_SHA256,
            "policy_version": core.policy.POLICY_VERSION,
            "scope": core.empty_report(git.root, "range", (), comparison, requested_head)["scope"],
        }
        report = core.verify(
            git.root,
            "range",
            base=comparison,
            head=requested_head,
            budget=max(0.001, git.deadline - time.monotonic()),
        )
        result["report"] = report
        code = core.EXIT_CODES.get(report.get("verdict"), 2) if type(report) is dict else 2
        errors = validate_report(report, expected, code)
        # Check selected objects and locations again before accepting the receiver result.
        git.commit(comparison)
        git.commit(requested_head)
        if git.locations() != (private, common):
            errors.append("Git locations changed before acceptance")
        if errors:
            result["errors"] = errors
            if type(report) is dict and report.get("verdict") == "FAIL" and code == 1:
                result["verdict"] = "FAIL"
        else:
            result["verdict"] = "PASS"
    except (OSError, ValueError, TypeError, UnicodeError, subprocess.SubprocessError) as exc:
        result["errors"].append(str(exc))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True)
    parser.add_argument("--event-name", required=True)
    parser.add_argument("--event-file", required=True)
    parser.add_argument("--base")
    parser.add_argument("--head")
    parser.add_argument("--budget", type=float, default=35)
    parser.add_argument("--fetch-pr", action="store_true")
    parser.add_argument("--trusted-manifest", required=True)
    parser.add_argument("--expected-manifest-sha256")
    args = parser.parse_args(argv)
    try:
        helper = Path(__file__).with_name("git_docs_source_loader.py")
        loader = {"__file__": str(helper), "__name__": "_git_docs_source_loader"}
        exec(compile(helper.read_bytes(), str(helper), "exec"), loader)
        runtime, manifest_sha = loader["load_runtime"](
            TRUSTED_ROOT, args.trusted_manifest, args.expected_manifest_sha256
        )
        raw = Path(args.event_file).read_bytes()
        if len(raw) > 5_000_000:
            raise ValueError("event too large")
        event = json.loads(
            raw.decode("utf-8"), object_pairs_hook=runtime["src.harness.git_docs_delivery"]._unique
        )
        result = check(
            args.root,
            args.event_name,
            event,
            base=args.base,
            head=args.head,
            budget=args.budget,
            fetch_pr=args.fetch_pr,
            runtime=runtime,
        )
        result["checker_manifest_sha256"] = manifest_sha
    except Exception as exc:
        result = {"schema_version": 1, "verdict": "UNKNOWN", "errors": [str(exc)]}
    print(json.dumps(result, ensure_ascii=True))
    return {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}[result["verdict"]]


if __name__ == "__main__":
    raise SystemExit(main())
