#!/usr/bin/env python3
"""Generate benchmark tasks JSON for BSL rename refactoring."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
BSL_SRC = REPO_ROOT / "src" / "bsl"
OUTPUT_DIR = REPO_ROOT / "docs" / "roadmap" / "benchmark"

_RE_OLD = r"^-\s*(?:Процедура|Функция|Procedure|Function|Перем|Var)\s+(\w+)\s*\("
_RE_NEW = r"^\+\s*(?:Процедура|Функция|Procedure|Function|Перем|Var)\s+(\w+)\s*\("


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )
    return result.stdout


def find_symbol(file_path: Path, symbol: str) -> tuple[int, int] | None:
    if not file_path.exists():
        return None
    pattern = re.compile(rf"\b{re.escape(symbol)}\b")
    with open(file_path, encoding="utf-8") as f:
        for line_idx, line in enumerate(f, start=1):
            m = pattern.search(line)
            if m:
                return (line_idx, m.start())
    return None


def _file_uri(rel_path: str) -> str:
    return f"src/bsl/{rel_path}"


def _form_xml_path(module_rel: str) -> str:
    return module_rel.replace("Module.bsl", "Form.xml")


def _build_curated_tasks() -> list[dict[str, Any]]:
    paths: dict[str, str] = {
        "adr": "CommonModules/АдресныйКлассификатор/Ext/Module.bsl",
        "adr_s": "CommonModules/АдресныйКлассификаторСлужебный/Ext/Module.bsl",
        "adr_k": "CommonModules/АдресныйКлассификаторКлиент/Ext/Module.bsl",
        "adr_p": "CommonModules/АдресныйКлассификаторПовтИсп/Ext/Module.bsl",
        "gp": "CommonModules/GoogleПереводчик/Ext/Module.bsl",
        "gp_c": "CommonModules/GoogleПереводчикКлиент/Ext/Module.bsl",
        "gp_p": "CommonModules/GoogleПереводчикПовтИсп/Ext/Module.bsl",
        "adm": "CommonModules/АдминистрированиеКластера/Ext/Module.bsl",
        "f1": "Catalogs/Валюты/Forms/ПараметрыПрописиВалюты_en/Ext/Form/Module.bsl",
        "f2": "Catalogs/Валюты/Forms/ФормаСписка/Ext/Form/Module.bsl",
        "f3": "Catalogs/ВариантыОтчетов/Forms/РазмещениеВРазделах/Ext/Form/Module.bsl",
    }

    tasks: list[dict[str, Any]] = []

    cat1 = [
        ("T01", "СписокРегионов", "РегionsСписок", "adr", 54, 6, "97de8a6", "e6643f2", 1, 1),
        ("T02", "РезультатЗапроса", "ЗапросРезультат", "adr", 208, 6, "97de8a6", "e6643f2", 1, 1),
        (
            "T03",
            "НаименованияРегионов",
            "ИменаРегионов",
            "adr_s",
            223,
            6,
            "97de8a6",
            "e6643f2",
            1,
            1,
        ),
        ("T04", "Параметры", "Парам", "adr_k", 17, 18, "97de8a6", "e6643f2", 1, 1),
    ]
    for tid, sym, new, fkey, fl, fc, sha, par, efa, ee in cat1:
        rel = paths[fkey]
        full = BSL_SRC / rel
        pos = find_symbol(full, sym)
        line, col = pos if pos else (fl, fc)
        tasks.append(
            {
                "id": tid,
                "category": "CAT-1-local-variable",
                "commit_sha": sha,
                "parent_sha": par,
                "file_uri": _file_uri(rel),
                "line": line,
                "character": col,
                "old_name": sym,
                "new_name": new,
                "expected_files_affected": efa,
                "expected_edits": ee,
                "expected_files": [_file_uri(rel)],
                "notes": f"Local variable: {sym}.",
            }
        )

    cat2 = [
        ("T05", "Выборка", "РезультатВыборки", "adr", 177, 10, "e09730e", "97de8a6", 1, 1),
        ("T06", "ПеревестиТекст", "ВыполнитьПеревод", "gp", 11, 9, "7e2b3c2", "b40eb80", 1, 2),
        (
            "T07",
            "МаксимальныйРазмерПорции",
            "ПредельныйОбъёмПорции",
            "gp",
            66,
            9,
            "7e2b3c2",
            "b40eb80",
            1,
            1,
        ),
        ("T08", "ДоступныеЯзыки", "ПоддерживаемыеЯзыки", "gp", 72, 9, "7e2b3c2", "b40eb80", 1, 1),
    ]
    for tid, sym, new, fkey, fl, fc, sha, par, efa, ee in cat2:
        rel = paths[fkey]
        full = BSL_SRC / rel
        pos = find_symbol(full, sym)
        line, col = pos if pos else (fl, fc)
        tasks.append(
            {
                "id": tid,
                "category": "CAT-2-module-local-proc",
                "commit_sha": sha,
                "parent_sha": par,
                "file_uri": _file_uri(rel),
                "line": line,
                "character": col,
                "old_name": sym,
                "new_name": new,
                "expected_files_affected": efa,
                "expected_edits": ee,
                "expected_files": [_file_uri(rel)],
                "notes": f"Module-local: {sym}.",
            }
        )

    cat3_data = [
        (
            "T09",
            "СписокРегионов",
            "ПереченьРегионов",
            "adr_p",
            1,
            9,
            "732cb0b",
            "478049a",
            3,
            4,
            ["adr_p", "adr", "adr_s"],
        ),
        (
            "T10",
            "ИсточникДанныхАдресногоКлассификатораВебСервис",
            "ЭтоВебСервисИсточник",
            "adr_p",
            1,
            9,
            "732cb0b",
            "478049a",
            2,
            3,
            ["adr_p", "adr"],
        ),
        (
            "T11",
            "ПеревестиТексты",
            "ПеревестиМассивТекстов",
            "gp",
            21,
            9,
            "478049a",
            "7e2b3c2",
            2,
            2,
            ["gp", "gp_c"],
        ),
        (
            "T12",
            "НастройкиАвторизации",
            "ПараметрыАвторизации",
            "gp",
            137,
            9,
            "478049a",
            "7e2b3c2",
            2,
            2,
            ["gp", "gp_p"],
        ),
    ]
    for tid, sym, new, fkey, fl, fc, sha, par, efa, ee, efkeys in cat3_data:
        rel = paths[fkey]
        full = BSL_SRC / rel
        pos = find_symbol(full, sym)
        line, col = pos if pos else (fl, fc)
        expected = [_file_uri(paths[k]) for k in efkeys]
        tasks.append(
            {
                "id": tid,
                "category": "CAT-3-cross-file-export",
                "commit_sha": sha,
                "parent_sha": par,
                "file_uri": _file_uri(rel),
                "line": line,
                "character": col,
                "old_name": sym,
                "new_name": new,
                "expected_files_affected": efa,
                "expected_edits": ee,
                "expected_files": expected,
                "notes": f"Cross-file export: {sym}.",
            }
        )

    cat4_data = [
        (
            "T13",
            "ПриСозданииНаСервере",
            "ПриИнициализацииНаСервере",
            "f1",
            12,
            11,
            "40e7357",
            "0454f9e",
        ),
        (
            "T14",
            "ПриСозданииНаСервере",
            "ПриФормированииНаСервере",
            "f2",
            12,
            11,
            "40e7357",
            "0454f9e",
        ),
        ("T15", "ПриОткрытии", "ПослеЗагрузки", "f1", 27, 11, "40e7357", "0454f9e"),
        ("T16", "ПриОткрытии", "НаСтарте", "f3", 26, 11, "649b105", "f9a701e"),
    ]
    for tid, sym, new, fkey, fl, fc, sha, par in cat4_data:
        rel = paths[fkey]
        full = BSL_SRC / rel
        pos = find_symbol(full, sym)
        line, col = pos if pos else (fl, fc)
        xml_rel = _form_xml_path(rel)
        tasks.append(
            {
                "id": tid,
                "category": "CAT-4-form-handler",
                "commit_sha": sha,
                "parent_sha": par,
                "file_uri": _file_uri(rel),
                "line": line,
                "character": col,
                "old_name": sym,
                "new_name": new,
                "expected_files_affected": 2,
                "expected_edits": 2,
                "expected_files": [_file_uri(rel), _file_uri(xml_rel)],
                "notes": f"Form handler: {sym}.",
            }
        )

    cat5 = [
        ("T17", "Выполнить", "Исполнить", "adm", 1060, 40, "5f520bb", "5eb22fd"),
        ("T18", "ИсточникДанных", "ПровайдерДанных", "adr", 146, 6, "018d763", "7a8f0b8"),
        ("T19", "Разрешения", "ПраваДоступа", "gp", 219, 9, "8cf1e71", "695b982"),
        ("T20", "НастройкаВыполнена", "КонфигурацияГотова", "gp", 177, 9, "8cf1e71", "695b982"),
    ]
    for tid, sym, new, fkey, fl, fc, sha, par in cat5:
        rel = paths[fkey]
        full = BSL_SRC / rel
        pos = find_symbol(full, sym)
        line, col = pos if pos else (fl, fc)
        tasks.append(
            {
                "id": tid,
                "category": "CAT-5-edge-case",
                "commit_sha": sha,
                "parent_sha": par,
                "file_uri": _file_uri(rel),
                "line": line,
                "character": col,
                "old_name": sym,
                "new_name": new,
                "expected_files_affected": 0,
                "expected_edits": 0,
                "expected_files": [],
                "notes": f"Edge case: {sym}.",
            }
        )

    return tasks


def _build_auto_tasks(limit: int = 40) -> list[dict[str, Any]]:
    log = _git("log", "--diff-filter=M", "--format=%H %P", "-n", str(limit), "--", "*.bsl")
    re_old = re.compile(_RE_OLD)
    re_new = re.compile(_RE_NEW)
    re_file = re.compile(r"^\+\+\+ b/(.+\.bsl)$")
    tasks: list[dict[str, Any]] = []
    task_id = 0

    for line in log.strip().splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        sha, parent = parts[0], parts[1]
        diff = _git("diff", "-U0", parent, sha, "--", "*.bsl")
        if not diff:
            continue

        current_file: str | None = None
        for dl in diff.splitlines():
            fm = re_file.match(dl)
            if fm:
                current_file = fm.group(1)
                break

        old_names: list[str] = []
        new_names: list[str] = []
        dlines = diff.splitlines()
        i = 0
        while i < len(dlines):
            om = re_old.match(dlines[i])
            if om and i + 1 < len(dlines):
                nm = re_new.match(dlines[i + 1])
                if nm:
                    old_names.append(om.group(1))
                    new_names.append(nm.group(1))
                    i += 2
                    continue
            i += 1

        if current_file and old_names and new_names:
            for old, new in zip(old_names, new_names):
                task_id += 1
                tasks.append(
                    {
                        "id": f"A{task_id:03d}",
                        "category": "auto-detected",
                        "commit_sha": sha[:7],
                        "parent_sha": parent[:7],
                        "file_uri": current_file,
                        "line": 0,
                        "character": 0,
                        "old_name": old,
                        "new_name": new,
                        "expected_files_affected": -1,
                        "expected_edits": -1,
                        "expected_files": [],
                        "notes": f"Auto: {old} -> {new}.",
                    }
                )

    return tasks


def main() -> None:
    parser = argparse.ArgumentParser(description="Build benchmark tasks for BSL rename refactoring")
    parser.add_argument("--auto", action="store_true", help="Scan git history for rename commits")
    parser.add_argument("--write", action="store_true", help="Write output to file")
    parser.add_argument("--limit", type=int, default=40, help="Max commits (auto mode)")
    args = parser.parse_args()

    if args.auto:
        tasks = _build_auto_tasks(args.limit)
        output_name = "tasks-auto.json"
    else:
        tasks = _build_curated_tasks()
        output_name = "tasks.json"

    data = {
        "version": 2,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "source_repo": str(REPO_ROOT),
        "tasks": tasks,
    }

    output_str = json.dumps(data, indent=2, ensure_ascii=False)

    if args.write:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = OUTPUT_DIR / output_name
        out_path.write_text(output_str, encoding="utf-8")
        print(f"Wrote {len(tasks)} tasks to {out_path}", file=sys.stderr)
    else:
        print(output_str)


if __name__ == "__main__":
    main()
