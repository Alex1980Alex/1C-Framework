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


def component_exists(host, key, token) -> bool:
    try:
        api(host, "/api/components/show?component=" + urllib.parse.quote(key), token)
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        return True  # иная ошибка — не считаем «не проанализирован» (консервативно)
    except Exception:
        return True


def blocker_critical_count(host, key, severities, token) -> int:
    # inNewCodePeriod=true → только НОВЫЕ нарушения (Clean-as-You-Code: «легаси не гейтим»,
    # ADR-033/034 R6): правка легаси-файла с пред-существующими issue не должна валить гейт.
    # Требует настроенного new-code period в Sonar; при его отсутствии (первый скан — весь код
    # «новый») ведёт себя как total (безопасно строже, не пропускает).
    q = (
        "/api/issues/search?componentKeys="
        + urllib.parse.quote(key)
        + "&resolved=false&inNewCodePeriod=true&ps=1&severities="
        + ",".join(severities)
    )
    try:
        return int(api(host, q, token).get("total", 0))
    except Exception:
        return -1  # ошибка запроса → пометим как нарушение (безопасно: не пропустить)


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

    fail_files = []
    for rel in changed:
        key = f"{a.project}:{rel}"
        if not component_exists(a.host, key, a.token):
            fail_files.append(f"{rel} (не проанализирован Sonar)")
            continue
        bc = blocker_critical_count(a.host, key, severities, a.token)
        if bc != 0:
            fail_files.append(
                f"{rel} ({'ошибка запроса' if bc < 0 else str(bc) + ' BLOCKER/CRITICAL'})"
            )

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
