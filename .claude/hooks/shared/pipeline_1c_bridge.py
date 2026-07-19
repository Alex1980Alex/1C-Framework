#!/usr/bin/env python3
"""Мост 1С-слэш-команд → generic pipeline-state (ADR-019 B′ F-1, ядро G3).

Зовётся из ``analyze-1c-task-preflight`` / ``implement-1c-task-preflight`` (UPS).
Идемпотентно заводит ``pipeline/<slug>/.pipeline-state.json``, чтобы 1С-слэш-маршрут
удовлетворял инвариант ADR-018 ``pipeline-protocol-stop`` БЕЗ ручного пайплайна (G3).

Контракт:
  * **best-effort** — ``ensure_pipeline_1c`` НИКОГДА не кидает (preflight не должен ломаться);
  * **один пайплайн на задачу** — slug = JIRA-код (стабилен между analyze и implement);
    fallback — ASCII-slug первой строки prompt; пусто/кириллица-без-JIRA → ``"1c-task"``
    (общий слот; не-JIRA задачи могут не объединиться analyze↔implement — приемлемо для F-1,
    G3-блок всё равно снят).

Реверс F-1: убрать вызовы ``ensure_pipeline_1c`` из 2 preflight + удалить этот файл.
"""

from __future__ import annotations

import json
import os
import re
import sys
import unicodedata

_JIRA = re.compile(r"[A-Z]{2,}-\d+")

# Д-1 (roadmap 260703 P0.3): паттерн `[A-Z]{2,}-\d+` матчит технические акронимы вида
# UTF-8 / SHA-256 / GPT-4 / ISO-8601 → раньше давали confidence 1.0 + veto-иммунитет →
# «поправь кодировку UTF-8 в отчёте» уходило в flow=auto. Denylist отсекает акронимы как
# JIRA-коды; allowlist проектных префиксов (env ONEC_JIRA_PREFIXES, csv) даёт им 1.0-уверенность;
# прочие generic-совпадения → veto-able (не 1.0) — обрабатывается в classify_1c_task.
_JIRA_ACRONYM_DENY = frozenset(
    {
        "UTF",
        "SHA",
        "MD",
        "GPT",
        "ISO",
        "AES",
        "RSA",
        "TLS",
        "SSL",
        "CRC",
        "HTTP",
        "HTTPS",
        "JSON",
        "XML",
        "HTML",
        "CSS",
        "SQL",
        "API",
        "URL",
        "URI",
        "UUID",
        "CPU",
        "GPU",
        "RAM",
        "RFC",
        "PEP",
        "ISBN",
        "UTC",
        "GMT",
        "BASE",
        "MD5",
        "IEEE",
        "ANSI",
        "ASCII",
        "PDF",
        "PNG",
        "JPG",
        "GIF",
        "MP3",
        "MP4",
        "AV1",
        "IPV",
        "ID",
        "OAUTH",
        "JWT",
        "GRPC",
        "TCP",
        "UDP",
        "DNS",
        "SMTP",
        "IMAP",
        "FTP",
        "SSH",
        "VPN",
        "LTS",
        "EOL",
        "CI",
        "CD",
    }
)
_JIRA_PREFIX_ALLOW_DEFAULT = ("GKSTCPLK",)


def _jira_prefix_allow() -> set[str]:
    allow = {p.upper() for p in _JIRA_PREFIX_ALLOW_DEFAULT}
    env = os.environ.get("ONEC_JIRA_PREFIXES", "")
    if env:
        allow |= {x.strip().upper() for x in env.split(",") if x.strip()}
    return allow


def _find_jira(text: str):
    """Первое JIRA-совпадение, НЕ являющееся техническим акронимом из denylist (Д-1).

    Allowlist-префикс (GKSTCPLK / env ONEC_JIRA_PREFIXES) проходит всегда. Denylist-акроним
    (UTF/SHA/GPT/…) пропускается (не JIRA). Прочие generic-коды проходят как совпадение, но
    caller понижает их уверенность (classify → 0.7 veto-able вместо 1.0). Возврат: re.Match|None.
    """
    allow = _jira_prefix_allow()
    for m in _JIRA.finditer(text or ""):
        prefix = m.group(0).split("-", 1)[0].upper()
        if prefix in allow:
            return m
        if prefix in _JIRA_ACRONYM_DENY:
            continue
        return m
    return None


def _jira_is_confident(match) -> bool:
    """True если префикс JIRA — из allowlist проектных кодов (→ confidence 1.0, veto-иммунитет)."""
    if not match:
        return False
    return match.group(0).split("-", 1)[0].upper() in _jira_prefix_allow()


_1C_TITLE_PREFIX = (
    "1С-задача ("  # формат ensure_pipeline_1c / run-1c-task: f"1С-задача ({command}): {slug}"
)


def is_1c_task_title(title) -> bool:
    """Единый предикат «pipeline реальной 1С-задачи» (N4: убирает дубль/рассинхрон префикса в 6 местах).

    Строго ``startswith("1С-задача (")`` (с открывающей скобкой) — исключает framework-lookalike
    «1С-задача из чата: …». Используется в guard'ах моста И в Stop-gate (onec-task-completion-stop).
    """
    return str(title or "").startswith(_1C_TITLE_PREFIX)


def derive_slug(prompt: str) -> str:
    """JIRA-код приоритетно (стабильный ID задачи между командами); иначе ASCII-slug."""
    m = _find_jira(prompt or "")
    if m:
        return m.group(0)
    base = (prompt or "").strip().split("\n", 1)[0][:40]
    ascii_ = unicodedata.normalize("NFKD", base).encode("ascii", "ignore").decode().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")
    return slug or "1c-task"


def resolve_task_input(arg: str) -> dict:
    """Вход ``/run-1c-task``: путь к ТЗ-папке / JIRA-код / описание из чата.

    Возврат ``{kind: 'folder'|'jira'|'chat', slug, folder}``. Чистая функция (os.path + derive_slug,
    без pipeline_state) → collision-immune тест. ``folder=None`` если вход — не существующая папка.

    Приоритет: существующая папка (slug из её имени) > JIRA-код > описание (ASCII-slug).
    Несуществующий путь с JIRA-кодом в имени → ветка jira (код задачи как slug).
    """
    a = (arg or "").strip().strip('"').strip("'")
    if a and (os.sep in a or "/" in a) and os.path.isdir(a):
        slug = derive_slug(os.path.basename(os.path.normpath(a)))
        return {"kind": "folder", "slug": slug, "folder": a}
    m = _find_jira(a)
    if m:
        return {"kind": "jira", "slug": m.group(0), "folder": None}
    return {"kind": "chat", "slug": derive_slug(a), "folder": None}


