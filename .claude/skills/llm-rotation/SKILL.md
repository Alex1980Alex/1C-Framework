---
name: llm-rotation
description: "LLM Rotation Service — мульти-провайдерное LLM API с автофоллбэком. ИСПОЛЬЗУЙ когда делегируешь генерацию Z.AI, проверяешь статус провайдеров, сбрасываешь failed provider. Триггеры: 'llm_complete', 'llm rotation', 'Z.AI', 'провайдер LLM', 'fallback LLM', 'llm_reset_provider', 'llm_test_providers', 'делегировать генерацию'. НЕ для прямых вызовов Anthropic API (→ claude-api)."
---

# LLM Rotation Service

## When to Use
- Multi-provider LLM completion with automatic fallback
- Provider health monitoring and rotation
- Z.AI proxy (OpenAI -> Anthropic format translation)
- MCP tools: `llm_complete`, `llm_get_stats`, `llm_reset_provider`, `llm_test_providers`, `llm_list_providers`

## Architecture

```
LLMRotationService
  ├── ProviderConfig (6 providers, priority-ordered)
  ├── ProviderState (health tracking per provider)
  ├── complete() → auto-fallback on error
  └── _make_request_openai() / _make_request_ollama()

ZAIProxy (HTTP server, port 8000)
  ├── openai_to_anthropic() — request conversion
  ├── anthropic_to_openai() — response conversion
  └── SSE streaming support
```

## Providers (priority order)

| # | Provider | Model | Format | Key Required |
|---|----------|-------|--------|-------------|
| 0 | **zai-glm5** | **glm-5** | **anthropic** | Yes (ZAI_API_KEY) |
| 1 | zhipu | glm-4-flash | openai | Yes |
| 2 | gemini | gemini-2.0-flash | openai | Yes |
| 3 | openrouter | llama-3.3-70b:free | openai | Yes |
| 4 | mistral | mistral-small-latest | openai | Yes |
| 5 | ollama-local | qwen2.5:7b | ollama | No |
| 6 | ollama-cloud | qwen2.5:7b | ollama | No |

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

## Configuration

```env
LLM_ROTATION_PRIMARY_PROVIDER=zai-glm5
LLM_ROTATION_MAX_RETRIES=3
LLM_ROTATION_TIMEOUT=30
LLM_ROTATION_COOLDOWN_SECONDS=300
LLM_ROTATION_RATE_LIMIT_COOLDOWN=60
```

API keys via standard env vars: `ZHIPU_API_KEY`, `GEMINI_API_KEY`, `OPENROUTER_API_KEY`, `MISTRAL_API_KEY`.

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
| section_summary | 2 | 300 | `processing/section_summary.py` |
| context_generator | 2 | 200 | `processing/context_generator.py` |
| entity_extractor | 2 | 4096 | `processing/extractors/entity_extractor.py` |
| community_summarizer | 2 | 1024 | `graph_store/summarizer.py` |

Category 1 enabled by default. Category 2 opt-in via `LLM_ROTATION_COMPONENTS` env.

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
| `src/shared/llm_rotation/mcp.py` | MCP server (5 tools) |
| `tests/integration/test_llm_rotation.py` | 33 integration tests |

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
| `llm_get_stats` | Provider statistics |
| `llm_reset_provider` | Reset provider to HEALTHY |
| `llm_test_providers` | Test all available providers |
| `llm_list_providers` | List configured providers |

## Known Issues

- `providers=[]` (empty list) must use `if providers is None` check, not `or` (empty list is falsy)
- Z.AI proxy requires `ZAI_API_KEY` env var
- GLM-5 thinking mode is **disabled** — it consumes output token budget, returning empty text for most tasks. Tested: 0/5 pass with thinking ON, 5/5 pass with thinking OFF
- Z.AI uses Anthropic format (x-api-key header, /v1/messages endpoint)
- `_make_request_anthropic()` handles Anthropic format natively (no proxy needed)
- Ollama providers don't need API keys but require running Ollama instance
