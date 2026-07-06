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

# Реестр проектов split-режима (P3.A wiring). Defensive: недоступен → mono-only.
try:
    from sonar_projects import project_for_path, split_enabled  # scripts/ на sys.path (_dotenv)
except Exception:  # pragma: no cover
    project_for_path = None

    def split_enabled() -> bool:
        return False


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


def _paged(host, path_base, token, items_key, page_size=500, cap_pages=100):
    """Собирает все элементы пагинированного Sonar-эндпоинта (project-level).

    componentKeys/component = ASCII-ключ проекта → нет кириллического 500; ключи файлов
    приходят в теле ответа (UTF-8), фильтруем локально по суффиксу пути. ОДНО keep-alive
    соединение на все страницы (иначе десятки сокетов → WinError 10048 port exhaustion).

    P2.1 (roadmap 260706, A2): cap_pages по умолчанию 100 (100×500=50k; проект ~14.4k файлов
    с запасом). При достижении cap с непрочитанным хвостом — ⚠ печатается (не молчаливое
    усечение, иначе неполная выборка читается как «всё покрыто»)."""
    u = urllib.parse.urlsplit(host)
    is_https = u.scheme == "https"
    conn_cls = http.client.HTTPSConnection if is_https else http.client.HTTPConnection
    conn = conn_cls(u.hostname, u.port or (443 if is_https else 80), timeout=30)
    hdr = {"Authorization": _auth(token)}
    out = []
    truncated = False
    try:
        page = 1
        while True:
            if page > cap_pages:
                truncated = True  # вышли по cap, а не по завершению → хвост не прочитан
                break
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
    if truncated:
        print(
            f"  ⚠ _paged: усечение выборки '{items_key}' на cap_pages={cap_pages} "
            f"(>{cap_pages * page_size} элементов) — выборка НЕПОЛНАЯ, подними cap"
        )
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


def show_file(host, project, token, rel) -> int:
    """P1.3 (roadmap 260706, I5): печать разрешённого component_key + unresolved issues файла.

    Оператору не нужен ручной curl с кириллическим ключом — та же машинерия
    `analyzed_file_keys`/`_match_component`/`_paged`. Показывает ВСЕ severities
    (диагностика). Exit: 0 = ок, 1 = не проанализирован, 2 = Sonar недоступен/ошибка API."""
    if not reachable(host):
        print(f"sonar --show-file: SonarQube недоступен ({host})")
        return 2
    try:
        analyzed = analyzed_file_keys(host, project, token)
    except Exception as exc:
        print(f"sonar --show-file: ошибка получения компонентов: {str(exc)[:80]}")
        return 2
    comp = _match_component(rel, project, analyzed)
    if comp is None:
        print(f"✗ {rel}: не проанализирован Sonar (компонент не найден в проекте {project})")
        return 1
    print(f"component_key: {comp}")
    base = "/api/issues/search?componentKeys=" + urllib.parse.quote(comp) + "&resolved=false"
    try:
        items = _paged(host, base, token, "issues", cap_pages=20)
    except Exception as exc:
        print(f"  ошибка issues/search: {str(exc)[:80]}")
        return 2
    items.sort(key=lambda i: i.get("line") or 0)
    print(f"unresolved issues: {len(items)}")
    for i in items:
        ln = i.get("line") or "—"  # file-level issue (line=None/отсутствует) → «—»
        sev = i.get("severity", "?")
        rule = i.get("rule", "?")
        msg = (i.get("message") or "").replace("\n", " ")[:120]
        print(f"  L{ln}\t{sev}\t{rule}\t{msg}")
    return 0


