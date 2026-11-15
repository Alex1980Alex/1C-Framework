"""Independent callback controls, fault injection, races and rule parity."""

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.harness import git_docs_boundary as core
from src.harness import git_docs_policy as policy

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
CODE = "src/pdf_framework/agents/check.py"
DOC = "docs/framework documentation/2_КОНТЕКСТ/2.3_RAG_АГЕНТЫ/check.md"


def git(root, *args, input=None):
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    result = subprocess.run(
        [
            "git",
            "--no-optional-locks",
            "-C",
            str(root),
            "-c",
            "core.hooksPath=" + os.devnull,
            *args,
        ],
        input=input,
        capture_output=True,
        env=env,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


def put(root, path, text):
    target = root / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.name", "Boundary acceptance")
    git(root, "config", "user.email", "boundary@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    put(root, CODE, "before\n")
    git(root, "add", "--", CODE)
    git(root, "commit", "-qm", "base")
    base = git(root, "rev-parse", "HEAD").decode().strip()
    put(root, CODE, "after\n")
    git(root, "add", "--", CODE)
    return root, base


def callback(tmp_path, kind):
    marker, script = tmp_path / (kind + ".called"), tmp_path / (kind + ".py")
    output = (
        "sys.stdout.buffer.write(b'token\\0')"
        if kind == "fsmonitor"
        else "sys.stdout.buffer.write(sys.stdin.buffer.read())"
    )
    script.write_text(
        "import sys\nfrom pathlib import Path\n"
        f"Path({str(marker)!r}).write_text('called')\n{output}\n",
        encoding="utf-8",
    )
    return f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}"', marker


@pytest.mark.parametrize("mode", ["index", "range"])
@pytest.mark.parametrize("kind", ["external", "textconv", "filter", "fsmonitor"])
def test_callbacks_work_but_checker_never_invokes_them(repo, tmp_path, mode, kind):
    root, base = repo
    command, marker = callback(tmp_path, kind)
    if kind == "external":
        git(root, "config", "diff.external", command)
        git(root, "diff", "--cached")
    elif kind == "textconv":
        put(root, ".gitattributes", "*.py diff=probe\n")
        git(root, "config", "diff.probe.textconv", command)
        git(root, "diff", "--cached", "--textconv")
    elif kind == "filter":
        put(root, ".gitattributes", "*.py filter=probe\n")
        git(root, "config", "filter.probe.clean", command)
        git(root, "hash-object", "--path=" + CODE, CODE)
    else:
        git(root, "config", "core.fsmonitor", command)
        git(root, "status", "--porcelain")
    assert marker.read_text() == "called", "positive callback control failed"
    if mode == "range":
        git(root, "commit", "-qm", "code")
    marker.unlink()
    before = {p: p.read_bytes() for p in (root / ".git/index", root / ".git/config", root / CODE)}
    head = git(root, "rev-parse", "HEAD").decode().strip()
    assert not marker.exists()
    report = core.verify(root, mode, **({"base": base, "head": head} if mode == "range" else {}))
    assert report["verdict"] == "FAIL" and report["findings"] and not report["errors"], report
    assert not marker.exists()
    assert all(p.read_bytes() == value for p, value in before.items())
    assert git(root, "rev-parse", "HEAD").decode().strip() == head


def test_git_env_cannot_select_another_index_or_root(repo, monkeypatch, tmp_path):
    for key, value in {
        "GIT_DIR": str(tmp_path / "wrong"),
        "GIT_WORK_TREE": str(tmp_path),
        "GIT_INDEX_FILE": str(tmp_path / "clean-index"),
        "GIT_CONFIG_COUNT": "1",
        "GIT_CONFIG_KEY_0": "core.worktree",
        "GIT_CONFIG_VALUE_0": str(tmp_path),
        "GIT_CONFIG_PARAMETERS": "malformed",
        "GIT_EXTERNAL_DIFF": "missing",
    }.items():
        monkeypatch.setenv(key, value)
    report = core.verify(repo[0], "index")
    assert report["verdict"] == "FAIL" and report["checked_root"] == str(repo[0].resolve())
    assert not (tmp_path / "clean-index").exists()


def test_index_race_preserves_findings_but_is_unknown(repo, monkeypatch):
    root, _ = repo
    original = core.Git.diff

    def race(self, *args):
        changes = original(self, *args)
        put(root, "tests/late.txt", "late\n")
        git(root, "add", "--", "tests/late.txt")
        return changes

    monkeypatch.setattr(core.Git, "diff", race)
    report = core.verify(root, "index")
    assert report["verdict"] == "UNKNOWN" and report["findings"]
    assert "changed" in report["errors"][0] and report["snapshot"]["stable"] is False


@pytest.mark.parametrize("fault", ["stderr", "failure", "timeout", "nul"])
def test_git_faults_are_not_clean(repo, monkeypatch, fault):
    original = core.subprocess.run

    def broken(command, **kwargs):
        if "--name-status" in command:
            if fault == "timeout":
                raise subprocess.TimeoutExpired(command, 12)
            rc, out, err = {
                "stderr": (0, b"", b"incomplete scan"),
                "failure": (128, b"", b"bad object"),
                "nul": (0, b"M\0truncated", b""),
            }[fault]
            return subprocess.CompletedProcess(command, rc, out, err)
        return original(command, **kwargs)

    monkeypatch.setattr(core.subprocess, "run", broken)
    report = core.verify(repo[0], "index")
    assert report["verdict"] == "UNKNOWN" and report["errors"]


@pytest.mark.parametrize("budget", [0, -1, float("nan"), float("inf"), 0.000001])
def test_budget_never_becomes_pass(repo, budget):
    report = core.verify(repo[0], "index", budget=budget)
    assert report["verdict"] == "UNKNOWN" and report["errors"]


def test_exact_source_rule_snapshot_and_independent_imports():
    import hashlib

    raw = (ROOT / "tests/fixtures/git_docs_rules_baseline.json").read_bytes()
    assert (
        hashlib.sha256(raw).hexdigest()
        == "74364254d394138d3838894d04e6245e118a84436ace2e47c66404db53a0888a"
    )
    baseline = json.loads(raw.decode("utf-8"))
    assert len(baseline["CODE_TO_DOMAIN"]) == 34
    assert len(baseline["SKIP_PATTERNS"]) == 88
    assert policy.RULES["DOCS_BASE"] == baseline["DOCS_BASE"]
    assert policy.RULES["SKIP_PATTERNS"] == baseline["SKIP_PATTERNS"]
    assert policy.RULES["CODE_TO_DOMAIN"][1:] == baseline["CODE_TO_DOMAIN"]
    assert policy.RULES["CODE_TO_DOMAIN"][0] == [
        "src/harness/",
        "7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ",
        "harness-guide",
    ]
    for file in ("git_docs_boundary.py", "git_docs_policy.py"):
        tree = ast.parse((ROOT / "src/harness" / file).read_text(encoding="utf-8"))
        imports = [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any("codex" in n or "ownership" in n or "stop" in n for n in imports)


def test_new_boundary_can_check_its_own_documented_delivery():
    source = "src/harness/git_docs_boundary.py"
    chapter = "docs/framework documentation/7_ПРОВЕРКА/7.2_АДМИНИСТРИРОВАНИЕ/09.7_Система_хуков.md"
    assert policy.evaluate([source], [])
    assert policy.evaluate([source], [chapter]) == []


@pytest.mark.parametrize("target", ["code", "document"])
@pytest.mark.parametrize("object_kind", ["commit", "missing", "tree"])
def test_index_object_type_and_existence_are_checked(repo, target, object_kind):
    root, base = repo
    put(root, DOC, "real documentation\n")
    git(root, "add", "--", DOC)
    oid = {
        "commit": base,
        "missing": "1" * 40,
        "tree": git(root, "rev-parse", "HEAD^{tree}").decode().strip(),
    }[object_kind]
    git(
        root,
        "update-index",
        "--add",
        "--cacheinfo",
        f"100644,{oid},{DOC if target == 'document' else CODE}",
    )
    report = core.verify(root, "index")
    assert report["verdict"] == "UNKNOWN" and report["errors"], report


@pytest.mark.parametrize(
    "case,code",
    [("clean", 0), ("violation", 1), ("bad-mode", 2), ("missing-args", 2), ("relative-root", 2)],
)
def test_actual_cli_v1_and_exit_code(repo, case, code):
    root, _ = repo
    if case == "clean":
        put(root, DOC, "documentation\n")
        git(root, "add", "--", DOC)
    argv = ["--root", str(root), "--mode", "index"]
    if case == "bad-mode":
        argv[-1] = "worktree"
    elif case == "missing-args":
        argv = []
    elif case == "relative-root":
        argv[1] = "relative"
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts/git_docs_verify.py"), *argv],
        capture_output=True,
        timeout=40,
    )
    assert result.returncode == code and not result.stderr, result.stderr
    report = json.loads(result.stdout)
    assert report["schema_version"] == 1 and report["author"] == "not_assessed"
    assert report["verdict"] == {0: "PASS", 1: "FAIL", 2: "UNKNOWN"}[code]


def test_cli_missing_policy_is_unknown_and_no_bytecode(repo, tmp_path):
    import shutil

    package = tmp_path / "checker"
    (package / "src").mkdir(parents=True)
    (package / "src/__init__.py").write_text("", encoding="utf-8")
    for name in (
        "scripts/git_docs_verify.py",
        "src/harness/__init__.py",
        "src/harness/git_docs_boundary.py",
        "src/harness/git_docs_policy.py",
    ):
        dest = package / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, dest)
    result = subprocess.run(
        [
            sys.executable,
            str(package / "scripts/git_docs_verify.py"),
            "--root",
            str(repo[0]),
            "--mode",
            "index",
        ],
        capture_output=True,
        timeout=40,
        cwd=package,
    )
    report = json.loads(result.stdout)
    assert result.returncode == 2 and report["verdict"] == "UNKNOWN" and report["errors"]
    assert not list(package.rglob("*.pyc"))


