#!/usr/bin/env python3
"""Реестр Sonar-проектов по конфигурациям (ADR-048, P3.A).

Единственный источник маппинга «repo-путь → {проект, корень}» для split-режима
(`SONAR_SPLIT_PROJECTS=1`). В legacy-режиме (флаг OFF, дефолт) НЕ используется —
монопроект `upravlenie-transportom-plk` сканирует все корни разом (текущее поведение
бит-в-бит, `sonar_sources.py`).

Проекты = ЖИВЫЕ конфигурации:
  utp-ib     ← ИБTransportManagementDevelop/Конфигурация       (транспорт, главный продукт)
  utp-svetly ← TransportManagementDevelop_SVETLY/Конфигурация  (транспорт, база SVETLY)
  utp-mfm    ← MFM/Конфигурация  (УправлениеМатериальнымиПотоками; ADR-048 A7 вар.а — свой
              проект, сканируется, слепых зон нет)

Вне реестра (гейт их тоже НЕ детектит — `sonar_rescan_state._is_config_bsl`):
  - `configuration/<JIRA>` — папки ведения задач (ТЗ/доки/дампы), не код (ADR-048 A0).
Возврат конфигурации в скоуп = добавить запись в PROJECTS.

CLI:
    python scripts/sonar_projects.py --list        # key<TAB>root (диагностика)
    python scripts/sonar_projects.py --list-json    # JSON [{key,root,name}] для ps1/verify
stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repo root

# Объявленные проекты: key → repo-относительный корень конфигурации + имя проекта Sonar.
# Расширение (возврат конфигурации в скоуп) — одна запись здесь.
PROJECTS: list[dict[str, str]] = [
    {
        "key": "utp-ib",
        "root": "ИБTransportManagementDevelop/Конфигурация",
        "name": "УправлениеТранспортомНаПЛК (ИБ)",
    },
    {
        "key": "utp-svetly",
        "root": "TransportManagementDevelop_SVETLY/Конфигурация",
        "name": "УправлениеТранспортомНаПЛК (SVETLY)",
    },
    {
        "key": "utp-mfm",
        "root": "MFM/Конфигурация",
        "name": "УправлениеМатериальнымиПотоками (MFM)",
    },
]


def _has_bsl(d: Path) -> bool:
    return next(d.rglob("*.bsl"), None) is not None


def projects() -> list[dict[str, str]]:
    """Проекты реестра, чей корень существует и содержит хотя бы один .bsl."""
    out: list[dict[str, str]] = []
    for p in PROJECTS:
        d = ROOT / p["root"]
        if d.is_dir() and _has_bsl(d):
            out.append(p)
    return out


def roots() -> list[str]:
    """Repo-относительные корни (forward-slash) существующих проектов реестра.

    Единый источник «что в Sonar-скоупе» для scan (sonar_sources) и detect гейта
    (paired-инвариант: скан-скоуп ↔ гейт-детект меняются вместе)."""
    return [Path(p["root"]).as_posix() for p in projects()]


def project_for_path(rel: str) -> tuple[str, str, str] | None:
    """(key, root, rel_in_root) для repo-относительного пути rel под корнем проекта.

    None — путь вне всех корней реестра (configuration/<JIRA>, MFM/, framework и т.п.).
    Матч по ОБЪЯВЛЕННЫМ PROJECTS (существование корня для маппинга не важно; важно для скана).
    Более длинный корень выигрывает (нет вложенности корней сейчас, но детерминизм на будущее)."""
    r = rel.replace("\\", "/")
    best: tuple[str, str, str] | None = None
    best_len = -1
    for p in PROJECTS:
        root = Path(p["root"]).as_posix().rstrip("/")
        prefix = root + "/"
        if r.startswith(prefix) and len(root) > best_len:
            best = (p["key"], p["root"], r[len(prefix) :])
            best_len = len(root)
    return best


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Реестр Sonar-проектов по конфигурациям (ADR-048)")
    ap.add_argument("--list", action="store_true", help="key<TAB>root по строке (диагностика)")
    ap.add_argument(
        "--list-json", action="store_true", help="JSON [{key,root,name}] для ps1/verify"
    )
    a = ap.parse_args(argv)
    ps = projects()
    if a.list_json:
        # stdout UTF-8 байтами (cp1251-консоль на Windows иначе ломает кириллицу)
        sys.stdout.buffer.write(json.dumps(ps, ensure_ascii=False).encode("utf-8"))
        sys.stdout.buffer.write(b"\n")
    else:
        out = "\n".join(f"{p['key']}\t{p['root']}" for p in ps)
        sys.stdout.buffer.write((out + "\n").encode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
