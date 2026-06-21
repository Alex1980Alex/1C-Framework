#!/usr/bin/env python3
"""Pull SonarQube issues for the 1C remediation stage (gl. 43.7).

Выгружает незакрытые issues проекта, группирует по severity/правилу/файлу и
строит приоритизированный worklist (severity -> файл -> строка) для подачи в
1С-конвейер (/implement-1c-task / правки BSL через EDT-MCP). Zero-dep (urllib).

Auth: SONAR_TOKEN (env/--token) либо basic admin:admin (локальный CB).
Примеры:
  python scripts/sonar_issues_pull.py                         # BLOCKER+CRITICAL bsl
  python scripts/sonar_issues_pull.py --types BUG,VULNERABILITY
  python scripts/sonar_issues_pull.py --path-contains configuration   # фокус кастомного кода
"""

import argparse
import base64
import collections
import datetime
import json
import os
import urllib.parse
import urllib.request

SEV_ORDER = {"BLOCKER": 0, "CRITICAL": 1, "MAJOR": 2, "MINOR": 3, "INFO": 4}


def api(host, path, token=None):
    req = urllib.request.Request(host.rstrip("/") + path)
    cred = f"{token}:" if token else "admin:admin"
    req.add_header("Authorization", "Basic " + base64.b64encode(cred.encode()).decode())
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def pull(host, project, sev, typ, lang, max_issues, token):
    base = f"/api/issues/search?componentKeys={urllib.parse.quote(project)}&resolved=false&ps=500"
    if sev:
        base += "&severities=" + ",".join(sev)
    if typ:
        base += "&types=" + ",".join(typ)
    if lang:
        base += "&languages=" + ",".join(lang)
    issues, page = [], 1
    while True:
        data = api(host, base + f"&p={page}", token)
        batch = data.get("issues", [])
        issues.extend(batch)
        total = data.get("total", 0)
        if not batch or page * 500 >= min(total, 10000) or len(issues) >= max_issues:
            break
        page += 1
    return issues[:max_issues], total


def short(comp):
    return comp.split(":", 1)[1] if ":" in comp else comp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("SONAR_HOST_URL", "http://localhost:9000"))
    ap.add_argument("--project", default="upravlenie-transportom-plk")
    ap.add_argument("--severities", default="BLOCKER,CRITICAL")
    ap.add_argument("--types", default="")
    ap.add_argument("--languages", default="bsl")
    ap.add_argument("--path-contains", default="", help="фильтр по пути компонента (фокус кастома)")
    ap.add_argument("--max", type=int, default=2000)
    ap.add_argument("--out-dir", default="data/reports/sonar")
    ap.add_argument("--token", default=os.environ.get("SONAR_TOKEN"))
    a = ap.parse_args()
    sev = [s for s in a.severities.split(",") if s]
    typ = [t for t in a.types.split(",") if t]
    lang = [x for x in a.languages.split(",") if x]
    issues, total = pull(a.host, a.project, sev, typ, lang, a.max, a.token)
    for i in issues:
        i["_file"] = short(i.get("component", ""))
    if a.path_contains:
        issues = [i for i in issues if a.path_contains.lower() in i["_file"].lower()]
    by_rule = collections.Counter(i.get("rule") for i in issues)
    by_file = collections.Counter(i["_file"] for i in issues)
    by_sev = collections.Counter(i.get("severity") for i in issues)
    issues.sort(key=lambda i: (SEV_ORDER.get(i.get("severity"), 9), i["_file"], i.get("line", 0)))
    os.makedirs(a.out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(a.out_dir, f"sonar-issues-{ts}")
    json.dump(
        {
            "project": a.project,
            "total_matching": total,
            "pulled": len(issues),
            "filters": {
                "severities": sev,
                "types": typ,
                "languages": lang,
                "path_contains": a.path_contains,
            },
            "issues": [
                {
                    "rule": i.get("rule"),
                    "severity": i.get("severity"),
                    "type": i.get("type"),
                    "file": i["_file"],
                    "line": i.get("line"),
                    "message": i.get("message"),
                }
                for i in issues
            ],
        },
        open(out + ".json", "w", encoding="utf-8"),
        ensure_ascii=False,
        indent=2,
    )
    L = [
        f"# SonarQube remediation worklist — {a.project}",
        "",
        f"Генерация: {ts} · severities={sev} types={typ or 'all'} lang={lang} path~{a.path_contains or 'all'}",
        f"Совпало (resolved=false): **{total}** · выгружено: **{len(issues)}** (cap --max={a.max})",
        "",
        "## По severity",
        "",
    ]
    for s in sorted(by_sev, key=lambda x: SEV_ORDER.get(x, 9)):
        L.append(f"- {s}: {by_sev[s]}")
    L += ["", "## Top-15 правил", "", "| правило | кол-во |", "|---|--:|"]
    for r, c in by_rule.most_common(15):
        L.append(f"| {r} | {c} |")
    L += ["", "## Top-15 файлов (батчи для фикса)", "", "| файл | issues |", "|---|--:|"]
    for f, c in by_file.most_common(15):
        L.append(f"| {f} | {c} |")
    L += ["", "## Worklist (severity → файл → строка), первые 200", ""]
    cur = None
    for i in issues[:200]:
        if i["_file"] != cur:
            cur = i["_file"]
            L.append(f"\n### {i.get('severity')} · {cur}")
        L.append(f"- L{i.get('line', '?')} `{i.get('rule')}` — {i.get('message', '')}")
    open(out + ".md", "w", encoding="utf-8").write("\n".join(L))
    print(f"pulled {len(issues)}/{total} -> {out}.md / .json")
    print("severity:", dict(by_sev))
    print("top rules:", by_rule.most_common(5))


if __name__ == "__main__":
    main()
