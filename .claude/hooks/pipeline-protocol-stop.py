#!/usr/bin/env python3
"""
Hook: pipeline-protocol-stop
Event: Stop
Matcher: (none)
Purpose: ADR-018 — hard-enforce обязательной пайплайн-парадигмы. Если в ЭТОЙ сессии
  были правки кода/файлов БЕЗ использования пайплайна (ни один
  `pipeline/<slug>/.pipeline-state.json` не обновлён за сессию) → block с инструкцией.
  Чистые вопросы (нет правок за сессию) → exempt (нет deadlock).

  Сигнал «была правка» — два независимых источника (ИЛИ):
    (a) PreToolUse Write/Edit в invocation-логе (`data/hook-invocations.jsonl`);
    (b) `_git_session_edit` — незакоммиченный файл, изменённый за сессию (git status +
        mtime). Закрывает пробел инструментов без PreToolUse-матчера (MultiEdit/NotebookEdit),
        НЕ трогая settings.json.

  Анти-deadlock: (1) opt-out env; (2) keyed на реальный Write-сигнал из invocation-лога
  (+ git-fallback с mtime-bound: pre-session грязь не считается); (3) graceful degradation
  (исключение/нет данных → allow); (4) выход всегда достижим — создать pipeline-артефакт
  и завершить снова.
Timeout: 8s
Opt-out: PIPELINE_PROTOCOL_DISABLE=1
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# R3 (ADR-034): унифицированный decision-log гейтов (best-effort, не ронять Stop-хук)
try:
    from shared.gate_policy import decision as _gp_decision
    from shared.gate_policy import log_decision as _gp_log
except Exception:

    def _gp_decision(*a, **k):
        return {}

    def _gp_log(*a, **k):
        return None


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INVOCATIONS = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
_TAIL_BYTES = 2_000_000  # ~5-6k последних записей (CloudEvents-конверт ~300-400 байт/строка)
# MultiEdit/NotebookEdit входят в набор «на будущее», но СЕЙЧАС не имеют PreToolUse-матчера
# в settings.json → их правки не логируются. Этот пробел закрывает второй сигнал
# `_git_session_edit` (git status + mtime >= старт сессии) — ловит файл-чейндж ЛЮБЫМ
# инструментом, не трогая settings.json. Когда матчер на них добавят — log-сигнал (a) заработает сам.
_WRITE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Единый предикат «вызов отклонён гардом» + расходуемое сопоставление — из
# scripts/tool_effectiveness.py (single-source с report-слоем tool-health, N-P4.3):
# один и тот же факт нужен обоим слоям, и разъехаться их определения не должны.
# sys.path.append, НЕ insert(0): insert шеделил бы одноимённые модули в хук-процессе.
try:
    _SCRIPTS_DIR = str(PROJECT_ROOT / "scripts")
    if _SCRIPTS_DIR not in sys.path:
        sys.path.append(_SCRIPTS_DIR)
    from tool_effectiveness import is_guard_block as _is_guard_block
    from tool_effectiveness import take_block as _take_block
except Exception:  # модуля нет → вычета нет, поведение прежнее (гейт не ослабляем)

    def _is_guard_block(_e: dict) -> bool:
        return False

    def _take_block(_blocks: list, _session: str, _ts: datetime) -> bool:
        return False


# Файлы, авто-пишущиеся Stop-цепочкой ПОСЛЕ нас (session-memory-save → docs/wiki/log.md),
# не считаем «правкой задачи»: иначе на повторном Stop-проходе git-сигнал ложно сработал бы
# в чистом вопросе. Пути нормализованы к forward-slash.
_GIT_SKIP = {"docs/wiki/log.md"}


def _parse_dt(s: str) -> datetime | None:
    """ISO → naive datetime (tz-agnostic): снимает offset, чтобы сравнения log-ts vs
    state-updated_at не падали TypeError при смешении naive/aware меток (fail-safe)."""
    try:
        dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _read_tail_lines() -> list[str]:
    try:
        with open(INVOCATIONS, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - _TAIL_BYTES))
            return f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _session_writes_and_start(sid: str) -> tuple[bool, datetime | None]:
    """(были_правки, время_старта_сессии) для sid из invocation-лога.

    **Правка = ФАКТ записи, а не намерение.** Правкой считается canonical Pre-запись
    Write/Edit (``category="tool_call"``, её пишет tool-invocation-logger), НЕ объяснённая
    block-записью энфорсера того же инструмента в той же сессии (±``BLOCK_MATCH_SEC``,
    расходуемое сопоставление 1:1 — один блок объясняет РОВНО один вызов, иначе одна
    блокировка «оправдала» бы серию реальных правок).

    Инцидент 2026-07-26: один Write, отклонённый ``TaskProtocolEnforcer``, оставил в логе
    12 Pre-записей — по одной на хук цепочки (блокирующий отдаёт ``decision:"block"``, при
    котором цепочка доходит до логгера) → гейт читал их как «были правки кода» и требовал
    пайплайн в сессии, где ни один файл не записан (git-дерево чистое). Тот же вычет, что
    ``blocked`` в tool-health (N-P4.3): отклонённый вызов не исполнялся ⇒ правки не было.

    Fail-closed: если canonical-записей в сессии нет вовсе (логгер отключён/не
    зарегистрирован на инструмент) либо их ``ts`` не парсится — считаем правкой, как
    раньше. Гейт не должен ослабнуть из-за пробела в телеметрии.
    """
    start: datetime | None = None
    canonical: list[tuple[str, datetime]] = []  # (tool, ts) — фактические вызовы
    blocks: dict[str, list[tuple[str, datetime]]] = {}  # tool -> [(session, ts)]
    legacy_write = False  # Write/Edit Pre вне canonical-категории (старый формат лога)
    unmatchable = False  # canonical-запись с непарсящимся ts → сопоставить нельзя
    for line in _read_tail_lines():
        line = line.strip()
        if not line or sid not in line:
            continue
        try:
            o = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        if o.get("session") != sid:
            continue
        dt = _parse_dt(o.get("ts", ""))
        if dt is not None and (start is None or dt < start):
            start = dt
        tool = o.get("tool")
        if o.get("event") != "PreToolUse" or tool not in _WRITE_TOOLS:
            continue
        if _is_guard_block(o):
            if dt is not None:
                blocks.setdefault(tool, []).append((sid, dt))
        elif o.get("category") == "tool_call":
            if dt is None:
                unmatchable = True
            else:
                canonical.append((tool, dt))
        else:
            legacy_write = True
    if canonical:
        had_write = unmatchable or any(
            not _take_block(blocks.get(tool, []), sid, ts)
            for tool, ts in sorted(canonical, key=lambda p: p[1])
        )
    else:
        had_write = legacy_write or unmatchable
    return had_write, start


def _git_session_edit(start: datetime | None) -> bool:
    """Второй сигнал «была правка» — через git, независимо от инструмента.

    Ловит правки инструментами без PreToolUse-матчера (MultiEdit/NotebookEdit) и любой
    иной файл-чейндж, не попавший в invocation-лог. Считаем правкой незакоммиченный
    *обычный* файл (не сабмодуль/каталог), изменённый ЗА сессию (mtime >= start) и не
    входящий в denylist авто-артефактов. Fail-safe: нет start / ошибка git → False.

    Корректность времени: лог-`ts` = ``datetime.now().isoformat()`` (naive-local), как и
    ``st_mtime`` (epoch); ``naive.timestamp()`` трактует метку как local → одна шкала.
    mtime-bound отсекает pre-session грязь (незавершённая прошлая сессия) → нет ложного блока.
    """
    if start is None:
        return False
    try:
        r = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "status",
                "--porcelain",
                "--ignore-submodules=all",
            ],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except (OSError, ValueError, subprocess.SubprocessError):
        return False
    if r.returncode != 0:
        return False
    start_ts = start.timestamp()
    for line in r.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        if " -> " in path:  # переименование "old -> new" → актуальный путь назначения
            path = path.split(" -> ", 1)[1].strip().strip('"')
        if path.replace("\\", "/") in _GIT_SKIP:
            continue
        try:
            fp = PROJECT_ROOT / path
            if fp.is_file():  # обычный файл (modified/staged/новый)
                mtime = fp.stat().st_mtime
            elif path.endswith("/") and fp.is_dir():
                # untracked collapsed dir (`?? newdir/`): git схлопывает новый каталог в один
                # entry. mtime каталога ловит файл, созданный инструментом в ранее не
                # существовавшем каталоге. Сабмодуль-entry идёт БЕЗ trailing slash → сюда не
                # попадает (остаётся пропуск ниже).
                mtime = fp.stat().st_mtime
            else:
                continue  # сабмодуль/прочий каталог → пропуск
            if mtime >= start_ts:
                return True
        except OSError:
            continue
    return False


def _iter_all_states():
    """(slug, data) всех пайплайнов: generic pipeline/*/ + 1С из реестра (папки задач).

    Через pipeline_state.iter_states() — после переезда 1С-состояния в папку задачи свой generic-glob
    его не нашёл бы → ложный «пайплайн не использован» → ложный блок. Graceful fallback на старый glob.
    """
    try:
        from shared import pipeline_state

        yield from pipeline_state.iter_states()
        return
    except Exception:
        pass
    if PIPELINE_DIR.is_dir():  # fallback: только generic
        for sf in PIPELINE_DIR.glob("*/.pipeline-state.json"):
            try:
                yield sf.parent.name, json.loads(sf.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue


def _pipeline_used_since(start: datetime | None) -> bool:
    """Был ли хоть один пайплайн (generic ИЛИ 1С в папке задачи) обновлён за сессию."""
    for _slug, d in _iter_all_states():
        dt = _parse_dt(d.get("updated_at", ""))
        if dt is None:
            continue
        if start is None or dt >= start:
            return True
    return False


class PipelineProtocolStop(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("PIPELINE_PROTOCOL_DISABLE") == "1":
            return None
        if os.environ.get("GATE_ORCHESTRATOR_ENABLE") == "1":
            return None  # R3: уступаем gate-orchestrator-stop (composition)
        sid = inp.session_id or ""
        if not sid:
            return None  # не можем привязать к сессии → allow (без deadlock)
        had_write, start = _session_writes_and_start(sid)
        if not had_write:
            # Второй сигнал: правки инструментами без PreToolUse-лога (MultiEdit/NotebookEdit и т.п.)
            had_write = _git_session_edit(start)
        if not had_write:
            return None  # нет правок за сессию → не задача → exempt
        if _pipeline_used_since(start):
            _gp_log(_gp_decision("pipeline-protocol", True, "pipeline used"))
            return None  # пайплайн использован → ok
        _gp_log(_gp_decision("pipeline-protocol", False, "edits without pipeline"))
        return HookOutput().block(
            "[PIPELINE-PROTOCOL] В этой сессии были правки кода без пайплайна (ADR-018, "
            "обязательная парадигма). Оформи задачу через пайплайн перед завершением:\n"
            '  .venv/Scripts/python.exe .claude/hooks/shared/pipeline_state.py init <slug> --title "..."\n'
            "  trivial → создай pipeline/<slug>/pipeline.md (4 секции: План/Дизайн/Реализация/Тест);\n"
            "  medium/complex → 01-architecture…04-testing.\n"
            "  затем: pipeline_state.py done <slug> <N> <файл>\n"
            "Для 1С-задачи после пайплайна сработает ЕДИНЫЙ task-completion gate (`onec-task-completion-stop`): "
            "память (recall+capture) + внешний анализ (`onec_search.py` Infostart / `ecosystem_scan.py` GitHub — "
            "голый GitHub-`WebSearch` блокирует энфорсер) — закрой всё в этом же проходе.\n"
            "Аварийный обход (если правка не была задачей): PIPELINE_PROTOCOL_DISABLE=1."
        )


if __name__ == "__main__":
    PipelineProtocolStop().run()