def verify_project(host, project, token, files, severities, wait_ce_s) -> dict:
    """Дельта-verify ОДНОГО Sonar-проекта. Ядро, общее для mono и split (P3.A wiring).

    files = [(repo_rel, comp_rel)]: repo_rel — от корня репо (mtime/diff через PROJECT_ROOT),
    comp_rel — от projectBaseDir проекта для матчинга component-ключа:
      - mono: projectBaseDir = корень репо → comp_rel == repo_rel;
      - split: projectBaseDir = корень конфигурации → comp_rel = путь ВНУТРИ конфигурации.
    → dict {project, pass, scan_stale, last_analysis, fail_files, verified(repo_rel),
    baseline_degenerate, new_total, all_total, issues_truncated}."""
    repo_rels = [fr for fr, _ in files]
    # P0.1: дождаться финализации CE (иначе ложный stale — сканер exit 0 ≠ анализ дописан)
    if not wait_ce(host, project, token, wait_ce_s):
        print(
            f"  ⚠ [{project}] CE ещё обрабатывает анализ (ждали {wait_ce_s:.0f}с) — freshness может отстать"
        )
    last_an = last_analysis_dt(host, project, token)
    br_an = branches_analysis_dt(host, project, token)
    if br_an is not None and (last_an is None or br_an > last_an):
        last_an = br_an  # branches обновляется атомарнее project_analyses (I4)
    nm = newest_mtime(PROJECT_ROOT, repo_rels)
    scan_stale = bool(last_an is None or (nm and last_an.timestamp() < nm))

    try:
        analyzed = analyzed_file_keys(host, project, token)
    except Exception as exc:
        analyzed, api_error = set(), str(exc)
    else:
        api_error = None

    degenerate, new_total, all_total = baseline_degenerate(host, project, token)

    global_cache: dict[str, list] | None = None
    truncated = False
    fail_files: list[str] = []
    for repo_rel, comp_rel in files:
        if api_error is not None:
            fail_files.append(f"{repo_rel} (ошибка запроса Sonar API: {api_error[:60]})")
            continue
        comp_key = _match_component(comp_rel, project, analyzed)
        if comp_key is None:
            fail_files.append(f"{repo_rel} (не проанализирован Sonar)")
            continue
        lns = file_issue_lines(host, comp_key, severities, token)
        if lns is None:
            if global_cache is None:
                try:
                    global_cache, truncated = project_issue_lines(host, project, severities, token)
                except Exception as exc:
                    fail_files.append(f"{repo_rel} (ошибка запроса Sonar API: {str(exc)[:60]})")
                    continue
            lns = global_cache.get(comp_key, [])
        ranges = changed_line_ranges(PROJECT_ROOT, repo_rel)
        if ranges is None:
            hits = len(lns)  # новый/untracked → все issue мои (fail-closed)
        else:
            hits = sum(
                1 for ln in lns if isinstance(ln, int) and any(s <= ln <= e for s, e in ranges)
            )
        if hits:
            fail_files.append(f"{repo_rel} ({hits} {','.join(severities)} на изменённых строках)")

    return {
        "project": project,
        "pass": (not scan_stale) and (not fail_files),
        "scan_stale": scan_stale,
        "last_analysis": last_an.isoformat() if last_an else None,
        "fail_files": fail_files,
        "verified": repo_rels,
        "baseline_degenerate": degenerate,
        "new_total": new_total,
        "all_total": all_total,
        "issues_truncated": truncated,
    }


def _print_project_notes(res: dict, tagged: bool = False) -> None:
    """Печать диагностических ⚠ (degenerate/truncated/scan_stale) по результату verify_project."""
    p = f"[{res['project']}] " if tagged else ""
    if res["baseline_degenerate"]:
        print(
            f"  ⚠ {p}server new-code baseline ВЫРОЖДЕН (new={res['new_total']} ≈ total={res['all_total']}): "
            "штатный Quality Gate Sonar завышает «новое»; этот гейт независим — дельта считается "
            "по diff-строкам. Починка: scripts/sonar_set_new_code_baseline.py (branch-level SPECIFIC_ANALYSIS)"
        )
    if res["issues_truncated"]:
        print(
            f"  ⚠ {p}>10k unresolved issues одной severity — выборка усечена ES-лимитом (best-effort)"
        )
    if res["scan_stale"]:
        print(
            f"  ⚠ {p}последний анализ Sonar СТАРШЕ правок — прогони сначала run-sonar-analysis.ps1"
        )


def _group_by_project(changed) -> tuple[dict, list]:
    """Группировка изменённых repo-путей по проектам реестра (split-режим, P3.A).

    → (groups {key: {"root", "files":[(repo_rel, comp_rel)]}}, unmapped [repo_rel]).
    unmapped = `.bsl` под /src/ вне корней реестра (fail-closed у вызывающего)."""
    groups: dict[str, dict] = {}
    unmapped: list[str] = []
    for rel in changed:
        pr = project_for_path(rel) if project_for_path else None
        if pr is None:
            unmapped.append(rel)
            continue
        key, root_rel, rel_in = pr
        groups.setdefault(key, {"root": root_rel, "files": []})
        groups[key]["files"].append((rel, rel_in))
    return groups, unmapped


