# План: Принудительное использование Skills при планировании/архитектуре

**Дата:** 2026-02-24
**Статус:** Планирование

## Контекст

Когда Claude запускает субагенты (`Plan`, `architect-design`) для планирования, субагент должен **обязательно** загрузить skills (`analyze-1c-task-v2`, `implement-1c-task`) и использовать их методологию. Сейчас это не принуждается — субагент может спланировать "по своему усмотрению".

**Цель:** Тройная защита:
- **Уровень A:** Блокировать вызов субагента если промпт не содержит требование загрузить skills
- **Уровень B:** Блокировать tool calls субагента пока он не загрузит skill + systemMessage напоминания
- **Уровень C:** MANDATORY задача на уровне основной сессии (страховка если субагент всё равно вернулся без skills)

---

## Схема работы (три уровня)

```
════════════════════════════════════════════════════════════════
  УРОВЕНЬ A — PreToolUse на Task (блокировка вызова субагента)
════════════════════════════════════════════════════════════════

Claude → Task(subagent_type="Plan", prompt="спланируй X...")
              │
              ▼
   PreToolUse hook "Task":
   subagent_type ∈ {Plan, architect-design, pm-spec-spec}?
              │
           ДА ▼
   prompt содержит ссылки на skills?
   (regex: SKILL\.md|analyze-1c-task|implement-1c-task|\.claude/skills/)
       │              │
    НЕТ ▼          ДА ▼
   БЛОКИРУЕТ       Записывает state:
   "Добавь в       active=true,
    промпт         pending_subagent=true
    skills!"       Пропускает вызов

════════════════════════════════════════════════════════════════
  УРОВЕНЬ B — PreToolUse/PostToolUse внутри субагента
  (блокировка tool calls + systemMessage напоминания)
════════════════════════════════════════════════════════════════

Субагент запущен, делает tool calls:
              │
              ▼
   Каждый tool call субагента проходит через хуки:
              │
              ▼
   state.active == true И state.satisfied == false?
       │              │
    ДА ▼           НЕТ ▼
   Tool == Read     Пропускает
   на SKILL.md?     (skill уже загружен
       │              или enforcement неактивен)
    ДА ▼
   Записать консультацию в state
   state.satisfied = true
   systemMessage: "Skill загружен, продолжайте"
       │
    НЕТ ▼
   Tool == Read/Grep/Glob/mcp__ (рабочий инструмент)?
       │
    ДА ▼
   Разрешить N первых вызовов (grace_period = 3)
   чтобы субагент мог осмотреться
       │
   После grace_period ▼
   БЛОКИРОВАТЬ tool call:
   "СТОП! Сначала загрузите skill:
    Read('.claude/skills/analyze-1c-task-v2/SKILL.md')
    Вы не сможете продолжить пока не загрузите skill."
   +
   systemMessage: "НАПОМИНАНИЕ: Skill не загружен!"

════════════════════════════════════════════════════════════════
  УРОВЕНЬ C — PostToolUse после возврата субагента + Stop
  (MANDATORY задача — страховка)
════════════════════════════════════════════════════════════════

Субагент завершился → результат вернулся
              │
              ▼
   PostToolUse на "Task":
   state.pending_subagent == true?
              │
           ДА ▼
   state.satisfied == true?
       │              │
    НЕТ ▼          ДА ▼
   add_task(        Очистить state
   MANDATORY,       Всё ок
   "Загрузить
    skills!")
              │
              ▼
   Claude пытается остановиться
              │
              ▼
   task-enforcer.py → БЛОКИРУЕТ Stop
   "MANDATORY: загрузи skills!"
```

---

## Файлы для создания/модификации

### 1. СОЗДАТЬ: `.claude/hooks/planning-skill-enforcer.py`

**Подписка:** PreToolUse (`Task`) + PostToolUse (`Task|Read|Skill|Grep|Glob|mcp__`)

**Конфигурация:**

