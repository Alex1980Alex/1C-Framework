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

# Изоляция completions/adaptive/budget-синков — в tests/conftest.py (единая точка).


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
    cli = _cfg("cli")  # свой тир — sonnet
    assert resolve_model_for_provider(cli, None) == "claude-sonnet-5"
    assert resolve_model_for_provider(cli, "sonnet") == "claude-sonnet-5"
    assert resolve_model_for_provider(cli, "claude-sonnet-5") == "claude-sonnet-5"
    # Строгое совпадение тира (решение пользователя 2026-07-26): claude-cli технически
    # запускает любую claude-модель, но исполнять ЧУЖОЙ тир «за компанию» больше нельзя —
    # иначе провайдер с именем claude-cli-haiku исполняет opus (живой лог эскалации).
    assert resolve_model_for_provider(cli, "haiku") is None
    assert resolve_model_for_provider(cli, "claude-opus-4-8") is None
    # тир исполняется тем, кто его ОБЪЯВЛЯЕТ
    haiku = _cfg("cli-haiku", default_model="haiku")
    assert resolve_model_for_provider(haiku, "haiku") == "claude-haiku-4-5"
    assert resolve_model_for_provider(haiku, "sonnet") is None


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


def test_paid_provider_declares_only_its_own_tier():
    """anthropic-sonnet объявляет только свой тир: под строгим совпадением любой лишний
    элемент означал бы, что платный провайдер молча исполнит чужой тир — для opus это
    расход денег на самой дорогой модели."""
    by_name = {c.name: c for c in DEFAULT_PROVIDERS}
    assert by_name["anthropic-sonnet"].models == ["claude-sonnet-5"]


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
            _cfg("p0", priority=0, default_model="haiku"),
            _cfg("p1", priority=1, default_model="haiku"),
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


def test_explicit_model_routes_to_its_own_tier_provider(monkeypatch):
    """model='haiku' уходит провайдеру ТИРА haiku, а primary-sonnet скипается.

    До этого запрос haiku исполнял primary claude-cli-sonnet, и имя провайдера в логе
    расходилось с фактически исполняемой моделью.
    """
    svc = _service(
        [
            _cfg("claude-cli-sonnet", priority=0),
            _cfg("claude-cli-haiku", priority=1, default_model="haiku"),
        ]
    )
    svc._settings.primary_provider = "claude-cli-sonnet"
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
    result = _run(svc.complete("hi", model="haiku"))
    assert calls == [("claude-cli-haiku", "claude-haiku-4-5")]
    assert result["provider"] == "claude-cli-haiku"


def test_opus_not_callable_without_opus_tier_provider(monkeypatch):
    """model='opus' — честный отказ, а НЕ исполнение на провайдере младшего тира.

    Это и есть исходный симптом расследования: в живом логе `provider=claude-cli-haiku,
    model=claude-opus-4-7`. Отказ обязан называть лечение (завести провайдера тира).
    """
    svc = _service(
        [
            _cfg("claude-cli-sonnet", priority=0),
            _cfg("claude-cli-haiku", priority=1, default_model="haiku"),
        ]
    )
    svc._settings.primary_provider = "claude-cli-sonnet"

    async def fake_call(*a, **k):
        raise AssertionError("провайдер младшего тира не должен получить opus")

    monkeypatch.setattr(svc, "_call_provider", fake_call)
    with pytest.raises(RuntimeError) as ei:
        _run(svc.complete("hi", model="opus"))
    msg = str(ei.value)
    assert "model=opus" in msg
    assert "DEFAULT_PROVIDERS" in msg, "отказ должен называть лечение, а не только факт"


def test_unavailable_own_tier_does_not_claim_model_undeclared(monkeypatch):
    """Провайдер нужного тира ЕСТЬ, но недоступен → отказ говорит про доступность,
    а НЕ «модель никем не объявлена».

    Судить по счётчику скипов нельзя: достаточно одного скипа по модели у чужого тира
    (здесь ollama) рядом с закулдауненным провайдером своего тира, чтобы сообщение
    соврало про причину. Поэтому ветка смотрит на ОБЪЯВЛЕНИЕ модели, а не на скипы.
    """
    svc = _service(
        [
            _cfg("cli-haiku", priority=0, default_model="haiku"),
            _cfg("ollama", fmt="ollama", priority=1, models=["qwen2.5:7b"]),
        ]
    )
    svc._settings.primary_provider = "cli-haiku"
    for _ in range(3):  # свой тир объявлен, но провайдер закулдаунен
        svc._providers["cli-haiku"].record_error("boom")
    assert not svc._providers["cli-haiku"].is_available()

    async def fake_call(*a, **k):
        raise AssertionError("недоступный провайдер не должен вызываться")

    monkeypatch.setattr(svc, "_call_provider", fake_call)
    with pytest.raises(RuntimeError) as ei:
        _run(svc.complete("hi", model="haiku"))
    msg = str(ei.value)
    assert "model=haiku" in msg
    assert "не объявляет" not in msg, "тир объявлен — врать про объявление нельзя"


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


def test_completions_sink_is_isolated_repo_wide():
    """Изоляция синка стоит в tests/conftest.py и потому действует на ВСЕ модули.

    Пофайловая фикстура уже протекла: её скопировали в test_llm_rotation.py, а соседний
    test_backoff.py остался без неё и продолжал писать в продовый лог (5 записей за
    прогон), причём llm_health.is_provider_down() читает этот же файл и мог из-за
    тестового мусора разоружить z-ai-write-guard. Тест краснеет, если блок из conftest
    убрать или обойти.
    """
    from src.shared.llm_rotation import service as svc_mod

    resolved = svc_mod._completions_log_path().resolve()
    prod_path = (svc_mod._REPO_ROOT / "data" / "llm-rotation-completions.jsonl").resolve()
    assert resolved != prod_path, "тест-прогон пишет в ПРОДОВЫЙ completions-лог"


def test_first_try_success_is_not_logged_as_retry(tmp_path, monkeypatch):
    """Успех с первой попытки: primary_attempts=1 и никакого «ретрая» в записи.

    Поле звалось primary_retries и инкрементилось ДО вызова, поэтому КАЖДЫЙ чистый
    вызов читался в логе как «был ретрай» и завышал видимое флапанье primary (живой
    прогон 2026-07-26: три реальных вызова, все с attempt=1 и primary_retries=1).
    """
    import json

    target = tmp_path / "completions.jsonl"
    monkeypatch.setenv("LLM_ROTATION_COMPLETIONS_LOG", str(target))
    svc = _service([_cfg("claude-cli-sonnet")], primary_provider="claude-cli-sonnet")

    async def ok(state, *a, **k):
        return {
            "provider": state.config.name,
            "model": "claude-sonnet-5",
            "text": "ok",
            "response_time": 1.0,
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        }

    monkeypatch.setattr(svc, "_call_provider", ok)
    _run(svc.complete("hi"))

    rec = json.loads(target.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert rec["attempt"] == 1
    assert rec["primary_attempts"] == 1
    assert "primary_retries" not in rec, "имя поля должно означать попытки, а не ретраи"
