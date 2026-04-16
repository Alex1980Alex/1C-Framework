# BSL LS Recon Plan (Phase 0b)

Краткосрочный план разведки (reconnaissance) для оценки возможности прямого использования [bsl-language-server](https://github.com/1c-syntax/bsl-language-server) в рамках гибридного подхода (Сценарий W Hybrid Extract-only). Цель — за 4-6 часов проверить, способен ли BSL LS работать standalone через stdio в качестве subprocess, и корректно ли он обрабатывает запрос `textDocument/rename`. Результаты лягут в основу архитектурного решения Serena Audit (раздел §5.1) и определят стратегию реализации Phase 3.

Полный контекст доступен в документе: [260414_Serena Audit углублённый анализ эффективности](260414_Serena%20Audit%20углублённый%20анализ%20эффективности.md).

## Scenarios

| Исход | Описание | Следующие шаги |
| :--- | :--- | :--- |
| **Scenario 1** | LS стартует, `rename` отрабатывает корректно (включая базовый cross-file поиск) | Переход к **Phase 3 Variant A**. Оценка трудозатрат: 2-3 дня на реализацию полноценного BSL LS backend. |
| **Scenario 2** | LS стартует, но `rename` падает, возвращает неполные данные или неточен | **Variant A** ограничивается только in-file переименованием. Для cross-file рефакторинга реализуется **Variant B** (построение графа зависимостей в Neo4j). |
| **Scenario 3** | LS не стартует standalone, критические ошибки инициализации или падения | **Variant A** полностью отменяется. Ядром плана становится исключительно **Variant B** (Neo4j граф). |

## Чеклист (4-6 часов)

### Этап 1. Сборка окружения (30 мин)
- [ ] Скачать JAR-файл с релиза [v0.24.0-rc.3](https://github.com/1c-syntax/bsl-language-server/releases/tag/v0.24.0-rc.3)
- [ ] Разместить исполняемый файл в директории `tools/bsl-ls/`
- [ ] Проверить наличие и версию Java (требуется Java 21, команда `java -version`)
- [ ] Создать структуру директорий `tools/bsl-ls/test-workspace/`
- [ ] Создать 2-3 тестовых файла `.bsl` (например, `CommonModule.bsl` и `Catalogs/ManagerModule.bsl`) с процедурами и функциями

### Этап 2. Ручной запуск LS (1 час)
- [ ] Запустить процесс: `java -jar bsl-language-server-0.24.0-rc.3.jar --lsp` (stdio transport)
- [ ] Убедиться, что процесс остается живым и не падает после инициализации
- [ ] Отправить базовый LSP запрос `initialize`
- [ ] Зафиксировать ответ сервера (capabilities) в файле `recon-log-01-initialize.txt`

### Этап 3. LSP методы (1.5-2 часа)
- [ ] Реализовать отправку `textDocument/didOpen` для тестового файла
- [ ] Вызвать `textDocument/documentSymbol` для проверки парсинга AST
- [ ] Вызвать `textDocument/references` для поиска локальных использований
- [ ] Вызвать `textDocument/prepareRename` для проверки валидности позиции
- [ ] Вызвать `textDocument/rename` и получить `WorkspaceEdit`
- [ ] Применить `WorkspaceEdit` вручную, проанализировать корректность изменений

### Этап 4. Cross-file refactoring (1 час)
- [ ] Подготовить 2 модуля: экспортный (источник) и вызывающий (потребитель)
- [ ] Выполнить `rename` экспортного метода в исходном модуле
- [ ] Проверить, нашёл ли LS вызов этой функции в другом файле (cross-file)
- [ ] Если cross-file поиск не работает, задокументировать это как архитектурное ограничение (Variant A = in-file only)

### Этап 5. Разбор issues (30 мин - 1 ч)
- [ ] Изучить [GitHub issue #802](https://github.com/1c-syntax/bsl-language-server/issues/802)
- [ ] Изучить [GitHub issue #798](https://github.com/1c-syntax/bsl-language-server/issues/798)
- [ ] Изучить [GitHub issue #792](https://github.com/1c-syntax/bsl-language-server/issues/792)
- [ ] Зафиксировать актуальные ограничения LS и статус их исправлений в версии v0.24.0-rc.3

### Этап 6. Артефакт (30 мин)
- [ ] Сформировать итоговый документ `docs/roadmap/bsl-ls-recon-results.md`
- [ ] Указать итоговый Scenario (1, 2 или 3)
- [ ] Включить логи ключевых ошибок (если есть)
- [ ] Внести метрики: cold start time, memory consumption (RSS), время выполнения rename

## Минимальный Python LSP клиент

Одноразовый скрипт для автоматизации этапов 2-4. Реализует протокол LSP через subprocess и stdio с правильным `Content-Length` framing.

```python
import subprocess
import json

def write_request(proc, request_dict):
    content = json.dumps(request_dict)
    header = f"Content-Length: {len(content)}\r\n\r\n"
    proc.stdin.write(header.encode('utf-8'))
    proc.stdin.write(content.encode('utf-8'))
    proc.stdin.flush()

def read_response(proc):
    length = 0
    while True:
        line = proc.stdout.readline().decode('utf-8')
        if line.startswith("Content-Length:"):
            length = int(line.split(":")[1].strip())
        if line == "\r\n":
            break
    body = proc.stdout.read(length).decode('utf-8')
    return json.loads(body)

proc = subprocess.Popen(
    ["java", "-jar", "tools/bsl-ls/bsl-language-server-0.24.0-rc.3.jar", "--lsp"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

init_request = {
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "processId": None,
        "rootUri": "file:///tools/bsl-ls/test-workspace",
        "capabilities": {},
    },
}
write_request(proc, init_request)
print(read_response(proc))
```

## Выход

По завершении Phase 0b Recon необходимо выполнить следующие действия:
- [ ] Создать и сохранить `docs/roadmap/bsl-ls-recon-results.md` с заполненными метриками и выводами.
- [ ] Обновить статус в основном документе: Serena Audit §5.1 Phase 0b = `DONE`.
- [ ] Принять формальное решение по архитектуре Phase 3 на основе выявленного Scenario (утвердить Variant A, гибрид A+B, или Variant B only).
