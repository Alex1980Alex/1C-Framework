"""Event selection, hostile reports and target-source isolation for trusted CI."""

import copy
import importlib.util
import json
import os
import py_compile
import runpy
import subprocess
import sys
from pathlib import Path

import pytest

from src.harness import git_docs_boundary as core
from src.harness import git_docs_delivery as delivery

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CI = runpy.run_path(str(ROOT / "scripts/git_docs_ci.py"))
CODE = "src/pdf_framework/agents/check.py"
DOC = "docs/framework documentation/2_КОНТЕКСТ/2.3_RAG_АГЕНТЫ/check.md"


def git(root, *args):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    result = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "-c",
            "core.hooksPath=" + os.devnull,
            "-c",
            "commit.gpgsign=false",
            *args,
        ],
        capture_output=True,
        env=env,
        timeout=20,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.decode("utf-8").strip()


def put(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def commit(root, message):
    git(root, "add", "--all")
    git(root, "commit", "-qm", message)
    return git(root, "rev-parse", "HEAD")


def event(base, head):
    return {"number": 3, "pull_request": {"base": {"sha": base}, "head": {"sha": head}}}


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "target"
    root.mkdir()
    git(root, "init", "-q", "--initial-branch=main")
    git(root, "config", "user.name", "CI acceptance")
    git(root, "config", "user.email", "ci@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    put(root, CODE, "before\n")
    base = commit(root, "base")
    put(root, CODE, "after\n")
    violation = commit(root, "code without docs")
    put(root, DOC, "Documentation\n")
    head = commit(root, "docs")
    return root, base, violation, head


def test_real_pr_pass_and_code_only_fail(repo):
    root, base, violation, head = repo
    failed = CI["check"](root, "pull_request_target", event(base, violation))
    assert failed["verdict"] == "FAIL" and failed["report"]["findings"], failed
    passed = CI["check"](root, "pull_request_target", event(base, head))
    assert passed["verdict"] == "PASS" and passed["errors"] == [], passed
    assert passed["requested_target"] == passed["comparison_base"] == base
    assert passed["requested_head"] == passed["report"]["head"] == head


def test_divergent_pr_chooses_unique_merge_base_before_verify(repo, monkeypatch):
    root, base, _, head = repo
    git(root, "checkout", "-qb", "target-branch", base)
    put(root, "README.md", "target branch advancement\n")
    target = commit(root, "target advance")
    original = core.verify
    seen = []

    def observed(*args, **kwargs):
        seen.append((kwargs["base"], kwargs["head"]))
        return original(*args, **kwargs)

    monkeypatch.setattr(core, "verify", observed)
    result = CI["check"](root, "pull_request", event(target, head))
    assert result["verdict"] == "PASS", result
    assert result["requested_target"] == target and result["comparison_base"] == base
    assert seen == [(base, head)]


def test_missing_object_stays_unknown_without_verify(repo, monkeypatch):
    root, base, _, _ = repo

    def forbidden(*args, **kwargs):
        pytest.fail("checker must not run after missing event object")

    monkeypatch.setattr(core, "verify", forbidden)
    result = CI["check"](root, "pull_request_target", event(base, "9" * 40))
    assert result["verdict"] == "UNKNOWN" and result["errors"]
    assert result["comparison_base"] is None


@pytest.mark.parametrize(
    "name,payload",
    [
        ("workflow_dispatch", {}),
        ("pull_request_target", {}),
        ("pull_request", []),
        ("pull_request", {"pull_request": {"base": {}, "head": {}}}),
        ("pull_request", event("0" * 40, "1" * 40)),
        ("pull_request", event("HEAD", "1" * 40)),
        ("pull_request", event("1" * 40, "1" * 40 + "; echo bad")),
        ("push", {"before": "1" * 40, "after": "2" * 40}),
        ("push", {"before": "0" * 40, "after": "2" * 40, "created": True, "deleted": False}),
    ],
)
def test_malformed_or_unsupported_event_is_not_accepted(name, payload):
    with pytest.raises(ValueError):
        CI["event_inputs"](name, payload)


def test_push_requires_ancestor_and_records_original_endpoints(repo):
    root, base, _, head = repo
    payload = {"before": base, "after": head, "created": False, "deleted": False}
    result = CI["check"](root, "push", payload)
    assert result["verdict"] == "PASS" and result["comparison_base"] == base
    payload.update(before=head, after=base, forced=True)
    result = CI["check"](root, "push", payload)
    assert result["verdict"] == "UNKNOWN" and result["errors"]


@pytest.mark.parametrize("override", [{"base": "1" * 40}, {"base": "1" * 40, "head": "2" * 40}])
def test_explicit_endpoints_must_equal_validated_event(repo, override):
    root, base, _, head = repo
    result = CI["check"](root, "pull_request_target", event(base, head), **override)
    assert result["verdict"] == "UNKNOWN" and result["errors"]


@pytest.mark.parametrize(
    "key,value",
    [
        ("schema_version", True),
        ("checked_root", "/other"),
        ("git_dir", "/other/.git"),
        ("git_common_dir", "/other/.git"),
        ("base", "1" * 40),
        ("head", "2" * 40),
        ("scope", {"mode": "range", "paths": ["only-docs"], "exclusions": {}}),
        ("policy_sha256", "f" * 64),
        ("policy_version", "pretend"),
        ("index_fingerprint", "f" * 64),
        ("snapshot", {"stable": False, "id": "a" * 64}),
        ("errors", ["partial read"]),
        ("findings", [{"rule": "ignored"}]),
        ("author", "proven"),
    ],
)
def test_hostile_pass_report_is_rejected(repo, monkeypatch, key, value):
    root, base, _, head = repo
    report = core.verify(root, "range", base=base, head=head)
    assert report["verdict"] == "PASS"
    report = copy.deepcopy(report)
    report[key] = value
    monkeypatch.setattr(core, "verify", lambda *args, **kwargs: report)
    result = CI["check"](root, "pull_request_target", event(base, head))
    assert result["verdict"] == "UNKNOWN" and result["errors"], result


def test_pr_rule_weakening_does_not_replace_trusted_policy(repo):
    root, base, violation, _ = repo
    git(root, "checkout", "--detach", violation)
    put(root, "src/harness/git_docs_rules.json", '{"CODE_TO_DOMAIN": [], "SKIP_PATTERNS": [""]}')
    head = commit(root, "weaken candidate policy")
    result = CI["check"](root, "pull_request_target", event(base, head))
    assert result["verdict"] == "FAIL", result
    assert any(f["file"] == CODE for f in result["report"]["findings"])
    assert result["report"]["policy_sha256"] == core.policy.POLICY_SHA256


def test_actual_wrapper_never_imports_target_python(repo, tmp_path):
    root, base, violation, _ = repo
    marker = tmp_path / "executed"
    put(
        root,
        "src/__init__.py",
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('unsafe')\n",
    )
    archive = tmp_path / "trusted.zip"
    package = delivery.build(ROOT, archive, "1" * 40)
    payload = tmp_path / "event.json"
    payload.write_text(json.dumps(event(base, violation)), encoding="utf-8")
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            str(ROOT / "scripts/git_docs_ci.py"),
            "--root",
            str(root),
            "--event-name",
            "pull_request_target",
            "--event-file",
            str(payload),
            "--trusted-manifest",
            package["trusted_manifest_candidate"],
            "--expected-manifest-sha256",
            package["manifest_sha256"],
        ],
        capture_output=True,
        cwd=root,
        timeout=50,
    )
    assert result.returncode == 1, result.stderr
    assert json.loads(result.stdout)["verdict"] == "FAIL"
    assert not marker.exists()


