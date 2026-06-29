#!/usr/bin/env python3
"""Динамическое открытие BSL-корней для SonarQube `sonar.sources` (ADR-021 G19).

Источники РАСТУТ (новые `configuration/<JIRA>` сабмодули, доп. конфиги) → НЕ хардкодим
один путь, а открываем все корни с .bsl на момент скана. Новый конфиг/задача
подхватывается автоматически, без правки `sonar-project.properties`.

Вывод (stdout): comma-joined относительные пути (для `-Dsonar.sources=...`), только
существующие и непустые (≥1 .bsl) — пустые/невыгруженные сабмодули отбрасываются.

Использование:
    SRC=$(python scripts/sonar_sources.py)        # для -Dsonar.sources
    python scripts/sonar_sources.py --list        # человекочитаемо (диагностика)

Расширение: добавить корень — допиши в STABLE_ROOTS или GROWING_PARENTS ниже.
stdlib-only.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # repo root

# Стабильные корни (всегда кандидаты).
STABLE_ROOTS = [
    "ИБTransportManagementDevelop/Конфигурация",  # главный конфиг (продукт)
    "TransportManagementDevelop_SVETLY/Конфигурация",  # конфиг базы SVETLY (тот же продукт, отд. база)
    # "src/bsl",  # framework-дамп BSL — отдельный продукт; включить при необходимости
]

# Родители, чьи подкаталоги = РАСТУЩИЕ корни (новые per-JIRA конфиги добавляются сюда).
GROWING_PARENTS = [
    "configuration",  # configuration/<JIRA>/... — per-task сабмодули
]


def _has_bsl(d: Path) -> bool:
    """Быстро: есть ли хотя бы один .bsl (не обходит всё дерево целиком)."""
    return next(d.rglob("*.bsl"), None) is not None


def discover() -> list[str]:
    seen: set[str] = set()
    out: list[str] = []

    def add(d: Path) -> None:
        if not d.is_dir() or not _has_bsl(d):
            return
        rel = d.relative_to(ROOT).as_posix()
        if rel not in seen:
            seen.add(rel)
            out.append(rel)

    for r in STABLE_ROOTS:
        add(ROOT / r)
    for parent in GROWING_PARENTS:
        p = ROOT / parent
        if p.is_dir():
            for sub in sorted(p.iterdir()):
                if sub.is_dir():
                    add(sub)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Discover BSL source roots for sonar.sources")
    ap.add_argument("--list", action="store_true", help="по строке на корень (диагностика)")
    args = ap.parse_args(argv)
    roots = discover()
    # stdout UTF-8 байтами (cp1251-консоль на Windows иначе ломает кириллицу путей)
    sep = "\n" if args.list else ","
    sys.stdout.buffer.write(sep.join(roots).encode("utf-8"))
    sys.stdout.buffer.write(b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
