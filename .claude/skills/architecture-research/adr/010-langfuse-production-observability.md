# ADR-010: Langfuse for Production LLM Observability

> **Status:** proposed (locked-in после первого 30-day production traffic + cost baseline measurement)
> **Date:** 2026-05-09
> **Roadmap:** [260509_ROADMAP_CONSOLIDATED_BACKLOG.md §5c](../../../../docs/roadmap/260509_ROADMAP_CONSOLIDATED_BACKLOG.md)

## Context

§3.1 closed Phase A (handler infrastructure ready, settings refactor done, smoke tests pass). §5c describes Phase B — full production rollout. Эта ADR формализует strategic decisions для Phase B чтобы не пере-обсуждать в каждой следующей сессии.

Без observability фреймворк "летит вслепую" в production:
- Регрессии prompt change замечаются через дни/недели по user complaints
- Cost spikes невидимы до monthly billing
- Quality degradation после model upgrade требует ручного digging в logs
- §4.5 trained router blocked — нет outcome corpus для learning

Альтернативы рассматривались:
- **LangSmith** (LangChain native) — tight LangChain integration, но vendor lock-in + LangChain-only tracing (не покрывает direct anthropic SDK calls)
- **OpenLLMetry** (Traceloop) — OpenTelemetry-based, vendor-agnostic, но more setup overhead
- **Phoenix** (Arize) — open-source, но слабее prompt versioning
- **Helicone** — strong cost tracking, но weaker on quality scores
- **Self-hosted custom** — full control, maintenance overhead высок

## Decision

**Langfuse** (Cloud free tier для dev, self-host опция для production sensitivity) как primary observability platform.

### Tools choice rationale

| Criterion | Langfuse score | Why |
|---|---|---|
| LangChain integration | ✅ Native callback handler | `langfuse.langchain.CallbackHandler` plug-and-play |
| Vendor neutrality | ✅ Provider-agnostic | Tracks Anthropic / OpenAI / любой LLM через unified API |
| Free tier | ✅ 50K observations/month | Достаточно для hobby + small production |
| Self-host option | ✅ Open-source Docker | Опция при cost concerns или privacy regulations |
| Cost tracking | ✅ Per-trace token + cost | Identifies expensive queries для optimization |
| Quality scores | ✅ Numeric scores API | Wire-up с feedback loop §3.5 |
| Prompt versioning | ✅ Built-in | A/B prompt testing без code changes |

### Retention policy

- **Traces:** 30 days в Cloud free tier (Langfuse default), 90 days в self-host (configurable).
- **Aggregated metrics:** indefinite (rollups для historical trends).
- **PII redaction:** автоматический regex-based на input/output strings перед отправкой (имена, email, phone, credit cards).

### Sampling strategy

| Traffic level | Sampling rate | Rationale |
|---|---|---|
| Dev / staging | 100% | Полная visibility для debugging |
| Production < 1000 RPS | 100% | Cost negligible на free tier (≤30K observations/day) |
| Production > 1000 RPS | Adaptive (100% errors + 10% successful) | Stay within cost limits, prioritise problematic traces |

### Cost limits

- **Hard cap:** $50/month default (через Langfuse billing alerts).
- **Soft alert:** $20/month → review top expensive queries.
- **При exceeding:** включить sampling 10% или migrate на self-host.

### Integration points

Three layers:

1. **LangChain callback handler** (already wired в §3.1)
   - File: [`callbacks/langfuse/langfuse_callback.py`](../../../../src/pdf_framework/callbacks/langfuse/langfuse_callback.py)
   - Covers: `on_llm_start`, `on_llm_end`, `on_llm_error`
   - Activates через `with_middleware(llm, enable_langfuse=True)` в [middleware.py](../../../../src/pdf_framework/agents/rag/middleware.py)

2. **Manual spans для non-LLM operations** (5c.5 pending)
   - Targets: `agents/rag/agent.py:invoke`, `search/manager.py:search`, `tools/*`
   - Pattern: `langfuse.start_span(name="retrieval")` → measure latency / metadata
   - Wire-up через `observability/langfuse_setup.build_langfuse_callback()` (existing helper)

3. **Memory hooks** (5c.4 pending — closes deferred §3.3.4)
   - Targets: `memory-first-hook`, `memory-sync`, `session-memory-save`
   - Pattern: hook spans correlate с LLM trace через session_id + run_id
   - Cross-hook trace via `db.get_run_trace(run_id)` (already exists, see §3.3 closure)

