> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Мониторинг

> Узнайте, как включить и настроить OpenTelemetry для Claude Code.

Claude Code поддерживает метрики и события OpenTelemetry (OTel) для мониторинга и наблюдаемости.

Все метрики представляют собой данные временных рядов, экспортируемые через стандартный протокол метрик OpenTelemetry, а события экспортируются через протокол логов/событий OpenTelemetry. Пользователь несет ответственность за обеспечение надлежащей конфигурации своих бэкендов метрик и логов, а также за то, чтобы гранулярность агрегации соответствовала требованиям мониторинга.

## Быстрый старт

Настройте OpenTelemetry с помощью переменных окружения:

```bash  theme={null}
# 1. Включить телеметрию
export CLAUDE_CODE_ENABLE_TELEMETRY=1

# 2. Выбрать экспортеры (оба опциональны - настройте только необходимое)
export OTEL_METRICS_EXPORTER=otlp       # Опции: otlp, prometheus, console
export OTEL_LOGS_EXPORTER=otlp          # Опции: otlp, console

# 3. Настроить OTLP endpoint (для OTLP экспортера)
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# 4. Установить аутентификацию (если требуется)
export OTEL_EXPORTER_OTLP_HEADERS="Authorization=Bearer your-token"

# 5. Для отладки: сократить интервалы экспорта
export OTEL_METRIC_EXPORT_INTERVAL=10000  # 10 секунд (по умолчанию: 60000ms)
export OTEL_LOGS_EXPORT_INTERVAL=5000     # 5 секунд (по умолчанию: 5000ms)

# 6. Запустить Claude Code
claude
```

<Note>
  Интервалы экспорта по умолчанию составляют 60 секунд для метрик и 5 секунд для логов. Во время настройки вы можете использовать более короткие интервалы для целей отладки. Не забудьте сбросить эти значения для использования в production.
</Note>

