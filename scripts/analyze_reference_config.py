#!/usr/bin/env python3
"""Унифицированный offline-анализ эталонного 1С-конфига (Designer-дамп).

Покрывает слои 43.7: (2) инвентарь метаданных + (1-lite) BSL-метрики — без инфобазы/EDT/Java,
работает прямо на Designer-выгрузке (Configuration.xml + папки типов объектов + Ext/*.bsl).
Слой 3a (call-graph) — отдельно через scripts/build_call_graph.py --project <root> --db <db>.

Usage: python scripts/analyze_reference_config.py --root external/1c-reference-src/erp --name erp
Выход: data/reports/reference/<name>-inventory.md (+ .json).
"""

import argparse
import json
import os
import re
import time

# Топ-уровневые папки Designer-дампа = типы метаданных (объект = подпапка).
META_DIRS = [
    "Catalogs",
    "Documents",
    "DocumentJournals",
    "Enums",
    "Reports",
    "DataProcessors",
    "ChartsOfCharacteristicTypes",
    "ChartsOfAccounts",
    "ChartsOfCalculationTypes",
    "InformationRegisters",
    "AccumulationRegisters",
    "AccountingRegisters",
    "CalculationRegisters",
    "BusinessProcesses",
    "Tasks",
    "CommonModules",
    "CommonForms",
    "CommonTemplates",
    "CommonCommands",
    "CommonAttributes",
    "CommonPictures",
    "Constants",
    "Subsystems",
    "Roles",
    "ExchangePlans",
    "FilterCriteria",
    "SettingsStorages",
    "FunctionalOptions",
    "DefinedTypes",
    "WebServices",
    "HTTPServices",
    "Bots",
    "IntegrationServices",
    "ExternalDataSources",
    "StyleItems",
    "EventSubscriptions",
    "ScheduledJobs",
]

DEF_RE = re.compile(r"(?im)^\s*(?:Процедура|Функция|Procedure|Function)\b")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--out-dir", default="data/reports/reference")
    a = ap.parse_args()
    root = a.root
    t0 = time.time()

    # версия/имя из Configuration.xml (regex по началу — файл крупный)
    ver, conf_name = "?", "?"
    cfg = os.path.join(root, "Configuration.xml")
    if os.path.exists(cfg):
        head = open(cfg, encoding="utf-8-sig", errors="replace").read(300000)
        mv = re.search(r"<Version>([^<]+)</Version>", head)
        mn = re.search(r"<Name>([^<]+)</Name>", head)
        ver = mv.group(1) if mv else "?"
        conf_name = mn.group(1) if mn else "?"

    # инвентарь: объектов на тип = число подпапок верхнего уровня типа
    inventory = {}
    for d in META_DIRS:
        p = os.path.join(root, d)
        if os.path.isdir(p):
            inventory[d] = sum(1 for e in os.scandir(p) if e.is_dir())

    # один проход os.walk: BSL-метрики + формы + макеты
    bsl_files = bsl_loc = bsl_defs = forms = templates = 0
    largest = []  # (loc, relpath)
    for dirpath, dirs, files in os.walk(root):
        if os.sep + ".git" in dirpath:
            dirs[:] = [x for x in dirs if x != ".git"]
            continue
        base = os.path.basename(dirpath)
        if base == "Forms":
            forms += sum(1 for e in os.scandir(dirpath) if e.is_dir())
        if base in ("Templates", "CommonTemplates"):
            templates += sum(1 for e in os.scandir(dirpath) if e.is_dir())
        for f in files:
            if f.lower().endswith(".bsl"):
                bsl_files += 1
                fp = os.path.join(dirpath, f)
                try:
                    txt = open(fp, encoding="utf-8-sig", errors="replace").read()
                except OSError:
                    continue
                loc = txt.count("\n") + 1
                bsl_loc += loc
                bsl_defs += len(DEF_RE.findall(txt))
                largest.append((loc, os.path.relpath(fp, root).replace("\\", "/")))
    largest.sort(reverse=True)
    largest = largest[:10]

    total_objects = sum(inventory.values())
    result = {
        "name": a.name,
        "root": root,
        "configuration_name": conf_name,
        "version": ver,
        "format": "designer-dump",
        "totals": {
            "metadata_objects": total_objects,
            "bsl_modules": bsl_files,
            "bsl_loc": bsl_loc,
            "bsl_proc_func": bsl_defs,
            "forms": forms,
            "templates": templates,
            "avg_loc_per_module": round(bsl_loc / bsl_files, 1) if bsl_files else 0,
        },
        "inventory": dict(sorted(inventory.items(), key=lambda kv: -kv[1])),
        "largest_modules": [{"loc": loc, "path": p} for loc, p in largest],
        "elapsed_s": round(time.time() - t0, 1),
    }

    os.makedirs(a.out_dir, exist_ok=True)
    json.dump(
        result,
        open(os.path.join(a.out_dir, f"{a.name}-inventory.json"), "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2,
    )

    L = [
        f"# Reference-конфиг {a.name} — инвентарь + BSL-метрики (слои 2 + 1-lite, offline)",
        "",
        f"Конфигурация: **{conf_name}** v**{ver}** · формат: Designer-дамп · корень: `{root}`",
        f"Генерация: {time.strftime('%Y-%m-%d %H:%M')} · проход {result['elapsed_s']}s",
        "",
        "## Итоги",
        "",
        f"- Объектов метаданных: **{total_objects}**",
        f"- BSL-модулей (.bsl): **{bsl_files}** · LOC: **{bsl_loc:,}** · процедур/функций: **{bsl_defs:,}**",
        f"- Средний размер модуля: **{result['totals']['avg_loc_per_module']} LOC**",
        f"- Форм: **{forms}** · макетов (Templates): **{templates}**",
        "",
        "## Инвентарь по типам метаданных (объектов)",
        "",
        "| Тип | Объектов |",
        "|---|--:|",
    ]
    for k, v in result["inventory"].items():
        L.append(f"| {k} | {v} |")
    L += ["", "## Топ-10 крупнейших BSL-модулей (LOC)", "", "| LOC | модуль |", "|--:|---|"]
    for it in result["largest_modules"]:
        L.append(f"| {it['loc']} | `{it['path']}` |")
    open(os.path.join(a.out_dir, f"{a.name}-inventory.md"), "w", encoding="utf-8").write(
        "\n".join(L)
    )

    print(
        f"[{a.name}] objects={total_objects} bsl={bsl_files} loc={bsl_loc} defs={bsl_defs} "
        f"forms={forms} templates={templates} in {result['elapsed_s']}s"
    )
    print(f"  -> {a.out_dir}/{a.name}-inventory.md")


if __name__ == "__main__":
    main()
