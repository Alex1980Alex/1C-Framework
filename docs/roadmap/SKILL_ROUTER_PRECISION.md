# Plan: Улучшение точности рекомендаций скиллов

## Context

Рекомендаций 72, а активаций 4 — Activation Rate 2%. Две причины:
1. **Рекомендации неточные** — `min_score: 1` слишком низкий, generic keywords срабатывают на обычных промптах, информационные запросы получают рекомендации для action-скиллов
2. **Session dedup сломан** — `get_already_recommended()` / `record_recommendation()` импортируются в `skill-router.py:302-303`, но **не определены** в `session_state.py` → except молча глотает ошибку → один скилл рекомендуется повторно каждый промпт

Запрос: «рекомендации некорректные — нужно делать правильные рекомендации, и если рекомендация последовала — использовать скиллы»

## Изменения

### 1. `session_state.py` — добавить недостающие функции

Файл: [`.claude/hooks/shared/session_state.py`](.claude/hooks/shared/session_state.py)

Добавить в класс `SessionState`:
- `record_recommendation(skills: list[str])` — записывает рекомендованные скиллы в `state["recommended_skills"]` (list, dedup)
- `get_already_recommended() -> list[str]` — возвращает уже рекомендованные

Добавить module-level обёртки (по аналогии с `set_prompt_id` / `get_prompt_id`):
```python
def record_recommendation(skills: list[str]) -> None:
    SessionState.record_recommendation(skills)

def get_already_recommended() -> list[str]:
    return SessionState.get_already_recommended()
```

Обновить `__all__`, `_empty_state()` (добавить `"recommended_skills": []`), `reset_session()`.

### 2. `skill-router-config.json` — поднять пороги, убрать generic keywords

Файл: [`.claude/skills/skill-router-config.json`](.claude/skills/skill-router-config.json)

| Параметр | Было | Станет | Почему |
|----------|------|--------|--------|
| `min_score` | 1 | 2 | Одно keyword-совпадение — слишком шумно |
| `max_bundles` | 3 | 2 | Меньше шума, точнее рекомендации |

Очистка generic keywords из бандлов (срабатывают на обычных промптах):
- `framework-config`: убрать `"настройка"`, `"settings"` (слишком общие)
- `framework-troubleshooting`: убрать `"ошибка"`, `"error"`, `"проблема"` (срабатывают на любом баге)
- `search`: убрать `"найди"`, `"найти"` (срабатывает на любом поиске по коду)
- `infrastructure`: убрать `"hook"`, `"skill"`, `"mcp"`, `"хук"`, `"навык"` (срабатывают при любом обсуждении хуков)
- `workflow-research`: убрать `"как работает"`, `"что такое"`, `"объясни"`, `"explain"`, `"research"` (срабатывают на любом вопросе)

Стратегия: оставить только **конкретные** ключевые слова. Для generic-бандлов (`workflow-research`, `infrastructure`) — перевести в weighted_keywords с весом 1 и добавить конкретные фразы с весом 3+.

### 3. `skill-router.py` — intent classification + confidence

Файл: [`.claude/hooks/skill-router.py`](.claude/hooks/skill-router.py)

**3a. Intent classification** (в начале `execute()`, после IDE-skip):

```python
def _classify_intent(prompt: str) -> str:
    """Classify prompt intent: action | informational | system."""
    p = prompt.strip().lower()
    # System: slash-commands, very short
    if p.startswith("/") or len(p) < 15:
        return "system"
    # Informational markers
    info_patterns = [
        r"^(что такое|как работает|объясни|расскажи|почему|зачем|what is|how does|explain|describe|tell me)",
        r"^(покажи|где находится|найди файл|прочитай|открой|read |show |where is|find file)",
        r"\?$",  # Questions ending with ?
    ]
    for pat in info_patterns:
        if re.search(pat, p):
            return "informational"
    return "action"
```

**3b. Intent-dependent min_score**:
- `action` → `min_score` из конфига (2)
- `informational` → `min_score + 1` (3) — строже, потому что info-промпты редко нуждаются в скиллах
- `system` → skip (return None)

**3c. Confidence levels** в output:
- HIGH (score >= 4): `"ОБЯЗАТЕЛЬНО: {skill}"`
- MEDIUM (score 3): `"Рекомендуется: {skill}"`
- LOW (score 2): `"Опционально: {skill}"`

### 4. `skill-eval-enforcer-shell.py` — conditional enforcement

Файл: [`.claude/hooks/skill-eval-enforcer-shell.py`](.claude/hooks/skill-eval-enforcer-shell.py)

Сейчас: MANDATORY на **каждый** промпт > 15 chars — создаёт шум.

Изменение: применять _classify_intent() — если `informational`, не выводить MANDATORY instruction.

```python
# Import intent classifier
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from skill_router import _classify_intent  # Reuse

intent = _classify_intent(prompt)
if intent != "action":
    sys.exit(0)  # No enforcement for informational/system prompts
```

## Файлы

| Файл | Действие |
|------|----------|
| `.claude/hooks/shared/session_state.py` | +`record_recommendation()`, +`get_already_recommended()`, обновить state |
| `.claude/skills/skill-router-config.json` | `min_score: 2`, `max_bundles: 2`, очистить generic keywords |
| `.claude/hooks/skill-router.py` | +`_classify_intent()`, intent-dependent thresholds, confidence levels |
| `.claude/hooks/skill-eval-enforcer-shell.py` | Conditional enforcement (skip for informational) |

## Verification

```bash
# 1. Проверить session dedup
cd .claude/hooks && python -c "
from shared.session_state import record_recommendation, get_already_recommended
record_recommendation(['tech-research', 'pdf-search'])
print('Recommended:', get_already_recommended())
record_recommendation(['tech-research'])  # Dedup
print('After dedup:', get_already_recommended())
"

# 2. Проверить intent classification
cd .claude/hooks && python -c "
from skill_router import _classify_intent
print(_classify_intent('что такое RAG?'))           # -> informational
print(_classify_intent('создай новый endpoint'))     # -> action
print(_classify_intent('/help'))                     # -> system
"

# 3. Проверить min_score=2 (одно keyword не проходит)
echo '{"prompt":"найди файл config.py"}' | python .claude/hooks/skill-router.py
# Ожидание: НЕТ рекомендаций (score=1 для search, ниже порога)

# 4. Проверить enforcer conditional
echo '{"prompt":"что такое embeddings?"}' | python .claude/hooks/skill-eval-enforcer-shell.py
# Ожидание: пустой вывод (informational -> skip)

# 5. Dashboard — перезапустить сервер и проверить метрики
curl http://127.0.0.1:8000/metrics | python -c "import sys,json; print(json.load(sys.stdin)['skill_metrics'])"
```
