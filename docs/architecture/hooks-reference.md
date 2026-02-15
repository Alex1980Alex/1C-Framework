# Hooks Reference

## Обзор

13 hooks в `.claude/hooks/`:

| Категория | Hooks | Python | Назначение |
|-----------|-------|--------|-----------|
| **Ralph Wiggum** (2) | ralph_activator, ralph_wiggum_stop | venv | Автономный цикл |
| **Guards** (3) | root-clutter-guard, bulk-action-guard, git-commit-enforcer | venv | Защита от ошибок |
| **Domain routing** (4) | skill-router, research-task-detector, decision-to-triad, search-optimizer | venv | Маршрутизация задач |
| **Enforcement** (4) | knowledge-cache-reminder, factory-enforcer, task-enforcer, docs-change-tracker | venv | Обязательные действия |

## Hook Protocol

**Вход** (stdin): JSON объект `HookInput`
```json
{
  "prompt": "текст промпта",          // UserPromptSubmit
  "tool_name": "Write",               // PreToolUse, PostToolUse
  "tool_input": {"file_path": "..."},  // PreToolUse, PostToolUse
  "tool_result": "...",               // PostToolUse
  "stop_reason": "end_turn",          // Stop
  "transcript": "..."                 // Stop
}
```

**Выход** (stdout): JSON объект `HookOutput`
```json
{"continue": true, "systemMessage": "подсказка для Claude"}   // allow + hint
{"continue": false, "decision": "block", "reason": "причина"} // block
```

**Без выхода** = allow (hook не возражает).

---

## Ralph Wiggum

### ralph_activator.py
| | |
|---|---|
| **Event** | UserPromptSubmit |
| **Timeout** | 5s |
| **Назначение** | Автоактивация Ralph Wiggum для сложных задач |

**Логика**: negative-first (простые задачи → skip), затем tiered detection:
1. Simple signals (2+ совпадений → skip Ralph)
2. Factory signals → type=factory, max 12
3. Phase signals → type=phase, max 15
4. Brainstorm signals → type=brainstorm, max 10
5. Research signals → type=research, max 8
6. Multi-step (numbered lists, sequential markers) → max 10
7. Fuzzy fallback (pymorphy3 для сложных глаголов)

**Output**: systemMessage с criteria + max iterations. Создаёт `.ralph_active` + `.ralph_criteria.json`.

---

### ralph_wiggum_stop.py
| | |
|---|---|
| **Event** | Stop |
| **Timeout** | 5s |
| **Назначение** | Контроль цикла Ralph — блокирует выход если критерии не выполнены |

**Логика**: читает `.ralph_criteria.json`, проверяет критерии через `CRITERIA_SIGNAL_MAP`, считает итерации. Блокирует если:
- Ralph активен И критерии не выполнены
- Итераций < max

**Criteria signals**:
| Критерий | Сигналы в transcript |
|---------|---------------------|
| `cache saved` | cache, кеш, saved, сохранён |
| `_index.json updated` | _index, index.json, обновлён |
| `settings.json updated` | settings, настройки |
| `MEMORY.md updated` | MEMORY, память |
| `test passed` | test, тест, passed, прошёл |
| `comparison table created` | comparison, таблица, matrix, pros, cons |
| `recommendation given` | recommendation, рекомендация, выбран |

---

## Guards

### root-clutter-guard.py
| | |
|---|---|
| **Event** | PreToolUse (matcher: Write) |
| **Timeout** | 3s |
| **Назначение** | Блокирует создание мусорных файлов в корне проекта |

**Блокирует**: `test_*`, `search_*`, `temp_*`, `check_*`, `reindex_*` в корне проекта.

**Output**: `decision: block` с причиной.

---

### bulk-action-guard.py
| | |
|---|---|
| **Event** | PostToolUse (matcher: Bash) |
| **Timeout** | 3s |
| **Назначение** | Детектирует bulk/destructive операции → Q5 reminder |

