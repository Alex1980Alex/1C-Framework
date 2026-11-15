"""Load exact Git/docs source files, ignoring package directories and bytecode.

Entry scripts, this helper and delivery.py are the trusted bootstrap. Use -I -B
with trusted Python/stdlib. CI additionally authenticates every runtime source
and initializer against an externally selected manifest before executing it.
"""

from __future__ import annotations

import hashlib
import sys
import types
from pathlib import Path

MODULE_FILES = (
    ("src", "src/__init__.py"),
    ("src.harness", "src/harness/__init__.py"),
    ("src.harness.git_docs_policy", "src/harness/git_docs_policy.py"),
    ("src.harness.git_docs_boundary", "src/harness/git_docs_boundary.py"),
    ("src.harness.git_docs_report", "src/harness/git_docs_report.py"),
    ("src.harness.git_docs_delivery", "src/harness/git_docs_delivery.py"),
)


def load_delivery(root):
    """Compile trusted bootstrap source directly; never consult Python importers."""
    path = Path(root) / "src/harness/git_docs_delivery.py"
    module = types.ModuleType("_git_docs_delivery_bootstrap")
    module.__file__ = str(path)
    raw = path.read_bytes()
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def load_runtime(root, trusted_manifest=None, expected_digest=None):
    root = Path(root)
    delivery = load_delivery(root)
    if trusted_manifest is None:
        snapshot = {path: delivery.no_links(root / path).read_bytes() for _, path in MODULE_FILES}
        snapshot["src/harness/git_docs_rules.json"] = delivery.no_links(
            root / "src/harness/git_docs_rules.json"
        ).read_bytes()
        manifest_sha = None
    else:
        manifest_sha, snapshot = delivery.verified_snapshot(root, trusted_manifest, expected_digest)
    modules = {}
    absent = object()
    previous = {name: sys.modules.get(name, absent) for name, _ in MODULE_FILES}
    try:
        # Only fresh package objects are modified; existing parents retain their attrs.
        for name, path in MODULE_FILES:
            module = types.ModuleType(name)
            module.__file__ = str(root / path)
            package = path.endswith("/__init__.py")
            module.__package__ = name if package else name.rpartition(".")[0]
            if package:
                module.__path__ = []
            modules[name] = module
            sys.modules[name] = module
            parent, _, child = name.rpartition(".")
            if parent:
                setattr(modules[parent], child, module)
        for name, path in MODULE_FILES:
            exec(compile(snapshot[path], str(root / path), "exec"), modules[name].__dict__)
        rules_sha = hashlib.sha256(snapshot["src/harness/git_docs_rules.json"]).hexdigest()
        if modules["src.harness.git_docs_policy"].POLICY_SHA256 != rules_sha:
            raise ValueError("policy bytes changed between verification and source load")
    finally:
        for name, prior in previous.items():
            if prior is absent:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = prior
    return modules, manifest_sha
