"""Contradictory and stale PASS envelopes must never satisfy the report consumer."""

import copy

import pytest

from src.harness.git_docs_boundary import empty_report
from src.harness.git_docs_report import validate_report

pytestmark = pytest.mark.unit


def sample():
    report = empty_report("/checked", "index", (), None, "a" * 40)
    report.update(
        verdict="PASS",
        git_dir="/checked/.git",
        git_common_dir="/checked/.git",
        index_path="/checked/.git/index",
        index_fingerprint="b" * 64,
        snapshot={"stable": True, "id": "c" * 64},
    )
    expected = {
        key: copy.deepcopy(report[key])
        for key in (
            "checked_root",
            "git_dir",
            "git_common_dir",
            "base",
            "head",
            "index_fingerprint",
            "index_path",
            "policy_version",
            "policy_sha256",
            "scope",
            "comparison_policy",
        )
    }
    return report, expected


def test_complete_matching_pass():
    report, expected = sample()
    assert validate_report(report, expected, 0) == []


@pytest.mark.parametrize(
    "key",
    [
        "checked_root",
        "git_dir",
        "git_common_dir",
        "base",
        "head",
        "index_fingerprint",
        "index_path",
        "policy_version",
        "policy_sha256",
        "scope",
        "comparison_policy",
    ],
)
def test_wrong_or_stale_binding_rejected(key):
    report, expected = sample()
    report[key] = "different"
    assert any(key in error for error in validate_report(report, expected, 0))


@pytest.mark.parametrize(
    "key",
    [
        "checked_root",
        "git_dir",
        "git_common_dir",
        "base",
        "head",
        "index_fingerprint",
        "policy_version",
        "policy_sha256",
        "scope",
    ],
)
def test_missing_expected_binding_is_not_a_wildcard(key):
    report, expected = sample()
    del expected[key]
    assert validate_report(report, expected, 0)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("schema_version", True),
        ("schema_version", 2),
        ("schema_version", "1"),
        ("verdict", "UNKNOWN"),
        ("verdict", "FAIL"),
        ("errors", ["problem"]),
        ("errors", None),
        ("findings", {}),
        ("findings", ["missing docs"]),
        ("author", "current_agent"),
        ("snapshot", None),
        ("snapshot", {"stable": 1, "id": "c" * 64}),
        ("snapshot", {"stable": True, "id": ""}),
        ("snapshot", {"stable": True, "id": "not-a-sha"}),
        ("range_policy", "net"),
    ],
)
def test_contradictory_pass_envelope_rejected(key, value):
    report, expected = sample()
    report[key] = value
    assert validate_report(report, expected, 0)


@pytest.mark.parametrize("returncode", [1, 2, -1, None, False, "0"])
def test_bad_returncode_never_passes(returncode):
    report, expected = sample()
    assert validate_report(report, expected, returncode)


def test_v1_without_optional_index_identity_remains_accepted():
    report, expected = sample()
    del report["index_path"]
    del expected["index_path"]
    assert validate_report(report, expected, 0) == []


def test_range_has_no_index_and_requires_net_policy():
    report, expected = sample()
    for mapping in (report, expected):
        mapping.update(
            base="d" * 40, index_fingerprint=None, index_path=None, comparison_policy="net"
        )
        mapping["scope"]["mode"] = "range"
    report["range_policy"] = "net"
    assert validate_report(report, expected, 0) == []
    report["range_policy"] = None
    assert validate_report(report, expected, 0)


@pytest.mark.parametrize("value", [None, [], "PASS", 1])
def test_nonobject_report_rejected(value):
    _, expected = sample()
    assert validate_report(value, expected, 0)


@pytest.mark.parametrize("key", list(sample()[0].keys() - {"index_path"}))
def test_every_mandatory_report_field_is_required(key):
    report, expected = sample()
    del report[key]
    assert validate_report(report, expected, 0)


@pytest.mark.parametrize(
    "scope",
    [
        {"mode": "range", "paths": [123], "exclusions": {}},
        {"mode": [], "paths": [], "exclusions": {}},
        {"mode": "index", "paths": ["../escape"], "exclusions": {}},
        {"mode": "index", "paths": [], "exclusions": {}},
        {
            "mode": "index",
            "paths": [],
            "exclusions": {"patterns": [1], "submodule_worktrees": True},
        },
    ],
)
def test_matching_malformed_scopes_are_rejected(scope):
    report, expected = sample()
    report["scope"] = expected["scope"] = scope
    assert validate_report(report, expected, 0)


@pytest.mark.parametrize(
    "changes",
    [
        {},
        [None],
        [{}],
        [{"kind": "M", "path": "x", "source": "extra"}],
        [{"kind": "R100", "path": "x", "source": None}],
        [{"kind": "M", "path": "../escape", "source": None}],
    ],
)
def test_malformed_changes_rejected(changes):
    report, expected = sample()
    report["changes"] = changes
    assert validate_report(report, expected, 0)
