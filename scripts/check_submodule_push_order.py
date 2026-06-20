#!/usr/bin/env python3
"""check_submodule_push_order.py — pre-push guard (ADR-027).

Блокирует push родителя, если он двигает gitlink сабмодуля на коммит, НЕ достижимый
на remote сабмодуля (класс «dangling gitlink», PR #77: клон ломается, т.к. родитель
ссылается на неопубликованный коммит сабмодуля).

Вызов из scripts/git_hooks/pre-push:  python check_submodule_push_order.py <base> <local_sha>
Возврат: 0 — ок / graceful skip; 1 — блок (причина в stderr).
Bypass: PREPUSH_SKIP=1 git push  /  git push --no-verify.
Best-effort: любая ошибка/неинициализированный сабмодуль → пропуск (exit 0).
"""

from __future__ import annotations

import subprocess
import sys


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def _submodule_paths() -> list[str]:
    """Пути сабмодулей из .gitmodules (`submodule.<name>.path <path>`)."""
    r = _run(["git", "config", "-f", ".gitmodules", "--get-regexp", r"^submodule\..*\.path$"])
    if r.returncode != 0:
        return []
    out: list[str] = []
    for line in r.stdout.splitlines():
        line = line.strip()
        if " " in line:
            out.append(line.split(" ", 1)[1].strip())
    return out


def _gitlink_sha(rev: str, path: str) -> str | None:
    """SHA, на который указывает gitlink <path> в ревизии <rev> (mode 160000), иначе None."""
    r = _run(["git", "ls-tree", rev, "--", path])
    if r.returncode != 0 or not r.stdout.strip():
        return None
    parts = r.stdout.split()
    if len(parts) >= 3 and parts[0] == "160000":
        return parts[2]
    return None


def _is_initialized(path: str) -> bool:
    return _run(["git", "-C", path, "rev-parse", "--git-dir"]).returncode == 0


def _on_remote(path: str, sha: str) -> bool:
    """Достижим ли <sha> на каком-либо remote-tracking ref сабмодуля."""
    r = _run(["git", "-C", path, "branch", "-r", "--contains", sha])
    return r.returncode == 0 and r.stdout.strip() != ""


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        return 0
    base, lsha = argv[1], argv[2]

    problems: list[tuple[str, str]] = []
    for path in _submodule_paths():
        new = _gitlink_sha(lsha, path)
        if new is None or new == _gitlink_sha(base, path):
            continue  # сабмодуль не изменён в диапазоне
        if not _is_initialized(path):
            continue  # неинициализированный сабмодуль — graceful
        if not _on_remote(path, new):
            problems.append((path, new))

    if not problems:
        return 0

    sys.stderr.write(
        "[pre-push] BLOCKED: указатель(и) сабмодуля двигаются на НЕ запушенный коммит "
        "(класс dangling gitlink, PR #77):\n"
    )
    for path, sha in problems:
        sys.stderr.write(f"  - {path} -> {sha[:12]} (нет на remote сабмодуля)\n")
    sys.stderr.write(
        'Сначала запушь сабмодуль:  git -C "<path>" push  — затем push родителя.\n'
        "Bypass: PREPUSH_SKIP=1 git push  /  git push --no-verify\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
