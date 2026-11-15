"""Read an explicit Git index or commit range without client state or writes."""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
import stat
import subprocess
import time
from pathlib import Path

from . import git_docs_policy as policy

SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
EXIT_CODES = {"PASS": 0, "FAIL": 1, "UNKNOWN": 2}


class CheckError(ValueError):
    """The selected input could not be checked completely."""


def digest(value):
    return hashlib.sha256(value).hexdigest()


def nul_fields(raw):
    if not isinstance(raw, bytes) or (raw and not raw.endswith(b"\0")):
        raise CheckError("incomplete NUL output")
    return raw[:-1].decode("utf-8").split("\0") if raw else []


def valid_path(path):
    if (not isinstance(path, str) or not path or path.startswith("/")
            or "\\" in path or "\0" in path or re.match(r"^[A-Za-z]:", path)
            or any(p in ("", ".", "..") for p in path.split("/"))):
        raise CheckError("expected literal repository-relative POSIX path")
    return path


def parse_changes(raw):
    fields, result, i = nul_fields(raw), [], 0
    while i < len(fields):
        kind = fields[i]
        i += 1
        if not re.fullmatch(r"[AMDT]|[RC](?:100|[0-9]{1,2})", kind):
            raise CheckError("invalid name-status record")
        count = 2 if kind[0] in "RC" else 1
        if i + count > len(fields):
            raise CheckError("missing changed path")
        paths = [valid_path(p) for p in fields[i:i + count]]
        i += count
        result.append({"kind": kind, "source": paths[0] if count == 2 else None,
                       "path": paths[-1]})
    return result


def parse_index(raw):
    entries = {}
    for field in nul_fields(raw):
        meta, sep, path = field.partition("\t")
        parts = meta.split(" ")
        if (not sep or len(parts) != 3 or parts[0] not in
                {"100644", "100755", "120000", "160000"}
                or not SHA.fullmatch(parts[1]) or parts[2] != "0"
                or set(parts[1]) == {"0"}):
            raise CheckError("invalid, unmerged or intent-to-add index")
        valid_path(path)
        if path in entries:
            raise CheckError("duplicate index path")
        entries[path] = (parts[0], parts[1])
    return entries


