"""Archive and installed-file controls using separately trusted manifest bytes."""
import hashlib
import importlib.util
import json
import os
import py_compile
import runpy
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from src.harness import git_docs_delivery as delivery

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "source"
    for name in delivery.PACKAGE_FILES:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(("sample " + name).encode())
    (root / "private.env").write_text("must stay outside package")
    return root


def make_package(source, tmp_path, name="package.zip"):
    output = tmp_path / name
    result = delivery.build(source, output, "1" * 40)
    return output, Path(result["trusted_manifest_candidate"]), result["manifest_sha256"]


def rewrite_archive(path, alter):
    with zipfile.ZipFile(path) as archive:
        records = [(info, archive.read(info)) for info in archive.infolist()]
    with zipfile.ZipFile(path, "w") as archive:
        for info, data in records:
            info, data = alter(info, data)
            archive.writestr(info, data)


def test_deterministic_allowlisted_archive_and_manifest(source, tmp_path):
    first, manifest, expected = make_package(source, tmp_path)
    second, second_manifest, second_expected = make_package(source, tmp_path, "other.zip")
    assert first.read_bytes() == second.read_bytes()
    assert manifest.read_bytes() == second_manifest.read_bytes()
    assert expected == second_expected
    assert delivery.verify_archive(first, manifest, expected)["verdict"] == "PASS"
    assert delivery.verify_installed(source, manifest, expected) == expected
    with zipfile.ZipFile(first) as archive:
        assert archive.namelist() == sorted(delivery.PACKAGE_FILES)
        assert "private.env" not in archive.namelist()


def test_archive_includes_real_guide_and_authenticates_its_bytes(tmp_path):
    name = "docs/git-docs-boundary.md"
    data = (ROOT / name).read_bytes()
    archive, manifest, expected = make_package(ROOT, tmp_path)
    with zipfile.ZipFile(archive) as stream:
        assert stream.read(name) == data
    record = json.loads(manifest.read_bytes())["files"][name]
    assert record == {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    rewrite_archive(archive, lambda info, content:
                    (info, b"!" * len(content) if info.filename == name else content))
    with pytest.raises(ValueError, match="archive file digest mismatch: " + name):
        delivery.verify_archive(archive, manifest, expected)


@pytest.mark.parametrize("value", ["../x", "/x", "a//b", "a/./b", "a/../b",
                                  "a\\b", "C:/x", "x:stream", "x\0y", ""])
def test_cross_platform_archive_path_rejection(value):
    with pytest.raises(ValueError, match="unsafe package path"):
        delivery.safe_path(value)


def test_output_must_be_absolute_external_and_new(source, tmp_path):
    with pytest.raises(ValueError, match="absolute"):
        delivery.build(source, Path("relative.zip"), "1" * 40)
    with pytest.raises(ValueError, match="outside source"):
        delivery.build(source, source / "package.zip", "1" * 40)
    make_package(source, tmp_path)
    with pytest.raises(ValueError, match="already exists"):
        make_package(source, tmp_path)


@pytest.mark.parametrize("kind", ["file", "ancestor"])
def test_source_symlink_or_reparse_is_refused(source, tmp_path, kind):
    file = source / "src/harness/git_docs_policy.py"
    target = tmp_path / "external.py"
    target.write_text("secret")
    try:
        if kind == "file":
            file.unlink()
            file.symlink_to(target)
            candidate = source
        else:
            candidate = tmp_path / "source-link"
            candidate.symlink_to(source, target_is_directory=True)
    except OSError as exc:
        pytest.skip("symlink privilege unavailable: " + str(exc))
    with pytest.raises(ValueError, match="symlink/reparse"):
        delivery.build(candidate, tmp_path / "refused.zip", "1" * 40)


def test_manifest_pin_rejects_changed_candidate_and_self_manifest(source, tmp_path):
    archive, manifest, expected = make_package(source, tmp_path)
    rewrite_archive(archive, lambda info, data: (info, b"x" * len(data)))
    with pytest.raises(ValueError, match="digest mismatch"):
        delivery.verify_archive(archive, manifest, expected)
    changed = json.loads(manifest.read_text())
    for record in changed["files"].values():
        record["sha256"] = hashlib.sha256(b"x" * record["size"]).hexdigest()
    manifest.write_text(json.dumps(changed))
    with pytest.raises(ValueError, match="manifest digest mismatch"):
        delivery.verify_archive(archive, manifest, expected)


@pytest.mark.parametrize("attack", ["traversal", "symlink", "extra", "duplicate"])
def test_hostile_archive_structure_is_refused(source, tmp_path, attack):
    archive, manifest, expected = make_package(source, tmp_path)
    def alter(info, data):
        if info.filename == delivery.PACKAGE_FILES[0]:
            if attack == "traversal":
                info.filename = "../escaped.py"
            if attack == "symlink":
                info.external_attr = 0o120777 << 16
        return info, data
    rewrite_archive(archive, alter)
    if attack in {"extra", "duplicate"}:
        with zipfile.ZipFile(archive, "a") as stream:
            stream.writestr("extra.py" if attack == "extra" else delivery.PACKAGE_FILES[0], b"bad")
    with pytest.raises(ValueError):
        delivery.verify_archive(archive, manifest, expected)


def test_installed_trusted_checker_tamper_is_detected(source, tmp_path):
    _, manifest, expected = make_package(source, tmp_path)
    path = source / "src/harness/git_docs_policy.py"
    original = path.read_bytes()
    path.write_bytes(b"!" * len(original))
    with pytest.raises(ValueError, match="installed delivery digest mismatch"):
        delivery.verify_installed(source, manifest, expected)


def test_missing_component_does_not_silently_shrink_package(source, tmp_path):
    (source / "src/harness/git_docs_report.py").unlink()
    with pytest.raises(ValueError, match="missing regular delivery file"):
        make_package(source, tmp_path)


def test_clean_standalone_archive_cli_without_pipeline_or_hooks(tmp_path):
    archive, manifest, expected = make_package(ROOT, tmp_path)
    delivery.verify_archive(archive, manifest, expected)
    installed = tmp_path / "installed"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(installed)
    assert not (installed / "pipeline").exists()
    assert not (installed / ".codex").exists()
    target = tmp_path / "target"
    target.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("GIT_")}
    def git(*args):
        result = subprocess.run(["git", "-C", str(target), "-c", "core.hooksPath=" + os.devnull,
                                 "-c", "commit.gpgsign=false", *args],
                                capture_output=True, env=env, timeout=20)
        assert result.returncode == 0, result.stderr
        return result.stdout.decode().strip()
    git("init", "-q")
    git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "commit", "--allow-empty", "-qm", "base")
    head = git("rev-parse", "HEAD")
    result = subprocess.run([sys.executable, "-I", "-B", str(installed / "scripts/git_docs_verify.py"),
                             "--root", str(target), "--mode", "range", "--base", head, "--head", head],
                            capture_output=True, cwd=target, env=dict(env, PYTHONPATH="untrusted"), timeout=40)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["verdict"] == "PASS"
    assert not list(installed.rglob("*.pyc"))


