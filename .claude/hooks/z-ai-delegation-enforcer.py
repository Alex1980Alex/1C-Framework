#!/usr/bin/env python3
"""
Hook: z-ai-delegation-enforcer
Event: UserPromptSubmit
Matcher: (none - fires on every user prompt)
Purpose: Detects tasks delegatable to cheap LLM tier via LLM Rotation,
         reminds to use delegation protocol for token economy.
Timeout: 3s

§4.5.3 A/B canary (2026-05-16): when env DELEGATION_ROUTER_CANARY_PCT
is set to a float in (0.0, 1.0], that fraction of prompts gets routed
through TrainedRouter (cosine similarity vs exemplar embeddings,
roadmap 260509 §4.5.1 bootstrap) instead of LinUCB bandit. Both paths
CAN emit a Langfuse `delegation.routing.decision` span — but only under
DELEGATION_ROUTING_SPAN=1 (по умолчанию ВЫКЛЮЧЕНО: замер 2026-07-26 дал
~1.9 с при таймауте хука 3 с, см. комментарий в `_delegation_level`).
Основа §5c.9 outcome corpus — при включённом флаге.
"""

import hashlib
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput

# §4.5.3 canary config — fraction of prompts routed through TrainedRouter
# instead of LinUCB bandit. Default 0.0 = router OFF (legacy behavior).
# Set to e.g. 0.1 to enable A/B testing at 10%.
# Garbage env (non-float / out-of-range) silently falls back to 0.0
# so the hook process keeps booting (don't break delegation on misconfig).
try:
    _ROUTER_CANARY_PCT = float(os.environ.get("DELEGATION_ROUTER_CANARY_PCT", "0.0"))
    if not (0.0 <= _ROUTER_CANARY_PCT <= 1.0):
        _ROUTER_CANARY_PCT = 0.0
except (TypeError, ValueError):
    _ROUTER_CANARY_PCT = 0.0

# --- Delegation signal keywords ---

# Orchestrator: complex tasks needing decompose + batch delegate
_ORCHESTRATOR_SIGNALS = [
    "each file",
    "for every",
    "per file",
    "all files",
    "batch",
    "multiple files",
    "several files",
    # Russian
    "каждый файл",
    "для каждого",
    "все файлы",
    "пакетно",
    "несколько файлов",
    "по файлам",
    "каждая фаза",
    "каждый модуль",
    "по фазам",
    "несколько фаз",
    "для каждой фазы",
]

# Medium: docs, decomposition, tests, boilerplate, configs
_MEDIUM_SIGNALS = [
    "documentation",
    "readme",
    "changelog",
    "decompos",
    "split into",
    "break down",
    "generate tests",
    "test cases",
    "write tests",
    "boilerplate",
    "template",
    "scaffold",
    "config",
    "setup",
    "migration script",
    "checklist",
    "summary",
    "table",
    "roadmap",
    "plan document",
    # Russian
    "разбей",
    "декомпозиция",
    "разбить на",
    "дорожн",
    "план реализаци",
    "план фаз",
    "создай документ",
    "напиши документ",
    "сгенерируй",
    "напиши тесты",
    "создай тесты",
    "напиши readme",
    "changelog",
    "по шаблону",
    "бойлерплейт",
    "максимальн",
    "подробн",
    "конфиг",
    "настрой",
    "миграц",
    "чеклист",
    "таблиц",
    "сводк",
    "добавь",
    "создай файл",
]

# Hard: code generation, refactoring, analysis
_HARD_SIGNALS = [
    "write code",
    "implement",
    "create module",
    "refactor",
    "rewrite",
    "add feature",
    "analysis report",
    "generate report",
    "new class",
    "new function",
    "new hook",
    "write service",
    "write handler",
    # Russian
    "напиши код",
    "реализуй",
    "создай модуль",
    "рефакторинг",
    "перепиши",
    "аналитический отчёт",
    "сгенерируй отчёт",
    "написать функцию",
    "написать класс",
    "новый класс",
    "новый хук",
    "новый сервис",
    "добавь функционал",
    "добавь фичу",
]

# Never: architecture, security, debugging (skip delegation)
_NEVER_SIGNALS = [
    "architecture",
    "how to design",
    "security",
    "debug",
    "investigate",
    "why does",
    # Russian
    "архитектур",
    "как лучше сделать",
    "безопасност",
    "отладка",
    "отладить",
    "почему не работает",
    "расследовать",
    "причина ошибки",
]

# Numeric patterns: "10 files", "5 modules", etc.
import re

_MULTI_FILE_RE = re.compile(
    r"\b([3-9]|[1-9]\d+)\s*(файл|file|модул|module|фаз|phase|часте|part)", re.IGNORECASE
)

