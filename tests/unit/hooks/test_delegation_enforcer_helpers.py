"""Регресс на потерю helper-блока z-ai-delegation-enforcer.

История: ca61a74b0 (2026-05-16) добавил §4.5.3 A/B canary - четыре метода
(_bandit_level / _router_level / _should_canary / _delegation_level) плюс их
вызов в execute(). Мерж около 2026-05-23 удалил методы, оставив вызов →
AttributeError на каждом промпте, прошедшем NEVER-фильтр. BaseHook.run()
гасил исключение, поэтому отказ был бесшумным: 2607 записей в
.claude/hooks/cache/hook-errors.log за два месяца, при этом хук считался
рабочим и просто ничего не советовал.

Тесты пинят обе стороны инварианта:
  1. методы существуют (прямая причина),
  2. execute() на делегируемом промпте не роняет AttributeError (симптом),
  3. langfuse-span выключен по умолчанию (защита бюджета: с ним хук
     занимает ~2.2 с при таймауте 3 с, без него ~200 мс).
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from unittest import mock

import pytest

pytestmark = pytest.mark.unit

_ROOT = Path(__file__).resolve().parents[3]
_HOOKS = _ROOT / ".claude" / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))  # for `from base import ...`
_spec = importlib.util.spec_from_file_location(
    "zai_delegation_enforcer", _HOOKS / "z-ai-delegation-enforcer.py"
)
zde = importlib.util.module_from_spec(_spec)
sys.modules["zai_delegation_enforcer"] = zde
_spec.loader.exec_module(zde)

_LANGFUSE_MOD = "src.pdf_framework.observability.langfuse_setup"

# Промпт обязан пройти NEVER-фильтр (без "архитектур", "отладка", "debug",
# "security", "причина ошибки" и т.д.) и быть длиннее _MIN_PROMPT_LEN,
# иначе execute() выйдет раньше вызова _delegation_level и тест позеленеет
# по ложной причине.
DELEGATABLE_PROMPT = "напиши функцию парсинга json в отдельном модуле проекта"


@pytest.fixture
def spy_langfuse():
    """Подменяет langfuse-эмиттер счётчиком вызовов (без сети)."""
    calls: list[dict] = []
    fake = types.ModuleType(_LANGFUSE_MOD)
    fake.emit_observation = lambda **kw: calls.append(kw)
    parents = {
        name: sys.modules.get(name) or types.ModuleType(name)
        for name in ("src", "src.pdf_framework", "src.pdf_framework.observability")
    }
    with mock.patch.dict(sys.modules, {**parents, _LANGFUSE_MOD: fake}):
        yield calls


@pytest.fixture(autouse=True)
def _span_off(monkeypatch):
    """Детерминизм: окружение разработчика не должно решать за тест."""
    monkeypatch.delenv("DELEGATION_ROUTING_SPAN", raising=False)


def test_helper_methods_exist():
    """Прямая причина: мерж удалил методы, оставив вызов."""
    for name in ("_bandit_level", "_router_level", "_should_canary", "_delegation_level"):
        assert hasattr(zde.ZAIDelegationEnforcer, name), f"потерян helper {name}"


def test_execute_does_not_raise_attribute_error(spy_langfuse):
    """Симптом: до фикса здесь падал AttributeError, погашенный BaseHook.run()."""
    hook = zde.ZAIDelegationEnforcer()
    inp = zde.HookInput({"hook_event_name": "UserPromptSubmit", "prompt": DELEGATABLE_PROMPT})
    hook.execute(inp)  # не должно бросать


def test_delegation_level_returns_level_and_method(spy_langfuse):
    """Контракт: (level, method_tag), method_tag из известного набора."""
    hook = zde.ZAIDelegationEnforcer()
    level, method = hook._delegation_level(DELEGATABLE_PROMPT, DELEGATABLE_PROMPT.lower())
    assert method in {"linucb", "router", "router-abstain-fallback"}
    assert level is None or isinstance(level, str)


def test_routing_span_disabled_by_default(spy_langfuse):
    """Бюджет хука: без флага телеметрия не трогается совсем.

    С включённым span хук занимает ~2.2 с при таймауте 3 с (замер 2026-07-26:
    _get_langfuse_client 740 мс + client.flush 1132 мс, амортизировать нечем -
    на каждый промпт стартует новый процесс).
    """
    hook = zde.ZAIDelegationEnforcer()
    hook._delegation_level(DELEGATABLE_PROMPT, DELEGATABLE_PROMPT.lower())
    assert spy_langfuse == [], "span не должен эмититься без DELEGATION_ROUTING_SPAN"


def test_routing_span_emitted_when_enabled(monkeypatch, spy_langfuse):
    """Гейт - именно гейт, а не удаление кода: под флагом span уходит."""
    monkeypatch.setenv("DELEGATION_ROUTING_SPAN", "1")
    hook = zde.ZAIDelegationEnforcer()
    hook._delegation_level(DELEGATABLE_PROMPT, DELEGATABLE_PROMPT.lower())
    assert len(spy_langfuse) == 1
    assert spy_langfuse[0]["name"] == "delegation.routing.decision"


def test_should_canary_off_by_default():
    """_ROUTER_CANARY_PCT=0.0 → router-путь не трогается (и его цена не платится)."""
    assert zde._ROUTER_CANARY_PCT == 0.0
    assert zde.ZAIDelegationEnforcer._should_canary("любой промпт") is False


def test_should_canary_is_deterministic_per_prompt(monkeypatch):
    """Один и тот же промпт всегда идёт одним путём (воспроизводимость A/B)."""
    monkeypatch.setattr(zde, "_ROUTER_CANARY_PCT", 0.5)
    first = zde.ZAIDelegationEnforcer._should_canary("стабильный промпт")
    for _ in range(5):
        assert zde.ZAIDelegationEnforcer._should_canary("стабильный промпт") is first


def test_should_canary_full_rollout(monkeypatch):
    monkeypatch.setattr(zde, "_ROUTER_CANARY_PCT", 1.0)
    assert zde.ZAIDelegationEnforcer._should_canary("любой промпт") is True
