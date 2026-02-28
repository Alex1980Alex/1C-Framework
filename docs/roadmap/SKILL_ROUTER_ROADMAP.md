# Дорожная карта: Intelligent Skill Router v2

**Дата создания:** 2026-02-12
**Дата обновления:** 2026-02-28
**Статус:** Фазы 0-1, 7-13 DONE. Эволюция: Keyword → Hybrid → Semantic
**Проекты:** PDF Framework + 1C-Enterprise (shared pattern)

---

## Текущее состояние (аудит 2026-02-28)

### Архитектура

```
UserPromptSubmit
  │
  ├── skill-router.py (Layer A: keyword match + Layer B: fuzzy/lemma)
  │     ↓ stdout: "[SKILL-ROUTER] Bundles: X, Y" + "ОБЯЗАТЕЛЬНО: Skill('X')"
  │     ↓ 100% injection rate (stdout approach)
  │
  └── skill-eval-enforcer-shell.py (stdout: "MANDATORY SKILL EVALUATION")
        ↓ plain text → 100% injection rate

PreToolUse / PostToolUse
  └── code-skill-enforcer.py (Level A-F: pattern→skill blocking)
```

### Метрики (eval-skill-router.py, 64 ground truth samples)

| Метрика | v4 (46 bundles) | v5 (25 bundles) | Δ |
|---------|----------------|----------------|---|
| **Bundle F1** | 0.68 | **0.89** | +31% |
| **Required Skill Precision** | 0.79 | **0.88** | +12% |
| **Required Skill F1** | 0.83 | **0.81** | -2% |
| **All Skill Recall** | 1.00 | **1.00** | — |
| **Action Intent Accuracy** | 98% | **100%** | +2% |
| **Informational Intent** | — | **100%** | — |
| Кол-во бандлов | 46 | **25** | -46% |
| Кол-во keywords | ~649 | ~649 | — |
| Ground truth samples | 64 | 64 | — |
| FP count | — | 38 | tracked |
| FN count | — | 0 | — |

### Домены (Level 1 hierarchical routing)

| Домен | Бандлы |
|-------|--------|
| 1c | research-1c |
| framework | search, indexing, eval-benchmark, graph, agents, data-stores, deploy, framework-use, framework-ops |
| claude-code | claude-code-dev, claude-code-config, claude-code-ops, hooks, creation, docs |
| langchain | langchain-core, langchain-infra |
| research | research-tech, architecture, workflow |
| tools | git-parsing, tenacity-retry, code-verify, learning-loop |

### Прогресс

**Решённые проблемы:**
1. ~~systemMessage игнорируется~~ → **FIXED** (Фаза 11): stdout approach = 100% injection
2. ~~Нет принуждения~~ → **FIXED** (Фаза 11): конкретные `Skill('X')` + императивная инструкция
3. ~~Слишком много бандлов (42)~~ → **FIXED** (Фаза 13): 46→25 бандлов, F1 bundle 0.68→0.89
4. ~~Нет ground truth~~ → **FIXED** (Фаза 12): 64 samples, eval script, CI gate

**Оставшиеся проблемы:**
4. **Нет semantic understanding** — keyword matching не ловит парафразы → Фаза 14
5. **Нет feedback loop** — recommend/activate логи есть, но нет автоматической коррекции → Фаза 15
6. **FP noise** — 38 false positives (optional/affinity skills) → нужна calibration → Фаза 14-15

---

## Исследование: подходы к роутингу (web + GitHub, 2025-2026)

### Сравнительная таблица подходов

| Подход | Accuracy (GQR-Bench) | Latency | Стоимость | Ловит парафразы | Нужны данные |
|--------|----------------------|---------|-----------|-----------------|--------------|
| Naive keyword/substring | ~40-60% | <1ms | $0 | Нет | Нет |
| **TF-IDF + WideMLP** | **~88%** | <4ms | $0 | Частично | Да (labeled) |
| Embedding similarity (MiniLM) | ~58% | <1ms | $0 | Да | Нет (примеры) |
| **Embedding + SVM/RF** | **~83%** | <5ms | $0 | Да | Да (labeled) |
| Embedding + centroid (curated) | ~80-90% | <1ms | $0 | Да | Нет (примеры) |
| LLM function calling | ~91% | 62-669ms | $0.01+ | Да | Нет |

*Источник: GQR-Bench (arXiv 2505.14524), RouteLLM (ICLR 2025)*

