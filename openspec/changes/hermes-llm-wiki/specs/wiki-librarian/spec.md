# Spec: wiki-librarian

**Change:** hermes-llm-wiki
**Phase:** 3
**Profile:** python-framework

## Контекст

Существующая инфраструктура включает [docs-change-tracker.py](../../../../.claude/hooks/docs-change-tracker.py) (28KB, PostToolUse Write|Edit мониторинг docs/) и [docs-change-enforcer.py](../../../../.claude/hooks/docs-change-enforcer.py) (20KB, Stop hook с 50+ CODE_TO_DOMAIN mappings). Оба работают с docs/ как generic документацией, не знают про wiki-links и frontmatter валидацию.

Параллельно существует Qdrant `learned_patterns` коллекция (L2 слой, vector-memory MCP) — накапливает паттерны через `skill-learning.capture_pattern`, но без автоматического пути промоции в канонический L3 wiki-слой. Паттерны остаются pending/confirmed, никогда не «графдуируются» в читаемые wiki-страницы.

Фаза 3 вводит тонкий компонент `src/memory/librarian/wiki_promoter.py` (~80-100 LoC) для L2→L3 промоции и **расширяет** существующие docs-change hooks wiki-specific логикой без переписывания их core. Компонент **переиспользует** production-grade инфраструктуру:
- `ConflictResolver` (10KB, 4 стратегии резолюции)
- `EventBus` + `EventStore` (32KB, event sourcing)
- `LinkRegistry` (798 LoC, новые типы `PROMOTED_TO`/`SUPERSEDED_BY` из Phase 0)
- `MemoryCube.to_wiki_page()` (из Phase 0)
- `UnifiedSearch` (adapter pattern, dedup через cosine similarity)