### Self-hosted vs Cloud trade-off

**Cloud (default):** Free tier sufficient. Zero setup overhead. Trade: data leaves jurisdiction.

**Self-hosted (опционально):** Docker compose deployment. Trade: maintenance overhead (~2-4ч/quarter). Use when:
- Strict data sovereignty (1С Enterprise customers, EU GDPR).
- Cost > $50/mo (предсказуемее self-host capacity).
- Need >30 day retention.

### Privacy & compliance

- **PII redaction:** обязательно перед отправкой. Implement через regex patterns + Pydantic validators в callback handler.
- **Sensitive endpoints:** `/auth/*`, `/tenants/*` исключить из traces (через middleware-level skip list).
- **GDPR right to erasure:** Langfuse поддерживает trace deletion API. Wire-up при user delete request.
- **Multi-tenant isolation:** Langfuse projects per tenant ИЛИ tag traces `tenant_id` для filtering.

## Consequences

### Положительные

- End-to-end visibility: token usage, latency, cost per query.
- Proactive quality regression detection (prompt drift, model upgrade impact).
- Foundation для §4.5 trained router (outcome corpus accumulates с traffic).
- Score collection via UI buttons → feedback loop §3.5 closes circle.
- Cost optimization data-driven (top-10 expensive queries).

### Отрицательные

- External SaaS dep (mitigated через self-host option).
- Latency overhead ~10-50ms per LLM call (Langfuse async batching minimizes).
- PII redaction complexity (false negatives → privacy leaks; false positives → useless redacted traces).
- Free tier 50K/month limit может быть exceeded при growth → требует upgrade decision.

### Riski mitigation

- **Langfuse outage:** `fail_ci_if_error: false` + `LangfuseCallbackHandler.enabled=False` graceful degradation. Framework работает без observability.
- **Cost overrun:** soft alert $20 + hard cap $50 + adaptive sampling.
- **PII leaks:** regex-based redaction + integration tests с known-PII fixtures.
- **Vendor lock-in:** if Langfuse pivots / shuts down, callback handler легко перенесён на OpenLLMetry (~4 ч migration).

## Альтернативы (rejected)

- **LangSmith:** vendor lock-in (LangChain-only), не покрывает direct SDK calls в `bsl/` subsystem. Free tier меньше (5K traces/month).
- **OpenLLMetry:** более flexible (OTel-based), но dual instrumentation (Langfuse + OTel) → maintenance overhead. Future migration option.
- **Phoenix:** weaker prompt versioning, less mature ecosystem.
- **Self-hosted custom (Prometheus + Grafana):** полная control, но 4-6 weeks initial setup для feature parity. Не оправдано для текущего scale.

## Implementation status (Phase B subtasks)

| ID | Status | Notes |
|---|---|---|
| 5c.1 Langfuse Cloud account | OPEN — user-side | Free tier signup на cloud.langfuse.com |
| 5c.2 .env credentials | OPEN — user-side | После 5c.1 |
| 5c.3 Smoke test | OPEN | После 5c.2 — verify trace появляется в dashboard |
| 5c.4 Wire memory hooks | OPEN — closes §3.3.4 | После 5c.3 |
| 5c.5 Manual spans | OPEN | После 5c.4 |
| 5c.6 Dashboard alerts | OPEN | После 5c.3, ongoing tuning |
| 5c.7 Cost baseline | OPEN — needs 7d traffic | После 5c.5 |
| 5c.8 Score collection | OPEN — closes feedback loop | После 5c.7 |
| 5c.9 Outcome corpus | OPEN — needs 30d traffic | Unblocks §4.5 |
| 5c.10 ADR-010 | ✅ THIS DOC | Locked-in після baseline data |

## Related

- ADR-008 Qwen3 retrieval — sibling production decision
- ADR-009 DeepEval thresholds — quality gate complement (5c.4 unblocks DeepEval full activation)
- §3.1 Langfuse Phase A closure (handler refactor)
- §3.3 Memory P5 observability (cross-hook trace API)
- §4.5 Delegation Iter 4-5 (consumer of outcome corpus from 5c.9)
- 09.4 Мониторинг — operational documentation