### Ключевые GitHub-проекты

| Проект | Stars | Суть | URL |
|--------|-------|------|-----|
| **semantic-router** (aurelio-labs) | ~3,200 | Embedding-based route matching | [GitHub](https://github.com/aurelio-labs/semantic-router) |
| **RouteLLM** (lm-sys) | ~4,500 | Model routing via preference data | [GitHub](https://github.com/lm-sys/RouteLLM) |
| **LLMRouter** (UIUC) | ~1,000 | 16+ routing algorithms unified | [GitHub](https://github.com/ulab-uiuc/LLMRouter) |
| awesome-ai-model-routing | 158 | Curated list of approaches | [GitHub](https://github.com/Not-Diamond/awesome-ai-model-routing) |
| awesome-claude-code | — | Community hooks/skills collection | [GitHub](https://github.com/hesreallyhim/awesome-claude-code) |

### Ключевой инсайт

> Pure embedding-similarity routing (Semantic Router + MiniLM) = **58% accuracy** (GQR-Bench).
> TF-IDF + классификатор = **88%**.
> Embedding + обученный RF/SVM = **83%**.
> Ваш keyword + fuzzy = вероятно **50-70%** (нет ground truth).

**Вывод:** Переход на «чистые embeddings» без классификатора — шаг НАЗАД. Нужен hybrid: keyword + embedding + lightweight classifier.

---

## ДОРОЖНАЯ КАРТА УЛУЧШЕНИЙ

### Фаза 11: FIX — Критическое исправление activation rate

**Приоритет:** P0 — без этого остальные фазы бессмысленны
**Цель:** Activation rate 8.8% → 70%+

| # | Задача | Артефакт | Детали |
|---|--------|----------|--------|
| 11.1 | Мигрировать skill-router.py с `systemMessage` на `stdout` | skill-router.py | Как skill-eval-enforcer-shell.py: `print()` вместо `HookOutput().system_message()`. Исследование Scott Spence: stdout = 100% injection vs 55% для JSON |
| 11.2 | Объединить skill-router + eval-enforcer в один stdout output | Один hook или chain | Сейчас: generic "MANDATORY SKILL EVALUATION" + отдельный `[SKILL-ROUTER] Bundles:`. Нужно: один stdout с конкретными скиллами + императивной инструкцией |
| 11.3 | Конкретизировать инструкцию | Шаблон stdout | `"ОБЯЗАТЕЛЬНО: Skill('X'), Skill('Y'). НЕ ПРОДОЛЖАЙ без активации."` вместо generic "evaluate skill relevance" |
| 11.4 | A/B тест: замерить activation rate до/после | data/skill-accuracy.jsonl | 50 промптов до, 50 после. Метрика: % recommend→activate |
| 11.5 | Добавить негативный маркер при не-активации | skill-eval-enforcer | Если скиллы рекомендованы, но в следующем промпте нет `<command-name>` — логировать miss |

**Ожидаемый результат:** activation rate 70-85% (уровень best practices для forced-evaluation pattern)

---

### Фаза 12: MEASURE — Ground Truth и метрики качества

**Приоритет:** P0 — без метрик невозможно оптимизировать
**Цель:** Автоматический расчёт precision/recall/F1

| # | Задача | Артефакт | Детали |
|---|--------|----------|--------|
| 12.1 | Создать ground truth dataset | data/skill-router-ground-truth.jsonl | 100+ prompt→skills пар, размеченных вручную. Формат: `{"prompt": "...", "expected_skills": ["X", "Y"], "expected_bundles": ["Z"]}` |
| 12.2 | Скрипт оценки offline | scripts/eval-skill-router.py | Прогоняет ground truth через роутер, считает precision/recall/F1 по skill и по bundle |
| 12.3 | Интеграция в CI | .github/workflows/ | Запускать eval при изменении config или router code. FAIL если F1 < threshold |
| 12.4 | Dashboard метрик | scripts/skill-router-dashboard.py | Визуализация: activation rate, precision, recall, confusion matrix по бандлам |
| 12.5 | False positive tracking | data/skill-router-fp.jsonl | Ручная пометка ненужных рекомендаций через feedback hook |

**Ожидаемый результат:** Возможность объективно сравнивать подходы и итерировать

---

### Фаза 13: PRUNE — Оптимизация конфигурации

**Приоритет:** P1 — снизить noise, повысить precision
**Цель:** Сократить бандлы с 42 до 15-20, повысить precision

| # | Задача | Артефакт | Детали |
|---|--------|----------|--------|
| 13.1 | Анализ бандлов по usage | Отчёт | 42 бандла, но 50% трафика = top-5. Мертвые бандлы (0 срабатываний за 30 дней) → кандидаты на удаление |
| 13.2 | Мержить мелкие бандлы | skill-router-config.json | `hook-debugging` + `hook-bugs` + `windows-paths` + `hook-enforcer` + `hook-architecture` → один `hooks-debug` bundle |
| 13.3 | Мержить claude-code-* | skill-router-config.json | 7 claude-code-* бандлов → 2-3: `claude-code-dev` (plugins, subagents, programmatic), `claude-code-config` (settings, cli, terminal-ux), `claude-code-ops` (admin, github-actions) |
| 13.4 | Мержить langchain-* | skill-router-config.json | 5 langchain-* бандлов → 2: `langchain-core` (core, integrations, multiagent), `langchain-infra` (streaming, mcp, memory, production) |
| 13.5 | Мержить framework-* | skill-router-config.json | 7 framework-* бандлов → 3: `framework-use` (cli, api, quickstart), `framework-ops` (config, troubleshooting, caching), `framework-ui` (mcp-ui) |
| 13.6 | Убрать overlap keywords | Скрипт анализа | Ключевое слово "langchain" матчит `langchain-agent` И `langchain-rag` — нужна disambiguation |
| 13.7 | Hierarchical routing | 2-level config | Level 1: domain (1c, framework, claude-code, langchain). Level 2: sub-skill. Как NVIDIA blueprint с 77→10 groups |

**Ожидаемый результат:** 15-20 бандлов, precision +15-20%, меньше noise

---

### Фаза 14: EMBED — Semantic scoring layer

**Приоритет:** P1 — ключевое улучшение качества
**Цель:** Ловить парафразы и novel phrasings

| # | Задача | Артефакт | Детали |
|---|--------|----------|--------|
| 14.1 | Выбрать embedding модель | ADR | Кандидаты: `all-MiniLM-L6-v2` (22MB, <1ms), `nomic-embed-text` (130MB, ~3ms), `BGE-M3` (multilingual). Критерий: latency <50ms (hook timeout 5s), русский язык |
| 14.2 | Pre-compute route embeddings | data/route-embeddings.npz | Для каждого бандла: 5-10 примеров промптов → embed → средний вектор (centroid). Offline, при изменении конфига |
| 14.3 | Скрипт генерации embeddings | scripts/build-route-embeddings.py | `python scripts/build-route-embeddings.py` → читает config + примеры → генерирует .npz |
| 14.4 | Добавить примеры промптов в конфиг | skill-router-config.json | Новое поле `"utterances"`: 5-10 примеров на бандл. Пример: `{"query": {"utterances": ["напиши запрос", "сделай выборку", "помоги с SQL"]}}` |
| 14.5 | Layer C: Embedding scoring в skill-router.py | skill-router.py | `score_total = keyword_score * 0.4 + fuzzy_score * 0.2 + embedding_score * 0.4`. Embedding score = cosine_similarity(prompt_embed, bundle_centroid) |
| 14.6 | Lazy-load embeddings | skill-router.py | Первый вызов: load .npz + model (~200ms). Последующие: <10ms. В пределах 5s timeout |
| 14.7 | Benchmark: keyword vs hybrid | scripts/benchmark-router.py | Прогнать ground truth через оба подхода, сравнить F1. Ожидание: +10-20% recall |
| 14.8 | Fallback при отсутствии модели | skill-router.py | Если embedding model не установлена — graceful degradation на keyword-only |

**Ожидаемый результат:** Recall +15-25% за счёт семантического понимания

**Архитектура:**
```
prompt → [Layer A: keyword match]     → score_kw
       → [Layer B: fuzzy/lemma match] → score_fuzzy
       → [Layer C: embedding cosine]  → score_embed
       → weighted_sum → ranked bundles → top-N skills
```

---

### Фаза 15: LEARN — Автоматическая коррекция из логов

**Приоритет:** P2 — самооптимизация
**Цель:** Автоматическое улучшение конфига на основе usage data

| # | Задача | Артефакт | Детали |
|---|--------|----------|--------|
| 15.1 | Собирать feedback: useful/not-useful | data/skill-router-feedback.jsonl | После активации скилла — был ли он полезен? Маркер: если скилл активирован И задача завершена без ошибок → useful |
| 15.2 | Скрипт: keyword mining из логов | scripts/mine-keywords.py | Анализ промптов из data/skill-accuracy.jsonl, где activate произошёл. Извлечь n-grams, которые коррелируют с конкретными скиллами |
| 15.3 | Скрипт: auto-suggest config changes | scripts/suggest-config-updates.py | На основе missed activations: "Добавить keyword 'парсинг git' в бандл 'git-parsing'" |
| 15.4 | Weekly cron: accuracy report | scripts/weekly-router-report.py | Еженедельный отчёт: activation rate, top misses, suggested keywords |
| 15.5 | Train lightweight classifier (Phase 2 of LEARN) | models/skill-classifier.pkl | Когда накопится 200+ labeled pairs: TF-IDF + SVM/RF. Benchmark: ~83-88% accuracy (GQR-Bench data) |
| 15.6 | Layer D: Classifier scoring | skill-router.py | `score_total = kw*0.3 + fuzzy*0.1 + embed*0.3 + clf*0.3`. Classifier = trained model, fastest and most accurate |

**Ожидаемый результат:** Self-improving router, accuracy растёт с каждой неделей

---

### Фаза 16: SCALE — Hierarchical routing для 50+ скиллов

**Приоритет:** P2 — масштабирование
**Цель:** Поддержка 50-100 скиллов без деградации

| # | Задача | Артефакт | Детали |
|---|--------|----------|--------|
| 16.1 | 2-level routing | skill-router-config.json v4 | Level 1: domain classification (6 доменов). Level 2: skill selection внутри домена. Как NVIDIA blueprint |
| 16.2 | Domain definitions | config | `domains: {1c: [...], framework: [...], claude-code: [...], langchain: [...], research: [...], infra: [...]}` |
| 16.3 | Per-domain config files | skills/<domain>/router-config.json | Каждый домен — свой конфиг с бандлами. Загружается только при match на Level 1 |
| 16.4 | Token budget enforcement | skill-router.py | Max N skills × avg_tokens ≤ budget. Если budget exceeded — приоритизировать по score |
| 16.5 | Skill description index | data/skill-descriptions.json | Автоматически собирать description из YAML frontmatter всех SKILL.md |
| 16.6 | Dynamic skill discovery | skill-router.py | Новые SKILL.md автоматически добавляются в routing без ручного обновления конфига |

**Архитектура Level 1→2:**
```
prompt → [Domain Classifier] → "langchain"
                                    ↓
              [LangChain Sub-Router] → langchain-core, langgraph-core
```

---

### Фаза 17: OBSERVE — Production observability

**Приоритет:** P2 — мониторинг и алерты
**Цель:** Real-time visibility в работу роутера

| # | Задача | Артефакт | Детали |
|---|--------|----------|--------|
| 17.1 | SQLite metrics store | src/pdf_framework/observability/router_metrics_db.py | Структурированные метрики вместо JSONL. Таблицы: events, recommendations, activations, feedback |
| 17.2 | Streamlit dashboard page | src/ui/pages/skill_router_dashboard.py | Real-time: activation rate, bundle heatmap, accuracy trend, confusion matrix |
| 17.3 | OpenTelemetry spans | skill-router.py | Трейсинг: время каждого layer (keyword, fuzzy, embed), общее время роутинга |
| 17.4 | Alerting | scripts/router-alert.py | Если activation rate падает ниже 50% за последние 24ч — уведомление |
| 17.5 | A/B testing framework | skill-router.py | Флаг `"experiment": "embed_v1"` в конфиге. 50% промптов → старый алгоритм, 50% → новый. Сравнение activation rate |

---

## Сводка по фазам v2

| Фаза | Что | Приоритет | Зависимости | Ключевая метрика |
|------|-----|-----------|-------------|------------------|
| **11** | FIX activation rate | **P0** | — | 8.8% → 70%+ |
| **12** | Ground truth + metrics | **P0** | — | precision/recall/F1 |
| **13** | Prune bundles 42→15-20 | P1 | 12 | precision +15-20% |
| **14** | Embedding scoring layer | P1 | 12 | recall +15-25% |
| **15** | Auto-learn from logs | P2 | 12, 14 | Self-improving accuracy |
| **16** | Hierarchical routing | P2 | 13 | Support 50-100 skills |
| **17** | Observability | P2 | 12 | Real-time monitoring |

### Порядок выполнения

```
Фаза 11 (FIX) ──→ Фаза 12 (MEASURE) ──┬──→ Фаза 13 (PRUNE) ──→ Фаза 16 (SCALE)
                                         │
                                         ├──→ Фаза 14 (EMBED) ──→ Фаза 15 (LEARN)
                                         │
                                         └──→ Фаза 17 (OBSERVE)
```

**Минимальный viable набор:** Фазы 11 + 12 + 13

---

## Источники исследования

### Бенчмарки и статьи
- [GQR-Bench: Guarded Query Routing](https://arxiv.org/html/2505.14524v1) — TF-IDF + WideMLP = 88%, embedding similarity = 58%
- [RouteLLM (ICLR 2025)](https://arxiv.org/abs/2406.18665) — Matrix factorization router, 85%+ cost reduction
- [RouterXBench: Fair Evaluation](https://arxiv.org/html/2602.11877v1) — 16 routing algorithms compared
- [Agent Skills for LLMs](https://arxiv.org/html/2602.12430) — Skill selection patterns

### GitHub-проекты
- [aurelio-labs/semantic-router](https://github.com/aurelio-labs/semantic-router) (~3,200 ★) — Embedding-based route matching
- [lm-sys/RouteLLM](https://github.com/lm-sys/RouteLLM) (~4,500 ★) — Model routing via preference data
- [ulab-uiuc/LLMRouter](https://github.com/ulab-uiuc/LLMRouter) (~1,000 ★) — 16+ algorithms unified
- [NVIDIA-AI-Blueprints/llm-router](https://github.com/NVIDIA-AI-Blueprints/llm-router) — Hierarchical intent routing
- [Not-Diamond/awesome-ai-model-routing](https://github.com/Not-Diamond/awesome-ai-model-routing) (158 ★)

### Claude Code hooks community
- [Scott Spence: Skill Activation Rate Research](https://scottspence.com/posts/how-to-make-claude-code-skills-activate-reliably) — stdout = 100%, JSON systemMessage = 55%
- [claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) — All 13 hook events
- [awesome-claude-code](https://github.com/hesreallyhim/awesome-claude-code) — Community collection
- [Claude Code Hooks Reference](https://code.claude.com/docs/en/hooks) — Official docs

### Паттерны роутинга
- [Arize AI: Best Practices for Agent Routing](https://arize.com/blog/best-practices-for-building-an-ai-agent-router/)
- [Patronus AI: AI Agent Routing](https://www.patronus.ai/ai-agent-development/ai-agent-routing)
- [Short Primer on LLM Routing](https://kleiber.me/blog/2025/08/10/llm-router-primer/)
- [Intent Classification in <1ms with Embeddings](https://medium.com/@durgeshrathod.777/intent-classification-in-1ms-how-we-built-a-lightning-fast-classifier-with-embeddings-db76bfb6d964)

---

## Архив: Фазы 0-10 (DONE)

<details>
<summary>Фазы 0-10 (оригинальный roadmap, выполнены)</summary>

### Фаза 0: Подготовка и проектирование ✅
- Спроектирована JSON-схема конфига роутера
- Определён формат systemMessage
- Стратегия scoring: keyword match + fuzzy
- Fallback: pass-through при отсутствии совпадений
- Приоритет при пересечении: top-N по score

### Фаза 1: Universal Skill Router Engine ✅
- `skill-router.py` — BaseHook, keyword + fuzzy matching
- Загрузка конфига из skill-router-config.json
- Multi-bundle detection, optional skills, session dedup
- Affinity injection

### Фазы 2-6: 1C-Enterprise ⏳ Pending
- Meta-skill, domain skills, config, testing

### Фаза 7: PDF Framework Config ✅
- 16 бандлов, 8 тестов, skill-router-config.json v3

### Фаза 8: PDF Domain Skills ✅
- 9 доменных скиллов: search-pipeline-debug, indexing-pipeline, graph-operations, evaluation-benchmark, embedding-models, qdrant-operations, agent-orchestration, prompt-engineering, deployment

### Фаза 9: MCP Per-Project ✅
- .mcp.json для PDF Framework

### Фаза 10: Мониторинг ✅ (частично)
- 10.1 DONE: logging в data/skill-router.log
- 10.2-10.7: pending → заменены Фазой 17

</details>
