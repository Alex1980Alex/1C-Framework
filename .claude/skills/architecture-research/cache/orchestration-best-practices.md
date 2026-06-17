# Оркестрация LLM-агентов и stateful-workflow — фреймворки, паттерны, практики

**Дата:** 2026-06-18
**Статус:** актуально
**Теги:** [orchestration, agent-workflow, langgraph, durable-execution, saga, hitl, otel-genai, multi-agent, state-machine, circuit-breaker, event-sourcing]

> Объективные факты (frameworks / patterns / practices + URL). Проекция на конкретный фреймворк и решения — в ADR, не здесь (ADR-002).

## Фреймворки оркестрации (GitHub, звёзды live 2026-06-18, ±округление)

| Framework | Repo | ★ | Модель оркестрации | Дифференциатор |
|---|---|---|---|---|
| LangGraph | langchain-ai/langgraph | ~35k | Graph / state-machine (nodes+edges над shared typed state) | low-level граф-рантайм, checkpointer-персист, циклы/branch/HITL pause-resume |
| CrewAI | crewAIInc/crewAI | ~54k | Supervisor/hierarchical role-crews + event-driven Flows | Crews (Sequential/Hierarchical Process) + Flows (`@start/@listen/@router` FSM) |
| OpenAI Agents SDK | openai/openai-agents-python | ~27k | Decentralized peer handoff (choreography) | агенты передают управление через `handoffs` (как LLM-tool) + guardrails + tracing; преемник Swarm |
| Microsoft AutoGen | microsoft/autogen | ~59k | Event-driven actor model (v0.4 `autogen-core`) | async message-passing между актор-агентами; maintenance-mode → Agent Framework |
| Google ADK | google/adk-python | ~20k | Hierarchical agents + deterministic workflow-agents | `sub_agents` дерево + `Sequential/Parallel/LoopAgent` примитивы |
| MS Semantic Kernel | microsoft/semantic-kernel | ~28k | Hybrid: plugin-planner + Process Framework (event) + Agent Framework | несколько субстратов в одном SDK; A2A/MCP interop |
| Mastra (TS) | mastra-ai/mastra | ~25k | Graph durable workflow + agents | TS-граф (`.then/.branch/.parallel`) + durable suspend/resume |
| Temporal | temporalio/temporal | ~21k | Durable execution / workflow-as-code (event-history replay) | весь agent-loop crash-proof/resumable; интегрирует OpenAI Agents SDK / ADK |
| Pydantic-AI | pydantic/pydantic-ai | ~18k | Typed agent loop + optional graph (`pydantic_graph`) | валидируемый run-loop + type-hint FSM |
| Hatchet | hatchet-dev/hatchet | ~7k | Postgres task-queue + DAG + durable execution | Postgres = durability + observability |
| Marvin 3.x | PrefectHQ/marvin | ~6k | Task-graph agentic workflow (поглотил ControlFlow) | Task/Agent/Thread на Pydantic-AI |
| Atomic Agents | BrainBlend-AI/atomic-agents | ~6k | Pipeline / schema-chained components | контроль в Python (не LLM): `output_schema`→`input_schema` typed I/O |
| Inngest | inngest/inngest | ~5.5k | Event-driven durable step-functions | events → durable steps; AgentKit для multi-agent TS |
| AG2 | ag2ai/ag2 | ~4.7k | Conversational multi-agent (GroupChat) | форк legacy AutoGen v0.2 GroupChat |
| Restate | restatedev/restate | ~4k | Durable execution + durable promises/timers | Rust runtime/log; suspend на долгих async tool-call, exactly-once |
| Burr | DAGWorks-Inc/burr | ~2.4k | State machine (actions + transitions над central state) | control flow = граф переходов; built-in trace/persist |
| DBOS | dbos-inc/dbos-transact-py | ~1.4k | Durable execution как in-process библиотека (Postgres checkpoints) | durability = декоратор + Postgres, без брокера/control-plane |
| Dapr Agents | dapr/dapr-agents | ~0.7k | Durable-execution workflow на actor model | агенты = virtual stateful actors на Dapr Workflow API |
| OpenAI Swarm (superseded) | openai/swarm | ~22k | Lightweight handoffs/routines (choreography) | educational; заменён Agents SDK |

**Линии:** AutoGen→ MS Agent Framework (`microsoft/agent-framework`, GA 2026-04-07, Python+.NET); Swarm→ Agents SDK; ControlFlow archived 2026-03→ Marvin 3.x. LlamaIndex Workflows = event-driven typed-event step-model (`run-llama/workflows-py`).

## Паттерны оркестрации (control-flow: D=deterministic, M=model-driven, H=hybrid)

