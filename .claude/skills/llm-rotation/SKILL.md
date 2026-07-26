---
name: llm-rotation
description: "LLM Rotation Service — мульти-провайдерное LLM API с автофоллбэком. ИСПОЛЬЗУЙ когда делегируешь генерацию на дешёвый тир (sonnet-first), проверяешь статус/маршрут провайдеров, сбрасываешь failed provider. Триггеры: 'llm_complete', 'llm rotation', 'провайдер LLM', 'llm_route_explain', 'fallback LLM', 'llm_reset_provider', 'llm_test_providers', 'делегировать генерацию'. НЕ для прямых вызовов Anthropic API (→ claude-api)."
---

# LLM Rotation Service

## When to Use
- Multi-provider LLM completion with automatic fallback
- Provider health monitoring and rotation
- Z.AI proxy (OpenAI -> Anthropic format translation)
- MCP tools: `llm_complete`, **`llm_complete_batch`** (веерная отправка N промптов ПАРАЛЛЕЛЬНО — один вызов вместо N последовательных), `llm_get_stats`, `llm_reset_provider`, `llm_test_providers`, `llm_list_providers`, **`llm_route_explain`** (какая модель будет выбрана и почему — БЕЗ вызова LLM)

## Architecture

```
LLMRotationService
  ├── ProviderConfig (5 providers, priority-ordered)
  ├── ProviderState (health tracking per provider)
  ├── complete() → auto-fallback on error
  └── _make_request_openai() / _make_request_ollama()

ZAIProxy (HTTP server, port 8000)
  ├── openai_to_anthropic() — request conversion
  ├── anthropic_to_openai() — response conversion
  └── SSE streaming support
```

## Providers (priority order — sonnet-first, 2026-07-04)

| # | Provider | Model | Format | Key Required |
|---|----------|-------|--------|-------------|
| 0 | **claude-cli-sonnet** | `claude-sonnet-5` | **claude-cli** | No (CLI subscription) — **primary** |
| 1 | **claude-cli-haiku** | `haiku` → claude-haiku-4-5 | **claude-cli** | No (CLI subscription) |
| 2 | ollama-local | qwen2.5-coder:7b | ollama | No |
| 3 | anthropic-sonnet | `claude-sonnet-5` | anthropic | **Yes** (ANTHROPIC_API_KEY — silent skip if unset) |
| 5 | **claude-cli-opus** | `claude-opus-5` | **claude-cli** | No — **`explicit_only`: только по явному `model`, вне авто-ротации** |

Model-ID resolution (единый источник — `MODEL_ALIASES` в `service.py`, актуализировано 2026-07-26):
`haiku`→`claude-haiku-4-5`, `sonnet`→`claude-sonnet-5`, `opus`→`claude-opus-5`.
claude-cli-sonnet и anthropic-sonnet прибиты к `claude-sonnet-5` явно. **После правки моделей
в коде нужен `/mcp reconnect`** — stdio-сервер держит старый код ([[feedback-mcp-stale-code-reconnect]]).

**claude-cli-** providers use `claude -p` subprocess via the user's Claude Code CLI subscription quota (flat-rate, not token-billed). Latency 5-15s per spawn — acceptable for batch/indexing, **not for hot-path** (Self-RAG grader, hallucination check). For hot-path, set `ANTHROPIC_API_KEY` to enable anthropic-sonnet HTTP escape hatch.

## Зачем это: экономия токенов по тиру модели

**Главная цель llm-rotation — не скорость, а экономия токенов/квоты за счёт понижения тира модели.**
Оркестратор (Claude Code — этот агент) работает на дорогом верхнем тире (**Opus**), который «жжёт»
квоту в разы быстрее младших моделей. Делегируя рутинную генерацию через `llm_complete`, ты уводишь
её на **дешёвый тир** (`claude-haiku-4-5` / `claude-sonnet-5`) или на бесплатный локальный `ollama-local` —
и экономия реальна **даже в рамках одной подписки**, потому что разные тиры расходуют общую квоту с разной
скоростью (Opus ≫ Sonnet > Haiku). Латентность 20–30 с здесь **не минус, а плата за экономию** — этот путь
для фоновой/batch-генерации, не для hot-path.

