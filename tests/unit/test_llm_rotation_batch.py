"""Батч-делегация и потолки пропускной способности llm-rotation (мандат 2026-07-26).

Мандат «настроить на максимальное использование» вскрыл три дыры, которые тут и пинятся:

  B1 `batch_complete` не принимал `model` и не передавал его в `complete()` — строгий
     тир (haiku/sonnet/opus), сделанный в тот же день, из батча был НЕДОСТИЖИМ, а
     explicit_only-провайдер (opus) недостижим тем более: его выбирает только явная модель.
  B2 общий старт конкурентности поднят 3→6 ради пропускной способности, но для
     провайдеров format="claude-cli" это означало бы 6 параллельных ПОЛНЫХ Claude Code
     (каждый вызов = вторая сессия со своей цепочкой хуков, ~2.8 ГБ commit). Инцидент
     2026-07-26 16:51 — сессия оборвалась молча ровно на llm_complete. Отсюда отдельный
     потолок batch_cli_concurrency, режущий И явный per-call аргумент.
  B3 `complete_batch` существовал в сервисе, но наружу MCP его не отдавал — параллельная
     делегация оркестратору была недоступна вовсе.

Без сети: `complete()` подменяется, провайдерских вызовов не происходит.
Изоляция completions/adaptive/budget-синков — в tests/conftest.py (единая точка).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

from src.shared.llm_rotation.config import LLMRotationSettings
from src.shared.llm_rotation.service import LLMRotationService, ProviderConfig


def _settings(**over) -> LLMRotationSettings:
    base = dict(
        force_primary=False,
        rate_limiting_enabled=False,
        health_check_enabled=False,
        persist_adaptive=False,
        primary_provider="p0",
    )
    base.update(over)
    return LLMRotationSettings(**base)


def _cfg(name: str = "p0", fmt: str = "claude-cli") -> ProviderConfig:
    return ProviderConfig(
        name=name,
        base_url="",
        api_key_env="",
        default_model="claude-sonnet-5" if fmt != "ollama" else "qwen2.5:7b",
        models=[],
        format=fmt,
        requires_key=False,
        priority=0,
    )


def _service(fmt: str = "claude-cli", **sover) -> LLMRotationService:
    return LLMRotationService(providers=[_cfg("p0", fmt)], settings=_settings(**sover))


def _peak_harness(svc: LLMRotationService, hold: float = 0.05):
    """Подменяет complete() счётчиком одновременно летящих вызовов.

    Возвращает callable, отдающий пиковую одновременность. Каждый вызов инкрементит
    счётчик ДО await, поэтому все допущенные семафором задачи успевают войти прежде,
    чем первая проснётся — пик детерминирован без гонки на медленной машине.
    """
    state = {"inflight": 0, "peak": 0}

    async def fake_complete(**kwargs):
        state["inflight"] += 1
        state["peak"] = max(state["peak"], state["inflight"])
        await asyncio.sleep(hold)
        state["inflight"] -= 1
        return {"provider": "p0", "text": "ok", "model": kwargs.get("model")}

    svc.complete = fake_complete  # type: ignore[method-assign]
    return lambda: state["peak"]


# ── B1: model доезжает из батча до complete() ──────────────────────────────────


def test_batch_passes_model_through_to_complete():
    """Без этого явный тир (и весь explicit_only-путь на opus) из батча недостижим."""
    svc = _service()
    seen: list[str | None] = []

    async def fake_complete(**kwargs):
        seen.append(kwargs.get("model"))
        return {"provider": "p0", "text": "ok"}

    svc.complete = fake_complete  # type: ignore[method-assign]
    results = asyncio.run(svc.batch_complete(["a", "b", "c"], model="opus"))

    assert seen == ["opus", "opus", "opus"], "model обязан транслироваться на КАЖДЫЙ промпт"
    assert len(results) == 3


def test_batch_without_model_keeps_auto_semantics():
    """model=None — авто-ротация; подмены на «какой-нибудь тир» быть не должно."""
    svc = _service()
    seen: list[str | None] = []

    async def fake_complete(**kwargs):
        seen.append(kwargs.get("model"))
        return {"provider": "p0", "text": "ok"}

    svc.complete = fake_complete  # type: ignore[method-assign]
    asyncio.run(svc.batch_complete(["a"]))

    assert seen == [None]


# ── B2: гейт спавнов claude-cli ────────────────────────────────────────────────
#
# Контроль стоит в ТОЧКЕ СПАВНА (_call_provider), а не на уровне батча. На уровне батча
# он был fail-open: там известен лишь ПРЕДПОЧИТАЕМЫЙ провайдер, а исполнителя выбирает
# ротация — preferred="ollama-local" при лежащем ollama давал фоллбэк на claude-cli и
# 6 полных Claude Code, ровно тот инцидент, против которого гард писался.


def _spawn_peak_harness(svc: LLMRotationService, fmt: str, hold: float = 0.05):
    """Считает ОДНОВРЕМЕННЫЕ спавны на уровне провайдерского запроса."""
    state = {"inflight": 0, "peak": 0}
    attr = {
        "claude-cli": "_make_request_claude_cli",
        "ollama": "_make_request_ollama",
    }[fmt]

    async def fake_request(*_a, **_kw):
        state["inflight"] += 1
        state["peak"] = max(state["peak"], state["inflight"])
        await asyncio.sleep(hold)
        state["inflight"] -= 1
        return {"choices": [{"message": {"content": "ok"}}], "usage": {}}

    setattr(svc, attr, fake_request)
    return lambda: state["peak"]


def _drive_provider_calls(svc: LLMRotationService, n: int):
    provider_state = next(iter(svc._providers.values()))

    async def _go():
        await asyncio.gather(*(svc._call_provider(provider_state, "p") for _ in range(n)))

    asyncio.run(_go())


def test_claude_cli_spawns_are_gated():
    """Не больше batch_cli_concurrency одновременных спавнов — при ЛЮБОМ маршруте."""
    svc = _service(fmt="claude-cli", batch_cli_concurrency=2)
    peak = _spawn_peak_harness(svc, "claude-cli")

    _drive_provider_calls(svc, 6)

    assert peak() <= 2, "гейт обязан держать инвариант «не больше N полных Claude Code»"


def test_cheap_provider_spawns_are_not_gated():
    """Гейт claude-cli не должен протекать на дешёвые форматы — иначе «6» декоративна."""
    svc = _service(fmt="ollama", batch_cli_concurrency=2)
    peak = _spawn_peak_harness(svc, "ollama")

    _drive_provider_calls(svc, 6)

    assert peak() == 6


def test_gate_survives_garbage_setting():
    """Мусорный 0 в env не должен обнулять семафор (ValueError в asyncio.Semaphore)."""
    svc = _service(fmt="claude-cli", batch_cli_concurrency=0)
    peak = _spawn_peak_harness(svc, "claude-cli")

    _drive_provider_calls(svc, 4)

    assert peak() == 1


def test_batch_level_concurrency_ignores_preferred_provider_format():
    """Уровень батча больше НЕ клемпит по preferred_provider.

    Раньше здесь стоял клемп по формату предпочитаемого провайдера — он и был
    fail-open. Теперь общая параллельность батча живёт как задана, а безопасность
    держит гейт спавнов; неизвестный provider не должен ни падать, ни менять её.
    """
    svc = _service(fmt="claude-cli", batch_cli_concurrency=2)
    peak = _peak_harness(svc)

    asyncio.run(svc.batch_complete(["x"] * 6, preferred_provider="нет-такого", concurrency=6))

    assert peak() == 6


# ── Р2: агрегатный дедлайн батча ───────────────────────────────────────────────


def test_batch_budget_returns_partial_instead_of_losing_everything():
    """Истёкший бюджет снимает недовыполненные, но НЕ выбрасывает готовые."""
    svc = _service(batch_budget_seconds=1)

    async def fake_complete(prompt: str = "", **kwargs):
        if prompt == "slow":
            await asyncio.sleep(30)
        return {"provider": "p0", "text": "fast"}

    svc.complete = fake_complete  # type: ignore[method-assign]
    results = asyncio.run(svc.batch_complete(["fast", "slow"], concurrency=2))

    assert results[0]["text"] == "fast", "готовый результат обязан пережить дедлайн"
    assert isinstance(results[1], TimeoutError)
    assert "batch budget" in str(results[1])


# ── Пропускная способность: значения конфига ───────────────────────────────────


def test_budget_stays_below_client_window():
    """Инвариант, а не константа: бюджет сервиса < клиентского окна из .mcp.json.

    Пинить `== 270` бессмысленно — опусти клиентский `timeout` до 120000, и такой
    тест остался бы зелёным, пока вызовы рвутся (находка ревьюера Р8).
    """
    mcp_cfg = json.loads(Path(".mcp.json").read_text(encoding="utf-8"))
    client_ms = mcp_cfg["mcpServers"]["llm-rotation"]["timeout"]
    s = LLMRotationSettings()

    assert s.total_budget_seconds * 1000 < client_ms
    # Батч-бюджет обязан истекать раньше per-call, иначе частичный результат не успеет
    # вернуться до обрыва клиентом.
    assert s.batch_budget_seconds < s.total_budget_seconds


def test_rotation_retries_cover_second_pass():
    """Авто-ротация видит трёх провайдеров; 3 ротации давали каждому ровно одну попытку."""
    assert LLMRotationSettings().max_retries == 5


def test_cli_concurrency_default_is_conservative():
    """Дефолт потолка спавн-провайдеров — не общие 6 (иначе 6 полных Claude Code)."""
    assert LLMRotationSettings().batch_cli_concurrency == 3


# ── B3: MCP-тул llm_complete_batch ─────────────────────────────────────────────


def _mcp():
    import src.shared.llm_rotation.mcp as m

    return m


def test_batch_tool_is_registered_with_prompts_required():
    m = _mcp()
    tools = {t.name: t for t in asyncio.run(m.list_tools())}

    assert "llm_complete_batch" in tools, "batch_complete был недостижим снаружи вовсе"
    schema = tools["llm_complete_batch"].inputSchema
    assert schema["required"] == ["prompts"]
    assert schema["properties"]["prompts"]["type"] == "array"
    # model обязан быть в схеме, иначе тир из батча не выбрать (B1)
    assert "model" in schema["properties"]
    assert "concurrency" in schema["properties"]


class _FakeService:
    def __init__(self, results):
        self._results = results
        self.calls: list[dict] = []

    async def batch_complete(self, prompts, **kwargs):
        self.calls.append({"prompts": prompts, **kwargs})
        return self._results


def _run_batch_tool(monkeypatch, results, arguments):
    """Гоняет ветку call_tool, перехватывая сервис и per-call лог."""
    m = _mcp()
    fake = _FakeService(results)
    logged: list[tuple] = []
    monkeypatch.setattr(m, "_get_service", lambda: fake)
    monkeypatch.setattr(
        m, "_log_call", lambda *a, **kw: logged.append((kw.get("ok"), kw.get("error_type")))
    )
    out = asyncio.run(m.call_tool("llm_complete_batch", arguments))
    return fake, logged, json.loads(out[0].text)


def test_batch_tool_forwards_model_and_concurrency(monkeypatch):
    fake, _, payload = _run_batch_tool(
        monkeypatch,
        [{"provider": "p0", "text": "a"}],
        {"prompts": ["one"], "model": "haiku", "concurrency": 4},
    )

    assert fake.calls[0]["model"] == "haiku"
    assert fake.calls[0]["concurrency"] == 4
    assert fake.calls[0]["return_exceptions"] is True
    assert payload["ok"] == 1 and payload["failed"] == 0


def test_batch_tool_reports_partial_failure_honestly(monkeypatch):
    """Батч, где часть упала, не имеет права читаться как чистый успех."""
    _, logged, payload = _run_batch_tool(
        monkeypatch,
        [{"provider": "p0", "text": "a"}, RuntimeError("boom")],
        {"prompts": ["one", "two"]},
    )

    assert payload["total"] == 2 and payload["ok"] == 1 and payload["failed"] == 1
    failed = [r for r in payload["results"] if not r["ok"]][0]
    assert failed["index"] == 1
    assert failed["error_type"] == "RuntimeError"
    assert "boom" in failed["error"]
    assert logged == [(True, "partial_failure")]


def test_batch_tool_reports_total_failure(monkeypatch):
    _, logged, payload = _run_batch_tool(
        monkeypatch,
        [RuntimeError("a"), RuntimeError("b")],
        {"prompts": ["one", "two"]},
    )

    assert payload["ok"] == 0 and payload["failed"] == 2
    assert logged == [(False, "all_failed")]


def test_batch_tool_logs_machine_readable_counters(monkeypatch):
    """У `error_type` в этом стоке нет читателя (tool_llm_judge смотрит только `ok`),
    поэтому «9 из 10 упало» обязано быть видно плоскими счётчиками."""
    m = _mcp()
    monkeypatch.setattr(
        m,
        "_get_service",
        lambda: _FakeService([{"provider": "p0", "text": "a"}, RuntimeError("x")]),
    )
    captured: dict = {}
    monkeypatch.setattr(m, "_log_call", lambda *a, **kw: captured.update(kw))

    asyncio.run(m.call_tool("llm_complete_batch", {"prompts": ["a", "b"]}))

    assert captured["batch_total"] == 2
    assert captured["batch_failed"] == 1


def test_service_fields_cannot_shadow_index_and_ok(monkeypatch):
    """Поле из результата провайдера не имеет права затереть выравнивание и признак успеха."""
    _, _, payload = _run_batch_tool(
        monkeypatch,
        [{"provider": "p0", "text": "a", "index": 999, "ok": False}],
        {"prompts": ["one"]},
    )

    assert payload["results"][0]["index"] == 0
    assert payload["results"][0]["ok"] is True


def test_batch_tool_clean_success_is_clean(monkeypatch):
    _, logged, payload = _run_batch_tool(
        monkeypatch,
        [{"provider": "p0", "text": "a"}],
        {"prompts": ["one"]},
    )

    assert logged == [(True, None)]
    assert payload["results"][0]["text"] == "a"


@pytest.mark.parametrize("bad", [[], "not-a-list", [1, 2], None])
def test_batch_tool_rejects_malformed_prompts(monkeypatch, bad):
    """Невнятный вход отсекается на границе, а не внутри gather.

    Контракт MCP-обёртки: исключение НЕ пробрасывается наружу, а превращается в
    структурный конверт {"ok": false, ...} + честный per-call лог ok=False. Голая
    строка была бы для клиента неотличима от успешного текста.
    """
    m = _mcp()
    fake = _FakeService([])
    logged: list[tuple] = []
    monkeypatch.setattr(m, "_get_service", lambda: fake)
    monkeypatch.setattr(
        m, "_log_call", lambda *a, **kw: logged.append((kw.get("ok"), kw.get("error_type")))
    )

    out = asyncio.run(m.call_tool("llm_complete_batch", {"prompts": bad}))
    payload = json.loads(out[0].text)

    assert payload["ok"] is False
    assert payload["tool"] == "llm_complete_batch"
    assert "prompts" in payload["error"]
    assert logged == [(False, "ValueError")]
    assert fake.calls == [], "провальная валидация не имеет права дойти до сервиса"


# ── Покрытие фреймворка: Category 2 по умолчанию ───────────────────────────────


def test_category_two_components_enabled_by_default(monkeypatch):
    """Cat-2 числилась «opt-in через env», но env читается сырым os.environ, а
    load_dotenv() во фреймворке не зовётся — настройка была мёртвой."""
    from src.shared.llm_rotation import adapter

    monkeypatch.delenv("LLM_ROTATION_COMPONENTS", raising=False)
    monkeypatch.setattr(adapter, "_enabled_components", None)

    for name in ("section_summary", "entity_extractor", "community_summarizer"):
        assert adapter.is_cheap_llm_enabled(name), f"{name} обязан идти по дешёвому тиру"


def test_explicit_component_list_still_overrides(monkeypatch):
    """Откат к прежнему поведению остаётся возможен явным списком."""
    from src.shared.llm_rotation import adapter

    monkeypatch.setenv("LLM_ROTATION_COMPONENTS", "grader")
    monkeypatch.setattr(adapter, "_enabled_components", None)

    assert adapter.is_cheap_llm_enabled("grader")
    assert not adapter.is_cheap_llm_enabled("entity_extractor")
