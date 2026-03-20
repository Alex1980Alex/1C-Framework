# Roadmap: LLM Rotation Service Improvements

**Date:** 2026-03-20 | **Status:** PLANNING

**Goal:** Улучшить LLM Rotation Service на основе GitHub best practices: circuit breaker, exponential backoff, health checks, multi-level failover, adaptive routing.

**Code:** `src/shared/llm_rotation/service.py`, `config.py`, `adapter.py`, `mcp.py`

---

## Текущая архитектура

```
prompt
  │
  ▼
Phase 1: Force-Primary (zai-glm5)
  ├── retry 1 → success? → return
  ├── retry 2 → success? → return
  └── fail → tried.append(primary)
  │
  ▼
Phase 2: Fallback Rotation
  ├── get_best_provider(exclude=tried) → zhipu
  │   └── fail → tried.append(zhipu)
  ├── get_best_provider(exclude=tried) → gemini
  │   └── fail → tried.append(gemini)
  └── ... → RuntimeError("All providers failed")
```

**Scoring:** `(health_status, consecutive_errors, priority, avg_response_time)`

**Провайдеры:** zai-glm5 (primary), zhipu, gemini, openrouter, mistral, ollama-local, ollama-cloud

---

## Gap Analysis

| Feature | Текущее | Best Practice | Gap |
|---------|---------|--------------|-----|
| Failure handling | Cooldown timer (фиксированный) | Circuit Breaker (Closed/Open/Half-Open) | Нет Half-Open test, нет graduated recovery |
| Retry delay | `delay * 2`, cap 10s | Exponential backoff + jitter | Нет jitter → thundering herd risk |
| Health monitoring | Manual `reset_provider()` | Periodic health probe + auto-recovery | Провайдеры не восстанавливаются автоматически |
| Failover levels | 2 уровня (primary → rest) | 3 уровня (instance → model → provider) | Нет retry альтернативной модели того же провайдера |
| Rate limiting | Cooldown после факта | Token bucket + retry-after headers | Нет proactive rate limiting |
| Routing strategy | Статичный priority | Adaptive (quality + cost + latency) | Не учитывает качество ответов |
| Cost tracking | Нет | Per-provider token * price | Нет бюджета и алертов |
| Provider comparison | Нет | A/B testing | Нет данных для сравнения |

**Ключевые GitHub-проекты:**

