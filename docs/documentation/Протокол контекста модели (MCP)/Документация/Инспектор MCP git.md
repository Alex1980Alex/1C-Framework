# Инспектор MCP
https://github.com/modelcontextprotocol/inspector

MCP Inspector — это инструмент разработчика для тестирования и отладки MCP-серверов.

## Обзор архитектуры

Программа MCP Inspector состоит из двух основных компонентов, работающих совместно:

* **MCP Inspector Client (MCPI)** : веб-интерфейс на основе React, предоставляющий интерактивный интерфейс для тестирования и отладки серверов MCP.
* **MCP Proxy (MCPP)** : сервер Node.js, выступающий в качестве моста протокола, соединяющего веб-интерфейс с MCP-серверами с помощью различных методов передачи данных (stdio, SSE, streamable-http).

Обратите внимание, что прокси-сервер не является сетевым прокси для перехвата трафика. Вместо этого он функционирует как клиент MCP (подключаясь к вашему серверу MCP) и как HTTP-сервер (предоставляя веб-интерфейс), обеспечивая взаимодействие с серверами MCP, использующими различные транспортные протоколы, через браузер.

## Запуск инспектора

### Требования

* Node.js: ^22.7.5

### Быстрый старт (режим пользовательского интерфейса)

Чтобы сразу же начать работу с пользовательским интерфейсом, просто выполните следующую команду:

```bash
npx @modelcontextprotocol/inspector
```

Сервер запустится, и пользовательский интерфейс станет доступен по адресу http://localhost:6274.

### Контейнер Docker

Вы также можете запустить его в контейнере Docker с помощью следующей команды:

```bash
docker run --rm \
  -p 127.0.0.1:6274:6274 \
  -p 127.0.0.1:6277:6277 \
  -e HOST=0.0.0.0 \
  -e MCP_AUTO_OPEN_ENABLED=false \
  ghcr.io/modelcontextprotocol/inspector:latest
```

### Из репозитория сервера MCP

Для проверки реализации сервера MCP нет необходимости клонировать этот репозиторий. Вместо этого используйте команду `npx`. Например, если ваш сервер собран по адресу build/index.js:

```bash
npx @modelcontextprotocol/inspector node build/index.js
```

Вы можете передавать на свой MCP-сервер как аргументы, так и переменные окружения. Аргументы передаются непосредственно на сервер, а переменные окружения можно установить с помощью флага `-e`:

```bash
# Pass arguments only
npx @modelcontextprotocol/inspector node build/index.js arg1 arg2

# Pass environment variables only
npx @modelcontextprotocol/inspector -e key=value -e key2=$VALUE2 node build/index.js

# Pass both environment variables and arguments
npx @modelcontextprotocol/inspector -e key=value -e key2=$VALUE2 node build/index.js arg1 arg2

# Use -- to separate inspector flags from server arguments
npx @modelcontextprotocol/inspector -e key=$VALUE -- node build/index.js -e server-flag
```

Инспектор запускает как клиентский интерфейс MCP Inspector (MCPI) (порт по умолчанию 6274), так и сервер MCP Proxy (MCPP) (порт по умолчанию 6277). Откройте клиентский интерфейс MCPI в браузере, чтобы использовать инспектор. При необходимости вы можете настроить порты:

```bash
CLIENT_PORT=8080 SERVER_PORT=9000 npx @modelcontextprotocol/inspector node build/index.js
```

## Экспорт файлов серверов

MCP Inspector предоставляет удобные кнопки для экспорта конфигураций запуска сервера для использования в таких клиентах, как Cursor, Claude Code или CLI Inspector. Файл обычно называется `mcp.json`.

### Запись сервера

Копирует одну запись конфигурации сервера в буфер обмена. Ее можно добавить в файл `mcp.json` внутри объекта `mcpServers`, указав желаемое имя сервера.

**Пример передачи данных по протоколу STDIO:**

```json
{
  "command": "node",
  "args": ["build/index.js", "--debug"],
  "env": {
    "API_KEY": "your-api-key",
    "DEBUG": "true"
  }
}
```

**Пример транспортировки SSE:**