Для полного списка параметров конфигурации см. [спецификацию OpenTelemetry](https://github.com/open-telemetry/opentelemetry-specification/blob/main/specification/protocol/exporter.md#configuration-options).

## Конфигурация администратора

Администраторы могут настраивать параметры OpenTelemetry для всех пользователей через [файл управляемых параметров](/ru/settings#settings-files). Это позволяет централизованно управлять параметрами телеметрии в организации. Дополнительную информацию о том, как применяются параметры, см. в разделе [приоритет параметров](/ru/settings#settings-precedence).

Пример конфигурации управляемых параметров:

```json  theme={null}
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "otlp",
    "OTEL_LOGS_EXPORTER": "otlp",
    "OTEL_EXPORTER_OTLP_PROTOCOL": "grpc",
    "OTEL_EXPORTER_OTLP_ENDPOINT": "http://collector.company.com:4317",
    "OTEL_EXPORTER_OTLP_HEADERS": "Authorization=Bearer company-token"
  }
}
```

<Note>
  Управляемые параметры можно распространять через MDM (Mobile Device Management) или другие решения для управления устройствами. Переменные окружения, определенные в файле управляемых параметров, имеют высокий приоритет и не могут быть переопределены пользователями.
</Note>

## Детали конфигурации

### Общие переменные конфигурации

| Переменная окружения                            | Описание                                                                              | Примеры значений                     |
| ----------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------------------ |
| `CLAUDE_CODE_ENABLE_TELEMETRY`                  | Включает сбор телеметрии (обязательно)                                                | `1`                                  |
| `OTEL_METRICS_EXPORTER`                         | Тип экспортера метрик (разделенные запятыми)                                          | `console`, `otlp`, `prometheus`      |
| `OTEL_LOGS_EXPORTER`                            | Тип экспортера логов/событий (разделенные запятыми)                                   | `console`, `otlp`                    |
| `OTEL_EXPORTER_OTLP_PROTOCOL`                   | Протокол для OTLP экспортера (все сигналы)                                            | `grpc`, `http/json`, `http/protobuf` |
| `OTEL_EXPORTER_OTLP_ENDPOINT`                   | OTLP endpoint коллектора (все сигналы)                                                | `http://localhost:4317`              |
| `OTEL_EXPORTER_OTLP_METRICS_PROTOCOL`           | Протокол для метрик (переопределяет общий)                                            | `grpc`, `http/json`, `http/protobuf` |
| `OTEL_EXPORTER_OTLP_METRICS_ENDPOINT`           | OTLP endpoint метрик (переопределяет общий)                                           | `http://localhost:4318/v1/metrics`   |
| `OTEL_EXPORTER_OTLP_LOGS_PROTOCOL`              | Протокол для логов (переопределяет общий)                                             | `grpc`, `http/json`, `http/protobuf` |
| `OTEL_EXPORTER_OTLP_LOGS_ENDPOINT`              | OTLP endpoint логов (переопределяет общий)                                            | `http://localhost:4318/v1/logs`      |
| `OTEL_EXPORTER_OTLP_HEADERS`                    | Заголовки аутентификации для OTLP                                                     | `Authorization=Bearer token`         |
| `OTEL_EXPORTER_OTLP_METRICS_CLIENT_KEY`         | Ключ клиента для аутентификации mTLS                                                  | Путь к файлу ключа клиента           |
| `OTEL_EXPORTER_OTLP_METRICS_CLIENT_CERTIFICATE` | Сертификат клиента для аутентификации mTLS                                            | Путь к файлу сертификата клиента     |
| `OTEL_METRIC_EXPORT_INTERVAL`                   | Интервал экспорта в миллисекундах (по умолчанию: 60000)                               | `5000`, `60000`                      |
| `OTEL_LOGS_EXPORT_INTERVAL`                     | Интервал экспорта логов в миллисекундах (по умолчанию: 5000)                          | `1000`, `10000`                      |
| `OTEL_LOG_USER_PROMPTS`                         | Включить логирование содержимого пользовательских подсказок (по умолчанию: отключено) | `1` для включения                    |
| `CLAUDE_CODE_OTEL_HEADERS_HELPER_DEBOUNCE_MS`   | Интервал для обновления динамических заголовков (по умолчанию: 1740000ms / 29 минут)  | `900000`                             |

### Управление кардинальностью метрик

Следующие переменные окружения управляют тем, какие атрибуты включены в метрики для управления кардинальностью:

| Переменная окружения                | Описание                                      | Значение по умолчанию | Пример для отключения |
| ----------------------------------- | --------------------------------------------- | --------------------- | --------------------- |
| `OTEL_METRICS_INCLUDE_SESSION_ID`   | Включить атрибут session.id в метрики         | `true`                | `false`               |
| `OTEL_METRICS_INCLUDE_VERSION`      | Включить атрибут app.version в метрики        | `false`               | `true`                |
| `OTEL_METRICS_INCLUDE_ACCOUNT_UUID` | Включить атрибут user.account\_uuid в метрики | `true`                | `false`               |

Эти переменные помогают управлять кардинальностью метрик, что влияет на требования к хранилищу и производительность запросов в вашем бэкенде метрик. Более низкая кардинальность обычно означает лучшую производительность и более низкие затраты на хранилище, но менее детальные данные для анализа.

### Динамические заголовки

Для корпоративных сред, требующих динамической аутентификации, вы можете настроить скрипт для динамического создания заголовков:

#### Конфигурация параметров

Добавьте в ваш `.claude/settings.json`:

```json  theme={null}
{
  "otelHeadersHelper": "/bin/generate_opentelemetry_headers.sh"
}
```

#### Требования к скрипту

Скрипт должен выводить корректный JSON с парами строк ключ-значение, представляющими HTTP заголовки:

```bash  theme={null}
#!/bin/bash
# Пример: несколько заголовков
echo "{\"Authorization\": \"Bearer $(get-token.sh)\", \"X-API-Key\": \"$(get-api-key.sh)\"}"
```

#### Поведение обновления

Скрипт помощника заголовков запускается при запуске и периодически после этого для поддержки обновления токена. По умолчанию скрипт запускается каждые 29 минут. Настройте интервал с помощью переменной окружения `CLAUDE_CODE_OTEL_HEADERS_HELPER_DEBOUNCE_MS`.

### Поддержка многокомандной организации

Организации с несколькими командами или отделами могут добавлять пользовательские атрибуты для различия между разными группами, используя переменную окружения `OTEL_RESOURCE_ATTRIBUTES`:

```bash  theme={null}
# Добавить пользовательские атрибуты для идентификации команды
export OTEL_RESOURCE_ATTRIBUTES="department=engineering,team.id=platform,cost_center=eng-123"
```

Эти пользовательские атрибуты будут включены во все метрики и события, позволяя вам:

* Фильтровать метрики по команде или отделу
* Отслеживать затраты по центру затрат
* Создавать панели мониторинга для конкретных команд
* Настраивать оповещения для конкретных команд

<Warning>
  **Важные требования к форматированию для OTEL\_RESOURCE\_ATTRIBUTES:**

  Переменная окружения `OTEL_RESOURCE_ATTRIBUTES` следует [спецификации W3C Baggage](https://www.w3.org/TR/baggage/), которая имеет строгие требования к форматированию:

  * **Пробелы не допускаются**: Значения не могут содержать пробелы. Например, `user.organizationName=My Company` недопустимо
  * **Формат**: Должны быть пары ключ=значение, разделенные запятыми: `key1=value1,key2=value2`
  * **Допустимые символы**: Только символы US-ASCII, исключая управляющие символы, пробелы, двойные кавычки, запятые, точки с запятой и обратные слэши
  * **Специальные символы**: Символы вне допустимого диапазона должны быть закодированы в процентах

  **Примеры:**

  ```bash  theme={null}
  # ❌ Недопустимо - содержит пробелы
  export OTEL_RESOURCE_ATTRIBUTES="org.name=John's Organization"

  # ✅ Допустимо - используйте подчеркивания или camelCase вместо этого
  export OTEL_RESOURCE_ATTRIBUTES="org.name=Johns_Organization"
  export OTEL_RESOURCE_ATTRIBUTES="org.name=JohnsOrganization"

  # ✅ Допустимо - закодируйте специальные символы в процентах, если необходимо
  export OTEL_RESOURCE_ATTRIBUTES="org.name=John%27s%20Organization"
  ```

  Примечание: заключение значений в кавычки не экранирует пробелы. Например, `org.name="My Company"` приводит к буквальному значению `"My Company"` (с кавычками включены), а не `My Company`.
</Warning>

### Примеры конфигураций

```bash  theme={null}
# Отладка консоли (интервалы 1 секунда)
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=console
export OTEL_METRIC_EXPORT_INTERVAL=1000

# OTLP/gRPC
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Prometheus
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=prometheus

# Несколько экспортеров
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=console,otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=http/json

# Разные endpoints/бэкенды для метрик и логов
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_METRICS_PROTOCOL=http/protobuf
export OTEL_EXPORTER_OTLP_METRICS_ENDPOINT=http://metrics.company.com:4318
export OTEL_EXPORTER_OTLP_LOGS_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_LOGS_ENDPOINT=http://logs.company.com:4317

# Только метрики (без событий/логов)
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317

# Только события/логи (без метрик)
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_PROTOCOL=grpc
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4317
```

## Доступные метрики и события

### Стандартные атрибуты

Все метрики и события имеют эти стандартные атрибуты:

| Атрибут             | Описание                                                          | Управляется                                              |
| ------------------- | ----------------------------------------------------------------- | -------------------------------------------------------- |
| `session.id`        | Уникальный идентификатор сеанса                                   | `OTEL_METRICS_INCLUDE_SESSION_ID` (по умолчанию: true)   |
| `app.version`       | Текущая версия Claude Code                                        | `OTEL_METRICS_INCLUDE_VERSION` (по умолчанию: false)     |
| `organization.id`   | UUID организации (при аутентификации)                             | Всегда включается, когда доступно                        |
| `user.account_uuid` | UUID учетной записи (при аутентификации)                          | `OTEL_METRICS_INCLUDE_ACCOUNT_UUID` (по умолчанию: true) |
| `terminal.type`     | Тип терминала (например, `iTerm.app`, `vscode`, `cursor`, `tmux`) | Всегда включается при обнаружении                        |

### Метрики

Claude Code экспортирует следующие метрики:

| Имя метрики                           | Описание                                                        | Единица |
| ------------------------------------- | --------------------------------------------------------------- | ------- |
| `claude_code.session.count`           | Количество запущенных сеансов CLI                               | count   |
| `claude_code.lines_of_code.count`     | Количество строк кода, которые были изменены                    | count   |
| `claude_code.pull_request.count`      | Количество созданных pull request                               | count   |
| `claude_code.commit.count`            | Количество созданных git коммитов                               | count   |
| `claude_code.cost.usage`              | Стоимость сеанса Claude Code                                    | USD     |
| `claude_code.token.usage`             | Количество использованных токенов                               | tokens  |
| `claude_code.code_edit_tool.decision` | Количество решений о разрешении инструмента редактирования кода | count   |
| `claude_code.active_time.total`       | Общее активное время в секундах                                 | s       |

### Детали метрик

#### Счетчик сеансов

Увеличивается в начале каждого сеанса.

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)

#### Счетчик строк кода

Увеличивается при добавлении или удалении кода.

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `type`: (`"added"`, `"removed"`)

#### Счетчик pull request

Увеличивается при создании pull request через Claude Code.

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)

#### Счетчик коммитов

Увеличивается при создании git коммитов через Claude Code.

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)

