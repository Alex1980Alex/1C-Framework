"""Exercise the Codex bridge with real committed ranges and broken transports."""

import copy
import importlib.util
import json
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

PACKAGE = Path(__file__).resolve().parents[2]
SCRIPT = PACKAGE / "scripts/git_docs_codex.py"
spec = importlib.util.spec_from_file_location("git_docs_codex_test", SCRIPT)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True).stdout.decode().strip()


@pytest.fixture
def commits(tmp_path):
    root = tmp_path / "repository with spaces"
    root.mkdir()
    git(root, "init")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "user.name", "Fixture")
    (root / "initial.txt").write_text("initial", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "initial")
    base = git(root, "rev-parse", "HEAD")
    feature = root / "src/pdf_framework/agents/feature.py"
    feature.parent.mkdir(parents=True)
    feature.write_text("print('example')\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "code")
    code = git(root, "rev-parse", "HEAD")
    doc = root / "docs/framework documentation/2_КОНТЕКСТ/2.3_RAG_АГЕНТЫ/p4_acceptance.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("Documentation updated.\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "docs")
    return root, base, code, git(root, "rev-parse", "HEAD")


def test_real_fail_and_pass(commits):
    root, base, code, docs = commits
    failed, rc = adapter.check(PACKAGE, root, base, code)
    assert rc == 1 and failed["verdict"] == "FAIL"
    assert failed["checker_report"]["findings"][0]["file"] == "src/pdf_framework/agents/feature.py"
    assert failed["checker_report"]["findings"][0]["rule"] == "domain-docs"
    passed, rc = adapter.check(PACKAGE, root, base, docs)
    assert rc == 0 and passed["verdict"] == "PASS"
    assert passed["checker_report"]["author"] == "not_assessed"
    assert passed["checker_report"]["adapter_status"] == "not_used"
    assert passed["context"]["scope"]["mode"] == "range"


def test_invalid_base_and_missing_cli(commits, tmp_path):
    root, _, _, _ = commits
    report, rc = adapter.check(PACKAGE, root, "not-a-sha")
    assert rc == 2 and report["adapter_status"] == "not_invoked"
    report, rc = adapter.check(tmp_path, root, "0" * 40)
    assert rc == 2 and report["adapter_status"] == "unavailable"


@pytest.mark.parametrize("payload,rc", [
    (b"", 0), (b"noise {}", 0), (b'{"verdict":"PASS","verdict":"FAIL"}', 0),
    (b'{"verdict":"PASS","value":NaN}', 0), (b"[]", 0),
    (b'{"verdict":"PASS","value":1e999}', 0),
    (b'{"verdict":"PASS","schema_version":1}', 1),
])
def test_broken_protocol(commits, monkeypatch, payload, rc):
    root, base, _, head = commits
    original = adapter.subprocess.run

    def run(command, **kwargs):
        if command[0] == adapter.sys.executable:
            return SimpleNamespace(stdout=payload, stderr=b"", returncode=rc)
        return original(command, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "run", run)
    report, result = adapter.check(PACKAGE, root, base, head)
    assert result == 2 and report["adapter_status"] == "protocol_error"
    assert report["adapter_errors"]


def test_timeout_and_exact_argv(commits, monkeypatch):
    root, base, _, head = commits
    original = adapter.subprocess.run

    def run(command, **kwargs):
        if command[0] == adapter.sys.executable:
            assert command == [adapter.sys.executable, "-I", "-B", str(PACKAGE / "scripts/git_docs_verify.py"),
                               "--root", str(root.resolve()), "--mode", "range", "--base", base, "--head", head]
            assert "shell" not in kwargs
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return original(command, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "run", run)
    report, rc = adapter.check(PACKAGE, root, base, head)
    assert rc == 2 and "TimeoutExpired" in report["adapter_errors"][0]


def test_stale_default_head(commits, monkeypatch):
    root, base, code, _ = commits
    original = adapter._context
    calls = 0

    def context(*args):
        nonlocal calls
        result = original(*args)
        calls += 1
        if calls == 2:
            result["head"] = code
        return result

    monkeypatch.setattr(adapter, "_context", context)
    report, rc = adapter.check(PACKAGE, root, base)
    assert rc == 2 and report["checker_report"]["verdict"] == "PASS"
    assert "changed" in report["adapter_errors"][0]


