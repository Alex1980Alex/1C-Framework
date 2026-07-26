# fix-llm-rotation-model-routing — «не всегда переключается на нужную модель»

**Дата:** 2026-07-26 · **Мандат:** анализ llm-rotation + определение текущей модели и
логики переключения + переименование скилла «z.ai» + GitHub best practices + исправление.

## 1. План (диагноз по живым данным)

Три независимых корня жалобы:

| # | Корень | Доказательство |
|---|--------|----------------|
| R1 | **Per-server `timeout: 60000`** в [.mcp.json](../../.mcp.json) рвал вызов на 60с; по официальной doc env-vars per-server поле **сильнее** `MCP_TOOL_TIMEOUT` (наши 240000 игнорировались; у stdio нет per-request 60s таймера). При этом force_primary жевал primary 2×до-240с + backoff → фоллбэк в клиентском окне НЕДОСТИЖИМ: ротация не успевала ротировать | вызовы 2026-07-25/26 рвались ровно на 60с; последняя успешная запись лога — `response_time: 59.41` (впритык) |
| R2 | **Model-blind ротация**: `model` не влиял на выбор провайдера; фоллбэк перебирал ВСЕ модели провайдера → тихая подмена вплоть до ЭСКАЛАЦИИ на opus | живой лог: `provider=claude-cli-haiku, model=claude-opus-4-7` (attempt=3) |
| R3 | **Adaptive score РАНЬШЕ priority** в sort_key → sonnet-first подрывался скором; нормализация `max_latency=30с` давала CLI-спавну (25-150с) latency_score≈0 всегда | живые скоры на момент фикса: haiku 0.535 > sonnet 0.500 (default) |

Плюс наблюдаемость: llm-rotation — единственный активный сервер БЕЗ per-call лога
(N-P2.2 его пропустил), ошибки MCP-слоя возвращались неотличимой от успеха строкой,
completions-лог писался по ОТНОСИТЕЛЬНОМУ пути (в проде 120+ записей тестового мусора:
mock/test-provider/working). Имя скилла лгало: Z.AI удалён из ротации 2026-05-16.

**GitHub-скан** (ecosystem_scan ×1 + gh search по звёздам): litellm 54.7k⭐ / bifrost 6.8k⭐ —
приёмы: deadline propagation сверху вниз, model-group маппинг провайдеров, cooldown+CB,
приоритет как политика / скор как совет. Свежак 30-дн окна — нулевой engagement, не берём.

## 2. Дизайн

- **R1**: `.mcp.json` timeout 60000→**300000**; в `complete()` сквозной бюджет
  `total_budget_seconds=240` + `primary_budget_share=0.6` (deadline propagation: каждой
  попытке `min(tier_timeout, остаток фазы)`; остаток <8с → выход со сводкой). Бюджет <
  клиентского потолка ⇒ клиент всегда получает структурированный ответ, а не обрыв.
- **R2**: `resolve_model_for_provider(cfg, model)` — единый alias-резолв + совместимость;
  несовместимый провайдер скипается С ПРИЧИНОЙ (обе фазы); явный `model` не подменяется;
  `models` клод-провайдеров сужены до своего тира (анти-эскалация; явный opus — можно);
  в ответе `requested_model`/`substituted`; никто не способен → честная ошибка со сводкой.
- **R3**: sort_key `(healthy, priority, -adaptive, ...)` — приоритет = политика, скор =
  tie-breaker; `max_latency` 30→120.
- **Наблюдаемость**: тул `llm_route_explain` (порядок/skip-причины/CB/эффективная модель,
  без вызова LLM — прямой ответ на «какая модель и почему»); `mcp_call_log`-обвязка всех
  тулов; JSON-конверт ошибок `{ok:false}`; completions-лог абсолютный + env-override.
- **Rename**: скилл `z-ai-delegation` → **`llm-delegation`** (git mv, SKILL.md переписан
  под sonnet-first реальность); router-config bundle; delegation-classifier; тексты хуков
  `[Z.AI WRITE GUARD]`→`[LLM WRITE GUARD]`, `Skill('llm-delegation')`; CLAUDE.md; память.
  **Файлы хуков НЕ переименованы** (осознанно: регистрация в settings.json, имена классов
  в invocation-логах, тесты test_z_ai_guard_* — blast radius > ценности; тексты честные).

## 3. Реализация

[service.py](../../src/shared/llm_rotation/service.py) (резолвер, бюджет, sort_key,
анти-эскалация, сводка отказов, `explain_route`) · [config.py](../../src/shared/llm_rotation/config.py)
(+2 настройки) · [adaptive.py](../../src/shared/llm_rotation/adaptive.py) (max_latency) ·
[mcp.py](../../src/shared/llm_rotation/mcp.py) (route_explain, per-call лог, JSON-ошибки) ·
[.mcp.json](../../.mcp.json) (timeout) · скилл llm-delegation + llm-rotation SKILL.md ·
хуки (тексты) · router-config · CLAUDE.md · 2 файла памяти.

## 4. Тест

[test_llm_rotation_routing.py](../../tests/unit/test_llm_rotation_routing.py) — 11 unit:
резолвер (alias/чужие модели/канонический регистр — кейс поймал возврат пользовательского
регистра, исправлено в продукте), анти-эскалация DEFAULT_PROVIDERS, priority>adaptive,
adaptive-tie-break, скип несовместимого primary, честная ошибка без способных, фоллбэк без
подмены явной модели, бюджет капит primary и оставляет время фоллбэку (fake-clock), сводка
в ошибке бюджета, env-override лога. Существующие: 34 integration (изолированный лог) +
freshness 8 + guard-тесты 12 = **65 passed**. lint_skills 0 errors; router-GT lint OK.
Live: `explain_route()` на реальном сервисе показывает порядок и skip-причины (см. §18
ретро). ⚠ Рантайм MCP-сервера — после `/mcp reconnect`.
