"""Import-smoke tests for the first-party ``src.pdf_framework`` package tree.

Why this exists
---------------
The framework contains *orphan* modules (e.g. the Phase 15 image pipeline, Phase 58
proposition splitter) not yet wired into any caller. Latent ``ImportError`` /
``AttributeError`` bugs there only surface on the *first* call in production —
far too late. This suite turns "first call" into "every CI run".

It is **fully automated**: it auto-discovers every module under the packages listed
in ``_PKG_PREFIXES`` (no per-file maintenance — new modules are covered the moment
they are added), and it is marked ``unit`` (``pytestmark`` below) so the existing
``test-unit`` CI job (``pytest tests/ -m unit``) runs it on every push / PR with no
manual step. To extend coverage to another zone, append one string to
``_PKG_PREFIXES``.

These tests complement ``mypy`` rather than duplicate it. mypy is a static
analyzer: it never executes imports, so it cannot see

* import-time **side effects** or **circular imports** (a module that type-checks
  fine but blows up the moment Python actually imports it), and
* **lazy / factory imports** (``from x import y`` *inside a function body*) when
  CI runs mypy with ``--ignore-missing-imports`` — a real bug we already hit:
  ``create_image_processor`` imported the non-existent ``get_embedding``.

Two layers
----------
1. ``test_module_imports_cleanly`` — actually ``import`` every module (catches
   syntax errors, top-level failures, circular imports, import-time side effects).
2. ``test_firstparty_imports_resolve`` — AST-walk every module and verify that
   every first-party ``from src.* import NAME`` (**including imports nested in
   function bodies**) resolves to a name that truly exists at runtime. This is
   what would have caught the ``get_embedding`` factory bug without having to
   execute the (heavy, API-key-requiring) factory itself.

Robustness: a genuinely missing *third-party* dependency (``qdrant_client``,
``fitz``, ``pdfplumber`` …, not installed in every CI matrix slice) yields ``skip``
rather than a misleading failure. A missing *first-party* (``src.*``) module/name
always fails — that is the bug class we are guarding.
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import pkgutil
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

# First-party package roots to sweep. Append a string here to cover another zone;
# enumeration is automatic from there. ``src.workers`` is intentionally excluded
# (pre-existing ``arq.worker.WorkerSettings`` version-drift import error).
_PKG_PREFIXES: list[str] = ["src.pdf_framework"]


def _all_first_party_modules() -> list[str]:
    """Auto-discover every importable module under each configured package root."""
    found: set[str] = set()
    for prefix in _PKG_PREFIXES:
        try:
            pkg = importlib.import_module(prefix)
        except ImportError:  # pragma: no cover - root package must import
            continue
        # ``onerror`` keeps a sub-package that fails to import (e.g. an uninstalled
        # optional dependency in a reduced CI matrix) from aborting *collection* —
        # the per-module test below still reports it via skip/fail.
        for info in pkgutil.walk_packages(
            pkg.__path__, prefix=f"{prefix}.", onerror=lambda _name: None
        ):
            found.add(info.name)
    return sorted(found)


_MODULES = _all_first_party_modules()


def _is_missing_thirdparty(exc: ModuleNotFoundError) -> bool:
    """True if the missing module is an optional third-party dep (not first-party)."""
    name = exc.name or ""
    return not name.startswith("src")


def _name_resolves(target_mod: object, target: str, name: str) -> bool:
    """True if ``name`` exists in ``target`` — either as an attribute/symbol or as
    an (importable) submodule. ``from pkg import submod`` is valid Python even when
    ``submod`` has not been imported as an attribute yet, so attribute-only checks
    would false-positive on package-style imports."""
    if hasattr(target_mod, name):
        return True
    try:
        return importlib.util.find_spec(f"{target}.{name}") is not None
    except ModuleNotFoundError:
        return False


@pytest.mark.parametrize("module_name", _MODULES)
def test_module_imports_cleanly(module_name: str) -> None:
    """Every first-party module must import at runtime.

    Catches: syntax errors, top-level ``ImportError`` (incl. ``cannot import name``),
    circular imports, and import-time side-effect failures — none of which mypy sees.
    """
    try:
        importlib.import_module(module_name)
    except ModuleNotFoundError as exc:
        if _is_missing_thirdparty(exc):
            pytest.skip(f"optional third-party dependency not installed: {exc.name}")
        raise  # missing first-party module → real bug


def _firstparty_from_imports(module_name: str) -> list[tuple[str, list[str]]]:
    """Return (target_module, [names]) for every first-party ``from src.* import ...``.

    Resolves relative imports against the module's package and includes imports
    nested inside function/class bodies (``ast.walk`` visits the whole tree).
    """
    spec = importlib.util.find_spec(module_name)
    if spec is None or not spec.origin or not spec.origin.endswith(".py"):
        return []
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    # ``spec.parent`` is the correct relative-import anchor: for a package
    # (``__init__.py``) it is the package itself, for a module it is the parent
    # package — unlike ``rpartition``, which would wrongly climb one level for packages.
    package = spec.parent or module_name.rpartition(".")[0]

    results: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        # Build the (possibly relative) target name, then make it absolute.
        rel = "." * node.level + (node.module or "")
        try:
            target = (
                importlib.util.resolve_name(rel, package) if node.level else (node.module or "")
            )
        except (ImportError, ValueError):
            continue
        if not target.startswith("src"):
            continue  # third-party / stdlib → out of scope for this guard
        names = [a.name for a in node.names if a.name != "*"]
        if names:
            results.append((target, names))
    return results


@pytest.mark.parametrize("module_name", _MODULES)
def test_firstparty_imports_resolve(module_name: str) -> None:
    """Every first-party ``from src.* import NAME`` must resolve to a real name.

    Catches lazy/factory imports (nested in function bodies) that the module-import
    sweep never executes — e.g. a factory importing a non-existent symbol.
    """
    for target, names in _firstparty_from_imports(module_name):
        try:
            target_mod = importlib.import_module(target)
        except ModuleNotFoundError as exc:
            if _is_missing_thirdparty(exc):
                pytest.skip(f"optional third-party dependency not installed: {exc.name}")
            raise  # first-party target module missing → real bug
        for name in names:
            assert _name_resolves(target_mod, target, name), (
                f"{module_name}: `from {target} import {name}` — "
                f"name does not exist in {target!r} (stale/typo import)"
            )


def test_discovery_is_non_empty() -> None:
    """Guard the guard: a misconfigured prefix must not silently cover nothing."""
    assert _MODULES, "no first-party modules discovered — check _PKG_PREFIXES"


def test_name_resolver_guard_behavior() -> None:
    """Lock the resolver's contract so the guard itself cannot silently regress.

    Uses the real ``embeddings`` package — the exact site of the historical
    ``get_embedding`` factory bug this suite is meant to catch.
    """
    import src.pdf_framework.embeddings as emb

    target = "src.pdf_framework.embeddings"
    # Stale symbol (the bug we fixed) must NOT resolve → suite would fail loudly.
    assert not _name_resolves(emb, target, "get_embedding")
    # Real exported symbol resolves.
    assert _name_resolves(emb, target, "get_embedding_engine")
    # A real submodule resolves too. Whether it goes through the ``hasattr`` or the
    # ``find_spec`` branch depends on import order (importing ``pkg.sub`` anywhere
    # binds ``sub`` as a package attribute), so we assert only the result, not the path.
    assert _name_resolves(emb, target, "vision")
