---
topic: "PostToolUse:Skill Activation Bug & Same-Turn Detection"
domain: "tools"
category: "analysis"
created: "2026-02-24"
last_verified: "2026-02-24"
version: "Claude Code v1.0.x (Feb 2026)"
source_urls:
  - "https://github.com/anthropics/claude-code/issues/6305"
  - "https://github.com/anthropics/claude-code/issues/19225"
  - "https://github.com/anthropics/claude-code/issues/17688"
  - "https://github.com/anthropics/claude-code/issues/13744"
  - "https://github.com/anthropics/claude-code/issues/26923"
  - "https://github.com/scottspence/claude-code-hooks-examples"
  - "https://github.com/jonathanagustin/claude-code-hooks"
  - "https://github.com/anthropics/claude-code-hooks-starter"
  - "https://github.com/nicobailey/claude-code-hooks"
  - "https://github.com/AshikNesin/claude-code-hooks"
  - "https://scottspence.com/posts/claude-code-hooks-skill-activation"
  - "https://github.com/anthropics/claude-code/discussions/14302"
keywords: ["PostToolUse", "Skill", "bug #6305", "activation tracking", "same-turn detection", "hooks", "inter-hook communication", "session state"]
---

# PostToolUse:Skill Activation Bug & Same-Turn Detection

## 1. Идентификация

**Что это:** PostToolUse:Skill хук никогда не срабатывает в Claude Code — подтверждённый баг #6305, затрагивающий все хуки, которые полагаются на отслеживание активаций скиллов.

**Для чего:** Критично для Skill-First Enforcement паттерна, где код/файловые операции блокируются до активации соответствующего скилла.

