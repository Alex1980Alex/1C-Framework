# 260516 — LLM Rotation production improvements

> **Origin:** follow-up к roadmap [260509 §2.2 closure](260509_ROADMAP_CONSOLIDATED_BACKLOG.md) — устранение unrealized problems из subprocess approach.
>
> **Research cache:** [`architecture-research/cache/llm-rotation-production-improvements-2026.md`](../../.claude/skills/architecture-research/cache/llm-rotation-production-improvements-2026.md) — full analysis, code patterns, 11 sources.
>
> **Status as of 2026-05-17 (post §3 + §4.1 closures):**
> - ✅ Phase 1 closed (commit `8742cb090`) — claude-agent-sdk migration
> - ✅ Phase 3 closed (commit `7dd1fbea8`) — concurrent batch + adaptive concurrency
> - ⏸️ **Phase 2 / 4 / 5 DEFERRED** — requires `ANTHROPIC_API_KEY` ($20-100/month budget)
> - **Master deferral plan:** [`260517_ROADMAP_API_KEY_DEFERRED.md`](260517_ROADMAP_API_KEY_DEFERRED.md) — consolidates все paid-API tasks с decision tree

## §0 — Контекст

Сегодня `LLMRotationService` (commit `99c021ea2`) использует 3-tier setup:
- `claude-cli-haiku` (priority 0, subscription, batch-only — 5-15s/call)
- `claude-cli-sonnet` (priority 1, subscription)
- `ollama-local` (priority 2, free fallback)
- `anthropic-sonnet` (priority 3, silent skip без `ANTHROPIC_API_KEY`)

**Unrealized после empirical testing (commit `606d9f06f`):**

| Проблема | Симптом | Root cause |
|---|---|---|
| `--max-turns N` не работает | `error_max_turns` даже на "Reply: pong" | Claude Code CLI в `-p` mode фундаментально агентичен |
| `--output-format json` ломает parsing | `is_error=true`, нет `result` field | Зависит от max-turns |
| `--bare` mode требует API key | `Not logged in · Please run /login` | Намеренный design — skip OAuth keychain |
| Hot-path latency 25-150s/query | Self-RAG grader × 10 calls subprocess | Subprocess startup overhead |
| Subscription rate limit unknown | Possible throttling без warning | Anthropic не публикует exact RPM |

---

## §1 — Phase 1: Migrate to `claude-agent-sdk` Python package (Foundation)

**Цель:** Заменить raw subprocess на official Anthropic Python SDK который properly manages agent loop + exposes typed messages.

**Выгоды:**
- Real `max_turns=1` работает через SDK options (vs broken через CLI flag)
- Typed messages (`AssistantMessage`, `ResultMessage`, `SystemMessage`) — лучшее parsing чем raw text
- Error taxonomy (`CLINotFoundError`, `CLIConnectionError`, `ClaudeSDKError`) — точная диагностика
- Subprocess management internal — не наша забота, fewer bugs

**Реализация:**
- [ ] **1.1** Add dependency: `claude-agent-sdk>=0.5,<1.0` в `pyproject.toml` под `[project.optional-dependencies] llm-rotation`
- [ ] **1.2** Refactor `src/shared/llm_rotation/service.py::_make_request_claude_cli` — replace `asyncio.create_subprocess_exec` block (~90 LoC) на SDK calls:
  ```python
  from claude_agent_sdk import query, ClaudeAgentOptions, AssistantMessage, ResultMessage
  options = ClaudeAgentOptions(
      system_prompt=system_prompt,
      max_turns=1,
      permission_mode="bypassPermissions",
      model=f"claude-{target_model}-4-5",
  )
  async for msg in query(prompt=prompt, options=options):
      if isinstance(msg, ResultMessage): ...
  ```