#### Счетчик затрат

Увеличивается после каждого запроса API.

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `model`: Идентификатор модели (например, "claude-sonnet-4-5-20250929")

#### Счетчик токенов

Увеличивается после каждого запроса API.

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `type`: (`"input"`, `"output"`, `"cacheRead"`, `"cacheCreation"`)
* `model`: Идентификатор модели (например, "claude-sonnet-4-5-20250929")

#### Счетчик решений инструмента редактирования кода

Увеличивается, когда пользователь принимает или отклоняет использование инструмента Edit, Write или NotebookEdit.

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `tool`: Имя инструмента (`"Edit"`, `"Write"`, `"NotebookEdit"`)
* `decision`: Решение пользователя (`"accept"`, `"reject"`)
* `language`: Язык программирования отредактированного файла (например, `"TypeScript"`, `"Python"`, `"JavaScript"`, `"Markdown"`). Возвращает `"unknown"` для неузнанных расширений файлов.

#### Счетчик активного времени

Отслеживает фактическое время, потраченное на активное использование Claude Code (не время простоя). Эта метрика увеличивается во время взаимодействия пользователя, такого как ввод подсказок или получение ответов.

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)

### События

Claude Code экспортирует следующие события через логи/события OpenTelemetry (когда настроен `OTEL_LOGS_EXPORTER`):