class Git:
    """Only plumbing reads; no worktree hashing or user-configured callbacks."""

    def __init__(self, root, budget=35, *, index_path=None):
        if not math.isfinite(budget) or budget <= 0:
            raise CheckError("budget must be finite and positive")
        if not Path(root).is_absolute():
            raise CheckError("absolute root required")
        self.root = Path(root).resolve(strict=True)
        self.deadline = time.monotonic() + budget
        allowed = {"PATH", "SYSTEMROOT", "COMSPEC", "TEMP", "TMP", "PATHEXT"}
        self.env = {k: v for k, v in os.environ.items() if k.upper() in allowed}
        self.env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_TERMINAL_PROMPT="0", GIT_OPTIONAL_LOCKS="0",
                        GIT_NO_LAZY_FETCH="1", GIT_NO_REPLACE_OBJECTS="1",
                        GIT_ATTR_NOSYSTEM="1", GIT_GRAFT_FILE=os.devnull, LC_ALL="C")
        exe = shutil.which("git")
        if not exe:
            raise CheckError("Git unavailable")
        self.command = [exe, "--no-pager", "--no-optional-locks", "--literal-pathspecs",
                        "-C", str(self.root), "-c", "core.fsmonitor=false",
                        "-c", "core.untrackedCache=false", "-c", "core.quotePath=false",
                        "-c", "diff.external=", "-c", "core.pager=cat",
                        "-c", "advice.graftFileDeprecated=false"]
        private, _ = self.locations()
        self.private = Path(private)
        self.explicit_index = index_path is not None
        self.index_path = self.validate_index(index_path) if self.explicit_index else self.private / "index"
        self.env["GIT_INDEX_FILE"] = str(self.index_path)

    def validate_index(self, value):
        candidate = Path(value)
        if not candidate.is_absolute():
            raise CheckError("absolute index_path required")
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(self.private):
            raise CheckError("index_path must be inside the actual private Git directory")
        for part in (candidate, *candidate.parents):
            info = part.lstat()
            if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
                raise CheckError("index_path must not traverse a symlink or reparse point")
        if not stat.S_ISREG(candidate.stat().st_mode):
            raise CheckError("index_path must be a regular file")
        return resolved

    def index_bytes(self):
        # Revalidate on every observation, including after Git has read the index.
        if self.explicit_index:
            if self.validate_index(self.index_path) != self.index_path:
                raise CheckError("index_path identity changed")
        elif self.index_path.is_symlink():
            raise CheckError("default index must not be a symlink")
        return self.index_path.read_bytes() if self.index_path.exists() else None

    def run(self, *args):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise CheckError("Git check budget expired")
        result = subprocess.run(self.command + list(args), env=self.env,
                                capture_output=True, stdin=subprocess.DEVNULL,
                                timeout=min(12, remaining))
        if result.returncode != 0 or result.stderr:
            detail = result.stderr.decode("utf-8", errors="replace")[:800]
            raise CheckError(f"git {args[0]} exit {result.returncode}: {detail}")
        return result.stdout

    def line(self, *args):
        raw = self.run(*args)
        if not raw.endswith(b"\n") or b"\0" in raw or b"\n" in raw[:-1]:
            raise CheckError("invalid single-line Git response")
        return raw[:-1].removesuffix(b"\r").decode("utf-8")

    def locations(self):
        actual = Path(self.line("rev-parse", "--show-toplevel")).resolve(strict=True)
        if actual != self.root:
            raise CheckError("root must be the actual Git working tree root")
        private = Path(self.line("rev-parse", "--absolute-git-dir")).resolve(strict=True)
        common = Path(self.line("rev-parse", "--path-format=absolute", "--git-common-dir"))
        if self.line("rev-parse", "--is-shallow-repository") != "false":
            raise CheckError("shallow history is unsupported")
        return str(private), str(common.resolve(strict=True))

    def commit(self, value):
        if not isinstance(value, str) or not SHA.fullmatch(value):
            raise CheckError("full immutable commit SHA required")
        if self.line("rev-parse", "--verify", value + "^{commit}") != value:
            raise CheckError("input is not the exact commit object")
        return value

    def current_head(self):
        return self.commit(self.line("rev-parse", "--verify", "HEAD^{commit}"))

    def index_state(self):
        before = self.index_bytes()
        raw = self.run("ls-files", "--stage", "-z")
        entries = parse_index(raw)
        after = self.index_bytes()
        if before != after:
            raise CheckError("index changed while reading")
        # Logical entries also cover shared-index content in split-index repositories.
        return digest((b"missing" if before is None else b"present" + before) + raw), entries

    def diff(self, mode, base, head):
        args = ["diff", "--no-ext-diff", "--no-textconv", "--name-status", "-z",
                "--find-renames", "--ignore-submodules=none", "--diff-algorithm=myers"]
        if mode == "index":
            args += ["--cached", "--ita-visible-in-index", head]
        else:
            args += [base, head]
        raw = self.run(*args, "--")
        if mode == "index":
            invisible = ["--ita-invisible-in-index" if a == "--ita-visible-in-index" else a for a in args]
            if self.run(*invisible, "--") != raw:
                raise CheckError("intent-to-add index entries are unsupported")
        return parse_changes(raw)

    def tree_entry(self, mode, path, head, entries):
        if mode == "index":
            entry = entries.get(path)
        else:
            fields = nul_fields(self.run("ls-tree", "-z", head, "--", path))
            if len(fields) != 1:
                raise CheckError("missing or ambiguous changed tree entry")
            meta, sep, found = fields[0].partition("\t")
            parts = meta.split(" ")
            if not sep or found != path or len(parts) != 3 or not SHA.fullmatch(parts[2]):
                raise CheckError("invalid ls-tree entry")
            if parts[0] not in {"100644", "100755", "120000", "160000"}:
                raise CheckError("unsupported changed tree entry mode")
            entry = (parts[0], parts[2])
        if entry is None:
            raise CheckError("changed path missing from selected tree/index")
        if entry[0] != "160000" and self.line("cat-file", "-t", entry[1]) != "blob":
            raise CheckError("non-blob object in selected file entry")
        return entry

    def regular_blob(self, entry):
        if entry[0] not in {"100644", "100755"}:
            return False
        size = self.line("cat-file", "-s", entry[1])
        if not re.fullmatch(r"[0-9]+", size):
            raise CheckError("invalid blob size")
        return int(size) > 0


