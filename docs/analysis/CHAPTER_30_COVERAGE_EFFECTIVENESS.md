# Глубокий анализ покрытия и эффективности главы 30

**Дата анализа:** 2026-04-23
**Объект:** `docs/framework documentation/30_ЭФФЕКТИВНОСТЬ/` (30.1–30.5)
**Метод:** инвентаризация реальной системы → сравнение с документацией → метрики SQLite/JSONL

---

## TL;DR

Глава 30 на 70% соответствует реальности. Найдено **12 расхождений**, из которых **3 критических**:

1. Hook `research-task-detector.py` упомянут в 30.2, но **отсутствует в `settings.json`** — документирован как активный, фактически не регистрирован
2. Метрики `hook-metrics.db` **устарели на 2 месяца** (Feb 22-24), новые хуки (z-ai-*, approval-gate) не имеют ни одной записи об исполнении
3. Router recommend↔activate gap: **14.5% activation rate** (658 активаций на 4554 рекомендаций) — основной KPI эффективности маршрутизации провален

Секция «Экономика» в 30.5 содержит **недоказанное утверждение** «~70% экономии» без бенчмарка.

---

## 1. Инвентаризация реальной системы

### 1.1 Hooks

| Метрика | Документ (30.2/30.3) | Реальность | Δ |
|---|---|---|---|
| Физических `.py` файлов в `.claude/hooks/` | — | 44 | — |
| Зарегистрировано в `settings.json` | 5 PreToolUse + 3 Stop | 42 hooks script refs | +34 |
| Упомянутых в главе 30 | ~15 | — | — |
| Orphan-файлы (не в settings) | 0 | **2** | +2 |

**Orphan hooks** (физически существуют, но не в `settings.json`):
- `research-task-detector.py` — **документирован в 30.2 как активный роутер**, но не зарегистрирован
- `skill-eval-enforcer.py` — заменён на `skill-eval-enforcer-shell.py`, старый файл не удалён

### 1.2 Skills и bundles

| Метрика | Документ | Реальность | Δ |
|---|---|---|---|
| SKILL.md файлов | ~66 (triad skill) / 75 (30.2 semantic) | **81** | +6..+15 |
| Всего bundles в router-config | 32 (30.2) | **41** | +9 |
| Конфиг version | 9 (30.2) | 9 | OK |
| Доменов | 8 | 8 | OK |

**Недокументированные bundles** (9 штук, отсутствуют в таблице 30.2):

| Домен | Bundle | Статус в 30.2 |
|---|---|---|
| 1c | `va-bdd` | отсутствует |
| framework | `framework-troubleshoot` | отсутствует |
| framework | `framework-cache` | отсутствует |
| langchain | `langchain-streaming` | отсутствует |
| langchain | `langchain-multiagent` | отсутствует |
| tools | `obsidian-vault` | отсутствует |

### 1.3 MCP серверы

| Метрика | Документ (30.5) | Реальность | Δ |
|---|---|---|---|
| Всего в `.mcp.json` | «21+» | **24** (22 active + 2 disabled) | +3 |
| Серверов в `bsl.json` | 4 | **8** | +4 |
| Серверов в `full.json` | «+4» | **13** | +9 |
| Серверов в `pdf.json` | 1 | 1 | OK |

**Некорректный статус в 30.5:**
- **`serena` документирован как активный** («ключевые MCP-серверы» таблица), но фактически `disabled: true` в `.mcp.json`

**Недокументированные серверы** (11 активных, не упомянуты в 30.5):
- `bsl-code-search`, `bsl-debugger`, `bsl-platform-context`
- `memory-ai`, `vector-memory`, `skill-learning` (документирован только агрегатор `memory-orchestrator`)
- `edt-mcp`, `mcp-onec-test-runner`, `1c-debug`
- `1c-mcp-crud-infeeda`, `1c-mcp-crud-daily`, `1c-mcp-crud-dev39144` (три дополнительные базы)
- `obsidian-mcp` — в MEMORY.md помечен как DISABLED, в реальности active

---

## 2. Метрики эффективности

### 2.1 Два параллельных SQLite-трекера

