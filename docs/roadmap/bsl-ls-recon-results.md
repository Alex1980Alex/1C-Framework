# BSL Language Server: Recon Results (Phase 0b)

Связанные документы: [bsl-ls-recon-plan.md](bsl-ls-recon-plan.md) | [260414_Serena Audit углублённый анализ эффективности.md](260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md)

## Сводка

По результатам Phase 0b (Hybrid Extract-only) подтверждён **Scenario 2**: BSL Language Server стартует и успешно обрабатывает in-file операции (символы, локальный rename, диагностика), но не способен выполнять cross-file поиск и переименование. Запросы `textDocument/references` и `textDocument/rename` для экспортных функций ограничиваются пределами одного файла.

Добавление метаданных `Configuration.xml` и `.mdo` не активировало workspace-wide индексацию. Архитектура BSL LS является «per-document»: сервер анализирует исключительно те файлы, которые клиент явно открыл через `textDocument/didOpen`. Это подтверждает изначальную гипотезу routing matrix из Serena Audit §4.6: LSP способен покрывать только локальные сущности (A), в то время как кросс-модульные вызовы (B) требуют реализации через Neo4j граф (Variant B).

## Окружение

| Параметр | Значение |
| :--- | :--- |
| **Платформа** | Windows 11, Git Bash |
| **Java** | OpenJDK 17.0.13 Zulu (запуск успешен, несмотря на требование плана Java 21) |
| **BSL LS JAR** | v0.22.0 (94 MB), существующий в репо (план предполагал v0.24.0-rc.3) |
| **Расположение JAR** | `tools/bsl-ls/bsl-language-server.jar` |
| **Test workspace** | `tools/bsl-ls/test-workspace/` |

## Метрики

| Метрика | Значение |
| :--- | :--- |
| **Cold start (run 1)** | 4798 ms |
| **Cold start (run 2)** | 4021 ms (с добавлением `Configuration.xml`) |
| **stderr** | Пусто (старт без ошибок) |
| **Timeout LSP запросов** | Все уложились в 30s |
| **RSS памяти** | Не замерялся, ориентировочно ~500 MB по профилю Java LS данного класса |

## Результаты LSP запросов

| # | Запрос | Цель | Статус | Результат / Вывод |
| :--- | :--- | :--- | :---: | :--- |
| 1 | `textDocument/documentSymbol` | `ТестоваяУтилита/Module.bsl` | OK | Распознаны 3 функции, корректные `ranges` и `selectionRanges` |
| 2 | `textDocument/references` | Экспортная функция `ПолучитьПараметр` (includeDeclaration=true) | FAIL | `result: []` — пустой массив даже для in-file declaration |
| 3 | `textDocument/prepareRename` | Экспортная функция `ПолучитьПараметр` | OK | Диапазон идентификатора (line 0, char 8-24) |
| 4 | `textDocument/rename` | Экспортная функция `ПолучитьПараметр` → `ПолучитьПараметрНовый` | WARN | WorkspaceEdit содержит **только 1 edit** в файле декларации. Вызов `ТестоваяУтилита.ПолучитьПараметр("ключ")` в другом файле проигнорирован. Cross-file rename НЕ работает |
| 5 | `textDocument/prepareRename` | Локальная функция `ПолучитьЗначениеПоУмолчанию` | OK | Диапазон определён |
| 6 | `textDocument/rename` | Локальная функция `ПолучитьЗначениеПоУмолчанию` → `ПолучитьДефолт` | OK | 2 edits в одном файле (декларация + call-site). In-file rename работает |
| 7 | Повтор полного прогона (run 2) | С добавлением `Configuration.xml` + `.mdo` | WARN | Результаты идентичны run 1. Метаданные не включили cross-file поиск |

## Анализ issues #802 / #798 / #792

Проверка GitHub issues из Serena Audit §4.9.4 / список «known BSL integration issues»:

- [#802 «База обработчиков событий по модулям»](https://github.com/1c-syntax/bsl-language-server/issues/802) — OPEN, enhancement для `DiagnosticScope`. Не относится к cross-file rename.
- [#798 «New diagnostic: FormDataToValue method call»](https://github.com/1c-syntax/bsl-language-server/issues/798) — MERGED, про диагностику. Не относится к rename.
- [#792 «Отбор замечаний по подсистемам»](https://github.com/1c-syntax/bsl-language-server/issues/792) — OPEN, про фильтр замечаний. Не относится к rename.

**Вывод:** Указанные в аудите issues не релевантны проблематике cross-file поиска и переименования. Они были восприняты как общий сигнал о состоянии интеграции BSL LS, однако прямых баг-репортов или roadmap-задач по workspace-wide индексации в них нет. Real cause найден через эксперимент, а не через issues.

## Архитектурный вывод

BSL Language Server реализует LSP и работает standalone через stdio без зависимости от Serena/Eclipse. Парсер BSL работает корректно (подтверждено приходом `textDocument/publishDiagnostics` с замечанием `DeprecatedMessage` на метод `Сообщить`).

Архитектура сервера — **«per-document»**: он анализирует только те файлы, которые клиент открыл через `textDocument/didOpen`. Автоматического индексирования всего workspace не происходит. Для cross-module references возможны следующие варианты преодоления:

1. **Клиент открывает ВСЕ `.bsl` файлы workspace заранее.** Неразумно: десятки тысяч файлов × ~500 MB LS = RAM exhaustion + деградация производительности.
2. **Реализация `preloadAllDocuments` в LSP клиенте с batch didOpen.** Частичный workaround, расходующий ресурсы. Не решает проблему для больших конфигураций.
3. **Ожидание workspace indexing в самом BSL LS.** Отсутствует в публичном roadmap. Полагаться на стороннюю фичу нецелесообразно.

Ни один вариант не даёт cross-file rename за разумную цену. Variant B (Neo4j граф `bsl-semantic-search`) остаётся единственным разумным путём для cross-module операций.

## Решение по Phase 3 (Scenario 2)

Подтверждена гипотеза routing matrix (Serena Audit §4.6). LSP Backend покрывает только in-file symbol kinds (`local_var`, `parameter`, `module_private_proc`). Кросс-модульные вызовы (`module_export_proc`, `manager_method`, `object_method`) должны обрабатываться через Neo4j граф (Variant B).

**Рекомендация по Variant A:**

- **Реализовать** строго для in-file scenarios. Protocol-based контракт из §4.8 audit остаётся валидным: `LspBackend.can_handle(kind in {local_var, parameter, module_private_proc})`.
- **Сроки:** снижены до ~1-1.5 дней (было 2-3).
- **Urgency:** сниженная. Основная ценность идёт от Variant B.
- **Persistent subprocess:** cold start 4s приемлем только для long-running процесса. BSL LS должен жить в MCP-сервере как persistent subprocess с health checks и circuit breaker.

**Корректировка routing matrix (§4.6 Serena Audit):**

| Symbol Kind | Было | После recon | Комментарий |
|---|---|---|---|
| `local_var` | A (BSL LS) | A ✅ | Подтверждено |
| `parameter` | A + B verify | A ✅ | Параметр не cross-file, B verify излишен |
| `module_private_proc` | A | A ✅ | Подтверждено на локальной функции |
| `module_export_proc` | A + B parallel | **B only** | A не нашёл вызовы в другом модуле даже с Configuration.xml |
| `manager_method` | B + EDT verify | B + EDT verify | Не менялось |
| `object_method` | B + EDT verify | B + EDT verify | Не менялось |
| `form_handler` | B (std names) | B | Не менялось |

## Артефакты recon

- `tools/bsl-ls/recon-logs-run1/` — логи первого прогона (без `Configuration.xml`)
- `tools/bsl-ls/recon-logs/` — логи второго прогона (с `Configuration.xml` + `.mdo`)
- `tools/bsl-ls/lsp_recon.py` — Python-скрипт LSP клиента (~230 строк)
- `tools/bsl-ls/test-workspace/` — тестовый workspace: 2 CommonModule, `Configuration.xml`, `.mdo`

## Next steps

- [ ] Скачать и проверить BSL LS `v0.24.0-rc.3` на том же test-workspace — возможно cross-file рефакторинг улучшен. Сверить changelog. Если нет улучшений — routing matrix выше финальна.
- [ ] Обновить Serena Audit §5.1: Phase 0b = DONE, фиксировать `Scenario 2` и ссылку на этот документ.
- [ ] Обновить §4.6 audit (routing matrix) с корректировкой `module_export_proc` → **B only** вместо parallel A+B.
- [ ] Запустить Phase 1 (Tier 2 wrappers) и Phase 2 (Variant B core) в параллель — не ждать Phase 3.
- [ ] В спецификации `bsl-semantic-search` MCP-сервера заложить LSP subprocess lifecycle (spawn, health check, circuit breaker, reuse across requests).