| Тир | Провайдер | Стоимость | Когда |
|---|---|---|---|
| Верхний (оркестратор) | Opus (текущая сессия) | Самый дорогой по квоте | Планирование, ревью, сложные решения |
| Дешёвый делегат | claude-cli-haiku / -sonnet | Та же подписка, младший тир — расход квоты ×N меньше | grader, извлечение сущностей, черновики, summary |
| Бесплатный | ollama-local (qwen2.5-coder:7b) | $0 (локально) | где хватает 7B, максимум экономии |
| Платный (выкл.) | anthropic-sonnet | Per-token API — **тратит деньги** | только hot-path <2с при заданном `ANTHROPIC_API_KEY` |

**Правило делегирования** (память `Opus = Planner/Reviewer, delegate generation`): что можно унести
на младший тир без потери качества — уносить (через `llm_complete` / CheapLLM-адаптер); дорогой
верхний тир беречь для того, что реально требует силы модели. Мерять эффект — `data/llm-rotation-metrics.jsonl`
(provider, tokens, fallback) + `llm_get_stats`.

**Removed** (broken / misconfigured per audit): zai-glm5, zhipu, gemini, openrouter, mistral, ollama-cloud. Re-add via custom `providers=` arg to `LLMRotationService` if needed.

## Маршрутизация (актуализировано 2026-07-26)

- **Сквозной бюджет**: весь `complete()` (force-primary + fallback) живёт в
  `LLM_ROTATION_TOTAL_BUDGET_SECONDS=240`; primary капится `primary_budget_share=0.6` —
  фоллбэку ГАРАНТИРОВАННО остаётся время (раньше primary с ретраями съедал всё окно).
- **⚠ Per-server timeout**: `.mcp.json` → `llm-rotation.timeout=300000`. Это поле
  **СИЛЬНЕЕ** env `MCP_TOOL_TIMEOUT` — прежние 60000 рвали вызовы на 60с при «живом»
  MCP_TOOL_TIMEOUT=240000. После правки — `/mcp reconnect`.
- **Model-aware, строгое совпадение тира** (решение пользователя 2026-07-26):
  `resolve_model_for_provider` сверяет запрошенную модель со СВОИМ набором провайдера
  (`default_model` + `models`) — одинаково для всех форматов. claude-cli технически
  запускает любую claude-модель, но исполнять чужой тир «за компанию» больше нельзя:
  именно так провайдер `claude-cli-haiku` исполнял opus. Практика:
  `model="haiku"` → `claude-cli-haiku` (primary-sonnet **скипается**),
  `model="sonnet"` → `claude-cli-sonnet`,
  `model="opus"` → `claude-cli-opus` (`claude-opus-5`) — тир заведён 2026-07-26.
  Чтобы вызывать новый тир — завести провайдера этого тира в `DEFAULT_PROVIDERS`
  (или передать `providers=`); пока провайдера нет, отказ честный `RuntimeError`,
  называющий лечение. Явная модель НЕ подменяется тихо; в ответе
  `requested_model` + `substituted`.
- **`explicit_only` — тир по явному запросу** (мандат 2026-07-26: из сессии любого тира,
  включая Fable, дотягиваться до opus/sonnet/haiku по сложности задачи). `claude-cli-opus`
  объявлен `explicit_only=True`: при `model=None` он **невидим** для авто-ротации, поэтому
  падение sonnet/haiku не уводит молча на самый дорогой тир. Выбор тира — за вызывающим.
- **Анти-эскалация**: списки `models` сужены до своего тира у ВСЕХ провайдеров, включая
  платный `anthropic-sonnet` (`["claude-sonnet-5"]`) — иначе явный opus молча ушёл бы на
  самый дорогой платный тир.
- **Скип ≠ попытка**: провайдер, пропущенный по несовместимости модели, не тратит единицу
  `max_retries` — иначе провайдер нужного тира с низким приоритетом (opus, priority=5)
  не получал бы очереди вовсе.
- **Priority > adaptive**: скор — только tie-breaker внутри одного приоритета
  (sonnet-first не подрывается; `max_latency` нормализации 30→120с — CLI-спавн 25-150с
  больше не дискриминируется).
- **Диагностика**: `llm_route_explain` + per-call лог `.claude/cache/mcp-llm-rotation-calls.jsonl`
  (обвязка `mcp_call_log`, N-P2.2-класс) + completions-лог по абсолютному пути с env-override
  `LLM_ROTATION_COMPLETIONS_LOG` (тесты больше не пишут в продовый jsonl).

## Health States

| Status | Meaning | Available? |
|--------|---------|-----------|
| HEALTHY | Normal operation | Yes |
| DEGRADED | 1-2 errors, still usable | Yes |
| COOLDOWN | 3+ errors or rate limit (429) | No (until expires) |
| UNAVAILABLE | Permanently disabled | No |

