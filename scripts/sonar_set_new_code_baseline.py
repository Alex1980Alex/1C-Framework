#!/usr/bin/env python3
"""Пин new-code baseline проекта = конкретный анализ (SPECIFIC_ANALYSIS, branch-level).

P2.2 roadmap 260706 (A4). Чинит ВЫРОЖДЕННЫЙ server new-code baseline: при первом скане
проекта все легаси-issue получают creationDate дня скана → «новых» ≈ total → QG=ERROR-шум
(soft). Скрипт пинит период «держим чисто с этого анализа» на ВЕТКЕ.

⚠ Тонкости сервера (проверено live, [[reference-sonar-changed-lines-gate]]):
  - `SPECIFIC_ANALYSIS` принимается ТОЛЬКО branch-level: `POST api/new_code_periods/set`
    с `branch=<branch>`. Project-level set (без branch) = тихий HTTP 204 БЕЗ эффекта →
    проверять результат через `api/new_code_periods/list` (не `/show`).
  - `value` = ПОЛНЫЙ analysisId (UUID). Усечённый → 404.
  - `sonar_setup_quality_gate.py` (шаг [1/3] run-sonar-analysis.ps1) ставит `previous_version`
    project-level — это может СБРОСИТЬ branch-пин. Порядок: сначала скан + QG-setup, ПОТОМ
    этот скрипт (пин доживает до следующего анализа — период применяется CE при след. скане).

Использование:
    python scripts/sonar_set_new_code_baseline.py --show                    # текущие периоды (list)
    python scripts/sonar_set_new_code_baseline.py --analysis-id <UUID>       # пин на конкретный анализ
    python scripts/sonar_set_new_code_baseline.py --to-latest-before 2026-07-03T00:00:00+0000

zero-dep (urllib). Auth: SONAR_TOKEN или basic admin:admin. Exit: 0 ок, 1 не вышло, 2 недоступен.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime

# .env loader (SONAR_TOKEN/SONAR_HOST_URL); env > .env.
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from _dotenv import load_dotenv as _ld

    _ld()
except Exception:
    pass

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

_UUID_RE = re.compile(r"^[0-9a-fA-F-]{20,}$")  # analysisId — длинный UUID-подобный


def _auth(token):
    cred = f"{token}:" if token else "admin:admin"
    return "Basic " + base64.b64encode(cred.encode()).decode()


def _get(host, path, token, timeout=30):
    req = urllib.request.Request(host.rstrip("/") + path)
    req.add_header("Authorization", _auth(token))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _post(host, path, token, data, timeout=30):
    body = urllib.parse.urlencode(data).encode()
    req = urllib.request.Request(host.rstrip("/") + path, data=body, method="POST")
    req.add_header("Authorization", _auth(token))
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")


def reachable(host, token) -> bool:
    try:
        return _get(host, "/api/system/status", token, timeout=5).get("status") == "UP"
    except Exception:
        return False


def _parse_dt(s):
    try:
        return datetime.fromisoformat(str(s or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def pick_latest_before(analyses: list[dict], before) -> str | None:
    """analysisId самого свежего анализа СТРОГО раньше `before` (datetime). Pure → тестируемо.

    analyses — элементы api/project_analyses/search (каждый {key, date}). None если нет."""
    best_key, best_dt = None, None
    for a in analyses:
        d = _parse_dt(a.get("date"))
        if d is None or (before is not None and d >= before):
            continue
        if best_dt is None or d > best_dt:
            best_dt, best_key = d, a.get("key")
    return best_key


def list_periods(host, project, token) -> list[dict]:
    d = _get(host, f"/api/new_code_periods/list?project={urllib.parse.quote(project)}", token)
    return d.get("newCodePeriods", [])


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Пин new-code baseline (SPECIFIC_ANALYSIS, branch-level)"
    )
    ap.add_argument("--host", default=os.environ.get("SONAR_HOST_URL", "http://localhost:9000"))
    ap.add_argument("--project", default="upravlenie-transportom-plk")
    ap.add_argument("--branch", default="main")
    ap.add_argument("--token", default=os.environ.get("SONAR_TOKEN"))
    ap.add_argument(
        "--analysis-id", dest="analysis_id", default=None, help="полный analysisId (UUID)"
    )
    ap.add_argument(
        "--to-latest-before",
        dest="before",
        default=None,
        help="ISO-дата: пин на самый свежий анализ РАНЬШЕ неё (напр. 2026-07-03T00:00:00+0000)",
    )
    ap.add_argument("--show", action="store_true", help="показать текущие периоды (list) и выйти")
    a = ap.parse_args(argv)

    if not reachable(a.host, a.token):
        print(f"SonarQube недоступен ({a.host})")
        return 2

    if a.show or not (a.analysis_id or a.before):
        try:
            periods = list_periods(a.host, a.project, a.token)
        except Exception as exc:
            print(f"ошибка list: {str(exc)[:100]}")
            return 2
        print(f"new_code_periods проекта {a.project}:")
        for p in periods:
            br = p.get("branchKey", "<project-level>")
            print(f"  branch={br}\ttype={p.get('type')}\tvalue={p.get('value')}")
        if not periods:
            print("  (пусто — наследуется настройка по умолчанию)")
        return 0

    # 1. Разрешить analysisId
    analysis_id = a.analysis_id
    if not analysis_id:
        try:
            d = _get(
                a.host,
                f"/api/project_analyses/search?project={urllib.parse.quote(a.project)}"
                f"&branch={urllib.parse.quote(a.branch)}&ps=100",
                a.token,
            )
        except Exception as exc:
            print(f"ошибка project_analyses/search: {str(exc)[:100]}")
            return 2
        before_dt = _parse_dt(a.before)
        if before_dt is None:
            print(
                f"не разобрал --to-latest-before '{a.before}' (ISO, напр. 2026-07-03T00:00:00+0000)"
            )
            return 1
        if (
            before_dt.tzinfo is None
        ):  # naive-вход → UTC (Sonar-даты aware; иначе TypeError сравнения)
            before_dt = before_dt.replace(tzinfo=UTC)
        analysis_id = pick_latest_before(d.get("analyses", []), before_dt)
        if not analysis_id:
            print(f"нет анализа раньше {a.before} на ветке {a.branch}")
            return 1
        print(f"выбран анализ {analysis_id} (самый свежий раньше {a.before})")

    if not _UUID_RE.match(analysis_id):
        print(f"⚠ analysisId '{analysis_id}' не похож на полный UUID — усечённый value → 404")

    # 2. POST set (branch-level — ОБЯЗАТЕЛЬНО, иначе тихий no-op)
    try:
        status, _ = _post(
            a.host,
            "/api/new_code_periods/set",
            a.token,
            {
                "project": a.project,
                "branch": a.branch,
                "type": "SPECIFIC_ANALYSIS",
                "value": analysis_id,
            },
        )
    except urllib.error.HTTPError as exc:
        print(f"ошибка set (HTTP {exc.code}): {exc.read().decode('utf-8', 'replace')[:120]}")
        return 1
    except Exception as exc:
        print(f"ошибка set: {str(exc)[:100]}")
        return 1
    if status not in (200, 204):
        print(f"set вернул HTTP {status} (ожидалось 204)")
        return 1

    # 3. Verify через /list (project-level set был бы тихим no-op)
    try:
        periods = list_periods(a.host, a.project, a.token)
    except Exception as exc:
        print(f"set отправлен, но list-verify упал: {str(exc)[:100]}")
        return 1
    ok = any(
        p.get("branchKey") == a.branch
        and p.get("type") == "SPECIFIC_ANALYSIS"
        and p.get("value") == analysis_id
        for p in periods
    )
    if ok:
        print(f"✓ baseline ветки {a.branch} = SPECIFIC_ANALYSIS {analysis_id}")
        print("  (период применится метриками при СЛЕДУЮЩЕМ анализе — Compute Engine)")
        return 0
    print(
        f"✗ set прошёл (HTTP {status}), но /list не подтвердил branch-пин — "
        "вероятно project-level no-op ИЛИ перезаписано previous_version. Проверь порядок "
        "(скан+QG-setup → потом пин) и что branch указан."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
