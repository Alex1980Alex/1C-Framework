#!/usr/bin/env python3
"""Pipeline state helper — generic 4-stage SDLC pipeline (ADR-017).

Backbone домен-агностичного пайплайна:
  Планирование архитектуры → Дизайн реализации → Кодирование → Тестирование

Каждый этап производит ОДИН артефакт (``pipeline/<task>/0N-*.md``); следующий
этап читает прошлый артефакт + делает свою работу. Состояние —
``pipeline/<task>/.pipeline-state.json``. Указатель ``pipeline/CURRENT`` хранит
активную задачу, чтобы stage-командам не передавать slug каждый раз.

Importable API (использует hook ``pipeline-gate.py``):
    load(slug=None), gate_check(command, slug=None), resolve_current(),
    artifact_path(command, slug=None), render_status(slug=None)

CLI (используют ``pl-*`` слэш-команды через Bash):
    python .../pipeline_state.py init <slug> [--title T]
    python .../pipeline_state.py done <slug|-> <stage_n> [artifact]
    python .../pipeline_state.py approve <slug|-> [--stage N] [--by who]
    python .../pipeline_state.py status [slug]
    python .../pipeline_state.py gate <command> [slug]   # → JSON {ok,hard,reason}

stdlib-only; безопасно импортировать из хуков (нет внешних зависимостей).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# .claude/hooks/shared/pipeline_state.py → parents[3] = repo root
PROJECT_ROOT = Path(__file__).resolve().parents[3]
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
CURRENT_PTR = PIPELINE_DIR / "CURRENT"
STATE_NAME = ".pipeline-state.json"
# Реестр 1С-задач: {slug: task_dir(rel-to-root POSIX)} — состояние 1С-пайплайна живёт В ПАПКЕ ЗАДАЧИ
# (configuration/<parent>/docs/<task>/), а не в generic pipeline/<slug>/. Generic-поток реестр не трогает.
REGISTRY_PTR = PIPELINE_DIR / "_1c_index.json"
_1C_TITLE_PREFIX = "1С-задача ("  # совпадает с pipeline_1c_bridge.is_1c_task_title (N4)

# Этапы — единый источник истины (команда ↔ этап ↔ артефакт).
STAGES = [
    {
        "n": 1,
        "name": "architecture",
        "command": "pl-plan",
        "artifact": "01-architecture.md",
        "title": "Планирование архитектуры",
        "delegates": "architecture-research",
    },
    {
        "n": 2,
        "name": "design",
        "command": "pl-design",
        "artifact": "02-design.md",
        "title": "Дизайн реализации",
        "delegates": "design-doc",
    },
    {
        "n": 3,
        "name": "implementation",
        "command": "pl-code",
        "artifact": "03-implementation.md",
        "title": "Кодирование",
        "delegates": "implementer",
    },
    {
        "n": 4,
        "name": "testing",
        "command": "pl-test",
        "artifact": "04-testing.md",
        "title": "Тестирование",
        "delegates": "code-verify",
    },
]
_BY_COMMAND = {s["command"]: s for s in STAGES}
PIPELINE_COMMANDS = tuple(s["command"] for s in STAGES)
APPROVAL_STAGE = 2  # дизайн человек одобряет перед кодированием (единственный hard-гейт)

# 1С-профиль этапов: имена артефактов = реальные файлы методики 1С (в папке задачи), а не generic 0N-*.md.
# Выбирается по title-маркеру `1С-задача (`. Этап 4 = `.run-state.json` (решение пользователя — в папке задачи).
STAGES_1C = [
    {"n": 1, "name": "planning", "command": "pl-plan", "artifact": "ANALYSIS-REPORT.md",
     "title": "Планирование архитектуры", "delegates": "analyze-1c-task-v2"},
    {"n": 2, "name": "design", "command": "pl-design", "artifact": "ANALYSIS-REPORT.md",
     "title": "Дизайн реализации", "delegates": "analyze-1c-task-v2"},
    {"n": 3, "name": "implementation", "command": "pl-code", "artifact": "IMPLEMENTATION-PROGRESS.md",
     "title": "Кодирование", "delegates": "implement-1c-task"},
    {"n": 4, "name": "testing", "command": "pl-test", "artifact": ".run-state.json",
     "title": "Тестирование", "delegates": "va-bdd-testing"},
]


def is_1c(title: str | None) -> bool:
    """1С-задача по title-маркеру (локальный prefix-чек — ядро не зависит от bridge)."""
    return str(title or "").startswith(_1C_TITLE_PREFIX)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _slugify(s: str) -> str:
    out = "".join(c if (c.isalnum() or c in "-_") else "-" for c in s.strip().lower())
    while "--" in out:
        out = out.replace("--", "-")
    return out.strip("-") or "task"


def _read_registry() -> dict:
    try:
        return json.loads(REGISTRY_PTR.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_registry(reg: dict) -> None:
    REGISTRY_PTR.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY_PTR.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(REGISTRY_PTR)  # атомарно


def _rel_to_root(task_dir: str | Path) -> str:
    """task_dir → POSIX-путь относительно репо (портабельно); вне репо — абсолютный."""
    p = Path(task_dir)
    try:
        return p.resolve().relative_to(PROJECT_ROOT).as_posix()
    except (ValueError, OSError):
        return p.as_posix()


def register_1c(slug: str, task_dir: str | Path) -> str:
    """Зарегистрировать 1С-задачу: состояние живёт в task_dir. Идемпотентно. Возврат — сохранённый rel-путь."""
    slug = _slugify(slug)  # симметрия с init_task — ключ реестра всегда нормализован
    rel = _rel_to_root(task_dir)
    reg = _read_registry()
    if reg.get(slug) != rel:
        reg[slug] = rel
        _write_registry(reg)
    return rel


def state_dir(slug: str) -> Path:
    """Каталог состояния slug: папка задачи (реестр 1С) либо generic pipeline/<slug>/."""
    td = _read_registry().get(_slugify(slug))
    if td:
        p = Path(td)
        return p if p.is_absolute() else (PROJECT_ROOT / p)
    return PIPELINE_DIR / _slugify(slug)


def is_registered(slug: str) -> bool:
    """slug — зарегистрированная 1С-задача (состояние в папке задачи)? Публичный предикат для внешних
    потребителей (напр. tool_usage_report) — без опоры на приватный _read_registry."""
    return _slugify(slug) in _read_registry()


def relocate_1c(slug: str, task_dir: str | Path) -> bool:
    """Перенести состояние 1С-задачи в папку задачи (relocate-on-artifact). Идемпотентно. True если перенёс.

    Порядок (каждый шаг атомарен через _save/_write_registry tmp+replace): прочитать состояние (из текущего
    расположения ИЛИ generic) → register (резолв переключается на task_dir) → _save в папку задачи → удалить
    старый generic-файл/папку. Сходимость при частичном крэше: если register прошёл, но _save не успел, generic
    ещё держит состояние → повторный relocate подхватит его из generic и до-мигрирует.
    """
    slug = _slugify(slug)
    new_rel = _rel_to_root(task_dir)
    if _read_registry().get(slug) == new_rel and (state_dir(slug) / STATE_NAME).exists():
        return False  # уже в папке задачи — no-op
    generic = PIPELINE_DIR / slug
    data = None
    for sp in (state_dir(slug) / STATE_NAME, generic / STATE_NAME):  # текущее, затем generic (crash-retry)
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
            break
        except (OSError, ValueError):
            continue
    register_1c(slug, task_dir)  # после этого state_dir(slug) == task_dir
    if data is not None:
        _save(slug, data)  # пишет в папку задачи
    try:
        gs = generic / STATE_NAME
        if generic != state_dir(slug) and gs.exists():  # generic ≠ цель → удалить осиротевший generic
            gs.unlink()
            if not any(generic.iterdir()):  # подчистить пустую pipeline/<slug>/ (не папку задачи)
                generic.rmdir()
    except OSError:
        pass
    return True


def _state_path(slug: str) -> Path:
    return state_dir(slug) / STATE_NAME


def iter_states():
    """Все пайплайны (slug, data): 1С из реестра (папки задач) + generic из pipeline/*/. Dedup по slug.

    Единый источник для прямых читателей (pipeline-protocol-stop, onec-task-completion-stop) — после
    переезда 1С-состояния в папку задачи generic-glob его уже не найдёт, поэтому энумерируем оба места.
    """
    seen = set()
    for slug, td in _read_registry().items():  # 1С: авторитетное расположение — папка задачи
        p = Path(td)
        sp = (p if p.is_absolute() else PROJECT_ROOT / p) / STATE_NAME
        try:
            data = json.loads(sp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        seen.add(slug)
        yield slug, data
    if PIPELINE_DIR.is_dir():
        for sf in PIPELINE_DIR.glob("*/.pipeline-state.json"):
            slug = sf.parent.name
            if slug in seen:
                continue
            try:
                data = json.loads(sf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            seen.add(slug)
            yield slug, data


def resolve_current() -> str | None:
    try:
        return CURRENT_PTR.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _resolve_slug(slug: str | None) -> str | None:
    if slug and slug not in ("-", "@current", "."):
        return slug
    return resolve_current()


def load(slug: str | None = None) -> dict | None:
    slug = _resolve_slug(slug)
    if not slug:
        return None
    try:
        return json.loads(_state_path(slug).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(slug: str, data: dict) -> None:
    p = _state_path(slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    data["updated_at"] = _now()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)  # атомарно


def _set_current(slug: str) -> None:
    PIPELINE_DIR.mkdir(parents=True, exist_ok=True)
    CURRENT_PTR.write_text(slug, encoding="utf-8")


def init_task(slug: str, title: str = "", task_dir: str | None = None) -> dict:
    slug = _slugify(slug)
    if task_dir and is_1c(title):
        register_1c(slug, task_dir)  # состояние сразу в папке задачи (kind=folder)
    existing = load(slug)
    if existing:  # идемпотентно — повторный init не затирает прогресс
        _set_current(slug)
        return existing
    now = _now()
    template = STAGES_1C if is_1c(title) else STAGES  # 1С-профиль: артефакты = реальные файлы методики
    stages = []
    for s in template:
        st = {
            "n": s["n"],
            "name": s["name"],
            "command": s["command"],
            "artifact": s["artifact"],
            "status": "pending",
            "completed_at": None,
        }
        if s["n"] == APPROVAL_STAGE:
            st.update({"approved": False, "approved_by": None, "approved_at": None})
        stages.append(st)
    data = {
        "task": slug,
        "title": title or slug,
        "created_at": now,
        "updated_at": now,
        "current_stage": 1,
        "stages": stages,
    }
    _save(slug, data)
    _set_current(slug)
    return data


def _stage(data: dict, n: int) -> dict | None:
    return next((st for st in data.get("stages", []) if st.get("n") == n), None)


def mark_done(slug: str | None, n: int, artifact: str | None = None) -> dict:
    slug = _resolve_slug(slug)
    data = load(slug)
    if not data:
        raise SystemExit(f"pipeline: нет состояния для '{slug}' (сначала init)")
    st = _stage(data, n)
    if not st:
        raise SystemExit(f"pipeline: нет этапа {n}")
    st["status"] = "done"
    st["completed_at"] = _now()
    if artifact:
        st["artifact"] = artifact
    # current_stage = первый незавершённый этап, иначе 5 (всё готово)
    data["current_stage"] = next((s["n"] for s in data["stages"] if s["status"] != "done"), 5)
    _save(slug, data)
    return data


def approve(slug: str | None, n: int = APPROVAL_STAGE, by: str = "human") -> dict:
    slug = _resolve_slug(slug)
    data = load(slug)
    if not data:
        raise SystemExit(f"pipeline: нет состояния для '{slug}'")
    st = _stage(data, n)
    if not st:
        raise SystemExit(f"pipeline: нет этапа {n}")
    st["approved"] = True
    st["approved_by"] = by
    st["approved_at"] = _now()
    _save(slug, data)
    return data


def gate_check(command: str, slug: str | None = None) -> dict:
    """Вернуть {'ok','hard','reason'} для входа в этап команды ``command``.

    Hard-гейт ТОЛЬКО для pl-code (дизайн done + approved). pl-design/pl-test —
    advisory (ok=False, hard=False), если артефакт предыдущего этапа отсутствует.
    pl-plan всегда разрешён (бутстрап пайплайна).
    """
    stage = _BY_COMMAND.get(command)
    if not stage:
        return {"ok": True, "hard": False, "reason": ""}
    n = stage["n"]
    if n == 1:
        return {"ok": True, "hard": False, "reason": ""}
    data = load(slug)
    if n == 3:  # pl-code — HARD-гейт всегда: дизайн завершён И одобрен (даже без пайплайна)
        design = _stage(data, APPROVAL_STAGE) if data else None
        if not (design and design.get("status") == "done"):
            reason = (
                "Нет активного пайплайна. Пройди /pl-plan → /pl-design (+approve), затем /pl-code."
                if not data
                else "Этап 2 (Дизайн) не завершён. Сначала /pl-design, затем approve."
            )
            return {"ok": False, "hard": True, "reason": reason}
        if not design.get("approved"):
            return {
                "ok": False,
                "hard": True,
                "reason": (
                    "Дизайн (02-design.md) не одобрен. Отревьюй артефакт и одобри: "
                    f"`python .claude/hooks/shared/pipeline_state.py approve {data['task']}`"
                ),
            }
        return {"ok": True, "hard": False, "reason": ""}
    # pl-design (2) / pl-test (4): advisory
    if not data:
        return {
            "ok": False,
            "hard": False,
            "reason": "Нет активного пайплайна. Начни с /pl-plan <задача>.",
        }
    prev = _stage(data, n - 1)
    if not (prev and prev.get("status") == "done"):
        art = prev["artifact"] if prev else "?"
        return {
            "ok": False,
            "hard": False,
            "reason": f"Этап {n - 1} ещё не завершён (артефакт {art} отсутствует) — "
            "продолжаю, но проверь порядок.",
        }
    return {"ok": True, "hard": False, "reason": ""}


def artifact_path(command: str, slug: str | None = None) -> Path | None:
    stage = _BY_COMMAND.get(command)
    data = load(slug)
    if not stage or not data:
        return None
    return state_dir(data["task"]) / stage["artifact"]


def render_status(slug: str | None = None) -> str:
    data = load(slug)
    if not data:
        return "Нет активного пайплайна (pipeline/CURRENT пуст). Начни с /pl-plan <задача>."
    lines = [
        f"Пайплайн: {data['task']} — {data.get('title', '')}",
        f"Текущий этап: {data['current_stage']}/4  (обновлён {data.get('updated_at', '')})",
    ]
    for st in data["stages"]:
        mark = {"done": "[x]", "pending": "[ ]"}.get(st["status"], "[?]")
        extra = ""
        if st["n"] == APPROVAL_STAGE:
            extra = " (одобрен)" if st.get("approved") else " (НЕ одобрен)"
        art = state_dir(data["task"]) / st["artifact"]
        missing = "" if art.exists() else " — файла нет"
        lines.append(f"  {mark} {st['n']}. {st['command']:8s} -> {st['artifact']}{extra}{missing}")
    return "\n".join(lines)


def _setup_io() -> None:
    # cp1251-console safe: и stdout (_emit), и stderr (SystemExit-сообщения mark_done/approve)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass


def _emit(obj: object) -> None:
    print(obj if isinstance(obj, str) else json.dumps(obj, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    _setup_io()
    ap = argparse.ArgumentParser(
        prog="pipeline_state", description="Generic 4-stage pipeline state"
    )
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="создать пайплайн для задачи")
    p.add_argument("slug")
    p.add_argument("--title", default="")
    p.add_argument("--task-dir", default=None, help="папка 1С-задачи (состояние ляжет туда, а не в pipeline/)")

    p = sub.add_parser("done", help="отметить этап завершённым")
    p.add_argument("slug", help="slug или '-' (текущий)")
    p.add_argument("stage", type=int)
    p.add_argument("artifact", nargs="?", default=None)

    p = sub.add_parser("approve", help="одобрить артефакт этапа (по умолч. дизайн)")
    p.add_argument("slug", help="slug или '-' (текущий)")
    p.add_argument("--stage", type=int, default=APPROVAL_STAGE)
    p.add_argument("--by", default="human")

    p = sub.add_parser("status", help="показать состояние пайплайна")
    p.add_argument("slug", nargs="?", default=None)

    p = sub.add_parser("gate", help="проверить гейт входа в этап → JSON")
    p.add_argument("command")
    p.add_argument("slug", nargs="?", default=None)

    args = ap.parse_args(argv)
    if args.cmd == "init":
        d = init_task(args.slug, args.title, task_dir=args.task_dir)
        _emit(f"init {d['task']} -> {state_dir(d['task'])}/ (CURRENT)")
        _emit(render_status(d["task"]))
    elif args.cmd == "done":
        d = mark_done(args.slug, args.stage, args.artifact)
        _emit(f"этап {args.stage} done; следующий {d['current_stage']}")
    elif args.cmd == "approve":
        approve(args.slug, args.stage, args.by)
        _emit(f"этап {args.stage} одобрен ({args.by})")
    elif args.cmd == "status":
        _emit(render_status(args.slug))
    elif args.cmd == "gate":
        _emit(gate_check(args.command, args.slug))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
