#!/usr/bin/env python3
"""Обязательный Sonar re-scan изменённого/добавленного 1С-кода — дельта-verify.

Шаг «Тестирование» для правил «изменённый/добавленный 1С-код обязательно через SonarQube»
(ADR — см. docs гл. 43). Проверяет, что КАЖДЫЙ изменённый/новый `.bsl` (осн. репо + сабмодули):
  1) проанализирован Sonar (component существует), 2) имеет 0 НОВЫХ BLOCKER/CRITICAL (Clean-as-You-Code),
  3) последний анализ Sonar СВЕЖЕЕ правок (иначе скан устарел → нужен прогон сканера).
Пишет `.claude/cache/onec-sonar-rescan-state.json` (контракт для Stop-гейта
onec-task-completion-stop). Zero-dep (urllib). Auth: SONAR_TOKEN или basic admin:admin.

Порядок в пайплайне: сначала прогнать сканер (`run-sonar-analysis.ps1`) — он заливает анализ,
потом этот скрипт — он проверяет результат дельты по затронутым файлам.

Reachability: Sonar недоступен → state `skipped:true`, exit 0 (гейт не блокирует — проверить нельзя).
Exit: 0 = pass / skipped; 1 = есть нарушения (гейт заблокирует завершение).

Примеры:
  python scripts/sonar_rescan_verify.py
  python scripts/sonar_rescan_verify.py --severities BLOCKER,CRITICAL,MAJOR
"""

import argparse
import base64
import http.client
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# Общий контракт детекта/состояния (DRY с гейтом). hooks-shared на sys.path.
sys.path.insert(0, str(PROJECT_ROOT / ".claude" / "hooks"))
from shared.sonar_rescan_state import (
    changed_bsl_paths,
    newest_mtime,
    parse_dt,
    write_state,
)

# .env loader (gitignored секреты: SONAR_TOKEN/SONAR_HOST_URL); env > .env. ADR-041 follow-up.
try:
    import os as _o
    import sys as _s

    _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
    from _dotenv import load_dotenv as _ld

    _ld()
except Exception:
    pass

# Windows-консоль = cp1251: символы ✗/⚠ роняют print → форсим UTF-8 stdout (best-effort)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def _auth(token):
    cred = f"{token}:" if token else "admin:admin"
    return "Basic " + base64.b64encode(cred.encode()).decode()


def api(host, path, token=None, timeout=30, retries=3):
    # Ретрай на ТРАНЗИЕНТНЫХ ошибках (сокет/сеть, напр. WinError 10048 «address already in use»
    # при частых запросах). HTTPError (4xx/5xx) — не транзиент: пробрасываем сразу, не маскируем
    # реальный ответ Sonar. Без ретрая транзиент давал ложное «ошибка запроса» → ложный блок гейта.
    last: Exception | None = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(host.rstrip("/") + path)
            req.add_header("Authorization", _auth(token))
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            # 5xx (напр. транзиентный 500 Sonar во время фоновой индексации свежего скана —
            # флапает на кириллических ключах компонентов) — ретраим; 4xx (404/400 и пр.) —
            # не транзиент, пробрасываем сразу (реальный ответ Sonar не маскируем).
            if e.code >= 500 and attempt < retries - 1:
                last = e
                time.sleep(0.4 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, OSError) as e:
            last = e
            time.sleep(0.4 * (attempt + 1))
    raise last if last else RuntimeError("api: retries exhausted")


def reachable(host) -> bool:
    try:
        return api(host, "/api/system/status", timeout=5).get("status") == "UP"
    except Exception:
        return False


def last_analysis_dt(host, project, token):
    try:
        d = api(
            host, f"/api/project_analyses/search?project={urllib.parse.quote(project)}&ps=1", token
        )
        an = d.get("analyses", [])
        return parse_dt(an[0].get("date")) if an else None
    except Exception:
        return None


# Per-file component_exists/blocker_critical_count (кириллический component-key → Sonar API 500,
# reference-sonar-cyrillic-component-api) заменены project-level запросами ниже: ключи файлов
# приходят в теле ответа (UTF-8) и матчатся локально по суффиксу пути — без 500.


def _paged(host, path_base, token, items_key, page_size=500, cap_pages=60):
    """Собирает все элементы пагинированного Sonar-эндпоинта (project-level).

    componentKeys/component = ASCII-ключ проекта → нет кириллического 500; ключи файлов
    приходят в теле ответа (UTF-8), фильтруем локально по суффиксу пути. ОДНО keep-alive
    соединение на все страницы (иначе десятки сокетов → WinError 10048 port exhaustion)."""
    u = urllib.parse.urlsplit(host)
    is_https = u.scheme == "https"
    conn_cls = http.client.HTTPSConnection if is_https else http.client.HTTPConnection
    conn = conn_cls(u.hostname, u.port or (443 if is_https else 80), timeout=30)
    hdr = {"Authorization": _auth(token)}
    out = []
    try:
        page = 1
        while page <= cap_pages:
            path = f"{path_base}&p={page}&ps={page_size}"
            body = None
            for attempt in range(3):
                conn.request("GET", path, headers=hdr)
                resp = conn.getresponse()
                raw = resp.read()
                if resp.status >= 500 and attempt < 2:
                    time.sleep(0.4 * (attempt + 1))
                    continue
                if resp.status >= 400:
                    raise RuntimeError(f"Sonar {resp.status} на {path[:80]}")
                body = raw
                break
            d = json.loads(body)
            items = d.get(items_key, [])
            out.extend(items)
            total = (d.get("paging") or {}).get("total", d.get("total", len(out)))
            if not items or len(out) >= total:
                break
            page += 1
    finally:
        conn.close()
    return out


