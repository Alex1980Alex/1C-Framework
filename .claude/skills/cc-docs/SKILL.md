# cc-docs — поиск по документации Claude Code (со свежестью)

Семантический поиск по **code.claude.com/docs** (CLI/SDK/хуки/субагенты/настройки/permissions/MCP/плагины/интеграции).
Индекс в Qdrant `cc_docs` (TEI Qwen3-8B 4096d, ~150 EN-страниц). **Доки живые/обновляются** → есть freshness.

## Когда использовать
Вопросы про Claude Code: возможности, флаги CLI, hooks, subagents, settings/env-vars, permission modes, Agent SDK (python/typescript), MCP, plugins, интеграции (Bedrock/Vertex/Slack/GitHub Actions), «что нового».

## Использование
- **Поиск:** `python scripts/cc_docs_search.py search "<вопрос>" [--top 8]` → топ-чанки (url+heading+snippet+score). Синтез ответа с цитатами [code.claude.com/.../page].
- **Свежесть:** `python scripts/cc_docs_search.py check` → сколько страниц обновилось/добавилось с последней индексации (по sitemap `<lastmod>`).
- **Обновить инкрементально:** `python scripts/cc_docs_search.py index --incremental` → ре-индекс ТОЛЬКО изменённых/новых (дёшево).
- **Полный ре-индекс:** `python scripts/cc_docs_search.py index` (idempotent, _pid=md5(url#idx)).

## Freshness — важно (доки обновляются)
sitemap несёт `<lastmod>` на каждую страницу. **Перед ответом, чувствительным к актуальности (новые фичи, «latest»), сначала `check`; если изменилось → `index --incremental`, затем поиск.** Каденция по умолчанию: `check` раз в день/неделю или при сомнении.

## Конвейер
sitemap(EN)+lastmod → urllib (публичные доки, без браузера) → trafilatura→markdown → chunk(## +1500) → TEI(4096d, batch≤32) → Qdrant `cc_docs` (Cosine, lastmod в payload). search: query+Qwen3 query-instruct → Qdrant top-k.

## Связано
slash-команда `/cc-docs`; reuse TEI :8080 + Qdrant :6333 + trafilatura; reversible (удалить коллекцию `cc_docs` = откат). Кеш [[cc-docs-search-2026]]. НЕ путать с `/pdf-search` (тот по локальным PDF/BSL/wiki/skill коллекциям).