```python
HOOK_ID = "planning-skill-enforcer"
STATE_FILE = "cache/planning-skill-enforcer-state.json"

PLANNING_SUBAGENTS = {"Plan", "architect-design", "pm-spec-spec"}

# Маппинг контекст → требуемые skills
SKILL_REQUIREMENTS = {
    "1c_analysis":        ["analyze-1c-task-v2"],
    "1c_implementation":  ["implement-1c-task"],
    "architecture":       [],  # любой skill
    "general_planning":   [],  # любой skill
}

# Regex для проверки промпта субагента
SKILL_REFERENCE_PATTERN = r"SKILL\.md|analyze-1c-task|implement-1c-task|\.claude/skills/"

# Grace period: сколько tool calls разрешить до блокировки
GRACE_PERIOD = 3

# Пропуск
SKIP_PHRASES = [r"без\s+анализа", r"просто\s+сделай", r"без\s+skill"]
TRIVIAL_INDICATORS = [r"исправь\s+опечатку", r"typo", r"одну\s+строку"]

# Cooldown
COOLDOWN_MINUTES = 5
```

**Обработчики:**

**A) `handle_pre_tool_use(input_data)` — Уровень A + B**

```
Если tool_name == "Task":
  → УРОВЕНЬ A: Проверка промпта субагента
  → subagent_type ∈ PLANNING_SUBAGENTS?
  → prompt содержит SKILL_REFERENCE_PATTERN?
     НЕТ → БЛОКИРОВАТЬ: "Добавь в промпт требование загрузить skills..."
     ДА  → Определить контекст, записать state, пропустить

Если state.active И НЕ state.satisfied:
  → УРОВЕНЬ B: Блокировка tool calls субагента
  → Это Read на SKILL.md? → Записать консультацию, satisfied=true, пропустить
  → Это рабочий инструмент (Grep/Glob/Read-не-skill/mcp__)?
    → state.tool_calls_count < GRACE_PERIOD? → Инкремент, пропустить
    → state.tool_calls_count >= GRACE_PERIOD? → БЛОКИРОВАТЬ:
        "СТОП! Загрузите skill: Read('.claude/skills/{skill}/SKILL.md')
         Вы не можете продолжить без загрузки skill."
```

**B) `handle_post_tool_use(input_data)` — Уровень B + C**

```
Если state.active И НЕ state.satisfied:
  → Это Read на SKILL.md / Skill tool / mcp__1c-docs-rag(skills)?
    → Записать консультацию, проверить удовлетворённость
    → Если satisfied → complete_task_by_hook(), systemMessage: "Skill загружен!"
  → Иначе: systemMessage напоминание: "Skill ещё не загружен"

Если tool_name == "Task" И state.pending_subagent:
  → УРОВЕНЬ C: Субагент вернул результат
  → state.satisfied?
     НЕТ → add_task(MANDATORY, "Загрузить skills: ...")
     ДА  → Очистить state
```

### 2. АВТОСОЗДАНИЕ: `cache/planning-skill-enforcer-state.json`

```json
{
  "active": false,
  "context_type": null,
  "activated_at": null,
  "required_skills": [],
  "consultations": [],
  "satisfied": false,
  "pending_subagent": false,
  "tool_calls_count": 0,
  "updated_at": null
}
```

### 3. ИЗМЕНИТЬ: `.claude/hooks/stop/task-enforcer.py` (строка 36-42)

Добавить `"planning-skill-enforcer"` в MANDATORY_HOOKS:

```python
MANDATORY_HOOKS = {
    "memory-blocker-hook",
    "documentation-blocker-hook",
    "git-commit-reminder-hook",
    "code-task-creator-hook",
    "code-skill-enforcer",
    "planning-skill-enforcer"   # <-- НОВОЕ
}
```

### 4. ИЗМЕНИТЬ: `.claude/settings.json`

**PreToolUse** — matcher для Task + рабочих инструментов:
```json
{
  "matcher": "Task|Read|Grep|Glob|mcp__serena__|mcp__ripgrep__|mcp__ast-grep",
  "hooks": [
    {
      "type": "command",
      "command": "python D:/1C-Enterprise_Framework/.claude/hooks/planning-skill-enforcer.py"
    }
  ]
}
```

**PostToolUse** — matcher для отслеживания + Task возврат:
```json
{
  "matcher": "Task|Read|Skill|Grep|Glob|mcp__1c-docs-rag__search_docs|mcp__1c-docs-rag__search_docs_with_facets",
  "hooks": [
    {
      "type": "command",
      "command": "python D:/1C-Enterprise_Framework/.claude/hooks/planning-skill-enforcer.py"
    }
  ]
}
```