Ключевой принцип: **никакой прямой записи в docs/wiki/**, только в `docs/wiki/drafts/`. Промоция из drafts в canonical — через human review (git PR), что обеспечивает контроль качества.

---

## ## ADDED REQ-1: WikiPromoter компонент

**Файл:** `src/memory/librarian/wiki_promoter.py` (новый, ~80-100 LoC)

Класс `WikiPromoter` отвечает за сканирование Qdrant `learned_patterns`, детектирование готовых паттернов (по confidence + usage count), дедупликацию через `UnifiedSearch`, резолюцию конфликтов через `ConflictResolver`, и создание draft'ов через `MemoryCube.to_wiki_page()`.

### API signatures

```python
# src/memory/librarian/wiki_promoter.py

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.memory.infrastructure.conflict_resolver import (
    ConflictResolver,
    ConflictStrategy,
)
from src.memory.infrastructure.event_bus import EventBus
from src.memory.orchestrator.link_registry import LinkRegistry, LinkType
from src.memory.orchestrator.memcube import MemoryCube, ContentType
from src.memory.orchestrator.unified_search import UnifiedSearchEngine


@dataclass
class PromotionConfig:
    confidence_threshold: float = 0.8
    # Field on the wire is `application_count` (canonical name, written by
    # vector_memory/server.py:handle_apply_pattern). Constructor arg retains
    # `usage_threshold` for back-compat with earlier spec wording; aligned
    # 2026-05-14 — see docs/roadmap/260514_ROADMAP_WIKI_PROMOTION_GAP.md.
    usage_threshold: int = 5
    dedup_similarity_threshold: float = 0.85
    drafts_dir: Path = Path("docs/wiki/drafts")
    search_timeout_s: float = 2.0


@dataclass
class PromotionResult:
    pattern_id: str
    success: bool
    draft_path: Optional[Path] = None
    conflict_resolved: bool = False
    superseded_by: Optional[str] = None
    error: Optional[str] = None


class WikiPromoter:
    def __init__(
        self,
        config: PromotionConfig,
        vector_memory_client,           # existing vector-memory MCP client
        search_engine: UnifiedSearchEngine,
        conflict_resolver: ConflictResolver,
        link_registry: LinkRegistry,
        event_bus: EventBus,
    ) -> None: ...

    async def scan_and_promote(self) -> list[PromotionResult]:
        """Scan learned_patterns и промоцировать ready кандидатов."""

    async def try_promote_pattern(self, pattern_id: str) -> PromotionResult:
        """Single-pattern promotion flow."""

    async def _check_readiness(self, pattern: dict) -> bool:
        """confidence >= threshold AND application_count >= threshold.

        Field name `application_count` is canonical (written by
        vector_memory/server.py:handle_apply_pattern). Earlier spec
        revisions used `usage_count` — see roadmap 260514 §Resolution.
        """

    async def _find_duplicate(self, pattern_text: str) -> Optional[str]:
        """unified_search по wiki для дедуп-проверки."""

    async def _resolve_conflict(
        self, pattern_id: str, existing_wiki_id: str
    ) -> ConflictStrategy: ...

    async def _create_draft(
        self, pattern: dict, slug: str
    ) -> Path:
        """MemoryCube(content_type=WIKI).to_wiki_page() → write file."""
```

### Сценарий 1: Успешная промоция нового паттерна

**Given** pattern `{id: "zai-provider-selection", confidence: 0.92, application_count: 8}` в `learned_patterns`
**And** `UnifiedSearch` не находит duplicates (max cosine < 0.85)
**When** вызывается `await promoter.try_promote_pattern("zai-provider-selection")`
**Then** создаётся файл `docs/wiki/drafts/zai-provider-selection.md` через `MemoryCube.to_wiki_page()`
**And** `link_registry.create_link(source=pattern_id, target=wiki_slug, link_type=LinkType.PROMOTED_TO)` вызван
**And** `event_bus.publish("wiki.draft.created", {...})` вызван
**And** возвращается `PromotionResult(success=True, draft_path=<path>)`

### Сценарий 2: Дедуп-коллизия → pattern superseded

**Given** pattern `{id: "qdrant-query-points", confidence: 0.88, application_count: 6}`
**And** существует `docs/wiki/patterns/qdrant-operations.md` с cosine similarity = 0.91
**When** вызывается `try_promote_pattern("qdrant-query-points")`
**Then** `ConflictResolver.resolve(strategy=SOURCE_PRIORITY)` возвращает решение «wiki wins»
**And** `link_registry.create_link(source=pattern_id, target=wiki_slug, link_type=LinkType.SUPERSEDED_BY)` вызван
**And** draft **не создаётся**
**And** `event_bus.publish("wiki.conflict.detected", {strategy: "SOURCE_PRIORITY", ...})`
**And** возвращается `PromotionResult(success=True, conflict_resolved=True, superseded_by="qdrant-operations")`

### Граничные условия

- Pattern не найден в Qdrant → `PromotionResult(success=False, error="Pattern not found")`
- Confidence < threshold → `success=False`, `error=None` (silent skip)
- `UnifiedSearch` timeout (>2s) → retry 1 раз, затем `error="Search timeout"`
- `drafts_dir` не существует → `mkdir(parents=True, exist_ok=True)` автоматически
- `ConflictResolver` возвращает `ConflictStrategy.MANUAL` → draft не создаётся, `error="Manual resolution required"`, событие `wiki.conflict.detected` всё равно публикуется
- EventBus.publish выбрасывает exception → log warning, промоция не прерывается (fire-and-forget)

### Ссылки

- `src/memory/infrastructure/conflict_resolver.py` — существующий `ConflictResolver`
- `src/memory/infrastructure/event_bus.py` — существующий `EventBus.publish()`
- `src/memory/orchestrator/link_registry.py` — `LinkRegistry.create_link()`, новые типы `PROMOTED_TO`, `SUPERSEDED_BY` (Phase 0)
- `src/memory/orchestrator/memcube.py` — `MemoryCube.to_wiki_page()` (Phase 0)
- `src/memory/orchestrator/unified_search.py` — `UnifiedSearchEngine.search()` с адаптерами wiki+graph (Phase 0)

---

## ## MODIFIED REQ-2: docs-change-tracker.py wiki validation extension

**Файл:** `.claude/hooks/docs-change-tracker.py`
**Было:** PostToolUse hook, маппит код→docs через `CODE_TO_DOMAIN` (50+ правил), создаёт hook-todos
**Стало:** дополнительная wiki-валидация при Write/Edit в `docs/wiki/*.md`

### Новая логика

1. Если изменённый файл лежит в `docs/wiki/` или `docs/wiki/drafts/`:
   - Запустить `kb-lint --json <file>` → парсинг JSON output
   - Парсинг `[[wiki-link]]` через regex `\[\[([^\]]+)\]\]`
   - Для каждой ссылки: проверить существование target файла в vault
   - Валидация YAML frontmatter: наличие обязательных полей (`unified_id`, `content_type`, `created_at`)
2. Результаты валидации:
   - `WIKI_OK`: silent, просто обновить mtime в `wiki_pages_v1` Qdrant collection
   - `WIKI_WARNING`: добавить в hook-todos как normal priority
   - `WIKI_ERROR`: добавить в hook-todos как high priority
3. Сохранить существующую `CODE_TO_DOMAIN` логику без изменений

### Сценарий 1: Broken wiki-link детектируется

**Given** пользователь редактирует `docs/wiki/entities/qdrant.md` и добавляет ссылку `[[nonexistent-page]]`
**When** PostToolUse hook срабатывает после Write
**Then** `docs-change-tracker` парсит `[[nonexistent-page]]`
**And** файл `docs/wiki/<...>/nonexistent-page.md` не найден в vault
**And** hook-todos получает новую задачу `{priority: high, content: "Broken wiki-link: [[nonexistent-page]] in qdrant.md"}`

### Сценарий 2: Invalid frontmatter

**Given** новый файл `docs/wiki/entities/test.md` без поля `unified_id` в frontmatter
**When** hook запускается
**Then** валидация возвращает `WIKI_ERROR: "Missing required frontmatter field: unified_id"`
**And** hook-todos получает high priority задачу

### Граничные условия

- `kb-lint` не установлен → silent skip kb-lint проверки, но regex/frontmatter работают
- Файл вне `docs/wiki/` → только существующая `CODE_TO_DOMAIN` логика, wiki-validation skipped
- Пустой файл (0 bytes) → `WIKI_WARNING`
- Циклические wiki-links (`A → B → A`) → detection + `WIKI_WARNING`
- Timeout kb-lint (>5s) → skip, log warning
- Файл переименован (Write на новый путь + старый удалён) → только new path валидируется

### Ссылки

- `.claude/hooks/docs-change-tracker.py` — базовый hook для расширения
- `.kb-lint.toml` — конфиг (новый файл, создаётся в задаче `tasks.md`)
- `shared/task_master.py` — `add_task()` для hook-todos

---

## ## MODIFIED REQ-3: docs-change-enforcer.py Stop-check для drafts

**Файл:** `.claude/hooks/docs-change-enforcer.py`
**Было:** Stop hook, блокирует если код изменён без обновления docs (50+ mappings)
**Стало:** дополнительная проверка pending drafts в `docs/wiki/drafts/`

### Новая логика

При Stop hook срабатывании:
1. Существующие проверки `CODE_TO_DOMAIN` (UNMAPPED блокировки)
2. **Новое:** Сканировать `docs/wiki/drafts/*.md`
3. Для каждого draft: age = `time.time() - file.stat().st_mtime` (в часах)
4. Если есть draft старше threshold (default 48h, настраивается через `WIKI_DRAFT_MAX_AGE_HOURS`):
   - **НЕ блокировать** (advisory only)
   - Добавить `systemMessage` с списком stale drafts
   - Предложить: `review → merge to docs/wiki/` или `rm stale drafts`

### Сценарий 1: Stale draft warning

**Given** файл `docs/wiki/drafts/old-pattern.md` с mtime = now - 72h
**And** `WIKI_DRAFT_MAX_AGE_HOURS=48`
**When** Stop hook срабатывает
**Then** enforcer не блокирует (advisory)
**And** systemMessage содержит `[WIKI-DRAFT-WARN] 1 stale draft: old-pattern.md (72h old, threshold 48h)`
**And** подсказка: `Review or delete: docs/wiki/drafts/old-pattern.md`

### Сценарий 2: Свежие drafts — молча пропускается

**Given** 3 draft файла, все с mtime = now - 12h
**When** Stop hook срабатывает
**Then** enforcer проходит без сообщений о drafts
**And** выполняет существующие `CODE_TO_DOMAIN` проверки

### Граничные условия

- `docs/wiki/drafts/` не существует → skip (не ошибка)
- Пустая директория → skip
- Все drafts свежие → silent
- Env var `WIKI_DRAFT_MAX_AGE_HOURS` не установлена → default 48
- Файл с mtime в будущем (clock skew) → treat as age=0, skip
- `.wiki-draft-ignore` файл (если есть) → исключить перечисленные паттерны из проверки

### Ссылки

- `.claude/hooks/docs-change-enforcer.py` — базовый hook
- `openspec/profiles/python-framework.yaml` — определение wiki rules (справочно)

---

## ## ADDED REQ-4: EventBus интеграция с типами событий

**Файл:** `src/memory/librarian/wiki_promoter.py` (часть REQ-1)

`WikiPromoter` публикует 3 типа событий через существующий `EventBus` (`src/memory/infrastructure/event_bus.py:138`):

| Event type | Когда | Payload |
|-----------|-------|---------|
| `wiki.draft.created` | Draft создан в `docs/wiki/drafts/` | `{pattern_id, draft_path, confidence, usage_count, timestamp}` |
| `wiki.promoted` | Draft смержён в `docs/wiki/` (ручная промоция, отдельный flow) | `{draft_path, final_path, promoted_at}` |
| `wiki.conflict.detected` | Дубликат найден при промоции | `{pattern_id, existing_wiki_id, similarity, strategy, timestamp}` |

События сохраняются в `EventStore` (`src/memory/infrastructure/event_store.py`) автоматически — event sourcing позволяет replay истории промоций через `EventStore.replay()` для аудита.

### Сценарий 1: Draft creation event

**Given** `WikiPromoter.try_promote_pattern("zai-providers")` успешно создал draft
**When** `await event_bus.publish("wiki.draft.created", payload, source="wiki_promoter")` вызывается
**Then** событие сохранено в `EventStore` (hot buffer + cold SQLite)
**And** все subscribers на `wiki.draft.created` получают событие асинхронно
**And** Phase 6.5 `IncrementalGraphUpdater` (если subscribed) может реэкспортировать affected entities

### Сценарий 2: Conflict event с replay capability

**Given** за неделю произошло 15 conflict событий
**When** администратор запускает `await event_store.replay(event_type="wiki.conflict.detected", since=<week_ago>)`
**Then** возвращаются все 15 событий для анализа паттернов конфликтов
**And** можно корректировать `dedup_similarity_threshold` на основе data

### Граничные условия

- `EventBus` не запущен → log warning, promotion продолжается без events
- Payload слишком большой (>10KB) → truncate + warning
- Cold SQLite storage недоступна → события идут только в hot buffer, warning
- Нет subscribers → события всё равно публикуются (для audit log)

### Ссылки

- `src/memory/infrastructure/event_bus.py:64` — `EventBus` class
- `src/memory/infrastructure/event_bus.py:138` — `publish(event_type, data, source)`
- `src/memory/infrastructure/event_store.py:37` — `EventStore` с hot/cold storage
- `src/memory/infrastructure/event_store.py:132` — `replay()`

---

## ## ADDED REQ-5: pre-commit hook integration

**Файл:** `.pre-commit-config.yaml` (новый или расширение)

Добавление `kb-lint` и `markdownlint-cli2` как pre-commit hooks для автоматической проверки wiki файлов при коммите.

### Конфигурация

```yaml
# .pre-commit-config.yaml (добавление)

repos:
  - repo: local
    hooks:
      - id: kb-lint-wiki
        name: Knowledge Base Lint (wiki)
        entry: kb-lint --ci
        language: python
        types: [markdown]
        files: ^docs/wiki/.*\.md$
        additional_dependencies: [kb-lint]

      - id: markdownlint-wiki
        name: Markdownlint (wiki)
        entry: markdownlint-cli2
        language: node
        types: [markdown]
        files: ^docs/(wiki|architecture|roadmap)/.*\.md$
        additional_dependencies: [markdownlint-cli2@0.13]
```

### Сценарий 1: Блок коммита при broken link

**Given** developer добавил `[[invalid-page]]` в `docs/wiki/entities/qdrant.md`
**When** `git commit` запускается
**Then** `kb-lint-wiki` hook fail с exit 1
**And** коммит блокируется
**And** сообщение содержит: `Broken wiki-link: [[invalid-page]] at docs/wiki/entities/qdrant.md:42`

### Сценарий 2: Markdown formatting issue

**Given** файл `docs/wiki/concepts/memory-layers.md` использует `**bold**` вместо `## Heading`
**When** `git commit` запускается
**Then** `markdownlint-wiki` fail с MD001 rule violation
**And** коммит блокируется с hint на правильный синтаксис

### Граничные условия

- `kb-lint` не установлен глобально → pre-commit создаёт isolated venv (`additional_dependencies`)
- Изменён файл вне `docs/wiki/` → `kb-lint-wiki` skipped (files filter)
- Изменения в `docs/wiki/drafts/` → применяются ослабленные правила (`.kb-lint-drafts.toml`)
- Hook timeout (>30s) → fail с error
- `--no-verify` флаг → обход (standard git behavior, не блокируем)

### Ссылки

- `.pre-commit-config.yaml` — файл для расширения
- `kb-lint` pypi package — https://pypi.org/project/kb-lint/
- `markdownlint-cli2` npm package — https://github.com/DavidAnson/markdownlint-cli2

---

## Регрессия

Фаза 3 **НЕ ДОЛЖНА** ломать:

- [ ] Существующий `docs-change-tracker.py` — `CODE_TO_DOMAIN` маппинги (50+ правил) работают как раньше для файлов вне `docs/wiki/`
- [ ] Существующий `docs-change-enforcer.py` — UNMAPPED блокировки продолжают работать
- [ ] `SKIP_PATTERNS` уже включает `openspec/` (Phase 6.1) — spec файлы не триггерят UNMAPPED
- [ ] Существующие hooks не меняют timing (`PostToolUse` остаётся PostToolUse)
- [ ] Задачи в `hook-todos.json` продолжают работать через существующий `task_master`

## Новые тесты

```
tests/unit/memory/librarian/
  __init__.py
  test_wiki_promoter.py          — WikiPromoter unit tests с моками всех зависимостей
  test_promotion_config.py       — PromotionConfig validation

tests/integration/
  test_wiki_promotion_flow.py    — End-to-end: pattern в Qdrant → scan → draft created
  test_wiki_conflict_resolution.py — ConflictResolver integration в промоции
  test_wiki_events_replay.py     — EventBus publish + EventStore replay

tests/unit/hooks/
  test_docs_change_tracker_wiki.py — wiki extension, broken links, frontmatter
  test_docs_change_enforcer_drafts.py — stale drafts warning

tests/fixtures/wiki_samples/
  valid_pattern.md
  broken_links.md
  missing_frontmatter.md
  stale_draft.md
```

**Coverage target:** `wiki_promoter.py` ≥90%, hook extensions ≥85%.
