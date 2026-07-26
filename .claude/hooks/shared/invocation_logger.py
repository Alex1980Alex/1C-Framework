"""Hook invocation logger — JSONL append-only structured logging.

Logs every hook invocation to data/hook-invocations.jsonl.
Format: one JSON object per line (JSONL — append-only, crash-safe).
Rotation: when file exceeds 10MB, rename to .1 and start fresh.

Used by:
- BaseHook.run() — automatic for all 15 BaseHook-derived hooks
- Standalone hooks — via log_invocation() direct call
  (ralph_wiggum_stop, git-commit-enforcer, docs-change-enforcer,
   task-enforcer, auto-git-save-prompt, skill-eval-enforcer-shell)

Entry format (§15 P0 ADD: CloudEvents v1.0 envelope + W3C traceparent):
  {"ts":"ISO","hook":"SkillRouter","event":"UserPromptSubmit",
   "tool":null,"elapsed_ms":45,"outcome":"message",
   "session":"abc123","agent_id":"xyz789","error":null,
   "specversion":"1.0","id":"<uuid>","source":"claude-code-hooks",
   "type":"com.anthropic.claude.hook.UserPromptSubmit",
   "time":"ISO","correlationid":"<run_id|session>",
   "causationid":"<parent_id or empty>",
   "traceparent":"00-<32hex>-<16hex>-01"}

Phase 7: Added agent_id for subagent monitoring.
Phase 9 (§15 P0): CloudEvents wrapping + W3C trace context.

Backward compatibility: all pre-§15 flat fields preserved verbatim.
New fields are additive — existing grep/jq/DuckDB queries continue
to work without modification.

Based on task_master.py patterns: graceful degradation, never block.
"""

import json
import os
import secrets
import time
import uuid
from datetime import datetime
from pathlib import Path

# --- Path resolution (cached) ---

_LOG_FILE: Path | None = None
MAX_LOG_SIZE = 10 * 1024 * 1024  # 10MB
# Сколько ротированных архивов держать. roadmap 260718 N-P0.2: одного архива
# (.1) хватало лишь на ~2 дня при ~8МБ/день, а вердикты считаются за окно 14д →
# window_incomplete всегда True. Каскад .1→.2→…→.N покрывает окно. ~10МБ/файл ×
# 12 ≈ 120МБ (gitignored, локально) ≈ 14 дней. Тюнится env HOOK_LOG_ARCHIVES.
try:
    HOOK_LOG_ARCHIVES = max(1, int(os.environ.get("HOOK_LOG_ARCHIVES", "12")))
except ValueError:
    HOOK_LOG_ARCHIVES = 12


def _get_log_file() -> Path:
    """Resolve log file path. Cached after first call."""
    global _LOG_FILE
    if _LOG_FILE is not None:
        return _LOG_FILE

    try:
        from shared.core_paths import get_project_dir

        project_root = get_project_dir().parent
    except ImportError:
        # Fallback: hooks/ -> .claude/ -> project/
        project_root = Path(__file__).resolve().parent.parent.parent

    _LOG_FILE = project_root / "data" / "hook-invocations.jsonl"
    return _LOG_FILE


def _rotate_if_needed(filepath: Path) -> None:
    """Rotate log file if it exceeds MAX_LOG_SIZE.

    Каскадная ротация (roadmap 260718 N-P0.2): перед переносом LOG→.1 сдвигаем
    существующие .N→.N+1 вплоть до HOOK_LOG_ARCHIVES, старейший (.N над лимитом)
    затирается. Раньше держался лишь .1 (os.replace перезатирал предыдущий) →
    LOG+.1 покрывали ~2 дня, а аналитика окна 14д всегда была window_incomplete.

    os.replace (атомарный overwrite) вместо unlink+rename: раздельные шаги давали
    межпроцессную гонку — процесс B удалял свежесозданный процессом A архив,
    а его собственный rename падал (adversarial-review 260713 P0#3). При проигрыше
    гонки os.replace у второго процесса источник уже переименован → FileNotFoundError
    → поглощён except OSError, архив цел.
    """
    try:
        if not (filepath.exists() and filepath.stat().st_size > MAX_LOG_SIZE):
            return
        # сдвиг .N→.N+1 сверху вниз (старейший затирается по достижении лимита)
        for n in range(HOOK_LOG_ARCHIVES - 1, 0, -1):
            src = filepath.with_name(f"hook-invocations.{n}.jsonl")
            if src.exists():
                dst = filepath.with_name(f"hook-invocations.{n + 1}.jsonl")
                try:
                    os.replace(src, dst)
                except OSError:
                    pass
        os.replace(filepath, filepath.with_name("hook-invocations.1.jsonl"))
    except OSError:
        pass