def resolve_active_1c_slug(prompt: str) -> str | None:
    """Slug активного 1С-пайплайна — единая идентификация для gate/ensure-implement (C2/C3).

    JIRA в промпте → его код (стабильный ID задачи; gate сам проверит существование/approve, как раньше).
    Иначе → CURRENT-указатель, ЕСЛИ это 1С-пайплайн (метка is_1c_task_title) — так /implement
    прицепляется к пайплайну /analyze для НЕ-JIRA задач (у которых derive_slug(analyze)≠derive_slug(implement)).
    best-effort → None (нет JIRA и нет активного 1С-пайплайна / сбой импорта).
    """
    try:
        m = _find_jira(prompt or "")
        if m:
            return m.group(0)
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        cur = pipeline_state.resolve_current()
        data = pipeline_state.load(cur) if cur else None
        return cur if (data and is_1c_task_title(data.get("title"))) else None
    except Exception:
        return None


def ensure_pipeline_1c(prompt: str, command: str, task_dir: str | None = None) -> str | None:
    """Идемпотентно завести pipeline для 1С-задачи. Возврат slug | None (best-effort).

    task_dir (если известна папка ТЗ, напр. kind=folder) → состояние рождается сразу в ней; иначе
    в generic pipeline/<slug>/ до первого артефакта (relocate-on-artifact перенесёт в папку задачи).
    """
    try:
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        # C2/C3: /implement прицепляется к активному 1С-пайплайну (не-JIRA: пайплайн /analyze через
        # CURRENT) вместо нового slug из своего prompt; analyze / нет активного → свежий derive_slug.
        slug = (
            resolve_active_1c_slug(prompt) if command == "implement-1c-task" else None
        ) or derive_slug(prompt)
        pipeline_state.init_task(
            slug, title=f"1С-задача ({command}): {slug}", task_dir=task_dir
        )  # идемпотентно
        return slug
    except Exception:
        return None  # никогда не ломаем preflight


# ADR-019 F-1.5: запись 1С-артефакта → продвижение этапов CURRENT 1С-пайплайна.
_ARTIFACT_STAGES = [
    (re.compile(r"ANALYSIS-REPORT", re.I), (1, 2)),  # analyze → Планирование + Дизайн
    (re.compile(r"IMPLEMENTATION-PROGRESS", re.I), (3,)),  # implement → Кодирование
]
_ARTIFACT_MIN_CHARS = (
    200  # H7: порог непробельных символов против false-advance на пустом/stub-артефакте
)


def _artifact_has_content(file_path: str, min_chars: int = _ARTIFACT_MIN_CHARS) -> bool:
    """H7: артефакт несёт реальное содержимое (не пустой/stub) — иначе этапы не продвигаем.

    Настоящий ANALYSIS-REPORT / IMPLEMENTATION-PROGRESS (методики analyze/implement) — это >1KB
    структурированного текста; порог 200 непробельных символов отсекает заглушку, не задевая
    реальный отчёт. Инкрементальная запись: пустой header не продвинет, заполняющий Edit — продвинет.
    """
    try:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            body = f.read()
    except OSError:
        return False
    return len("".join(body.split())) >= min_chars


def _owning_1c_slug(file_path: str, pipeline_state) -> str | None:
    """Зарегистрированный 1С-пайплайн, которому ПРИНАДЛЕЖИТ артефакт (P1.5, класс «чужой задачи»).

    Артефакт (ANALYSIS-REPORT/IMPLEMENTATION-PROGRESS) лежит В папке своей задачи → владелец =
    пайплайн, чей ``state_dir`` — предок пути артефакта (точная привязка). Fallback: JIRA в пути
    совпал с зарегистрированным slug. None → caller использует CURRENT (прежнее поведение).
    Без этого запись артефакта задачи B продвигала/переносила state задачи A (CURRENT)."""
    try:
        art = os.path.abspath(file_path or "")
        pairs = list(pipeline_state.iter_states())
        # Самый ГЛУБОКИЙ state_dir-предок = наиболее специфичный владелец (снимает латентную
        # неоднозначность, если родительская и дочерняя задачи зарегистрированы на вложенные папки).
        best_slug, best_len = None, -1
        for slug, data in pairs:
            if not is_1c_task_title(data.get("title")):
                continue
            sd = os.path.abspath(str(pipeline_state.state_dir(slug)))
            if (art == sd or art.startswith(sd + os.sep)) and len(sd) > best_len:
                best_slug, best_len = slug, len(sd)
        if best_slug:
            return best_slug
        # fallback: ЛЮБОЙ JIRA в пути (nested-путь `…/260304_GKSTCPLK-2182/docs/…_GKSTCPLK-2637/…`
        # несёт и родителя, и задачу) совпал с зарегистрированным 1С-slug'ом.
        jiras = {_slug_norm(mm.group(0)) for mm in _JIRA.finditer(file_path or "")}
        if jiras:
            for slug, data in pairs:
                if is_1c_task_title(data.get("title")) and _slug_norm(slug) in jiras:
                    return slug
    except Exception:
        pass
    return None


def _slug_norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def advance_for_artifact(file_path: str) -> tuple[int, ...] | None:
    """Продвинуть этапы CURRENT 1С-пайплайна по записи 1С-артефакта (F-1.5). best-effort → None.

    ANALYSIS-REPORT → этапы 1,2 (Планирование+Дизайн); IMPLEMENTATION-PROGRESS → этап 3 (Кодирование).
    Guard: трогаем ТОЛЬКО пайплайн с меткой F-1 (title «1С-задача…») — не двигаем framework-dev пайплайны.
    Идемпотентно: mark_done только для ещё-не-done этапов. Возврат — кортеж реально продвинутых этапов | None.
    """
    try:
        name = (file_path or "").replace("\\", "/").rsplit("/", 1)[-1]
        stages = next((st for rx, st in _ARTIFACT_STAGES if rx.search(name)), None)
        if not stages:
            return None
        if not _artifact_has_content(file_path):
            return None  # H7: пустой/stub-артефакт не продвигает этапы (false-advance guard)
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        # P1.5: сперва владелец по пути артефакта (state_dir-предок / JIRA), иначе CURRENT (legacy).
        # Без этого запись артефакта задачи B продвигала CURRENT (задачу A) и переносила её state.
        slug = _owning_1c_slug(file_path, pipeline_state) or pipeline_state.resolve_current()
        data = pipeline_state.load(slug) if slug else None
        if not data or not is_1c_task_title(data.get("title")):
            return None  # guard: только 1С-пайплайн (метка ensure_pipeline_1c)
        # relocate-on-artifact: состояние 1С-задачи живёт В ПАПКЕ ЗАДАЧИ рядом с артефактом.
        # task_dir = каталог только что записанного ANALYSIS-REPORT/IMPLEMENTATION-PROGRESS.
        try:
            task_dir = os.path.dirname(os.path.abspath(file_path))
            if task_dir and hasattr(pipeline_state, "relocate_1c"):
                pipeline_state.relocate_1c(slug, task_dir)
                data = pipeline_state.load(slug) or data  # перечитать из нового расположения
        except Exception:
            pass  # best-effort: перенос не должен ломать продвижение этапов
        done_now = []
        for n in stages:
            st = next((s for s in data.get("stages", []) if s.get("n") == n), None)
            if st and st.get("status") != "done":
                pipeline_state.mark_done(slug, n)
                done_now.append(n)
        return tuple(done_now) or None
    except Exception:
        return None


