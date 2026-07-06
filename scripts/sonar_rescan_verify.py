#!/usr/bin/env python3
"""Обязательный Sonar re-scan изменённого/добавленного 1С-кода — дельта-verify.

Шаг «Тестирование» для правил «изменённый/добавленный 1С-код обязательно через SonarQube»
(ADR — см. docs гл. 43). Проверяет, что КАЖДЫЙ изменённый/новый `.bsl` (осн. репо + сабмодули):
  1) проанализирован Sonar (component существует),
  2) имеет 0 BLOCKER/CRITICAL **на изменённых строках** (пересечение line issue с
     `git diff -w` файла — сервер-независимый Clean-as-You-Code; inNewCodePeriod больше
     НЕ гейтит: вырожденный server-baseline [первый скан → new≈total] давал ложный FAIL
     на легаси-строках, см. baseline-degenerate детект ниже),
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
    changed_line_ranges,
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


def branches_analysis_dt(host, project, token):
    """Свежайший analysisDate по веткам (project_branches/list).

    P0.1 (roadmap 260706, I4): во время финализации Compute Engine project_analyses?ps=1
    отдаёт ПРЕДЫДУЩИЙ анализ, а branches.analysisDate уже свежий → freshness берём как
    max двух источников. Ошибка/пусто → None."""
    try:
        d = api(host, f"/api/project_branches/list?project={urllib.parse.quote(project)}", token)
        dts = [parse_dt(b.get("analysisDate")) for b in d.get("branches", [])]
        dts = [x for x in dts if x is not None]
        return max(dts) if dts else None
    except Exception:
        return None


def wait_ce(host, project, token, timeout_s, poll_s=5.0):
    """Ждёт финализацию Compute Engine: pending==0 И inProgress==0 (P0.1, I4 roadmap 260706).

    Сканер завершается (exit 0) ДО того, как CE допишет анализ (минуты на большом
    проекте) → без ожидания verify видит предыдущий анализ → ложный scan_stale.
    True = CE свободен; False = таймаут (честный stale-путь + подсказка). timeout_s<=0 = не ждать.
    Транзиентные ошибки API не прерывают ожидание (ждём до дедлайна)."""
    if timeout_s <= 0:
        return True
    deadline = time.monotonic() + timeout_s
    while True:
        try:
            st = api(
                host,
                f"/api/ce/activity_status?component={urllib.parse.quote(project)}",
                token,
                timeout=10,
            )
            if int(st.get("pending", 0)) == 0 and int(st.get("inProgress", 0)) == 0:
                return True
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return True  # проекта ещё нет (первый прогон/опечатка) — CE ждать нечего (R1)
            # прочие HTTP-коды — как транзиент, ждём до дедлайна
        except Exception:
            pass  # транзиент (рестарт/индексация) — продолжаем до дедлайна
        if time.monotonic() >= deadline:
            return False
        time.sleep(poll_s)


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


def file_issue_lines(host, comp_key, severities, token) -> list | None:
    """[line|None, ...] unresolved issues заданных severities ОДНОГО файлового компонента.

    Кириллический component-key в issues/search работает на SQ CB 26.x (HTTP 200,
    ре-проверено live 2026-07-03; прежний 500-баг — reference-sonar-cyrillic-component-api).
    None = запрос не удался → вызывающий падает на project-wide fallback (усечение 10k)."""
    try:
        base = (
            "/api/issues/search?componentKeys="
            + urllib.parse.quote(comp_key)
            + "&resolved=false&severities="
            + ",".join(severities)
        )
        return [i.get("line") for i in _paged(host, base, token, "issues", cap_pages=20)]
    except Exception:
        return None


def project_issue_lines(host, project, severities, token) -> tuple[dict[str, list], bool]:
    """FALLBACK: component_key -> [line|None, ...] всех unresolved issues заданных severities
    project-wide (когда per-file запрос не удался, напр. рецидив кириллического 500).

    БЕЗ inNewCodePeriod: дельту гейт считает сам по изменённым строкам (независимость от
    server-baseline). ES-лимит Sonar = 10k результатов на запрос → тянем по severity
    отдельно; total>10k у одной severity → усечение (truncated=True, best-effort)."""
    lines: dict[str, list] = {}
    truncated = False
    for sev in severities:
        base = (
            "/api/issues/search?componentKeys="
            + urllib.parse.quote(project)
            + "&resolved=false&severities="
            + sev
        )
        items = _paged(host, base, token, "issues", cap_pages=20)  # 20×500 = ES-лимит 10k
        if len(items) >= 10_000:
            truncated = True
        for iss in items:
            comp = iss.get("component")
            if comp:
                lines.setdefault(comp, []).append(iss.get("line"))
    return lines, truncated


def baseline_degenerate(host, project, token) -> tuple[bool, int, int]:
    """Вырожденный server-baseline new-code: new-issues ≈ all-issues (типично: первый скан
    проекта — ВСЕ легаси-issue получают creationDate дня скана; или PREVIOUS_VERSION без
    валидного version-события). → (degenerate, new_total, all_total). Информационная
    диагностика (не гейтит): без неё расследование «почему 5 CRITICAL на нетронутом файле»
    занимает часы. Ошибка API → (False, -1, -1)."""
    try:
        q = (
            "/api/issues/search?componentKeys="
            + urllib.parse.quote(project)
            + "&resolved=false&ps=1"
        )
        all_total = (api(host, q, token).get("paging") or {}).get("total", 0)
        new_total = (api(host, q + "&inNewCodePeriod=true", token).get("paging") or {}).get(
            "total", 0
        )
        return (all_total >= 200 and new_total >= 0.5 * all_total), new_total, all_total
    except Exception:
        return False, -1, -1


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
    ap.add_argument(
        "--wait-ce",
        type=float,
        default=120.0,
        dest="wait_ce",
        help="сек ожидания финализации Compute Engine перед freshness-проверкой (0 = не ждать)",
    )
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

    # P0.1: дождаться финализации CE (иначе ложный stale — сканер exit 0 ≠ анализ дописан)
    if not wait_ce(a.host, a.project, a.token, a.wait_ce):
        print(f"  ⚠ CE ещё обрабатывает анализ (ждали {a.wait_ce:.0f}с) — freshness может отстать")

    last_an = last_analysis_dt(a.host, a.project, a.token)
    br_an = branches_analysis_dt(a.host, a.project, a.token)
    if br_an is not None and (last_an is None or br_an > last_an):
        last_an = br_an  # branches обновляется атомарнее project_analyses (I4)
    nm = newest_mtime(PROJECT_ROOT, changed)
    scan_stale = bool(last_an is None or (nm and last_an.timestamp() < nm))

    try:
        analyzed = analyzed_file_keys(a.host, a.project, a.token)
    except Exception as exc:
        # API-сбой целиком → консервативно: все файлы «ошибка запроса» (не пропускаем)
        analyzed, api_error = set(), str(exc)
    else:
        api_error = None

    degenerate, new_total, all_total = baseline_degenerate(a.host, a.project, a.token)

    # per-file запросы точны (нет ES-усечения); project-wide paged — ленивый fallback
    global_cache: dict[str, list] | None = None
    truncated = False
    fail_files = []
    for rel in changed:
        if api_error is not None:
            fail_files.append(f"{rel} (ошибка запроса Sonar API: {api_error[:60]})")
            continue
        comp_key = _match_component(rel, a.project, analyzed)
        if comp_key is None:
            fail_files.append(f"{rel} (не проанализирован Sonar)")
            continue
        lns = file_issue_lines(a.host, comp_key, severities, a.token)
        if lns is None:
            if global_cache is None:
                try:
                    global_cache, truncated = project_issue_lines(
                        a.host, a.project, severities, a.token
                    )
                except Exception as exc:
                    fail_files.append(f"{rel} (ошибка запроса Sonar API: {str(exc)[:60]})")
                    continue
            lns = global_cache.get(comp_key, [])
        ranges = changed_line_ranges(PROJECT_ROOT, rel)
        if ranges is None:
            # новый/untracked файл (или дифф не получен): все его issue — мои,
            # включая файловые (line=None) — fail-closed
            hits = len(lns)
        else:
            # изменённый файл: гейтим только issue на содержательно изменённых строках;
            # файловые issue (line=None) на изменённом файле легаси-атрибуции не имеют
            hits = sum(
                1 for ln in lns if isinstance(ln, int) and any(s <= ln <= e for s, e in ranges)
            )
        if hits:
            fail_files.append(f"{rel} ({hits} {','.join(severities)} на изменённых строках)")

    passed = (not scan_stale) and (not fail_files)
    write_state(
        PROJECT_ROOT,
        {
            "ts": now.isoformat(),
            "host": a.host,
            "mode": "changed-lines",
            "pass": passed,
            "skipped": False,
            "files_verified": changed,
            "fail_files": fail_files,
            "scan_stale": scan_stale,
            "last_analysis": last_an.isoformat() if last_an else None,
            "baseline_degenerate": degenerate,
            "issues_truncated": truncated,
        },
    )

    print(
        f"sonar-rescan: изменённых .bsl={len(changed)}; severities={severities}; mode=changed-lines"
    )
    if degenerate:
        print(
            f"  ⚠ server new-code baseline ВЫРОЖДЕН (new={new_total} ≈ total={all_total}): "
            "штатный Quality Gate Sonar завышает «новое»; этот гейт независим — дельта "
            "считается по diff-строкам. Починка сервера: api/new_code_periods/set "
            "(branch-level SPECIFIC_ANALYSIS на пре-change анализ)"
        )
    if truncated:
        print(
            "  ⚠ >10k unresolved issues одной severity — выборка усечена ES-лимитом (best-effort)"
        )
    if scan_stale:
        print("  ⚠ последний анализ Sonar СТАРШЕ правок — прогони сначала run-sonar-analysis.ps1")
    for ff in fail_files:
        print("  ✗ " + ff)
    print("РЕЗУЛЬТАТ:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