# --- Public API ---


def extract_duration_ms(raw: dict, event: str) -> int | None:
    """260718 H-P0.1: настоящая длительность тула из PostToolUse-payload.

    Платформа кладёт top-level ``duration_ms`` в PostToolUse (эмпирически
    подтверждено дампом tool-response-shapes.jsonl — Read Post-payload несёт
    ключ ``duration_ms``). Прямой источник латентности БЕЗ пэйринга: не завышен
    overhead'ом хука и не зависит от FIFO-эвристики пары.

    Возвращает int мс или None (нет поля / не PostToolUse / нечисло) →
    потребитель падает на pair_durations. Общий для обоих логгеров
    (built-in + MCP), чтобы контракт извлечения не разошёлся.
    """
    if event != "PostToolUse":
        return None
    val = raw.get("duration_ms")
    if val is None:
        val = raw.get("durationMs")  # camelCase-страховка на случай дрейфа payload
    if isinstance(val, bool):  # bool — подкласс int, но не длительность
        return None
    if isinstance(val, (int, float)) and val >= 0:
        return int(val)
    return None


def _make_traceparent(run_id: str = "", session_id: str = "") -> str:
    """Build W3C traceparent header value.

    Format: `00-<trace_id_32hex>-<span_id_16hex>-01`.
    trace_id derived from run_id|session for cross-event correlation.
    span_id always fresh (per-event).

    Spec: https://www.w3.org/TR/trace-context/#traceparent-header
    """
    seed = (run_id or session_id or "").replace("-", "")[:32]
    if len(seed) >= 32:
        trace_id = seed[:32]
    else:
        # Derive deterministic 32-hex from seed; pad with random if seed empty/short
        if seed:
            # Hash-pad to 32 hex chars (uuid.uuid5 gives 32 hex via .hex)
            trace_id = uuid.uuid5(uuid.NAMESPACE_URL, seed).hex
        else:
            trace_id = secrets.token_hex(16)
    span_id = secrets.token_hex(8)  # 16 hex chars = 8 bytes
    return f"00-{trace_id}-{span_id}-01"