### 5. ИЗМЕНИТЬ: `CLAUDE.md`

```markdown
## КРИТИЧЕСКОЕ ПРАВИЛО: Принудительная загрузка Skills в субагентах

**Хук `planning-skill-enforcer` работает на трёх уровнях:**

**Уровень A (PreToolUse на Task) — блокировка вызова:**
При вызове субагента Plan/architect-design/pm-spec-spec промпт ОБЯЗАТЕЛЬНО
должен содержать требование загрузить skills. Без этого вызов БЛОКИРУЕТСЯ.

Пример промпта:
  "ОБЯЗАТЕЛЬНО: Перед началом работы прочитай
   .claude/skills/analyze-1c-task-v2/SKILL.md и следуй методологии.
   [далее основная задача...]"

**Уровень B (PreToolUse внутри субагента) — блокировка tool calls:**
Субагент получает 3 бесплатных tool calls (grace period) для ориентации.
После этого все рабочие инструменты БЛОКИРУЮТСЯ пока субагент не прочитает SKILL.md.

**Уровень C (PostToolUse + Stop) — страховка MANDATORY:**
Если субагент всё-таки вернулся без загрузки skills — создаётся MANDATORY задача,
task-enforcer блокирует завершение основной сессии.

**Маппинг контекст → skill:**
- Анализ 1С → analyze-1c-task-v2
- Реализация 1С → implement-1c-task
- Архитектура/Планирование → любой релевантный skill

**Отключение:** "без анализа" или "просто сделай" в промпте.
```

---

## Зависимости / Переиспользуемый код

| Компонент | Файл | Что переиспользуем |
|-----------|------|-------------------|
| `add_task()` | `.claude/hooks/shared/task_master.py:286` | Создание MANDATORY задачи (Уровень C) |
| `complete_task_by_hook()` | `.claude/hooks/shared/task_master.py:486` | Авто-завершение при загрузке skills |
| `has_recent_completion()` | `.claude/hooks/shared/task_master.py:569` | Cooldown (5 мин) |
| `hook_lock` | `.claude/hooks/shared/hook_lock.py` | Потокобезопасная запись state |
| `code-skill-enforcer.py` | `scripts/claude-backend/.claude/hooks/` | Эталон PreToolUse блокировки tool calls |
| `documentation-blocker.py` | `.claude/hooks/documentation-blocker.py` | Эталон lifecycle detect→track→complete |
| `task-enforcer.py` | `.claude/hooks/stop/task-enforcer.py` | Бэкенд Stop-блокировки (Уровень C) |

---

## Порядок выполнения

1. Создать `planning-skill-enforcer.py` в `.claude/hooks/`
2. Добавить `"planning-skill-enforcer"` в MANDATORY_HOOKS в `task-enforcer.py`
3. Зарегистрировать хук в `settings.json` (PreToolUse + PostToolUse)
4. Добавить правило в `CLAUDE.md`
5. Тесты

---

## Верификация

1. **Тест Уровня A:** `Task(subagent_type="Plan", prompt="спланируй задачу")` без skills → хук блокирует вызов
2. **Тест Уровня A (пропуск):** `Task(subagent_type="Plan", prompt="...SKILL.md...")` → вызов проходит
3. **Тест Уровня B (grace):** Субагент делает 3 tool calls без skill → разрешены (grace period)
4. **Тест Уровня B (блокировка):** 4-й tool call без skill → БЛОКИРОВАН: "Загрузите skill!"
5. **Тест Уровня B (разблокировка):** Субагент читает SKILL.md → tool calls разрешены, systemMessage "Skill загружен"
6. **Тест Уровня C:** Субагент вернулся без skills → MANDATORY задача создана → task-enforcer блокирует Stop
7. **Тест пропуска:** "просто исправь опечатку" → enforcement неактивен
8. **Тест обычного субагента:** `Task(subagent_type="Explore")` → хук не вмешивается
9. **Тест cooldown:** Повторный промпт в течение 5 мин → нет дубликатов
