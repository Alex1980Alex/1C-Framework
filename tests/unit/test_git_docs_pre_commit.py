"""Real Git commits exercise the index selected by Git, with trusted code elsewhere."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import git_docs_pre_commit as hook
from src.harness import git_docs_boundary as core

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CODE = "src/pdf_framework/agents/check.py"
DOC = "docs/framework documentation/2_КОНТЕКСТ/2.3_RAG_АГЕНТЫ/check.md"


def git(root, *args, hooks=False, env=None):
    clean = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    clean["PYTHON"] = sys.executable
    clean.update(env or {})
    command = ["git", "--no-optional-locks", "-c", "commit.gpgsign=false"]
    if not hooks:
        command += ["-c", "core.hooksPath=" + os.devnull]
    return subprocess.run(command + list(args), cwd=root, env=clean,
                          capture_output=True, timeout=35)


def ok(root, *args, **kwargs):
    result = git(root, *args, **kwargs)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout


def put(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(text.encode("utf-8"))


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "checked repo"
    root.mkdir()
    ok(root, "init", "-q", "--initial-branch=main")
    ok(root, "config", "user.name", "Commit boundary test")
    ok(root, "config", "user.email", "boundary@example.invalid")
    ok(root, "config", "core.autocrlf", "false")
    put(root, CODE, "before\n")
    put(root, DOC, "before docs\n")
    ok(root, "add", "--", CODE, DOC)
    ok(root, "commit", "-qm", "base")
    trusted = tmp_path / "trusted package"
    for path in (
        "src/__init__.py", "src/harness/__init__.py",
        "src/harness/git_docs_boundary.py", "src/harness/git_docs_policy.py",
        "src/harness/git_docs_rules.json", "src/harness/git_docs_report.py",
        "scripts/git_docs_source_loader.py", "src/harness/git_docs_delivery.py",
        "scripts/git_docs_pre_commit.py", "scripts/git_hooks/pre-commit.git-docs.example",
    ):
        target = trusted / ("scripts/git_hooks/pre-commit" if path.endswith(".example") else path)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / path, target)
    (trusted / "scripts/git_hooks/pre-commit").chmod(0o755)
    # Capture exactly the selected logical tree before calling the unchanged hook.
    capture = tmp_path / "capture.py"
    capture.write_text(
        "import os,subprocess\nfrom pathlib import Path\n"
        f"Path({str(tmp_path / 'selected-index')!r}).write_bytes("
        "subprocess.check_output(['git','--no-optional-locks','ls-files','--stage','-z']))\n",
        encoding="utf-8",
    )
    wrapper = tmp_path / "capture hooks/pre-commit"
    wrapper.parent.mkdir()
    wrapper.write_text(
        '#!/bin/sh\n"$PYTHON" ' + '"' + capture.as_posix() + '" || exit 2\n'
        'exec "' + (trusted / "scripts/git_hooks/pre-commit").as_posix() + '"\n',
        encoding="utf-8",
    )
    wrapper.chmod(0o755)
    ok(root, "config", "core.hooksPath", str(wrapper.parent))
    return root


def report_of(result):
    lines = (result.stdout + result.stderr).decode("utf-8", "replace").splitlines()
    reports = [json.loads(line) for line in lines if line.startswith('{"schema_version"')]
    assert len(reports) == 1, lines
    return reports[0]


def assert_commit_matches(root, before, report):
    selected = core.parse_index((root.parent / "selected-index").read_bytes())
    actual = {}
    for record in core.nul_fields(ok(root, "ls-tree", "-rz", "--full-tree", "HEAD")):
        metadata, path = record.split("\t", 1)
        mode, _, oid = metadata.split(" ")
        actual[path] = (mode, oid)
    assert actual == selected, "created commit tree differs from the hook's selected index"
    changes = core.parse_changes(ok(root, "diff", "--name-status", "-z", "--find-renames",
                                   before, "HEAD", "--"))
    assert report["changes"] == changes
    assert report["head"] == before
    assert report["scope"]["mode"] == "index" and report["scope"]["paths"] == []
    assert report["comparison_policy"] == "current_head_delta"
    assert report["snapshot"]["stable"] is True


@pytest.mark.parametrize("mode", ["ordinary", "partial", "all", "only", "amend", "worktree"])
def test_real_commit_blocks_then_passes_selected_tree(repo, mode):
    root = repo
    if mode == "worktree":
        root = repo.parent / "linked worktree"
        ok(repo, "worktree", "add", "-qb", "linked", str(root))
    before = ok(root, "rev-parse", "HEAD").decode().strip()
    put(root, CODE, "staged code\n")
    if mode != "all":
        ok(root, "add", "--", CODE)
    arguments = ["commit", "-qm", "candidate"]
    if mode == "all":
        arguments += ["-a"]
    elif mode == "only":
        arguments += ["--only", "--", CODE]
    elif mode == "amend":
        arguments += ["--amend"]
    failed = git(root, *arguments, hooks=True)
    failed_report = report_of(failed)
    assert failed.returncode != 0 and failed_report["verdict"] == "FAIL"
    assert failed_report["findings"] and not failed_report["errors"]
    assert ok(root, "rev-parse", "HEAD").decode().strip() == before
    put(root, DOC, "staged docs\n")
    if mode != "all":
        ok(root, "add", "--", DOC)
    if mode == "only":
        # Unrelated staged code must not contaminate the path-limited commit.
        put(root, "src/pdf_framework/search/unrelated.py", "unrelated\n")
        ok(root, "add", "--", "src/pdf_framework/search/unrelated.py")
        arguments.append(DOC)
    elif mode == "partial":
        put(root, CODE, "unstaged code\n")
        put(root, DOC, "unstaged docs\n")
    passed = git(root, *arguments, hooks=True)
    report = report_of(passed)
    assert passed.returncode == 0 and report["verdict"] == "PASS", report
    assert_commit_matches(root, before, report)
    assert ok(root, "show", "HEAD:" + CODE) == b"staged code\n"
    assert ok(root, "show", "HEAD:" + DOC) == b"staged docs\n"
    index = Path(report["index_path"])
    if mode == "all":
        assert index.name == "index.lock"
    elif mode == "only":
        assert index.name.startswith("next-index-")
        assert b"unrelated.py" in ok(root, "diff", "--cached", "--name-only")
    if mode == "worktree":
        assert report["git_dir"] != report["git_common_dir"]
        assert index.parent == Path(report["git_dir"])


def test_amend_checks_delta_not_rewritten_parent(repo):
    put(repo, CODE, "old undocumented change\n")
    ok(repo, "add", "--", CODE)
    ok(repo, "commit", "-qm", "old code bypass", "--no-verify")
    before = ok(repo, "rev-parse", "HEAD").decode().strip()
    # No new change: this is explicitly a current-HEAD delta guarantee only.
    result = git(repo, "commit", "--amend", "--no-edit", hooks=True)
    report = report_of(result)
    assert result.returncode == 0 and report["changes"] == []
    assert_commit_matches(repo, before, report)


def test_checker_runs_after_existing_mutating_handler(repo):
    put(repo, CODE, "new code\n")
    put(repo, DOC, "new docs\n")
    ok(repo, "add", "--", CODE)
    wrapper = repo.parent / "capture hooks/pre-commit"
    previous = wrapper.read_text(encoding="utf-8")
    wrapper.write_text(previous.replace('#!/bin/sh\n', '#!/bin/sh\ngit add -- "' + DOC + '" || exit 2\n', 1), encoding="utf-8")
    result = git(repo, "commit", "-qm", "prior handler", hooks=True)
    assert result.returncode == 0 and report_of(result)["verdict"] == "PASS"
    assert ok(repo, "show", "HEAD:" + DOC) == b"new docs\n"


def test_trusted_hook_does_not_load_checked_repo_checker(repo):
    put(repo, "scripts/git_docs_pre_commit.py", "raise SystemExit('candidate executed')\n")
    put(repo, CODE, "undocumented\n")
    ok(repo, "add", "--", CODE)
    result = git(repo, "commit", "-qm", "candidate", hooks=True)
    assert result.returncode != 0 and report_of(result)["verdict"] == "FAIL"
    assert b"candidate executed" not in result.stderr


def test_direct_cli_ignores_inherited_index_but_explicit_index_is_checked(repo):
    private = Path(ok(repo, "rev-parse", "--absolute-git-dir").decode().strip())
    alternate = private / "alternate-index"
    shutil.copyfile(private / "index", alternate)
    put(repo, CODE, "new\n")
    ok(repo, "add", "--", CODE)
    polluted = dict(os.environ, GIT_INDEX_FILE=str(alternate), GIT_DIR=str(private / "wrong"))
    command = [sys.executable, str(ROOT / "scripts/git_docs_verify.py"),
               "--root", str(repo), "--mode", "index"]
    result = subprocess.run(command, env=polluted, capture_output=True, timeout=35)
    assert result.returncode == 1 and json.loads(result.stdout)["verdict"] == "FAIL"
    selected = subprocess.run(command + ["--index-path", str(alternate)],
                              env=polluted, capture_output=True, timeout=35)
    assert selected.returncode == 0 and json.loads(selected.stdout)["index_path"] == str(alternate)
    assert core.verify(repo, "index", index_path=alternate)["changes"] == []


@pytest.mark.parametrize("kind", ["relative", "outside", "directory", "missing", "range"])
def test_explicit_invalid_index_is_unknown(repo, kind):
    selected = {"relative": ".git/index", "outside": repo / CODE,
                "directory": repo / ".git", "missing": repo / ".git/missing",
                "range": repo / ".git/index"}[kind]
    result = core.verify(repo, "range" if kind == "range" else "index", index_path=selected)
    assert result["verdict"] == "UNKNOWN" and result["errors"]


def test_explicit_symlink_index_is_unknown(repo):
    link = repo / ".git/index-link"
    try:
        link.symlink_to(repo / ".git/index")
    except OSError:
        pytest.skip("symlink privilege unavailable")
    report = core.verify(repo, "index", index_path=link)
    assert report["verdict"] == "UNKNOWN" and report["errors"]


def test_hook_rejects_mismatched_pass_and_state_mutation(repo, monkeypatch):
    original = hook.verify

    def wrong_report(*args, **kwargs):
        report = original(*args, **kwargs)
        report["head"] = "0" * 40
        return report

    monkeypatch.setattr(hook, "verify", wrong_report)
    report, code = hook.check_commit(repo)
    assert code == 2 and any("head" in error for error in report["errors"])

    def mutate_after_pass(*args, **kwargs):
        report = original(*args, **kwargs)
        put(repo, CODE, "changed while checking\n")
        ok(repo, "add", "--", CODE)
        return report

    monkeypatch.setattr(hook, "verify", mutate_after_pass)
    report, code = hook.check_commit(repo)
    assert code == 2 and any("state changed" in error for error in report["errors"])


def test_no_verify_bypass_is_detected_by_range_checker(repo):
    base = ok(repo, "rev-parse", "HEAD").decode().strip()
    put(repo, CODE, "bypassed code\n")
    ok(repo, "add", "--", CODE)
    ok(repo, "commit", "--no-verify", "-qm", "bypass", hooks=True)
    head = ok(repo, "rev-parse", "HEAD").decode().strip()
    report = core.verify(repo, "range", base=base, head=head)
    assert report["verdict"] == "FAIL" and report["range_policy"] == "net"