def gate_1c_implement(prompt: str) -> dict:
    """G4 (ADR-019 F-2): блок /implement-1c-task если дизайн (этап 2) 1С-пайплайна НЕ approved.

    Возврат {ok, hard, reason}. Нет 1С-пайплайна / не-1С / сбой → ok=True (no-op, best-effort —
    не блокируем нормальный поток). Хард-блок ТОЛЬКО при существующем 1С-пайплайне с не-одобренным дизайном.
    """
    try:
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        # C2/C3: единая идентификация (как ensure-implement) — JIRA-slug, иначе активный CURRENT-1С.
        # Для не-JIRA это находит пайплайн /analyze (раньше derive_slug(implement_prompt) ≠ analyze-slug
        # → G4 молча no-op либо ложно блокировал свежий implement-пайплайн).
        slug = resolve_active_1c_slug(prompt)
        data = pipeline_state.load(slug) if slug else None
        if not data or not is_1c_task_title(data.get("title")):
            # P1.3 (К-4): /implement вызван, но активный 1С-пайплайн (дизайн) не найден →
            # раньше молчаливый no-op. Advisory сообщает, что G4 НЕ применён (не блок).
            return {
                "ok": True,
                "hard": False,
                "reason": "",
                "advisory": (
                    "активный 1С-пайплайн (дизайн) не найден — G4-гейт «Дизайн→Кодирование» НЕ "
                    "применён. Убедись, что `/analyze-1c-task` создал pipeline-state этой задачи, "
                    "или укажи JIRA-код в промпте (проверь: `pipeline_state.py status`)."
                ),
            }
        st2 = next((s for s in data.get("stages", []) if s.get("n") == 2), None)
        if st2 and st2.get("status") == "done" and st2.get("approved"):
            return {
                "ok": True,
                "hard": False,
                "reason": "",
            }  # дизайн одобрен (pipeline-state) → allow
        # R1+R2 (ADR-041): дизайн мог быть одобрен через SDD-обёртку — /opsx:approve пишет
        # openspec/changes/<id>/.openspec.yaml (approval.status), а НЕ pipeline-state. sync_approval:
        # (R1) honor OpenSpec-approval — иначе ложный G4-блок implement в SDD-потоке (расхождение
        # сторов); (R2) проецирует одобрение в pipeline-state → сторы СХОДЯТСЯ (единый источник).
        # JIRA-gated: non-JIRA путь нетронут (нет JIRA → плечо не срабатывает → G4 по pipeline-state).
        if _find_jira(prompt or ""):
            try:
                if sync_approval(prompt).get("openspec_approved"):
                    return {"ok": True, "hard": False, "reason": "", "source": "openspec"}
            except (Exception, SystemExit):
                pass
        return {
            "ok": False,
            "hard": True,
            "reason": (
                f"Дизайн (ANALYSIS-REPORT, этап 2) задачи {slug} НЕ одобрен. Отревьюй ANALYSIS-REPORT "
                f"и одобри: `.venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py approve {slug}`"
            ),
        }
    except Exception:
        return {"ok": True, "hard": False, "reason": ""}  # best-effort: не блокируем при сбое


def sync_approval(prompt: str) -> dict:
    """R2 (ADR-041): мост state↔yaml — односторонняя проекция OpenSpec-approval → pipeline-state.

    Единый источник одобрения: если дизайн одобрен через SDD (``/opsx:approve`` пишет ``.openspec.yaml``),
    проецируем это в ``.pipeline-state.json`` (этап 2 approved, ``by="openspec-bridge"``) — чтобы оба стора
    СХОДИЛИСЬ, а не расходились (корень R1/R2). **Одностороннe**: pipeline-approve НЕ пишет обратно в
    OpenSpec (обошло бы human-review ``/opsx:approve``). best-effort, идемпотентно, JIRA-gated.

    Возврат ``{openspec_approved, synced, slug, reason}``.
    """
    out = {"openspec_approved": False, "synced": False, "slug": None, "reason": ""}
    try:
        if not _find_jira(prompt or ""):
            out["reason"] = "no-jira"
            return out
        from shared.approval_state import is_design_approved_via_openspec

        if not is_design_approved_via_openspec(prompt):
            out["reason"] = "openspec-not-approved"
            return out
        out["openspec_approved"] = True
        slug = resolve_active_1c_slug(prompt)
        out["slug"] = slug
        if not slug:
            out["reason"] = "no-pipeline-slug"
            return out
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        data = pipeline_state.load(slug)
        if not data or not is_1c_task_title(data.get("title")):
            out["reason"] = "no-1c-pipeline"
            return out
        st2 = next((s for s in data.get("stages", []) if s.get("n") == 2), None)
        if st2 is None:
            out["reason"] = (
                "no-stage-2"  # malformed state — не зовём approve (он кинул бы SystemExit)
            )
            return out
        if st2.get("approved"):
            out["reason"] = "already-synced"
            return out
        # pipeline_state.approve — CLI-функция, на ошибке кидает SystemExit (BaseException, НЕ Exception)
        # → ловим (Exception, SystemExit), иначе утечёт сквозь гейт на UPS (нарушит fail-open).
        try:
            pipeline_state.approve(slug, by="openspec-bridge")
            out["synced"] = True
            out["reason"] = "projected openspec->pipeline"
        except (Exception, SystemExit):
            out["reason"] = "approve-failed"
        return out
    except (Exception, SystemExit):
        return out


def _lineage_issues(change_dir: str, analysis_report: str | None = None) -> list:
    """R3 (ADR-041): чистый детектор дрейфа SDD-change — structural coverage + staleness vs ANALYSIS-REPORT.

    Возврат списка проблем (пустой = consistent). Чистая функция (tmp_path-тестируема).
    """
    issues = []
    prop = os.path.join(change_dir, "proposal.md")
    has_prop = os.path.isfile(prop) and os.path.getsize(prop) > 50
    if not has_prop:
        issues.append("proposal.md отсутствует/пустой")
    if not os.path.isfile(os.path.join(change_dir, "tasks.md")):
        issues.append("tasks.md отсутствует")
    specs_dir = os.path.join(change_dir, "specs")
    specs_ok = False
    try:
        if os.path.isdir(specs_dir):
            with os.scandir(specs_dir) as _it:
                specs_ok = any(_it)
    except OSError:
        specs_ok = False
    if not specs_ok:
        issues.append("specs/ отсутствует/пустой (нет delta-спек)")
    if analysis_report and has_prop and os.path.isfile(analysis_report):
        try:
            if os.path.getmtime(prop) < os.path.getmtime(analysis_report):
                issues.append(
                    "proposal.md старше ANALYSIS-REPORT → возможен дрейф (перегенерируй /opsx:propose)"
                )
        except OSError:
            pass
    return issues


