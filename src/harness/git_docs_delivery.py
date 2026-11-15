"""Deterministic, explicit Git/docs delivery; run this verifier from trusted code."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import zipfile
from pathlib import Path, PurePosixPath

# No directory walks: adding a component requires an explicit delivery change.
PACKAGE_FILES = (
    "docs/git-docs-boundary.md",
    "src/__init__.py", "src/harness/__init__.py",
    "src/harness/git_docs_boundary.py", "src/harness/git_docs_policy.py",
    "src/harness/git_docs_rules.json", "src/harness/git_docs_report.py",
    "src/harness/git_docs_delivery.py", "scripts/git_docs_verify.py",
    "scripts/git_docs_package.py", "scripts/git_docs_ci.py",
    "scripts/git_docs_source_loader.py",
    "scripts/git_docs_pre_commit.py", "scripts/git_hooks/pre-commit.git-docs.example",
    "tests/unit/test_git_docs_boundary_contract.py",
    "tests/unit/test_git_docs_boundary_safety.py",
    "tests/unit/test_git_docs_delivery.py", "tests/unit/test_git_docs_ci.py",
    "tests/unit/test_git_docs_pre_commit.py", "tests/unit/test_git_docs_report.py",
    "tests/fixtures/git_docs_rules_baseline.json", ".github/workflows/git-docs.yml",
)
MAX_FILE_BYTES = 2_000_000
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_path(value):
    """Reject cross-platform ambiguous archive names, including NTFS streams."""
    if (not isinstance(value, str) or not value or "\\" in value or ":" in value
            or "\0" in value or PurePosixPath(value).is_absolute()
            or any(p in {"", ".", ".."} for p in value.split("/"))):
        raise ValueError("unsafe package path")
    return value


def no_links(path):
    """Check every existing ancestor without resolving away symlink evidence."""
    path = Path(path)
    if not path.is_absolute():
        raise ValueError("absolute path required")
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("symlink/reparse path refused")
    return path.resolve()


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load_manifest(raw, expected_digest=None):
    if expected_digest is not None and (
            not SHA256.fullmatch(expected_digest) or sha256(raw) != expected_digest):
        raise ValueError("trusted manifest digest mismatch")
    manifest = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
    if (type(manifest) is not dict or type(manifest.get("schema_version")) is not int
            or manifest["schema_version"] != 1
            or set(manifest) != {"schema_version", "source_base", "files"}
            or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", str(manifest["source_base"]))
            or type(manifest["files"]) is not dict
            or set(manifest["files"]) != set(PACKAGE_FILES)):
        raise ValueError("unsupported delivery manifest")
    for name, record in manifest["files"].items():
        safe_path(name)
        if (type(record) is not dict or set(record) != {"sha256", "size"}
                or not isinstance(record["sha256"], str) or not SHA256.fullmatch(record["sha256"])
                or type(record["size"]) is not int or not 0 <= record["size"] <= MAX_FILE_BYTES):
            raise ValueError("invalid delivery file record")
    return manifest


def build(source, output, source_base):
    """Create candidate archive and separate manifest; base is provenance, not approval."""
    source = no_links(source)
    output = no_links(output)
    manifest_path = no_links(Path(str(output) + ".manifest.json"))
    if output.is_relative_to(source) or manifest_path.is_relative_to(source):
        raise ValueError("delivery output must be outside source")
    if output.exists() or manifest_path.exists():
        raise ValueError("delivery output already exists")
    payload = {}
    for name in sorted(PACKAGE_FILES):
        file = no_links(source / safe_path(name))
        if not file.is_relative_to(source) or not file.is_file():
            raise ValueError("missing regular delivery file: " + name)
        if file.stat().st_size > MAX_FILE_BYTES:
            raise ValueError("delivery file too large")
        payload[name] = file.read_bytes()
        if len(payload[name]) > MAX_FILE_BYTES:
            raise ValueError("delivery file grew too large")
    manifest = {"schema_version": 1, "source_base": source_base,
                "files": {name: {"sha256": sha256(data), "size": len(data)}
                          for name, data in payload.items()}}
    raw = (json.dumps(manifest, sort_keys=True, indent=2, ensure_ascii=True) + "\n").encode()
    load_manifest(raw)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_STORED) as archive:
        for name, data in payload.items():
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, data)
    with manifest_path.open("xb") as stream:
        stream.write(raw)
    return {"archive": str(output), "trusted_manifest_candidate": str(manifest_path),
            "manifest_sha256": sha256(raw), "source_base": source_base}


def verify_archive(archive_path, trusted_manifest, expected_digest=None):
    """Check bytes only; caller must establish trust in this code and external manifest."""
    archive_path, trusted_manifest = no_links(archive_path), no_links(trusted_manifest)
    if trusted_manifest.stat().st_size > 100_000:
        raise ValueError("manifest too large")
    raw = trusted_manifest.read_bytes()
    manifest = load_manifest(raw, expected_digest)
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        if (len(entries) != len(PACKAGE_FILES)
                or {i.filename for i in entries} != set(PACKAGE_FILES)):
            raise ValueError("archive does not match explicit delivery list")
        for info in entries:
            safe_path(info.filename)
            mode = info.external_attr >> 16
            record = manifest["files"][info.filename]
            if (not stat.S_ISREG(mode) or info.flag_bits & 1
                    or info.file_size != record["size"] or info.file_size > MAX_FILE_BYTES):
                raise ValueError("invalid archive member")
            data = archive.read(info)
            if len(data) != record["size"] or sha256(data) != record["sha256"]:
                raise ValueError("archive file digest mismatch: " + info.filename)
    return {"verdict": "PASS", "manifest_sha256": sha256(raw),
            "source_base": manifest["source_base"], "files": len(PACKAGE_FILES)}


def verified_snapshot(root, trusted_manifest, expected_digest=None):
    """Return the exact verified bytes; execution must not reread source files."""
    root, trusted_manifest = no_links(root), no_links(trusted_manifest)
    if trusted_manifest.stat().st_size > 100_000:
        raise ValueError("manifest too large")
    raw = trusted_manifest.read_bytes()
    manifest = load_manifest(raw, expected_digest)
    snapshot = {}
    for name, record in manifest["files"].items():
        file = no_links(root / name)
        if not file.is_file() or file.stat().st_size != record["size"]:
            raise ValueError("installed delivery file size mismatch: " + name)
        data = file.read_bytes()
        if len(data) != record["size"] or sha256(data) != record["sha256"]:
            raise ValueError("installed delivery digest mismatch: " + name)
        snapshot[name] = data
    return sha256(raw), snapshot


def verify_installed(root, trusted_manifest, expected_digest=None):
    """Compatibility check for callers that do not execute installed modules."""
    return verified_snapshot(root, trusted_manifest, expected_digest)[0]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    builder = commands.add_parser("build")
    builder.add_argument("--source", required=True)
    builder.add_argument("--output", required=True)
    builder.add_argument("--source-base", required=True)
    verifier = commands.add_parser("verify")
    verifier.add_argument("--archive", required=True)
    verifier.add_argument("--trusted-manifest", required=True)
    verifier.add_argument("--expected-manifest-sha256")
    args = parser.parse_args(argv)
    try:
        result = (build(args.source, args.output, args.source_base) if args.command == "build"
                  else verify_archive(args.archive, args.trusted_manifest,
                                      args.expected_manifest_sha256))
    except (OSError, ValueError, zipfile.BadZipFile, KeyError) as exc:
        print(json.dumps({"verdict": "UNKNOWN", "errors": [str(exc)]}))
        return 2
    print(json.dumps(result, ensure_ascii=True))
    return 0
