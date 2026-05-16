---
topic: llm-rotation-production-improvements-2026
domain: architecture-research
created: 2026-05-16
last_verified: 2026-05-16
version: anthropic-sdk / claude-agent-sdk / litellm / 2026
sources:
  - https://pypi.org/project/claude-agent-sdk/
  - https://platform.claude.com/docs/en/agent-sdk/python
  - https://platform.claude.com/docs/en/api/sdks/python
  - https://docs.litellm.ai/docs/routing
  - https://docs.litellm.ai/docs/proxy/reliability
  - https://github.com/TribeAI/claude-evals
  - https://github.com/milistu/anthropic-parallel-calling
  - https://www.sitepoint.com/claude-api-429-error-handling-python/
  - https://localaimaster.com/blog/ai-gateway-litellm
keywords: [llm-rotation, claude-agent-sdk, anthropic-python, litellm, asyncio.gather, rate-limit, batch-eval, parallel-batch, fallback-chain, hot-path, subscription-quota, anthropic-api]
---

# LLM Rotation production improvements — 2026 roadmap

## Контекст

Текущая реализация `LLMRotationService` (2026-05-16, roadmap 260509 §2.2): 3-tier rotation (claude-cli-haiku → claude-cli-sonnet → ollama-local) + escape hatch (anthropic-sonnet silent если API key unset). Smoke verified: subscription path работает для batch (15s/call), hot-path unusable из-за subprocess overhead.

**Unrealized problems** (документировано в `tech-research/cache/claude-code-subprocess-wrappers.md`):
- `--max-turns N` не работает: Claude Code CLI в `-p` mode фундаментально агентичен, любой prompt триггерит tool-use turns
- `--output-format json` parsing ломается при error_max_turns (нет `result` field)
- `--bare` mode не подходит (требует ANTHROPIC_API_KEY, не OAuth subscription)
- Hot-path latency 25-150s per Self-RAG query — interactive UX broken
- Subscription rate limit (Anthropic не публикует exact RPM) — risk of throttling unknown

## Идентификация

**Что**: architectural roadmap для решения 4 unrealized problems из subprocess approach.

**Когда использовать**: при planning Sprint 1-3 для production unlock LLM rotation.

**Альтернативы (рассмотрены)**:
- (A) Continue raw subprocess + iterate flags → DEAD END (CLI agentic by design)
- (B) Switch to `claude-agent-sdk` Python package → RECOMMENDED Phase 1
- (C) Switch to direct Anthropic HTTP SDK → RECOMMENDED Phase 2 for hot-path
- (D) Switch to LiteLLM unified gateway → DEFER as Phase 4 (big refactor)

## Решения по проблемам

### Problem 1 + 2: `--max-turns` + `--output-format json` ломаются

**Best practice (research-confirmed)**: `claude-agent-sdk` Python package управляет agent loop + subprocess внутри, exposes typed messages.

```python
from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage

async def call(prompt: str, system: str) -> str:
    opts = ClaudeAgentOptions(
        system_prompt=system,
        max_turns=1,                         # Real single-shot via SDK
        permission_mode="bypassPermissions",
        model="claude-haiku-4-5",
    )
    parts = []
    async for msg in query(prompt=prompt, options=opts):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if hasattr(block, "text"):
                    parts.append(block.text)
        elif isinstance(msg, ResultMessage):
            return "".join(parts) or msg.content
    return "".join(parts)
```