# Min prompt length to consider (skip short prompts)
_MIN_PROMPT_LEN = 20


class ZAIDelegationEnforcer(BaseHook):
    # Блок helper-методов восстановлен 2026-07-26 из ca61a74b0 (§4.5.3 A/B canary).
    # Мерж около 2026-05-23 удалил все четыре метода, оставив в execute() вызов
    # self._delegation_level() → AttributeError на каждом промпте, прошедшем
    # NEVER-фильтр (2607 записей в .claude/hooks/cache/hook-errors.log,
    # 2026-05-23T19:02 → 2026-07-26). BaseHook.run() гасил исключение, поэтому
    # отказ был бесшумным: хук просто переставал что-либо советовать.

    def _bandit_level(self, prompt_lower: str) -> str | None:
        """Get delegation level from bandit model (AUTONOMOUS mode only)."""
        try:
            import importlib.util
            from pathlib import Path

            bandit_path = str(
                Path(__file__).resolve().parent.parent.parent
                / "src"
                / "shared"
                / "delegation_bandit.py"
            )
            spec = importlib.util.spec_from_file_location("delegation_bandit", bandit_path)
            if not spec or not spec.loader:
                return None
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            bandit = mod.DelegationBandit()
            if bandit.mode != "AUTONOMOUS":
                return None
            ctx = {
                "content_type": "docs"
                if any(kw in prompt_lower for kw in ("документ", "readme", "дорожн", "plan"))
                else "code",
                "has_code": any(
                    kw in prompt_lower
                    for kw in ("def ", "class ", "import ", "код", "функци", "модул")
                ),
                "has_architecture": any(
                    kw in prompt_lower for kw in ("архитектур", "pattern", "design")
                ),
                "domain": "other",
                "estimated_lines": 50,
            }
            action, confidence = bandit.predict(ctx)
            if confidence > 0.3:
                return action
        except Exception:
            pass
        return None

    def _router_level(self, prompt: str) -> tuple[str | None, float, bool]:
        """Get delegation level from TrainedRouter (§4.5.3 canary path).

        Returns (level, score, abstained). On any failure returns
        (None, 0.0, True) - caller falls through to _bandit_level.
        """
        try:
            from pathlib import Path

            # append, НЕ insert(0): на позиции 0 уже стоит .claude/hooks, и
            # приоритет корня репозитория затенил бы hooks-local shared.*
            repo_root = str(Path(__file__).resolve().parent.parent.parent)
            if repo_root not in sys.path:
                sys.path.append(repo_root)

            from src.shared.llm_rotation.router.trained import classify_sync

            res = classify_sync(prompt)
            return res.level, res.score, res.abstained
        except Exception:
            return None, 0.0, True

    @staticmethod
    def _should_canary(prompt: str) -> bool:
        """Deterministic per-prompt canary selection.

        Uses sha256(prompt)[:8] as RNG seed so the same prompt always
        routes through the same path within a session - useful for A/B
        comparison reproducibility. Returns True if this prompt should
        be routed via TrainedRouter.
        """
        if _ROUTER_CANARY_PCT <= 0.0:
            return False
        if _ROUTER_CANARY_PCT >= 1.0:
            return True
        seed = int(hashlib.sha256(prompt.encode()).hexdigest()[:8], 16)
        rng = random.Random(seed)
        return rng.random() < _ROUTER_CANARY_PCT

    def _delegation_level(self, prompt: str, prompt_lower: str) -> tuple[str | None, str]:
        """A/B routing: returns (level, method_tag).

        method_tag in {"linucb", "router", "router-abstain-fallback"}.
        Emits Langfuse span for outcome-corpus collection (§5c.9 stepstone).
        """
        method = "linucb"
        level: str | None = None
        router_score = 0.0
        router_abstained = False

        if self._should_canary(prompt):
            level, router_score, router_abstained = self._router_level(prompt)
            if level is not None and not router_abstained:
                method = "router"
            else:
                # Router abstained or failed - fall back to bandit
                level = self._bandit_level(prompt_lower)
                method = "router-abstain-fallback"
        else:
            level = self._bandit_level(prompt_lower)

        # Emit decision span (best-effort, never raises).
        #
        # Под env-флагом и по умолчанию ВЫКЛЮЧЕН. Замер 2026-07-26 на здоровом
        # Langfuse: _get_langfuse_client() 740 мс + client.flush() 1132 мс =
        # ~1.9 с из 3 с таймаута хука (flush=False не помогает - SDK выгружает
        # буфер на atexit). Хук стартует новым процессом на каждый промпт,
        # поэтому амортизировать клиент нечем: телеметрия съедала 95% бюджета
        # и ставила под удар основную функцию хука. Канареечный A/B
        # (_ROUTER_CANARY_PCT) тоже выключен по умолчанию, так что при OFF
        # span нечего записывать, кроме method="linucb".
        if os.environ.get("DELEGATION_ROUTING_SPAN", "") not in ("1", "true", "True"):
            return level, method

        try:
            from src.pdf_framework.observability.langfuse_setup import emit_observation

            emit_observation(
                name="delegation.routing.decision",
                input={"prompt_len": len(prompt), "method": method},
                output={
                    "level": level or "abstain",
                    "router_score": router_score,
                    "router_abstained": router_abstained,
                    "canary_pct": _ROUTER_CANARY_PCT,
                },
                metadata={"hook": "z-ai-delegation-enforcer"},
            )
        except Exception:
            pass

        return level, method

    def execute(self, inp: HookInput) -> HookOutput | None:
        prompt = inp.prompt.strip()
        if not prompt or len(prompt) < _MIN_PROMPT_LEN:
            return None

        prompt_lower = prompt.lower()

        # Never delegate - skip silently
        never_score = sum(1 for s in _NEVER_SIGNALS if s in prompt_lower)
        if never_score >= 1:
            return None

        # §4.5.3 A/B routing: canary % goes through TrainedRouter, rest LinUCB.
        # method_tag preserved for emitted observation only — downstream
        # decision logic unchanged (uses bandit_level variable name for
        # backward compatibility with the rest of execute()).
        bandit_level, _method = self._delegation_level(prompt, prompt_lower)

        # Orchestrator mode: 3+ files or batch signals
        orchestrator_score = sum(1 for s in _ORCHESTRATOR_SIGNALS if s in prompt_lower)
        has_multi_file = bool(_MULTI_FILE_RE.search(prompt))
        medium_score = sum(1 for s in _MEDIUM_SIGNALS if s in prompt_lower)
        hard_score = sum(1 for s in _HARD_SIGNALS if s in prompt_lower)

        if orchestrator_score >= 1 or has_multi_file:
            level = "HARD" if hard_score >= 1 else "MEDIUM"
            return HookOutput().system_message(
                f"[LLM DELEGATION: ORCHESTRATOR ({level})] Complex task detected (3+ outputs).\n"
                "Protocol: DECOMPOSE -> PREPARE prompts -> DELEGATE via llm_complete -> REVIEW -> ASSEMBLE.\n"
                "Steps:\n"
                "1. Opus: decompose into subtasks, classify each (Soft/Medium/Hard/Never)\n"
                "2. Opus: build prompt per subtask (task+context+format+constraints)\n"
                "3. Delegate: mcp__llm-rotation__llm_complete() per subtask\n"
                "4. Opus: review each result, fix inline\n"
                "5. Opus: assemble + Write() final files\n"
                "Full protocol: Skill('llm-delegation')"
            )

        # Bandit-based routing (when model is confident)
        if bandit_level and bandit_level != "Never":
            bandit_msg = f"[LLM DELEGATION: {bandit_level.upper()}] Bandit model suggests delegation level {bandit_level}.\n"
            if bandit_level == "Hard":
                bandit_msg += (
                    "Protocol: delegate generates draft -> Opus THOROUGH review (mandatory).\n"
                )
            elif bandit_level == "Medium":
                bandit_msg += "Protocol: delegate generates draft -> Opus review (mandatory).\n"
            else:
                bandit_msg += "Protocol: delegate generates draft -> format check.\n"
            bandit_msg += "Use: mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)\n"
            bandit_msg += "Full protocol: Skill('llm-delegation')"
            return HookOutput().system_message(bandit_msg)

        # Hard signals (single task)
        if hard_score >= 1:
            return HookOutput().system_message(
                "[LLM DELEGATION: HARD] This task can be delegated to cheap LLM tier.\n"
                "Protocol: delegate generates draft -> Opus THOROUGH review (mandatory).\n"
                "Use: mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)\n"
                "Review checklist: accuracy + completeness + format + logic + edge cases + security.\n"
                "If >50% rewrite needed -> do it yourself (Opus).\n"
                "Full protocol: Skill('llm-delegation')"
            )

        # Medium signals (single task) — threshold 1 for maximum delegation
        if medium_score >= 1:
            return HookOutput().system_message(
                "[LLM DELEGATION: MEDIUM] This task should be delegated to cheap LLM tier.\n"
                "Protocol: delegate generates draft -> Opus review (mandatory).\n"
                "Use: mcp__llm-rotation__llm_complete(prompt=..., max_tokens=4096)\n"
                "Review checklist: accuracy + completeness + format.\n"
                "Full protocol: Skill('llm-delegation')"
            )

        return None


if __name__ == "__main__":
    ZAIDelegationEnforcer().run()