| Проект | Решаемая проблема | Итерация |
|--------|------------------|----------|
| [OmniRoute](https://github.com/diegosouzapw/OmniRoute) | Circuit Breaker per-model, anti-thundering herd | 1, 2 |
| [resilient-llm](https://github.com/gitcommitshow/resilient-llm) | Circuit breaker + adaptive retries + token bucket | 1, 2 |
| [pybreaker](https://github.com/danielfm/pybreaker) | Python CB: fail_max, success_threshold, reset_timeout | 1 |
| [python-circuit](https://github.com/edgeware/python-circuit) | CB с built-in jitter и back_off_cap | 2 |
| [pllm](https://github.com/andreimerfu/pllm) | 3-level failover (instance → model → provider) | 4 |
| [LLM-API-Key-Proxy](https://github.com/Mirrowel/LLM-API-Key-Proxy) | Balanced/sequential key rotation, auto failover | 3 |
| [llm-use](https://github.com/llm-use/llm-use) | Learned fallback: (task, provider) pairs + cosine similarity | 5 |
| [NadirClaw](https://github.com/doramirdor/NadirClaw) | 3-tier routing, cost tracking, budget alerts | 5 |
| [LiteLLM](https://github.com/BerriAI/litellm) | 100+ providers, retry-after, cooldowns, 8ms P95 | 2, 3 |
| [LLMRouter](https://github.com/ulab-uiuc/LLMRouter) | 16+ routing strategies, plugin system | 5 |

---

## Итерации

### Iteration 1: Circuit Breaker (паттерн OmniRoute / pybreaker)

**Цель:** Заменить примитивный cooldown на полноценный Circuit Breaker с 3 состояниями.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 1.1 `CircuitBreaker` class | Closed/Open/Half-Open, configurable thresholds | 2h |
| 1.2 Интеграция в `ProviderState` | Заменить `cooldown_until` на CB | 1h |
| 1.3 Half-Open test request | 1 probe request → success=Close, fail=reOpen | 1h |
| 1.4 Tests | Unit tests для state transitions | 1h |

**Архитектура (паттерн pybreaker):**
```python
class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject all
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    def __init__(
        self,
        fail_threshold: int = 3,
        success_threshold: int = 1,
        reset_timeout: float = 60.0,
    ):
        self.state = CircuitState.CLOSED
        self.fail_count = 0
        self.success_count = 0
        self.fail_threshold = fail_threshold
        self.success_threshold = success_threshold
        self.reset_timeout = reset_timeout
        self.opened_at: float | None = None

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.opened_at >= self.reset_timeout:
                self.state = CircuitState.HALF_OPEN
                return True
            return False
        # HALF_OPEN: allow one test request
        return True

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.fail_count = 0
                self.success_count = 0
        else:
            self.fail_count = 0

    def record_failure(self):
        self.fail_count += 1
        self.success_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.opened_at = time.monotonic()
        elif self.fail_count >= self.fail_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = time.monotonic()
```

**Изменения в `ProviderState`:**
```python
# Было:
cooldown_until: datetime | None = None

# Стало:
circuit_breaker: CircuitBreaker = field(
    default_factory=lambda: CircuitBreaker(fail_threshold=3, reset_timeout=60.0)
)

def is_available(self) -> bool:
    return self.circuit_breaker.can_execute()
```

**Acceptance:** CB переходит Open→Half-Open→Closed автоматически, без `reset_provider()`.

### Iteration 2: Exponential Backoff + Jitter (паттерн python-circuit)

**Цель:** Заменить фиксированный delay на exponential backoff с jitter и retry-after.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 2.1 `BackoffStrategy` class | Exponential + jitter + cap | 1h |
| 2.2 retry-after header parsing | Читать Retry-After из HTTP response | 1h |
| 2.3 Интеграция в `complete()` | Заменить `delay * 2` | 30 min |
| 2.4 Anti-thundering herd | Jitter предотвращает одновременный retry | included |

**Формула:**
```python
import random

class BackoffStrategy:
    def __init__(
        self,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        jitter: float = 1.0,
        multiplier: float = 2.0,
    ):
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter
        self.multiplier = multiplier

    def compute_delay(self, attempt: int, retry_after: float | None = None) -> float:
        if retry_after is not None:
            return retry_after + random.uniform(0, self.jitter)
        delay = min(
            self.base_delay * (self.multiplier ** attempt),
            self.max_delay,
        )
        return delay + random.uniform(0, self.jitter)
```

**retry-after parsing:**
```python
async with session.post(url, json=payload, headers=headers) as resp:
    if resp.status == 429:
        retry_after = resp.headers.get("Retry-After")
        delay = float(retry_after) if retry_after else None
        raise RateLimitError(f"429 Rate Limited", retry_after=delay)
```

**Acceptance:** Backoff delay растёт экспоненциально, jitter предотвращает thundering herd, retry-after учитывается.

### Iteration 3: Health Check + Auto-Recovery (паттерн OmniRoute)

**Цель:** Автоматическая проверка и восстановление провайдеров.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 3.1 Health probe (lightweight) | Минимальный запрос для проверки доступности | 2h |
| 3.2 Auto-recovery loop | Background asyncio task | 1h |
| 3.3 Config: probe interval, enabled | Settings в LLMRotationSettings | 30 min |
| 3.4 Логирование recovery events | JSONL health events | 30 min |

**Реализация:**
```python
async def _health_check_loop(self):
    """Background loop: probe unavailable providers."""
    while True:
        await asyncio.sleep(self._settings.health_check_interval)  # e.g. 120s

        for name, state in self._providers.items():
            if state.circuit_breaker.state != CircuitState.OPEN:
                continue
            if not state.circuit_breaker.can_execute():
                continue  # still in timeout

            # Half-Open: send lightweight probe
            try:
                await self._call_provider(
                    state, "ping", max_tokens=5,
                )
                state.circuit_breaker.record_success()
                logger.info(f"[{name}] Health check PASSED, recovered")
            except Exception:
                state.circuit_breaker.record_failure()
                logger.info(f"[{name}] Health check FAILED, staying open")
```

**Config addition:**
```python
health_check_enabled: bool = True
health_check_interval: int = 120  # seconds
```

**Acceptance:** OPEN провайдер автоматически восстанавливается после probe, без `reset_provider()`.

### Iteration 4: Multi-level Failover (паттерн pllm 3-level)

**Цель:** 3-уровневый failover вместо 2-фазного.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 4.1 Level 1: retry same instance | Transient error → retry with backoff | 1h |
| 4.2 Level 2: alternative model | Same provider, different model | 2h |
| 4.3 Level 3: fallback provider | Next provider by score | existing |
| 4.4 Config: retries per level | per_instance_retries, try_alt_model | 30 min |

**Обновлённый flow:**
```
prompt
  │
  ▼
Level 1: Retry Same Instance (transient errors: timeout, 500, 503)
  ├── attempt 1 → backoff(0) → retry
  ├── attempt 2 → backoff(1) → retry
  └── all failed
  │
  ▼
Level 2: Alternative Model (same provider)
  ├── zai-glm5 failed → try glm-4.6 on same Z.AI
  ├── gemini-2.0-flash failed → try gemini-1.5-flash
  └── no alt models or all failed
  │
  ▼
Level 3: Fallback Provider (different provider)
  ├── get_best_provider(exclude=tried)
  └── ... → RuntimeError if all exhausted
```

**Изменения:**
```python
# ProviderConfig.models уже есть — использовать как fallback models
# zai-glm5: ["glm-5", "glm-4.6", "glm-4.5-air"]
# gemini: ["gemini-2.0-flash", "gemini-1.5-flash"]

async def _try_provider_with_model_fallback(self, state, prompt, **kwargs):
    """Try default model, then alternative models of same provider."""
    models_to_try = [state.config.default_model] + [
        m for m in state.config.models if m != state.config.default_model
    ]
    for model in models_to_try:
        try:
            return await self._call_provider(state, prompt, model=model, **kwargs)
        except Exception as e:
            if not self._is_transient(e):
                raise
            logger.warning(f"[{state.config.name}/{model}] Failed, trying next model")
    raise RuntimeError(f"All models exhausted for {state.config.name}")
```

**Acceptance:** Transient error на glm-5 → auto-retry glm-4.6 → fallback to zhipu.

### Iteration 5: Adaptive Routing + Cost Tracking (паттерн llm-use / NadirClaw)

**Цель:** Learned routing с учётом quality + cost + latency.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 5.1 Response quality signal | Track: response length, parse success, user feedback | 2h |
| 5.2 Cost per provider | Token price table, per-request cost calculation | 1h |
| 5.3 Adaptive scorer | Composite score: 0.4*quality + 0.3*latency + 0.3*cost | 2h |
| 5.4 Budget alerts | Daily/monthly token budget, warning at 80% | 1h |
| 5.5 Provider comparison dashboard | CLI: accuracy, cost, latency per provider | 1h |

**Adaptive scoring:**
```python
class AdaptiveScorer:
    """Score providers based on historical performance."""

    def __init__(self):
        self.history: dict[str, list[dict]] = {}  # provider → outcomes

    def record(self, provider: str, latency: float, tokens: int, quality: float):
        self.history.setdefault(provider, []).append({
            "latency": latency,
            "tokens": tokens,
            "quality": quality,
            "cost": tokens * PRICE_PER_TOKEN.get(provider, 0.0),
        })

    def score(self, provider: str) -> float:
        records = self.history.get(provider, [])
        if len(records) < 5:
            return 0.5  # insufficient data

        recent = records[-20:]
        avg_quality = sum(r["quality"] for r in recent) / len(recent)
        avg_latency = sum(r["latency"] for r in recent) / len(recent)
        avg_cost = sum(r["cost"] for r in recent) / len(recent)

        # Normalize to 0-1 (lower latency/cost = higher score)
        latency_score = max(0, 1 - avg_latency / 30.0)
        cost_score = max(0, 1 - avg_cost / 0.01)

        return 0.4 * avg_quality + 0.3 * latency_score + 0.3 * cost_score
```

**Cost tracking:**
```python
PRICE_PER_1K_TOKENS = {
    "zai-glm5": 0.002,
    "zhipu": 0.001,
    "gemini": 0.0,       # free tier
    "openrouter": 0.0,   # free models
    "mistral": 0.001,
    "ollama-local": 0.0,
}
```

**Acceptance:** Provider selection учитывает quality + cost + latency, бюджет с алертами.

---

## Dependency Graph

```
Iter 1 (Circuit Breaker)
  │  + pybreaker / OmniRoute pattern
  ▼
Iter 2 (Exponential Backoff + Jitter)
  │  + python-circuit / resilient-llm
  ▼
Iter 3 (Health Check + Auto-Recovery)
  │  + OmniRoute health probe
  │  + depends on Iter 1 (CB states)
  ▼
Iter 4 (Multi-level Failover)
  │  + pllm 3-level pattern
  │  + depends on Iter 2 (backoff per level)
  ▼
Iter 5 (Adaptive Routing + Cost)
     + llm-use learned routing
     + NadirClaw cost tracking
     + depends on Iter 1-4 (all infrastructure)
```

---

## Метрики успеха

| Metric | Current | Iter 1 | Iter 3 | Iter 5 |
|--------|---------|--------|--------|--------|
| Auto-recovery | Manual only | CB Half-Open | Health probe | Auto + learned |
| Retry strategy | Fixed delay | Exp backoff + jitter | + retry-after | + adaptive |
| Failover levels | 2 | 2 + CB | 2 + CB + health | 3 (instance/model/provider) |
| Provider downtime | Until manual reset | ~60s (CB timeout) | ~120s (probe) | ~30s (adaptive) |
| Cost tracking | None | None | None | Per-request + budget |
| Routing intelligence | Static priority | Priority + CB | + health status | Adaptive (quality+cost+latency) |
| Thundering herd risk | High (no jitter) | Low (jitter) | Low | Low |

---

## Зависимости (pip)

| Package | Iteration | License | Purpose | Required |
|---------|-----------|---------|---------|----------|
| (none — pure Python) | 1-4 | — | CB, backoff, health — no external deps | — |
| `sentence-transformers` | 5 (optional) | Apache 2.0 | Learned routing (quality signal) | Optional |

Iterations 1-4 не требуют новых зависимостей — всё реализуется на чистом Python + asyncio.

---

## Ключевой принцип

**Каждый уровень защиты дополняет предыдущий:**

```
Circuit Breaker (fast fail) → Backoff (smart retry) → Health Check (auto-recover) → Multi-level (exhaustive) → Adaptive (intelligent)
```

Не "провайдер упал — ждём manual reset", а "CB изолировал → backoff с jitter → health probe восстановил → если persistent failure, alternative model → если всё плохо, adaptive scorer выбирает лучший fallback по реальным метрикам".
