#!/usr/bin/env python3
"""
Hook: onec-task-completion-stop
Event: Stop
Matcher: (none)
Purpose: ЕДИНЫЙ task-completion gate для 1С-задачи (консолидирует memory-protocol-stop +
  research-protocol-stop в ОДИН хук — убирает 3-каскад). Если в сессии была 1С-задача
  (pipeline title `1С-задача (`) и не закрыты обязательные петли — блокирует ОДИН раз с
  КОНСОЛИДИРОВАННЫМ чеклистом (всё недостающее сразу).

  Условие = «1С-задача завершена корректно». Критерии (один проход по транскрипту):
    RECALL   [hard] — unified_search / vector-memory search_patterns;
    CAPTURE  [hard] — skill-learning capture_pattern/batch_capture / route_and_save /
                      Write `.md` в курируемую память (`/.claude/.../memory/*.md`);
    RESEARCH [hard] — WebSearch / WebFetch (внешний анализ: Infostart + GitHub best-practices);
    SONAR    [hard, при config_edit] — изменённый/добавленный 1С-код прогнан через SonarQube
                      с чистой дельтой (0 BLOCKER/CRITICAL на затронутых .bsl), контракт state
                      `shared.sonar_rescan_state`; verify = scripts/sonar_rescan_verify.py;
                      Sonar-down → state.skipped → ok; opt-out ONEC_SONAR_GATE_DISABLE=1;
    SKILL    [info] — Skill-вызов analyze-1c-task-v2 / implement-1c-task / va-bdd-testing /
                      run-1c-task / code-verify — уже принудительно на Write через code-skill-enforcer.
  Пайплайн-петля — отдельный концерн (pipeline-protocol-stop, general, ДО нас); тут показана ✓
  (раз 1С-задача детектится по pipeline-state — пайплайн существует).

  Детект — фактические tool_use транскрипта (НЕ raw-text). Не-1С-сессии → exempt.
  Anti-deadlock: opt-out ONEC_TASK_GATE_DISABLE=1; start=None / нет пайплайна → exempt; graceful
  exit 0; выход достижим (закрыть ✗-петли). No per-session sentinel — условие напрямую выполнимо.
  1С-сигнал и tail общие с pipeline_1c_bridge (единый предикат `is_1c_task_title`, N4).
Timeout: 8s
Opt-out: ONEC_TASK_GATE_DISABLE=1
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
INVOCATIONS_LOG = PROJECT_ROOT / "data" / "hook-invocations.jsonl"
PIPELINE_DIR = PROJECT_ROOT / "pipeline"
TAIL_BYTES = 2 * 1024 * 1024  # invocation-лог: короткие CloudEvents
TRANSCRIPT_TAIL_BYTES = 8 * 1024 * 1024  # транскрипт крупнее → не обрезать ранние сигналы

# N4: единый предикат 1С-задачи из моста (graceful fallback — Stop-хук не должен падать на импорте)
try:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from shared.pipeline_1c_bridge import is_1c_task_title
except Exception:

    def is_1c_task_title(title) -> bool:  # type: ignore[misc]
        return str(title or "").startswith("1С-задача (")


# R3 (ADR-034): унифицированный decision-log гейтов (best-effort, не ронять Stop-хук)
try:
    from shared.gate_policy import decision as _gp_decision
    from shared.gate_policy import log_decision as _gp_log
except Exception:

    def _gp_decision(*a, **k):
        return {}

    def _gp_log(*a, **k):
        return None


# Sonar-гейт (мандат): общий контракт состояния re-scan изменённого 1С-кода
# (graceful — Stop-хук не должен падать на импорте).
try:
    from shared.sonar_rescan_state import evaluate as _sonar_rescan_evaluate
except Exception:
    _sonar_rescan_evaluate = None


_RECALL_TOOLS = {
    "mcp__memory-orchestrator__unified_search",
    "mcp__vector-memory__search_patterns",
    "mcp__vector-memory__list_patterns",
}
_CAPTURE_TOOLS = {
    "mcp__skill-learning__capture_pattern",
    "mcp__skill-learning__batch_capture",
    "mcp__memory-orchestrator__route_and_save",
}
_RESEARCH_TOOLS = {"WebSearch", "WebFetch"}
# P0.4 (roadmap 260703 / К-1): канонический внешний анализ идёт НЕ голым WebSearch, а
# скриптами (GitHub-WebSearch хард-блокируется энфорсером ADR-039; 1С/RU-веб → onec_search).
# Bash-вызов любого из них засчитывается RESEARCH — иначе следование одному энфорсеру
# (ecosystem_scan вместо WebSearch) мешало удовлетворить research-петлю этого гейта.
_RESEARCH_BASH_MARKERS = (
    "ecosystem_scan.py",
    "onec_search.py",
    "its_fetch.py",
    "cc_docs_search.py",
)
_1C_SKILLS = (
    "analyze-1c-task-v2",
    "implement-1c-task",
    "va-bdd-testing",
    "run-1c-task",
    "code-verify",
)

# ADR-035 Фаза 1 — high-leverage инструменты как ADVISORY (info, НИКОГДА не блок;
# блок-решение остаётся строго по recall/capture/research). Сбор follow_rate/FP за окно
# → ADVISORY_EVENTS_LOG. Surfacing условный (текст подсказки сам поясняет «когда»).
#   T1 — impact-анализ перед правкой экспортного метода + live BP-trace для runtime-логики;
#   T2 — поиск эталона (reference) на Планировании.
_IMPACT_TOOLS = {"mcp__bsl-semantic-search__bsl_impact_analysis"}
_REFSEARCH_TOOLS = {
    "mcp__bsl-semantic-search__bsl_search",
    "mcp__bsl-semantic-search__bsl_hybrid_search",
    "mcp__bsl-semantic-search__bsl_similar",
}
# Префиксы серверов 1c-debug/1c-debug-hmr + маркеры СОДЕРЖАТЕЛЬНОГО BP-trace: метрика follow_rate
# должна отражать реальную трассировку (set_breakpoint/stack_trace/variables/evaluate/step/logpoint),
# а НЕ connection-проверки (ping/health_check/connect/targets) — иначе «использование» завышается.
_DEBUG_TOOL_PREFIXES = ("mcp__1c-debug-hmr__", "mcp__1c-debug__")
_DEBUG_TRACE_MARKERS = (
    "set_breakpoint",
    "stack_trace",
    "variables",
    "evaluate",
    "set_logpoint",
    "break_on_next",
    "_step",
    "wait_for_target",
)
# ADR-036 T1 — find_callers / call-graph (advisory): полнота охвата перед [REFACTOR]/удалением символа
_CALLERS_TOOLS = {
    "mcp__bsl-code-search__find_callers",
    "mcp__bsl-semantic-search__bsl_call_graph",
}
# Тир-2 кандидаты (advisory-only, ADR-035; НЕ влияют на блок — измеряем follow_rate):
_FORM_TOOLS = {"mcp__edt-mcp__get_form_screenshot"}  # визуальный verify формы без клиента
# API платформы / документация 8.3.27 (авторитет вместо галлюцинации API) — по префиксу сервера:
_PLATFORM_CTX_PREFIXES = ("mcp__bsl-platform-context__", "mcp__pdf-vector-graph__")
# bsl_analyze_method (codepilot1c) — точное имя сервера варьируется → детект по подстроке имени тула
_ANALYZE_METHOD_MARKER = "bsl_analyze_method"
ADVISORY_EVENTS_LOG = PROJECT_ROOT / ".claude" / "cache" / "onec-toolgate-events.jsonl"
ADVISORY_LOG_CAP = 5000  # FIFO-ротация лога advisory-событий (рост не безграничен)


def _read_stdin() -> dict:
    try:
        return json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    except Exception:
        return {}


def _parse_dt(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def _read_tail(path: Path, n: int = TAIL_BYTES) -> list[str]:
    try:
        with open(path, "rb") as f:
            f.seek(0, 2)
            size = f.tell()
            f.seek(max(0, size - n))
            return f.read().decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _session_start(sid: str) -> datetime | None:
    if not sid:
        return None
    start: datetime | None = None
    for line in _read_tail(INVOCATIONS_LOG):
        if sid not in line:
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
    return start


def _iter_1c_pipelines():
    """(slug, state_dict) всех 1С-задача-пайплайнов (по title-предикату).

    Через pipeline_state.iter_states() — 1С-состояние живёт в папке задачи (реестр), generic-glob его
    не найдёт. Graceful fallback на старый glob по pipeline/*/ (если ядро недоступно)."""
    try:
        from shared import pipeline_state

        for slug, d in pipeline_state.iter_states():
            if is_1c_task_title(d.get("title")):
                yield slug, d
        return
    except Exception:
        pass
    if not PIPELINE_DIR.is_dir():  # fallback: только generic
        return
    for sf in PIPELINE_DIR.glob("*/.pipeline-state.json"):
        try:
            d = json.loads(sf.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if is_1c_task_title(d.get("title")):
            yield sf.parent.name, d


def _onec_pipeline_updated(start: datetime | None) -> str | None:
    """slug 1С-пайплайна, обновлённого ЗА сессию (start=None → None). Прямой сигнал «1С-задача в этой сессии»."""
    if start is None:
        return None
    for slug, d in _iter_1c_pipelines():
        dt = _parse_dt(d.get("updated_at", ""))
        if dt is not None and dt >= start:
            return slug
    return None


def _incomplete_onec_pipeline() -> str | None:
    """slug 1С-пайплайна с НЕ-завершёнными этапами (H5: межсессионная задача из прошлой сессии).

    P1.7 (2.E.5): age-bound + tie-break на САМЫЙ СВЕЖИЙ. У голой BSL-правки нет надёжной привязки
    к конкретной задаче, поэтому (а) не «оживляем» давно брошенные пайплайны (иначе side-effects
    LOOPS.md/advisory уходят в чужую старую задачу); (б) среди подходящих берём последний
    обновлённый (наиболее вероятный владелец). Порог — env ONEC_INCOMPLETE_MAX_AGE_DAYS (default 14;
    0/пусто → без ограничения, прежнее поведение)."""
    try:
        max_age = float(os.environ.get("ONEC_INCOMPLETE_MAX_AGE_DAYS", "14") or 0)
    except ValueError:
        max_age = 14.0
    cutoff = (datetime.now() - timedelta(days=max_age)) if max_age > 0 else None
    best_slug: str | None = None
    best_dt: datetime | None = None
    for slug, d in _iter_1c_pipelines():
        stages = d.get("stages", [])
        if not stages or all(s.get("status") == "done" for s in stages):
            continue
        dt = _parse_dt(d.get("updated_at", ""))
        # Скипаем ТОЛЬКО заведомо-старые (парсибельный dt < cutoff). Отсутствие/непарс метки →
        # не повод исключать (реальный state всегда несёт updated_at; missing = не доказано-старый).
        if cutoff is not None and dt is not None and dt < cutoff:
            continue
        if best_slug is None or (dt is not None and (best_dt is None or dt > best_dt)):
            best_slug, best_dt = slug, dt
    return best_slug


def _iter_tool_uses(obj):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use" and obj.get("name"):
            yield obj
        for v in obj.values():
            yield from _iter_tool_uses(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_tool_uses(item)


def _collect_signals(transcript_path: str) -> dict:
    """Один проход по транскрипту → {recall, capture, research, skill, config_edit} по фактическим tool_use."""
    sig = {
        "recall": False,
        "capture": False,
        "research": False,
        "skill": False,
        "config_edit": False,
        # ADR-035 Фаза 1 / ADR-036 — advisory ИЛИ conditional-hard (зависит от env-флагов)
        "impact": False,
        "debug_trace": False,
        "ref_search": False,
        "callers": False,
        # Тир-2 advisory-кандидаты (ADR-035)
        "form_screenshot": False,
        "platform_ctx": False,
        "analyze_method": False,
    }
    if not transcript_path or not Path(transcript_path).exists():
        return sig
    for line in _read_tail(Path(transcript_path), TRANSCRIPT_TAIL_BYTES):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except (ValueError, json.JSONDecodeError):
            continue
        for tu in _iter_tool_uses(entry):
            name = tu.get("name", "")
            inp = tu.get("input") or {}
            if name in _RECALL_TOOLS:
                sig["recall"] = True
            elif name in _CAPTURE_TOOLS:
                sig["capture"] = True
            elif name in _RESEARCH_TOOLS:
                sig["research"] = True
            elif name in _IMPACT_TOOLS:  # ADR-035 T1 (advisory)
                sig["impact"] = True
            elif name in _REFSEARCH_TOOLS:  # ADR-035 T2 (advisory)
                sig["ref_search"] = True
            elif name.startswith(_DEBUG_TOOL_PREFIXES) and any(  # ADR-035 T1 (advisory)
                mk in name for mk in _DEBUG_TRACE_MARKERS
            ):
                sig["debug_trace"] = True
            elif name in _CALLERS_TOOLS:  # ADR-036 T1 (advisory)
                sig["callers"] = True
            elif name in _FORM_TOOLS:  # Тир-2 (advisory)
                sig["form_screenshot"] = True
            elif name.startswith(_PLATFORM_CTX_PREFIXES):  # Тир-2 (advisory)
                sig["platform_ctx"] = True
            elif _ANALYZE_METHOD_MARKER in name:  # Тир-2 (advisory)
                sig["analyze_method"] = True
            elif name == "Skill":
                s = str(inp.get("skill") or inp.get("command") or "")
                if any(k in s for k in _1C_SKILLS):
                    sig["skill"] = True
            elif name in ("Bash", "PowerShell"):  # P0.4: канонический research через скрипты
                cmd = str(inp.get("command") or "")
                if any(mk in cmd for mk in _RESEARCH_BASH_MARKERS):
                    sig["research"] = True
            elif name in ("Write", "Edit", "MultiEdit"):
                fp = (inp.get("file_path") or "").replace("\\", "/").lower()
                # курируемая память (`.claude/.../memory/*.md`), не src/memory/ или docs/*/memory/
                if "/memory/" in fp and fp.endswith(".md") and "/.claude/" in fp:
                    sig["capture"] = True
                # H5: правка 1С-кода в этой сессии (сигнал «1С-работа была» для межсессионной задачи)
                if "/configuration/" in fp or fp.endswith((".bsl", ".mdo", ".os")):
                    sig["config_edit"] = True
    return sig


def _write_loops_report(slug: str, sig: dict, optout: bool = False) -> None:
    """H2: сводка обязательных петель -> <state_dir>/LOOPS.md (для 1С = папка задачи). best-effort."""
    try:
        try:
            from shared import pipeline_state

            d = pipeline_state.state_dir(slug)  # 1С: папка задачи; generic: pipeline/<slug>/
        except Exception:
            d = PIPELINE_DIR / slug
        if not d.is_dir():
            return

        def m(ok):
            return "✓" if ok else "✗"

        def adv(ok):  # ADR-035 Фаза 1 — advisory-маркер (не блок)
            return "✓" if ok else "⚠ advisory"

        # N-P1.4 (260718): tool-effectiveness.jsonl ретирован — метрики эффективности
        # теперь считает analyze_tool_health.py напрямую из hook-invocations.jsonl (окно
        # 14д, per-tool/per-server), отчёт в data/reports/tools/_latest.md.
        tool_health = PROJECT_ROOT / "data" / "reports" / "tools" / "_latest.md"
        usage = d / "TOOL-USAGE-REPORT.md"
        skill_cell = "✓" if sig.get("skill") else "⚠ info (enforced на Write)"
        lines = [
            f"# LOOPS — обязательные петли задачи `{slug}`",
            "",
            "| Петля | Статус |",
            "|---|---|",
            "| ПАЙПЛАЙН | ✓ (pipeline-state) |",
            f"| RECALL (память) | {m(sig.get('recall'))} |",
            f"| CAPTURE (память) | {m(sig.get('capture'))} |",
            f"| RESEARCH (Infostart+GitHub) | {m(sig.get('research'))} |",
            f"| SONAR re-scan изменённого/добавленного кода | {m(sig.get('sonar_rescan'))} |",
            f"| SKILL-методика 1С | {skill_cell} |",
            f"| T1 impact-анализ перед правкой (advisory) | {adv(sig.get('impact'))} |",
            f"| T1 live BP-trace runtime-логики (advisory) | {adv(sig.get('debug_trace'))} |",
            f"| T2 поиск эталона на Планировании (advisory) | {adv(sig.get('ref_search'))} |",
            f"| T1 find_callers/call-graph перед [REFACTOR] (advisory) | {adv(sig.get('callers'))} |",
            f"| Тир-2 get_form_screenshot (advisory) | {adv(sig.get('form_screenshot'))} |",
            f"| Тир-2 bsl-platform-context/pdf-vector-graph (advisory) | {adv(sig.get('platform_ctx'))} |",
            f"| Тир-2 bsl_analyze_method (advisory) | {adv(sig.get('analyze_method'))} |",
            "",
            "_T1-T2 — рекомендательно по умолчанию; при ONEC_TOOLGATE_HARD=1 impact (и при "
            "ONEC_TOOLGATE_DEBUG_HARD=1 — BP-trace) становятся HARD на правке 1С-кода (ADR-036). "
            "find_callers всегда advisory. Блок ядра — RECALL/CAPTURE/RESEARCH._",
            "",
            f"- opt-out gate: {'ДА (ONEC_TASK_GATE_DISABLE)' if optout else 'нет'}",
            f"- W per-task (`TOOL-USAGE-REPORT.md`): {'есть' if usage.exists() else 'НЕ запущен (H3)'}",
            f"- tool-health (cross-task 14д): {'есть' if tool_health.exists() else 'нет'} — `data/reports/tools/_latest.md` (analyze_tool_health)",
            "",
            "_Авто-сводка onec-task-completion-stop на Stop (H2); фактические tool_use транскрипта._",
        ]
        (d / "LOOPS.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    except Exception:
        pass


def _impact_applicable() -> bool:
    """В2 260718 (W1): применимо ли `bsl_impact_analysis` к этой задаче — правка/добавление
    экспортного метода. Даёт валидатору честный applicable-знаменатель (presence на ВСЕХ
    задачах = survivorship-caveat ADR-035). best-effort: любая ошибка → False (не роняем)."""
    try:
        from shared.onec_change_scope import edits_exported_method

        return bool(edits_exported_method(PROJECT_ROOT))
    except Exception:
        return False


def _log_advisory_event(slug: str, sig: dict, hard_blocked: bool) -> None:
    """ADR-035 Фаза 1 — лог advisory-состояния T1-T2 на КАЖДОЙ 1С-задаче (allow и block).

    Данные для замера follow_rate / FP перед промоутом T1-T2 в hard (Фаза 2): какой % 1С-задач
    уже использует impact/BP-trace/reference-search. Модель — tdd-guard events.jsonl (ADR-015).
    best-effort: ошибка лога никогда не влияет на gate. JSONL в `.claude/cache/` (gitignored runtime).
    В2 260718: + `impact_applicable` — узкое условие применимости impact (честный знаменатель).
    """
    try:
        ADVISORY_EVENTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        rec = {
            "ts": datetime.now().isoformat(),
            "adr": "ADR-035-phase1",
            "slug": slug,
            "impact": bool(sig.get("impact")),
            "impact_applicable": _impact_applicable(),  # В2: правка экспортного метода?
            "debug_trace": bool(sig.get("debug_trace")),
            "ref_search": bool(sig.get("ref_search")),
            "callers": bool(sig.get("callers")),
            "form_screenshot": bool(sig.get("form_screenshot")),
            "platform_ctx": bool(sig.get("platform_ctx")),
            "analyze_method": bool(sig.get("analyze_method")),
            "config_edit": bool(sig.get("config_edit")),
            "hard_blocked": bool(hard_blocked),
        }
        with open(ADVISORY_EVENTS_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # FIFO-ротация: лог не растёт безгранично (1С-задачи редки → файл мал, чтение дёшево)
        lines = ADVISORY_EVENTS_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > ADVISORY_LOG_CAP:
            ADVISORY_EVENTS_LOG.write_text(
                "\n".join(lines[-ADVISORY_LOG_CAP:]) + "\n", encoding="utf-8"
            )
    except Exception:
        pass


def _compute_hard_ok(
    sig: dict, sonar_ok: bool, sonar_hard: bool, impact_hard: bool, debug_hard: bool
) -> bool:
    """Чистое блок-решение (ЕДИНЫЙ источник вердикта — parity живой хук == оркестратор).

    recall/capture/research — ВСЕГДА hard; impact/debug_trace — при hard-флагах ADR-036;
    Sonar — при sonar_hard. Отдельная pure-функция → тестируется матрицей без I/O (P0.1)."""
    hard_keys = ["recall", "capture", "research"]
    if impact_hard:
        hard_keys.append("impact")
    if debug_hard:
        hard_keys.append("debug_trace")
    return all(sig.get(k) for k in hard_keys) and (sonar_ok or not sonar_hard)


def _fix_recipe(
    sig: dict,
    sonar_ok: bool,
    sonar_hard: bool,
    sonar_detail: str,
    impact_hard: bool,
    debug_hard: bool,
) -> str:
    """P3.1 (koto {{gate_output}}): конкретные copy-paste команды ТОЛЬКО для незакрытых ✗-петель.

    Вывод гейта → готовый вход для фикса (не «догадайся, чем закрыть»). Sonar-детали (fail-файлы
    из state) уже в sonar_detail — прокидываем в рецепт, чтобы агент видел, ЧТО чинить."""
    lines = []
    if not sig.get("recall"):
        lines.append('  RECALL:   mcp__memory-orchestrator__unified_search(query="<тема задачи>")')
    if not sig.get("capture"):
        lines.append(
            "  CAPTURE:  mcp__skill-learning__capture_pattern(...) ПОСЛЕ verify PASS "
            "(или route_and_save / Write .md в /.claude/.../memory/)"
        )
    if not sig.get("research"):
        lines.append(
            '  RESEARCH: python scripts/onec_search.py "<тема>"  # Infostart/RU  |  '
            'python scripts/ecosystem_scan.py "<тема>" --top 8  # GitHub'
        )
    if sonar_hard and not sonar_ok:
        detail = f"  # {sonar_detail}" if sonar_detail else ""
        lines.append(
            "  SONAR:    powershell scripts/run-sonar-analysis.ps1; "
            f"python scripts/sonar_rescan_verify.py{detail}"
        )
    if impact_hard and not sig.get("impact"):
        lines.append("  IMPACT:   mcp__bsl-semantic-search__bsl_impact_analysis <экспортный_метод>")
    if debug_hard and not sig.get("debug_trace"):
        lines.append(
            "  BP-TRACE: 1c-debug-hmr set_breakpoint/stack_trace/variables на сценарии bugfix"
        )
    if not lines:
        return ""
    return "\n▶ Как закрыть ✗ (copy-paste):\n" + "\n".join(lines) + "\n"


def _build_reason(
    sig: dict,
    sonar_ok: bool,
    sonar_status: str,
    sonar_detail: str,
    sonar_hard: bool,
    impact_hard: bool,
    debug_hard: bool,
    hard_on: bool,
) -> str:
    """Консолидированный блок-чеклист (единый gate, всё недостающее сразу)."""

    def mark(ok: bool) -> str:
        return "✓" if ok else "✗"

    def tier(ok: bool, is_hard: bool) -> str:
        return "✓" if ok else ("✗" if is_hard else "•")

    hl_hdr = "HARD при правке кода" if hard_on else "• = advisory, НЕ блок"
    block_by = "RECALL/CAPTURE/RESEARCH"
    if sonar_hard:
        block_by += " + Sonar"
    if impact_hard:
        block_by += " + impact"
    if debug_hard:
        block_by += " + BP-trace"
    return (
        "[ONEC-TASK-GATE] 1С-задача не завершена: незакрыты обязательные петли (единый gate, всё сразу):\n"
        "  ✓ ПАЙПЛАЙН — pipeline-state заведён (1С-задача детектится по нему)\n"
        f"  {mark(sig['recall'])} RECALL — `mcp__memory-orchestrator__unified_search` / `search_patterns` (поиск прошлого опыта)\n"
        f"  {mark(sig['capture'])} CAPTURE — `mcp__skill-learning__capture_pattern` после verify PASS (или `route_and_save` / `.md`-память)\n"
        f"  {mark(sig['research'])} RESEARCH — `WebSearch`/`WebFetch` или `ecosystem_scan.py`/`onec_search.py` (внешний анализ: Infostart + GitHub)\n"
        f"  {(mark(sonar_ok) if sonar_hard else '•')} SONAR — re-scan изменённого/добавленного 1С-кода "
        f"(0 BLOCKER/CRITICAL на затронутых .bsl): {sonar_detail or sonar_status}\n"
        "      выход: `scripts/run-sonar-analysis.ps1` (скан) → `python scripts/sonar_rescan_verify.py` (verify дельты)\n"
        f"  {'✓' if sig['skill'] else '⚠'} SKILL [1С-методика] — "
        f"{'активирована' if sig['skill'] else 'не видно в транскрипте (на Write принудит. через code-skill-enforcer)'}\n"
        f"  — — — high-leverage (ADR-035/036; {hl_hdr}) — — —\n"
        f"  {tier(sig['impact'], impact_hard)} T1 impact-анализ — `bsl_impact_analysis` перед правкой экспортного метода"
        f"{' [HARD: правился 1С-код]' if impact_hard else ''}\n"
        f"  {tier(sig['debug_trace'], debug_hard)} T1 live BP-trace — `1c-debug-hmr` для bugfix / ≥3 ветвлений"
        f"{' [HARD]' if debug_hard else ''}\n"
        f"  {'✓' if sig['ref_search'] else '•'} T2 поиск эталона — `bsl_search`/`bsl_similar` на Планировании\n"
        f"  {'✓' if sig['callers'] else '•'} T1 find_callers / `bsl_call_graph` — перед `[REFACTOR]`/удалением символа\n"
        f"  {'✓' if sig['form_screenshot'] else '•'} Тир-2 `get_form_screenshot` — визуальный verify формы без клиента\n"
        f"  {'✓' if sig['platform_ctx'] else '•'} Тир-2 `bsl-platform-context`/`pdf-vector-graph` — API/доки 8.3.27 (вместо догадки)\n"
        f"  {'✓' if sig['analyze_method'] else '•'} Тир-2 `bsl_analyze_method` — сложность/unused метода до коммита\n"
        + _fix_recipe(sig, sonar_ok, sonar_hard, sonar_detail, impact_hard, debug_hard)
        + "\n"
        + f"Блок — по ✗ ({block_by}); • = advisory (не блок).\n"
        "Закрой ✗ и заверши снова. Opt-out: ONEC_TASK_GATE_DISABLE=1 (вся gate) / "
        "ONEC_SONAR_GATE_DISABLE=1 (только Sonar-проверка) / "
        "ONEC_TOOLGATE_HARD_DISABLE=1 (только high-leverage hard — для trivial-правок)."
    )


def evaluate_completion(root, start, transcript, *, apply_side_effects: bool = True) -> dict | None:
    """ЕДИНЫЙ источник решения 1С task-completion gate (P0.1, roadmap 260703 / инцидент G-1).

    Зовётся ОБОИМИ путями завершения: ``main()`` живого хука И
    ``gate_policies.build_context`` (оркестратор при GATE_ORCHESTRATOR_ENABLE=1). До P0.1
    Sonar-петля и side-effects (LOOPS.md, advisory-event) жили только в ``main()`` → при
    включённом оркестраторе молча не исполнялись (Sonar-энфорсмент/окно ADR-035 мертвы).

    Возврат ``None`` → 1С-задачи в сессии нет (gate не применим). Иначе dict:
      {is_1c, task_slug, sig(+sonar_rescan), sonar_ok/status/detail, sonar_hard,
       impact_hard, debug_hard, hard_ok, reason}.
    ``apply_side_effects=True`` → пишет LOOPS.md + advisory-event (для активного пути завершения;
    оба пути взаимоисключаемы по GATE_ORCHESTRATOR_ENABLE → ровно одна запись).
    """
    slug = _onec_pipeline_updated(start)  # прямой сигнал: 1С-пайплайн обновлён в этой сессии
    incomplete = _incomplete_onec_pipeline() if not slug else None  # H5: незавершённый из прошлого
    if not slug and not incomplete:
        return None  # 1С-задачи нет вовсе → gate не применим

    sig = _collect_signals(transcript)
    # H5: «незавершённая из прошлой сессии» применяется лишь при 1С-правке в ЭТОЙ сессии
    if not slug and not sig.get("config_edit"):
        return None
    task_slug = slug or incomplete

    # Sonar-гейт (мандат 2026-06-23): изменённый/добавленный 1С-код обязан пройти Sonar re-scan
    # с чистой дельтой (0 BLOCKER/CRITICAL). Default-ON при config_edit. Guard'ы против дедлока:
    # opt-out ONEC_SONAR_GATE_DISABLE=1; Sonar-down → verify skipped → ok; нет state → block missing.
    sonar_hard = (
        bool(sig.get("config_edit"))
        and os.environ.get("ONEC_SONAR_GATE_DISABLE") != "1"
        and _sonar_rescan_evaluate is not None
    )
    sonar_ok, sonar_status, sonar_detail = True, "n/a", ""
    if sonar_hard:
        try:
            sonar_ok, sonar_status, sonar_detail = _sonar_rescan_evaluate(root, start)
        except Exception as e:
            sonar_ok = True  # graceful: внутренняя ошибка evaluate → не блокируем
            sonar_status, sonar_detail = "degraded", f"{type(e).__name__}: {e}"
            # P1.8 (2.E.4): fail-open Sonar-ветки виден в decision-log (не молчаливый allow)
            _gp_log(_gp_decision("onec-task-completion:sonar", True, f"degraded:{sonar_detail}"))
    sig["sonar_rescan"] = sonar_ok

    # ADR-036 (вариант A промоута high-leverage): при ONEC_TOOLGATE_HARD=1 И правке 1С-кода impact
    # → hard; debug_trace — дополнительно при ONEC_TOOLGATE_DEBUG_HARD=1. Default (флаги off) =
    # прежнее поведение (блок строго по recall/capture/research) — нулевой риск ложных блоков.
    _hard_disable = os.environ.get("ONEC_TOOLGATE_HARD_DISABLE") == "1"
    _hard_on = (
        os.environ.get("ONEC_TOOLGATE_HARD") == "1"
        and bool(sig.get("config_edit"))
        and not _hard_disable
    )
    impact_hard = _hard_on
    debug_hard = _hard_on and os.environ.get("ONEC_TOOLGATE_DEBUG_HARD") == "1"
    hard_ok = _compute_hard_ok(sig, sonar_ok, sonar_hard, impact_hard, debug_hard)

    if apply_side_effects:
        _write_loops_report(task_slug, sig)  # H2: сводка петель -> pipeline/<slug>/LOOPS.md
        # ADR-035/036 — лог advisory/hard состояния T1-T2 на КАЖДОЙ 1С-задаче (allow и block)
        _log_advisory_event(task_slug, sig, hard_blocked=not hard_ok)

    reason = _build_reason(
        sig, sonar_ok, sonar_status, sonar_detail, sonar_hard, impact_hard, debug_hard, _hard_on
    )
    return {
        "is_1c": True,
        "task_slug": task_slug,
        "sig": sig,
        "sonar_ok": sonar_ok,
        "sonar_status": sonar_status,
        "sonar_detail": sonar_detail,
        "sonar_hard": sonar_hard,
        "impact_hard": impact_hard,
        "debug_hard": debug_hard,
        "hard_ok": hard_ok,
        "reason": reason,
    }


def main() -> None:
    try:
        from shared.invocation_logger import InvocationTimer

        timer = InvocationTimer("onec-task-completion-stop", event="Stop").start()
    except Exception:
        timer = None

    if os.environ.get("ONEC_TASK_GATE_DISABLE") == "1":
        if timer:
            timer.log(outcome="allow-optout")
        sys.exit(0)

    if os.environ.get("GATE_ORCHESTRATOR_ENABLE") == "1":
        if timer:
            timer.log(outcome="allow-yield-orchestrator")  # R3: уступаем gate-orchestrator-stop
        sys.exit(0)

    inp = _read_stdin()
    sid = inp.get("session_id", "")
    transcript = inp.get("transcript_path", inp.get("transcript", ""))
    if timer:
        timer.session_id = sid

    try:
        start = _session_start(sid)
        res = evaluate_completion(PROJECT_ROOT, start, transcript, apply_side_effects=True)
        if res is None:
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)  # 1С-задачи нет → decision-log не пишем (не наш концерн)
        if res["hard_ok"]:
            # P1.6: логируем и ALLOW реальной 1С-задачи (симметрия decision-log — иначе периоды
            # в gate-decisions.jsonl между deny-only и allow+deny режимами несравнимы).
            s = res["sig"]
            _gp_log(
                _gp_decision(
                    "onec-task-completion",
                    True,
                    "обязательные петли закрыты",
                    recall=s.get("recall"),
                    capture=s.get("capture"),
                    research=s.get("research"),
                    sonar_rescan=s.get("sonar_rescan"),
                )
            )
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        s = res["sig"]
        _gp_log(
            _gp_decision(
                "onec-task-completion",
                False,
                "1С-задача: незакрыты обязательные петли",
                recall=s.get("recall"),
                capture=s.get("capture"),
                research=s.get("research"),
                sonar_rescan=s.get("sonar_rescan"),
                skill=s.get("skill"),
                impact=s.get("impact"),  # ADR-035/036 advisory|hard
                debug_trace=s.get("debug_trace"),
                ref_search=s.get("ref_search"),
                callers=s.get("callers"),
                form_screenshot=s.get("form_screenshot"),
                platform_ctx=s.get("platform_ctx"),
                analyze_method=s.get("analyze_method"),
            )
        )
        sys.stdout.buffer.write(
            json.dumps({"decision": "block", "reason": res["reason"]}, ensure_ascii=False).encode(
                "utf-8"
            )
            + b"\n"
        )
        sys.stdout.buffer.flush()
        if timer:
            timer.log(outcome="block")
        sys.exit(2)
    except SystemExit:
        raise
    except Exception as e:
        if timer:
            timer.log(outcome="error", error=f"{type(e).__name__}: {e}")
        sys.exit(0)  # graceful: никогда не блокируем при внутренней ошибке


if __name__ == "__main__":
    main()
