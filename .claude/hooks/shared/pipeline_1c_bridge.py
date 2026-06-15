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


def derive_slug(prompt: str) -> str:
    """JIRA-код приоритетно (стабильный ID задачи между командами); иначе ASCII-slug."""
    m = _JIRA.search(prompt or "")
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
    m = _JIRA.search(a)
    if m:
        return {"kind": "jira", "slug": m.group(0), "folder": None}
    return {"kind": "chat", "slug": derive_slug(a), "folder": None}


def ensure_pipeline_1c(prompt: str, command: str) -> str | None:
    """Идемпотентно завести pipeline для 1С-задачи. Возврат slug | None (best-effort)."""
    try:
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        slug = derive_slug(prompt)
        pipeline_state.init_task(slug, title=f"1С-задача ({command}): {slug}")  # идемпотентно
        return slug
    except Exception:
        return None  # никогда не ломаем preflight


# ADR-019 F-1.5: запись 1С-артефакта → продвижение этапов CURRENT 1С-пайплайна.
_ARTIFACT_STAGES = [
    (re.compile(r"ANALYSIS-REPORT", re.I), (1, 2)),        # analyze → Планирование + Дизайн
    (re.compile(r"IMPLEMENTATION-PROGRESS", re.I), (3,)),  # implement → Кодирование
]


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
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        slug = pipeline_state.resolve_current()
        data = pipeline_state.load(slug) if slug else None
        if not data or not str(data.get("title", "")).startswith("1С-задача"):
            return None  # guard: только 1С-пайплайн (метка ensure_pipeline_1c)
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

        slug = derive_slug(prompt)
        data = pipeline_state.load(slug)
        if not data or not str(data.get("title", "")).startswith("1С-задача"):
            return {"ok": True, "hard": False, "reason": ""}  # нет 1С-пайплайна → no-op
        st2 = next((s for s in data.get("stages", []) if s.get("n") == 2), None)
        if st2 and st2.get("status") == "done" and st2.get("approved"):
            return {"ok": True, "hard": False, "reason": ""}  # дизайн одобрен → allow
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


def advance_test_done(file_path: str) -> tuple[int, ...] | None:
    """F-1.6: запись `features/<task>/.run-state.json` со ВСЕМИ секциями passed → этап 4 (Тестирование) done.

    best-effort → None. Guard: только 1С-пайплайн (title-метка F-1). Идемпотентно (не done → done).
    """
    try:
        name = (file_path or "").replace("\\", "/").rsplit("/", 1)[-1]
        if name != ".run-state.json":
            return None
        with open(file_path, encoding="utf-8") as f:
            rs = json.load(f)
        chain = rs.get("chain") or []
        if not chain or not all(s.get("status") == "passed" for s in chain):
            return None  # ещё не все секции passed → этап 4 не закрываем
        hooks = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if hooks not in sys.path:
            sys.path.insert(0, hooks)
        from shared import pipeline_state

        slug = pipeline_state.resolve_current()
        data = pipeline_state.load(slug) if slug else None
        if not data or not str(data.get("title", "")).startswith("1С-задача"):
            return None
        st4 = next((s for s in data.get("stages", []) if s.get("n") == 4), None)
        if st4 and st4.get("status") != "done":
            pipeline_state.mark_done(slug, 4)
            return (4,)
        return None
    except Exception:
        return None


# input-ingestion (V.6/G20–G23): классификация 1С-задачи из чата.
_TASK_VERB = re.compile(r"доработ|исправ|добав|создать|реализ|провед|настро", re.I)
_1C_SIGNAL = re.compile(r"гкс_|Документ\.|Справочник\.|РегистрСведений|реквизит|ПриЗаписи|проведени", re.I)


def classify_1c_task(prompt: str) -> dict:
    """V.6: тип входящей 1С-задачи. {is_1c, jira, ttype(T1/T2/T3), ask}. best-effort → is_1c False.

    is_1c = JIRA-код ИЛИ (1С-сигнал + таск-глагол). T2=bugfix, T3=«не учтено»/found-in-testing, T1=новое.
    ask=True если 1С-задача из чата без JIRA (уточнить новая/доработка + создать ТЗ-папку, V.6).
    """
    try:
        p = prompt or ""
        jira = _JIRA.search(p)
        is_1c = bool(jira) or bool(_1C_SIGNAL.search(p) and _TASK_VERB.search(p))
        if not is_1c:
            return {"is_1c": False, "jira": None, "ttype": None, "ask": False}
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
        }
    except Exception:
        return {"is_1c": False, "jira": None, "ttype": None, "ask": False}