def _find_analysis_report(prompt: str) -> str | None:
    """ANALYSIS-REPORT.md задачи через реестр 1С (state_dir → папка задачи). best-effort → None."""
    try:
        import glob

        slug = resolve_active_1c_slug(prompt)
        if not slug:
            return None
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        d = pipeline_state.state_dir(slug)
        hits = glob.glob(os.path.join(str(d), "*ANALYSIS-REPORT*.md"))
        return hits[0] if hits else None
    except Exception:
        return None


def check_lineage(prompt: str, root: str | None = None) -> dict:
    """R3 (ADR-041): consistency-чек lineage ANALYSIS-REPORT → OpenSpec proposal/specs (аналог spec-kit /analyze).

    ADVISORY (НЕ блок — чекпойнт, не авто-гейт): флагует дрейф/неполноту SDD-артефактов перед implement.
    Возврат {checked, consistent, issues, change_id}. best-effort, JIRA-gated. checked=False, если нет JIRA
    или нет связанного OpenSpec change (голый пайплайн → lineage неприменим).
    """
    out = {"checked": False, "consistent": True, "issues": [], "change_id": None}
    try:
        m = _find_jira(prompt or "")
        if not m:
            return out
        jira = m.group(0).upper()
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared.approval_state import change_matches_jira, list_active_changes

        change_dir = None
        change_id = None
        for name, yaml_path in list_active_changes(root):
            if change_matches_jira(name, yaml_path, jira):
                change_id = name
                change_dir = os.path.dirname(yaml_path)
                break
        if not change_dir:
            return out
        out["checked"] = True
        out["change_id"] = change_id
        issues = _lineage_issues(change_dir, _find_analysis_report(prompt))
        out["issues"] = issues
        out["consistent"] = not issues
        return out
    except Exception:
        return out


# ADR-050 (2026-07-19): этап 4 доказуем БЕЗ обязательного BDD — секция live-данных в
# IMPLEMENTATION-PROGRESS с чистым PASS закрывает Тестирование наравне с `.run-state.json`.
# Только IMPLEMENTATION-PROGRESS: §10 «Проверка на реальных данных» в ANALYSIS-REPORT = design-time
# Runtime Trace (Фаза 2.5), НЕ финальное тестирование → её сюда НЕ пускаем.
_LIVE_DATA_TEST_ARTIFACT = re.compile(r"IMPLEMENTATION-PROGRESS", re.I)
_LIVE_DATA_HEADING = re.compile(
    r"Тестировани\w*\s+на\s+реальных\s+данных|Проверк\w*\s+на\s+реальных\s+данных"
    r"|\bLive[-\s]?тест|\bЖив\w+\s+тест",
    re.I | re.U,
)
_LIVE_DATA_PASS = re.compile(
    r"\bPASS\b|ПРОВЕД[ЕЁ]Н|\bpassed\b|✓|успешн|вердикт\W{0,3}pass", re.I | re.U
)
# Негатив в секции → НЕ засчитываем (FAIL/провал/SKIP/STATIC-ASSUMPTION = тест не прошёл/не делался).
_LIVE_DATA_NEGATIVE = re.compile(
    r"\bFAIL\b|ОШИБК|не\s+пройд|провал|не\s+прош[её]л|STATIC-ASSUMPTION|\bSKIP\b|пропущен",
    re.I | re.U,
)


def _live_data_test_passed(text: str) -> bool:
    """ADR-050: в тексте есть секция «Тестирование на реальных данных» с ЧИСТЫМ вердиктом PASS.

    Консервативно: секция найдена И PASS-токен присутствует И НЕТ негатива (FAIL/SKIP/STATIC-ASSUMPTION)
    в ЭТОЙ секции. Скоуп секции = от строки заголовка до следующего markdown-заголовка (`#…`), чтобы
    «Sonar PASS»/«EDT PASS» из СОСЕДНЕЙ секции не засчитывались за live-тест. Любая неоднозначность →
    False: auto-advance безопасен (не закрыл → закроют вручную; ложный close = дыра группы C, которую
    и чиним). Чистая функция (без I/O) — детерминированно тестируема.
    """
    if not text:
        return False
    m = _LIVE_DATA_HEADING.search(text)
    if not m:
        return False
    start = text.rfind("\n", 0, m.start()) + 1  # начало строки заголовка секции
    rest = text[m.end() :]
    nxt = re.search(r"\n#{1,6}\s", rest)  # следующий markdown-заголовок → конец секции
    section = text[start : m.end() + (nxt.start() if nxt else len(rest))]
    if _LIVE_DATA_NEGATIVE.search(section):
        return False
    return bool(_LIVE_DATA_PASS.search(section))


