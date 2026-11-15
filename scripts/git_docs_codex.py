"""Read-only Codex bridge for a committed net range.

The caller selects a trusted accepted package and Python/bootstrap; this adapter
does not authenticate a downloaded package. Worktree/index and authorship are
outside the assessment.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

sys.dont_write_bytecode = True


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _nonfinite(value):
    raise ValueError(f"nonfinite JSON number: {value}")


def _float(value):
    result = float(value)
    if not math.isfinite(result):
        _nonfinite(value)
    return result


def _runtime(package):
    helper = package / "scripts/git_docs_source_loader.py"
    namespace = {"__file__": str(helper), "__name__": "_git_docs_source_loader"}
    exec(compile(helper.read_bytes(), str(helper), "exec"), namespace)
    return namespace["load_runtime"](package)[0]


def _context(core, root, base, head, timeout):
    git = core.Git(root, budget=timeout)
    private, common = git.locations()
    base = git.commit(base)
    head = git.current_head() if head is None else git.commit(head)
    context = core.empty_report(str(git.root), "range", (), base, head)
    context.update(git_dir=private, git_common_dir=common)
    keys = (
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
        "range_policy",
    )
    return {key: context[key] for key in keys}


def _fail_errors(report, expected, validator, core):
    errors = []
    if any(key not in report for key in validator._ENVELOPE):
        errors.append("incomplete FAIL envelope")
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        errors.append("unsupported FAIL schema")
    for key, value in expected.items():
        if type(report.get(key)) is not type(value) or report.get(key) != value:
            errors.append(f"FAIL binding mismatch: {key}")
    if report.get("author") != "not_assessed" or report.get("adapter_status") != "not_used":
        errors.append("invalid FAIL attribution or inner adapter status")
    if not validator._valid_scope(report.get("scope")) or not validator._valid_changes(
        report.get("changes")
    ):
        errors.append("invalid FAIL scope or changes")
    snapshot = report.get("snapshot")
    if (
        not isinstance(snapshot, dict)
        or snapshot.get("stable") is not True
        or not isinstance(snapshot.get("id"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", snapshot["id"])
    ):
        errors.append("FAIL requires a stable SHA256 snapshot")
    if type(report.get("errors")) is not list or report["errors"]:
        errors.append("FAIL errors must be empty")
    findings = report.get("findings")
    if type(findings) is not list or not findings:
        errors.append("FAIL requires findings")
    else:
        for finding in findings:
            try:
                if not isinstance(finding, dict):
                    raise ValueError("finding must be an object")
                core.valid_path(finding.get("file"))
                if any(
                    not isinstance(finding.get(key), str) or not finding[key]
                    for key in ("rule", "required")
                ):
                    raise ValueError("finding requires rule and required strings")
            except (ValueError, TypeError, core.CheckError):
                errors.append("invalid FAIL finding")
    return errors


def check(package_root, root, base, head=None, timeout=45):
    """Invoke only the fixed accepted CLI and bind its result to fresh Git inputs."""
    envelope = {
        "schema_version": 1,
        "adapter_status": "not_invoked",
        "verdict": "UNKNOWN",
        "context": None,
        "checker_report": None,
        "adapter_errors": [],
    }
    started = False
    try:
        if not math.isfinite(timeout) or not 0 < timeout <= 300:
            raise ValueError("timeout must be finite and in (0, 300] seconds")
        deadline = time.monotonic() + timeout

        def remaining():
            budget = deadline - time.monotonic()
            if budget <= 0:
                raise TimeoutError("adapter overall timeout expired")
            return budget

        package = Path(package_root)
        if not package.is_absolute() or not Path(root).is_absolute():
            raise ValueError("absolute --package-root and --root required")
        package = package.resolve(strict=True)
        cli = package / "scripts/git_docs_verify.py"
        if not cli.is_file():
            envelope["adapter_status"] = "unavailable"
            raise FileNotFoundError(f"accepted checker CLI unavailable: {cli}")
        runtime = _runtime(package)
        core = runtime["src.harness.git_docs_boundary"]
        validator = runtime["src.harness.git_docs_report"]
        expected = _context(core, root, base, head, remaining())
        envelope["context"] = expected
        command = [
            sys.executable,
            "-I",
            "-B",
            str(cli),
            "--root",
            expected["checked_root"],
            "--mode",
            "range",
            "--base",
            expected["base"],
            "--head",
            expected["head"],
        ]
        child_env = core.Git(root, budget=remaining()).env
        child_timeout = remaining()
        started = True
        result = subprocess.run(
            command,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            timeout=child_timeout,
            env=child_env,
        )
        envelope["adapter_status"] = "invoked"
        report = json.loads(
            result.stdout, object_pairs_hook=_pairs, parse_constant=_nonfinite, parse_float=_float
        )
        envelope["checker_report"] = report
        if not isinstance(report, dict):
            raise ValueError("checker report must be an object")
        if result.stderr:
            raise ValueError("checker emitted unexpected stderr")
        if _context(core, root, base, head, remaining()) != expected:
            raise ValueError("selected Git context changed before acceptance; retry")
        remaining()
        verdict = report.get("verdict")
        if (
            type(result.returncode) is not int
            or {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}.get(verdict) != result.returncode
        ):
            raise ValueError("checker returncode/verdict mismatch")
        if verdict == "PASS":
            errors = validator.validate_report(report, expected, result.returncode)
        elif verdict == "FAIL":
            errors = _fail_errors(report, expected, validator, core)
        else:
            if (
                type(report.get("schema_version")) is not int
                or report["schema_version"] != 1
                or any(key not in report for key in validator._ENVELOPE)
                or report.get("author") != "not_assessed"
                or report.get("adapter_status") != "not_used"
                or type(report.get("errors")) is not list
                or not all(isinstance(error, str) for error in report["errors"])
            ):
                raise ValueError("malformed UNKNOWN envelope")
            envelope["adapter_errors"].append(
                "checker returned UNKNOWN; inspect checker_report.errors"
            )
            return envelope, 2
        if errors:
            raise ValueError("; ".join(errors))
        envelope["verdict"] = verdict
        return envelope, result.returncode
    except Exception as exc:
        if started:
            envelope["adapter_status"] = "protocol_error"
        envelope["adapter_errors"].append(f"{type(exc).__name__}: {exc}")
        return envelope, 2


def _human(report):
    def quote(value):
        return json.dumps(value, ensure_ascii=True)

    context = report["context"] or {}
    lines = [
        f"Git/docs: {report['verdict']} ({report['adapter_status']})",
        "Область: committed net range; рабочее дерево, индекс и авторство не оценены.",
        f"root={quote(context.get('checked_root'))} base={quote(context.get('base'))} head={quote(context.get('head'))}",
    ]
    inner = report["checker_report"]
    if isinstance(inner, dict):
        for key in ("findings", "errors"):
            if isinstance(inner.get(key), list):
                lines.extend(f"{key}: {quote(item)}" for item in inner[key])
    lines.extend(f"adapter_error: {quote(error)}" for error in report["adapter_errors"])
    return "\n".join(lines)


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    machine = any(
        args[i : i + 2] == ["--format", "json"] or args[i] == "--format=json"
        for i in range(len(args))
    )
    try:
        parser = _Parser(description=__doc__)
        parser.add_argument("--package-root", required=True)
        parser.add_argument("--root", required=True)
        parser.add_argument("--base", required=True)
        parser.add_argument("--head")
        parser.add_argument("--format", choices=("human", "json"), default="human")
        parser.add_argument(
            "--timeout",
            type=float,
            default=45,
            help="overall adapter budget, in seconds (0 < timeout <= 300)",
        )
        parsed = parser.parse_args(args)
        machine = parsed.format == "json"
        report, code = check(
            parsed.package_root, parsed.root, parsed.base, parsed.head, parsed.timeout
        )
    except Exception as exc:
        report = {
            "schema_version": 1,
            "adapter_status": "not_invoked",
            "verdict": "UNKNOWN",
            "context": None,
            "checker_report": None,
            "adapter_errors": [str(exc)],
        }
        code = 2
    print(json.dumps(report, ensure_ascii=True) if machine else _human(report))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