def log_invocation(
    hook: str,
    event: str | None = None,
    tool: str | None = None,
    elapsed_ms: int = 0,
    outcome: str = "allow",
    session_id: str = "",
    error: str | None = None,
    agent_id: str = "",  # Phase 7: Subagent monitoring
    category: str = "hook",  # Phase 8: Multi-source log unification
    run_id: str = "",  # Phase 8: Cross-hook correlation (slash-command run)
    causation_id: str = "",  # Phase 9 (§15 P0): parent event id (DAG causality)
    tool_call_id: str = "",  # ADR-022 P0.4: tool_use_id — join-ключ Pre/Post (= gen_ai.tool.call.id)
    error_type: str = "",  # ADR-022 P0.4: низкокардинальная категория ошибки (= OTel error.type)
    args_hash: str = "",  # ADR-022 P1: хеш аргументов вызова → детект retry (повтор идентичного)
    duration_ms: int
    | None = None,  # 260718 H-P0.1: реальная длительность тула из PostToolUse-payload
    in_repo: bool | None = None,  # 2026-07-26: цель вызова внутри корня проекта? (см. докстринг)
) -> None:
    """Log a single hook invocation to JSONL file.

    Args:
        hook: Hook class name or script name (e.g. "SkillRouter")
        event: Hook event type (UserPromptSubmit, PreToolUse, PostToolUse, Stop)
        tool: Tool name (for PreToolUse/PostToolUse events)
        elapsed_ms: Время работы САМОГО ХУКА (~20мс), НЕ инструмента. Реальная латентность
            тула = Pre→Post-пара по tool_call_id (tool_effectiveness.pair_durations) ЛИБО
            прямое поле `duration_ms` (см. ниже, точнее пэйринга).
        duration_ms: 260718 H-P0.1 — НАСТОЯЩАЯ длительность тула из PostToolUse-payload
            (платформа кладёт top-level `duration_ms`, эмпирически подтверждено дампом
            tool-response-shapes.jsonl). Прямой источник латентности БЕЗ пэйринга: не
            завышается overhead'ом хука и не зависит от FIFO-эвристики пары. None вне
            PostToolUse или если поле отсутствует → потребитель падает на pair_durations.
        outcome: Result — one of: allow, block, message, error
        session_id: Claude Code session ID (from stdin JSON)
        error: Error message if outcome is "error"
        agent_id: Subagent ID (for subagent monitoring, Phase 7)
        category: Log category for filtering — "hook" (default, BaseHook auto-log),
                  "mcp_call" (MCP server invocation),
                  "slash_run" (slash-command lifecycle: start/end),
                  "phase" (skill phase marker). Future categories add here.
        run_id: UUID linking events to one slash-command invocation.
                Set by slash-command-tracker on UserPromptSubmit, read by other
                hooks via shared/run_context.get_run_id(session_id).
        causation_id: CloudEvents extension — id of the event that directly
                      triggered this one (parent in DAG). Empty for roots.
        in_repo: 2026-07-26 — цель файлового вызова лежит внутри корня проекта?
            ОДИН БИТ, а не путь: логгер осознанно не пишет сырьё аргументов
            (`_args_fingerprint`: «пути/секреты не утекают»), а потребителю
            (`pipeline-protocol`) нужно лишь отличить product-код от записи вовне
            (память в `~/.claude/...`, пользовательские настройки). None ⟶ ключ не
            пишется вовсе (тул без файловой цели / не удалось определить), и
            потребитель обязан трактовать отсутствие fail-closed — как правку.
    """
    try:
        filepath = _get_log_file()
        filepath.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed(filepath)

        iso_now = datetime.now().isoformat()
        event_id = str(uuid.uuid4())
        # CloudEvents `type` follows reverse-DNS convention. Fall back when event missing.
        ce_type = f"com.anthropic.claude.hook.{event}" if event else "com.anthropic.claude.hook"
        # correlationid pins all events in one slash-command/session together.
        correlation_id = run_id or session_id or event_id

        # §15 P0 P0.4 — crypto-shred sensitive `error` field per session key.
        # Opt-out via env CLAUDE_LOG_NO_CRYPTO=1 (kept plain).
        # Encryption silently no-ops если cryptography/key unavailable.
        error_value = error
        if error and session_id and os.environ.get("CLAUDE_LOG_NO_CRYPTO") != "1":
            try:
                from shared.crypto_shred import encrypt
                from shared.session_keys import get_or_create_key

                _key = get_or_create_key(session_id)
                if _key:
                    _ct = encrypt(error, _key)
                    if _ct:
                        error_value = _ct  # replace plaintext with envelope
            except Exception:
                pass  # never block logging

        # error.type — низкокардинальная категория ошибки, единый источник для
        # плоского `error_type` и OTel-алиаса `error.type` (roadmap 260713 P2.1).
        err_type = error_type or ("unknown" if outcome == "error" else "")
        success = outcome != "error" and not error

        entry = {
            "ts": iso_now,
            "hook": hook,
            "event": event,
            "tool": tool,
            "elapsed_ms": elapsed_ms,
            "outcome": outcome,
            "session": session_id or "",
            "error": error_value,  # §15 P0: may be `enc::<base64>` envelope when crypto active
            "agent_id": agent_id,  # Phase 7
            "category": category,  # Phase 8
            "run_id": run_id,  # Phase 8
            # --- ADR-022 P0.4: OTel-совместимые поля tool-call (gen_ai.tool.call.id / success / error.type) ---
            "tool_call_id": tool_call_id,
            "success": success,
            "error_type": err_type,
            "args_hash": args_hash,  # ADR-022 P1: фингерпринт аргументов (детект retry)
            # 260718 H-P0.1: прямая длительность тула из payload (точнее пэйринга).
            # Пишется только когда платформа прислала (PostToolUse) — иначе ключа нет
            # (не null-шум), потребитель отличает «не было» от «0мс».
            **({"duration_ms": int(duration_ms)} if duration_ms is not None else {}),
            # 2026-07-26: цель вызова внутри репозитория? Ключ пишется ТОЛЬКО когда
            # определён — отсутствие означает «неизвестно», и потребитель трактует
            # его fail-closed (как правку), а не как «вне репо».
            **({"in_repo": bool(in_repo)} if in_repo is not None else {}),
            # --- OTel GenAI semconv алиасы (roadmap 260713 P2.1) ---
            # Аддитивно и дублируют плоские поля дословно: будущий OTel-экспорт
            # становится переименованием, существующие jq/DuckDB-запросы не ломаются.
            # Dotted-ключи легальны в JSON; потребители по плоским именам их не видят.
            "gen_ai.tool.name": tool,
            "gen_ai.tool.call.id": tool_call_id,
            "error.type": err_type,
            # --- CloudEvents v1.0 envelope (§15 P0) ---
            "specversion": "1.0",
            "id": event_id,
            "source": "claude-code-hooks",
            "type": ce_type,
            "time": iso_now,
            "datacontenttype": "application/json",
            "correlationid": correlation_id,
            "causationid": causation_id or "",
            # --- W3C Trace Context (§15 P0) ---
            "traceparent": _make_traceparent(run_id=run_id, session_id=session_id),
        }

        # §15 P1 — optional JSON Schema validation (opt-in via CLAUDE_LOG_VALIDATE=1).
        # Validation failures logged but never block — schema is advisory, not gate.
        if os.environ.get("CLAUDE_LOG_VALIDATE") == "1":
            _validate_entry(entry)

        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass  # Never block on logging failure