- [ ] **1.3** Refactor `src/shared/benchmark_llm.py::_call_claude_cli` — same SDK migration
- [ ] **1.4** Restore `--max-turns 1` semantically via `ClaudeAgentOptions(max_turns=1)` (CLI flag was rolled back; SDK option actually works)
- [ ] **1.5** Restore typed parsing — `isinstance(msg, ResultMessage)` вместо raw JSON parsing
- [ ] **1.6** Tests: 34 integration + 2 new для SDK path (`tests/integration/test_llm_rotation.py::TestClaudeCLIProvider`)
- [ ] **1.7** Handle [SDK pitfall #472](https://github.com/anthropics/claude-agent-sdk-python/issues/472): API errors come as text messages, not raised — добавить check + raise pattern

**Effort:** 2-3h actual coding + 30 min testing.
**Зависимости:** None — config-additive change. Falls back если SDK install не удался (try/except ImportError).
**Risk:** SDK actively developed; pin `>=0.5,<1.0`. Subscription billing transition 2026-06-15 может изменить cost.

---

## §2 — Phase 2: Direct Anthropic SDK для hot-path (Production unlock) ⭐ HIGHEST ROI

**Цель:** Активировать hot-path через direct Anthropic HTTP API. Self-RAG grader / hallucination check / classifier перестают быть subprocess-bound.

**Выгоды:**
- Hot-path latency: 88s → **2-3s per user query** (30× speedup)
- Built-in retry/backoff (Anthropic SDK 2x retries on 408/409/429/5xx, exponential + jitter)
- Production interactive UX становится приемлемой
- Cost predictable: ~$0.01-0.03/query Haiku, ~$0.10-0.30/query Sonnet

**Реализация (config-only, no code changes — provider уже существует):**
- [ ] **2.1** Set environment variable:
  ```bash
  echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env
  ```
- [ ] **2.2** Switch primary provider в `.env`:
  ```bash
  sed -i 's/LLM_ROTATION_PRIMARY_PROVIDER=.*/LLM_ROTATION_PRIMARY_PROVIDER=anthropic-sonnet/' .env
  ```
- [ ] **2.3** Verify: `pytest tests/integration/test_llm_rotation.py` — `anthropic-sonnet` activates (previously silently skipped)
- [ ] **2.4** Smoke: live `cheap_llm_call` через grader-style prompt → measure latency (expect 0.5-2s)
- [ ] **2.5** Cost monitor: Anthropic dashboard alerts at $50/month threshold (configurable)
- [ ] **2.6** Documentation: [`09.4.1_Langfuse.md`](../framework%20documentation/09_АДМИНИСТРИРОВАНИЕ/09.4.1_Langfuse.md) update — cost tracking активен через existing Langfuse spans

**Effort:** **30 minutes** (config-only).
**Зависимости:** None — provider config-ready since 2026-05-16.
**Risk:** Real $$ cost. Production 10K queries/month ≈ $100-300. Mitigate через per-tenant budget tracking (§3.1 Langfuse already wired).

---

## §3 — Phase 3: Concurrent batch processing (Throughput)

**Цель:** Параллелизовать batch eval / indexing через `asyncio.gather` + semaphore.

**Выгоды:**
- Indexing 200-chunk PDF: 33 минуты → **5 минут** (concurrency=5)
- Batch grounding (73 items): 12 минут → **2 минуты**
- Conservative concurrency respect rate limits — start с 3, ramp до 10

**Реализация:**
- [ ] **3.1** Add `batch_complete()` method в `LLMRotationService`:
  ```python
  async def batch_complete(self, prompts: list[str], concurrency: int = 5, **kwargs) -> list[dict]:
      sem = asyncio.Semaphore(concurrency)
      async def _one(p):
          async with sem:
              try:
                  return await self.complete(prompt=p, **kwargs)
              except RateLimitError as e:
                  retry_after = self._parse_retry_after(e)
                  await asyncio.sleep(retry_after)
                  return await self.complete(prompt=p, **kwargs)
              except Exception as e:
                  return {"error": str(e), "prompt": p[:80]}
      return await asyncio.gather(*(_one(p) for p in prompts))
  ```
- [ ] **3.2** Wire в `scripts/ground_golden_v1.py` — replace sequential loop:
  ```python
  results = await service.batch_complete(prompts, concurrency=5, component="grounding_judge")
  ```
- [ ] **3.3** Parse Anthropic `retry-after` header + `anthropic-ratelimit-requests-remaining`:
  ```python
  if resp.headers.get('anthropic-ratelimit-requests-remaining', '99') == '0':
      await asyncio.sleep(int(resp.headers.get('retry-after', 60)))
  ```
- [ ] **3.4** Tune concurrency dynamically через `RateLimiter` class (`src/shared/llm_rotation/rate_limiter.py` уже есть)
- [ ] **3.5** Smoke benchmark: 40 grounding items — measure wall-clock sequential vs concurrent=5

**Effort:** **~1 hour**.
**Зависимости:** Phase 2 (Anthropic SDK with native rate-limit headers).
**Risk:** Subscription rate limit (Anthropic не публикует RPM). Start conservative concurrency=3.

---

## §4 — Phase 4: LiteLLM unified gateway (Architecture, OPTIONAL)

**Цель:** Заменить ~600 LoC custom `LLMRotationService` на industry-standard LiteLLM proxy.

**Выгоды:**
- Battle-tested (100+ providers, multi-million prod deployments)
- YAML config — декларативно
- Built-in semantic cache, cost tracking, alerts, dashboard
- Multi-provider switching без переписывания adapter

**Trade-off:** Adds external dep + maintenance. Только если multi-tenant production или 5+ providers active.

**Реализация (если решено делать):**
- [ ] **4.1** Add deps: `litellm[proxy]>=1.40` в `pyproject.toml`
- [ ] **4.2** Create `config/litellm.yaml`:
  ```yaml
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
  litellm_settings:
    cache: true
    cache_params: { type: redis, host: localhost, port: 6379 }
  ```
- [ ] **4.3** Refactor `adapter.py::cheap_llm_call` — use `litellm.Router` вместо `LLMRotationService`
- [ ] **4.4** Keep `LLMRotationService` as compat layer — deprecation period для 10 callsites
- [ ] **4.5** Deprecate custom retry/circuit-breaker/adaptive code (LiteLLM имеет встроенное)
- [ ] **4.6** Optional: Run LiteLLM proxy as separate process для UI dashboard (`http://localhost:4000`)
- [ ] **4.7** Migrate tests — 34 → cover LiteLLM router patterns

**Effort:** **4-6 hours** (large refactor требует thorough testing).
**Зависимости:** Phase 2 (для производственного ANTHROPIC_API_KEY).
**Decision criterion:** Defer unless multi-tenant production OR want industry standard.

---

## §5 — Phase 5: Eval framework integration (Quality gate)

**Цель:** Regression testing на provider quality — adaptive scorer оценивает output correctness, не только latency.

**Выгоды:**
- Detection quality regression early (provider downgrade automated через CI cron)
- Comparison between providers — informed routing decision
- Baseline `data/eval/provider_baselines/` — historical tracking

**Реализация:**
- [ ] **5.1** `scripts/eval_providers.py` — runner per provider в rotation:
  ```python
  async def eval_provider(provider_name: str, dataset: list[dict]) -> dict:
      correct = 0
      for item in dataset:
          res = await service.complete(prompt=item["query"], preferred_provider=provider_name)
          if check_answer(res["text"], item["expected_answer"]):
              correct += 1
      return {"provider": provider_name, "accuracy": correct/len(dataset), ...}
  ```
- [ ] **5.2** Output schema: `data/eval/provider_baselines/<provider>_<YYYY-MM-DD>.json`
- [ ] **5.3** CI integration: weekly cron eval; alert если accuracy drops > 5pp vs baseline
- [ ] **5.4** Hot-swap pickup: adaptive scorer reads accuracy metric из baseline (не только latency)
- [ ] **5.5** Memory: save `reference_provider_quality_baseline.md` с конкретными numbers
- [ ] **5.6** Inspiration: [GitHub TribeAI/claude-evals](https://github.com/TribeAI/claude-evals) — 50-case golden, one-command comparison

**Effort:** **3 hours**.
**Зависимости:** Phase 2 (eval нуждается в working hot-path) + golden_v1 v2.1 ✅ (73 items grounded, готов).
**Output**: `data/eval/provider_baselines/` populated with comparison data.

---

## §6 — Sprint planning

### Sprint 1 (1 day, immediate production unlock)

| Task | Effort | Deliverable |
|---|---|---|
| §2 — Phase 2 ANTHROPIC_API_KEY + switch primary | 30 min | Hot-path 0.5-2s/call |
| §1 — Phase 1 claude-agent-sdk migration | 2-3h | max_turns=1 works, typed messages |
| Smoke + commit | 30 min | Verified production ready |

**Total Sprint 1**: ~4h. **80% value gain** (interactive UX usable).

### Sprint 2 (1 day, throughput + quality)

| Task | Effort | Deliverable |
|---|---|---|
| §3 — Phase 3 batch_complete() | 1h | 4-6× indexing speedup |
| §5 — Phase 5 eval framework | 3h | Provider quality baselines |

**Total Sprint 2**: ~4h.

### Sprint 3 (optional, 1-2 days, architecture refactor)

| Task | Effort | Deliverable |
|---|---|---|
| §4 — Phase 4 LiteLLM migration | 4-6h | Industry-standard gateway |
| Deprecate `LLMRotationService` custom code | 2h | -600 LoC complexity |
| Update docs + skill | 1h | `llm-rotation` skill rewrite |

**Total Sprint 3**: ~8h. **Only if multi-tenant production needed**.

---

## §7 — Cost projection после implementation

| Workload | Сейчас (subscription only) | После Phase 2 + 3 (paid hot-path) |
|---|---|---|
| Production query (Self-RAG grader × 10) | 88s, $0 | **2-3s**, $0.01-0.03/query |
| Indexing 200-chunk PDF | 33 минуты, $0 | 4-5 минут (concurrent), $0.40 |
| Batch eval 73 golden items | 12 минут, $0 | **2 минуты**, $0.30 |
| Daily dev queries (~100) | not feasible | ~$1-3/day |
| Monthly production (10k queries) | not feasible | ~$100-300/month |

**ROI положителен для любого production use case с >$300/month budget.**

---

## §8 — Sources (research summary)

- [Claude Agent SDK Python (PyPI)](https://pypi.org/project/claude-agent-sdk/) — official package, recommended path
- [Agent SDK Python reference](https://platform.claude.com/docs/en/agent-sdk/python) — `query()`, `ClaudeSDKClient`, options
- [Anthropic Python SDK](https://platform.claude.com/docs/en/api/sdks/python) — `messages.create`, max_retries, exp backoff
- [LiteLLM Router](https://docs.litellm.ai/docs/routing) — fallback chains, load balancing
- [LiteLLM Fallbacks](https://docs.litellm.ai/docs/proxy/reliability) — context_window_fallbacks, content policy
- [GitHub TribeAI/claude-evals](https://github.com/TribeAI/claude-evals) — production eval framework 50-case golden
- [GitHub milistu/anthropic-parallel-calling](https://github.com/milistu/anthropic-parallel-calling) — semaphore + rate-limit guard
- [GitHub anshumanbh/securevibes Agent SDK guide](https://github.com/anshumanbh/securevibes/blob/main/docs/references/claude-agent-sdk-guide.md) — production patterns
- [GitHub anthropics/claude-agent-sdk-python#472](https://github.com/anthropics/claude-agent-sdk-python/issues/472) — error handling pitfall
- [Claude API 429 Handling 2026 (SitePoint)](https://www.sitepoint.com/claude-api-429-error-handling-python/) — production retry patterns
- [LocalAIMaster LiteLLM 2026](https://localaimaster.com/blog/ai-gateway-litellm) — gateway production patterns

---

## §9 — Связано

- **Roadmap 260509 §2.2** — closure of dead-provider cleanup that produced this follow-up
- **Tech research cache** [`claude-code-subprocess-wrappers.md`](../../.claude/skills/tech-research/cache/claude-code-subprocess-wrappers.md) — current implementation gaps, anti-patterns
- **Architecture research cache** [`llm-rotation-production-improvements-2026.md`](../../.claude/skills/architecture-research/cache/llm-rotation-production-improvements-2026.md) — full code patterns + sources
- **Memory** [`feedback_delegation_aggressive.md`](file:///C:/Users/Tech.%20Boutique/.claude/projects/C--1--Framework/memory/feedback_delegation_aggressive.md) — delegation protocol behavior
- **Skill** [`llm-rotation`](../../.claude/skills/llm-rotation/SKILL.md) — provider config + dispatch reference