def _pager_control(root):
    import threading
    import time

    from winpty import PtyProcess

    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    process = PtyProcess.spawn(
        ["git", "--no-optional-locks", "-C", str(root), "--paginate", "diff", "--cached"],
        cwd=str(root),
        env=env,
        backend="0",
    )

    def drain():
        try:
            while True:
                process.read()
        except (EOFError, OSError):
            pass

    reader = threading.Thread(target=drain, daemon=True)
    reader.start()
    deadline = time.monotonic() + 10
    try:
        while process.isalive() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not process.isalive(), "owned pager control exceeded deadline"
    finally:
        process.close(force=process.isalive())
        reader.join(2)


def test_real_pager_control_and_no_pager_checker(repo, tmp_path):
    if os.name != "nt":
        pytest.skip("Windows ConPTY control")
    root, _ = repo
    command, marker = callback(tmp_path, "pager")
    git(root, "config", "core.pager", command)
    # Isolate ConPTY std-handle changes from the rest of the pytest process.
    control = (
        "import runpy,pathlib; m=runpy.run_path("
        + repr(__file__)
        + "); m['_pager_control'](pathlib.Path("
        + repr(str(root))
        + "))"
    )
    result = subprocess.run(
        [sys.executable, "-c", control], input=b"", capture_output=True, timeout=20
    )
    assert result.returncode == 0, result.stderr
    assert marker.read_text() == "called", "pager was not actually activated"
    marker.unlink()
    assert core.verify(root, "index")["verdict"] == "FAIL"
    assert not marker.exists()


def test_grafted_ancestry_cannot_turn_nonancestor_into_pass(repo):
    root, base = repo
    git(root, "checkout", "--orphan", "unrelated")
    git(root, "commit", "-qm", "unrelated root")
    head = git(root, "rev-parse", "HEAD").decode().strip()
    git(root, "config", "advice.graftFileDeprecated", "false")
    put(root, ".git/info/grafts", f"{head} {base}\n")
    # Positive control: without checker isolation this repo spoofs the ancestry.
    git(root, "merge-base", "--is-ancestor", base, head)
    put(root, DOC, "documentation\n")
    git(root, "add", "--", DOC)
    git(root, "commit", "-qm", "documented descendant")
    head = git(root, "rev-parse", "HEAD").decode().strip()
    report = core.verify(root, "range", base=base, head=head)
    assert report["verdict"] == "UNKNOWN" and any(
        "git merge-base exit 1" in e for e in report["errors"]
    ), report
