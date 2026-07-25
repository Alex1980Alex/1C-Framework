---
name: cc-docs
description: Семантический поиск по документации Claude Code (code.claude.com/docs) со свежестью (sitemap lastmod). CLI/SDK/hooks/subagents/settings/permissions/MCP/plugins.
allowed-tools:
  - Bash
---

Поиск по документации Claude Code. Запрос пользователя: $ARGUMENTS

Выполни (из корня репозитория, `.venv` python):
1. `.venv/Scripts/python.exe scripts/cc_docs_search.py search "$ARGUMENTS" --top 8` → топ-чанки (url + heading + snippet + score).
2. Синтезируй ответ из топ-результатов на языке пользователя, **с цитатами** `[code.claude.com/.../<page>]` после фактов.
3. Если 0 хитов ИЛИ вопрос про самое свежее («latest», новая фича): выполни `.venv/Scripts/python.exe scripts/cc_docs_search.py check` (доки обновляются); если изменилось → `.venv/Scripts/python.exe scripts/cc_docs_search.py index --incremental`, затем повтори поиск.

Документация Claude Code живая — при сомнении в актуальности сначала `check`. Индекс: Qdrant `cc_docs` (TEI Qwen3 4096d). Скилл: `cc-docs`.