def test_selectors_and_output(commits, monkeypatch, capsys):
    root, base, _, head = commits
    monkeypatch.setenv("GIT_DIR", str(root / "wrong"))
    monkeypatch.setenv("GIT_WORK_TREE", str(root / "wrong"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(root / "wrong"))
    args = ["--package-root", str(PACKAGE), "--root", str(root), "--base", base, "--head", head]
    assert adapter.main(args + ["--format", "json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == "PASS"
    assert report["checker_report"]["adapter_status"] == "not_used"
    assert adapter.main(args) == 0
    human = capsys.readouterr().out
    assert "committed net range" in human and head in human


@pytest.fixture
def child_response(monkeypatch):
    """Replace only the checker child, leaving every Git plumbing call real."""
    original = adapter.subprocess.run
    response = SimpleNamespace(stdout=b"", stderr=b"", returncode=0)

    def run(command, **kwargs):
        if command[0] == adapter.sys.executable:
            return response
        return original(command, **kwargs)

    monkeypatch.setattr(adapter.subprocess, "run", run)
    return response


@pytest.mark.parametrize("verdict", ["PASS", "FAIL"])
@pytest.mark.parametrize("field,value,error", [
    ("schema_version", True, "schema"),
    ("base", "0" * 40, "base"),
    ("head", "0" * 40, "head"),
    ("checked_root", "/different-root", "checked_root"),
    ("git_dir", "/different-private", "git_dir"),
    ("git_common_dir", "/different-common", "git_common_dir"),
    ("policy_sha256", "0" * 64, "policy_sha256"),
    ("snapshot.stable", False, "snapshot"),
    ("snapshot.id", "not-sha256", "snapshot"),
    ("findings", None, "finding"),
    ("errors", {}, "errors"),
    ("scope", {}, "scope"),
    ("changes", [{"kind": "A", "source": None, "path": "../escape.py"}], "changes"),
    ("author", "assessed", "attribution"),
    ("adapter_status", "invoked", "adapter"),
    ("returncode", 9, "returncode"),
])
def test_full_report_mutation(commits, child_response, verdict, field, value, error):
    root, base, code, docs = commits
    head = docs if verdict == "PASS" else code
    core = adapter._runtime(PACKAGE)["src.harness.git_docs_boundary"]
    original = core.verify(str(root), "range", base=base, head=head)
    expected_code = 0 if verdict == "PASS" else 1
    assert original["verdict"] == verdict
    child_response.stdout = json.dumps(original).encode()
    child_response.returncode = expected_code
    positive, rc = adapter.check(PACKAGE, root, base, head)
    assert rc == expected_code and positive["verdict"] == verdict
    assert positive["checker_report"] == original
    damaged = copy.deepcopy(original)
    if field == "returncode":
        child_response.returncode = value
    elif "." in field:
        parent, name = field.split(".")
        damaged[parent][name] = value
    else:
        damaged[field] = value
    child_response.stdout = json.dumps(damaged).encode()
    rejected, rc = adapter.check(PACKAGE, root, base, head)
    assert rc == 2 and rejected["verdict"] == "UNKNOWN"
    assert rejected["adapter_status"] == "protocol_error"
    assert rejected["checker_report"] == damaged
    detail = "; ".join(rejected["adapter_errors"])
    # PASS uses unchanged core validator wording; FAIL has its own attribution check.
    expected_error = "author" if field == "author" and verdict == "PASS" else error
    assert expected_error in detail


@pytest.mark.parametrize("field,value", [
    ("file", "../escape.py"), ("rule", ""), ("required", 42),
])
def test_full_fail_finding_mutation(commits, child_response, field, value):
    root, base, code, _ = commits
    core = adapter._runtime(PACKAGE)["src.harness.git_docs_boundary"]
    report = core.verify(str(root), "range", base=base, head=code)
    assert report["verdict"] == "FAIL"
    report["findings"][0][field] = value
    child_response.stdout = json.dumps(report).encode()
    child_response.returncode = 1
    rejected, rc = adapter.check(PACKAGE, root, base, code)
    assert rc == 2 and "invalid FAIL finding" in rejected["adapter_errors"][0]


def test_valid_checker_unknown_and_stderr(commits, child_response):
    root, base, _, head = commits
    core = adapter._runtime(PACKAGE)["src.harness.git_docs_boundary"]
    report = core.verify(str(root), "range", base=base, head=head)
    report.update(verdict="UNKNOWN", errors=["test checker failure"],
                  snapshot={"id": None, "stable": False})
    child_response.stdout = json.dumps(report).encode()
    child_response.returncode = 2
    unknown, rc = adapter.check(PACKAGE, root, base, head)
    assert rc == 2 and unknown["adapter_status"] == "invoked"
    assert unknown["checker_report"] == report
    assert "checker returned UNKNOWN" in unknown["adapter_errors"][0]
    child_response.stderr = b"unexpected child diagnostic"
    rejected, rc = adapter.check(PACKAGE, root, base, head)
    assert rc == 2 and rejected["adapter_status"] == "protocol_error"
    assert rejected["checker_report"] == report
    assert "stderr" in rejected["adapter_errors"][0]


def test_overall_deadline_covers_preflight(commits, monkeypatch):
    root, base, _, head = commits
    original = adapter._context
    clock = [0.0]
    monkeypatch.setattr(adapter.time, "monotonic", lambda: clock[0])

    def context(*args):
        result = original(*args)
        clock[0] = 46.0
        return result

    monkeypatch.setattr(adapter, "_context", context)
    report, rc = adapter.check(PACKAGE, root, base, head, timeout=45)
    assert rc == 2 and report["adapter_status"] == "not_invoked"
    assert "overall timeout" in report["adapter_errors"][0]


@pytest.mark.parametrize("format_args,is_json", [
    (["--format", "json", "--format", "human"], False),
    (["--form=json"], True),
])
def test_effective_parsed_format(commits, capsys, format_args, is_json):
    root, base, _, head = commits
    args = ["--package-root", str(PACKAGE), "--root", str(root),
            "--base", base, "--head", head, *format_args]
    assert adapter.main(args) == 0
    output = capsys.readouterr().out
    if is_json:
        assert json.loads(output)["verdict"] == "PASS"
    else:
        assert output.startswith("Git/docs: PASS (invoked)")
        assert "committed net range" in output