1. **Prompt chaining / Sequential** [D] — фикс. цепочка шагов, выход→вход. Anthropic; Azure "Sequential".
2. **Routing / classifier-dispatch** [D|M] — классификация → специализированный путь (one-shot на входе). Anthropic.
3. **Parallelization (sectioning + voting)** [D] — параллельные подзадачи / N-прогонов на consensus; нужна агрегация. Anthropic; Azure "Concurrent".
4. **Orchestrator-workers (supervisor/hierarchical)** [M] — оркестратор динамически декомпозирует+делегирует+синтезирует (подзадачи НЕ предопределены). Anthropic; LangGraph.
5. **Evaluator-optimizer / maker-checker** [M] — generate→critique→refine loop с iteration cap. Anthropic; Azure.
6. **Reflection / self-critique** [M] — single-actor self-review перед финалом (дешевле, риск rubber-stamp). Anthropic; LangChain.
7. **Plan-and-execute / ReWOO** [H] — planner делает план заранее, executors (дешевле) исполняют, re-plan при дивергенции; ReWOO decouple Planner/Worker/Solver. LangChain; arXiv 2305.18323.
8. **ReAct** [M] — Thought→Action→Observation tight loop, каждый шаг от наблюдения; iteration cap. arXiv 2210.03629.
9. **Handoff / delegation** [M] — динамическая передача полного управления специалисту (один активен); риск loop. Azure; OpenAI Agents SDK.
10. **Human-in-the-loop (interrupt-and-resume)** [D-barrier] — пауза на checkpoint, персист state, resume; scoped на sensitive tool-calls. Azure; LangGraph `interrupt`.
11. **Saga / compensation** [D-scaffold] — каждый шаг + compensating action; при падении — компенсации в обратном порядке (откат side-effects без локов). AWS agentic-AI; Step Functions/Temporal/DBOS.
12. **Blackboard / group-chat** [M] — специалисты пишут/читают shared workspace; manager выбирает следующего; cap ~3, обычно read-only. Azure "Group chat"; классич. blackboard.
13. **Orchestration vs Choreography** — централизованный контроллер vs event-driven peer-реакция (A2A); trade auditability↔loose-coupling. Azure event-driven.
14. **FSM / Graph** [D-skeleton] — workflow = граф состояний+переходов, conditional edges на runtime-данных; субстрат для остальных паттернов. LangGraph low-level; AWS Step Functions.
15. **Map-reduce / fan-out-fan-in** [D] — fan-out N параллельных (разные входы) → reduce/aggregate (отлично от voting=same input). LangGraph `Send`.
16. **Reflexion / memory-augmented** [M] — verbal self-reflection в episodic memory buffer между trials, обучение языком без fine-tune. arXiv 2303.11366.
17. **Magentic / dynamic task-ledger** [M] — manager строит и непрерывно правит task-ledger (goals+progress), backtrack/re-plan; auditable план для open-ended. Azure.

## Прод-практики (cross-cutting)

1. **Durable execution + checkpointing** — crash-safe resumable; append-only event-history + deterministic replay; side-effects в journaled steps. Temporal/DBOS/LangGraph checkpointer.
2. **Idempotency / exactly-once** — idempotency-keys на mutating-calls + journaling результатов + deterministic IDs (`content_hash→id`). Temporal/DBOS.
3. **Human approval gates** — пауза до необратимого (write main / delete / spend); approve/edit/reject/respond; durable pause. LangGraph `interrupt()`+`Command(resume)`.
4. **Observability / OTel GenAI semconv** — `gen_ai.*` spans (inference/tool/agent), `gen_ai.system/operation.name/request.model`+token-usage, W3C `traceparent` `00-{32hex}-{16hex}-{flags}`; LangSmith/Langfuse cost-per-call. OpenTelemetry GenAI semconv.
5. **Evaluation gates in-the-loop** — LLM-as-judge/rubric grader score→reject/regenerate/escalate; tiered (cheap validators→LLM-judge); adversarial judge-audit. Anthropic evaluator-optimizer; LLM-as-Judge survey.
6. **Retries+backoff + circuit breaker** — exp backoff+jitter на retryable(429/5xx/timeout), fail-fast на non-retryable(auth/validation); breaker Closed→Open→Half-Open trip на failure-rate. LangGraph RetryPolicy/TimeoutPolicy; Portkey; tenacity.
7. **Deterministic control flow over model** — workflows (predefined code-paths) для well-defined; agents (LLM directs) только для open-ended; граф/код владеет sequencing, LLM — per-node judgment. Anthropic workflows-vs-agents; ESAA.
8. **Guardrails / structured-output** — constrained decoding (Outlines/Guidance/JSONFormer) или native structured-output (Pydantic→JSON-schema `response_format`) + output-guardrails post-gen. Guardrails AI; Pydantic.
9. **Cost / token budgeting** — token-count per call → cost → aggregate full-workflow; budget caps (halt/escalate); tiered model routing. LangSmith/Langfuse cost-tracking.
10. **Versioned prompts/configs** — prompts как versioned objects (commits+tags), decoupled от кода; eval-suites pinned к версии. LangSmith/Braintrust/Langfuse; git.
11. **Dead-letter / compensation on failure** — DLQ для exhausted/non-retryable + Saga compensation в обратном порядке; LangGraph `error_handler` node атомарно после retries. LangGraph; Portkey.
12. **Event-sourcing / audit log** — immutable append-only log = source of truth, deterministic projection state, replay-verification via hashing; audit-log(forensics) ≠ event-log(state). ESAA arXiv; AWS Bedrock AgentCore; Temporal event-history.

## Ключевые источники
- Anthropic *Building Effective Agents*: https://www.anthropic.com/engineering/building-effective-agents
- Azure *AI Agent Orchestration Patterns* (2026-05): https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/ai-agent-design-patterns
- AWS *Prompt-chaining + Saga* (agentic): https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/prompt-chaining-saga-patterns.html
- LangGraph *Fault Tolerance*: https://www.langchain.com/blog/fault-tolerance-in-langgraph · low-level: https://langchain-ai.github.io/langgraph/concepts/low_level/
- OpenTelemetry *GenAI semconv*: https://opentelemetry.io/docs/specs/semconv/gen-ai/ · agent observability: https://opentelemetry.io/blog/2025/ai-agent-observability/
- arXiv: ReAct 2210.03629 · ReWOO 2305.18323 · Reflexion 2303.11366 · ESAA 2602.23193
- Temporal durable execution: https://docs.temporal.io/evaluate/understanding-temporal