def _run_split(a, changed, now, severities) -> int:
    """Split-режим (SONAR_SPLIT_PROJECTS=1): per-project verify + агрегатное state.

    Гейт (`sonar_rescan_state.evaluate`) читает АГРЕГАТ (pass/scan_stale/fail_files/
    files_verified/last_analysis) — не меняется; `projects:{}` — детальный срез сверху."""
    groups, unmapped = _group_by_project(changed)
    results = []
    for key in sorted(groups):
        res = verify_project(a.host, key, a.token, groups[key]["files"], severities, a.wait_ce)
        res["root"] = groups[key]["root"]
        results.append(res)

    fail_files = [f for r in results for f in r["fail_files"]]
    for rel in unmapped:  # вне реестра → fail-closed (нельзя подтвердить чистоту)
        fail_files.append(f"{rel} (не сопоставлен проекту реестра — вне Sonar-скоупа split)")
    scan_stale = any(r["scan_stale"] for r in results)
    passed = (not fail_files) and (not scan_stale)
    verified = [r_ for r in results for r_ in r["verified"]]  # только сопоставленные

    projects_state = {
        r["project"]: {
            "root": r.get("root"),
            "pass": r["pass"],
            "scan_stale": r["scan_stale"],
            "last_analysis": r["last_analysis"],
            "fail_files": r["fail_files"],
            "files": r["verified"],
            "baseline_degenerate": r["baseline_degenerate"],
        }
        for r in results
    }
    last_all = [r["last_analysis"] for r in results if r["last_analysis"]]
    write_state(
        PROJECT_ROOT,
        {
            "ts": now.isoformat(),
            "host": a.host,
            "mode": "changed-lines",
            "split": True,
            "pass": passed,
            "skipped": False,
            "files_verified": sorted(verified),
            "fail_files": fail_files,
            "scan_stale": scan_stale,
            "last_analysis": max(last_all) if last_all else None,
            "projects": projects_state,
            "issues_truncated": any(r["issues_truncated"] for r in results),
        },
    )

    print(
        f"sonar-rescan [SPLIT]: изменённых .bsl={len(changed)} в {len(groups)} проект(ах); "
        f"severities={severities}; mode=changed-lines"
    )
    for r in results:
        print(
            f"  проект {r['project']} ({r.get('root')}): файлов={len(r['verified'])} pass={r['pass']}"
        )
        _print_project_notes(r, tagged=True)
    for ff in fail_files:
        print("  ✗ " + ff)
    print("РЕЗУЛЬТАТ:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


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
    ap.add_argument(
        "--show-file",
        dest="show_file",
        default=None,
        help="диагностика (P1.3): component_key + unresolved issues файла (repo-относительный путь)",
    )
    a = ap.parse_args()
    severities = [s for s in a.severities.split(",") if s]
    if a.show_file:  # P1.3: диагностический подрежим (не гейт) — печать и выход
        return show_file(a.host, a.project, a.token, a.show_file.replace("\\", "/"))
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

    if split_enabled():  # P3.A: per-project скан+verify (opt-in SONAR_SPLIT_PROJECTS=1)
        return _run_split(a, changed, now, severities)

    # mono (legacy, default) — один проект, projectBaseDir = корень репо → comp_rel == repo_rel
    res = verify_project(
        a.host, a.project, a.token, [(r, r) for r in changed], severities, a.wait_ce
    )
    passed = res["pass"]
    write_state(
        PROJECT_ROOT,
        {
            "ts": now.isoformat(),
            "host": a.host,
            "mode": "changed-lines",
            "pass": passed,
            "skipped": False,
            "files_verified": changed,
            "fail_files": res["fail_files"],
            "scan_stale": res["scan_stale"],
            "last_analysis": res["last_analysis"],
            "baseline_degenerate": res["baseline_degenerate"],
            "issues_truncated": res["issues_truncated"],
        },
    )

    print(
        f"sonar-rescan: изменённых .bsl={len(changed)}; severities={severities}; mode=changed-lines"
    )
    _print_project_notes(res)
    for ff in res["fail_files"]:
        print("  ✗ " + ff)
    print("РЕЗУЛЬТАТ:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