Система собирает метрики в **две несинхронизированные БД**:

| БД | Окно данных | Записи | Покрытие hooks |
|---|---|---|---|
| `data/hook-metrics.db` | **2026-02-22 → 02-24** (2 дня) | 3026 invocations, 14 сессий | 22 hooks |
| `data/hooks.db` | 2026-03-29 → 04-23 | 892 skill_usage, 129 delegation | нет invocation-таблицы |

**Проблема**: `hook-metrics.db` перестал писаться после 24 февраля. Все хуки, зарегистрированные после этой даты (z-ai-write-guard, z-ai-delegation-enforcer, approval-gate, code-review-enforcer, posttooluse-*, session-context-enforcer), **не имеют ни одной записи** о своей работе. Документ 30.4 заявляет «полную видимость эффективности» — по факту видимость для ~50% хуков.

### 2.2 Hook invocation stats (hook-metrics.db, Feb 22-24)

Top-10 вызовов:

| Hook | Calls | Avg ms | Blocks | Block% |
|---|---:|---:|---:|---:|
| CodeSkillEnforcer | 605 | 14 | 67 | 11.1% |
| AutoGitSave | 546 | 83 | 0 | — |
| SearchOptimizer | 356 | 38 | 0 | — |
| BulkActionGuard | 324 | 22 | 0 | — |
| DocsChangeTracker | 220 | 26 | 0 | — |
| docs-change-enforcer | 111 | 68 | 15 | 13.5% |
| ralph-wiggum-stop | 108 | 2 | 19 | 17.6% |
| task-enforcer | 107 | 36 | 19 | 17.8% |
| git-commit-enforcer | 105 | 39 | 0 | — |
| SkillRouter | 76 | **153** | 0 | — |
| DecisionToTriad | 70 | **140** | 0 | — |

Исходы (2 дня):
- allow: 2455 (81%)
- message: 445 (15%)
- **block: 120 (4%)**
- error: 6 (0.2%)

**Наблюдение**: `SkillRouter` (153ms) и `DecisionToTriad` (140ms) — на порядок медленнее остальных. Layer C (TF-IDF) + Layer D (semantic Qdrant) создают нагрузку, близкую к SLA (timeout 5000ms у PreToolUse). Документ 30.2 не упоминает latency-бюджет.

### 2.3 Router accuracy — главный KPI

`data/skill-accuracy.jsonl`: **5260 записей**.

| Тип | Count |
|---|---:|
| recommend | 4554 |
| activate | 658 |
| confirmed | 42 |
| failed | 6 |

**Activation rate = 658 / 4554 = 14.4%** — на каждую активацию router делает ~7 напрасных рекомендаций.

Источники активаций:
- `direct` (PostToolUse:Skill): **655** (99.5%)
- `prompt-detection`: **3** (0.5%)

**Вывод**: workaround prompt-detection, позиционированный в 30.4 как основной обход бага #6305, **не работает на практике**. PostToolUse на Windows v2.1.87 работает исправно — workaround избыточен.

### 2.4 Router recommend vs activate mismatch

Top-5 рекомендованных vs top-5 активированных — **пересечение 0**:

| Ранг | Recommended | Activated |
|---|---|---|
| 1 | `langgraph-core` (593) | `bsl-development` (167) |
| 2 | `langchain-core` (589) | `code-verify` (93) |
| 3 | `doc-to-skill` (427) | `task-protocol` (49) |
| 4 | `embedding-models` (408) | `1c-doc-research` (34) |
| 5 | `framework-cli` (383) | `create-hook` (27) |

Router настойчиво рекомендует LangChain/LangGraph/framework-темы, пользователь активирует 1С/BSL/verify. **Router калиброван под неактуальный workload** — нужно пересмотреть `weighted_keywords` для 1С-доменов.

### 2.5 Delegation outcomes

Два источника с расхождением:

| Источник | Записей | Схема |
|---|---:|---|
| `delegation-outcomes.jsonl` | 561 | `{content_type, domain, classification, context_features, delegated}` (TensorZero) |
| `hooks.db:delegation_outcomes` | 129 | `{provider, model, content_type, response_time, text_length, quality_score, attempt}` |