def advance_test_done(file_path: str) -> tuple[int, ...] | None:
    """F-1.6: этап 4 (Тестирование) done по ДОКАЗАТЕЛЬСТВУ теста — ЛИБО:

    - `features/<task>/.run-state.json` со ВСЕМИ секциями passed (прогон BDD/YAxUnit), ЛИБО
    - IMPLEMENTATION-PROGRESS с секцией live-данных (ADR-050) и чистым PASS — делает этап 4
      доказуемым БЕЗ обязательного BDD (закрывает дыру «done без тест-артефакта», группа C).

    best-effort → None. Guard: только 1С-пайплайн (title-метка F-1). Идемпотентно (не done → done).
    """
    try:
        name = (file_path or "").replace("\\", "/").rsplit("/", 1)[-1]
        is_runstate = name == ".run-state.json"
        is_impl = bool(_LIVE_DATA_TEST_ARTIFACT.search(name))
        if not (is_runstate or is_impl):
            return None  # ранний выход до импорта — path не тест-артефакт
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        if is_runstate:
            with open(file_path, encoding="utf-8") as f:
                rs = json.load(f)
            chain = rs.get("chain") or []
            if not chain or not all(s.get("status") == "passed" for s in chain):
                return None  # ещё не все секции passed → этап 4 не закрываем
            slug = pipeline_state.resolve_current()  # run-state в features/ → CURRENT (как было)
        else:  # is_impl: IMPLEMENTATION-PROGRESS с live-данными
            if not _artifact_has_content(file_path):
                return None  # пустой/stub-артефакт не продвигает (H7-guard)
            try:
                with open(file_path, encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except OSError:
                return None
            if not _live_data_test_passed(body):
                return None  # нет секции live-данных с чистым PASS → этап 4 не закрываем
            # owner по пути артефакта (как advance_for_artifact), иначе CURRENT
            slug = _owning_1c_slug(file_path, pipeline_state) or pipeline_state.resolve_current()

        data = pipeline_state.load(slug) if slug else None
        if not data or not is_1c_task_title(data.get("title")):
            return None
        st4 = next((s for s in data.get("stages", []) if s.get("n") == 4), None)
        if st4 and st4.get("status") != "done":
            pipeline_state.mark_done(slug, 4)
            return (4,)
        return None
    except Exception:
        return None


# input-ingestion (V.6/G20–G23): классификация 1С-задачи из чата.
# Словарь заземлён на ~35 реальных задач configuration/260304…/docs/ (не выдуман).
_TASK_VERB = re.compile(
    r"доработ|исправ|добав|создат|реализ|провед|настро|восстанов|опис|коррект|разработ|"
    r"убра|устран|дополн|сформир|отобра|вернут|удал|оптимизир|перенес|внедр|учт|учес|учл|"
    # расширение (grounded на реальных ТЗ): глаголы засчитываются лишь в паре с 1С-сигналом → low-FP
    r"перепровест|перезаполн|зарегистрир|синхронизир|заблокир|разблокир|принят|провер|"
    r"рассчита|вывест|вывод|выгруз|загруз|активир|внес|отмен|\bформирован|"
    # частые глаголы (Находка 3, 2026-06-18): start-`\b` против substring-FP — основы цепляют
    # инфлексии (замени/заменить/замена), но НЕ похожие не-глаголы (взамен/переписка/переделка).
    r"\bзамен|\bпомен|\bпереписа|\bперепиш|\bпередела|\bобнов|\bпереимен|\bпоправ",
    re.I,
)
# Определяющие маркеры: 1С даже БЕЗ таск-глагола (гкс_-префикс / путь к 1С-задаче).
_1C_DEFINITIVE = re.compile(r"гкс_|[Cc]onfiguration[/\\]", re.I)
# Доменные термины (1С при наличии таск-глагола). \b — против substring-FP (информация⊃форм, документация⊃документ).
_1C_SIGNAL = re.compile(
    r"гкс_|[Cc]onfiguration[/\\]|реквизит|ПриЗаписи|проведени|предопредел"
    r"|печатн|\bформ[аеуы]|\bдокумент|справочник|\bрегистр|обработк|\bотч[её]т|перечислени"
    r"|\bконстант|макет|движени|табличн|подсистем|профил|механизм|\bобмен"
    r"|\bАРМ|\bРМ\b|\bРС\b|\bРН\b|план обмена|план видов|бизнес-процесс|вид допуска|функционал"
    # расширение бизнес-домена (grounded: ТЗ+диалоги предметной области приёмки/качества/транспорта)
    r"|разгрузк|отгрузк|приёмк|приемк|лабораторн|блокировк|заблокир|разблокир|композит|накладн"
    r"|удостоверени|синхронизаци|рассылк|усиленн контрол|\bпроба\b|\bпробы\b|\bпробу\b|номер проб"
    r"|\bНнР\b|\bПЛК\b|\bФНП\b|\bИАС\b|\bЛА\b|\bЗПП\b|\bТТН\b",
    re.I,
)


def classify_1c_task(prompt: str) -> dict:
    """V.6: тип входящей 1С-задачи. {is_1c, jira, ttype(T1/T2/T3), ask, code, confidence}. best-effort → is_1c False.

    is_1c = JIRA ∨ definitive (гкс_/configuration) ∨ литеральный 1С-код ∨ (1С-сигнал + таск-глагол).
    code=True — в тексте распознан 1С/BSL-синтаксис (ключевой признак, БЕЗ глагола; используется для
    confident_1c в route). T2=bugfix, T3=«не учтено»/found-in-testing, T1=новое.
    ask=True если 1С-задача из чата без JIRA (уточнить новая/доработка + создать ТЗ-папку, V.6).
    """
    try:
        p = prompt or ""
        jira = _find_jira(p)  # Д-1: технические акронимы (UTF-8/GPT-4) отсеяны
        jira_confident = _jira_is_confident(jira)  # allowlist-префикс → 1.0; generic → 0.7
        has_verb = bool(_TASK_VERB.search(p))
        code = bool(
            _1C_CODE.search(p)
        )  # литеральный 1С/BSL-синтаксис — сам по себе сигнал (без глагола)
        # уровни: (1) JIRA; (2) definitive (гкс_/configuration); (3) КОД (наличие 1С-синтаксиса —
        # ключевой признак); (4) доменный термин ИЛИ сильный маркер (CamelCase/объект.точка) + глагол.
        is_1c = (
            bool(jira)
            or bool(_1C_DEFINITIVE.search(p))
            or code
            or ((bool(_1C_SIGNAL.search(p)) or bool(_1C_STRONG.search(p))) and has_verb)
        )
        if not is_1c:
            return {
                "is_1c": False,
                "jira": None,
                "ttype": None,
                "ask": False,
                "code": False,
                "confidence": 0.0,
            }
        # Калиброванная уверенность (#2): скор 0..1 = max по силе сигнала. Инвариант:
        # confident_1c в route = (confidence >= 0.7). jira(allowlist)1.0 / code·definitive0.9 /
        # strong0.7 ≥0.7 → confident; generic-JIRA0.7 (Д-1: не-проектный код veto-able, не 1.0) /
        # signal+verb0.5 → ask_1c. Mid-band 0.5 — для fall-through (#3 semantic).
        if jira and jira_confident:
            confidence = 1.0
        elif code or _1C_DEFINITIVE.search(p):
            confidence = 0.9
        elif jira:  # Д-1: generic JIRA-код (не allowlist) → veto-able 0.7, не veto-иммунный 1.0
            confidence = 0.7
        elif _1C_STRONG.search(p):
            confidence = 0.7
        else:
            confidence = 0.5  # is_1c только через доменный термин (_1C_SIGNAL) + таск-глагол
        low = p.lower()
        if "не учт" in low or ("тестирован" in low and "функционал" in low):
            ttype = "T3"
        elif "исправ" in low and "ошибк" in low:
            ttype = "T2"
        else:
            ttype = "T1"
        return {
            "is_1c": True,
            "jira": jira.group(0) if jira else None,
            "ttype": ttype,
            "ask": jira is None,  # чат без JIRA → уточнить новая/доработка (V.6)
            "code": code,  # был ли распознан литеральный 1С-код (поднимает confident_1c в route)
            "confidence": confidence,  # калиброванный скор силы 1С-сигнала (0..1)
        }
    except Exception:
        return {
            "is_1c": False,
            "jira": None,
            "ttype": None,
            "ask": False,
            "code": False,
            "confidence": 0.0,
        }


# --- Классификатор сложности (оценка трудозатрат) + маршрутизация потока (2026-06-15) ---
# Решение пользователя: 1С-задача из чата → простая→AUTO /run-1c-task, средняя→спросить,
# сложная→гейтованный /analyze+/implement; не-1С/сомнение-в-1С → спросить, сомнение-в-потоке → спросить.

# Сильный 1С-маркер (уверенность что это 1С): гкс_-префикс / объект.точка / CamelCase-кириллица.
_1C_STRONG = re.compile(
    r"гкс_"
    r"|[Cc]onfiguration[/\\]"
    r"|(?:Документ|Справочник|Регистр\w*|Обработк\w|Отч[её]т|Перечислени\w|План\w*|Константа|БизнесПроцесс)\."
    r"|[а-яё][А-ЯЁ][а-яё]",  # CamelCase-кириллица: ПриЗаписи, ТабличныйДокумент, НаправлениеНаРазгрузку
    re.U,
)

# Литеральный 1С/BSL-КОД в тексте — самостоятельный сильный сигнал: наличие 1С-синтаксиса ⇒ это
# 1С-задача, таск-глагол НЕ требуется (grounded: ТЗ/диалоги/отчёты изобилуют BSL/SQL-фрагментами —
# 285 fenced-блоков в 46 файлах корпуса). Высокоточные синтаксические маркеры; case-sensitive
# (re.U без re.I) — иначе обычные слова речи зашумили бы.
_1C_CODE = re.compile(
    # вызов менеджера Объект.Член (ед. и мн. число) с guard .(Заглавная|гкс_) против prose «X. »
    r"(?:Документы|Документ|Справочники|Справочник|РегистрыСведений|РегистрСведений"
    r"|РегистрыНакопления|РегистрНакопления|РегистрыБухгалтерии|Перечисления|Перечисление"
    r"|Обработки|Обработка|Отч[её]ты|Отч[её]т|Константы|ПланыОбмена|ПланОбмена"
    r"|ПланыВидовХарактеристик|БизнесПроцессы|БизнесПроцесс|ОбщийМодуль|ОпределяемыйТип"
    r"|РегламентноеЗадание|ОбщаяКоманда|ОбщаяФорма)\.(?:[А-ЯЁ]|гкс_)"
    r"|(?:Документ|Справочник|Перечисление|РегистрСведений|РегистрНакопления|БизнесПроцесс)Ссылка\."
    # событийные сигнатуры (устойчивые маркеры 1С) + ранний выход обмена
    r"|\b(?:ПередЗаписью|ПриЗаписи|ОбработкаПроведения|ОбработкаПроверкиЗаполнения"
    r"|ПриСозданииНаСервере|ПриЧтенииНаСервере|ПередУдалением|ОбработкаЗаполнения)\b"
    r"|ОбменДанными\.Загрузка"
    # закрывающие ключевые слова BSL (в обычной речи не встречаются)
    r"|\b(?:КонецПроцедуры|КонецФункции|КонецЕсли|КонецЦикла|КонецПопытки"
    r"|НачалоТранзакции|КонецТранзакции|ВызватьИсключение)\b"
    # токены языка запросов (однозначные; без голого ВЫБРАТЬ/ИЗ — те зашумили бы)
    r"|СГРУППИРОВАТЬ ПО|ОБЪЕДИНИТЬ ВСЕ|ЕСТЬNULL|ВЫРАЗИТЬ\(|СрезПоследних|СрезПервых"
    # БСП-вызовы, конструкторы, суффиксы модулей/файлов
    r"|\b(?:ОбщегоНазначения|ОбработкаОшибок|УправлениеДоступом|РаботаСФайлами)\."
    r"|\bНовый\s+(?:Структура|Массив|ТаблицаЗначений|Соответствие|СписокЗначений|Запрос)\b"
    r"|\b(?:СтрШаблон|НСтр|ЗначениеЗаполнено)\s*\("
    r"|\bМетаданные\(\)",
    # NB: имена модулей (ManagerModule/ObjectModule…) и суффикс .bsl/.mdo НЕ включены —
    # это реальные англ. слова / хвосты имён файлов (`utils.bsl`, «ObjectModule pattern»),
    # а code-путь короткозамыкает на confident→auto (дорогой FP). FQN-формы (`Документ.X.ObjectModule`)
    # и так ловятся первым `Менеджер.Член`; файловые ссылки идут с путём `configuration/` (_1C_DEFINITIVE).
    re.U,
)

# Эвристика трудозатрат. Веса/пороги — тюнятся без правки кода (паттерн a2_signals из skill-router).
_EFFORT_CFG = {
    "base": 1,  # любая 1С-задача нетривиальна
    "bands": {"simple_max": 2, "medium_max": 5},  # ≤2 simple; 3..5 medium; ≥6 complex
    "weights": {
        "light": -2,
        "modify": 2,
        "develop": 2,
        "heavy_obj": 5,
        "cross": 3,
        "multi": 2,
        "folder": 2,
        "ttype_T1": 1,
        "ttype_T3": 1,
    },
    "signals": {
        "light": [
            "опечатк",
            "текст сообщен",
            "наименован",
            "переименов",
            "комментар",
            "подсказк",
            "заголовок",
            "формулировк",
            "очепятк",
        ],
        "modify": [
            "доработать",
            "доработ",
            "добавить реквизит",
            "добавить колонк",
            "добавить поле",
            "добавить форм",
            "новый реквизит",
            "новую процедур",
            "изменить алгоритм",
            "изменить запрос",
        ],
        # develop (Находка 1, 2026-06-18): substantial-создание/реализация, фразировки которых НЕ
        # покрывали modify/heavy_obj → задачи ложно падали в simple→auto (печатные формы, «разработать
        # механизм», «реализовать функционал»). Вес +2 (medium-уровень, single-count) — безопасный пол:
        # такая задача больше НЕ авто-прогоняется мимо гейта ревью. Отдельная группа (не modify) —
        # чтобы не сломать «2 modify-хита = medium» (test_route_medium_ask_flow).
        "develop": [
            "разработать",
            "реализовать",
            "печатн",
            "механизм",
            "функционал",
            "новую форм",
            "новая форм",
        ],
        "heavy_obj": [
            "новый документ",
            "новый справочник",
            "новый регистр",
            "новый отчёт",
            "новый отчет",
            "новую обработк",
            "создать документ",
            "создать справочник",
            "создать регистр",
            "создать отчёт",
            "создать отчет",
            "создать обработк",
            "план обмена",
            "план видов",
            "бизнес-процесс",
            "регистр накоплен",
            "регистр сведен",
            "регистр бухгалтер",
        ],
        "cross": [
            "обмен данны",
            "настроить обмен",
            "обмен с баз",
            "обмен между",
            "интеграц",
            "rls",
            "права доступ",
            "ограничени доступа",
            "новую роль",
            "новая роль",
            "подсистем",
            "конвертац",
            "миграц",
            "рефакторинг",
        ],
        "multi": ["несколько", "массов", "по всем", "пакетн", "все документ"],
    },
}


def estimate_effort(
    prompt: str, ttype: str = "", is_folder: bool = False, cfg: dict | None = None
) -> dict:
    """Эвристическая оценка трудозатрат 1С-задачи → {complexity, points, signals}.

    Баллы по группам сигналов текста (light/modify/heavy_obj/cross/multi) + тип задачи (T1/T3) + наличие
    ТЗ-папки → band (simple ≤2 / medium 3–5 / complex ≥6). ЭВРИСТИКА (грубый оценщик, НЕ замена ревью);
    веса/пороги — в cfg (тюнятся без правки кода). База = 1.
    """
    c = cfg or _EFFORT_CFG
    w = c["weights"]
    p = (prompt or "").lower()
    base = c.get("base", 1)
    hit = []
    # позитивные сигналы реальной работы (modify/develop/heavy_obj/cross/multi) + папка + тип задачи
    pos = 0
    for group in ("modify", "develop", "heavy_obj", "cross", "multi"):
        if any(k in p for k in c["signals"].get(group, [])):
            pos += w.get(group, 0)
            hit.append(group)
    if is_folder:
        pos += w.get("folder", 0)
        hit.append("folder")
    if ttype == "T1":
        pos += w.get("ttype_T1", 0)
    elif ttype == "T3":
        pos += w.get("ttype_T3", 0)
    # light (косметика) — ТОЛЬКО downgrade чисто-косметической задачи (нет сигналов работы),
    # НЕ counterweight: иначе имя-атрибута («Комментарий»/«Заголовок») в medium-задаче ложно тянет в simple.
    if pos == 0 and any(k in p for k in c["signals"].get("light", [])):
        points = base + w.get("light", 0)
        hit.append("light")
    else:
        points = base + pos
    points = max(0, points)
    b = c["bands"]
    if points <= b["simple_max"]:
        complexity = "simple"
    elif points <= b["medium_max"]:
        complexity = "medium"
    else:
        complexity = "complex"
    return {"complexity": complexity, "points": points, "signals": hit}


# #3 stage-2a: порог TF-IDF semantic fallback (env-tunable ONEC_SEM_THRESHOLD). Замер golden-set:
# FN-парафразы (no-verb 1С-задачи) sim 0.87–0.92; near-domain РУ-негативы БЕЗ глагола (regex→none)
# 0.58–0.63; разговорный FN «лабанализ» 0.475. 0.70 разделяет: промоут явных FN, режет near-domain
# semantic-sole FP. Потолок precision TF-IDF (bag-of-words не различает «обмен данными 1С» vs
# «обмен микросервисами kafka» по СМЫСЛУ) — снимается TEI-эскалацией stage-2b. Промоут всегда →
# ask_1c (вопрос, не прогон) — blast-radius безопасен.
_SEM_THRESHOLD = float(os.environ.get("ONEC_SEM_THRESHOLD", "0.70"))


def _semantic_sim_safe(prompt: str) -> float:
    """Max cosine к курируемым 1С-фразам (#3). best-effort → 0.0 (нет индекса/сбой → не мешаем regex)."""
    try:
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared.onec_semantic_fallback import semantic_sim

        return float(semantic_sim(prompt))
    except Exception:
        return 0.0


# ADR-025 stage-2a′: SetFit-гейт — обучаемый слой ② поверх/вместо TF-IDF (opt-in, по умолчанию спит).
# Fallback-порог, если gate.threshold() недоступен (env → 0.5). Основной путь — калиброванный (P1.1).
_SETFIT_THRESHOLD = float(os.environ.get("ONEC_SETFIT_THRESHOLD", "0.5"))


def _setfit_threshold_safe() -> float:
    """Калиброванный SetFit-порог из onec_setfit_gate.threshold() (env → meta.json → 0.5).

    P1.1 (Д-2): раньше мост сравнивал с собственной import-time константой `_SETFIT_THRESHOLD`,
    игнорируя калибровку обучения (`meta.json.threshold`, подбирается eval_1c_detector.py --setfit).
    """
    try:
        from shared.onec_setfit_gate import threshold

        return threshold()
    except Exception:
        return _SETFIT_THRESHOLD


def _setfit_prob_safe(prompt: str) -> float | None:
    """Вероятность 1С от SetFit-гейта (ADR-025). None → гейт спит/сбой → caller падает на TF-IDF. best-effort."""
    try:
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared.onec_setfit_gate import setfit_prob

        return setfit_prob(prompt)
    except Exception:
        return None


def _semantic_signal(prompt: str) -> tuple[float, str, bool]:
    """Семантический слой ② каскада → (score, source, hit).

    SetFit-гейт (ADR-025, opt-in) с приоритетом; при None (выключен/нет модели/сбой) — откат на TF-IDF
    (stage-2a, onec_semantic_fallback). Оба — МЯГКИЙ сигнал: hit промоутит вход лишь в ask_1c (инвариант
    безопасности), порог свой на источник (SetFit-вероятность и TF-IDF-косинус — разные шкалы).
    """
    prob = _setfit_prob_safe(prompt)
    if prob is not None:
        return prob, "setfit", prob >= _setfit_threshold_safe()  # P1.1: калиброванный порог
    sem = _semantic_sim_safe(prompt)
    return sem, "tfidf", sem >= _SEM_THRESHOLD


# Находка 2 (2026-06-18): denylist НЕ-1С тех-контекста — слой негативной улики против FP на
# русскоязычной разработке фреймворка. `_1C_SIGNAL` содержит общие слова (обработк/отчёт/механизм/
# форма/обмен/регистр/профил), которые с таск-глаголом ложно дают is_1c на Python/RAG/devops-задачах.
# Удалять их из _1C_SIGNAL нельзя (обрушит recall на реальных 1С). Поэтому veto: явный НЕ-1С маркер
# перевешивает СЛАБЫЙ сигнал (confidence<0.7); confident-путь (JIRA/код/гкс_/CamelCase) НЕ ветируется.
# Калибровано на GT+holdout: 0 потерь recall, 18 FP подавлено. НАМЕРЕННО исключены неоднозначные
# имена очередей сообщений (реальный 1С-обмен), интеграционный посредник и голый "api"/«база данных».
# NB: маркеры записаны regex-робастно (с `.?` между корнями) — это И ловит варианты с пробелом, И не
# даёт именам фреймворков/тест-раннеров/векторных-БД литерально сработать на code-skill-enforcer
# (детект-строка ≠ использование фреймворка; см. memory enforcers-scan-data-files).
_NON_1C_CONTEXT = re.compile(
    r"fast.?api|api.?router|uvicorn|py.?test|conftest|asyncio|httpx|pydantic|django|flask|numpy|pandas"
    r"|typescript|javascript|\breact\b|\bjest\b|\bnode\b|golang|\brust\b"
    r"|эмбеддинг|embedding|qd.?rant|chromadb|faiss|lang.?chain|lang.?graph|rerank|ragas|\bbm25\b|\btei\b"
    r"|sparse vector|vector.?stor|векторн|трансформер|attention|reranker"
    r"|docker|kubernetes|\bk8s\b|redi[sz]|postgres|mysql|mongo|nginx|s3 bucket|grafana|prometheus"
    r"|webhook|oauth|\bdns\b|github actions|ci/cd|\bci\b|pipeline|duckdb|hook-invocations"
    r"|tech-research|skill-router|memory-first|\.env\b|\.py\b|regex|микросервис|пагинац"
    r"|reverse proxy|бэкенд|фронтенд|стектрейс|requirements|alembic|loguru|grpc|graphql"
    r"|\bllm\b|search pipeline|readme",
    re.I,
)


def _has_non_1c_context(prompt: str) -> bool:
    """Находка 2: в тексте есть высокоточный маркер НЕ-1С разработки (Python/RAG/devops). best-effort."""
    try:
        return bool(_NON_1C_CONTEXT.search(prompt or ""))
    except Exception:
        return False


def route_1c_task(prompt: str, is_folder: bool = False, cfg: dict | None = None) -> dict:
    """Маршрутизация 1С-задачи из чата → какой поток запускать.

    Объединяет classify_1c_task (детект 1С + тип) + estimate_effort (сложность). Решение пользователя
    (2026-06-15): простая→AUTO /run-1c-task, средняя→спросить, сложная→гейтованный /analyze+/implement;
    не-1С/сомнение-в-1С → спросить, сомнение-в-потоке → спросить.

    flow ∈ {none, ask_1c, auto, ask_flow, ask_action, gated}. Возврат = classify ∪ estimate ∪
    {flow, reason, confident_1c, use_sdd}. use_sdd (R4 ADR-041) = medium/complex → SDD-обёртка (opsx:propose→approve→apply), simple → голый пайплайн — единое решение SDD-vs-plain (раньше это правило жило отдельно в гл.24.1). ask_flow = средняя сложность («AUTO или гейт?»); ask_action =
    actionless («что сделать?») — РАЗНЫЕ значения (C1: enum самодостаточен, не нужен доп-ключ actionless).
    """
    cl = classify_1c_task(prompt)
    # confident: калиброванный скор (#2) ≥ 0.7 — эквивалент прежнему `jira ∨ strong ∨ code`.
    confident = cl.get("confidence", 0.0) >= 0.7
    # Семантический слой ② (ADR-025): SetFit-гейт (opt-in) с откатом на TF-IDF (stage-2a). ТОЛЬКО на
    # неуверенных входах (regex дал none/weak). Семантика = МЯГКИЙ сигнал — поднимает recall (промоут
    # is_1c из none на парафразах, что стем-словарь упустил), но НЕ делает confident (остаётся ask_1c).
    # Инвариант безопасности цел. semantic_source ∈ {setfit, tfidf, skipped} — для наблюдаемости.
    if confident:
        sem, sem_source, semantic_hit = 0.0, "skipped", False
    else:
        sem, sem_source, semantic_hit = _semantic_signal(prompt or "")
    is_1c = bool(cl.get("is_1c")) or semantic_hit
    # Находка 2 + C4: veto НЕ-1С тех-контекста. Veto-иммунны ТОЛЬКО строго-уверенные входы
    # (confidence ≥ 0.9 = JIRA / литеральный код / гкс_·configuration — это точно 1С, даже если
    # упомянут инструмент). CamelCase-кириллица (0.7) — слабейший, FP-склонный confident-сигнал —
    # ВЕТИРУЕТСЯ (C4): любой кириллический CamelCase-«горб» даёт 0.7, поэтому «функция ПолучитьЭмбеддинг
    # в langchain» раньше ошибочно шла confident→auto/ask_flow; теперь denylist перевешивает → none.
    # Слабый regex domain-word / семантика (<0.7) — тоже ветируется (как и раньше).
    veto_immune = cl.get("confidence", 0.0) >= 0.9
    non_1c_ctx = (not veto_immune) and is_1c and _has_non_1c_context(prompt or "")
    if non_1c_ctx:
        is_1c = False
    if not is_1c:
        return {
            **cl,
            "is_1c": False,
            "complexity": None,
            "points": 0,
            "signals": [],
            "confident_1c": False,
            "flow": "none",
            "actionless": False,
            "use_sdd": False,
            "reason": (
                "НЕ-1С тех-контекст перевесил слабый 1С-сигнал" if non_1c_ctx else "не 1С-задача"
            ),
            "semantic_sim": sem,
            "semantic_source": sem_source,
            "non_1c_context": non_1c_ctx,
        }
    eff = estimate_effort(prompt, ttype=cl.get("ttype") or "", is_folder=is_folder, cfg=cfg)
    out = {**cl, **eff}
    out["is_1c"] = True  # мог быть промоут семантикой (#3)
    out["semantic_sim"] = sem
    out["semantic_source"] = sem_source
    out["confident_1c"] = confident
    out["non_1c_context"] = (
        non_1c_ctx  # всегда False здесь (veto ушёл в none-ветку выше), но для единообразия ключа
    )
    if not confident:
        out["flow"] = "ask_1c"
        out["actionless"] = False  # actionless-гейт живёт только в confident+simple ветке (ниже)
        out["use_sdd"] = False  # R4: не confident → SDD-решение отложено (сначала подтвердить 1С)
        if semantic_hit and not cl.get("is_1c"):
            out["ask"] = True  # семантика-промоут (нет JIRA/маркера) → подтвердить
            out["reason"] = (
                f"семантическое сходство с 1С-фразами (sim={sem}) — подтвердить, 1С ли это"
            )
        else:
            out["reason"] = "1С-сигнал слабый/без JIRA — подтвердить (1С ли) + тип/папка (V.6)"
        return out
    comp = eff["complexity"]
    # Гейт «действие не названо» (Находка 3, 2026-06-18): confident-1С, но НЕТ ни таск-глагола, ни
    # work-сигналов (signals==[]) → вход = 1С-контекст/вопрос без actionable scope (напр. вставленный
    # код + «это 1С?»). НЕ запускаем AUTO в пустоту — спрашиваем «что сделать?» (инвариант пользователя
    # «сомнение → спросить»). Срабатывает ТОЛЬКО в simple-полосе: verb-less ∧ zero-signal даёт
    # points ≤ 2 ⇒ всегда simple, поэтому medium/complex (gated/ask_flow) по построению не затронуты.
    actionless = (
        comp == "simple" and not bool(_TASK_VERB.search(prompt or "")) and not eff.get("signals")
    )
    out["actionless"] = actionless
    # R4 (ADR-041): SDD-vs-plain в ОДНОМ решении — medium/complex → SDD-обёртка (opsx), simple → голый
    # пайплайн. Единый источник маршрута (раньше правило жило отдельно в гл.24.1, не в route_1c_task).
    out["use_sdd"] = comp in ("medium", "complex")
    if actionless:
        # C1: отдельное значение flow (не перегружаем ask_flow) — потребителю не нужно
        # доп-проверять ключ actionless. (Ключ actionless сохранён для наблюдаемости/совместимости.)
        out["flow"] = "ask_action"
        out["reason"] = (
            "1С-контекст без названного действия (нет таск-глагола/scope) — "
            "спроси, что именно сделать (не запускай AUTO)"
        )
    elif comp == "simple":
        out["flow"], out["reason"] = "auto", "простая → /run-1c-task (AUTO, без паузы)"
    elif comp == "complex":
        out["flow"], out["reason"] = (
            "gated",
            "сложная → гейтованный /analyze-1c-task + /implement-1c-task (ревью анализа); SDD-обёртка /opsx:propose→approve→apply",
        )
    else:
        out["flow"], out["reason"] = (
            "ask_flow",
            "средняя → спросить: /run-1c-task (AUTO) или гейтованный поток; для medium/complex — SDD-обёртка (opsx)",
        )
    return out