- Rate limit (429) -> 60s cooldown
- 3+ consecutive errors -> 5min cooldown
- Success resets consecutive errors -> HEALTHY

## Installation

```bash
pip install -e ".[llm-rotation]"
```

Pulls (per `pyproject.toml`):
- `mistralai>=1.0`, `openai>=1.0`, `google-generativeai>=0.8` — provider SDKs
- **`claude-agent-sdk>=0.2,<0.3`** — Anthropic Python package for `claude-cli-*` providers (roadmap 260516 Phase 1, commit `8742cb090`). Manages CLI subprocess + agent loop internally, exposes typed messages (`AssistantMessage`, `ResultMessage`). Required for `format="claude-cli"` providers; HTTP providers (anthropic-sonnet, ollama-local) don't need it.

## Configuration

```env
LLM_ROTATION_PRIMARY_PROVIDER=claude-cli-sonnet
LLM_ROTATION_MAX_RETRIES=5          # 3→5 (2026-07-26): три ротации давали каждому из
                                    # трёх авто-провайдеров ровно одну попытку
LLM_ROTATION_TIMEOUT=90             # per-попытка, базовый тир (max_tokens ≤1024)
LLM_ROTATION_COOLDOWN_SECONDS=300
LLM_ROTATION_RATE_LIMIT_COOLDOWN=60
```

**Пропускная способность (2026-07-26, мандат «максимальное использование»):**

| Ключ | Знач. | Смысл |
|---|---|---|
| `total_budget_seconds` | **270** | сквозной бюджет ВСЕГО `complete()`. Обязан быть строго ниже клиентского окна (`.mcp.json` → `llm-rotation.timeout` = 300000 мс), иначе клиент обрывает вызов раньше ответа. Инвариант запинен тестом |
| `LLM_ROTATION_BATCH_CONCURRENCY` | **6** | стартовая параллельность `llm_complete_batch` (задана в `.mcp.json`; читается сырым `os.environ`, в `.env` НЕ подхватится) |
| `batch_cli_concurrency` (`LLM_ROTATION_BATCH_CLI_CONCURRENCY`) | **3** | ⚠ отдельный потолок для `format="claude-cli"`. Каждый такой вызов спавнит **полный второй Claude Code** (своя сессия + цепочка хуков, ~2.8 ГБ commit) — шесть параллельных кладут сессию по нехватке commit-памяти (инцидент 2026-07-26 16:51). Режет и явный per-call `concurrency`: это предохранитель машины, а не подсказка. Клемп громкий (`logger.warning`) |

⚠ **`LLM_ROTATION_TIMEOUT` убран из `.mcp.json`** (там стояло `60`, перебивая `.env`): живой максимум успешного claude-cli вызова — 66 с, то есть порог рвал вызовы. Теперь действует 90/120/240 по тиру `max_tokens`.

API keys: только `ANTHROPIC_API_KEY` (для `anthropic-sonnet`, опционально — по умолчанию не задан → провайдер молча пропускается). Ключи `ZHIPU/GEMINI/OPENROUTER/MISTRAL` **больше не используются** (провайдеры удалены 2026-05-16; мёртвые записи вычищены из `.mcp.json` 2026-07-04). `ZAI_API_KEY` нужен только автономному `zai_proxy.py`, не самой ротации.

## CheapLLM Adapter

Bridge between LLM Rotation and framework components. Cheap LLM first, falls back to Claude on failure.

### Integrated Components

| Component | Cat | max_tokens | File |
|-----------|-----|------------|------|
| grader | 1 | 50 | `agents/rag/nodes/grader.py` |
| hallucination_checker | 1 | 100 | `agents/rag/nodes/hallucination_checker.py` |
| rewriter | 1 | 200 | `agents/rag/nodes/rewriter.py` |
| query_expansion | 1 | 300 | `search/query_expansion.py` |
| hyde | 1 | 512 | `search/hyde.py` |
| search_classifier | 1 | 100 | `search/routing/classifier.py` |
| context_generator | 1 | 200 | `processing/context_generator.py` |
| qa_answer | 1 | 2048 | RAG-ответ `/search/ask` |
| section_summary | 2 | 300 | `processing/section_summary.py` |
| entity_extractor | 2 | 4096 | `processing/extractors/entity_extractor.py` |
| community_summarizer | 2 | 1024 | `graph_store/summarizer.py` |

