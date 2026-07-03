#!/usr/bin/env python3
"""
Hook: gate-orchestrator-stop
Event: Stop
Matcher: (none)
Purpose: ADR-034 R3 полная композиция гейтов. ОДИН проход build_context →
  evaluate_gates([pipeline_policy, onec_completion_policy]) → ОДИН консолидированный блок
  со ВСЕМИ ✗-гейтами сразу (вместо пинг-понга двух независимых Stop-хуков).
Opt-in: GATE_ORCHESTRATOR_ENABLE=1 (default OFF → no-op exit 0; старые pipeline-protocol-stop /
  onec-task-completion-stop делают всю работу как раньше). При ON старые хуки уступают
  (early-return по тому же env). Инварианты сохранены: per-policy opt-out
  (PIPELINE_PROTOCOL_DISABLE / ONEC_TASK_GATE_DISABLE), carve-out чистых вопросов (нет правок →
  allow), graceful degradation (любая ошибка → allow exit 0, никогда не deadlock).
Timeout: 10s
Exit codes: 0 = разрешить остановку, 2 = блокировать.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    # Default OFF: оркестратор спит, старые гейты работают (нулевое изменение поведения).
    if os.environ.get("GATE_ORCHESTRATOR_ENABLE") != "1":
        try:
            sys.stdin.buffer.read()
        except Exception:
            pass
        sys.exit(0)

    try:
        from shared.invocation_logger import InvocationTimer

        timer = InvocationTimer("gate-orchestrator-stop", event="Stop").start()
    except Exception:
        timer = None

    try:
        raw = sys.stdin.buffer.read().decode("utf-8", errors="replace")
    except Exception:
        raw = ""
    try:
        inp = json.loads(raw) if raw.strip() else {}
    except Exception:
        inp = {}
    sid = inp.get("session_id", "")
    transcript = inp.get("transcript_path", inp.get("transcript", ""))
    if timer:
        timer.session_id = sid

    try:
        from shared.gate_policies import DEFAULT_POLICIES, build_context
        from shared.gate_policy import evaluate_gates, log_decision

        ctx = build_context(sid, transcript)
        verdict = evaluate_gates(ctx, DEFAULT_POLICIES)
        for d in verdict["decisions"]:
            log_decision(d)

        if verdict["allow"]:
            if timer:
                timer.log(outcome="allow")
            sys.exit(0)

        failed = [d for d in verdict["decisions"] if not d.get("allow")]
        # Многострочный reason (богатый чеклист onec-петли) — самодостаточный блок, печатаем
        # как есть; короткий (pipeline-protocol) — строкой «✗ gate: reason» (P0.1 читаемость).
        parts = []
        for d in failed:
            r = d.get("reason", "")
            parts.append(r if "\n" in r else f"  ✗ {d['gate']}: {r}")
        reason = (
            "[GATE-ORCHESTRATOR] Завершение заблокировано (composition — всё недостающее сразу):\n"
            + "\n".join(parts)
            + "\n\nЗакрой все ✗ и заверши снова. "
            "Opt-out полностью: GATE_ORCHESTRATOR_ENABLE=0 (вернёт старые раздельные гейты)."
        )
        sys.stdout.buffer.write(
            json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False).encode("utf-8")
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
