#!/usr/bin/env python3
"""
Hook: analyze-1c-task-preflight
Event: UserPromptSubmit
Matcher: (none — content-based filter on slash-command name)
Purpose: When the user invokes `/analyze-1c-task` (with or without `--trace`),
         probe the debug-hmr environment so the SKILL knows whether the
         optional Phase 2.5 Runtime Trace can run live. Emits a single
         systemMessage with debug-hmr readiness and a hint about --trace
         capability. Never blocks (Phase 2.5 is opt-in; static analysis
         remains the default path).

Trigger detection reuses `shared.slash_detect.detect_slash_command` to stay
in sync with `slash-command-tracker.py` and `implement-1c-task-preflight.py`.

Logging:
  category="preflight" entries in data/hook-invocations.jsonl, correlated to
  the slash-command run via run_id (set by slash-command-tracker, fetched here
  via shared.run_context.get_run_id()).

Roadmap: docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md §5.1
"""

from __future__ import annotations

import os
import sys

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput  # noqa: E402

from shared.debug_hmr_health import probe_debug_hmr_ready  # noqa: E402
from shared.slash_detect import detect_slash_command  # noqa: E402

TARGET_COMMAND = "analyze-1c-task"
SMOKE_TEST_TIMEOUT = 25  # seconds
ROADMAP_REF = "docs/roadmap/260510_ROADMAP_DEBUG_HMR_INTEGRATION_INTO_1C_PIPELINE.md"


class AnalyzeOneCTaskPreflight(BaseHook):
    HOOK_NAME = "AnalyzeOneCTaskPreflight"

    def execute(self, inp: HookInput):
        prompt = inp.prompt or ""
        if detect_slash_command(prompt) != TARGET_COMMAND:
            return None

        trace_flag = "--trace" in prompt
        probe = probe_debug_hmr_ready(timeout=SMOKE_TEST_TIMEOUT)
        self._log_preflight(
            inp,
            exit_code=probe.exit_code,
            mode=probe.mode,
            debug_hmr_ready=probe.debug_hmr_ready,
            trace_flag=trace_flag,
        )
        return HookOutput().system_message(self._render_message(probe, trace_flag))

    @staticmethod
    def _render_message(probe, trace_flag: bool) -> str:
        prefix = "[analyze-1c-task-preflight]"

        if not probe.ok:
            return (
                f"{prefix} WARN preflight probe failed: {probe.error}. "
                f"Static analysis (Фазы 1-5) продолжит работу. "
                f"Phase 2.5 Runtime Trace недоступна — runtime-ветвления отметить как [STATIC-ASSUMPTION]. "
                f"Recovery: {ROADMAP_REF}"
            )

        if probe.debug_hmr_ready:
            trace_line = (
                "Phase 2.5 Runtime Trace будет запущена (флаг --trace)."
                if trace_flag
                else "Phase 2.5 Runtime Trace доступна через флаг --trace или skill self-decision."
            )
            return (
                f"{prefix} OK Debug environment ready (1c-debug-hmr handshake OK, mode={probe.mode}). "
                f"{trace_line}"
            )

        # debug-hmr недоступен, но static analysis работает — Phase 2.5 SKIP
        trace_line = (
            "ВНИМАНИЕ: флаг --trace передан, но Phase 2.5 будет SKIP — runtime-ветвления "
            "отмечены как [STATIC-ASSUMPTION]."
            if trace_flag
            else "Phase 2.5 Runtime Trace недоступна — для активации запусти 1c-debug-hmr "
            "(см. 16.6 EDT-MCP setup / 36.7 HMR wrapper)."
        )
        return (
            f"{prefix} WARN 1c-debug-hmr не отвечает (mode={probe.mode}). "
            f"Static analysis (Фазы 1-5) продолжит работу. {trace_line}"
        )

    def _log_preflight(self, inp, exit_code, mode, debug_hmr_ready, trace_flag):
        try:
            from shared.invocation_logger import log_invocation
            from shared.run_context import get_run_id

            log_invocation(
                hook=self.HOOK_NAME,
                event="UserPromptSubmit",
                tool=f"slash:{TARGET_COMMAND}",
                elapsed_ms=self.elapsed_ms,
                outcome=(
                    f"mode={mode};exit={exit_code};"
                    f"debug_hmr={int(debug_hmr_ready)};trace_flag={int(trace_flag)}"
                ),
                session_id=inp.session_id,
                category="preflight",
                run_id=get_run_id(inp.session_id),
            )
        except Exception:
            pass


class _NoAutoLogPreflight(AnalyzeOneCTaskPreflight):
    """Suppress BaseHook auto-log so we emit a single category=preflight record
    instead of a duplicate category=hook one. Mirrors slash-command-tracker."""

    def run(self):  # type: ignore[override]
        try:
            inp = HookInput.from_stdin()
            result = self.execute(inp)
            if result is not None:
                result.emit()
        except SystemExit:
            raise
        except Exception:
            sys.exit(0)


if __name__ == "__main__":
    _NoAutoLogPreflight().run()
