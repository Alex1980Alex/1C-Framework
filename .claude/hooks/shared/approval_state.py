#!/usr/bin/env python3
"""Единый источник OpenSpec-approval — ADR-041 R1 (унификация SDD/гл.24 ↔ пайплайн/гл.43).

Сводит чтение «дизайн одобрен через OpenSpec?» в ОДИН модуль, который используют оба гейта:
  - ``approval-gate.py`` (PreToolUse:Skill) — блок implement-skills без approved OpenSpec change;
  - ``pipeline_1c_bridge.gate_1c_implement`` (G4, UserPromptSubmit) — теперь **honors** OpenSpec-approval,
    т.к. ``/opsx:approve`` пишет ``.openspec.yaml`` (а не ``.pipeline-state.json``) → раньше G4 ложно
    блокировал implement в SDD-потоке (расхождение двух сторов — корневой баг R1).

DRY: чтение статуса (бывш. ``approval-gate._read_approval_status``/``_read_profile``) + матч change↔JIRA
(бывш. ``openspec-change-coverage._change_matches_jira``) живут здесь.

Контракт: **best-effort** — любая ошибка / нет каталога → нейтральный результат (None / False),
гейты не ломаем (fail-open, как было).
"""

from __future__ import annotations

import os
import re

_JIRA_RE = re.compile(r"(GKSTCPLK-\d{3,5})", re.IGNORECASE)


def project_root() -> str:
    """Корень репо: .claude/hooks/shared/approval_state.py → ../../.. ."""
    return os.path.normpath(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..")
    )


def _changes_dir(root: str | None = None) -> str:
    return os.path.join(root or project_root(), "openspec", "changes")


def read_approval_status(yaml_path: str) -> str | None:
    """approval.status из ``.openspec.yaml`` без pyyaml. None если секции нет / ошибка.

    Идентична бывшей ``approval-gate._read_approval_status`` (поведение сохранено).
    """
    try:
        with open(yaml_path, encoding="utf-8") as f:
            content = f.read()
        in_approval = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "approval:" or stripped.startswith("approval:"):
                after = stripped.split(":", 1)[1].strip()
                if after and after != "":
                    if "status:" in after:
                        for part in after.replace("{", "").replace("}", "").split(","):
                            if "status:" in part:
                                return part.split(":", 1)[1].strip().strip("'\"")
                in_approval = True
                continue
            if in_approval:
                if stripped.startswith("status:"):
                    return stripped.split(":", 1)[1].strip().strip("'\"")
                if not line.startswith(" ") and not line.startswith("\t") and stripped:
                    break
        return None
    except Exception:
        return None


def read_profile(yaml_path: str) -> str:
    """Top-level ``profile`` из ``.openspec.yaml``; ``1c-bsl`` по умолчанию (backward-compat)."""
    try:
        with open(yaml_path, encoding="utf-8") as f:
            content = f.read()
        for line in content.splitlines():
            stripped = line.strip()
            if (
                not line.startswith(" ")
                and not line.startswith("\t")
                and stripped.startswith("profile:")
            ):
                value = stripped.split(":", 1)[1].strip().strip("'\"")
                if value:
                    return value
        return "1c-bsl"
    except Exception:
        return "1c-bsl"


def list_active_changes(root: str | None = None) -> list[tuple[str, str]]:
    """[(change_name, yaml_path)] активных (не archive) change'ей с ``.openspec.yaml``."""
    cdir = _changes_dir(root)
    if not os.path.isdir(cdir):
        return []
    out: list[tuple[str, str]] = []
    try:
        for entry in os.listdir(cdir):
            if entry == "archive":
                continue
            change_dir = os.path.join(cdir, entry)
            if os.path.isdir(change_dir):
                yaml_path = os.path.join(change_dir, ".openspec.yaml")
                if os.path.isfile(yaml_path):
                    out.append((entry, yaml_path))
    except Exception:
        return []
    return out


def change_matches_jira(change_name: str, yaml_path: str, jira: str) -> bool:
    """JIRA-токен упомянут в имени change ИЛИ в ``.openspec.yaml``/``proposal.md``/``tasks.md``.

    Идентично логике ``openspec-change-coverage._change_matches_jira`` (case-insensitive).
    """
    j = (jira or "").lower()
    if not j:
        return False
    if j in (change_name or "").lower():
        return True
    change_dir = os.path.dirname(yaml_path)
    for fn in (".openspec.yaml", "proposal.md", "tasks.md"):
        try:
            with open(os.path.join(change_dir, fn), encoding="utf-8", errors="replace") as f:
                if j in f.read().lower():
                    return True
        except (FileNotFoundError, OSError):
            continue
        except Exception:
            continue
    return False


def openspec_status_for_jira(jira: str, root: str | None = None) -> str | None:
    """approval.status связанного с JIRA active change. None если связанного change нет.

    Несколько связанных → статус ПЕРВОГО совпадения (обычно один change на JIRA).
    """
    if not jira:
        return None
    for name, yaml_path in list_active_changes(root):
        if change_matches_jira(name, yaml_path, jira):
            return read_approval_status(yaml_path)
    return None


def is_design_approved_via_openspec(text: str, root: str | None = None) -> bool:
    """True ⇔ в тексте есть JIRA-токен и связанный OpenSpec change == ``approved``.

    best-effort → False (нет JIRA / нет связанного change / не approved / ошибка). Используется
    как ДОПОЛНИТЕЛЬНОЕ плечо «дизайн одобрен» в ``gate_1c_implement`` (OR с pipeline-state G4).
    """
    try:
        m = _JIRA_RE.search(text or "")
        if not m:
            return False
        return openspec_status_for_jira(m.group(1).upper(), root) == "approved"
    except Exception:
        return False