Классификации (JSONL): Medium 48%, Hard 33%, Never 11%, Soft 7%. Delegated: 501/558 = **89.8%** (30.4 цитирует 89.2% — отклонение +0.6 п.п.).

**Проблема**: две разные схемы трекинга делегирования не позволяют соединить «что классифицировано» с «как выполнено». Fusion layer отсутствует.

### 2.6 Skill usage (hooks.db, 2026-03-29 → 04-23)

Top-10 реально активируемых скиллов за последний месяц:

| Skill | Calls |
|---|---:|
| bsl-development | 200 |
| code-verify | 140 |
| 1c-doc-research | 55 |
| va-bdd-testing | 48 |
| learning-loop | 45 |
| 1c-mcp-crud | 44 |
| task-protocol | 42 |
| evaluation-benchmark | 37 |
| create-hook | 37 |
| z-ai-delegation | 28 |

**Аномалия**: `1c-mcp-crud` (44 активации) описывает **DISABLED** MCP-сервер (ROCTUP .epf :6003). В MEMORY.md стоит feedback "Не вызывать skill `1c-mcp-crud`". Однако skill активировался 44 раза за месяц — либо feedback не работает, либо skill-router продолжает его предлагать.

---

## 3. Покрытие документации главы 30

| Раздел | Заявлено в 30.X | Проверяемо в коде | Покрытие | Статус |
|---|---|---|---:|---|
| 30.2 — 4 слоя router | 4 | 4 (skill-router.py содержит все) | 100% | OK |
| 30.2 — 32 bundles | 32 | 41 (config v9) | 78% | **UNDER** |
| 30.2 — доп. роутеры | 3 | 2 активны (research-task-detector не в settings) | 67% | **BROKEN** |
| 30.3 — 5 PreToolUse enforcers | 5 | 5 (+ ещё code-review, search-optimizer) | 100% | OK |
| 30.3 — 3 Stop enforcers | 3 | 3 + ralph-wiggum-stop | 100% | OK |
| 30.4 — skill-accuracy источники | 2 (PostToolUse + prompt-detection) | 2 | 100% | функционально OK |
| 30.4 — DelegationBandit | Pure numpy, 4 arm, 6-dim | файл есть, 561 outcome | 100% | OK |
| 30.5 — 4 MCP профиля | 4 | 5 (включая `lazy-mcp-config.json`) | 80% | minor |
| 30.5 — 7 ключевых MCP | 7 | 22 active | **32%** | **SEVERE UNDER** |
| 30.5 — LLM Rotation 5 провайдеров | 5 | нужна отдельная верификация | — | не проверено |

---

## 4. Критические расхождения (требуют правки)

### P0 — сломанная информация

1. **30.2, таблица «Дополнительные роутеры UserPromptSubmit»**: удалить или пометить `research-task-detector.py` как «зарегистрирован как orphan-файл, не в settings.json». Либо вернуть его в `settings.json`.
2. **30.5, таблица «Ключевые MCP-серверы»**: `serena` помечена активной, фактически `disabled: true`. Удалить или поменять статус.
3. **MEMORY.md → skill 1c-mcp-crud**: feedback «не вызывать» нарушается 44 раза/мес. Либо усилить блокировку (hook-level), либо удалить feedback.

### P1 — устаревшие цифры

4. **30.2, таблица доменов**: обновить до 41 bundles, добавить 9 пропущенных (`va-bdd`, `framework-troubleshoot`, `framework-cache`, `langchain-streaming`, `langchain-multiagent`, `obsidian-vault`).
5. **30.5, MCP-экосистема**: расширить перечень с 7 до 22 активных серверов, выделить категории (BSL: 4, 1C CRUD: 4, Memory: 4, Dev tools: 6, Framework: 1, OpenSpec: 1, Proxy: 1, Obsidian: 1).
6. **30.5, «21+ MCP»**: уточнить до «24 (22 активных + 2 отключённых)».

### P2 — недоказанные утверждения

