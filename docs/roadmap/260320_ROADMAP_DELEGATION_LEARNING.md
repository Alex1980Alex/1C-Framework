# Roadmap: Delegation Learning System

**Date:** 2026-03-20 | **Status:** PLANNING | **Updated:** 2026-03-20 (GitHub best practices research)

**Goal:** Превратить делегирование из ad hoc решений в самообучающуюся систему с outcome tracking, feedback loop и итеративным улучшением.

**Skill:** [delegation-classifier](../../.claude/skills/delegation-classifier/SKILL.md)

---

## Текущее состояние (broken)

| Компонент | Статус | Проблема |
|-----------|--------|----------|
| `z-ai-write-guard.py` | Работает для кода | `.md` exempt, `docs/` exempt → docs проходят мимо |
| `z-ai-delegation-enforcer.py` | Работает частично | "дорожная карта" не матчится ни одним сигналом |
| Outcome tracking | **Отсутствует** | Нет данных: что делегировали, какой результат, сколько rewrite |
| Learning loop | **Отсутствует** | Правила статичны, не улучшаются от опыта |
| Pre-task analysis | **Отсутствует** | Нет структурированного "pause and classify" |

---

## GitHub Best Practices (исследование 2026-03-20)

| Проект | Решает проблему | Итерация |
|--------|----------------|----------|
| [TensorZero](https://github.com/tensorzero/tensorzero) | Structured outcomes + feedback loop + MIPRO auto-optimization + A/B testing | 2, 4 |
| [Tokenomics-AI](https://github.com/Tokenomics-AI/Tokenomics) | Bandit Optimizer (UCB), 90.7% cost reduction | 3 |
| [RouteLLM](https://github.com/lm-sys/RouteLLM) | Trained routers (sw_ranking, bert), 85% cost reduction | 4 |
| [contextualbandits](https://github.com/david-cortes/contextualbandits) | Python LinUCB/Thompson Sampling, partial_fit streaming | 3 |
| [SAFLA](https://github.com/ruvnet/SAFLA) | Self-Aware Feedback Loop, persistent memory, cross-session | 5 |
| [Agent Skill Bus](https://github.com/ShunsukeHayashi/agent-skill-bus) | Self-improving orchestration, quality degradation detection | 5 |
| [Router-R1](https://ulab-uiuc.github.io/Router-R1/) | RL routing, composite reward (format + outcome + cost) | 4, 5 |
| [Self-Evolving Agents](https://developers.openai.com/cookbook/examples/partners/self_evolving_agents/autonomous_agent_retraining) | GEPA evolutionary prompt optimization | 4 |
| [NVIDIA LLM Router](https://github.com/NVIDIA-AI-Blueprints/llm-router) | Intent-based (Qwen 1.75B) + auto-router (CLIP + NN) | 4 |
| [Anyscale LLM Router](https://github.com/anyscale/llm-router) | Training custom routers, 70% cost reduction | 4 |
| [Langfuse](https://github.com/langfuse/langfuse) | LLM observability + evals + feedback collection | 2 |
| [DeepEval](https://github.com/confident-ai/deepeval) | LLM evaluation framework (pytest-like) | 3 |

### Ключевой сдвиг: Rule-based → Online Learning

```
            ТЕКУЩИЙ                              УЛУЧШЕННЫЙ
    ┌─────────────────────┐              ┌────────────────────────┐
    │ keyword matching     │              │ contextual bandit      │
    │ (статичные сигналы)  │     →        │ (online learning)      │
    └──────────┬──────────┘              └───────────┬────────────┘
               │                                     │
    ┌──────────▼──────────┐              ┌───────────▼────────────┐
    │ batch analysis       │              │ каждый outcome =       │
    │ (скрипт, ручной)     │     →        │ reward signal (авто)   │
    └──────────┬──────────┘              └───────────┬────────────┘
               │                                     │
    ┌──────────▼──────────┐              ┌───────────▼────────────┐
    │ manual patch         │              │ UCB/Thompson auto-     │
    │ (keywords в хуке)    │     →        │ adjusts weights        │
    └─────────────────────┘              └────────────────────────┘
```

---

## Итерации улучшений

### Iteration 1: Foundation (immediate)

**Цель:** Начать записывать outcomes, починить очевидные дыры в хуках.

| Task | Deliverable | Status |
|------|-------------|--------|
| 1.1 Создать `data/delegation-outcomes.jsonl` | Файл + формат записи | DONE |
| 1.2 Fix `z-ai-write-guard.py`: `.md` > 50 lines в `docs/` не exempt | Патч хука | DONE |
| 1.3 Fix `z-ai-delegation-enforcer.py`: добавить сигналы | Патч хука | DONE |
| 1.4 Создать skill `delegation-classifier` | SKILL.md с матрицей + outcome format | DONE |
| 1.5 Зарегистрировать в `skill-router-config.json` | Bundle entry | DONE |
| 1.6 Первая запись outcome | JSONL entry | DONE |

### Iteration 2: Outcome Tracking Hook (1 day)

**Цель:** Автоматическая запись outcomes при каждом Write > 15 строк.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 2.1 Hook `delegation-outcome-tracker.py` (PreToolUse:Write) | Записывает estimated fields в JSONL | 2h |
| 2.2 Интеграция с SessionState | Track: delegated=true если был llm_complete | 1h |
| 2.3 Stop hook addition: summary append | При Stop — дописать actual_lines, rewrite_pct | 1h |
| 2.4 Structured outcome format (паттерн TensorZero) | Формат с reward signal для bandit | 30 min |

**Логика:**
```
PreToolUse:Write fires → content > 15 lines?
  YES → record outcome
  NO → skip
```

**Outcome format (расширенный, паттерн TensorZero):**
```jsonl
{
  "timestamp": "2026-03-20T21:30:00Z",
  "task_id": "delegation-roadmap",
  "content_type": "docs",
  "domain": "roadmap",
  "estimated_lines": 150,
  "actual_lines": 155,
  "delegated": false,
  "classification": "Never",
  "correct_classification": "Medium",
  "rewrite_pct": 0,
  "reward": 0.0,
  "context_features": {
    "has_code": false,
    "has_architecture": true,
    "file_extension": ".md",
    "target_dir": "docs/roadmap"
  }
}
```

- `context_features` — контекст для contextual bandit (Iter 3)
- `reward` — 1.0 если classification верная и rewrite < 25%, 0.0 иначе
- `correct_classification` — заполняется при Stop hook review

**Проблема:** PostToolUse не работает (bug #6305). Используем PreToolUse + Stop hook.

**Acceptance:** Каждый крупный Write создаёт запись в JSONL с context_features и reward.

### Iteration 3: Online Learning — ПЕРЕРАБОТАНА

**Было:** batch analysis скриптом + ручные recommendations.
**Стало:** Contextual Bandit (online learning) на библиотеке `contextualbandits`.

**Цель:** Bandit автоматически корректирует routing из каждого outcome.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 3.1 Contextual Bandit module | `src/shared/delegation_bandit.py` (LinUCB, 4 arms) | 3h |
| 3.2 Integration с outcome tracker | Каждый outcome → `bandit.update(context, action, reward)` | 1h |
| 3.3 Bandit-based classification | `bandit.predict(context)` → Soft/Medium/Hard/Never | 1h |
| 3.4 CLI dashboard | accuracy, delegation rate, bandit confidence | 1h |
| 3.5 Fallback to rules | outcomes < 20 → rule-based | 30 min |

**Архитектура (паттерн Tokenomics-AI UCB):**
```python
from contextualbandits.online import LinUCB

class DelegationBandit:
    ACTIONS = ["Soft", "Medium", "Hard", "Never"]

    def __init__(self, state_path="data/delegation-bandit.pkl"):
        self.model = LinUCB(nchoices=4, batch_train=True)
        self.state_path = state_path
        self._load_state()

    def predict(self, context: dict) -> str:
        features = self._extract_features(context)
        action_idx = self.model.predict(features.reshape(1, -1))[0]
        return self.ACTIONS[action_idx]

    def update(self, context: dict, action: str, reward: float):
        features = self._extract_features(context)
        action_idx = self.ACTIONS.index(action)
        self.model.partial_fit(
            features.reshape(1, -1),
            np.array([action_idx]),
            np.array([reward])
        )
        self._save_state()

    def _extract_features(self, ctx: dict) -> np.ndarray:
        return np.array([
            {"docs": 0, "code": 1, "test": 2, "template": 3}.get(
                ctx.get("content_type"), 4),
            ctx.get("line_count", 0) / 100,
            1 if ctx.get("has_code") else 0,
            1 if ctx.get("has_architecture") else 0,
            {"roadmap": 0, "skill": 1, "hook": 2, "src": 3}.get(
                ctx.get("domain"), 4),
        ])
```

**Warm-up стратегия:**

| Outcomes | Режим | Логика |
|----------|-------|--------|
| < 20 | Rule-based | Текущие `_MEDIUM_SIGNALS` |
| 20-50 | Hybrid | Bandit + rules голосуют, majority wins |
| > 50 | Pure bandit | Rules как fallback при low confidence |

**Dashboard:**
```
=== Delegation Learning Dashboard ===
Bandit mode: WARM-UP (37/50 to full autonomy)
Accuracy: 72% -> 78% (+6%)
Delegation rate: 45% -> 52%
Avg rewrite: 18% -> 14%

=== Confidence by Context ===
docs/roadmap  -> Medium (0.87, N=12)
code/src      -> Hard   (0.92, N=18)
templates     -> Soft   (0.76, N=5)
hooks         -> Never  (0.95, N=8)
```

**Acceptance:** Bandit предсказывает classification, accuracy > 70% после 30 outcomes.

### Iteration 4: Trained Router — ПЕРЕРАБОТАНА

**Было:** Авто-патч keywords в enforcer.
**Стало:** Trained classifier (RouteLLM pattern) заменяет keyword matching.

**Цель:** Обученный классификатор вместо regex-based enforcement.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 4.1 Similarity router (паттерн RouteLLM sw_ranking) | Embedding similarity вместо keyword match | 3h |
| 4.2 GEPA evolutionary optimization | Эволюция prompt/rules enforcer | 3h |
| 4.3 Eval script: before/after | Тест с eval prompts | 3h |
| 4.4 A/B testing (паттерн TensorZero) | Rule-based vs bandit vs router | 2h |

**4.1 Similarity Router:**
```python
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

model = SentenceTransformer("intfloat/multilingual-e5-small")

EXEMPLARS = {
    "Soft": ["переведи документ", "отформатируй таблицу"],
    "Medium": ["создай дорожную карту", "напиши документацию"],
    "Hard": ["напиши модуль обработки", "реализуй API endpoint"],
    "Never": ["отладь баг в хуке", "архитектурное решение"],
}

def classify_by_similarity(prompt: str) -> str:
    prompt_emb = model.encode([f"query: {prompt}"])
    best_level, best_score = None, -1
    for level, examples in EXEMPLARS.items():
        embs = model.encode([f"passage: {e}" for e in examples])
        score = cosine_similarity(prompt_emb, embs).max()
        if score > best_score:
            best_level, best_score = level, score
    return best_level
```

**4.2 GEPA Evolutionary Optimization (паттерн Self-Evolving Agents):**
```
Цикл (max 5 поколений):
1. Sample 10 outcomes с reward < 0.5
2. LLM reflects: "почему классификация была неверной?"
3. LLM proposes revision: "добавить сигнал X / изменить порог"
4. Apply revision → run eval → keep if improved, revert otherwise
```

**4.4 A/B Testing (паттерн TensorZero):**
```python
import random

def classify_ab(prompt: str, context: dict) -> tuple[str, str]:
    method = random.choices(
        ["rules", "bandit", "router"],
        weights=[0.2, 0.4, 0.4]
    )[0]
    if method == "rules":
        return rule_based_classify(prompt), "rules"
    elif method == "bandit":
        return bandit.predict(context), "bandit"
    else:
        return classify_by_similarity(prompt), "router"
```

**Acceptance:** Router accuracy > 80%, A/B тест показывает improvement vs rule-based.

### Iteration 5: AutoResearch + Self-Improving Loop — РАСШИРЕНА

**Цель:** Полная self-improving система с persistent learning и auto-detection.

| Task | Deliverable | Effort |
|------|-------------|--------|
| 5.1 Recipe `delegation` в autoresearch.ps1 | Verify = delegation dashboard | 2h |
| 5.2 Template `delegation-quality.md` | Instructions для Executor | 1h |
| 5.3 Ralph template `delegation` | ralph.bat --template delegation | 1h |
| 5.4 SAFLA persistent learning | Cross-session bandit state | 2h |
| 5.5 Quality degradation detection (паттерн Agent Skill Bus) | Alert при падении accuracy | 1h |
| 5.6 Composite reward (паттерн Router-R1) | 0.6 * accuracy + 0.4 * cost_reward | 2h |

**5.5 Quality Degradation Detection:**
```python
from collections import Counter

def check_delegation_health():
    """Запускать после каждых 20 новых outcomes."""
    recent = load_outcomes(last_n=20)
    accuracy = sum(1 for o in recent if o["reward"] > 0.5) / len(recent)

    if accuracy < 0.6:
        alert(f"Delegation accuracy {accuracy:.0%}! Review recent outcomes.")

    old_dist = Counter(o["classification"] for o in load_outcomes(offset=20, n=20))
    new_dist = Counter(o["classification"] for o in recent)
    if chi_squared_divergence(old_dist, new_dist) > 0.3:
        alert("Classification distribution shifted - retrain bandit.")
```

**5.6 Composite Reward:**
```python
def compute_reward(outcome: dict) -> float:
    accuracy_reward = 1.0 if (
        outcome["classification"] == outcome["correct_classification"]
    ) else 0.0

    if outcome["delegated"] and outcome["rewrite_pct"] < 25:
        cost_reward = 1.0
    elif not outcome["delegated"] and outcome["correct_classification"] == "Never":
        cost_reward = 1.0
    else:
        cost_reward = 0.0

    return 0.6 * accuracy_reward + 0.4 * cost_reward
```

**Acceptance:** `autoresearch.ps1 -Domain delegation` запускает цикл, accuracy > 85%.

---

## Dependency Graph

```
Iter 1 (Foundation) --- DONE
         |
         v
Iter 2 (Outcome Hook)
         |  + TensorZero structured format
         v
Iter 3 (Contextual Bandit)
         |  + contextualbandits lib
         |  + Tokenomics-AI UCB pattern
         v
Iter 4 (Trained Router)
         |  + RouteLLM sw_ranking
         |  + Self-Evolving Agents GEPA
         |  + TensorZero A/B testing
         v
Iter 5 (AutoResearch + Self-Improving)
            + SAFLA persistent learning
            + Agent Skill Bus quality monitoring
            + Router-R1 composite reward
```

---

## Метрики успеха

| Metric | Current | Iter 1 | Iter 3 | Iter 5 |
|--------|---------|--------|--------|--------|
| Classification accuracy | ~50% | ~60% | ~78% (bandit) | ~88% (router) |
| Delegation rate (>15 lines) | ~30% | ~45% | ~58% (bandit) | ~70% (optimized) |
| Outcome tracking | 0% | 100% (manual) | 100% (auto+reward) | 100% (composite) |
| Token savings | ~20% | ~35% | ~55% (UCB) | ~70% (Router-R1) |
| Under-delegation rate | ~40% | ~25% | ~12% (bandit) | ~5% (classifier) |
| Learning mode | none | none | bandit (online) | bandit+router+GEPA |
| Concept drift detection | none | none | none | auto-alert |

---

## Зависимости (pip)

| Package | Iteration | License | Purpose |
|---------|-----------|---------|---------|
| `contextualbandits` | 3 | MIT | LinUCB, Thompson Sampling |
| `sentence-transformers` | 4 | Apache 2.0 | Similarity router (уже в проекте) |
| `deepeval` | 3 (optional) | Apache 2.0 | Evaluation framework |

---

## Ключевой принцип

**Каждая ошибка делегирования = один outcome = один reward signal для bandit = автоматическое улучшение.**

Не "outcomes записаны и анализируются скриптом" (batch, ручной), а "bandit обновляет weights после каждого outcome в реальном времени" (online, автоматический). Система учится не потому что мы запускаем скрипт анализа, а потому что **UCB/Thompson Sampling корректирует routing при каждом новом наблюдении**.