@pytest.mark.parametrize("attack", ["package", "unchecked-pyc"])
def test_package_bootstrap_ignores_unmanifested_delivery_imports(tmp_path, attack):
    archive, manifest, expected = make_package(ROOT, tmp_path)
    delivery.verify_archive(archive, manifest, expected)
    installed = tmp_path / "installed"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(installed)
    marker = tmp_path / "untrusted-delivery-ran"
    malicious = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\n"
    module_path = installed / "src/harness/git_docs_delivery.py"
    if attack == "package":
        path = installed / "src/harness/git_docs_delivery/__init__.py"
        path.parent.mkdir()
        path.write_text(malicious)
    else:
        candidate = tmp_path / "malicious.py"
        candidate.write_text(malicious)
        py_compile.compile(str(candidate), cfile=importlib.util.cache_from_source(str(module_path)),
                           doraise=True, invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    control = subprocess.run([sys.executable, "-I", "-B", "-c",
                              "import sys; sys.path.insert(0, " + repr(str(installed))
                              + "); import src.harness.git_docs_delivery"],
                             capture_output=True, timeout=20)
    assert control.returncode == 0 and marker.exists(), control.stderr
    marker.unlink()
    result = subprocess.run([sys.executable, "-I", "-B", str(installed / "scripts/git_docs_package.py"),
                             "verify", "--archive", str(archive), "--trusted-manifest", str(manifest),
                             "--expected-manifest-sha256", expected], capture_output=True, timeout=30)
    assert result.returncode == 0 and json.loads(result.stdout)["verdict"] == "PASS", result.stderr
    assert not marker.exists()


def test_source_loader_restores_existing_module_objects_and_uses_snapshot(tmp_path, monkeypatch):
    import src
    from src import harness
    archive, manifest, expected = make_package(ROOT, tmp_path)
    installed = tmp_path / "installed"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(installed)
    helper = runpy.run_path(str(ROOT / "scripts/git_docs_source_loader.py"))
    load = helper["load_runtime"]
    bootstrap = helper["load_delivery"](installed)
    original = bootstrap.verified_snapshot
    marker = tmp_path / "unverified-source-ran"
    def snapshot_then_mutate(*args):
        digest, snapshot = original(*args)
        (installed / "src/harness/git_docs_report.py").write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).write_text('unsafe')\n")
        return digest, snapshot
    monkeypatch.setattr(bootstrap, "verified_snapshot", snapshot_then_mutate)
    monkeypatch.setitem(load.__globals__, "load_delivery", lambda root: bootstrap)
    runtime, digest = load(installed, manifest, expected)
    assert digest == expected and callable(runtime["src.harness.git_docs_report"].validate_report)
    assert not marker.exists()
    assert sys.modules["src"] is src and sys.modules["src.harness"] is harness
    assert src.harness is harness
    assert sys.modules["src.harness.git_docs_delivery"] is delivery


@pytest.mark.parametrize("initializer", ["src/__init__.py", "src/harness/__init__.py"])
def test_source_loader_checks_initializer_bytes_before_execution(tmp_path, initializer):
    archive, manifest, expected = make_package(ROOT, tmp_path)
    installed = tmp_path / "installed"
    with zipfile.ZipFile(archive) as stream:
        stream.extractall(installed)
    marker = tmp_path / "initializer-ran"
    (installed / initializer).write_text(
        f"from pathlib import Path\nPath({str(marker)!r}).write_text('unsafe')\n")
    loader = runpy.run_path(str(ROOT / "scripts/git_docs_source_loader.py"))
    with pytest.raises(ValueError, match="installed delivery"):
        loader["load_runtime"](installed, manifest, expected)
    assert not marker.exists()
