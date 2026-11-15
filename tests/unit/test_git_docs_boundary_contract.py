import hashlib
import os
import pathlib
import shutil
import subprocess

import pytest

from src.harness.git_docs_boundary import CheckError, verify

# ── policy constants ──────────────────────────────────────────────────────────
pytestmark = pytest.mark.unit

AGENTS_SRC = "src/pdf_framework/agents"
AGENTS_DOC = "docs/framework documentation/2_КОНТЕКСТ/2.3_RAG_АГЕНТЫ"
SEARCH_SRC = "src/pdf_framework/search"
SEARCH_DOC = "docs/framework documentation/2_КОНТЕКСТ/2.2_ПОИСК"


# ── helpers ───────────────────────────────────────────────────────────────────
def git(cwd, *args):
    r = subprocess.run(["git", "--no-optional-locks", "-c", "core.quotepath=false", "-c", "core.hooksPath=" + os.devnull, "-c", "commit.gpgsign=false", *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8", timeout=15)
    assert r.returncode == 0, f"git {' '.join(args)} rc={r.returncode} stderr={r.stderr}"
    return r.stdout


def write(path: pathlib.Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def init_repo(root: pathlib.Path) -> None:
    git(root, "init", "--initial-branch=main")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@local")
    git(root, "config", "core.autocrlf", "false")
    write(root / "README.md", "# repo\n")
    git(root, "add", "README.md")
    git(root, "commit", "-m", "init")


def stage(root: pathlib.Path, *files: str) -> None:
    git(root, "add", *files)


def commit(root: pathlib.Path, msg: str = "change") -> None:
    git(root, "commit", "-m", msg)


def fp(root: pathlib.Path) -> str:
    h = hashlib.sha256()
    for sub in ("HEAD", "config", "index"):
        p = root / ".git" / sub
        if p.exists():
            h.update(p.read_bytes())
    for line in git(root, "ls-files", "-z").rstrip("\0").split("\0"):
        fp_ = root / line
        if fp_.is_file():
            h.update(fp_.read_bytes())
    return h.hexdigest()


@pytest.fixture
def repo(tmp_path: pathlib.Path) -> pathlib.Path:
    root = tmp_path / "repo"
    root.mkdir()
    init_repo(root)
    return root


# ── basic structure ───────────────────────────────────────────────────────────
def test_verify_returns_expected_keys(repo):
    result = verify(repo, "index")
    for k in ("verdict", "findings", "errors", "scope", "index_fingerprint",
              "snapshot", "git_dir", "git_common_dir"):
        assert k in result, k
    assert result["snapshot"]["stable"] is True


def test_verdict_values(repo):
    assert verify(repo, "index")["verdict"] == "PASS"


# ── staged code without docs → FAIL ──────────────────────────────────────────
def test_staged_code_no_docs_fail(repo):
    write(repo / AGENTS_SRC / "model.py", "class M: pass\n")
    stage(repo, AGENTS_SRC + "/model.py")
    r = verify(repo, "index")
    assert r["verdict"] == "FAIL"
    assert any(AGENTS_DOC.lower() == f["required"].rstrip("/") for f in r["findings"])


def test_staged_search_code_no_docs_fail(repo):
    write(repo / SEARCH_SRC / "engine.py", "x=1\n")
    stage(repo, SEARCH_SRC + "/engine.py")
    r = verify(repo, "index")
    assert r["verdict"] == "FAIL"
    assert any(SEARCH_DOC.lower() == f["required"].rstrip("/") for f in r["findings"])


# ── doc on disk but not staged → still FAIL; add → PASS ──────────────────────
def test_doc_disk_only_fail_then_add_pass(repo):
    write(repo / AGENTS_SRC / "model.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/model.py")
    doc = repo / AGENTS_DOC / "guide.md"
    write(doc, "# Guide\n")
    # doc exists on disk but NOT staged
    r = verify(repo, "index")
    assert r["verdict"] == "FAIL"
    # now stage the doc
    stage(repo, str(doc.relative_to(repo)))
    r2 = verify(repo, "index")
    assert r2["verdict"] == "PASS"


# ── staged doc survives worktree deletion → PASS ─────────────────────────────
def test_staged_doc_survives_deletion(repo):
    src_f = repo / AGENTS_SRC / "agent.py"
    doc_f = repo / AGENTS_DOC / "agents.md"
    write(src_f, "x=1\n")
    write(doc_f, "# Agents\n")
    stage(repo, AGENTS_SRC + "/agent.py", AGENTS_DOC + "/agents.md")
    # delete worktree copy of doc (staged blob remains)
    doc_f.unlink()
    r = verify(repo, "index")
    assert r["verdict"] == "PASS"


# ── range mode ────────────────────────────────────────────────────────────────
def test_range_code_then_doc_net_pass(repo):
    write(repo / AGENTS_SRC / "a.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/a.py")
    commit(repo, "code only")

    write(repo / AGENTS_DOC / "doc.md", "# Doc\n")
    stage(repo, AGENTS_DOC + "/doc.md")
    commit(repo, "add doc")
    doc_sha = git(repo, "rev-parse", "HEAD").strip()

    base = git(repo, "rev-parse", "HEAD~2").strip()
    r = verify(repo, "range", base=base, head=doc_sha)
    assert r["verdict"] == "PASS"


def test_range_code_only_fail(repo):
    write(repo / SEARCH_SRC / "s.py", "y=2\n")
    stage(repo, SEARCH_SRC + "/s.py")
    commit(repo, "search code")
    head = git(repo, "rev-parse", "HEAD").strip()
    base = git(repo, "rev-parse", "HEAD~1").strip()
    r = verify(repo, "range", base=base, head=head)
    assert r["verdict"] == "FAIL"


# ── deletion / empty / symlink doc does not count ────────────────────────────
def test_deleted_doc_not_counted(repo):
    write(repo / AGENTS_DOC / "gone.md", "# x\n")
    stage(repo, AGENTS_DOC + "/gone.md")
    commit(repo, "old doc")
    git(repo, "rm", "--", AGENTS_DOC + "/gone.md")
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/m.py")
    r = verify(repo, "index")
    assert r["verdict"] == "FAIL"


def test_empty_doc_not_counted(repo):
    write(repo / AGENTS_DOC / "empty.md", "")
    stage(repo, AGENTS_DOC + "/empty.md")
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/m.py")
    r = verify(repo, "index")
    assert r["verdict"] == "FAIL"


def test_symlink_doc_not_counted(repo):
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/m.py")
    oid = git(repo, "rev-parse", "HEAD:README.md").strip()
    git(repo, "update-index", "--add", "--cacheinfo", f"120000,{oid},{AGENTS_DOC}/link.md")
    r = verify(repo, "index")
    assert r["verdict"] == "FAIL"


# ── rename agents→search requires BOTH domains ───────────────────────────────
def test_rename_requires_both_domains(repo):
    write(repo / AGENTS_SRC / "a.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/a.py")
    commit(repo, "original")
    (repo / SEARCH_SRC).mkdir(parents=True)
    git(repo, "mv", AGENTS_SRC + "/a.py", SEARCH_SRC + "/a.py")
    write(repo / AGENTS_DOC / "ok.md", "# ok\n")
    stage(repo, AGENTS_DOC + "/ok.md")
    # missing search doc
    r = verify(repo, "index")
    assert r["verdict"] == "FAIL"
    assert any(SEARCH_DOC.lower() == f["required"].rstrip("/") for f in r["findings"])
    assert any(c["kind"].startswith("R") and c["source"] == AGENTS_SRC + "/a.py"
               and c["path"] == SEARCH_SRC + "/a.py" for c in r["changes"])
    git(repo, "rm", "--cached", "--", AGENTS_DOC + "/ok.md")
    # add search doc
    write(repo / SEARCH_DOC / "ok.md", "# ok\n")
    stage(repo, SEARCH_DOC + "/ok.md")
    source_missing = verify(repo, "index")
    assert source_missing["verdict"] == "FAIL"
    assert any(f["required"].rstrip("/") == AGENTS_DOC.lower() for f in source_missing["findings"])
    stage(repo, AGENTS_DOC + "/ok.md")
    r2 = verify(repo, "index")
    assert r2["verdict"] == "PASS"


# ── special filenames ─────────────────────────────────────────────────────────
def test_special_filename_spaces(repo):
    f = repo / AGENTS_DOC / "my guide v2.md"
    write(f, "# hi\n")
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/m.py", AGENTS_DOC + "/my guide v2.md")
    r = verify(repo, "index")
    assert r["verdict"] == "PASS"


def test_special_filename_unicode(repo):
    f = repo / AGENTS_DOC / "док_指南.md"
    write(f, "# hi\n")
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/m.py", AGENTS_DOC + "/док_指南.md")
    r = verify(repo, "index")
    assert r["verdict"] == "PASS"


@pytest.mark.parametrize("name", ["tab\there.md", "nl\nname.md", ":(glob)*.md"])
def test_virtual_special_filename(repo, name):
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/m.py")
    oid = git(repo, "rev-parse", "HEAD:README.md").strip()
    path = AGENTS_DOC + "/" + name
    git(repo, "-c", "core.protectNTFS=false", "update-index", "--add", "--cacheinfo", f"100644,{oid},{path}")
    r = verify(repo, "index")
    assert r["verdict"] == "PASS", r
    assert path in {c["path"] for c in r["changes"]}


# ── UNKNOWN conditions ────────────────────────────────────────────────────────
def test_wrong_sha_unknown(repo):
    fake = "0" * 40
    r = verify(repo, "range", base=fake, head=fake)
    assert r["verdict"] == "UNKNOWN"


def test_existing_nonancestor_base_is_unknown(repo):
    initial = git(repo, "rev-parse", "HEAD").strip()
    write(repo / "tests/main.py", "main\n")
    stage(repo, "tests/main.py")
    commit(repo, "main advance")
    base = git(repo, "rev-parse", "HEAD").strip()
    git(repo, "checkout", "-b", "side", initial)
    write(repo / "tests/side.py", "side\n")
    stage(repo, "tests/side.py")
    commit(repo, "side advance")
    head = git(repo, "rev-parse", "HEAD").strip()
    r = verify(repo, "range", base=base, head=head)
    assert r["verdict"] == "UNKNOWN" and any("git merge-base exit 1" in e for e in r["errors"])


def test_shallow_unknown(repo):
    r = subprocess.run(["git", "clone", "--depth=1", "--no-local", str(repo), str(repo.parent / "shallow")],
                       capture_output=True, text=True)
    assert r.returncode == 0
    write(repo.parent / "shallow" / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo.parent / "shallow", AGENTS_SRC + "/m.py")
    head = git(repo.parent / "shallow", "rev-parse", "HEAD").strip()
    base = git(repo.parent / "shallow", "rev-parse", "HEAD").strip()
    res = verify(repo.parent / "shallow", "range", base=base, head=head)
    assert res["verdict"] == "UNKNOWN"


def test_unmerged_index_unknown(repo):
    # create a merge conflict
    git(repo, "checkout", "-b", "feature")
    write(repo / AGENTS_SRC / "conflict.py", "from branch\n")
    stage(repo, AGENTS_SRC + "/conflict.py")
    commit(repo, "feature")
    git(repo, "checkout", "main")
    write(repo / AGENTS_SRC / "conflict.py", "from main\n")
    stage(repo, AGENTS_SRC + "/conflict.py")
    commit(repo, "main change")
    r = subprocess.run(["git", "merge", "feature"], cwd=repo, capture_output=True, text=True)
    assert r.returncode != 0
    assert git(repo, "ls-files", "--unmerged").strip()
    assert verify(repo, "index")["verdict"] == "UNKNOWN"


def test_unknown_mode(repo):
    r = verify(repo, "bogus_mode")
    assert r["verdict"] == "UNKNOWN"


# ── selected paths ────────────────────────────────────────────────────────────
def test_selected_paths_omit_docs_fail(repo):
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    write(repo / AGENTS_DOC / "d.md", "# doc\n")
    stage(repo, AGENTS_SRC + "/m.py", AGENTS_DOC + "/d.md")
    # restrict to source only → doc outside scope → FAIL
    r = verify(repo, "index", paths=(AGENTS_SRC,))
    assert r["verdict"] == "FAIL"


# ── linked worktree ──────────────────────────────────────────────────────────
def test_linked_worktree_git_dirs(repo):
    wt = repo.parent / "wt"
    git(repo, "worktree", "add", str(wt), "-b", "wt-branch")
    write(wt / AGENTS_SRC / "m.py", "x=1\n")
    stage(wt, AGENTS_SRC + "/m.py")
    r = verify(wt, "index")
    assert r["git_dir"] != r["git_common_dir"]
    assert r["git_common_dir"].endswith(".git")
    assert r["verdict"] == "FAIL"


# ── no mutation ──────────────────────────────────────────────────────────────
def test_no_mutation(repo):
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/m.py")
    before = fp(repo)
    verify(repo, "index")
    after = fp(repo)
    assert before == after


# ── env pollution ────────────────────────────────────────────────────────────
def test_env_pollution_ignored(repo, monkeypatch):
    write(repo / AGENTS_SRC / "m.py", "x=1\n")
    stage(repo, AGENTS_SRC + "/m.py")
    fake_dir = str(repo.parent / "bogus_git")
    monkeypatch.setenv("GIT_DIR", fake_dir)
    monkeypatch.setenv("GIT_WORK_TREE", str(repo.parent / "nope"))
    monkeypatch.setenv("GIT_INDEX_FILE", str(repo.parent / "fake_index"))
    r = verify(repo, "index")
    assert r["verdict"] == "FAIL"
    # must still operate on the real repo
    assert "repo" in r["git_common_dir"] or "repo" in str(r.get("git_dir", ""))


# ── parse_changes NUL → CheckError ───────────────────────────────────────────
def test_parse_changes_nul_raises(repo):
    from src.harness.git_docs_boundary import parse_changes
    with pytest.raises(CheckError):
        parse_changes(b"M\0incomplete")


# ── excluded paths ───────────────────────────────────────────────────────────
def test_excluded_paths_not_flagged(repo):
    write(repo / "tests" / "x.py", "pass\n")
    write(repo / "scripts" / "y.py", "pass\n")
    write(repo / "docs" / "z.py", "pass\n")
    stage(repo, "tests/x.py", "scripts/y.py", "docs/z.py")
    r = verify(repo, "index")
    assert r["verdict"] == "PASS"


# ── budget respected ─────────────────────────────────────────────────────────
def test_budget_key_present(repo):
    r = verify(repo, "index", budget=10)
    assert "errors" in r