```json
{
  "type": "sse",
  "url": "http://localhost:3000/events",
  "note": "For SSE connections, add this URL directly in Client"
}
```

**Пример потокового HTTP-транспорта:**

```json
{
  "type": "streamable-http",
  "url": "http://localhost:3000/mcp",
  "note": "For Streamable HTTP connections, add this URL directly in your MCP Client"
}
```

### Файл серверов

Копирует полную структуру файла конфигурации MCP в буфер обмена, добавляя текущую конфигурацию сервера в качестве параметра `default-server`. Его можно сохранить напрямую как файл конфигурации `mcp.json`.

**Пример передачи данных по протоколу STDIO:**

```json
{
  "mcpServers": {
    "default-server": {
      "command": "node",
      "args": ["build/index.js", "--debug"],
      "env": {
        "API_KEY": "your-api-key",
        "DEBUG": "true"
      }
    }
  }
}
```

**Пример транспортировки SSE:**

```json
{
  "mcpServers": {
    "default-server": {
      "type": "sse",
      "url": "http://localhost:3000/events",
      "note": "For SSE connections, add this URL directly in Client"
    }
  }
}
```

**Пример потокового HTTP-транспорта:**

```json
{
  "mcpServers": {
    "default-server": {
      "type": "streamable-http",
      "url": "http://localhost:3000/mcp",
      "note": "For Streamable HTTP connections, add this URL directly in your MCP Client"
    }
  }
}
```

## Аутентификация

Инспектор поддерживает аутентификацию с помощью токена Bearer для SSE-подключений. Введите свой токен в пользовательском интерфейсе при подключении к серверу MCP, и он будет отправлен в заголовке Authorization. Вы можете изменить имя заголовка, используя поле ввода на боковой панели.

## Вопросы безопасности

MCP Inspector включает в себя прокси-сервер, который может запускать локальные процессы MCP и взаимодействовать с ними. Прокси-сервер не должен быть доступен из ненадежных сетей, поскольку он имеет разрешения на запуск локальных процессов и может подключаться к любому указанному серверу MCP.

### Аутентификация прокси-сервера

Прокси-сервер MCP Inspector по умолчанию требует аутентификации. При запуске сервера генерируется случайный токен сессии, который выводится в консоль:

```
🔑 Session token: 3a1c267fad21f7150b7d624c160b7f09b0b8c4f623c7107bbf13378f051538d4

🔗 Open inspector with token pre-filled:
   http://localhost:6274/?MCP_PROXY_AUTH_TOKEN=3a1c267fad21f7150b7d624c160b7f09b0b8c4f623c7107bbf13378f051538d4
```

Этот токен необходимо включить в заголовок Authorization в качестве токена Bearer для всех запросов к серверу. Инспектор автоматически откроет ваш браузер с предварительно заполненным токеном в URL-адресе.

#### Ручная настройка

Если у вас уже открыт инспектор:

1. Нажмите кнопку «Настройки» на боковой панели.
2. Найдите раздел «Токен прокси-сессии» и введите токен, отображаемый в консоли прокси-сервера.
3. Нажмите «Сохранить», чтобы применить настройки.

Токен будет сохранен в локальном хранилище вашего браузера для дальнейшего использования.

### Отключение аутентификации (НЕ РЕКОМЕНДУЕТСЯ)

Если вам необходимо отключить аутентификацию, вы можете установить переменную среды `DANGEROUSLY_OMIT_AUTH`:

```bash
DANGEROUSLY_OMIT_AUTH=true npm start
```

⚠️ **ВНИМАНИЕ** ⚠️

Отключение аутентификации `DANGEROUSLY_OMIT_AUTH` невероятно опасно! Это означает, что посещение вредоносного веб-сайта или просмотр вредоносной рекламы может позволить злоумышленнику удаленно скомпрометировать ваш компьютер. Не отключайте эту функцию, если вы действительно не понимаете рисков.

### Установка токена через переменную среды

Вы также можете установить токен с помощью переменной среды `MCP_PROXY_AUTH_TOKEN` при запуске сервера:

```bash
MCP_PROXY_AUTH_TOKEN=$(openssl rand -hex 32) npm start
```

