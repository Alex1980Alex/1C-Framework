#!/usr/bin/env python3
"""Динамическое открытие BSL-корней для SonarQube `sonar.sources` (ADR-021 G19).

Открываем все корни с .bsl на момент скана (НЕ хардкодим один путь).
`configuration/<JIRA>` ИСКЛЮЧЁН из Sonar-скоупа целиком (ADR-048 approve 2026-07-06:
папки ведения задач — ТЗ/доки/исторические дампы, живой код не ведётся; гейт ADR-037
их тоже не детектит — см. sonar_rescan_state._is_config_bsl).

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
    "MFM/Конфигурация",  # УправлениеМатериальнымиПотоками (проект utp-mfm; ADR-048 A7 вар.а —
    # скан в mono сейчас, без слепых зон; в split-режиме → отдельный проект utp-mfm)
    "TransportManagementDevelop_KAT/Конфигурация",  # KAT-конфиг (проект utp-kat, 2026-07-23;
    # в главном репо, не сабмодуль). В split ps1 берёт реестр sonar_projects — здесь для парного
    # инварианта «скан-скоуп ↔ mono-фоллбэк»; split-поведение бит-в-бит не меняет.
    # "src/bsl",  # framework-дамп BSL — отдельный продукт; включить при необходимости
]

# Родители, чьи подкаталоги = РАСТУЩИЕ корни. ПУСТО с 2026-07-06 (ADR-048 approve):
# configuration/<JIRA> исключён из скоупа целиком (ведение задач, не код). Механизм
# оставлен — возврат корня при возобновлении правок = одна строка здесь.
GROWING_PARENTS: list[str] = []


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
