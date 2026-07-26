"""Unit tests for §4.5.3 A/B canary routing logic in z-ai-delegation-enforcer.

Targets `ZAIDelegationEnforcer._should_canary` static method —
deterministic per-prompt routing decision. Pure logic test, no
TrainedRouter or LinUCB invocation.

Imports the hook module via importlib because filename contains '-'
(non-importable as regular package).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Маркер добавлен 2026-07-26 по вердикту ревьюера. Без него CI-гейт (`pytest -m unit`)
# этот файл НЕ отбирал — а он весь построен на `_should_canary`, то есть был обязан
# краснеть все два месяца, пока helper-блок отсутствовал. Это и есть корень
# «бесшумности» инцидента: тест, ловивший баг, находился вне гейта.
pytestmark = pytest.mark.unit


def _load_enforcer_module(canary_pct: float, monkeypatch: pytest.MonkeyPatch) -> object:
    """Re-import enforcer with custom DELEGATION_ROUTER_CANARY_PCT."""
    monkeypatch.setenv("DELEGATION_ROUTER_CANARY_PCT", str(canary_pct))
    # Ensure shared/hooks base modules are findable
    hook_dir = Path(__file__).resolve().parent.parent.parent / ".claude" / "hooks"
    sys.path.insert(0, str(hook_dir))
    spec = importlib.util.spec_from_file_location(
        "z_ai_delegation_enforcer_test_load",
        hook_dir / "z-ai-delegation-enforcer.py",
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_should_canary_zero_pct_always_false(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_enforcer_module(0.0, monkeypatch)
    cls = mod.ZAIDelegationEnforcer
    for prompt in ("alpha", "beta", "gamma", "delta", "epsilon"):
        assert cls._should_canary(prompt) is False


def test_should_canary_full_pct_always_true(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_enforcer_module(1.0, monkeypatch)
    cls = mod.ZAIDelegationEnforcer
    for prompt in ("alpha", "beta", "gamma", "delta", "epsilon"):
        assert cls._should_canary(prompt) is True


def test_should_canary_deterministic_per_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Same prompt must always route to the same path."""
    mod = _load_enforcer_module(0.5, monkeypatch)
    cls = mod.ZAIDelegationEnforcer
    prompt = "this is a stable test prompt"
    first = cls._should_canary(prompt)
    for _ in range(20):
        assert cls._should_canary(prompt) is first


def test_should_canary_distribution_approximates_pct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Over many distinct prompts, canary rate ≈ configured pct."""
    mod = _load_enforcer_module(0.5, monkeypatch)
    cls = mod.ZAIDelegationEnforcer
    n = 500
    hits = sum(1 for i in range(n) if cls._should_canary(f"prompt-{i}"))
    rate = hits / n
    # Allow ±10pp tolerance for n=500 binomial with p=0.5
    assert 0.40 <= rate <= 0.60, f"rate {rate:.2f} out of expected band"


def test_should_canary_low_pct_distribution(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_enforcer_module(0.1, monkeypatch)
    cls = mod.ZAIDelegationEnforcer
    n = 500
    hits = sum(1 for i in range(n) if cls._should_canary(f"prompt-{i}"))
    rate = hits / n
    # Allow ±5pp tolerance for n=500 binomial with p=0.1
    assert 0.05 <= rate <= 0.15, f"rate {rate:.3f} out of expected band"


def test_should_canary_high_pct_distribution(monkeypatch: pytest.MonkeyPatch) -> None:
    mod = _load_enforcer_module(0.9, monkeypatch)
    cls = mod.ZAIDelegationEnforcer
    n = 500
    hits = sum(1 for i in range(n) if cls._should_canary(f"prompt-{i}"))
    rate = hits / n
    # Allow ±5pp tolerance for n=500 binomial with p=0.9
    assert 0.85 <= rate <= 0.95, f"rate {rate:.3f} out of expected band"