def test_workflow_has_only_trusted_pr_checkout_and_read_permissions():
    workflow = (ROOT / ".github/workflows/git-docs.yml").read_text()
    assert "pull_request_target:" in workflow and "\n  push:" not in workflow
    assert "  pull_request_target:\n    branches: [master]\n    types:" in workflow
    assert "contents: read" in workflow and "write" not in workflow
    assert "ref: ${{ github.event.pull_request.base.sha }}" in workflow
    assert "pull_request.head" not in workflow
    assert "persist-credentials: false" in workflow and "fetch-depth: 0" in workflow
    assert "--trusted-manifest" in workflow and "--fetch-pr" in workflow
    assert "${{ github.event" not in workflow.split("run:", 1)[1]


@pytest.mark.parametrize("attack", ["package", "unchecked-pyc"])
@pytest.mark.parametrize("entry", ["ci", "verify", "pre_commit"])
def test_actual_clis_ignore_unmanifested_report_imports(repo, tmp_path, attack, entry):
    root, base, violation, _ = repo
    archive = tmp_path / "trusted.zip"
    package = delivery.build(ROOT, archive, "1" * 40)
    installed = tmp_path / "installed"
    import zipfile

    with zipfile.ZipFile(archive) as stream:
        stream.extractall(installed)
    marker = tmp_path / "untrusted-report-ran"
    malicious = (
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
        "def validate_report(*args): return []\n"
    )
    module_path = installed / "src/harness/git_docs_report.py"
    if attack == "package":
        put(installed, "src/harness/git_docs_report/__init__.py", malicious)
    else:
        candidate = tmp_path / "malicious.py"
        candidate.write_text(malicious, encoding="utf-8")
        py_compile.compile(
            str(candidate),
            cfile=importlib.util.cache_from_source(str(module_path)),
            doraise=True,
            invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH,
        )
    # Positive control: Python's normal importer really selects this attack.
    control = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import sys; sys.path.insert(0, "
            + repr(str(installed))
            + "); import src.harness.git_docs_report",
        ],
        capture_output=True,
        cwd=root,
        timeout=20,
    )
    assert control.returncode == 0 and marker.exists(), control.stderr
    marker.unlink()
    payload = tmp_path / "event.json"
    payload.write_text(json.dumps(event(base, violation)), encoding="utf-8")
    args = {
        "ci": [
            "--root",
            str(root),
            "--event-name",
            "pull_request_target",
            "--event-file",
            str(payload),
            "--trusted-manifest",
            package["trusted_manifest_candidate"],
            "--expected-manifest-sha256",
            package["manifest_sha256"],
        ],
        "verify": ["--root", str(root), "--mode", "range", "--base", base, "--head", violation],
        "pre_commit": ["--root", str(root)],
    }[entry]
    if entry == "pre_commit":
        put(root, CODE, "new staged violation\n")
        git(root, "add", "--", CODE)
    before_pyc = {p: p.read_bytes() for p in installed.rglob("*.pyc")}
    result = subprocess.run(
        [sys.executable, "-I", "-B", str(installed / ("scripts/git_docs_" + entry + ".py")), *args],
        capture_output=True,
        cwd=root,
        timeout=50,
    )
    assert result.returncode == 1, result.stderr
    report = json.loads(result.stdout)
    assert report["verdict"] == "FAIL", report
    if entry == "ci":
        assert report["report"]["verdict"] == "FAIL"
    assert not marker.exists()
    assert {p: p.read_bytes() for p in installed.rglob("*.pyc")} == before_pyc
