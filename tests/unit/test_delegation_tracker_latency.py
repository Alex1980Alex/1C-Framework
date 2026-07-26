"""Регресс: советчик делегирования не считает штатную латентность claude-cli аномалией.

Живой прогон 2026-07-26: успешный вызов claude-cli-sonnet за 66.18с получил от хука
«Z.AI response was slow (66.2s from claude-cli-sonnet). Consider switching provider».
Два дефекта в одной строке: имя Z.AI (провайдер удалён из ротации 2026-05-16) и порог
15с, откалиброванный под HTTP-провайдера, тогда как спавн claude-cli это 25-150с по
документации. Совет «смени провайдера» уводил с sonnet-first — против политики, ради
которой и чинилась маршрутизация.

Тесты пинят ОБЕ стороны инварианта: CLI-вызов на 66с молчит, HTTP-вызов на тех же 66с
по-прежнему помечается. Без второй половины правка выродилась бы в «отключили проверку».

Payload построен по ФАКТИЧЕСКОЙ форме PostToolUse от MCP-тула (tool_response = список
content-блоков, JSON внутри `text`), снятой с живого вызова, а не по выдуманной —
юнит-фикстура формы payload лжёт ([[feedback-hook-payload-shape-live-contract]]).
"""

import importlib.util
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

_HOOK = (
    Path(__file__).resolve().parents[2] / ".claude" / "hooks" / "posttooluse-delegation-tracker.py"
)

# Форма результата сервиса — снята с живого вызова 2026-07-26 (66.182с, sonnet, 2144 токена).
_LIVE_RESULT = {
    "provider": "claude-cli-sonnet",
    "model": "claude-sonnet-5",
    "text": "## Диагностика маршрутизации\n\n" + "содержательный абзац текста. " * 40,
    "response_time": 66.182,
    "usage": {"prompt_tokens": 625, "completion_tokens": 2144},
    "attempt": 1,
    "requested_model": None,
    "substituted": False,
}


def _load():
    spec = importlib.util.spec_from_file_location("posttooluse_delegation_tracker", _HOOK)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(module, monkeypatch, **over):
    """Прогнать хук на реальной форме payload. Запись в data/ подавлена: тест не должен
    писать в продовый delegation-outcomes.jsonl (ровно тот дефект, что чинится рядом)."""
    monkeypatch.setattr(module, "_log_outcome", lambda entry: None)
    result = {**_LIVE_RESULT, **over}
    raw = {
        "hook_event_name": "PostToolUse",
        "tool_name": "mcp__llm-rotation__llm_complete",
        "session_id": "regress-session",
        "tool_input": {"prompt": "сгенерируй текст раздела"},
        "tool_response": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
    }
    return module.PostToolUseDelegationTracker().execute(module.HookInput(raw))


def test_cli_provider_gets_wider_latency_profile():
    """claude-cli спавнит субпроцесс — норма шире, чем у HTTP-провайдера."""
    m = _load()
    cli_fast, cli_slow = m._latency_profile("claude-cli-sonnet")
    http_fast, http_slow = m._latency_profile("ollama-local")
    assert cli_slow > http_slow
    assert cli_slow >= 150.0, "25-150с — документированная норма спавна claude-cli"
    assert m._latency_profile("claude-cli-haiku") == (cli_fast, cli_slow)
    assert m._latency_profile("anthropic-sonnet") == (http_fast, http_slow)
    # нераспознанный провайдер (например, неразобранный ответ) → строгий HTTP-профиль:
    # fail-closed, детект аномалий не ослабляется неизвестностью
    assert m._latency_profile("unknown") == (http_fast, http_slow)
    assert m._latency_profile("") == (http_fast, http_slow)


def test_live_66s_sonnet_call_is_not_flagged(monkeypatch):
    """Живой случай: успешный 66с-вызов sonnet НЕ порождает advisory."""
    m = _load()
    assert _run(m, monkeypatch) is None


def test_http_provider_still_flagged_when_slow(monkeypatch):
    """Обратная сторона: те же 66с от HTTP-провайдера остаются аномалией.

    Саботаж-проверка: если «починить» хук, задрав порог для всех, этот тест покраснеет.
    """
    m = _load()
    out = _run(m, monkeypatch, provider="ollama-local", model="qwen2.5-coder:7b")
    assert out is not None
    assert "Delegate slow" in json.dumps(out._data, ensure_ascii=False)


def test_http_advisory_bar_unchanged(monkeypatch):
    """Порог совета для HTTP-провайдеров остался прежним (15с), а не уехал на 10с.

    До правки advisory жил на 15с, а штраф эвристики — на 10с. Профиль мог молча
    схлопнуть две разные константы в одну и добавить ложные «slow» обычным HTTP-вызовам.
    """
    m = _load()
    assert m._latency_profile("anthropic-sonnet")[1] == 15.0
    http = dict(provider="anthropic-sonnet", model="claude-sonnet-5")
    assert _run(m, monkeypatch, response_time=12.0, **http) is None
    assert _run(m, monkeypatch, response_time=20.0, **http) is not None


def test_empty_response_still_flagged(monkeypatch):
    """Пустой ответ — аномалия независимо от провайдера и латентности."""
    m = _load()
    assert _run(m, monkeypatch, text="") is not None


def test_quality_score_not_penalized_for_normal_cli_latency():
    """Штрафа «slow» нет на штатных 66с CLI, но он есть за пределами нормы."""
    m = _load()
    text = "## Заголовок\n\n" + "- пункт списка\n" * 30
    cli = m._latency_profile("claude-cli-sonnet")
    normal = m._quality_heuristic(text, 66.182, *cli)
    beyond = m._quality_heuristic(text, 300.0, *cli)
    http = m._quality_heuristic(text, 66.182, *m._latency_profile("ollama-local"))
    assert "slow" not in normal["details"]
    assert beyond["details"].get("slow") is True
    assert http["details"].get("slow") is True
    assert normal["score"] > beyond["score"]


def test_no_stale_zai_wording_in_hook():
    """Имя удалённого провайдера не должно возвращаться в тексты советов."""
    source = _HOOK.read_text(encoding="utf-8")
    assert "Z.AI" not in source
    assert "Consider switching provider" not in source, (
        "совет уводит с sonnet-first на штатной латентности CLI"
    )
