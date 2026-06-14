# ADR-017: Generic 4-stage SDLC Pipeline — слэш-команды + state-файл (артефакт-на-этап)

**Дата:** 2026-06-13
**Статус:** accepted (MVP реализован+smoke-verified 2026-06-13)
**Исследование:** ../cache/sdlc-pipeline-orchestration-patterns.md
**Шаг SDLC:** сквозной (оркестрация всех 4 шагов)

## Контекст
Нужен **домен-агностичный** пайплайн разработки: Планирование архитектуры → Дизайн реализации →
Кодирование → Тестирование, где **каждый этап производит артефакт**, а следующий этап начинается
с *(артефакт предыдущего + работа этапа)*. 1С-цепочка (`/analyze-1c-task → …`) — отдельная доменная
реализация со своей спецификой, её не трогаем. Все строительные блоки уже есть в репозитории
(`.run-state.json`, `approval-gate.py`, ADR, 4-step SDLC) — задача = обобщить их, не изобретать.

## Решение
**Реализация №1: тонкий оркестратор-каркас = слэш-команды + state-файл.** [own]
- **Артефакты:** `pipeline/<task>/0N-*.md` (01-architecture, 02-design, 03-implementation, 04-testing).
- **Состояние:** `pipeline/<task>/.pipeline-state.json` + указатель `pipeline/CURRENT`
  ([`shared/pipeline_state.py`](../../../../.claude/hooks/shared/pipeline_state.py), stdlib-only,
  importable API + CLI `init|done|approve|status|gate`). Паттерн заимствован из `.run-state.json`. [exp]
- **Этапы = команды** [`pl-plan`](../../../../.claude/commands/pl-plan.md) /
  [`pl-design`](../../../../.claude/commands/pl-design.md) /
  [`pl-code`](../../../../.claude/commands/pl-code.md) /
  [`pl-test`](../../../../.claude/commands/pl-test.md): каждая читает прошлый артефакт + state,
  **делегирует существующему скиллу** (architecture-research / дизайн-доку / implementer / code-verify),
  пишет новый артефакт, продвигает state. Реальную работу делают существующие скиллы — каркас не дублирует.
- **Гейт (из №4 OpenSpec):** единственный **hard-гейт** перед Этапом 3 (Кодирование) — дизайн (02) должен быть
  `done` + `approved` человеком. Хук [`pipeline-gate.py`](../../../../.claude/hooks/pipeline-gate.py)
  (UserPromptSubmit) детектит `pl-code` и блокирует (`decision:block`) до одобрения — аналог
  `approval-gate.py`, но над `.pipeline-state.json`. Переходы `pl-design`/`pl-test` — advisory (не блок).
- **№3 Workflow как опция (позже):** `/pl-run-all` — Workflow-скрипт, гоняющий те же 4 этапа автономно,
  **переиспользуя те же команды и формат артефактов**. Каркас один, режима два (ручной/авто).

## Последствия
**Положительные:** артефакт-ревью между этапами (естественный чекпоинт); resume с любого этапа;
минимальный риск (реверс = удалить 4 команды + hook + helper); каркас домен-агностичен; не дублирует
существующие скиллы, а оркестрирует их; non-breaking (гейт early-return для не-pl-* промптов).
**Отрицательные:** ручной драйв (человек запускает каждый этап) — компенсируется будущим `/pl-run-all`;
артефакты в `pipeline/` нужно вносить в SKIP_PATTERNS docs-enforcer (сделано).

## Альтернативы
- **№3 Workflow как основа** — отклонён: гонит все 4 этапа за один заход → теряется чекпоинт ревью
  артефакта между этапами; дорого по токенам; требует явного opt-in. Оставлен опцией поверх каркаса.
- **№4 Обобщить OpenSpec** — отклонён как основа: change/spec-ориентирован (delta-specs, capabilities,
  привязка к JIRA в части хуков); гнуть его в generic 4-этапную форму дороже, чем 4 тонкие команды.
  Его approval-gate-паттерн **заимствован** в гейт перед кодированием.
- **№2 Хук-gate как отдельный механизм** — поглощён: гейт реализован хуком, но как часть каркаса №1.

## Связанные файлы
`.claude/hooks/shared/pipeline_state.py`, `.claude/hooks/pipeline-gate.py`,
`.claude/commands/pl-{plan,design,code,test}.md`, `.claude/settings.json` (UPS-цепочка),
`.claude/hooks/docs-change-enforcer.py` (SKIP_PATTERNS += `pipeline/`), `CLAUDE.md` (Hooks Infrastructure).
