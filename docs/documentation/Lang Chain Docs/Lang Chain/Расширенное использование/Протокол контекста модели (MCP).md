> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Протокол контекста модели (MCP)

Протокол контекста модели (MCP) — это открытый протокол, стандартизирующий способы предоставления приложениями инструментов и контекста для LLM-систем. Агенты LangChain могут использовать инструменты, определенные на серверах MCP, с помощью библиотеки [`langchain-mcp-adapters`](https://github.com/langchain-ai/langchain-mcp-adapters).

## Быстрый старт

Установите библиотеку `langchain-mcp-adapters`:

<CodeGroup>
  ```bash pip theme={null}
  pip install langchain-mcp-adapters
  ```

  ```bash uv theme={null}
  uv add langchain-mcp-adapters
  ```
</CodeGroup>

`langchain-mcp-adapters` позволяет агентам использовать инструменты, определенные на одном или нескольких серверах MCP.

<Примечание>
  `MultiServerMCPClient` по умолчанию является **без сохранения состояния**. Каждый вызов инструмента создает новый `ClientSession` в MCP, запускает инструмент, а затем выполняет очистку. Дополнительные сведения см. в разделе [сохраняющие состояние сессии](#stateful-sessions).
</Примечание>

```python Доступ к нескольким серверам MCP icon="server" theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient # [!code highlight]
from langchain.agents import create_agent


клиент = MultiServerMCPClient( # [!подсветка кода]
    {
        "математика": {
            "транспорт": "stdio", # Локальная связь подпроцессов
            "команда": "python",
            # Абсолютный путь к вашему файлу math_server.py
            "args": ["/path/to/math_server.py"],
        },
        "погода": {
            "транспорт": "http", # удаленный сервер на основе HTTP
            # Убедитесь, что ваш сервер погоды запущен на порту 8000
            "url": "http://localhost:8000/mcp",
        }
    }
)

tools = await client.get_tools() # [!code highlight]
агент = create_agent(
    "claude-sonnet-4-5-20250929",
    инструменты # [!подсветка кода]
)
math_response = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "what's (3 + 5) x 12?"}]}
)
weather_response = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "what is the weather in nyc?"}]}
)
```

## Пользовательские серверы

Для создания собственного MCP-сервера используйте библиотеку [FastMCP](https://gofastmcp.com/getting-started/welcome):

<CodeGroup>
  ```bash pip theme={null}
  pip install fastmcp
  ```

  ```bash uv theme={null}
  uv add fastmcp
  ```
</CodeGroup>

Для тестирования вашего агента с помощью серверов инструментов MCP используйте следующие примеры:

<CodeGroup>
  ```python title="Math server (stdio transport)" icon="floppy-disk" theme={null}
  from fastmcp import FastMCP

  mcp = FastMCP("Math")

  @mcp.tool()
  def add(a: int, b: int) -> int:
      """Сложите два числа"""
      вернуть a + b

  @mcp.tool()
  def multiply(a: int, b: int) -> int:
      «Умножьте два числа»
      вернуть a * b

  если __name__ == "__main__":
      mcp.run(transport="stdio")
  ```

  ```python title="Сервер погоды (потоковый HTTP-транспорт)" icon="wifi" theme={null}
  from fastmcp import FastMCP

  mcp = FastMCP("Weather")

  @mcp.tool()
  async def get_weather(location: str) -> str:
      «Уточните прогноз погоды для данного места».
      вернуться "В Нью-Йорке всегда солнечно"

  если __name__ == "__main__":
      mcp.run(transport="streamable-http")
  ```
</CodeGroup>

## Транспорт

MCP поддерживает различные механизмы передачи данных для взаимодействия между клиентом и сервером.

### HTTP

Транспорт `http` (также называемый `streamable-http`) использует HTTP-запросы для связи между клиентом и сервером. Более подробную информацию можно найти в [спецификации транспорта HTTP MCP](https://modelcontextprotocol.io/specification/2025-03-26/basic/transports#streamable-http).

```python theme={null}
клиент = MultiServerMCPClient(
    {
        "погода": {
            "транспорт": "http",
            "url": "http://localhost:8000/mcp",
        }
    }
)
```

#### Передача заголовков

При подключении к серверам MCP по протоколу HTTP можно добавлять пользовательские заголовки (например, для аутентификации или трассировки) с помощью поля `headers` в конфигурации подключения. Это поддерживается для протоколов `sse` (устаревший в спецификации MCP) и `streamable_http`.

```python Передача заголовков с помощью MultiServerMCPClient theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

клиент = MultiServerMCPClient(
    {
        "погода": {
            "транспорт": "http",
            "url": "http://localhost:8000/mcp",
            "headers": { # [!code highlight]
                "Авторизация": "Предъявитель YOUR_TOKEN", # [!выделение кода]
                "X-Custom-Header": "custom-value" # [!code highlight]
            }, # [!подсветка кода]
        }
    }
)
инструменты = await client.get_tools()
agent = create_agent("openai:gpt-4.1", tools)
response = await agent.ainvoke({"messages": "Какая погода в Нью-Йорке?"})
```

#### Аутентификация

Библиотека `langchain-mcp-adapters` использует официальный [MCP SDK](https://github.com/modelcontextprotocol/python-sdk), что позволяет реализовать собственный механизм аутентификации путем использования интерфейса `httpx.Auth`.

```python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient

клиент = MultiServerMCPClient(
    {
        "погода": {
            "транспорт": "http",
            "url": "http://localhost:8000/mcp",
            "auth": auth, # [!code highlight]
        }
    }
)
```

* [Пример реализации пользовательской аутентификации](https://github.com/modelcontextprotocol/python-sdk/blob/main/examples/clients/simple-auth-client/mcp_simple_auth_client/main.py)
* [Встроенный поток OAuth](https://github.com/modelcontextprotocol/python-sdk/blob/main/src/mcp/client/auth.py#L179)

### стдио

Клиент запускает сервер как дочерний процесс и взаимодействует через стандартный ввод/вывод. Лучше всего подходит для локальных инструментов и простых конфигураций.

<Примечание>
  В отличие от HTTP-транспорта, соединения `stdio` по своей природе являются **состоятельными** — дочерний процесс сохраняется на протяжении всего времени существования клиентского соединения. Однако при использовании `MultiServerMCPClient` без явного управления сессиями каждый вызов инструмента по-прежнему создает новую сессию. См. [состоятельные сессии](#stateful-sessions) для управления постоянными соединениями.
</Примечание>

```python theme={null}
клиент = MultiServerMCPClient(
    {
        "математика": {
            "транспорт": "стдио",
            "команда": "python",
            "args": ["/path/to/math_server.py"],
        }
    }
)
```

## Сессии с сохранением состояния

По умолчанию `MultiServerMCPClient` является **без сохранения состояния** — каждый вызов инструмента создает новую сессию MCP, запускает инструмент, а затем выполняет очистку.

Если вам необходимо управлять [жизненным циклом](https://modelcontextprotocol.io/specification/2025-03-26/basic/lifecycle) сессии MCP (например, при работе с сервером, сохраняющим состояние и поддерживающим контекст между вызовами инструментов), вы можете создать постоянный `ClientSession` с помощью `client.session()`.

```python Использование MCP ClientSession для работы с инструментами, сохраняющими состояние theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools
from langchain.agents import create_agent

клиент = MultiServerMCPClient({...})

# Создать сессию явным образом
async with client.session("server_name") as session: # [!code highlight]
    # Передайте сессию для загрузки инструментов, ресурсов или подсказок
    tools = await load_mcp_tools(session) # [!code highlight]
    агент = create_agent(
        "anthropic:claude-3-7-sonnet-latest",
        инструменты
    )
```

## Основные функции

### Инструменты

Инструменты MCP позволяют серверам предоставлять исполняемые функции, которые LLM могут вызывать для выполнения действий, таких как запросы к базам данных, вызов API или взаимодействие с внешними системами. LangChain преобразует инструменты MCP в инструменты LangChain, что делает их непосредственно пригодными для использования в любом агенте или рабочем процессе LangChain.

#### Загрузка инструментов

Используйте `client.get_tools()` для получения инструментов с серверов MCP и передачи их вашему агенту:

```python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

клиент = MultiServerMCPClient({...})
tools = await client.get_tools() # [!code highlight]
agent = create_agent("claude-sonnet-4-5-20250929", tools)
```

#### Структурированный контент

Инструменты MCP могут возвращать [структурированное содержимое](https://modelcontextprotocol.io/specification/2025-03-26/server/tools#structured-content) наряду с удобочитаемым текстовым ответом. Это полезно, когда инструменту необходимо возвращать данные, пригодные для машинного анализа (например, JSON), в дополнение к тексту, отображаемому модели.

Когда инструмент MCP возвращает `structuredContent`, адаптер оборачивает его в [`MCPToolArtifact`](/docs/reference/langchain-mcp-adapters#MCPToolArtifact) и возвращает в качестве артефакта инструмента. Вы можете получить к нему доступ, используя поле `artifact` в `ToolMessage`. Вы также можете использовать [interceptors](#tool-interceptors) для автоматической обработки или преобразования структурированного контента.

**Извлечение структурированного содержимого из артефакта**

После запуска агента вы сможете получить доступ к структурированному содержимому из сообщений инструмента в ответе:

```python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent
from langchain.messages import ToolMessage

клиент = MultiServerMCPClient({...})
инструменты = await client.get_tools()
agent = create_agent("claude-sonnet-4-5-20250929", tools)

результат = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "Получить данные с сервера"}]}
)

# Извлечение структурированного содержимого из сообщений инструмента
for message in result["messages"]:
    if isinstance(message, ToolMessage) and message.artifact:
        structured_content = message.artifact["structured_content"]
```

**Добавление структурированного контента через перехватчик**

Если вы хотите, чтобы структурированное содержимое было видно в истории переписки (видимо для модели), вы можете использовать [перехватчик](#tool-interceptors), чтобы автоматически добавлять структурированное содержимое к результату инструмента:

```python theme={null}
импорт json

from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from mcp.types import TextContent

async def append_structured_content(request: MCPToolCallRequest, handler):
    «Добавить структурированное содержимое из артефакта в сообщение инструмента».
    результат = await обработчик(запрос)
    если result.structuredContent:
        result.content += [
            TextContent(type="text", text=json.dumps(result.structuredContent)),
        ]
    вернуть результат

клиент = MultiServerMCPClient({...}, tool_interceptors=[append_structured_content])
```

#### Мультимодальное содержимое инструмента

Инструменты MCP могут возвращать [мультимодальный контент](https://modelcontextprotocol.io/specification/2025-03-26/server/tools#tool-result) (изображения, текст и т. д.) в своих ответах. Когда сервер MCP возвращает контент, состоящий из нескольких частей (например, текст и изображения), адаптер преобразует их в [стандартные блоки контента]LangChain(/oss/python/langchain/messages#standard-content-blocks). Вы можете получить доступ к стандартизированному представлению через свойство `content_blocks` объекта `ToolMessage`:

```python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_agent

клиент = MultiServerMCPClient({...})
инструменты = await client.get_tools()
agent = create_agent("claude-sonnet-4-5-20250929", tools)

результат = await agent.ainvoke(
    {"messages": [{"role": "user", "content": "Сделать снимок экрана текущей страницы"}]}
)

# Доступ к мультимодальному контенту из сообщений инструмента
for message in result["messages"]:
    if message.type == "tool":
        # Исходный контент в формате, используемом поставщиком услуг
        print(f"Исходное содержимое: {message.content}")

        # Стандартизированные блоки контента # [!подсветка кода]
        for block in message.content_blocks: # [!code highlight]
            if block["type"] == "text": # [!подсветка кода]
                print(f"Текст: {block['text']}") # [!подсветка кода]
            elif block["type"] == "image": # [!code highlight]
                print(f"URL изображения: {block.get('url')}") # [!подсветка кода]
                print(f"Image base64: {block.get('base64', '')[:50]}...") # [!code highlight]
```

Это позволяет обрабатывать многомодальные ответы инструментов независимо от поставщика услуг, независимо от того, как базовый сервер MCP форматирует свое содержимое.

### Ресурсы

[Ресурсы](https://modelcontextprotocol.io/docs/concepts/resources) позволяют серверам MCP предоставлять данные — такие как файлы, записи в базе данных или ответы API — которые могут быть прочитаны клиентами. LangChain преобразует ресурсы MCP в объекты [Blob](/docs/reference/langchain-core/documents#Blob), которые предоставляют единый интерфейс для обработки как текстового, так и двоичного содержимого.

#### Загрузка ресурсов

Используйте `client.get_resources()` для загрузки ресурсов с сервера MCP:

```python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient

клиент = MultiServerMCPClient({...})

# Загрузка всех ресурсов с сервера
blobs = await client.get_resources("server_name") # [!code highlight]

# Или загрузка определенных ресурсов по URI
blobs = await client.get_resources("server_name", uris=["file:///path/to/file.txt"]) # [!code highlight]

для blob внутри blobs:
    print(f"URI: {blob.metadata['uri']}, MIME type: {blob.mimetype}")
    print(blob.as_string()) # Для текстового содержимого
```

Для большего контроля вы также можете использовать [`load_mcp_resources`](/docs/reference/langchain-mcp-adapters#load_mcp_resources) напрямую с сессией:

```python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.resources import load_mcp_resources

клиент = MultiServerMCPClient({...})

async with client.session("server_name") as session:
    # Загрузить все ресурсы
    blobs = await load_mcp_resources(session)

    # Или загрузка определенных ресурсов по URI
    blobs = await load_mcp_resources(session, uris=["file:///path/to/file.txt"])
```

### Подсказки

[Подсказки](https://modelcontextprotocol.io/docs/concepts/prompts) позволяют серверам MCP предоставлять многократно используемые шаблоны подсказок, которые могут быть получены и использованы клиентами. LangChain преобразует подсказки MCP в [сообщения](/docs/concepts/messages), что упрощает их интеграцию в рабочие процессы на основе чата.

#### Загрузка подсказок

Используйте `client.get_prompt()` для загрузки приглашения командной строки с сервера MCP:

```python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient

клиент = MultiServerMCPClient({...})

# Загрузка приглашения по имени
messages = await client.get_prompt("server_name", "summarize") # [!code highlight]

# Загрузка приглашения командной строки с аргументами
messages = await client.get_prompt( # [!code highlight]
    "server_name", # [!code highlight]
    "code_review", # [!code highlight]
    arguments={"language": "python", "focus": "security"} # [!code highlight]
) # [!подсветка кода]

# Используйте сообщения в своем рабочем процессе
для сообщения в сообщениях:
    print(f"{message.type}: {message.content}")
```

Для большего контроля вы также можете использовать [`load_mcp_prompt`](/docs/reference/langchain-mcp-adapters#load_mcp_prompt) напрямую с сессией:

```python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.prompts import load_mcp_prompt

клиент = MultiServerMCPClient({...})

async with client.session("server_name") as session:
    # Загрузка приглашения по имени
    messages = await load_mcp_prompt(session, "summarize")

    # Загрузка приглашения командной строки с аргументами
    messages = await load_mcp_prompt(
        сессия,
        "code_review",
        arguments={"language": "python", "focus": "security"}
    )
```

## Расширенные функции

### Перехватчики инструментов

Серверы MCP работают как отдельные процессы — они не имеют доступа к информации среды выполнения LangGraph, такой как [хранилище](/oss/python/langgraph/persistence#memory-store), [контекст](/oss/python/langchain/context-engineering) или состояние агента. **Перехватчики** устраняют этот пробел, предоставляя вам доступ к этому контексту среды выполнения во время выполнения инструмента MCP.

Перехватчики также обеспечивают управление вызовами инструментов, подобно промежуточному программному обеспечению: вы можете изменять запросы, реализовывать повторные попытки, динамически добавлять заголовки или полностью прерывать выполнение.

| Раздел                                                        | Описание                                                                              |
| ------------------------------------------------------------- | ------------------------------------------------------------------------------------- |
| [Доступ к контексту выполнения](#accessing-runtime-context)   | Чтение идентификаторов пользователей, ключей API, данных хранилища и состояния агента |
| [Обновления состояния и команды](#state-updates-and-commands) | Обновить состояние агента или поток графа управления с помощью команды `Command`      |
| [Написание перехватчиков](#writing-interceptors)              | Шаблоны для изменения запросов, составления перехватчиков и обработки ошибок          |

#### Доступ к контексту времени выполнения

При использовании инструментов MCP в агенте LangChain (через `create_agent`) перехватчики получают доступ к контексту `ToolRuntime`. Это обеспечивает доступ к идентификатору вызова инструмента, состоянию, конфигурации и хранилищу, что позволяет использовать мощные шаблоны для доступа к пользовательским данным, сохранения информации и управления поведением агента.

<Вкладки>
  <Tab title="Контекст выполнения">
    Получите доступ к пользовательским настройкам, таким как идентификаторы пользователей, ключи API или разрешения, передаваемые во время вызова:

    ```python Внедрить контекст пользователя в вызовы инструментов MCP theme={null}
    from dataclasses import dataclass
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.interceptors import MCPToolCallRequest
    from langchain.agents import create_agent

    @dataclass
    Контекст класса:
        user_id: str
        api_key: str

    async def inject_user_context(
        Запрос: MCPToolCallRequest,
        обработчик,
    ):
        «Внедрение учетных данных пользователя в вызовы инструментов MCP».
        runtime = request.runtime
        user_id = runtime.context.user_id # [!code highlight]
        api_key = runtime.context.api_key # [!code highlight]

        # Добавить контекст пользователя к аргументам инструмента
        modified_request = request.override(
            args={**request.args, "user_id": user_id}
        )
        return await handler(modified_request)

    клиент = MultiServerMCPClient(
        {...},
        tool_interceptors=[inject_user_context],
    )
    инструменты = await client.get_tools()
    agent = create_agent("gpt-4.1", tools, context_schema=Context)

    # Вызов с учетом контекста пользователя
    результат = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Search my orders"}]},
        context={"user_id": "user_123", "api_key": "sk-..."}
    )
    ```
  </Tab>

  <Tab title="Магазин">
    Для получения доступа к долговременной памяти и сохранения пользовательских настроек или сохранения данных между диалогами:

    ```python Доступ к пользовательским настройкам из темы магазина={null}
    from dataclasses import dataclass
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.interceptors import MCPToolCallRequest
    from langchain.agents import create_agent
    from langgraph.store.memory import InMemoryStore

    @dataclass
    Контекст класса:
        user_id: str

    async def personalize_search(
        Запрос: MCPToolCallRequest,
        обработчик,
    ):
        «Персонализируйте вызовы инструмента MCP, используя сохраненные настройки».
        runtime = request.runtime
        user_id = runtime.context.user_id
        store = runtime.store # [!code highlight]

        # Чтение пользовательских настроек из магазина
        prefs = store.get(("preferences",), user_id) # [!code highlight]

        если prefs и request.name == "search":
            # Применить выбранный пользователем язык и ограничение на количество результатов
            modified_args = {
                **request.args,
                "language": prefs.value.get("language", "en"),
                "limit": prefs.value.get("result_limit", 10),
            }
            request = request.override(args=modified_args)

        return await handler(request)

    клиент = MultiServerMCPClient(
        {...},
        tool_interceptors=[personalize_search],
    )
    инструменты = await client.get_tools()
    агент = create_agent(
        "gpt-4.1",
        инструменты,
        context_schema=Context,
        store=InMemoryStore()
    )
    ```
  </Tab>

  <Tab title="State">
    Для принятия решений на основе текущей сессии необходимо получить доступ к состоянию диалога:

    ```python Фильтрация инструментов на основе состояния аутентификации theme={null}
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.interceptors import MCPToolCallRequest
    from langchain.messages import ToolMessage

    async def require_authentication(
        Запрос: MCPToolCallRequest,
        обработчик,
    ):
        «Блокировать конфиденциальные инструменты MCP, если пользователь не авторизован».
        runtime = request.runtime
        state = runtime.state # [!выделение кода]
        is_authenticated = state.get("authenticated", False) # [!code highlight]

        sensitive_tools = ["delete_file", "update_settings", "export_data"]

        если request.name находится в sensitive_tools и не является is_authenticated:
            # Возвращать ошибку вместо вызова инструмента
            return ToolMessage(
                Требуется аутентификация. Пожалуйста, сначала войдите в систему.
                tool_call_id=runtime.tool_call_id,
            )

        return await handler(request)

    клиент = MultiServerMCPClient(
        {...},
        tool_interceptors=[require_authentication],
    )
    ```
  </Tab>

  <Tab title="Идентификатор вызова инструмента">
    Для получения корректно отформатированных ответов или отслеживания выполнения инструментов используйте идентификатор вызова инструмента:

    ```python Возвращает пользовательские ответы с идентификатором вызова инструмента theme={null}
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.interceptors import MCPToolCallRequest
    from langchain.messages import ToolMessage

    async def rate_limit_interceptor(
        Запрос: MCPToolCallRequest,
        обработчик,
    ):
        «Ограничение скорости вызовов дорогостоящих инструментов MCP».
        runtime = request.runtime
        tool_call_id = runtime.tool_call_id # [!code highlight]

        # Проверка лимита запросов (упрощенный пример)
        if is_rate_limited(request.name):
            return ToolMessage(
                content="Превышен лимит запросов. Пожалуйста, попробуйте позже."
                tool_call_id=tool_call_id, # [!code highlight]
            )

        результат = await обработчик(запрос)

        # Зарегистрировать успешный вызов инструмента
        log_tool_execution(tool_call_id, request.name, success=True)

        вернуть результат

    клиент = MultiServerMCPClient(
        {...},
        tool_interceptors=[rate_limit_interceptor],
    )
    ```
  </Tab>
</Вкладки>

Дополнительные шаблоны проектирования контекста см. в разделах [Проектирование контекста](/oss/python/langchain/context-engineering) и [Инструменты](/oss/python/langchain/tools).

#### Обновления состояния и команды

Перехватчики могут возвращать объекты `Command` для обновления состояния агента или управления потоком выполнения графа. Это полезно для отслеживания хода выполнения задачи, переключения между агентами или досрочного завершения выполнения.

```python Отметить задачу как выполненную и переключить агентов theme={null}
from langchain.agents import AgentState, create_agent
from langchain_mcp_adapters.interceptors import MCPToolCallRequest
from langchain.messages import ToolMessage
from langgraph.types import Command

async def handle_task_completion(
    Запрос: MCPToolCallRequest,
    обработчик,
):
    «Отметьте задачу как выполненную и передайте ее агенту по составлению сводки».
    результат = await обработчик(запрос)

    if request.name == "submit_order":
        return Command(
            обновление={
                "messages": [result] if isinstance(result, ToolMessage) else [],
                "task_status": "completed", # [!code highlight]
            },
            goto="summary_agent", # [!code highlight]
        )

    вернуть результат
```

Используйте `Command` с `goto="__end__"` для досрочного завершения выполнения:

```python End agent run on completion theme={null}
async def end_on_success(
    Запрос: MCPToolCallRequest,
    обработчик,
):
    «Завершить выполнение агента, когда задача будет помечена как выполненная».
    результат = await обработчик(запрос)

    if request.name == "mark_complete":
        return Command(
            обновление={"сообщения": [результат], "статус": "готово"},
            goto="__end__", # [!code highlight]
        )

    вернуть результат
```

#### Пользовательские перехватчики

Перехватчики — это асинхронные функции, которые инкапсулируют выполнение инструментов, обеспечивая модификацию запросов/ответов, логику повторных попыток и другие сквозные аспекты. Они следуют «луковой» схеме, где первый перехватчик в списке является самым внешним уровнем.

**Базовый узор**

Перехватчик — это асинхронная функция, которая принимает запрос и обработчик. Вы можете изменить запрос до вызова обработчика, изменить ответ после или полностью пропустить обработчик.

```Базовый шаблон перехватчика Python theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

async def logging_interceptor(
    Запрос: MCPToolCallRequest,
    обработчик,
):
    «Записывайте вызовы инструмента до и после выполнения».
    print(f"Вызов инструмента: {request.name} с аргументами: {request.args}")
    результат = await обработчик(запрос)
    print(f"Инструмент {request.name} вернул: {result}")
    вернуть результат

клиент = MultiServerMCPClient(
    {"math": {"transport": "stdio", "command": "python", "args": ["/path/to/server.py"]}},
    tool_interceptors=[logging_interceptor], # [!code highlight]
)
```

**Запросы на внесение изменений**

Используйте `request.override()` для создания измененного запроса. Это соответствует принципу неизменяемости, оставляя исходный запрос без изменений.

```python Изменение аргументов инструмента theme={null}
async def double_args_interceptor(
    Запрос: MCPToolCallRequest,
    обработчик,
):
    «Удвойте все числовые аргументы перед выполнением».
    modified_args = {k: v * 2 for k, v in request.args.items()}
    modified_request = request.override(args=modified_args) # [!code highlight]
    return await handler(modified_request)

# Исходный вызов: add(a=2, b=3) становится add(a=4, b=6)
```

**Изменение заголовков во время выполнения**

Перехватчики могут динамически изменять HTTP-заголовки в зависимости от контекста запроса:

```python Динамическое изменение заголовка theme={null}
async def auth_header_interceptor(
    Запрос: MCPToolCallRequest,
    обработчик,
):
    «Добавьте заголовки аутентификации в зависимости от вызываемого инструмента».
    token = get_token_for_tool(request.name)
    modified_request = request.override(
        headers={"Авторизация": f"Bearer {токен}"} # [!подсветка кода]
    )
    return await handler(modified_request)
```

**Компоновка перехватчиков**

Несколько перехватчиков располагаются в порядке, напоминающем «луковицу» — первый перехватчик в списке является самым внешним слоем:

```python Создание нескольких перехватчиков theme={null}
async def outer_interceptor(request, handler):
    print("outer: before")
    результат = await обработчик(запрос)
    print("outer: after")
    вернуть результат

async def inner_interceptor(request, handler):
    print("inner: before")
    результат = await обработчик(запрос)
    print("inner: after")
    вернуть результат

клиент = MultiServerMCPClient(
    {...},
    tool_interceptors=[outer_interceptor, inner_interceptor], # [!code highlight]
)

# Порядок исполнения:
# внешний: до -> внутренний: до -> выполнение инструмента -> внутренний: после -> внешний: после
```

**Обработка ошибок**

Используйте перехватчики для обнаружения ошибок выполнения инструментов и реализации логики повторных попыток:

```python Повторная попытка при ошибке theme={null}
import asyncio

async def retry_interceptor(
    Запрос: MCPToolCallRequest,
    обработчик,
    max_retries: int = 3,
    задержка: float = 1.0,
):
    """Повторить неудачные вызовы инструментов с экспоненциальной задержкой.""
    last_error = None
    for attempt in range(max_retries):
        пытаться:
            return await handler(request)
        за исключением исключения как e:
            last_error = e
            если attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt) # Экспоненциальная задержка
                print(f"Инструмент {request.name} не сработал (попытка {попытка + 1}), повторная попытка через {wait_time}с...")
                await asyncio.sleep(wait_time)
    вызвать последнюю ошибку

клиент = MultiServerMCPClient(
    {...},
    tool_interceptors=[retry_interceptor], # [!code highlight]
)
```

Вы также можете перехватывать определенные типы ошибок и возвращать резервные значения:

```python Обработка ошибок с резервной темой={null}
async def fallback_interceptor(
    Запрос: MCPToolCallRequest,
    обработчик,
):
    «Вернуть резервное значение, если выполнение инструмента завершится неудачей».
    пытаться:
        return await handler(request)
    except TimeoutError:
        "Вернуть "Время ожидания инструмента {request.name} истекло. Пожалуйста, попробуйте позже."
    except ConnectionError:
        return "Не удалось подключиться к сервису {request.name}. Используются кэшированные данные."
```

### Уведомления о ходе выполнения

Подпишитесь на уведомления о ходе выполнения длительных процессов с использованием инструментов:

```python Progress callback theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.callbacks import Callbacks, CallbackContext

async def on_progress(
    прогресс: плавающий объект,
    Итого: число с плавающей запятой | Нет,
    сообщение: str | None,
    контекст: CallbackContext,
):
    «Обрабатывать обновления о ходе выполнения от серверов MCP».
    процент = (прогресс / общий * 100), если общий, иначе прогресс
    tool_info = f" ({context.tool_name})" if context.tool_name else ""
    print(f"[{context.server_name}{tool_info}] Progress: {percent:.1f}% - {message}")

клиент = MultiServerMCPClient(
    {...},
    callbacks=Callbacks(on_progress=on_progress), # [!code highlight]
)
```

Объект `CallbackContext` предоставляет:

* `server_name`: Имя сервера MCP
* `tool_name`: Название выполняемого инструмента (доступно во время вызовов инструментов)

### Ведение журнала

Протокол MCP поддерживает [логирование](https://modelcontextprotocol.io/specification/2025-03-26/server/utilities/logging#log-levels) уведомлений от серверов. Используйте класс `Callbacks` для подписки на эти события.

```python Logging callback theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.callbacks import Callbacks, CallbackContext
from mcp.types import LoggingMessageNotificationParams

async def on_logging_message(
    параметры: LoggingMessageNotificationParams,
    контекст: CallbackContext,
):
    «Обработка сообщений журнала с серверов MCP».
    print(f"[{context.server_name}] {params.level}: {params.data}")

клиент = MultiServerMCPClient(
    {...},
    callbacks=Callbacks(on_logging_message=on_logging_message), # [!code highlight]
)
```

### Выявление

[Elicitation](https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation#elicitation) позволяет серверам MCP запрашивать дополнительные входные данные от пользователей во время выполнения инструмента. Вместо того чтобы требовать все входные данные заранее, серверы могут интерактивно запрашивать информацию по мере необходимости.

#### Настройка сервера

Определите инструмент, который использует `ctx.elicit()` для запроса пользовательского ввода со схемой:

```python MCP server with elicitation theme={null}
from pydantic import BaseModel
from mcp.server.fastmcp import Context, FastMCP

сервер = FastMCP("Профиль")

class UserDetails(BaseModel):
    электронная почта: str
    возраст: мн

@server.tool()
async def create_profile(name: str, ctx: Context) -> str:
    «Создайте профиль пользователя, запросив подробную информацию посредством опроса».
    result = await ctx.elicit( # [!code highlight]
        message=f"Пожалуйста, предоставьте подробную информацию о профиле {имя}:", # [!выделение кода]
        schema=UserDetails, # [!code highlight]
    ) # [!подсветка кода]
    if result.action == "accept" and result.data:
        return f"Создан профиль для {name}: email={result.data.email}, age={result.data.age}"
    если result.action == "decline":
        "Пользователь отклонил запрос. Создан минимальный профиль для {имя}."
    Возвращается сообщение "Создание профиля отменено."

если __name__ == "__main__":
    server.run(transport="http")
```

#### Настройка клиента

Обрабатывайте запросы на получение информации, предоставляя функцию обратного вызова для `MultiServerMCPClient`:

```python Обработка запросов на получение информации theme={null}
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.callbacks import Callbacks, CallbackContext
from mcp.shared.context import RequestContext
from mcp.types import ElicitRequestParams, ElicitResult

async def on_elication(
    mcp_context: RequestContext,
    параметры: ElicitRequestParams,
    контекст: CallbackContext,
) -> ElicitResult:
    «Обрабатывать запросы на получение информации с серверов MCP».
    # В реальном приложении вы бы запрашивали у пользователя ввод данных.
    # на основе params.message и params.requestedSchema
    return ElicitResult( # [!выделение кода]
        action="accept", # [!code highlight]
        content={"email": "user@example.com", "age": 25}, # [!code highlight]
    ) # [!подсветка кода]

клиент = MultiServerMCPClient(
    {
        "профиль": {
            "url": "http://localhost:8000/mcp",
            "транспорт": "http",
        }
    },
    callbacks=Callbacks(on_elicitation=on_elicitation), # [!code highlight]
)
```

#### Действия в ответ

Функция обратного вызова для получения информации может возвращать одно из трех действий:

| Действие    | Описание                                                                          |
| ----------- | --------------------------------------------------------------------------------- |
| `accept`    | Пользователь предоставил корректные данные. Включите эти данные в поле `content`. |
| `отклонить` | Пользователь отказался предоставить запрошенную информацию.                       |
| `отменить`  | Пользователь полностью отменил операцию.                                          |

Примеры действий Response на Python theme={null}
# Принять с данными
ElicitResult(action="accept", content={"email": "user@example.com", "age": 25})

# Отклонить (пользователь не хочет предоставлять информацию)
ElicitResult(action="decline")

# Отменить (прервать операцию)
ElicitResult(action="cancel")
```

## Дополнительные ресурсы

* [Документация MCP](https://modelcontextprotocol.io/introduction)
* [Документация по транспорту MCP](https://modelcontextprotocol.io/docs/concepts/transports)
* [`langchain-mcp-adapters`](https://github.com/langchain-ai/langchain-mcp-adapters)

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langchain/mcp.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Callout>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>