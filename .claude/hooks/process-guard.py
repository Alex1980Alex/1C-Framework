#!/usr/bin/env python3
"""
Hook: process-guard
Event: PreToolUse
Matcher: Bash|PowerShell
Purpose:
  Defense-in-depth (рекомендация п.4 анализа инцидента 2026-06-30): блокирует
  деструктивный process-control (`Stop-Process`/`taskkill`/`kill`/`pkill`/`killall`),
  нацеленный на ЗАЩИЩЁННЫЕ демоны фреймворка. Инцидент: ревьюер-субагент code-verify
  вместо статического разбора выполнил `Stop-Process` и убил keep-alive демон
  `tei_keepalive`. Этот гейт защищает демоны независимо от вызывающего (caller-agnostic),
  т.к. `agent_id` в hook-stdin недоступен → детект «субагента» ненадёжен.

  Матчит `Bash|PowerShell` ОБА (важно: `Stop-Process` — PowerShell-командлет, а
  PowerShell-инструмент НЕ покрыт ни одним из существующих Bash-матчеров).

  Защита (любое → block):
    1. protected NAME-токен в команде (напр. `tei_keepalive`);
    2. явный pid-таргет (`-Id N` / `/PID N` / `kill N`), где N = pid живого демона
       (читается из его lock-файла);
    3. broad python-kill (`Stop-Process -Name python` / `taskkill /IM python.exe` /
       `pkill -f python` / `killall python`) — снёс бы демон вместе со всеми python.

Timeout: 3s
Opt-out: env PROCESS_GUARD_DISABLE=1 (для легитимной остановки демона оркестратором).
Graceful degradation: любая ошибка парсинга/чтения → allow (никогда не ломать workflow).
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

_CACHE = Path(__file__).resolve().parent.parent / "cache"  # .claude/hooks -> .claude -> .claude/cache

# Реестр защищённых демонов: lock-файлы с полем `pid` (расширяемо).
_PROTECTED_LOCKFILES = [
    _CACHE / "tei-keepalive.lock",
]
# Имя-токены защищённых демонов (substring, case-insensitive).
_PROTECTED_NAME_TOKENS = [
    "tei_keepalive",
]

# Деструктивные process-control глаголы. `kill` — только с pid/сигналом (иначе FP на
# словах вроде `killed`/`killall` ловится отдельно).
_VERB_RE = re.compile(
    r"\b(?:stop-process|taskkill|pkill|killall)\b|\bkill\s+(?:-\S+\s+)*\d",
    re.I,
)
# Broad-kill: снёс бы и демон.
_BROAD_RE = re.compile(
    r"stop-process\s+(?:-name\s+)?['\"]?python"
    r"|taskkill\s+/im\s+python"
    r"|pkill\s+(?:-f\s+)?\S*python"
    r"|killall\s+\S*python",
    re.I,
)


def _protected_pids() -> set[int]:
    """pid'ы живых демонов из lock-файлов. Ошибки чтения тихо пропускаются."""
    pids: set[int] = set()
    for lf in _PROTECTED_LOCKFILES:
        try:
            data = json.loads(lf.read_text(encoding="utf-8"))
            pid = data.get("pid")
            if isinstance(pid, int):
                pids.add(pid)
        except (OSError, ValueError, AttributeError):
            continue
    return pids


def _ints(text: str) -> set[int]:
    """Все целые из команды (кандидаты в pid-таргеты)."""
    out: set[int] = set()
    for m in re.findall(r"\d+", text):
        try:
            out.add(int(m))
        except ValueError:
            pass
    return out


class ProcessGuard(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        if os.environ.get("PROCESS_GUARD_DISABLE") == "1":
            return None
        if inp.tool_name not in ("Bash", "PowerShell"):
            return None
        command = inp.tool_input.get("command", "") or ""
        if not command or not _VERB_RE.search(command):
            return None  # не process-kill → пропуск

        lower = command.lower()

        # 1. protected name-токен
        for tok in _PROTECTED_NAME_TOKENS:
            if tok.lower() in lower:
                return self._block(f"имя демона '{tok}'")

        # 3. broad python-kill (проверяем до pid: снесёт демон даже без явного pid)
        if _BROAD_RE.search(command):
            return self._block("массовое убийство python-процессов (снесёт демоны фреймворка)")

        # 2. явный pid защищённого демона
        protected = _protected_pids()
        if protected and (protected & _ints(command)):
            hit = sorted(protected & _ints(command))
            return self._block(f"pid защищённого демона {hit}")

        return None  # деструктив, но не по защищённой цели → пропуск

    def _block(self, why: str) -> HookOutput:
        return HookOutput().block(
            f"[PROCESS-GUARD] Заблокировано убийство защищённого процесса фреймворка ({why}).\n"
            "Это служебный демон (напр. keep-alive прогрева TEI); его остановка ломает "
            "инфраструктуру и обычно — ошибка (особенно из ревью/субагента: ревью должно быть "
            "read-only, см. skill `code-verify`).\n"
            "Если остановка ДЕЙСТВИТЕЛЬНО нужна (оркестратор, осознанно) — выставь "
            "PROCESS_GUARD_DISABLE=1 на этот вызов. Демон сам перезапустится на следующем "
            "SessionStart (`tei-warmup-on-start`)."
        )


if __name__ == "__main__":
    ProcessGuard().run()
