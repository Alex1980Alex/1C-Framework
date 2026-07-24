# ADR-056: Ретирмент src/bsl/mcp_server (устаревший vendored-близнец 1c_mcp py_server)

**Дата:** 2026-07-24
**Статус:** proposed
**Исследование:** [1c-bsl-tooling-ecosystem-2026.md](../cache/1c-bsl-tooling-ecosystem-2026.md) (раздел Verified 2026-07-24)

## Контекст

Аудит docs-coverage (ADR-054 контур) стабильно флагает `MCPProxy`/`OneCClient` из `src/bsl/mcp_server/` как doc-gaps. Глубокий разбор ценности модуля показал:

1. **Провенанс:** модуль перенесён миграцией PHASE_46 из старого фреймворка (`D:\1C-Enterprise_Framework\mcp-1c-server\`, ~март 2026). Файловая структура и имена классов (`config.py`, `onec_client.py`, `mcp_server.py`, `http_server.py`, `stdio_server.py`, класс `OneCClient`) идентичны `vladimir-kharin/1c_mcp` `src/py_server` - это один lineage [own, дифф].
2. **Расхождение:** upstream ушёл вперёд (дифф `mcp_server.py` 430 строк, `onec_client.py` 344 vs 318); наша копия получала только repo-wide sweep'ы (ruff/mypy/noqa) - **0 фичевых коммитов за всю жизнь** (15 коммитов, все авто/sweep) [exp, git log].
3. **Продакшн-путь другой:** `.mcp.json` `1c-mcp-crud` → `scripts/mcp_1c_stdio_launcher.py` → сабмодуль `external/1c_mcp` (upstream + локальные фичи B1 debug-worker, ADR-049). Докстринг лаунчера: «submodule stays pristine and syncable from upstream». Рантайм-вызывающих у `src/bsl/mcp_server` нет [exp, grep].
4. **Уникальная ценность уже извлечена:** OAuth 2.1 + PKCE вынесен в `src/shared/mcp_oauth` (Phase 12.3, openspec `2026-05-15-hermes-llm-wiki` oauth-extraction). В модуле остался thin compat-wrapper `auth/oauth2.py` + тест `tests/unit/test_bsl_oauth_wrapper.py` [exp].
5. **GitHub-экосистема жива** (gh api 2026-07-24): upstream `vladimir-kharin/1c_mcp` 466★/109 forks, пуш 2026-07-17, **license:null** (юр. риск редистрибуции); альтернативы - `feenlace/mcp-1c` (Go, 173★, MIT, пуш 2026-07-22), `FSerg/mcp-1c-v1` (161★, MIT, stale c 2025-08), каталог `Untru/1c-mcp` (132★), `SteelMorgan/mcp-bsl-lsp-bridge` (63★, Apache-2.0), `infaton/MCP35` (30★, MIT, 51 tool) [web].

## Решение (предложение)

Ретирмент `src/bsl/mcp_server/`:
- Удалить прокси-ядро (`main.py`, `mcp_server.py`, `onec_client.py`, `http_server.py`, `stdio_server.py`, `config.py`, `__main__.py`).
- Мигрировать `tests/unit/test_bsl_oauth_wrapper.py` на прямые импорты `src.shared.mcp_oauth` и удалить compat-wrapper `auth/oauth2.py` (либо, минимально, оставить wrapper до следующего рефакторинга).
- Обновить упоминания в доках: 16.5 (MCP-серверы для 1С), 28.1, 37.3/37.7 (OAuth-подсистема - хост-пример), 09.2.
- **НЕ трогать** `src/bsl/mcp_integration/1c_ext/` - живые исходники расширения 1С (mcp_APIBackend `/hs/mcp/`), задокументированы в 16.5:73, деплой по памяти `reference_1c_mcp_server_extension_deploy`.

Побочный эффект: doc-gaps `MCPProxy`/`OneCClient` исчезают из аудита корректным способом (код удалён, а не «задокументирован мёртвым»).

## Последствия

### Положительные
- −1560 LOC мёртвого кода; исчезает второй (расходящийся) экземпляр `OneCClient` в кодовой базе (сейчас их два: наш и сабмодульный - путаница при grep/навигации).
- Снижение юр. поверхности: наша копия унаследована от кода без LICENSE (upstream license:null).
- Аудит-баннер чистится честно; исчезает соблазн «документировать легаси».

### Отрицательные
- Потеря локального «референса» реализации MCP-прокси - смягчается git-историей и живым сабмодулем.
- Правка 4-5 doc-глав (механическая).

## Альтернативы

1. **Задокументировать как есть** - отклонено: документировали бы мёртвый расходящийся клон; аудит перестал бы шуметь по ложной причине.
2. **Синхронизировать с upstream** - отклонено: это дублирование сабмодуля `external/1c_mcp`, который уже synced + несёт локальные фичи.
3. **Оставить и добавить whitelist в аудит** - отклонено как основной путь (маскирует мёртвый код), но механизм known-gaps в `audit_docs_skills.py` полезен сам по себе (см. ADR-055 паттерн).
4. **Переехать на альтернативу (feenlace/mcp-1c Go и др.)** - не требуется: текущий стек (сабмодуль + launcher + extension) работает и активно развивается локально (B1 debug-worker).

## Связанные файлы

`src/bsl/mcp_server/**`, `src/shared/mcp_oauth/**`, `tests/unit/test_bsl_oauth_wrapper.py`,
`scripts/mcp_1c_stdio_launcher.py`, `external/1c_mcp` (сабмодуль), `src/bsl/mcp_integration/1c_ext/**` (не трогать),
`docs/framework documentation/3_ИНСТРУМЕНТЫ/3.2_ПОДКЛЮЧЕНИЕ_1С/16.5_MCP_серверы_для_1С.md`, `scripts/audit_docs_skills.py`.