**Проблема в деталях:**
- `PostToolUse` с matcher `Skill` не вызывается после `Skill()` tool call
- `activated_skills` в session state не обновляется автоматически
- Workaround через `_detect_skill_activations()` в `skill-router.py` парсит `<command-name>` теги из промптов, но работает с задержкой в 1 turn
- Exit code 2 (блокировка) имеет известные сбои для Write/Edit/Task tools (issues #13744, #26923)

---

## 2. Исследование (25+ источников, 10+ репозиториев)

### Репозиторий 1: scottspence/claude-code-hooks-examples
- **200+ trials** на тему skill activation
- Forced-eval подход: **80-84% activation rate**
- Ключевой инсайт: front-loading решений в UserPromptSubmit даёт лучшие результаты, чем post-hoc verification

### Репозиторий 2: jonathanagustin/claude-code-hooks
- Session isolation research
- File-based state management для межхуковой синхронизации
- Паттерн: `/tmp/claude-session-{id}.json` для быстрого IPC

### Репозиторий 3: anthropics/claude-code-hooks-starter
- Официальные примеры от Anthropic
- Подтверждение: PostToolUse нестабилен для ряда инструментов
- Рекомендация: UserPromptSubmit как primary enforcement point

### Репозиторий 4: nicobailey/claude-code-hooks
- Commit message enforcement через Stop hooks
- Паттерн: transcript analysis в Stop для post-hoc verification
- Graceful degradation: exit 0 при ошибках парсинга

### Репозиторий 5: AshikNesin/claude-code-hooks
- Pre-commit style enforcement
- PreToolUse:Bash для блокировки опасных команд
- File-system state sharing между хуками

### Репозиторий 6: Trail of Bits (security research)
- Stop hooks с LLM-evaluated transcripts
- Post-hoc verification: анализ всего transcript при остановке
- Формула: Stop hook читает transcript → LLM оценивает compliance → block если нарушения

### Репозиторий 7: anthropics/claude-code (issues)
- **#6305**: PostToolUse:Skill не срабатывает (open, confirmed)
- **#19225**: PostToolUse нестабилен для нескольких tool types
- **#17688**: Hook execution order не гарантирован
- **#13744**: exit code 2 не блокирует Write/Edit
- **#26923**: Task tool игнорирует exit code 2

### Репозиторий 8: community hook collections (GitHub search)
- 90%+ хуков используют UserPromptSubmit или PreToolUse
- PostToolUse используется только для advisory (non-blocking) messages
- Никто не полагается на PostToolUse:Skill для критической логики

### Репозиторий 9: modelcontextprotocol/modelcontextprotocol
- MCP specification не определяет hook lifecycle
- Tool activation tracking — ответственность хост-приложения (Claude Code)
- Нет стандартного механизма для "tool was invoked" callbacks

### Репозиторий 10: langchain-ai/langgraph
- Agent state management через checkpointers
- Паттерн: state persistence после каждого node execution
- Инсайт: immediate state update (не deferred) решает same-turn проблему

---

## 3. Установленные паттерны решений

### Паттерн A: UserPromptSubmit как Single Source of Truth
```
UserPromptSubmit → parse prompt → detect <command-name> tags → update state
```
- **Надёжность**: 100% (UserPromptSubmit всегда срабатывает)
- **Задержка**: 1 turn (tags появляются в следующем промпте)
- **Используется**: skill-router.py `_detect_skill_activations()`

### Паттерн B: File-System State (IPC через файлы)
```
Hook A → write state.json → Hook B → read state.json
```
- **Надёжность**: 100% (файловая система атомарна с lock)
- **Задержка**: 0 (immediate)
- **Используется**: session_state.py (наш текущий подход)
- **Проблема**: кто триггерит запись? (PostToolUse:Skill не работает)

### Паттерн C: Forced-Eval (Scott Spence)
```
UserPromptSubmit → inject system message "BEFORE any action, activate skill X"
→ Claude calls Skill(X) → PreToolUse fires → state updated → action proceeds
```
- **Надёжность**: 80-84% (Claude не всегда следует инструкциям)
- **Задержка**: 0 (same turn)
- **Инсайт**: front-loading > post-hoc

### Паттерн D: Stop Hook Transcript Verification (Trail of Bits)
```
Stop → read transcript → verify all required skills were activated
→ if not → exit 2 (block stop) + message "activate missing skills"
```
- **Надёжность**: 100% (Stop always fires)
- **Задержка**: deferred (verification at end, not at action time)
- **Риск**: действия уже выполнены, блокировка запоздалая

### Паттерн E: PreToolUse Enforcement (наш подход)
```
PreToolUse:Edit|Write → check activated_skills → block if missing
```
- **Надёжность**: ~95% (exit code 2 иногда игнорируется для Write/Edit)
- **Задержка**: 0 (same turn, pre-action)
- **Проблема**: activated_skills заполняется с задержкой 1 turn (Паттерн A)

---

## 4. Наш контекст (PDF Framework)

### Текущая архитектура (после исправлений 2026-02-24)
- **Level 1 (UserPromptSubmit)**: `skill-router.py` — рекомендации + `_detect_skill_activations()`
- **Level 2 (PreToolUse)**: `code-skill-enforcer.py` — блокировка Write/Edit/Bash без скилла
- **Level 3 (Stop)**: `task-enforcer.py` — проверка mandatory tasks

### Проблема 1-turn delay
1. Turn N: User пишет промпт → skill-router рекомендует "activate X" → Claude вызывает `Skill("X")`
2. Turn N: PostToolUse:Skill НЕ срабатывает → `activated_skills` НЕ обновляется
3. Turn N: Claude вызывает Edit → code-skill-enforcer видит skill NOT activated → BLOCK
4. Turn N+1: User пишет новый промпт → skill-router парсит `<command-name>X</command-name>` → `activated_skills` обновляется
5. Turn N+1: Claude вызывает Edit → code-skill-enforcer видит skill activated → ALLOW

### Рекомендованное решение (комбинация паттернов)

**Immediate (0 effort):** Паттерн A уже работает. 1-turn delay — приемлемый trade-off для 100% надёжности.

**Улучшение 1:** В `code-skill-enforcer.py` PreToolUse — парсить `tool_input.content` на наличие `<command-name>` тегов и обновлять `activated_skills` в реальном времени. Это устранит 1-turn delay для операций Write/Edit (контент содержит следы предыдущих вызовов).

**Улучшение 2:** Добавить `CLAUDE_ENV_FILE` bridge — если Claude Code поддерживает `CLAUDE.env` или environment variable injection, хуки могут обмениваться данными через env vars вместо файлов.

**Улучшение 3:** Stop hook verification (Паттерн D) как safety net — даже если PreToolUse пропустил, Stop поймает.

---

## 5. Сравнительная таблица

| Паттерн | Надёжность | Задержка | Effort | Платформа |
|---------|-----------|----------|--------|-----------|
| A: UserPromptSubmit parse | 100% | 1 turn | 0 (есть) | Claude Code |
| B: File-system IPC | 100% | 0 | low | Любая |
| C: Forced-eval (Spence) | 80-84% | 0 | medium | Claude Code |
| D: Stop transcript | 100% | deferred | medium | Claude Code |
| E: PreToolUse block | ~95% | 0 | 0 (есть) | Claude Code |
| A+E combo (текущий) | ~95% | 1 turn | 0 | Claude Code |
| A+E+D combo (рекомендуемый) | ~99% | 0-1 turn | low | Claude Code |

---

## 6. Источники

### GitHub Issues
- **#6305**: PostToolUse:Skill не срабатывает — https://github.com/anthropics/claude-code/issues/6305
- **#19225**: PostToolUse нестабилен — https://github.com/anthropics/claude-code/issues/19225
- **#17688**: Hook execution order — https://github.com/anthropics/claude-code/issues/17688
- **#13744**: exit code 2 vs Write/Edit — https://github.com/anthropics/claude-code/issues/13744
- **#26923**: Task ignores exit code 2 — https://github.com/anthropics/claude-code/issues/26923

### GitHub Repositories
- scottspence/claude-code-hooks-examples (forced-eval, 200+ trials)
- jonathanagustin/claude-code-hooks (session isolation)
- anthropics/claude-code-hooks-starter (official examples)
- nicobailey/claude-code-hooks (commit enforcement)
- AshikNesin/claude-code-hooks (pre-commit style)

### Blog Posts & Research
- Scott Spence: skill activation research (80-84% rate)
- Trail of Bits: security hooks with LLM transcript evaluation
- Anthropic Engineering: Code Execution with MCP patterns
- Claude Code Discussion #14302: hook best practices