### Привязка только к локальному интерфейсу

По умолчанию как прокси-сервер, так и клиент MCP Inspector привязываются только к одному сетевому интерфейсу `localhost`, чтобы предотвратить доступ из сети. Если вам необходимо привязаться ко всем интерфейсам в целях разработки, вы можете переопределить это с помощью переменной среды `HOST`:

```bash
HOST=0.0.0.0 npm start
```

⚠️ **Внимание:** Привязывайтесь ко всем интерфейсам только в доверенных сетевых средах, так как это открывает прокси-серверу доступ к сети для выполнения локальных процессов.

### Защита от повторной привязки DNS

Для предотвращения атак с использованием перепривязки DNS, инспектор MCP проверяет заголовок `Origin` входящих запросов. По умолчанию разрешены только запросы от источника клиента. Вы можете настроить дополнительные разрешенные источники, установив переменную среды `ALLOWED_ORIGINS` (список, разделенный запятыми):

```bash
ALLOWED_ORIGINS=http://localhost:6274,http://localhost:8000 npm start
```

## Конфигурация

MCP Inspector поддерживает следующие параметры конфигурации. Чтобы изменить их, нажмите кнопку Configuration в пользовательском интерфейсе MCP Inspector:

| Параметр                                | Описание                                                                                                              | По умолчанию |
| --------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------ |
| `MCP_SERVER_REQUEST_TIMEOUT`            | Тайм-аут на стороне клиента (мс) — Инспектор отменит запрос, если в течение этого времени не будет получен ответ.     | 300000       |
| `MCP_REQUEST_TIMEOUT_RESET_ON_PROGRESS` | Сбросить тайм-аут уведомлений о ходе выполнения.                                                                      | истинный     |
| `MCP_REQUEST_MAX_TOTAL_TIMEOUT`         | Максимальное общее время ожидания для запросов (мс) (используйте с уведомлениями о ходе выполнения).                  | 60000        |
| `MCP_PROXY_FULL_ADDRESS`                | Установите этот параметр, если вы используете прокси-сервер MCP Inspector на адресе, отличном от адреса по умолчанию. | ""           |
| `MCP_AUTO_OPEN_ENABLED`                 | Включить автоматическое открытие окна браузера при запуске инспектора.                                                | истинный     |

**Примечание о таймаутах:** указанные выше настройки определяют, когда Инспектор будет отменять запросы. Они не зависят от каких-либо таймаутов на стороне сервера.

### Файлы конфигурации

Инспектор также поддерживает конфигурационные файлы для хранения настроек различных серверов MCP:

```bash
npx @modelcontextprotocol/inspector --config path/to/config.json --server everything
```

**Пример файла конфигурации сервера:**

```json
{
  "mcpServers": {
    "everything": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-everything"],
      "env": {
        "hello": "Hello MCP!"
      }
    },
    "my-server": {
      "command": "node",
      "args": ["build/index.js", "arg1", "arg2"],
      "env": {
        "key": "value",
        "key2": "value2"
      }
    }
  }
}
```

### Типы транспорта в конфигурационных файлах

Инспектор автоматически определяет тип транспорта из вашего конфигурационного файла.

**STDIO (по умолчанию):**

```json
{
  "mcpServers": {
    "my-stdio-server": {
      "type": "stdio",
      "command": "npx",
      "args": ["@modelcontextprotocol/server-everything"]
    }
  }
}
```

**SSE (Server-Sent Events):**

```json
{
  "mcpServers": {
    "my-sse-server": {
      "type": "sse",
      "url": "http://localhost:3000/sse"
    }
  }
}
```

**Потоковая передача HTTP:**

```json
{
  "mcpServers": {
    "my-http-server": {
      "type": "streamable-http",
      "url": "http://localhost:3000/mcp"
    }
  }
}
```

### Выбор сервера по умолчанию

Вы можете запустить инспектор без указания имени сервера, если в вашей конфигурации указано следующее:

**Один сервер — выбран автоматически:**

```bash
npx @modelcontextprotocol/inspector --config mcp.json
```

**Сервер с именем "default-server" выбран автоматически:**