#### Событие пользовательской подсказки

Логируется, когда пользователь отправляет подсказку.

**Имя события**: `claude_code.user_prompt`

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `event.name`: `"user_prompt"`
* `event.timestamp`: Временная метка ISO 8601
* `prompt_length`: Длина подсказки
* `prompt`: Содержимое подсказки (скрыто по умолчанию, включите с помощью `OTEL_LOG_USER_PROMPTS=1`)

#### Событие результата инструмента

Логируется, когда инструмент завершает выполнение.

**Имя события**: `claude_code.tool_result`

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `event.name`: `"tool_result"`
* `event.timestamp`: Временная метка ISO 8601
* `tool_name`: Имя инструмента
* `success`: `"true"` или `"false"`
* `duration_ms`: Время выполнения в миллисекундах
* `error`: Сообщение об ошибке (если не удалось)
* `decision`: Либо `"accept"`, либо `"reject"`
* `source`: Источник решения - `"config"`, `"user_permanent"`, `"user_temporary"`, `"user_abort"` или `"user_reject"`
* `tool_parameters`: JSON строка, содержащая параметры, специфичные для инструмента (когда доступно)
  * Для инструмента Bash: включает `bash_command`, `full_command`, `timeout`, `description`, `sandbox`

#### Событие запроса API

Логируется для каждого запроса API к Claude.

**Имя события**: `claude_code.api_request`

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `event.name`: `"api_request"`
* `event.timestamp`: Временная метка ISO 8601
* `model`: Используемая модель (например, "claude-sonnet-4-5-20250929")
* `cost_usd`: Приблизительная стоимость в USD
* `duration_ms`: Длительность запроса в миллисекундах
* `input_tokens`: Количество входных токенов
* `output_tokens`: Количество выходных токенов
* `cache_read_tokens`: Количество токенов, прочитанных из кэша
* `cache_creation_tokens`: Количество токенов, использованных для создания кэша

#### Событие ошибки API

Логируется, когда запрос API к Claude не удается.

**Имя события**: `claude_code.api_error`

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `event.name`: `"api_error"`
* `event.timestamp`: Временная метка ISO 8601
* `model`: Используемая модель (например, "claude-sonnet-4-5-20250929")
* `error`: Сообщение об ошибке
* `status_code`: HTTP код состояния (если применимо)
* `duration_ms`: Длительность запроса в миллисекундах
* `attempt`: Номер попытки (для повторных запросов)

#### Событие решения инструмента

Логируется, когда принимается решение о разрешении инструмента (принять/отклонить).

**Имя события**: `claude_code.tool_decision`

**Атрибуты**:

* Все [стандартные атрибуты](#standard-attributes)
* `event.name`: `"tool_decision"`
* `event.timestamp`: Временная метка ISO 8601
* `tool_name`: Имя инструмента (например, "Read", "Edit", "Write", "NotebookEdit")
* `decision`: Либо `"accept"`, либо `"reject"`
* `source`: Источник решения - `"config"`, `"user_permanent"`, `"user_temporary"`, `"user_abort"` или `"user_reject"`

## Интерпретация данных метрик и событий

Метрики, экспортируемые Claude Code, предоставляют ценные сведения о паттернах использования и производительности. Вот некоторые распространенные визуализации и анализы, которые вы можете создать:

### Мониторинг использования

| Метрика                                                       | Возможность анализа                                                |
| ------------------------------------------------------------- | ------------------------------------------------------------------ |
| `claude_code.token.usage`                                     | Разбить по `type` (input/output), пользователю, команде или модели |
| `claude_code.session.count`                                   | Отслеживать принятие и вовлеченность с течением времени            |
| `claude_code.lines_of_code.count`                             | Измерить производительность, отслеживая добавления/удаления кода   |
| `claude_code.commit.count` & `claude_code.pull_request.count` | Понять влияние на рабочие процессы разработки                      |

### Мониторинг затрат

Метрика `claude_code.cost.usage` помогает с:

* Отслеживанием тенденций использования по командам или отдельным лицам
* Выявлением сеансов с высоким использованием для оптимизации

<Note>
  Метрики затрат являются приблизительными. Для официальных данных о выставлении счетов обратитесь к вашему поставщику API (Claude Console, AWS Bedrock или Google Cloud Vertex).
</Note>

### Оповещения и сегментация

Распространенные оповещения, которые следует рассмотреть:

* Скачки затрат
* Необычное потребление токенов
* Высокий объем сеансов от конкретных пользователей

Все метрики можно сегментировать по `user.account_uuid`, `organization.id`, `session.id`, `model` и `app.version`.

### Анализ событий

Данные событий предоставляют подробные сведения о взаимодействиях Claude Code:

**Паттерны использования инструментов**: анализируйте события результатов инструментов для выявления:

* Наиболее часто используемых инструментов
* Показателей успеха инструментов
* Среднего времени выполнения инструментов
* Паттернов ошибок по типам инструментов

**Мониторинг производительности**: отслеживайте длительность запросов API и время выполнения инструментов для выявления узких мест производительности.

## Рассмотрения бэкенда

Выбор вашего бэкенда метрик и логов определяет типы анализов, которые вы можете выполнять:

### Для метрик

* **Базы данных временных рядов (например, Prometheus)**: Расчеты скорости, агрегированные метрики
* **Колончатые хранилища (например, ClickHouse)**: Сложные запросы, анализ уникальных пользователей
* **Полнофункциональные платформы наблюдаемости (например, Honeycomb, Datadog)**: Продвинутые запросы, визуализация, оповещения

### Для событий/логов

* **Системы агрегации логов (например, Elasticsearch, Loki)**: Полнотекстовый поиск, анализ логов
* **Колончатые хранилища (например, ClickHouse)**: Анализ структурированных событий
* **Полнофункциональные платформы наблюдаемости (например, Honeycomb, Datadog)**: Корреляция между метриками и событиями

Для организаций, требующих метрик Daily/Weekly/Monthly Active User (DAU/WAU/MAU), рассмотрите бэкенды, поддерживающие эффективные запросы уникальных значений.

## Информация о сервисе

Все метрики и события экспортируются со следующими атрибутами ресурса:

* `service.name`: `claude-code`
* `service.version`: Текущая версия Claude Code
* `os.type`: Тип операционной системы (например, `linux`, `darwin`, `windows`)
* `os.version`: Строка версии операционной системы
* `host.arch`: Архитектура хоста (например, `amd64`, `arm64`)
* `wsl.version`: Номер версии WSL (присутствует только при запуске на Windows Subsystem for Linux)
* Имя счетчика: `com.anthropic.claude_code`

## Ресурсы для измерения ROI

Для полного руководства по измерению возврата инвестиций для Claude Code, включая настройку телеметрии, анализ затрат, метрики производительности и автоматизированные отчеты, см. [Руководство по измерению ROI Claude Code](https://github.com/anthropics/claude-code-monitoring-guide). Этот репозиторий предоставляет готовые конфигурации Docker Compose, настройки Prometheus и OpenTelemetry, а также шаблоны для создания отчетов о производительности, интегрированные с такими инструментами, как Linear.

## Рассмотрения безопасности/конфиденциальности

* Телеметрия является добровольной и требует явной конфигурации
* Конфиденциальная информация, такая как ключи API или содержимое файлов, никогда не включается в метрики или события
* Содержимое пользовательской подсказки скрыто по умолчанию - записывается только длина подсказки. Чтобы включить логирование пользовательских подсказок, установите `OTEL_LOG_USER_PROMPTS=1`

## Мониторинг Claude Code на Amazon Bedrock

Для подробного руководства по мониторингу использования Claude Code для Amazon Bedrock см. [Реализация мониторинга Claude Code (Bedrock)](https://github.com/aws-solutions-library-samples/guidance-for-claude-code-with-amazon-bedrock/blob/main/assets/docs/MONITORING.md).
