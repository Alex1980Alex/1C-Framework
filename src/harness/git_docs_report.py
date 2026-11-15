"""Fail-closed acceptance of checker reports against independently selected inputs."""
from __future__ import annotations

import re

from .git_docs_boundary import CheckError, valid_path

_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_REQUIRED = (
    "checked_root", "git_dir", "git_common_dir", "base", "head",
    "index_fingerprint", "policy_sha256", "policy_version", "scope",
)
_OPTIONAL = ("index_path", "comparison_policy")
_ENVELOPE = (
    "schema_version", "policy_version", "policy_sha256", "verdict", "scope",
    "checked_root", "git_dir", "git_common_dir", "base", "head", "index_fingerprint",
    "range_policy", "comparison_policy", "snapshot", "changes", "findings", "errors",
    "author", "adapter_status",
)


def _valid_scope(scope):
    if (not isinstance(scope, dict) or scope.get("mode") not in ("index", "range")
            or type(scope.get("paths")) is not list):
        return False
    try:
        if scope["paths"] != sorted({valid_path(path) for path in scope["paths"]}):
            return False
    except (CheckError, TypeError):
        return False
    exclusions = scope.get("exclusions")
    return (isinstance(exclusions, dict)
            and set(exclusions) == {"patterns", "submodule_worktrees"}
            and type(exclusions["patterns"]) is list
            and all(isinstance(pattern, str) for pattern in exclusions["patterns"])
            and exclusions["submodule_worktrees"] is True)


def _valid_changes(changes):
    if type(changes) is not list:
        return False
    for change in changes:
        if (not isinstance(change, dict) or set(change) != {"kind", "source", "path"}
                or not isinstance(change["kind"], str)
                or not re.fullmatch(r"[AMDT]|[RC](?:100|[0-9]{1,2})", change["kind"])):
            return False
        try:
            valid_path(change["path"])
            if change["kind"][0] in "RC":
                valid_path(change["source"])
            elif change["source"] is not None:
                return False
        except (CheckError, TypeError):
            return False
    return True


def validate_report(report, expected, returncode) -> list[str]:
    """Accept only a complete PASS matching the caller's fresh, trusted context."""
    errors = []
    if type(returncode) is not int or returncode != 0:
        errors.append("checker returncode must be integer zero")
    if not isinstance(report, dict) or not isinstance(expected, dict):
        return errors + ["report and expected inputs must be objects"]
    for key in _ENVELOPE:
        if key not in report:
            errors.append(f"missing report field: {key}")
    if type(report.get("schema_version")) is not int or report["schema_version"] != 1:
        errors.append("unsupported report schema_version")
    if report.get("verdict") != "PASS":
        errors.append("report verdict must be PASS")
    for key in ("findings", "errors"):
        if type(report.get(key)) is not list or report[key]:
            errors.append(f"report {key} must be an empty list")
    if report.get("author") != "not_assessed":
        errors.append("report author must be not_assessed")
    if report.get("adapter_status") != "not_used":
        errors.append("report adapter_status must be not_used")
    if not _valid_changes(report.get("changes")):
        errors.append("report changes must contain valid change records")
    if not _valid_scope(report.get("scope")):
        errors.append("invalid report scope")
    snapshot = report.get("snapshot")
    if (not isinstance(snapshot, dict) or snapshot.get("stable") is not True
            or not isinstance(snapshot.get("id"), str)
            or not _SHA256.fullmatch(snapshot["id"])):
        errors.append("report requires a stable SHA256 snapshot")
    for key in _REQUIRED + tuple(k for k in _OPTIONAL if k in expected):
        if key not in expected or key not in report or report[key] != expected[key]:
            errors.append(f"report binding mismatch: {key}")
    for key in ("checked_root", "git_dir", "git_common_dir", "policy_version"):
        if not isinstance(expected.get(key), str) or not expected[key]:
            errors.append(f"invalid expected input: {key}")
    if (not isinstance(expected.get("policy_sha256"), str)
            or not _SHA256.fullmatch(expected["policy_sha256"])):
        errors.append("invalid expected policy_sha256")
    scope = expected.get("scope")
    if not _valid_scope(scope):
        errors.append("invalid expected scope")
        return errors
    mode = scope["mode"]
    if (report.get("range_policy") != ("net" if mode == "range" else None)
            or report.get("comparison_policy", "net" if mode == "range" else "current_head_delta")
            != ("net" if mode == "range" else "current_head_delta")):
        errors.append("contradictory comparison policy")
    if mode == "index":
        if (expected.get("base") is not None
                or not isinstance(expected.get("index_fingerprint"), str)
                or not _SHA256.fullmatch(expected["index_fingerprint"])):
            errors.append("invalid expected index identity")
    elif expected.get("index_fingerprint") is not None or report.get("index_path") is not None:
        errors.append("range report cannot identify an index")
    for key in (("head",) if mode == "index" else ("base", "head")):
        if not isinstance(expected.get(key), str) or not re.fullmatch(
                r"(?:[0-9a-f]{40}|[0-9a-f]{64})", expected[key]):
            errors.append(f"invalid expected commit: {key}")
    return errors
