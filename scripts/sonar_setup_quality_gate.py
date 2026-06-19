#!/usr/bin/env python3
"""Создать/применить BSL quality gate «1C BSL Way» на SonarQube (ADR-021, G18).

Clean-as-You-Code: условия ТОЛЬКО на new-code → legacy-долг (на 2026-06-15 ~29k issues
на конфиге) grandfathered, гейт блокирует лишь то, что PR ДОБАВЛЯЕТ. Идемпотентно:
повторный запуск переиспользует gate, не дублирует условия.

Воспроизводимость (config-as-code): repo-tracked — любой SonarQube-инстанс восстановим
запуском. Применён+verified на live CB 26.6 (2026-06-15).

Использование:
    python scripts/sonar_setup_quality_gate.py \
        [--host http://localhost:9000] [--project upravlenie-transportom-plk] \
        [--token $SONAR_TOKEN] [--set-default]

Auth: --token / env SONAR_TOKEN (Basic user=token), иначе admin:admin (локальная разработка).
stdlib-only (urllib) — без зависимостей, безопасно гонять из CI.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

GATE_NAME = "1C BSL Way"

# Clean-as-You-Code: метрика, оператор, error-порог. Всё — new_* (только новый код).
# rating 1=A,2=B,3=C,4=D,5=E; op GT error=1 → «хуже A проваливает».
CONDITIONS = [
    ("new_reliability_rating", "GT", "1"),  # нет новых bugs (рейтинг надёжности = A)
    ("new_security_rating", "GT", "1"),  # нет новых vulnerabilities (рейтинг безопасности = A)
    ("new_security_hotspots_reviewed", "LT", "100"),  # 100% новых hotspots отревьюено
    ("new_maintainability_rating", "GT", "1"),  # нет новых code-smell-долгов выше A
    ("new_duplicated_lines_density", "GT", "3"),  # дубли в новом коде ≤ 3%
    # ОТЛОЖЕНО до Coverage41C (ADR-020 BLOCKED): ("new_coverage", "LT", "60"),
]

# Метрики, которые CB-шаблон CAYC добавляет сам, но мы НЕ хотим до разблокировки
# источника данных (нет покрытия без Coverage41C → new_coverage иначе ложно-блокирует).
DEFERRED_METRICS = {"new_coverage"}


def _auth_header(token: str | None) -> str:
    if token:
        raw = f"{token}:".encode()  # SonarQube: токен как Basic-user, пустой пароль
    else:
        raw = b"admin:admin"
    return "Basic " + base64.b64encode(raw).decode()


def _call(host: str, path: str, auth: str, params: dict | None = None, method: str = "POST"):
    url = host.rstrip("/") + path
    data = None
    if params:
        if method == "GET":
            url += "?" + urllib.parse.urlencode(params)
        else:
            data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", auth)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read().decode("utf-8")
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            return e.code, json.loads(body)
        except ValueError:
            return e.code, {"_raw": body[:200]}
    except urllib.error.URLError as e:
        return 0, {"_error": str(e.reason)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Setup 1C BSL quality gate on SonarQube")
    ap.add_argument("--host", default=os.environ.get("SONAR_HOST_URL", "http://localhost:9000"))
    ap.add_argument("--project", default="upravlenie-transportom-plk")
    ap.add_argument("--token", default=os.environ.get("SONAR_TOKEN"))
    ap.add_argument("--set-default", action="store_true", help="сделать gate дефолтным")
    args = ap.parse_args(argv)
    auth = _auth_header(args.token)

    # 0. health
    st, _ = _call(args.host, "/api/system/status", auth, method="GET")
    if st != 200:
        print(f"[FAIL] SonarQube недоступен на {args.host} (status={st}). Сервер поднят?")
        return 1

    # 1. gate (идемпотентно)
    st, lst = _call(args.host, "/api/qualitygates/list", auth, method="GET")
    existing = {g["name"] for g in lst.get("qualitygates", [])} if st == 200 else set()
    if GATE_NAME in existing:
        print(f"[ok] gate «{GATE_NAME}» уже есть")
    else:
        st, r = _call(args.host, "/api/qualitygates/create", auth, {"name": GATE_NAME})
        print(f"[{'ok' if st in (200, 201) else 'FAIL'}] create gate «{GATE_NAME}» (status={st})")
        if st not in (200, 201):
            return 1

    # 2. условия (skip уже существующие по метрике)
    st, show = _call(args.host, "/api/qualitygates/show", auth, {"name": GATE_NAME}, method="GET")
    have = {c["metric"] for c in show.get("conditions", [])} if st == 200 else set()
    for metric, op, err in CONDITIONS:
        if metric in have:
            print(f"  [skip] условие {metric} уже есть")
            continue
        st, r = _call(
            args.host,
            "/api/qualitygates/create_condition",
            auth,
            {"gateName": GATE_NAME, "metric": metric, "op": op, "error": err},
        )
        print(
            f"  [{'ok' if st in (200, 201) else 'WARN'}] +условие {metric} {op} {err} (status={st})"
        )

    # 2b. убрать deferred-условия (CB CAYC-шаблон сам добавляет new_coverage и т.п.)
    st, show = _call(args.host, "/api/qualitygates/show", auth, {"name": GATE_NAME}, method="GET")
    for c in show.get("conditions", []) if st == 200 else []:
        if c.get("metric") in DEFERRED_METRICS:
            cid = c.get("id")
            dst, _ = _call(args.host, "/api/qualitygates/delete_condition", auth, {"id": cid})
            print(
                f"  [{'ok' if dst in (200, 204) else 'WARN'}] -условие {c['metric']} (deferred, status={dst})"
            )

    # 3. проект (создать при отсутствии) + назначить gate
    _call(
        args.host, "/api/projects/create", auth, {"project": args.project, "name": args.project}
    )  # best-effort (уже есть → 400)
    st, _ = _call(
        args.host,
        "/api/qualitygates/select",
        auth,
        {"gateName": GATE_NAME, "projectKey": args.project},
    )
    print(f"[{'ok' if st in (200, 204) else 'WARN'}] gate -> проект {args.project} (status={st})")

    # 4. new-code = previous_version (Clean-as-You-Code baseline)
    st, _ = _call(
        args.host,
        "/api/new_code_periods/set",
        auth,
        {"type": "previous_version", "project": args.project},
    )
    print(
        f"[{'ok' if st in (200, 204) else 'WARN'}] new-code period = previous_version (status={st})"
    )

    # 5. опц. default
    if args.set_default:
        st, _ = _call(args.host, "/api/qualitygates/set_as_default", auth, {"name": GATE_NAME})
        print(f"[{'ok' if st in (200, 204) else 'WARN'}] set_as_default (status={st})")

    print(
        f"\n[DONE] «{GATE_NAME}» применён к {args.project}. Dashboard: {args.host}/dashboard?id={args.project}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
