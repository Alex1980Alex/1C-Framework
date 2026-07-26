"""Маршрутизация llm-rotation: model-aware выбор, бюджет, приоритет над adaptive.

Корни инцидента 2026-07-26 («не всегда переключается на нужную модель»):
  R1 per-server timeout 60000 в .mcp.json рвал вызов раньше, чем ротация успевала
     ротировать (force_primary жевал primary до 240с/попытка);
  R2 model-blind ротация: параметр model не влиял на выбор провайдера, фоллбэк тихо
     подменял модель вплоть до ЭСКАЛАЦИИ на opus (живой лог: provider=claude-cli-haiku,
     model=claude-opus-4-7);
  R3 adaptive score стоял раньше priority в сортировке — политика sonnet-first
     подрывалась скором (живые скоры: haiku 0.535 > sonnet 0.500-default).

Без сети: провайдерские вызовы мокается через monkeypatch _call_provider.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from src.shared.llm_rotation.config import LLMRotationSettings
from src.shared.llm_rotation.service import (
    DEFAULT_PROVIDERS,
    LLMRotationService,
    ProviderConfig,
    resolve_model_for_provider,
)


@pytest.fixture(autouse=True)
def _isolated_log(tmp_path, monkeypatch):
    """Completions-лог в tmp: тесты не должны писать в продовый data/*.jsonl
    (в живом логе уже лежали mock/test-provider от старых прогонов)."""
    monkeypatch.setenv("LLM_ROTATION_COMPLETIONS_LOG", str(tmp_path / "completions.jsonl"))


def _settings(**over) -> LLMRotationSettings:
    base = dict(
        force_primary=True,
        primary_max_retries=2,
        primary_retry_delay=0.0,
        max_retries=3,
        rate_limiting_enabled=False,
        health_check_enabled=False,
        adaptive_routing=True,
        persist_adaptive=False,
        total_budget_seconds=240,
        primary_budget_share=0.6,
        backoff_base_delay=0.0,
        backoff_max_delay=0.0,
        backoff_jitter=0.0,
    )
    base.update(over)
    return LLMRotationSettings(**base)


def _cfg(name: str, fmt: str = "claude-cli", priority: int = 0, **kw) -> ProviderConfig:
    defaults = dict(
        base_url="",
        api_key_env="",
        default_model="claude-sonnet-5" if fmt in ("claude-cli", "anthropic") else "qwen2.5:7b",
        models=[],
        format=fmt,
        requires_key=False,
        priority=priority,
    )
    defaults.update(kw)
    return ProviderConfig(name=name, **defaults)


# ── resolve_model_for_provider ─────────────────────────────────────────────────


def test_resolver_alias_and_full_names():
    cli = _cfg("cli")
    assert resolve_model_for_provider(cli, None) == "claude-sonnet-5"
    assert resolve_model_for_provider(cli, "sonnet") == "claude-sonnet-5"
    assert resolve_model_for_provider(cli, "haiku") == "claude-haiku-4-5"
    assert resolve_model_for_provider(cli, "claude-opus-4-8") == "claude-opus-4-8"


def test_resolver_rejects_foreign_models():
    cli = _cfg("cli")
    ollama = _cfg("ollama", fmt="ollama", models=["qwen2.5:7b", "llama3.1:8b"])
    # claude-провайдер не исполняет ollama-модель — сигнал скипа, не подмены
    assert resolve_model_for_provider(cli, "qwen2.5:7b") is None
    # ollama не исполняет claude-модель
    assert resolve_model_for_provider(ollama, "sonnet") is None
    # ollama исполняет своё, регистронезависимо (ревью sonnet 2026-07-26)
    assert resolve_model_for_provider(ollama, "QWEN2.5:7B") == "qwen2.5:7b"


def test_default_providers_do_not_escalate_tier():
    """Анти-эскалация: в списках models клод-провайдеров нет opus (живой случай
    эскалации haiku→opus в логе). Явный запрос model='opus' остаётся возможным."""
    by_name = {c.name: c for c in DEFAULT_PROVIDERS}
    for name in ("claude-cli-sonnet", "claude-cli-haiku"):
        expanded = {m.lower() for m in by_name[name].models}
        assert "opus" not in expanded
        assert not any(m.startswith("claude-opus") for m in expanded)


# ── выбор провайдера ───────────────────────────────────────────────────────────


def _service(providers, **settings_over) -> LLMRotationService:
    return LLMRotationService(providers=providers, settings=_settings(**settings_over))


def test_priority_dominates_adaptive_score():
    """R3: sonnet-first не подрывается adaptive-скором — приоритет решает, скор
    только tie-breaker. До фикса скор стоял раньше приоритета."""
    svc = _service(
        [
            _cfg("primary-sonnet", priority=0),
            _cfg("cheap-haiku", priority=1, default_model="haiku"),
        ]
    )
    # накачиваем cheap-haiku высоким скором (быстрый, дешёвый)
    for _ in range(10):
        svc._scorer.record("cheap-haiku", latency=1.0, tokens=100, quality=1.0)
    best = svc.get_best_provider()
    assert best is not None
    assert best.config.name == "primary-sonnet"


def test_adaptive_breaks_ties_within_same_priority():
    svc = _service(
        [
            _cfg("a", priority=1),
            _cfg("b", priority=1),
        ]
    )
    for _ in range(10):
        svc._scorer.record("b", latency=1.0, tokens=100, quality=1.0)
    best = svc.get_best_provider()
    assert best.config.name == "b"  # тот же приоритет → выигрывает скор


# ── complete(): model-aware и бюджет ───────────────────────────────────────────


def _run(coro):
    return asyncio.get_event_loop_policy().new_event_loop().run_until_complete(coro)


def test_incompatible_model_skips_to_capable_provider(monkeypatch):
    """R2: просим ollama-модель — claude-primary скипается по несовместимости,
    вызов уходит способному провайдеру, модель НЕ подменяется."""
    svc = _service(
        [
            _cfg("primary-cli", priority=0),
            _cfg("ollama", fmt="ollama", priority=2, models=["qwen2.5:7b"]),
        ]
    )
    calls: list[tuple[str, str]] = []

    async def fake_call(state, prompt, system_prompt, model, temperature, max_tokens, timeout):
        calls.append((state.config.name, model))
        return {
            "provider": state.config.name,
            "model": model,
            "text": "ok",
            "response_time": 0.01,
            "usage": {},
        }

    monkeypatch.setattr(svc, "_call_provider", fake_call)
    result = _run(svc.complete("hi", model="qwen2.5:7b"))
    assert [c[0] for c in calls] == ["ollama"]  # primary не получил чужую модель
    assert result["model"] == "qwen2.5:7b"
    assert result["requested_model"] == "qwen2.5:7b"
    assert result["substituted"] is False


def test_no_capable_provider_fails_loud(monkeypatch):
    """Никто не исполняет запрошенную модель → честная ошибка со сводкой,
    НЕ тихая подмена (класс вранья до фикса)."""
    svc = _service([_cfg("primary-cli", priority=0)])

    async def fake_call(*a, **k):  # не должен вызваться вовсе
        raise AssertionError("провайдер не должен был получить несовместимую модель")

    monkeypatch.setattr(svc, "_call_provider", fake_call)
    with pytest.raises(RuntimeError) as ei:
        _run(svc.complete("hi", model="qwen2.5:7b"))
    assert "model=qwen2.5:7b" in str(ei.value)


def test_explicit_model_not_substituted_on_fallback(monkeypatch):
    """Явный model при живом фоллбэке: второй провайдер получает ТУ ЖЕ модель
    (models_to_try не разворачивается в перебор чужих моделей)."""
    svc = _service(
        [
            _cfg("p0", priority=0),
            _cfg("p1", priority=1),
        ],
        primary_max_retries=1,
    )
    svc._settings.primary_provider = "p0"
    calls: list[tuple[str, str]] = []

    async def fake_call(state, prompt, system_prompt, model, temperature, max_tokens, timeout):
        calls.append((state.config.name, model))
        if state.config.name == "p0":
            raise RuntimeError("p0 down")
        return {
            "provider": state.config.name,
            "model": model,
            "text": "ok",
            "response_time": 0.01,
            "usage": {},
        }

    monkeypatch.setattr(svc, "_call_provider", fake_call)
    result = _run(svc.complete("hi", model="haiku"))
    assert calls[0] == ("p0", "claude-haiku-4-5")
    assert calls[-1] == ("p1", "claude-haiku-4-5")  # та же модель, не подмена
    assert result["substituted"] is False


def test_budget_caps_primary_and_leaves_room_for_fallback(monkeypatch):
    """R1: медленный primary не съедает весь бюджет — фоллбэк ГАРАНТИРОВАННО
    получает время (primary_budget_share). До фикса ротация не успевала ротировать."""
    svc = _service(
        [
            _cfg("p0", priority=0),
            _cfg("p1", priority=1),
        ],
        total_budget_seconds=20,
        primary_budget_share=0.5,
        primary_max_retries=5,
    )
    svc._settings.primary_provider = "p0"
    clock = {"t": 1000.0}
    monkeypatch.setattr("src.shared.llm_rotation.service.time.monotonic", lambda: clock["t"])
    calls: list[tuple[str, int]] = []

    async def fake_call(state, prompt, system_prompt, model, temperature, max_tokens, timeout):
        calls.append((state.config.name, timeout))
        if state.config.name == "p0":
            clock["t"] += 9.0  # каждая primary-попытка «длится» 9с
            raise RuntimeError("slow primary timeout")
        return {
            "provider": state.config.name,
            "model": model,
            "text": "ok",
            "response_time": 0.01,
            "usage": {},
        }

    monkeypatch.setattr(svc, "_call_provider", fake_call)
    result = _run(svc.complete("hi", max_tokens=100))
    p0_attempts = [c for c in calls if c[0] == "p0"]
    assert len(p0_attempts) < 5  # primary-бюджет (10с) отрезал ретраи, не 5 подряд
    assert result["provider"] == "p1"  # фоллбэк состоялся В бюджете
    # попыточный таймаут не превышает остаток бюджета
    assert all(t <= 20 for _n, t in calls)


def test_budget_exhaustion_fails_with_summary(monkeypatch):
    """Бюджет кончился до успеха → структурированная ошибка со сводкой попыток."""
    svc = _service(
        [_cfg("p0", priority=0)],
        total_budget_seconds=10,
        primary_budget_share=0.9,
        primary_max_retries=3,
        max_retries=2,
    )
    svc._settings.primary_provider = "p0"
    clock = {"t": 500.0}
    monkeypatch.setattr("src.shared.llm_rotation.service.time.monotonic", lambda: clock["t"])

    async def fake_call(state, *a, **k):
        clock["t"] += 6.0
        raise RuntimeError("boom")

    monkeypatch.setattr(svc, "_call_provider", fake_call)
    with pytest.raises(RuntimeError) as ei:
        _run(svc.complete("hi"))
    msg = str(ei.value)
    assert "budget 10s" in msg
    assert "boom" in msg  # сводка несёт фактическую причину


# ── лог не пишется в прод ──────────────────────────────────────────────────────


def test_completions_log_honors_env_override(tmp_path, monkeypatch):
    from src.shared.llm_rotation import service as svc_mod

    target = tmp_path / "x" / "log.jsonl"
    monkeypatch.setenv("LLM_ROTATION_COMPLETIONS_LOG", str(target))
    svc_mod._log_completion(provider="unit-test", model="m", response_time=0)
    assert target.is_file()
    assert "unit-test" in target.read_text(encoding="utf-8")
    prod = Path("data/llm-rotation-completions.jsonl")
    if prod.exists():
        tail = prod.read_text(encoding="utf-8", errors="replace")[-2000:]
        assert '"provider": "unit-test"' not in tail