**Источник**: [Claude Agent SDK Python](https://pypi.org/project/claude-agent-sdk/) — official Anthropic package.

**Pitfalls** ([GitHub anthropics/claude-agent-sdk-python#472](https://github.com/anthropics/claude-agent-sdk-python/issues/472)):
- API errors returned as text messages, не raised — нужна check + raise pattern
- Avoid `break` inside `async for` (asyncio cleanup issues per `securevibes` guide)

**Trade-off**: SDK actively developed, possible API breakage. Pin `>=0.5,<1.0`.

### Problem 3: `--bare` mode требует API key

**Best practice**: Don't fight it — accept that `--bare` is for ANTHROPIC_API_KEY path. Use OAuth subscription for non-bare (default), use API key for bare. **Two paths, not one**.

```python
if os.environ.get("ANTHROPIC_API_KEY"):
    # Use --bare for fast startup (or skip subprocess entirely → Anthropic SDK)
    args.insert(1, "--bare")
```

### Problem 4: Hot-path latency 25-150s/query

**Best practice**: Direct Anthropic SDK для hot-path components (grader, hallucination_check, classifier).

```python
import anthropic
client = anthropic.AsyncAnthropic(
    max_retries=3,  # built-in: 408/409/429/5xx exponential backoff
    timeout=60.0,
)
resp = await client.messages.create(
    model="claude-haiku-4-5-20251001",
    max_tokens=100,
    messages=[{"role": "user", "content": prompt}],
)
# 0.5-2s per call
```

**Built-in retry/backoff** (per [Anthropic Python SDK docs](https://platform.claude.com/docs/en/api/sdks/python)):
- Retries 2x default на 408 / 409 / 429 / 5xx
- Exponential backoff with jitter
- Parses `retry-after` header automatically

**Rate limit dimensions** (Anthropic enforces 3 simultaneously):
- request-rate (RPM)
- token-rate (TPM)
- concurrent requests

**Response headers для observability**:
- `anthropic-ratelimit-requests-remaining`
- `anthropic-ratelimit-tokens-remaining`
- `retry-after` (seconds)

**529 Overload** ≠ rate limit — capacity signal, safe to retry без consuming TPM quota.

**Уже реализовано в нашем `anthropic-sonnet` priority-3 provider** — need only set `ANTHROPIC_API_KEY` и switch primary.

### Problem 5: Concurrent batch processing

**Best practice** ([milistu/anthropic-parallel-calling](https://github.com/milistu/anthropic-parallel-calling)):

```python
import asyncio
sem = asyncio.Semaphore(CONCURRENCY)

async def call_with_limit(prompt: str) -> str:
    async with sem:
        try:
            return await call_anthropic(prompt)
        except anthropic.RateLimitError as e:
            retry_after = int(e.response.headers.get("retry-after", 60))
            await asyncio.sleep(retry_after)
            return await call_anthropic(prompt)

results = await asyncio.gather(*(call_with_limit(p) for p in prompts))
```

**Recommended concurrency**: start с 3, ramp до 10 based on RPM headers. Watch:
- 429 — too high concurrency for current TPM quota
- 529 — server overload, retry без backing off concurrency

### Problem 6: Unified gateway alternative

**Best practice** (LiteLLM industry pattern):

```yaml
# litellm-config.yaml
model_list:
  - model_name: tier-1-fast
    litellm_params:
      model: anthropic/claude-haiku-4-5-20251001
      api_key: os.environ/ANTHROPIC_API_KEY
      rpm: 50
  - model_name: tier-3-local
    litellm_params:
      model: ollama/qwen2.5-coder:7b
      api_base: http://localhost:11434

router_settings:
  routing_strategy: simple-shuffle
  fallbacks:
    - tier-1-fast: [tier-3-local]
  context_window_fallbacks:
    - tier-1-fast: [tier-2-quality]

litellm_settings:
  cache: true
  cache_params: { type: redis, host: localhost, port: 6379 }
```

```python
from litellm import Router
router = Router(model_list=[...], fallbacks=[...])
resp = await router.acompletion(model="tier-1-fast", messages=[...])
```

**Pros**: battle-tested (multi-million prod), built-in cache + cost tracking + dashboard, declarative YAML.

**Cons**: ~600 LoC custom `LLMRotationService` deprecated → migration cost. Additional dep + maintenance.

**Decision criterion**: LiteLLM only worth it if multi-tenant production or 5+ providers active.

## Архитектурная картина после реализации

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                         │
│  Self-RAG / Adaptive / HyDE / context_generator / grounding │
└──────────────────────┬───────────────────────────────────────┘
                       │ cheap_llm_call(component=...)
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  LLM ROTATION SERVICE                        │
│                  (adapter.py:cheap_llm_call)                 │
│                                                              │
│   Route by component category + ANTHROPIC_API_KEY presence: │
│                                                              │
│   ┌─ Hot-path (Cat 1, query-time):                          │
│   │   if ANTHROPIC_API_KEY:                                  │
│   │     → anthropic-sonnet direct HTTP (0.5-2s) ✓            │
│   │   else:                                                  │
│   │     → claude-cli-haiku via SDK (5-15s) ⚠ slow            │
│   │                                                          │
│   ├─ Batch (Cat 2, indexing):                               │
│   │   → claude-cli-haiku via claude-agent-sdk               │
│   │       + asyncio.gather concurrency=5                    │
│   │       + max_turns=1 (works via SDK)                     │
│   │                                                          │
│   └─ Eval (scripts/*):                                       │
│       → benchmark_llm.py — isolated, subprocess + Ollama    │
└──────────────────────────────────────────────────────────────┘
```

## Roadmap phases

| Phase | Что | Effort | Unblocks |
|---|---|---|---|
| **1** | Migrate to `claude-agent-sdk` Python package | 2-3h | Real `max_turns=1`, typed messages, restore `--output-format json` |
| **2** | Set ANTHROPIC_API_KEY + switch primary | 30 min | Production interactive hot-path (0.5-2s/call) |
| **3** | `batch_complete()` + asyncio.gather concurrency | 1h | 4-6× faster indexing (200 chunks: 33min → 5min) |
| **4** | LiteLLM gateway migration | 4-6h | Industry-standard, deprecate ~600 LoC custom code |
| **5** | Eval framework (TribeAI pattern) | 3h | Quality regression detection + provider comparison |

## Sprint plan

**Sprint 1 (Production unblock, 1 day)**:
- Phase 2 (30 min config) — immediate hot-path fix
- Phase 1 (3h SDK migration) — fixes max-turns, structured output
- Smoke test + commit

**Sprint 2 (Throughput, 1 day)**:
- Phase 3 (1h concurrency) — 4-6× batch speedup
- Phase 5 (3h eval framework) — regression baselines

**Sprint 3 (Architecture, optional 1-2 days)**:
- Phase 4 (4-6h LiteLLM) — only if multi-tenant production OR want industry standard

**Total**: 4-5h for 80% value (Phase 1-3). Full 5-phase = 2-3 sprints.

## Cost projection

| Workload | Сейчас (subscription only) | После Phase 2+3 (paid hot-path) |
|---|---|---|
| Production query (10× grader) | 88s, $0 | **2-3s, $0.01-0.03** |
| Indexing 200-chunk PDF | 33 мин, $0 | **5 мин (concurrent), $0.40** |
| Batch eval 73 items | 12 мин, $0 | **2 мин, $0.30** |
| Daily dev (~100 queries) | not feasible | $1-3/day |
| Monthly production (10K queries) | not feasible | $100-300/month |

ROI положителен для любого production use case с >$300/month budget.

## Источники

- **[Docs]** [Claude Agent SDK Python (pypi)](https://pypi.org/project/claude-agent-sdk/) — official package
- **[Docs]** [Agent SDK Python reference](https://platform.claude.com/docs/en/agent-sdk/python) — `query()`, `ClaudeSDKClient`, options
- **[Docs]** [Anthropic Python SDK](https://platform.claude.com/docs/en/api/sdks/python) — `messages.create`, max_retries, exp backoff
- **[Docs]** [LiteLLM Router](https://docs.litellm.ai/docs/routing) — fallback chains, load balancing
- **[Docs]** [LiteLLM Fallbacks](https://docs.litellm.ai/docs/proxy/reliability) — context_window_fallbacks, content policy
- **[GitHub]** [TribeAI/claude-evals](https://github.com/TribeAI/claude-evals) — production eval framework 50-case golden
- **[GitHub]** [milistu/anthropic-parallel-calling](https://github.com/milistu/anthropic-parallel-calling) — semaphore + rate-limit guard
- **[GitHub]** [anshumanbh/securevibes Agent SDK guide](https://github.com/anshumanbh/securevibes/blob/main/docs/references/claude-agent-sdk-guide.md) — production patterns
- **[GitHub]** [anthropics/claude-agent-sdk-python#472](https://github.com/anthropics/claude-agent-sdk-python/issues/472) — error handling pitfall
- **[Guide]** [Claude API 429 Handling 2026 (SitePoint)](https://www.sitepoint.com/claude-api-429-error-handling-python/) — production retry patterns
- **[Guide]** [LocalAIMaster LiteLLM 2026](https://localaimaster.com/blog/ai-gateway-litellm) — gateway production patterns

## Связано

- [[claude-code-subprocess-wrappers]] — tech-research cache, current implementation gaps
- [[delegation-aggressive]] — feedback memory, delegation protocol
- Skill `llm-rotation` — provider config + dispatch
- Skill `tech-research` — tech research methodology

## Наш опыт

**2026-05-16 implementation**:
- `LLMRotationService` rewritten для 3+1 providers (commit `99c021ea2`)
- `benchmark_llm.py` isolated wrapper для eval (commit `078579cff`)
- Best-practice flags tested + rolled back per `--max-turns` empirical conflict (commit `606d9f06f`)

**Discovered constraints**:
- Claude Code CLI -p mode = inherently agentic, не batchable через flags
- Subscription OAuth incompatible с `--bare`
- Subscription rate limit unknown until hit (start conservative concurrency=3)
- `_request_timeout` returns `aiohttp.ClientTimeout`, not int — gotcha for subprocess `asyncio.wait_for`
- Adaptive scorer stale data biased routing toward ollama until wiped — replication risk on fresh deploys