**Детектирует**: `rm -rf` с 5+ файлами, glob patterns, destructive commands.

**Output**: systemMessage с напоминанием о Q5 (enforce? нужен ли guard-hook?).

---

### git-commit-enforcer.py
| | |
|---|---|
| **Event** | Stop |
| **Timeout** | 5s |
| **Назначение** | Блокирует выход если есть незакоммиченные изменения |

**Проверяет**: `git status --porcelain` для watched paths (`.claude/`).

**Output**: список файлов + инструкция commit.

---

## Domain Routing

### skill-router.py
| | |
|---|---|
| **Event** | UserPromptSubmit |
| **Timeout** | 5s |
| **Назначение** | Config-driven маршрутизация промптов к скиллам по keyword bundles |

**Config**: `.claude/skills/skill-router-config.json` (7 bundles, ~50 keywords).

**Логика** (2-layer):
1. **Layer A**: phrase matching — lowercase prompt → scan bundle keywords → score
2. **Layer B**: fuzzy matching — pymorphy3 лемматизация + rapidfuzz опечатки (threshold 78%)

**Bundles**:
| Bundle | Skills | Keywords (примеры) |
|--------|--------|-------------------|
| search | pdf-search | поиск, search, найди, hybrid, bm25 |
| research-1c | 1c-doc-research | 1с, справочник, регистр, bsl |
| research-tech | tech-research | rag, embedding, qdrant, langchain |
| architecture | architecture-research | архитектура, подход, паттерн, best practice |
| infrastructure | hooks-skills-mcp-triad (+opt: triad-factory, create-hook) | hook, skill, mcp, триада |
| creation | create-hook (+opt: doc-to-skill) | создай hook, новый скилл |
| evaluation | task-evaluation | brainstorm, оценка подходов |

**Multi-bundle**: top-3 по score, dedup skills. No match → pass-through.

**Отличие от research-task-detector**: skill-router говорит КАКИЕ скиллы загрузить (data-driven), research-task-detector говорит КАКОЙ WORKFLOW использовать (code-driven).

---

### research-task-detector.py
| | |
|---|---|
| **Event** | UserPromptSubmit |
| **Timeout** | 5s |
| **Назначение** | Обнаружение research/brainstorm/hybrid задач → маршрут на skill |

**Маршруты**:
| Тип | Сигналы | Skill |
|-----|---------|-------|
| Hybrid | "как улучшить", "как оптимизировать" | research phases → brainstorm phases |
| Brainstorm | "придумай", "предложи", "спроектируй" | 5 brainstorm phases |
| Architecture | "best practices", "pattern", "подход" | architecture-research |
| 1C | "справочник", "документ", "регистр", "1С" | 1c-doc-research |
| Tech | "RAG", "embedding", "vector", "LangChain" | tech-research |
| Generic | "исследуй", "сделай обзор" | general research |

**FuzzyMatcher**: pymorphy3 для русских глаголов + rapidfuzz для опечаток (threshold 78%).

---

### decision-to-triad.py
| | |
|---|---|
| **Event** | UserPromptSubmit |
| **Timeout** | 5s |
| **Назначение** | Обнаружение решений/идей → маршрут на triad-factory |

**Сигналы**: "давай создадим", "нужен хук", "автоматизировать", "новый домен", "нужен guard".

**Skip**: если research-task-detector уже поймал (brainstorm фразы).

---

### search-optimizer.py
| | |
|---|---|
| **Event** | PreToolUse (matcher: Bash) |
| **Timeout** | 3s |
| **Назначение** | Подсказать оптимальные параметры для Search API |

**Детектирует**: `curl`, `http`, `search`, `api` в команде Bash.

**Output**: systemMessage с рекомендациями (strategy=hybrid, k=10).

**Не блокирует** — только advisory.

---

## Enforcement