7. **30.5, раздел «Экономика»**: утверждение «~70% экономии» не подтверждено бенчмарком. Либо удалить, либо провести измерение и заменить на реальные цифры (пример: собрать `response_time` + `text_length` из `hooks.db:delegation_outcomes` за месяц).
8. **30.4, prompt-detection**: позиционирование как «основной workaround» не соответствует 0.5% доле. Переписать: «запасной канал; PostToolUse на Windows v2.1.87 работает штатно».

### P3 — системные проблемы вне главы 30

9. **hook-metrics.db staleness**: остановил запись 2026-02-24. Найти и исправить причину — критично для 30.4 «полная видимость эффективности».
10. **Router calibration**: 14.4% activation rate + top-5 mismatch. Пересмотреть `weighted_keywords` под текущий workload (BSL/1С vs LangChain).
11. **Fusion delegation trackers**: два несинхронизированных источника (JSONL vs hooks.db) с разными схемами. Договориться об единой схеме и мигрировать.
12. **Latency SLA**: SkillRouter 153ms, DecisionToTriad 140ms. Добавить в 30.2 раздел «Производительность» с budget 200ms/500ms.

---

## 5. Рекомендации по итогам

### Короткие фиксы (день работы)

- [ ] Удалить `research-task-detector.py` из 30.2 или вернуть в `settings.json`
- [ ] Поменять статус `serena` в 30.5 таблице на «DISABLED (требует активации)»
- [ ] Обновить таблицу доменов 30.2 до 41 bundles
- [ ] Расширить таблицу MCP в 30.5 до 22 активных
- [ ] Убрать непроверенные «~70% экономии» из 30.5

### Средние (неделя)

- [ ] Починить запись в `hook-metrics.db` (исследовать почему остановилась)
- [ ] Объединить схемы delegation-outcomes (JSONL и hooks.db)
- [ ] Провести настоящий бенчмарк token economy: собрать `input/output tokens × cost` за месяц из `hooks.db:delegation_outcomes`

### Долгие (месяц)

- [ ] Перекалибровать skill-router под реальный workload (BSL/1С top-5, а не LangChain)
- [ ] Удалить или деактивировать skill `1c-mcp-crud` (44 активации/мес на DISABLED сервер)
- [ ] Ввести latency-SLA для UserPromptSubmit хуков (budget 200ms)
- [ ] Автоматизировать этот аудит: скрипт `audit-chapter-30.py` с запуском в CI

---

## 6. Что работает хорошо

Позитивные находки, которые стоит зафиксировать:

- **CodeSkillEnforcer**: 605 вызовов, 11.1% block rate — активно принуждает к Skill() без чрезмерных false-positive
- **Stop-enforcers** (task/git/docs): совокупно 323 вызова, 34 блока — работают согласно дизайну
- **DelegationBandit**: 561 outcome, 89.8% delegation rate — warm-up пройден, автономный режим активен
- **Skill usage spike** `bsl-development` (200/мес) и `code-verify` (140/мес) — триада эффективно поддерживает основной 1С-workflow
- **Config v9** синхронизирован между доком и реальностью

---

## Приложение A — источники данных

| Источник | Путь | Размер |
|---|---|---|
| Hooks settings | `.claude/settings.json` | 42 скрипта |
| Hook files | `.claude/hooks/*.py` | 44 файла |
| Skill router config | `.claude/skills/skill-router-config.json` | v9, 41 bundle |
| Skills directory | `.claude/skills/*/SKILL.md` | 81 скилл |
| MCP main | `.mcp.json` | 24 сервера |
| MCP profiles | `.mcp/*.json` | 5 профилей |
| Accuracy log | `data/skill-accuracy.jsonl` | 5260 записей |
| Router log | `data/skill-router.log` | 4842 записей |
| Usage log | `data/skill-usage.log` | 920 записей |
| Delegation JSONL | `data/delegation-outcomes.jsonl` | 561 запись |
| Metrics DB (stale) | `data/hook-metrics.db` | Feb 22-24, 3026 invocations |
| Hooks DB (active) | `data/hooks.db` | Mar 29 – Apr 23, 892 usage |

Методика инвентаризации воспроизводима: все данные получены через `sqlite3`, `json.load`, `Path.glob` — без ручного анализа кода.