# Cache for JSON Schema (populated on first validate call). Module-level
# для lazy-singleton pattern — single load per process lifetime.
_SCHEMA_CACHE: dict | None = None


def _validate_entry(entry: dict) -> None:
    """Best-effort JSON Schema validation. Logs warning to stderr on mismatch.

    Schema: .claude/schemas/events/hook-invocation.json (CloudEvents v1.0 +
    framework extensions). Validation is advisory only — never raises.
    Opt-in через env CLAUDE_LOG_VALIDATE=1 (default off для performance).
    """
    global _SCHEMA_CACHE
    try:
        import sys as _sys

        from jsonschema import Draft202012Validator

        if _SCHEMA_CACHE is None:
            schema_path = (
                Path(__file__).resolve().parent.parent.parent.parent
                / ".claude"
                / "schemas"
                / "events"
                / "hook-invocation.json"
            )
            if not schema_path.exists():
                return
            with open(schema_path, encoding="utf-8") as f:
                _SCHEMA_CACHE = json.load(f)

        validator = Draft202012Validator(_SCHEMA_CACHE)
        errors = list(validator.iter_errors(entry))
        if errors:
            # Stderr only — never log to files about logger to avoid loops.
            _sys.stderr.write(
                f"[invocation_logger] schema validation: {len(errors)} error(s) "
                f"in entry hook={entry.get('hook', '?')}: "
                f"{errors[0].message[:120]}\n"
            )
    except (ImportError, ValueError, OSError):
        pass  # validation never blocks


class InvocationTimer:
    """Context manager for timing hook invocations.

    Usage (standalone hooks):
        timer = InvocationTimer("git-commit-enforcer", event="Stop")
        timer.start()
        # ... hook logic ...
        timer.log(outcome="block", error=None)

    Phase 7: Added agent_id for subagent monitoring.
    """

    def __init__(self, hook: str, event: str | None = None):
        self.hook = hook
        self.event = event
        self.tool: str | None = None
        self.session_id: str = ""
        self.agent_id: str = ""  # Phase 7
        self.category: str = "hook"  # Phase 8
        self.run_id: str = ""  # Phase 8
        self.causation_id: str = ""  # Phase 9 (§15 P0) — parent event id
        self._start: float = 0.0

    def start(self) -> "InvocationTimer":
        self._start = time.time()
        return self

    def elapsed_ms(self) -> int:
        return int((time.time() - self._start) * 1000)

    def log(self, outcome: str = "allow", error: str | None = None) -> None:
        log_invocation(
            hook=self.hook,
            event=self.event,
            tool=self.tool,
            elapsed_ms=self.elapsed_ms(),
            outcome=outcome,
            session_id=self.session_id,
            error=error,
            agent_id=self.agent_id,  # Phase 7
            category=self.category,  # Phase 8
            run_id=self.run_id,  # Phase 8
            causation_id=self.causation_id,  # Phase 9 (§15 P0)
        )