def empty_report(root, mode, paths, base, head):
    return {"schema_version": 1, "policy_version": policy.POLICY_VERSION,
            "policy_sha256": policy.POLICY_SHA256, "verdict": "UNKNOWN",
            "scope": {"mode": mode, "paths": list(paths),
                      "exclusions": {"patterns": policy.RULES["SKIP_PATTERNS"],
                                     "submodule_worktrees": True}},
            "checked_root": str(root), "git_dir": None, "git_common_dir": None,
            "base": base, "head": head, "index_fingerprint": None,
            "index_path": None,
            "comparison_policy": "net" if mode == "range" else "current_head_delta",
            "range_policy": "net" if mode == "range" else None,
            "snapshot": {"id": None, "stable": False}, "changes": [],
            "findings": [], "errors": [], "author": "not_assessed",
            "adapter_status": "not_used"}


def verify(root, mode, *, base=None, head=None, paths=(), budget=35, index_path=None):
    """Return v1, with incomplete observations taking precedence over violations."""
    report = empty_report(root, mode, paths, base, head)
    try:
        paths = tuple(sorted({valid_path(p) for p in paths}))
        report["scope"]["paths"] = list(paths)
        if mode not in {"index", "range"}:
            raise CheckError("unsupported mode; worktree snapshots are unavailable")
        if mode == "index" and (base is not None or head is not None):
            raise CheckError("index mode does not accept base/head")
        if mode != "index" and index_path is not None:
            raise CheckError("index_path is only valid in index mode")
        git = Git(root, budget, index_path=index_path)
        report["checked_root"] = str(git.root)
        locations = git.locations()
        report["git_dir"], report["git_common_dir"] = locations
        if mode == "index":
            report["index_path"] = str(git.index_path)
            head = git.current_head()
            report["head"] = head
            before, entries = git.index_state()
            report["index_fingerprint"] = before
        else:
            git.commit(base)
            git.commit(head)
            git.run("merge-base", "--is-ancestor", base, head)
            before, entries = None, {}
        changes = git.diff(mode, base, head)

        def selected(path):
            return not paths or any(path == p or path.startswith(p + "/") for p in paths)

        # A rename is atomic: selecting either endpoint includes both in the report/rules.
        changes = [c for c in changes if selected(c["path"])
                   or (c["source"] is not None and selected(c["source"]))]
        report["changes"] = changes
        sources, updated = set(), set()
        for change in changes:
            path, source = change["path"], change["source"]
            sources.add(path)
            if source:
                sources.add(source)
            entry = git.tree_entry(mode, path, head, entries) if change["kind"] != "D" else None
            if (change["kind"] != "D" and
                    (path.lower().startswith(("docs/", ".claude/skills/", ".agents/skills/"))
                     or path.lower() == "claude.md")
                    and git.regular_blob(entry)):
                updated.add(path)
        report["findings"] = policy.evaluate(sources, updated)
        if git.locations() != locations:
            raise CheckError("Git repository locations changed during check")
        if mode == "index":
            if git.current_head() != head or git.index_state()[0] != before:
                raise CheckError("HEAD or index changed during check; retry")
        else:
            git.commit(base)
            git.commit(head)
        if digest(Path(policy.__file__).with_name("git_docs_rules.json").read_bytes()) != policy.POLICY_SHA256:
            raise CheckError("policy changed during check; restart checker")
        identity = {"mode": mode, "root": report["checked_root"], "locations": locations,
                    "base": base, "head": head, "index": before, "paths": paths,
                    "index_path": report["index_path"],
                    "policy": policy.POLICY_SHA256, "changes": changes}
        report["snapshot"] = {"stable": True, "id": digest(json.dumps(
            identity, ensure_ascii=True, sort_keys=True).encode())}
        if time.monotonic() >= git.deadline:
            report["snapshot"]["stable"] = False
            raise CheckError("Git check budget expired")
        report["verdict"] = "FAIL" if report["findings"] else "PASS"
    except (OSError, ValueError, TypeError, subprocess.SubprocessError) as exc:
        report["errors"].append(str(exc))
    return report