def analyzed_file_keys(host, project, token) -> set[str]:
    """Ключи всех файловых компонентов проекта (project-level tree, qualifiers=FIL)."""
    base = (
        "/api/components/tree?component="
        + urllib.parse.quote(project)
        + "&qualifiers=FIL&strategy=all"
    )
    return {c["key"] for c in _paged(host, base, token, "components") if c.get("key")}


def new_code_counts(host, project, severities, token) -> dict:
    """component_key -> число NEW-code нарушений заданных severities (один project-level запрос).

    inNewCodePeriod=true → Clean-as-You-Code (легаси-issue не гейтим)."""
    base = (
        "/api/issues/search?componentKeys="
        + urllib.parse.quote(project)
        + "&resolved=false&inNewCodePeriod=true&severities="
        + ",".join(severities)
    )
    counts: dict[str, int] = {}
    for iss in _paged(host, base, token, "issues"):
        comp = iss.get("component")
        if comp:
            counts[comp] = counts.get(comp, 0) + 1
    return counts


def _match_component(rel, project, analyzed) -> str | None:
    """Ключ анализированного компонента для repo-относительного пути rel.

    Штатно (projectBaseDir = корень репо) точный `project:rel` всегда срабатывает. Суффиксный
    fallback — только для нестандартного base; при НЕОДНОЗНАЧНОСТИ (>1 кандидата, напр. общий
    хвост `.../Ext/ObjectModule.bsl`) возвращаем None (fail-closed: не выбираем наугад чужой
    файл с count=0 → не даём ложный PASS)."""
    exact = f"{project}:{rel}"
    if exact in analyzed:
        return exact
    cands = [k for k in analyzed if k.endswith(":" + rel) or k.endswith("/" + rel)]
    return cands[0] if len(cands) == 1 else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("SONAR_HOST_URL", "http://localhost:9000"))
    ap.add_argument("--project", default="upravlenie-transportom-plk")
    ap.add_argument("--severities", default="BLOCKER,CRITICAL")
    ap.add_argument("--token", default=os.environ.get("SONAR_TOKEN"))
    a = ap.parse_args()
    severities = [s for s in a.severities.split(",") if s]
    now = datetime.now()

    changed = sorted(changed_bsl_paths(PROJECT_ROOT))
    if not changed:
        write_state(
            PROJECT_ROOT,
            {
                "ts": now.isoformat(),
                "host": a.host,
                "pass": True,
                "skipped": False,
                "files_verified": [],
                "fail_files": [],
                "scan_stale": False,
                "last_analysis": None,
            },
        )
        print("sonar-rescan: нет изменённых .bsl — нечего проверять (pass)")
        return 0

    if not reachable(a.host):
        write_state(
            PROJECT_ROOT,
            {
                "ts": now.isoformat(),
                "host": a.host,
                "pass": False,
                "skipped": True,
                "files_verified": [],
                "fail_files": [],
                "scan_stale": False,
                "last_analysis": None,
            },
        )
        print(f"sonar-rescan: SonarQube недоступен ({a.host}) — skip (гейт не блокирует)")
        return 0

    last_an = last_analysis_dt(a.host, a.project, a.token)
    nm = newest_mtime(PROJECT_ROOT, changed)
    scan_stale = bool(last_an is None or (nm and last_an.timestamp() < nm))

    # Project-level запросы (обход кириллического component-key 500 в per-file API,
    # reference-sonar-cyrillic-component-api): один запрос списка файловых компонентов +
    # один запрос new-code нарушений проекта, матчинг по суффиксу пути локально.
    try:
        analyzed = analyzed_file_keys(a.host, a.project, a.token)
        counts = new_code_counts(a.host, a.project, severities, a.token)
    except Exception as exc:
        # API-сбой целиком → консервативно: все файлы «ошибка запроса» (не пропускаем)
        analyzed, counts, api_error = set(), {}, str(exc)
    else:
        api_error = None

    fail_files = []
    for rel in changed:
        if api_error is not None:
            fail_files.append(f"{rel} (ошибка запроса Sonar API: {api_error[:60]})")
            continue
        comp_key = _match_component(rel, a.project, analyzed)
        if comp_key is None:
            fail_files.append(f"{rel} (не проанализирован Sonar)")
            continue
        bc = counts.get(comp_key, 0)
        if bc != 0:
            fail_files.append(f"{rel} ({bc} {','.join(severities)})")

    passed = (not scan_stale) and (not fail_files)
    write_state(
        PROJECT_ROOT,
        {
            "ts": now.isoformat(),
            "host": a.host,
            "pass": passed,
            "skipped": False,
            "files_verified": changed,
            "fail_files": fail_files,
            "scan_stale": scan_stale,
            "last_analysis": last_an.isoformat() if last_an else None,
        },
    )

    print(f"sonar-rescan: изменённых .bsl={len(changed)}; severities={severities}")
    if scan_stale:
        print("  ⚠ последний анализ Sonar СТАРШЕ правок — прогони сначала run-sonar-analysis.ps1")
    for ff in fail_files:
        print("  ✗ " + ff)
    print("РЕЗУЛЬТАТ:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