### knowledge-cache-reminder.py
| | |
|---|---|
| **Event** | PostToolUse (matcher: WebSearch\|WebFetch) |
| **Timeout** | 5s |
| **Назначение** | После веб-поиска — создать задачу на сохранение в кеш |

**Scoring по доменам**:
| Домен | Сигналы (threshold >= 2) | Кеш |
|-------|--------------------------|-----|
| 1C | "1с", "платформа", "справочник", "its.1c.ru" | .claude/skills/1c-doc-research/cache/ |
| Architecture | "best practice", "pattern", "architecture" | .claude/skills/architecture-research/cache/ |
| Tech | "rag", "embedding", "langchain", "qdrant" | .claude/skills/tech-research/cache/ |

**Cooldown**: 10 минут после последнего completion.

---

### factory-enforcer.py
| | |
|---|---|
| **Event** | PostToolUse (matcher: Write) |
| **Timeout** | 5s |
| **Назначение** | При создании артефакта (.claude/hooks/, .claude/skills/) — создать задачи ШАГ 4-5 |

**Детектирует**: Write в `.claude/hooks/` или `.claude/skills/`.

**Создаёт задачи**:
- ШАГ 4: Зарегистрировать в settings.json
- ШАГ 5: Протестировать (`echo | python hook.py`)

---

### task-enforcer.py
| | |
|---|---|
| **Event** | Stop |
| **Timeout** | 5s |
| **Назначение** | Блокирует выход если есть pending mandatory tasks |

**Читает**: `hook-todos.json` (created by knowledge-cache-reminder и factory-enforcer).

**Блокирует**: если `pending > 0` для mandatory hooks.

---

### docs-change-tracker.py
| | |
|---|---|
| **Event** | PostToolUse (matcher: Write) |
| **Timeout** | 3s |
| **Назначение** | При изменении файлов в ключевых директориях — напомнить обновить документацию |

**Маппинг** (путь → документ):
| Изменение в | Обновить |
|-------------|----------|
| `.claude/hooks/` | hooks-reference.md |
| `.claude/skills/` | skills-reference.md |
| `.claude/settings.json` | core-framework-separation.md |
| `src/pdf_framework/search/` | overview.md |
| `src/pdf_framework/agents/` | overview.md |
| `src/pdf_framework/config/` | overview.md |
| `src/pdf_framework/loaders/` | overview.md |
| `src/api/routes/` | overview.md |

**Skip**: `docs/architecture/`, `cache/`, `__pycache__`, `_index.json`

**Cooldown**: 5 минут. Max 3 pending tasks.

---

## Shared Infrastructure

| Модуль | Файл | Назначение |
|--------|------|-----------|
| **BaseHook** | `base/protocol.py` | HookInput, HookOutput, stdin/stdout protocol |
| **core_paths** | `shared/core_paths.py` | Path resolution (project level) |
| **FuzzyMatcher** | `shared/fuzzy_match.py` | pymorphy3 + rapidfuzz (lazy-load) |
| **TaskMaster** | `shared/task_master.py` | CRUD для hook-todos.json |
| **HookLock** | `shared/hook_lock.py` | File lock для inter-hook sync |
| **RalphState** | `shared/ralph_state.py` | State для Ralph iterative loop |

## Создание нового hook

Использовать skill `/create-hook`. Шаблон:

```python
#!/usr/bin/env python3
import sys, os

_HOOK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HOOK_DIR)

from base import BaseHook, HookInput, HookOutput

class MyHook(BaseHook):
    def execute(self, inp: HookInput) -> HookOutput | None:
        # логика
        return None  # или HookOutput().system_message("hint")

if __name__ == "__main__":
    MyHook().run()
```

Затем: зарегистрировать в settings.json + протестировать.

## См. также

- [Triad Architecture](triad-architecture.md)
- [Skills Reference](skills-reference.md)
- [Ralph Wiggum](ralph-wiggum.md)
