#!/usr/bin/env python3
"""Состояние обязательного Sonar re-scan изменённого/добавленного 1С-кода.

Единый контракт «что считается изменённым 1С-кодом» (детект `.bsl` в основном репо +
сабмодулях) + чтение/запись/оценка state-файла. Используется ОБОИМИ:
  - `scripts/sonar_rescan_verify.py` (пишет state после проверки дельты по Sonar),
  - `onec-task-completion-stop.py` (Stop-гейт читает state и решает блок).

DRY обязателен: если детект разойдётся, гейт заблокирует на файлах, которые verify не
проверял (или наоборот). Поэтому общая точка — здесь.

State-файл: `.claude/cache/onec-sonar-rescan-state.json`
  {
    "ts": ISO,                 # когда verify отработал
    "host": "...",             # Sonar host
    "pass": bool,              # все изменённые .bsl чисты (0 BLOCKER/CRITICAL) и скан свежий
    "skipped": bool,           # Sonar был недоступен → проверить нельзя (reachability-skip)
    "files_verified": [..],    # пути .bsl (относительно корня репо, forward-slash), что проверены
    "fail_files": [..],        # файлы с BLOCKER/CRITICAL или не проанализированные
    "scan_stale": bool,        # последний анализ Sonar старше правок (нужен свежий скан)
    "last_analysis": ISO|null
  }
stdlib-only (subprocess/json/pathlib) — безопасно импортировать из Stop-хука.
"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path

STATE_REL = ".claude/cache/onec-sonar-rescan-state.json"


def state_path(root: Path) -> Path:
    return Path(root) / ".claude" / "cache" / "onec-sonar-rescan-state.json"


def parse_dt(s) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(s or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    # НЕ срезать tzinfo: Sonar-дата приходит UTC (+0000); при срезе .timestamp() трактует
    # UTC-время как локальное → в TZ ахед UTC анализ выглядит на offset часов «старше» mtime
    # → ложное stale-scan. Aware-вход остаётся aware (корректный epoch), naive (локальный
    # state-ts от datetime.now()) остаётся naive — прямое сравнение ts<session_start не ломается.
    return dt


def _git_changed(cwd: str) -> list[str]:
    """Изменённые/добавленные пути (porcelain) в git work-tree cwd. Пусто при ошибке."""
    try:
        r = subprocess.run(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain", "--untracked-files=all"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    if r.returncode != 0:
        return []
    out: list[str] = []
    for line in r.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:  # rename "old -> new" → актуальный путь
            path = path.split(" -> ", 1)[1].strip().strip('"')
        out.append(path)
    return out


def _submodule_paths(root: Path) -> list[str]:
    """Пути сабмодулей из .gitmodules (config-конфигурации 1С лежат сабмодулями)."""
    gm = root / ".gitmodules"
    if not gm.exists():
        return []
    try:
        r = subprocess.run(
            ["git", "config", "--file", str(gm), "--get-regexp", r"\.path$"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return []
    paths: list[str] = []
    for line in r.stdout.splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            paths.append(parts[1].strip())
    return paths


def _is_config_bsl(rel: str) -> bool:
    """Продакшн-код 1С: `.bsl` в EDT-дереве конфигурации (под `/src/`).

    Отсекает scratch/пример-`.bsl` в `configuration/<JIRA>/docs/...` (не в Sonar-скоупе,
    не анализируется) — иначе гейт ложно блокировал бы на них («не проанализирован»).
    `configuration/` исключён ЦЕЛИКОМ — включая `.bsl` под `/src/` исторических дампов
    (ADR-048 approve 2026-07-06: это папки ведения задач — ТЗ/доки, живой код не ведётся;
    Sonar их не сканирует, значит и гейт не детектит, иначе dead-lock «не проанализирован»)."""
    r = rel.replace("\\", "/").lower()
    if r.startswith("configuration/"):
        return False
    return r.endswith(".bsl") and "/src/" in r


def changed_bsl_paths(root) -> set[str]:
    """Изменённые/добавленные продакшн-`.bsl` (под `/src/`) в основном репо + сабмодулях.

    Возвращает пути относительно корня репо (forward-slash) — совпадают с component-путём
    Sonar (projectBaseDir = корень репо). Сабмодуль-внутренние правки видны только через
    `git -C <submodule> status` (в основном репо сабмодуль = одна gitlink-запись).
    Фильтр `/src/`: scratch-`.bsl` в docs задачи в скоуп Sonar не входят."""
    root = Path(root)
    found: set[str] = set()
    for p in _git_changed(str(root)):
        full = p.replace("\\", "/")
        if _is_config_bsl(full):
            found.add(full)
    for sub in _submodule_paths(root):
        subdir = root / sub
        if not subdir.is_dir():
            continue
        prefix = sub.rstrip("/")
        for p in _git_changed(str(subdir)):
            full = (prefix + "/" + p).replace("\\", "/")
            if _is_config_bsl(full):
                found.add(full)
    return found


def _owning_tree(root: Path, rel: str) -> tuple[Path, str]:
    """Work-tree (main-репо или сабмодуль), которому принадлежит repo-относительный rel."""
    for sub in _submodule_paths(root):
        prefix = sub.rstrip("/") + "/"
        if rel.startswith(prefix):
            return root / sub.rstrip("/"), rel[len(prefix) :]
    return root, rel


def parse_hunk_new_ranges(diff_text: str) -> list[tuple[int, int]]:
    """Диапазоны строк new-стороны unified diff: `@@ -a[,b] +c[,d] @@` → [(start, end)],
    1-based включительно. d==0 (чистое удаление) диапазона не даёт."""
    ranges: list[tuple[int, int]] = []
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", diff_text, re.MULTILINE):
        start = int(m.group(1))
        count = 1 if m.group(2) is None else int(m.group(2))
        if count > 0:
            ranges.append((start, start + count - 1))
    return ranges


def changed_line_ranges(root, rel: str) -> list[tuple[int, int]] | None:
    """Строки rel, СОДЕРЖАТЕЛЬНО изменённые vs HEAD (`diff -w -U0`: whitespace-only и
    format-churn «моими» не считаются). Сервер-независимая основа Clean-as-You-Code:
    verify гейтит issue по пересечению с этими строками, а не по inNewCodePeriod.

    None = файл новый/untracked ИЛИ дифф не получен → потребитель считает ВСЕ строки
    изменёнными (fail-closed). [] = только whitespace/удаления (моих строк нет)."""
    root = Path(root)
    tree, rel_in = _owning_tree(root, rel)
    try:
        tracked = subprocess.run(
            ["git", "-c", "core.quotepath=false", "ls-files", "--error-unmatch", rel_in],
            cwd=str(tree),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=5,
        )
        if tracked.returncode != 0:
            return None  # untracked → все строки новые
        d = subprocess.run(
            ["git", "-c", "core.quotepath=false", "diff", "-w", "-U0", "HEAD", "--", rel_in],
            cwd=str(tree),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
        if d.returncode not in (0, 1):
            return None
        return parse_hunk_new_ranges(d.stdout)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def newest_mtime(root, paths) -> float:
    """Максимальный mtime (epoch) из переданных путей; 0.0 если ни один не читается."""
    root = Path(root)
    newest = 0.0
    for rel in paths:
        try:
            m = (root / rel).stat().st_mtime
            if m > newest:
                newest = m
        except OSError:
            continue
    return newest


def read_state(root) -> dict | None:
    p = state_path(Path(root))
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def write_state(root, data: dict) -> None:
    p = state_path(Path(root))
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


def evaluate(root, session_start: datetime | None) -> tuple[bool, str, str]:
    """Решение гейта по state. → (ok, status, human-detail).

    ok=True → не блокировать. Статусы блока: missing / stale / stale-scan / fail / uncovered /
    edits-after. skipped (Sonar был недоступен) и no-bsl → ok (нет дедлока).
    ts=None трактуется как stale (не доверяем state без метки времени, R1 code-verify)."""
    root = Path(root)
    changed = changed_bsl_paths(root)
    if not changed:
        return True, "no-bsl", "нет изменённых .bsl — проверять нечего"
    st = read_state(root)
    if not st:
        return (
            False,
            "missing",
            "Sonar-verify не запускался — прогони scripts/sonar_rescan_verify.py",
        )
    ts = parse_dt(st.get("ts"))
    if ts is None:
        return (
            False,
            "stale",
            "Sonar-verify без валидной метки времени — прогони scripts/sonar_rescan_verify.py заново",
        )
    if session_start is not None and ts < session_start:
        return False, "stale", "Sonar-verify последний раз вне этой сессии — прогони заново"
    if st.get("skipped"):
        return (
            True,
            "skipped",
            "Sonar был недоступен при verify — проверка пропущена (reachability)",
        )
    if st.get("scan_stale"):
        return (
            False,
            "stale-scan",
            "Sonar-анализ устарел относительно правок — прогони run-sonar-analysis.ps1, затем sonar_rescan_verify.py",
        )
    if not st.get("pass"):
        ff = ", ".join(st.get("fail_files", [])[:5]) or "см. state"
        return (
            False,
            "fail",
            f"на изменённых файлах есть BLOCKER/CRITICAL или они не проанализированы: {ff}",
        )
    verified = {str(x).replace("\\", "/") for x in st.get("files_verified", [])}
    uncovered = changed - verified
    if uncovered:
        return (
            False,
            "uncovered",
            f"не проверены изменённые файлы: {', '.join(sorted(uncovered)[:5])}",
        )
    nm = newest_mtime(root, changed)
    if ts is not None and nm and ts.timestamp() < nm:
        return False, "edits-after", "были правки .bsl ПОСЛЕ Sonar-verify — прогони verify заново"
    return True, "ok", "все изменённые .bsl проверены Sonar, BLOCKER/CRITICAL=0"
