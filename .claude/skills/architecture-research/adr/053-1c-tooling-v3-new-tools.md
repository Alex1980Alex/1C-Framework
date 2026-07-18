# ADR-053: В3 новые 1С-инструменты — bsl-lsp (adopt), formsserver (adopt-lazy), test-post (port)

- **Статус:** accepted
- **Дата:** 2026-07-18
- **Исследование:** [`1c-tooling-github-2026`](../cache/1c-tooling-github-2026.md) (сканы + WebFetch README 2026-07-18).
- **Контекст-источник:** roadmap [260718_1C_TOOLING_AUDIT](../../../../docs/roadmap/260718_ROADMAP_1C_TOOLING_AUDIT.md) этап В3 (§3 GitHub-кандидаты).

## Контекст

Аудит 1С-tooling (§3) выделил 3 внешних кандидата на внедрение для качества 1С-задач. В3 —
решение по каждому после research (WebFetch README). Ограничения исполнителя: `/plugin`-команды
запускает пользователь (не агент); клонирование+`pip install -e` стороннего репо = supply-chain
действие (осторожно). Поэтому решения разнесены по механизму внедрения.

## Решение

### 1. `1c-syntax/claude-code-bsl-lsp` — **ADOPT (user-gated install)**

Claude Code **плагин**: на старте сессии авто-скачивает нативный бинарь BSL Language Server и
поднимает LSP для `.bsl`/`.os` (диагностики, quick-fix, форматирование, go-to-def/references).

- **Почему ADOPT** (несмотря на общий SKIP плагин-маркетплейса ADR-013 N6): это **узкий,
  высокоценный LSP-плагин**, а не «экосистема маркетплейса». Он НЕ добавляет конкурирующих
  хуков (N6-конфликт был про хуки), а даёт диагностику BSL **в момент правки — ДО Sonar-скана**
  (закрывает W2: edt-search 12с + ловит ошибки до SQ-дельты). LSP ортогонален нашей hook-архитектуре.
- **Механизм**: ставит **пользователь** (агент не запускает slash-команды):
  `/plugin marketplace add 1c-syntax/claude-code-bsl-lsp` → `/plugin install bsl-language-server@bsl-language-server`.
- **Осторожно**: авто-download+auto-update бинаря на старте (supply-chain + cold-start); бинарь
  нативный (Win/mac/Linux). Реверс: `/plugin uninstall`.
- **Не дублировать** `bsl_lint --format` (наш селективный формат остаётся, [[feedback-bsl-batch-edit-format-hook]]).

### 2. `Desko77/1c-formsserver` — **ADOPT в lazy-mcp (on-demand)**

Python MCP-сервер (fastmcp), 18 тулов: `convert_form` между 3 форматами (Configurator `logform` /
Managed / EDT `form:Form`), `validate_form`/`validate_form_edt`, `generate_form*`, `search_form_examples`,
`form_screenshot`. **Работает STANDALONE на XML-файлах — живая ИБ НЕ нужна** (EDT-интеграция опц.,
`EDT_ENABLED=false` по умолчанию). stdio ИЛИ HTTP (:8011).

- **Почему ADOPT**: прямо закрывает W2-боль форм — мутации/конверсия форм у нас только через
  codepilot1c, EDT-MCP не умеет, `.mxlx` не компилится. Конверсия logform↔EDT standalone —
  недостающее звено. Standalone = дёшево поднять и проверить на реальном файле формы.
- **Механизм — lazy-mcp on-demand** (не в тяжёлый `.mcp.json`, паттерн 27 on-demand серверов
  `infra/lazy-mcp/`): клон + `pip install -e .` (или `docker compose up`) + запись в lazy-каталог;
  спавнится по требованию при форм-задаче. **Install-рецепт задокументирован**, фактический клон —
  при первой форм-задаче (supply-chain: сторонний Python-код исполняется → осознанный opt-in).
- **EVAL-критерий приёмки** (при первом использовании): `convert_form` logform↔EDT на реальной форме
  из задач round-trip без потерь → тогда постоянная прописка в lazy-каталог; иначе skip с фиксацией.

### 3. Приём «test-post в откатываемой транзакции» (`skiddgoddamn/1c-mcp`) — **PORT (сделано)**

Не тул, а **приём**: провести реальный документ внутри транзакции → собрать ошибки →
`ОтменитьТранзакцию()` (всегда). Live-проверка логики ПРОВЕДЕНИЯ на реальных данных БЕЗ порчи базы
и без шага очистки. **Портирован** в `implement-1c-task` Этап 6 (references/stage-details.md) как
безопасная альтернатива «провести→проверить→очистить» (усиление ADR-050 live-данных). ⚠ Побочки вне
транзакции БД (HTTP-сервисы, журнал регистрации) откатом не отменяются.

## Последствия

- **+**: BSL-диагностика в редакторе до Sonar (W2); конверсия форм standalone (W2); безопасная
  live-проверка проведения (ADR-050). Все три — реверсивны, opt-in.
- **−**: bsl-lsp авто-download бинаря (supply-chain/cold-start) — принят как узкий高-value; formsserver
  клон+pip стороннего кода — gated на первую форм-задачу; test-post не покрывает побочки вне БД-транзакции.
- **Реверс**: bsl-lsp `/plugin uninstall`; formsserver — убрать lazy-запись + удалить клон; test-post — снять абзац из references.

## Альтернативы (отклонены)

- **feenlace/mcp-1c** (eng=163) — SKIP: функционально дубль `1c-mcp-crud` (10 tools vs наш стек);
  EVAL-LOW не оправдал держать вечный eval.
- **infaton/MCP35 / onec-odata-mcp / RCS-kz** — SKIP (ERP-твины / OData-дубль / платный SaaS).
- **bsl-lsp в основной `.mcp.json` вместо плагина** — невозможно: это Claude Code plugin (LSP-механизм), не MCP-сервер.

## Связанные файлы

- `implement-1c-task/references/stage-details.md` (test-post), `implement-1c-task/SKILL.md` (пойнтер),
  кеш `1c-tooling-github-2026.md`, roadmap 260718_1C_TOOLING_AUDIT §3/§4.5-В3.