**Все компоненты включены по умолчанию, включая Category 2** (2026-07-26). Раньше дефолт
брал только Category 1, а Category 2 числилась «opt-in через `LLM_ROTATION_COMPONENTS`» —
и это была **мёртвая настройка**: env читается сырым `os.environ`, а `load_dotenv()` во
фреймворке не зовётся нигде, кроме `zai_proxy.py`, поэтому запись в `.env` не подхватилась
бы ни одним процессом. Страховка качества прежняя: провал/пустой ответ дешёвого тира →
`cheap_llm_call` возвращает `""` → вызывающий уходит на Claude. Откат к прежнему
поведению — явным списком Cat-1 в `LLM_ROTATION_COMPONENTS`.

### Quality Criteria (`QUALITY_CRITERIA` in adapter.py)

| Metric | Components |
|--------|-----------|
| exact_match | grader (yes/no), hallucination_checker (grounded/not_grounded) |
| different_from_input | rewriter |
| valid_json | entity_extractor |
| valid_classification | search_classifier |
| min_length | hyde (30), section_summary (20), context_generator (10), community_summarizer (30) |

### Auto-Discovery

`discover_unregistered_components()` scans `src/` for ChatAnthropic/Anthropic not in COMPONENT_REGISTRY.

### Metrics

JSONL: `data/llm-rotation-metrics.jsonl` (ts, component, provider, response_time, success, fallback, text_len).

## Key Files

| File | Purpose |
|------|---------|
| `src/shared/llm_rotation/config.py` | Pydantic-settings config |
| `src/shared/llm_rotation/service.py` | Core service + providers |
| `src/shared/llm_rotation/adapter.py` | CheapLLM adapter + quality + auto-discovery |
| `src/shared/llm_rotation/zai_proxy.py` | Z.AI OpenAI->Anthropic proxy |
| `src/shared/llm_rotation/mcp.py` | MCP server (7 tools) |
| `tests/integration/test_llm_rotation.py` | 34 теста. ⚠ 2026-07-26 файл не нёс **ни одного** маркера → оба CI-гейта (`-m "unit and not slow"` и `-m "integration or e2e"`) отсеивали его целиком, и `test_provider_priority_order` краснел незамеченным после ввода тира opus. Добавлен `pytestmark = pytest.mark.unit` (тесты офлайновые) |
| `tests/unit/test_llm_rotation_batch.py` | 20 unit: батч, потолки конкурентности, MCP-тул, Category 2 |

⚠ **После правки кода MCP-сервера — `/mcp reconnect`**: stdio держит старый код, новый
`llm_complete_batch` до переподключения не появится ([[feedback-mcp-stale-code-reconnect]]).

## Usage

```python
from src.shared.llm_rotation.service import LLMRotationService

service = LLMRotationService()
result = await service.complete(
    prompt="Explain X",
    system_prompt="You are helpful.",
    temperature=0.7,
    max_tokens=2048,
)
# result: {provider, model, text, response_time, usage, attempt}
```

## MCP Tools

Registered in `.mcp.json` as `llm-rotation` server.

| Tool | Description |
|------|------------|
| `llm_complete` | Send prompt with auto-rotation |
| `llm_complete_batch` | N промптов ПАРАЛЛЕЛЬНО через ту же ротацию. Результаты выровнены по индексу, провал одного промпта возвращается в своём слоте и НЕ обрывает батч (`{total, ok, failed, results[]}`). Параметры те же + `concurrency`. ⚠ claude-cli режется отдельным потолком — см. ниже |
| `llm_get_stats` | Provider statistics |
| `llm_reset_provider` | Reset provider to HEALTHY |
| `llm_test_providers` | Test all available providers |
| `llm_list_providers` | List configured providers |
| `llm_route_explain` | Порядок попыток, skip-причины (нет ключа/cooldown/model-несовместим), CB, эффективная модель |

## Known Issues

- `providers=[]` (empty list) must use `if providers is None` check, not `or` (empty list is falsy)
- Z.AI proxy requires `ZAI_API_KEY` env var
- GLM-5 thinking mode is **disabled** — it consumes output token budget, returning empty text for most tasks. Tested: 0/5 pass with thinking ON, 5/5 pass with thinking OFF
- Z.AI uses Anthropic format (x-api-key header, /v1/messages endpoint)
- `_make_request_anthropic()` handles Anthropic format natively (no proxy needed)
- Ollama providers don't need API keys but require running Ollama instance
- **FIXED**: `preferred_provider` bypassed `tried` list — all retries went to same provider instead of rotating. Fix: added `or preferred_provider in tried` check in `complete()`
