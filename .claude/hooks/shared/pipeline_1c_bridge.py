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


_1C_TITLE_PREFIX = "1С-задача ("  # формат ensure_pipeline_1c / run-1c-task: f"1С-задача ({command}): {slug}"


def is_1c_task_title(title) -> bool:
    """Единый предикат «pipeline реальной 1С-задачи» (N4: убирает дубль/рассинхрон префикса в 6 местах).

    Строго ``startswith("1С-задача (")`` (с открывающей скобкой) — исключает framework-lookalike
    «1С-задача из чата: …». Используется в guard'ах моста И в Stop-gate (onec-task-completion-stop).
    """
    return str(title or "").startswith(_1C_TITLE_PREFIX)


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

        slug = derive_slug(prompt)
        pipeline_state.init_task(slug, title=f"1С-задача ({command}): {slug}", task_dir=task_dir)  # идемпотентно
        return slug
    except Exception:
        return None  # никогда не ломаем preflight


# ADR-019 F-1.5: запись 1С-артефакта → продвижение этапов CURRENT 1С-пайплайна.
_ARTIFACT_STAGES = [
    (re.compile(r"ANALYSIS-REPORT", re.I), (1, 2)),        # analyze → Планирование + Дизайн
    (re.compile(r"IMPLEMENTATION-PROGRESS", re.I), (3,)),  # implement → Кодирование
]
_ARTIFACT_MIN_CHARS = 200  # H7: порог непробельных символов против false-advance на пустом/stub-артефакте


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

        slug = pipeline_state.resolve_current()
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

        slug = derive_slug(prompt)
        data = pipeline_state.load(slug)
        if not data or not is_1c_task_title(data.get("title")):
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
    r"убра|устран|дополн|сформир|отобра|вернут|удал|оптимизир|перенес|внедр|учт|учес|учл",
    re.I,
)
# Определяющие маркеры: 1С даже БЕЗ таск-глагола (гкс_-префикс / путь к 1С-задаче).
_1C_DEFINITIVE = re.compile(r"гкс_|[Cc]onfiguration[/\\]", re.I)
# Доменные термины (1С при наличии таск-глагола). \b — против substring-FP (информация⊃форм, документация⊃документ).
_1C_SIGNAL = re.compile(
    r"гкс_|[Cc]onfiguration[/\\]|реквизит|ПриЗаписи|проведени|предопредел"
    r"|печатн|\bформ[аеуы]|\bдокумент|справочник|\bрегистр|обработк|\bотч[её]т|перечислени"
    r"|\bконстант|макет|движени|табличн|подсистем|профил|механизм|\bобмен"
    r"|\bАРМ|\bРМ\b|\bРС\b|\bРН\b|план обмена|план видов|бизнес-процесс|вид допуска|функционал",
    re.I,
)


def classify_1c_task(prompt: str) -> dict:
    """V.6: тип входящей 1С-задачи. {is_1c, jira, ttype(T1/T2/T3), ask}. best-effort → is_1c False.

    is_1c = JIRA-код ИЛИ (1С-сигнал + таск-глагол). T2=bugfix, T3=«не учтено»/found-in-testing, T1=новое.
    ask=True если 1С-задача из чата без JIRA (уточнить новая/доработка + создать ТЗ-папку, V.6).
    """
    try:
        p = prompt or ""
        jira = _JIRA.search(p)
        has_verb = bool(_TASK_VERB.search(p))
        # двухуровнево: definitive (гкс_/configuration) — 1С даже без таск-глагола;
        # доменный термин ИЛИ сильный маркер (CamelCase/объект.точка) + таск-глагол — 1С.
        is_1c = (
            bool(jira)
            or bool(_1C_DEFINITIVE.search(p))
            or ((bool(_1C_SIGNAL.search(p)) or bool(_1C_STRONG.search(p))) and has_verb)
        )
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

# Эвристика трудозатрат. Веса/пороги — тюнятся без правки кода (паттерн a2_signals из skill-router).
_EFFORT_CFG = {
    "base": 1,  # любая 1С-задача нетривиальна
    "bands": {"simple_max": 2, "medium_max": 5},  # ≤2 simple; 3..5 medium; ≥6 complex
    "weights": {
        "light": -2, "modify": 2, "heavy_obj": 5, "cross": 3, "multi": 2,
        "folder": 2, "ttype_T1": 1, "ttype_T3": 1,
    },
    "signals": {
        "light": ["опечатк", "текст сообщен", "наименован", "переименов", "комментар",
                  "подсказк", "заголовок", "формулировк", "очепятк"],
        "modify": ["доработать", "доработ", "добавить реквизит", "добавить колонк",
                   "добавить поле", "добавить форм", "новый реквизит", "новую процедур",
                   "изменить алгоритм", "изменить запрос"],
        "heavy_obj": ["новый документ", "новый справочник", "новый регистр", "новый отчёт",
                      "новый отчет", "новую обработк", "создать документ", "создать справочник",
                      "создать регистр", "создать отчёт", "создать отчет", "создать обработк",
                      "план обмена", "план видов", "бизнес-процесс", "регистр накоплен",
                      "регистр сведен", "регистр бухгалтер"],
        "cross": ["обмен данны", "интеграц", "rls", "права доступ", "ограничени доступа",
                  "новую роль", "новая роль", "подсистем", "конвертац", "миграц", "рефакторинг"],
        "multi": ["несколько", "массов", "по всем", "пакетн", "все документ"],
    },
}


def estimate_effort(prompt: str, ttype: str = "", is_folder: bool = False, cfg: dict | None = None) -> dict:
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
    # позитивные сигналы реальной работы (modify/heavy_obj/cross/multi) + папка + тип задачи
    pos = 0
    for group in ("modify", "heavy_obj", "cross", "multi"):
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


def route_1c_task(prompt: str, is_folder: bool = False, cfg: dict | None = None) -> dict:
    """Маршрутизация 1С-задачи из чата → какой поток запускать.

    Объединяет classify_1c_task (детект 1С + тип) + estimate_effort (сложность). Решение пользователя
    (2026-06-15): простая→AUTO /run-1c-task, средняя→спросить, сложная→гейтованный /analyze+/implement;
    не-1С/сомнение-в-1С → спросить, сомнение-в-потоке → спросить.

    flow ∈ {none, ask_1c, auto, ask_flow, gated}. Возврат = classify ∪ estimate ∪ {flow, reason, confident_1c}.
    """
    cl = classify_1c_task(prompt)
    if not cl.get("is_1c"):
        return {**cl, "complexity": None, "points": 0, "signals": [], "confident_1c": False,
                "flow": "none", "reason": "не 1С-задача"}
    eff = estimate_effort(prompt, ttype=cl.get("ttype", ""), is_folder=is_folder, cfg=cfg)
    out = {**cl, **eff}
    confident = bool(cl.get("jira")) or bool(_1C_STRONG.search(prompt or ""))
    out["confident_1c"] = confident
    if not confident:
        out["flow"] = "ask_1c"
        out["reason"] = "1С-сигнал слабый/без JIRA — подтвердить (1С ли) + тип/папка (V.6)"
        return out
    comp = eff["complexity"]
    if comp == "simple":
        out["flow"], out["reason"] = "auto", "простая → /run-1c-task (AUTO, без паузы)"
    elif comp == "complex":
        out["flow"], out["reason"] = "gated", "сложная → гейтованный /analyze-1c-task + /implement-1c-task (ревью анализа)"
    else:
        out["flow"], out["reason"] = "ask_flow", "средняя → спросить: /run-1c-task (AUTO) или гейтованный поток"
    return out
