#!/usr/bin/env python3
"""Pull SonarQube issues for the 1C remediation stage (gl. 43.7 / ADR-033/034).

Выгружает незакрытые issues проекта, группирует по severity/правилу/файлу/классу
ремедиации и строит приоритизированный worklist для подачи в 1С-конвейер
(/fix-sonar-task → /analyze-1c-task → /implement-1c-task). Zero-dep (urllib).

Форматы вывода (--format):
  worklist  — MD + JSON (как раньше)
  sarif     — SARIF 2.1.0 (универсальный контракт находок, R4 ADR-034)
  both      — всё (дефолт)

R5 (ADR-034): каждый issue помечается remediation_class:
  deterministic — механический фикс (форматирование) → детерминированный трансформер, НЕ пайплайн
  judgment      — требует домена/анализа → обязательный пайплайн (/fix-sonar-task)

Auth: SONAR_TOKEN (env/--token) либо basic admin:admin (локальный CB).
Примеры:
  python scripts/sonar_issues_pull.py                          # BLOCKER+CRITICAL bsl
  python scripts/sonar_issues_pull.py --types BUG,VULNERABILITY
  python scripts/sonar_issues_pull.py --format sarif           # только SARIF
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

# R4 (ADR-034): severity -> уровень SARIF 2.1.0
SARIF_LEVEL = {
    "BLOCKER": "error",
    "CRITICAL": "error",
    "MAJOR": "warning",
    "MINOR": "note",
    "INFO": "note",
}

# R5 (ADR-034): чисто механические (форматирование) правила → класс "deterministic".
# Всё остальное → "judgment" (консервативно: не авто-фиксить неизвестное вне пайплайна).
DETERMINISTIC_RULES = {
    "LineLength",
    "MissingSpace",
    "ConsecutiveEmptyLines",
    "SemicolonPresence",
    "ExtraCommas",
    "SpaceAtStartComment",
    "IncorrectLineBreak",
    "OneStatementPerLine",
    "CanonicalSpellingKeywords",
    "YoLetterUsage",
    "NonStandardRegion",
    "EmptyRegion",
    "CodeOutOfRegion",
    "EmptyStatement",
}


def remediation_class(rule):
    short_rule = (rule or "").split(":")[-1]
    return "deterministic" if short_rule in DETERMINISTIC_RULES else "judgment"


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


def build_sarif(issues, project):
    """R4: SARIF 2.1.0 — универсальный контракт находок (interop с любым сканером/дашбордом)."""
    rules = sorted({i.get("rule") for i in issues if i.get("rule")})
    return {
        "version": "2.1.0",
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "bsl-language-server (via SonarQube)",
                        "informationUri": "https://1c-syntax.github.io/sonar-bsl-plugin-community/",
                        "rules": [{"id": r} for r in rules],
                    }
                },
                "properties": {"project": project},
                "results": [
                    {
                        "ruleId": i.get("rule"),
                        "level": SARIF_LEVEL.get(i.get("severity"), "warning"),
                        "message": {"text": i.get("message") or ""},
                        "properties": {
                            "severity": i.get("severity"),
                            "type": i.get("type"),
                            "remediationClass": i.get("_class"),
                        },
                        "locations": [
                            {
                                "physicalLocation": {
                                    "artifactLocation": {"uri": i["_file"]},
                                    "region": {"startLine": i.get("line") or 1},
                                }
                            }
                        ],
                    }
                    for i in issues
                ],
            }
        ],
    }


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
    ap.add_argument(
        "--format",
        default="both",
        choices=["worklist", "sarif", "both"],
        help="worklist=MD+JSON · sarif=SARIF 2.1.0 · both (дефолт)",
    )
    a = ap.parse_args()
    sev = [s for s in a.severities.split(",") if s]
    typ = [t for t in a.types.split(",") if t]
    lang = [x for x in a.languages.split(",") if x]
    issues, total = pull(a.host, a.project, sev, typ, lang, a.max, a.token)
    for i in issues:
        i["_file"] = short(i.get("component", ""))
        i["_class"] = remediation_class(i.get("rule"))  # R5
    if a.path_contains:
        issues = [i for i in issues if a.path_contains.lower() in i["_file"].lower()]
    by_rule = collections.Counter(i.get("rule") for i in issues)
    by_file = collections.Counter(i["_file"] for i in issues)
    by_sev = collections.Counter(i.get("severity") for i in issues)
    by_class = collections.Counter(i["_class"] for i in issues)  # R5
    issues.sort(key=lambda i: (SEV_ORDER.get(i.get("severity"), 9), i["_file"], i.get("line", 0)))
    os.makedirs(a.out_dir, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(a.out_dir, f"sonar-issues-{ts}")
    written = []

    if a.format in ("worklist", "both"):
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
                "by_remediation_class": dict(by_class),
                "issues": [
                    {
                        "rule": i.get("rule"),
                        "severity": i.get("severity"),
                        "type": i.get("type"),
                        "remediation_class": i["_class"],
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
            "## По классу ремедиации (R5)",
            "",
            f"- deterministic (механический фикс, НЕ пайплайн): {by_class.get('deterministic', 0)}",
            f"- judgment (домен → обязательный пайплайн /fix-sonar-task): {by_class.get('judgment', 0)}",
            "",
            "## По severity",
            "",
        ]
        for s in sorted(by_sev, key=lambda x: SEV_ORDER.get(x, 9)):
            L.append(f"- {s}: {by_sev[s]}")
        L += ["", "## Top-15 правил", "", "| правило | класс | кол-во |", "|---|---|--:|"]
        for r, c in by_rule.most_common(15):
            L.append(f"| {r} | {remediation_class(r)} | {c} |")
        L += ["", "## Top-15 файлов (батчи для фикса)", "", "| файл | issues |", "|---|--:|"]
        for f, c in by_file.most_common(15):
            L.append(f"| {f} | {c} |")
        L += ["", "## Worklist (severity → файл → строка), первые 200", ""]
        cur = None
        for i in issues[:200]:
            if i["_file"] != cur:
                cur = i["_file"]
                L.append(f"\n### {i.get('severity')} · {cur}")
            L.append(
                f"- L{i.get('line', '?')} `{i.get('rule')}` [{i['_class']}] — {i.get('message', '')}"
            )
        open(out + ".md", "w", encoding="utf-8").write("\n".join(L))
        written += [out + ".md", out + ".json"]

    if a.format in ("sarif", "both"):
        json.dump(
            build_sarif(issues, a.project),
            open(out + ".sarif", "w", encoding="utf-8"),
            ensure_ascii=False,
            indent=2,
        )
        written.append(out + ".sarif")

    print(f"pulled {len(issues)}/{total} -> {', '.join(os.path.basename(w) for w in written)}")
    print("severity:", dict(by_sev))
    print("remediation_class:", dict(by_class))
    print("top rules:", by_rule.most_common(5))


if __name__ == "__main__":
    main()
