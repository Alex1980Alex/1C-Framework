#!/usr/bin/env python3
"""Линтер полноты 1С-артефактов пайплайна: ANALYSIS-REPORT.md / IMPLEMENTATION-PROGRESS.md.

Проверяет наличие де-факто ОБЯЗАТЕЛЬНЫХ секций конвенции (analyze-1c-task-v2 §1-§11 /
implement-1c-task IMPLEMENTATION-PROGRESS). **Advisory, не hard-блок** — толерантен к вариациям
(bugfix Root Cause, мелкая задача сжимается): проверки широкие (case-insensitive, альтернативы),
флагает только ЯВНО отсутствующие core-секции. Корень пробела: run-1c-task давал тонкие отчёты,
ничто не проверяло структуру.

Использование:
    python scripts/lint_1c_artifacts.py <файл>          # авто-детект типа по имени
    python scripts/lint_1c_artifacts.py --json <файл>    # JSON для хуков/CI
    python scripts/lint_1c_artifacts.py --kind analysis|implementation <файл>

Возврат: всегда exit 0 (advisory). JSON: {kind, score, ok, present[], missing[]}.
stdlib-only.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

# Де-факто обязательные секции. (метка, regex-альтернативы). LENIENT: широкие паттерны.
# LENIENT, но по КОНТЕНТ-маркерам (не по голым номерам заголовков ## N — те матчат любую секцию).
_ANALYSIS_SECTIONS = [
    ("Требования (§1 / [REQ-N])", r"\bтребовани|\[REQ-"),
    ("Объекты конфигурации [MODIFIED]/[ADDED]", r"\[MODIFIED\]|\[ADDED\]|задействованны.{0,20}объект"),
    ("Анализ механизма / паттерны", r"механизм|паттерн|алгоритм"),
    ("План / точки модификации", r"точк[аи]\s+модификаци|план\s+(?:изменени|реализаци|модификаци)"),
    ("Риски / открытые вопросы", r"\bриск|открыты.{0,3}вопрос"),
    ("Тест-план / критерий приёмки", r"тест[-\s]?план|критери.{0,3}при[её]мк|тест[-\s]?страт|render[-\s]?verify"),
    ("Резюме / Маршрут (§9/§11)", r"резюме|следующие шаги|маршрут|сложность:"),
    ("JIRA / МЕТАДАННЫЕ", r"GKSTCPLK-\d+|метаданны|GMFM-\d+"),
]
# Pipeline mode — в шаблоне есть, но де-факто лишь ~68% файлов (code-verify ade29e8e) → НЕ scoring-core
# (иначе ложно-шумит на полных IMPL); остаётся рекомендацией в run-1c-task SKILL, не floor валидатора.
_IMPL_SECTIONS = [
    ("Статус", r"##\s*статус|статус:|status:"),
    ("Выполненные точки / реализация", r"выполненны|реализован|точк[аи]\s+модификаци"),
    ("Отклонения от ANALYSIS-REPORT", r"отклонени|расхожден|без отклонени"),
    ("Тестирование / результаты", r"тестировани|результаты тест|render[-\s]?verify|BP[-\s]?verif|verify\s+PASS"),
    ("Коммит / МЕТАДАННЫЕ", r"метаданны|сообщение коммита"),
]


def _kind_from_name(path: str) -> str:
    n = Path(path).name.upper()
    if "IMPLEMENTATION-PROGRESS" in n:
        return "implementation"
    if "ANALYSIS-REPORT" in n:
        return "analysis"
    return "analysis"  # дефолт


def lint_text(text: str, kind: str) -> dict:
    """Проверить текст артефакта на наличие core-секций. Возврат {kind, score, ok, present, missing}."""
    sections = _IMPL_SECTIONS if kind == "implementation" else _ANALYSIS_SECTIONS
    low = (text or "").lower()
    present, missing = [], []
    for label, rx in sections:
        (present if re.search(rx, low, re.I) else missing).append(label)
    total = len(sections) or 1
    score = round(100.0 * len(present) / total)
    # ok порог: ≥70% core-секций (advisory — мягко). Пустой/совсем тонкий → not ok.
    ok = score >= 70 and len(text.strip()) >= 200
    return {"kind": kind, "score": score, "ok": ok, "present": present, "missing": missing}


def lint_file(path: str, kind: str | None = None) -> dict:
    k = kind or _kind_from_name(path)
    try:
        text = Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        return {"kind": k, "score": 0, "ok": False, "present": [], "missing": ["<файл не прочитан>"], "error": str(e)}
    out = lint_text(text, k)
    out["file"] = path
    return out


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # cp1251-console safe
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Линтер полноты 1С-артефактов (advisory)")
    ap.add_argument("file")
    ap.add_argument("--kind", choices=["analysis", "implementation"], default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    res = lint_file(args.file, args.kind)
    if args.json:
        print(json.dumps(res, ensure_ascii=False))
    else:
        mark = "✓" if res["ok"] else "⚠"
        print(f"{mark} {res['kind']} score={res['score']}/100  ({Path(args.file).name})")
        if res["missing"]:
            print("  отсутствуют секции:")
            for m in res["missing"]:
                print(f"    ✗ {m}")
    return 0  # advisory — всегда 0


if __name__ == "__main__":
    raise SystemExit(main())