```json
{
  "mcpServers": {
    "default-server": {
      "command": "npx",
      "args": ["@modelcontextprotocol/server-everything"]
    },
    "other-server": {
      "command": "node",
      "args": ["other.js"]
    }
  }
}
```

### Параметры запроса

Вы также можете задать начальный `transport`, `serverUrl`, `serverCommand` и `serverArgs` с помощью параметров запроса:

```
http://localhost:6274/?transport=sse&serverUrl=http://localhost:8787/sse
http://localhost:6274/?transport=streamable-http&serverUrl=http://localhost:8787/mcp
http://localhost:6274/?transport=stdio&serverCommand=npx&serverArgs=arg1%20arg2
```

Вы также можете задать начальные параметры конфигурации:

```
http://localhost:6274/?MCP_SERVER_REQUEST_TIMEOUT=60000&MCP_REQUEST_TIMEOUT_RESET_ON_PROGRESS=false&MCP_PROXY_FULL_ADDRESS=http://10.1.1.22:5577
```

## Режим командной строки

Режим CLI обеспечивает программное взаимодействие с серверами MCP из командной строки, что идеально подходит для написания скриптов, автоматизации и интеграции с программными помощниками.

```bash
npx @modelcontextprotocol/inspector --cli node build/index.js
```

### Примеры команд CLI

```bash
# Basic usage
npx @modelcontextprotocol/inspector --cli node build/index.js

# With config file
npx @modelcontextprotocol/inspector --cli --config path/to/config.json --server myserver

# List available tools
npx @modelcontextprotocol/inspector --cli node build/index.js --method tools/list

# Call a specific tool
npx @modelcontextprotocol/inspector --cli node build/index.js --method tools/call --tool-name mytool --tool-arg key=value --tool-arg another=value2

# Call a tool with JSON arguments
npx @modelcontextprotocol/inspector --cli node build/index.js --method tools/call --tool-name mytool --tool-arg 'options={"format": "json", "max_tokens": 100}'

# List available resources
npx @modelcontextprotocol/inspector --cli node build/index.js --method resources/list

# List available prompts
npx @modelcontextprotocol/inspector --cli node build/index.js --method prompts/list

# Connect to a remote MCP server (default is SSE transport)
npx @modelcontextprotocol/inspector --cli https://my-mcp-server.example.com

# Connect to a remote MCP server (with Streamable HTTP transport)
npx @modelcontextprotocol/inspector --cli https://my-mcp-server.example.com --transport http --method tools/list

# Connect to a remote MCP server (with custom headers)
npx @modelcontextprotocol/inspector --cli https://my-mcp-server.example.com --transport http --method tools/list --header "X-API-Key: your-api-key"
```

## Режим пользовательского интерфейса против режима командной строки

| Вариант использования      | Режим пользовательского интерфейса                                                    | Режим командной строки                                                     |
| -------------------------- | ------------------------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| Разработка серверов        | Визуальный интерфейс для интерактивного тестирования и отладки в процессе разработки. | Скриптовые команды для быстрого тестирования и непрерывной интеграции.     |
| Разведка ресурсов          | Интерактивный браузер с иерархической навигацией и визуализацией JSON.                | Программное прослушивание и чтение для автоматизации и написания скриптов. |
| Тестирование инструментов  | Ввод параметров на основе форм с визуализацией ответа в реальном времени.             | Выполнение инструментов командной строки с выводом в формате JSON.         |
| Оперативное проектирование | Интерактивное сэмплирование с потоковой обработкой ответов.                           | Пакетная обработка запросов с выводом в машиночитаемом формате.            |
| Отладка                    | История запросов, визуализация ошибок и уведомления в режиме реального времени.       | Прямой вывод в формате JSON для анализа логов.                             |

## Разработка

### Режим разработки

```bash
npm run dev

# To co-develop with the typescript-sdk package:
npm run dev:sdk "cd sdk && npm run examples:simple-server:w"
```

**Примечание для пользователей Windows:**

```bash
npm run dev:windows
```

### Режим производства

```bash
npm run build
npm start
```

## Лицензия

Данный проект распространяется под лицензией MIT.