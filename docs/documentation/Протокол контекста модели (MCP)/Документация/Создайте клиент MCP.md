> ## Индекс документации
Полный индекс документации доступен по адресу: https://modelcontextprotocol.io/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Создание клиента MCP

Начните создавать собственное клиентское приложение, которое сможет интегрироваться со всеми серверами MCP.

В этом руководстве вы узнаете, как создать чат-бота на базе LLM, который подключается к серверам MCP.

Прежде чем начать, полезно ознакомиться с нашим руководством по [созданию MCP-сервера](/docs/develop/build-server), чтобы понять, как взаимодействуют клиенты и серверы.

<Вкладки>
  <Tab title="Python">
    [Полный код для этого урока можно найти здесь.](https://github.com/modelcontextprotocol/quickstart-resources/tree/main/mcp-client-python)

    ## Системные требования

    Перед началом убедитесь, что ваша система соответствует следующим требованиям:

    * Компьютер Mac или Windows
    * Установлена ​​последняя версия Python
    * Установлена ​​последняя версия `uv`

    ## Настройка вашей среды

    Сначала создайте новый проект Python с помощью `uv`:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      # Создание каталога проекта
      uv init mcp-client
      cd mcp-client

      # Создание виртуальной среды
      uv venv

      # Активировать виртуальную среду
      источник .venv/bin/activate

      # Установка необходимых пакетов
      uv add mcp anthropic python-dotenv

      # Удаление шаблонных файлов
      rm main.py

      # Создаем наш основной файл
      touch client.py
      ```

      ```Тема Windows PowerShell={null}
      # Создание каталога проекта
      uv init mcp-client
      cd mcp-client

      # Создание виртуальной среды
      uv venv

      # Активировать виртуальную среду
      .venv\Scripts\activate

      # Установка необходимых пакетов
      uv add mcp anthropic python-dotenv

      # Удаление шаблонных файлов
      del main.py

      # Создаем наш основной файл
      new-item client.py
      ```
    </CodeGroup>

    ## Настройка вашего API-ключа

    Вам потребуется ключ API Anthropic из [консоли Anthropic](https://console.anthropic.com/settings/keys).

    Создайте файл `.env` для его хранения:

    ```bash theme={null}
    echo "ANTHROPIC_API_KEY=ваш-ключ-API-здесь" > .env
    ```

    Добавьте `.env` в ваш файл `.gitignore`:

    ```bash theme={null}
    echo ".env" >> .gitignore
    ```

    <Предупреждение>
      Обязательно обеспечьте безопасность своего `ANTHROPIC_API_KEY`!
    </Предупреждение>

    ## Создание клиента

    ### Базовая структура клиента

    Для начала давайте настроим импорт и создадим базовый класс клиента:

    ```python theme={null}
    import asyncio
    из набора текста импорт Необязательный
    from contextlib import AsyncExitStack

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    из антропического импорта Антропический
    from dotenv import load_dotenv

    load_dotenv() # Загрузка переменных окружения из файла .env

    класс MCPClient:
        def __init__(self):
            # Инициализация объектов сессии и клиента
            self.session: Optional[ClientSession] = None
            self.exit_stack = AsyncExitStack()
            self.anthropic = Anthropic()
        # Здесь будут размещены методы
    ```

    ### Управление подключением к серверу

    Далее мы реализуем метод подключения к серверу MCP:

    ```python theme={null}
    async def connect_to_server(self, server_script_path: str):
        """Подключитесь к серверу MCP

        Аргументы:
            server_script_path: Путь к серверному скрипту (.py или .js)
        """
        is_python = server_script_path.endswith('.py')
        is_js = server_script_path.endswith('.js')
        если не (is_python или is_js):
            raise ValueError("Серверный скрипт должен быть файлом .py или .js")

        command = "python" if is_python else "node"
        server_params = StdioServerParameters(
            команда=команда,
            args=[server_script_path],
            env=None
        )

        stdio_transport = await self.exit_stack.enter_async_context(stdio_client(server_params))
        self.stdio, self.write = stdio_transport
        self.session = await self.exit_stack.enter_async_context(ClientSession(self.stdio, self.write))

        await self.session.initialize()

        # Список доступных инструментов
        response = await self.session.list_tools()
        инструменты = response.tools
        print("\nПодключено к серверу с помощью инструментов:", [tool.name для инструмента в tools])
    ```

    ### Логика обработки запросов

    Теперь добавим основной функционал для обработки запросов и вызовов инструментов:

    ```python theme={null}
    async def process_query(self, query: str) -> str:
        «Обработайте запрос с помощью Claude и доступных инструментов»
        сообщения = [
            {
                "роль": "пользователь",
                "содержание": запрос
            }
        ]

        response = await self.session.list_tools()
        available_tools = [{
            "name": tool.name,
            "description": tool.description,
            "input_schema": tool.inputSchema
        } for tool in response.tools]

        # Первоначальный вызов API Клода
        response = self.anthropic.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            сообщения=сообщения,
            инструменты=доступные_инструменты
        )

        # Обработка ответов и вызовов инструментов
        final_text = []

        assistant_message_content = []
        для содержимого в response.content:
            если content.type == 'text':
                final_text.append(content.text)
                assistant_message_content.append(content)
            elif content.type == 'tool_use':
                tool_name = content.name
                tool_args = content.input

                # Выполнить вызов инструмента
                result = await self.session.call_tool(tool_name, tool_args)
                final_text.append(f"[Вызов инструмента {tool_name} с аргументами {tool_args}]")

                assistant_message_content.append(content)
                сообщения.добавить({
                    "роль": "ассистент",
                    "content": assistant_message_content
                })
                сообщения.добавить({
                    "роль": "пользователь",
                    "содержание": [
                        {
                            "type": "tool_result",
                            "tool_use_id": content.id,
                            "content": result.content
                        }
                    ]
                })

                # Получить следующий ответ от Клода
                response = self.anthropic.messages.create(
                    model="claude-sonnet-4-20250514",
                    max_tokens=1000,
                    сообщения=сообщения,
                    инструменты=доступные_инструменты
                )

                final_text.append(response.content[0].text)

        return "\n".join(final_text)
    ```

    ### Интерактивный интерфейс чата

    Теперь добавим цикл чата и функцию очистки:

    ```python theme={null}
    async def chat_loop(self):
        """Запустить интерактивный чат"""
        print("\nКлиент MCP запущен!")
        print("Введите ваши запросы или 'quit' для выхода.")

        пока истинно:
            пытаться:
                query = input("\nQuery: ").strip()

                if query.lower() == 'quit':
                    перерыв

                response = await self.process_query(query)
                print("\n" + response)

            за исключением исключения как e:
                print(f"\nОшибка: {str(e)}")

    async def cleanup(self):
        «Очистка ресурсов»
        await self.exit_stack.aclose()
    ```

    ### Главный вход

    Наконец, добавим основную логику выполнения:

    ```python theme={null}
    async def main():
        если len(sys.argv) < 2:
            print("Использование: python client.py <путь_к_серверному_скрипту>")
            sys.exit(1)

        клиент = MCPClient()
        пытаться:
            await client.connect_to_server(sys.argv[1])
            await client.chat_loop()
        окончательно:
            await client.cleanup()

    если __name__ == "__main__":
        импорт sys
        asyncio.run(main())
    ```

    Полный файл `client.py` можно найти [здесь](https://github.com/modelcontextprotocol/quickstart-resources/blob/main/mcp-client-python/client.py).

    ## Объяснение ключевых компонентов

    ### 1. Инициализация клиента

    * Класс `MCPClient` инициализируется с помощью управления сессиями и API-клиентов.
    * Использует `AsyncExitStack` для корректного управления ресурсами.
    * Настраивает клиент Anthropic для взаимодействия с Клодом.

    ### 2. Подключение к серверу

    * Поддерживает серверы на Python и Node.js
    * Проверяет тип серверного скрипта
    * Создание надлежащих каналов связи
    * Инициализирует сессию и отображает список доступных инструментов.

    ### 3. Обработка запросов

    * Сохраняет контекст разговора
    * Обрабатывает ответы Клода и запросы к инструментам.
    * Управляет потоком сообщений между Клодом и инструментами.
    * Объединяет результаты в связный ответ

    ### 4. Интерактивный интерфейс

    * Предоставляет простой интерфейс командной строки
    * Обрабатывает ввод данных пользователем и отображает ответы.
    * Включает базовую обработку ошибок
    * Обеспечивает плавный выход

    ### 5. Управление ресурсами

    * Надлежащая очистка ресурсов
    * Обработка ошибок, связанных с проблемами подключения
    * Процедуры корректного завершения работы

    ## Общие точки настройки

    1. **Обращение с инструментом**
       * Измените функцию `process_query()` для обработки конкретных типов инструментов.
       * Добавлена ​​пользовательская обработка ошибок для вызовов инструментов.
       * Внедрить форматирование ответов, специфичное для конкретного инструмента.

    2. **Обработка ответа**
       * Настройте формат отображения результатов работы инструмента.
       * Добавить фильтрацию или преобразование ответа
       * Реализовать пользовательское логирование

    3. **Пользовательский интерфейс**
       * Добавить графический интерфейс пользователя или веб-интерфейс
       * Реализовать расширенный вывод в консоль
       * Добавить историю команд или автозавершение

    ## Запуск клиента

    Для запуска клиента на любом сервере MCP:

    ```bash theme={null}
    uv run client.py path/to/server.py # python server
    uv run client.py path/to/build/index.js # node server
    ```

    <Примечание>
      Если вы продолжаете [изучение темы погоды из руководства по быстрому запуску сервера](https://github.com/modelcontextprotocol/quickstart-resources/tree/main/weather-server-python), ваша команда может выглядеть примерно так: `python client.py .../quickstart-resources/weather-server-python/weather.py`
    </Примечание>

    Клиент будет:

    1. Подключитесь к указанному серверу.
    2. Перечислите доступные инструменты.
    3. Начните интерактивный чат, в котором вы сможете:
       * Введите запросы
       * См. выполнение инструментов
       * Получите ответы от Клода

    Вот пример того, как должно выглядеть подключение к серверу погоды через руководство по быстрому запуску сервера:

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/client-claude-cli-python.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=686d6e0ae7c54f807827db111eaed7d4" data-og-width="1932" width="1932" data-og-height="1739" height="1739" data-path="images/client-claude-cli-python.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/client-claude-cli-python.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=48ff45c4ca51501589d9f20f060daa56 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/client-claude-cli-python.png?w=5 60&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=b35ca5d8a67c2f08efec9c6519efcfe2 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/client-claude-cli-python.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=51b8f5c7fa48db6ccd30aa9988a8c917 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/client-claude-cli-python.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=9e1b01bc4c324a7e5100674f63f36b13 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/client-claude-cli-python.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=e3e961bd5b5506fed6c860f70df9bf9d 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/client-claude-cli-python.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=da01c2527db68cb0c99d29d20751a868 2500w" />
    </Frame>

    ## Как это работает

    Когда вы отправляете запрос:

    1. Клиент получает список доступных инструментов с сервера.
    2. Ваш запрос отправляется Клоду вместе с описанием инструментов.
    3. Клод решает, какие инструменты (если таковые имеются) использовать.
    4. Клиент выполняет все запрошенные вызовы инструментов через сервер.
    5. Результаты отправляются обратно Клоду.
    6. Клод дает ответ на естественном языке.
    7. Ответ отображается вам.

    ## Передовые методы

    1. **Обработка ошибок**
       * Всегда заключайте вызовы инструментов в блоки try-catch.
       * Предоставлять содержательные сообщения об ошибках
       * Корректно обрабатывайте проблемы с подключением

    2. **Управление ресурсами**
       * Используйте `AsyncExitStack` для корректной очистки ресурсов.
       * Закройте соединения после завершения работы
       * Обработка отключений от сервера

    3. **Безопасность**
       * Надежно храните ключи API в файле `.env`
       * Проверка ответов сервера
       * Будьте осторожны с правами доступа к инструментам.

    4. **Названия инструментов**
       * Названия инструментов могут проверяться в соответствии с форматом, указанным [здесь](/specification/draft/server/tools#tool-names)
       * Если название инструмента соответствует указанному формату, оно не должно отклоняться от проверки клиентом MCP.

    ## Поиск неисправностей

    ### Проблемы с путями к серверу

    * Дважды проверьте правильность пути к вашему серверному скрипту.
    * Используйте абсолютный путь, если относительный путь не работает.
    * Пользователям Windows следует использовать косые черты (/) или экранированные обратные косые черты (\\) в пути.
    * Убедитесь, что файл сервера имеет правильное расширение (.py для Python или .js для Node.js)

    Пример корректного использования пути:

    ```bash theme={null}
    # Относительный путь
    uv run client.py ./server/weather.py

    # Абсолютный путь
    uv run client.py /Users/username/projects/mcp-server/weather.py

    # Путь в Windows (подходит любой формат)
    uv run client.py C:/projects/mcp-server/weather.py
    uv run client.py C:\\projects\\mcp-server\\weather.py
    ```

    ### Время отклика

    * Первый ответ может быть получен в течение 30 секунд.
    * Это нормально и происходит в следующих случаях:
      * Сервер инициализируется
      * Клод обрабатывает запрос
      * Инструменты выполняются
    * Последующие ответы обычно поступают быстрее.
    * Не прерывайте процесс в течение этого начального периода ожидания.

    ### Типичные сообщения об ошибках

    Если вы видите:

    * `FileNotFoundError`: Проверьте путь к файлу на сервере.
    * `Соединение отклонено`: Убедитесь, что сервер запущен и путь указан правильно.
    * `Выполнение инструмента завершилось с ошибкой`: Убедитесь, что установлены необходимые переменные среды для инструмента.
    * `Ошибка таймаута`: Рекомендуется увеличить время ожидания в конфигурации клиента.
  </Tab>

  <Tab title="TypeScript">
    [Полный код для этого урока можно найти здесь.](https://github.com/modelcontextprotocol/quickstart-resources/tree/main/mcp-client-typescript)

    ## Системные требования

    Перед началом убедитесь, что ваша система соответствует следующим требованиям:

    * Компьютер Mac или Windows
    * Установлен Node.js версии 17 или выше
    * Установлена ​​последняя версия `npm`
    * Ключ API для антропологических исследований (Клод)

    ## Настройка вашей среды

    Для начала давайте создадим и настроим наш проект:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      # Создание каталога проекта
      mkdir mcp-client-typescript
      cd mcp-client-typescript

      # Инициализация проекта npm
      npm init -y

      # Установка зависимостей
      npm install @anthropic-ai/sdk @modelcontextprotocol/sdk dotenv

      # Установка зависимостей для разработки
      npm install -D @types/node typescript

      # Создать исходный файл
      touch index.ts
      ```

      ```Тема Windows PowerShell={null}
      # Создание каталога проекта
      md mcp-client-typescript
      cd mcp-client-typescript

      # Инициализация проекта npm
      npm init -y

      # Установка зависимостей
      npm install @anthropic-ai/sdk @modelcontextprotocol/sdk dotenv

      # Установка зависимостей для разработки
      npm install -D @types/node typescript

      # Создать исходный файл
      new-item index.ts
      ```
    </CodeGroup>

    Обновите файл `package.json`, указав `type: "module"` и скрипт сборки:

    ```json package.json theme={null}
    {
      "type": "module",
      "scripts": {
        "build": "tsc && chmod 755 build/index.js"
      }
    }
    ```

    Создайте файл `tsconfig.json` в корневой директории вашего проекта:

    ```json tsconfig.json theme={null}
    {
      "compilerOptions": {
        "цель": "ES2022",
        "модуль": "Node16",
        "moduleResolution": "Node16",
        "outDir": "./build",
        "rootDir": "./",
        "строгий": истинный,
        "esModuleInterop": true,
        "skipLibCheck": true,
        "forceConsistentCasingInFileNames": true
      },
      "include": ["index.ts"],
      "исключить": ["node_modules"]
    }
    ```

    ## Настройка вашего API-ключа

    Вам потребуется ключ API Anthropic из [консоли Anthropic](https://console.anthropic.com/settings/keys).

    Создайте файл `.env` для его хранения:

    ```bash theme={null}
    echo "ANTHROPIC_API_KEY=<ваш ключ здесь>" > .env
    ```

    Добавьте `.env` в ваш файл `.gitignore`:

    ```bash theme={null}
    echo ".env" >> .gitignore
    ```

    <Предупреждение>
      Обязательно обеспечьте безопасность своего `ANTHROPIC_API_KEY`!
    </Предупреждение>

    ## Создание клиента

    ### Базовая структура клиента

    Для начала настроим импорт и создадим базовый класс клиента в файле `index.ts`:

    ```typescript theme={null}
    import { Anthropic } from "@anthropic-ai/sdk";
    импорт {
      MessageParam,
      Инструмент,
    } из "@anthropic-ai/sdk/resources/messages/messages.mjs";
    import { Client } from "@modelcontextprotocol/sdk/client/index.js";
    import { StdioClientTransport } from "@modelcontextprotocol/sdk/client/stdio.js";
    import readline from "readline/promises";
    import dotenv from "dotenv";

    dotenv.config();

    const ANTHROPIC_API_KEY = process.env.ANTHROPIC_API_KEY;
    if (!ANTHROPIC_API_KEY) {
      throw new Error("ANTHROPIC_API_KEY не установлен");
    }

    класс MCPClient {
      private mcp: Client;
      частный антропический: Антропический;
      частный транспорт: StdioClientTransport | null = null;
      частные инструменты: Tool[] = [];

      конструктор() {
        this.anthropic = new Anthropic({
          apiKey: ANTHROPIC_API_KEY,
        });
        this.mcp = new Client({ name: "mcp-client-cli", version: "1.0.0" });
      }
      // Здесь будут размещены методы
    }
    ```

    ### Управление подключением к серверу

    Далее мы реализуем метод подключения к серверу MCP:

    ```typescript theme={null}
    async connectToServer(serverScriptPath: string) {
      пытаться {
        const isJs = serverScriptPath.endsWith(".js");
        const isPy = serverScriptPath.endsWith(".py");
        if (!isJs && !isPy) {
          throw new Error("Серверный скрипт должен быть файлом .js или .py");
        }
        const command = isPy
          ? process.platform === "win32"
            ? "питон"
            : "python3"
          : process.execPath;

        this.transport = new StdioClientTransport({
          команда,
          args: [serverScriptPath],
        });
        Ожидайте this.mcp.connect(this.transport);

        const toolsResult = await this.mcp.listTools();
        this.tools = toolsResult.tools.map((tool) => {
          возвращаться {
            имя: tool.name,
            описание: tool.description,
            input_schema: tool.inputSchema,
          };
        });
        console.log(
          "Подключено к серверу с помощью инструментов:",
          this.tools.map(({ name }) => name)
        );
      } catch (e) {
        console.log("Не удалось подключиться к серверу MCP: ", e);
        бросить e;
      }
    }
    ```

    ### Логика обработки запросов

    Теперь добавим основной функционал для обработки запросов и вызовов инструментов:

    ```typescript theme={null}
    async processQuery(query: string) {
      const messages: MessageParam[] = [
        {
          роль: "пользователь",
          содержимое: запрос,
        },
      ];

      const response = await this.anthropic.messages.create({
        модель: "claude-sonnet-4-20250514",
        max_tokens: 1000,
        сообщения,
        инструменты: this.tools,
      });

      const finalText = [];

      for (const content of response.content) {
        if (content.type === "text") {
          finalText.push(content.text);
        } else if (content.type === "tool_use") {
          const toolName = content.name;
          const toolArgs = content.input as { [x: string]: unknown } | undefined;

          const result = await this.mcp.callTool({
            имя: toolName,
            аргументы: toolArgs,
          });
          finalText.push(
            `[Вызов инструмента ${toolName} с аргументами ${JSON.stringify(toolArgs)}]`
          );

          сообщения.push({
            роль: "пользователь",
            содержимое: result.content в виде строки,
          });

          const response = await this.anthropic.messages.create({
            модель: "claude-sonnet-4-20250514",
            max_tokens: 1000,
            сообщения,
          });

          finalText.push(
            response.content[0].type === "text" ? response.content[0].text : ""
          );
        }
      }

      return finalText.join("\n");
    }
    ```

    ### Интерактивный интерфейс чата

    Теперь добавим цикл чата и функцию очистки:

    ```typescript theme={null}
    async chatLoop() {
      const rl = readline.createInterface({
        вход: process.stdin,
        вывод: process.stdout,
      });

      пытаться {
        console.log("\nКлиент MCP запущен!");
        console.log("Введите ваши запросы или 'quit' для выхода.");

        пока (true) {
          const message = await rl.question("\nQuery: ");
          if (message.toLowerCase() === "quit") {
            перерыв;
          }
          const response = await this.processQuery(message);
          console.log("\n" + response);
        }
      } окончательно {
        rl.close();
      }
    }

    async cleanup() {
      Ожидайте выполнения this.mcp.close();
    }
    ```

    ### Главный вход

    Наконец, добавим основную логику выполнения:

    ```typescript theme={null}
    асинхронная функция main() {
      if (process.argv.length < 3) {
        console.log("Использование: node index.ts <путь_к_серверному_скрипту>");
        возвращаться;
      }
      const mcpClient = new MCPClient();
      пытаться {
        await mcpClient.connectToServer(process.argv[2]);
        await mcpClient.chatLoop();
      } catch (e) {
        console.error("Ошибка:", e);
        await mcpClient.cleanup();
        process.exit(1);
      } окончательно {
        await mcpClient.cleanup();
        process.exit(0);
      }
    }

    основной();
    ```

    ## Запуск клиента

    Для запуска клиента на любом сервере MCP:

    ```bash theme={null}
    # Сборка TypeScript
    npm run build

    # Запуск клиента
    node build/index.js path/to/server.py # python server
    node build/index.js path/to/build/index.js # сервер Node
    ```

    <Примечание>
      Если вы продолжаете [изучение темы погоды из руководства по быстрому запуску сервера](https://github.com/modelcontextprotocol/quickstart-resources/tree/main/weather-server-typescript), ваша команда может выглядеть примерно так: `node build/index.js .../quickstart-resources/weather-server-typescript/build/index.js`
    </Примечание>

    **Клиент будет:**

    1. Подключитесь к указанному серверу.
    2. Перечислите доступные инструменты.
    3. Начните интерактивный чат, в котором вы сможете:
       * Введите запросы
       * См. выполнение инструментов
       * Получите ответы от Клода

    ## Как это работает

    Когда вы отправляете запрос:

    1. Клиент получает список доступных инструментов с сервера.
    2. Ваш запрос отправляется Клоду вместе с описанием инструментов.
    3. Клод решает, какие инструменты (если таковые имеются) использовать.
    4. Клиент выполняет все запрошенные вызовы инструментов через сервер.
    5. Результаты отправляются обратно Клоду.
    6. Клод дает ответ на естественном языке.
    7. Ответ отображается вам.

    ## Передовые методы

    1. **Обработка ошибок**
       * Используйте систему типов TypeScript для более эффективного обнаружения ошибок.
       * Оберните вызовы инструментов в блоки try-catch
       * Предоставлять содержательные сообщения об ошибках
       * Корректно обрабатывайте проблемы с подключением

    2. **Безопасность**
       * Надежно храните ключи API в файле `.env`
       * Проверка ответов сервера
       * Будьте осторожны с правами доступа к инструментам.

    ## Поиск неисправностей

    ### Проблемы с путями к серверу

    * Дважды проверьте правильность пути к вашему серверному скрипту.
    * Используйте абсолютный путь, если относительный путь не работает.
    * Пользователям Windows следует использовать косые черты (/) или экранированные обратные косые черты (\\) в пути.
    * Убедитесь, что файл сервера имеет правильное расширение (.js для Node.js или .py для Python).

    Пример корректного использования пути:

    ```bash theme={null}
    # Относительный путь
    node build/index.js ./server/build/index.js

    # Абсолютный путь
    node build/index.js /Users/username/projects/mcp-server/build/index.js

    # Путь в Windows (подходит любой формат)
    node build/index.js C:/projects/mcp-server/build/index.js
    node build/index.js C:\\projects\\mcp-server\\build\\index.js
    ```

    ### Время отклика

    * Первый ответ может быть получен в течение 30 секунд.
    * Это нормально и происходит в следующих случаях:
      * Сервер инициализируется
      * Клод обрабатывает запрос
      * Инструменты выполняются
    * Последующие ответы обычно поступают быстрее.
    * Не прерывайте процесс в течение этого начального периода ожидания.

    ### Типичные сообщения об ошибках

    Если вы видите:

    * `Ошибка: Не удается найти модуль`: Проверьте папку сборки и убедитесь, что компиляция TypeScript прошла успешно.
    * `Соединение отклонено`: Убедитесь, что сервер запущен и путь указан правильно.
    * `Выполнение инструмента завершилось с ошибкой`: Убедитесь, что установлены необходимые переменные среды для инструмента.
    * `ANTHROPIC_API_KEY не установлен`: проверьте файл .env и переменные среды.
    * `TypeError`: Убедитесь, что вы используете правильные типы для аргументов инструмента.
    * `BadRequestError`: Убедитесь, что у вас достаточно кредитов для доступа к антропному API.
  </Tab>

  <Tab title="Java">
    <Примечание>
      Это демонстрационная версия для быстрого запуска, основанная на автоматической настройке и загрузочных шаблонах Spring AI MCP.
      Чтобы узнать, как создавать синхронные и асинхронные клиенты MCP вручную, обратитесь к документации [Java SDK Client](/sdk/java/mcp-client).
    </Примечание>

    В этом примере показано, как создать интерактивный чат-бот, который объединяет протокол контекста модели Spring AI (MCP) с [сервером MCP Brave Search](https://github.com/modelcontextprotocol/servers-archived/tree/main/src/brave-search). Приложение создает разговорный интерфейс на основе модели искусственного интеллекта Claude от Anthropic, который может выполнять поиск в интернете через Brave Search, обеспечивая взаимодействие на естественном языке с веб-данными в реальном времени.
    [Полный код для этого урока можно найти здесь.](https://github.com/spring-projects/spring-ai-examples/tree/main/model-context-protocol/web-search/brave-chatbot)

    ## Системные требования

    Перед началом убедитесь, что ваша система соответствует следующим требованиям:

    * Java 17 или выше
    * Maven 3.6+
    * Менеджер пакетов npx
    * Ключ API для антропологических исследований (Клод)
    * Ключ API Brave Search

    ## Настройка вашей среды

    1. Установите npx (выполните команду Node Package eXecute):
       Для начала убедитесь, что установили [npm](https://docs.npmjs.com/downloading-and-installing-node-js-and-npm)
       а затем выполните:

       ```bash theme={null}
       npm install -g npx
       ```

    2. Клонируйте репозиторий:

       ```bash theme={null}
       git clone https://github.com/spring-projects/spring-ai-examples.git
       cd model-context-protocol/web-search/brave-chatbot
       ```

    3. Настройте свои API-ключи:

       ```bash theme={null}
       export ANTHROPIC_API_KEY='your-anthropic-api-key-here'
       export BRAVE_API_KEY='your-brave-api-key-here'
       ```

    4. Соберите приложение:

       ```bash theme={null}
       ./mvnw чистая установка
       ```

    5. Запустите приложение с помощью Maven:
       ```bash theme={null}
       ./mvnw spring-boot:run
       ```

    <Предупреждение>
      Обязательно обеспечьте безопасность ваших ключей `ANTHROPIC_API_KEY` и `BRAVE_API_KEY`!
    </Предупреждение>

    ## Как это работает

    Приложение интегрирует Spring AI с сервером Brave Search MCP посредством нескольких компонентов:

    ### Конфигурация клиента MCP

    1. Необходимые зависимости в файле pom.xml:

    ```xml theme={null}
    <зависимость>
        <groupId>org.springframework.ai</groupId>
        <artifactId>spring-ai-starter-mcp-client</artifactId>
    </зависимость>
    <зависимость>
        <groupId>org.springframework.ai</groupId>
        <artifactId>spring-ai-starter-model-anthropic</artifactId>
    </зависимость>
    ```

    2. Свойства приложения (application.yml):

    ```yml theme={null}
    весна:
      ИИ:
        мКП:
          клиент:
            включено: true
            имя: brave-search-client
            версия: 1.0.0
            тип: SYNC
            request-timeout: 20s
            стдио:
              root-change-notification: true
              servers-configuration: classpath:/mcp-servers-config.json
            toolcallback:
              включено: true
        антропический:
          api-ключ: ${ANTHROPIC_API_KEY}
    ```

    Это активирует `spring-ai-starter-mcp-client` для создания одного или нескольких `McpClient` на основе предоставленной конфигурации сервера.
    Свойство `spring.ai.mcp.client.toolcallback.enabled=true` включает механизм обратного вызова инструментов, который автоматически регистрирует все инструменты MCP как инструменты Spring AI.
    По умолчанию эта функция отключена.

    3. Конфигурация сервера MCP (`mcp-servers-config.json`):

    ```json theme={null}
    {
      "mcpServers": {
        "brave-search": {
          "команда": "npx",
          "args": ["-y", "@modelcontextprotocol/server-brave-search"],
          "env": {
            "BRAVE_API_KEY": "<УКАЖИТЕ ВАШ КЛЮЧ API BRAVE>"
          }
        }
      }
    }
    ```

    ### Реализация чата

    Чат-бот реализован с использованием ChatClient от Spring AI с интеграцией с инструментом MCP:

    ```java theme={null}
    вар чатКлиент = чатКлиентБилдер
        .defaultSystem("Вы полезный помощник, эксперт в области ИИ и Java.")
        .defaultToolCallbacks((Object[]) mcpToolAdapter.toolCallbacks())
        .defaultAdvisors(new MessageChatMemoryAdvisor(new InMemoryChatMemory())
        .строить();
    ```

    Основные характеристики:

    * Использует модель искусственного интеллекта Claude для понимания естественного языка.
    * Интегрирует Brave Search через MCP для обеспечения возможности веб-поиска в режиме реального времени.
    * Поддерживает память для диалогов с помощью InMemoryChatMemory
    * Запускается как интерактивное приложение командной строки

    ### Сборка и запуск

    ```bash theme={null}
    ./mvnw чистая установка
    java -jar ./target/ai-mcp-brave-chatbot-0.0.1-SNAPSHOT.jar
    ```

    или

    ```bash theme={null}
    ./mvnw spring-boot:run
    ```

    Приложение запустит интерактивный чат, в котором вы сможете задавать вопросы. Чат-бот будет использовать Brave Search, когда ему потребуется найти информацию в интернете для ответа на ваши запросы.

    Чат-бот может:

    * Отвечайте на вопросы, используя встроенные знания.
    * При необходимости выполняйте поиск в интернете с помощью Brave Search.
    * Помните контекст из предыдущих сообщений в переписке.
    * Объедините информацию из нескольких источников для получения исчерпывающих ответов.

    ### Расширенные настройки

    Клиент MCP поддерживает дополнительные параметры конфигурации:

    * Настройка клиента с помощью `McpSyncClientCustomizer` или `McpAsyncClientCustomizer`
    * Множество клиентов с различными типами транспорта: `STDIO` и `SSE` (Server-Sent Events)
    * Интеграция с фреймворком выполнения инструментов Spring AI
    * Автоматическая инициализация клиента и управление жизненным циклом.

    Для приложений, использующих WebFlux, можно использовать стартовый пакет WebFlux:

    ```xml theme={null}
    <зависимость>
        <groupId>org.springframework.ai</groupId>
        <artifactId>spring-ai-mcp-client-webflux-spring-boot-starter</artifactId>
    </зависимость>
    ```

    Это обеспечивает аналогичную функциональность, но использует реализацию транспортного протокола SSE на основе WebFlux, рекомендованную для развертывания в производственной среде.
  </Tab>

  <Tab title="Kotlin">
    [Полный код для этого урока можно найти здесь.](https://github.com/modelcontextprotocol/kotlin-sdk/tree/main/samples/kotlin-mcp-client)

    ## Системные требования

    Перед началом убедитесь, что ваша система соответствует следующим требованиям:

    * Java 17 или выше
    * Ключ API для антропологических исследований (Клод)

    ## Настройка среды

    Для начала, если вы еще этого не сделали, давайте установим `java` и `gradle`.
    Вы можете скачать `java` с [официального сайта Oracle JDK](https://www.oracle.com/java/technologies/downloads/).
    Проверьте правильность установки Java:

    ```bash theme={null}
    java --version
    ```

    Теперь давайте создадим и настроим ваш проект:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      # Создаем новую директорию для нашего проекта
      mkdir kotlin-mcp-client
      cd kotlin-mcp-client

      # Инициализация нового проекта Kotlin
      gradle init
      ```

      ```Тема Windows PowerShell={null}
      # Создаем новую директорию для нашего проекта
      md kotlin-mcp-client
      cd kotlin-mcp-client
      # Инициализация нового проекта Kotlin
      gradle init
      ```
    </CodeGroup>

    После выполнения команды `gradle init` вам будут предложены варианты для создания вашего проекта.
    Выберите **Приложение** в качестве типа проекта, **Kotlin** в качестве языка программирования и **Java 17** в качестве версии Java.

    В качестве альтернативы вы можете создать приложение Kotlin, используя [мастер создания проектов IntelliJ IDEA](https://kotlinlang.org/docs/jvm-get-started.html).

    После создания проекта добавьте следующие зависимости:

    <CodeGroup>
      ```kotlin build.gradle.kts theme={null}
      val mcpVersion = "0.4.0"
      val slf4jVersion = "2.0.9"
      val anthropicVersion = "0.8.0"

      зависимости {
          implementation("io.modelcontextprotocol:kotlin-sdk:$mcpVersion")
          implementation("org.slf4j:slf4j-nop:$slf4jVersion")
          implementation("com.anthropic:anthropic-java:$anthropicVersion")
      }
      ```

      ```groovy build.gradle theme={null}
      def mcpVersion = '0.3.0'
      def slf4jVersion = '2.0.9'
      def anthropicVersion = '0.8.0'
      зависимости {
          реализация "io.modelcontextprotocol:kotlin-sdk:$mcpVersion"
          реализация "org.slf4j:slf4j-nop:$slf4jVersion"
          реализация "com.anthropic:anthropic-java:$anthropicVersion"
      }
      ```
    </CodeGroup>

    Кроме того, добавьте следующие плагины в свой скрипт сборки:

    <CodeGroup>
      ```kotlin build.gradle.kts theme={null}
      плагины {
          id("com.gradleup.shadow") version "8.3.9"
      }
      ```

      ```groovy build.gradle theme={null}
      плагины {
          id 'com.gradleup.shadow' version '8.3.9'
      }
      ```
    </CodeGroup>

    ## Настройка вашего API-ключа

    Вам потребуется ключ API Anthropic из [консоли Anthropic](https://console.anthropic.com/settings/keys).

    Настройте свой API-ключ:

    ```bash theme={null}
    export ANTHROPIC_API_KEY='your-anthropic-api-key-here'
    ```

    <Предупреждение>
      Обязательно обеспечьте безопасность своего `ANTHROPIC_API_KEY`!
    </Предупреждение>

    ## Создание клиента

    ### Базовая структура клиента

    Для начала создадим базовый класс клиента:

    ```kotlin theme={null}
    class MCPClient : AutoCloseable {
        private val anthropic = AnthropicOkHttpClient.fromEnv()
        private val mcp: Client = Client(clientInfo = Implementation(name = "mcp-client-cli", version = "1.0.0"))
        private lateinit var tools: List<ToolUnion>

        // Здесь будут размещены методы

        override fun close() {
            runBlocking {
                mcp.close()
                антропический.закрыть()
            }
        }
    ```

    ### Управление подключением к серверу

    Далее мы реализуем метод подключения к серверу MCP:

    ```kotlin theme={null}
    suspend fun connectToServer(serverScriptPath: String) {
        пытаться {
            val command = buildList {
                когда (serverScriptPath.substringAfterLast(".")) {
                    "js" -> add("node")
                    "py" -> add(if (System.getProperty("os.name").lowercase().contains("win")) "python" else "python3")
                    "jar" -> addAll(listOf("java", "-jar"))
                    иначе -> выбросить исключение IllegalArgumentException("Серверный скрипт должен быть файлом .js, .py или .jar")
                }
                add(serverScriptPath)
            }

            val process = ProcessBuilder(command).start()
            val transport = StdioClientTransport(
                input = process.inputStream.asSource().buffered(),
                output = process.outputStream.asSink().buffered()
            )

            mcp.connect(transport)

            val toolsResult = mcp.listTools()
            tools = toolsResult?.tools?.map { tool ->
                ToolUnion.ofTool(
                    Tool.builder()
                        .name(tool.name)
                        .description(tool.description ?: "")
                        .inputSchema(
                            Tool.InputSchema.builder()
                                .type(JsonValue.from(tool.inputSchema.type))
                                .properties(tool.inputSchema.properties.toJsonValue())
                                .putAdditionalProperty("required", JsonValue.from(tool.inputSchema.required))
                                .строить()
                        )
                        .строить()
                )
            } ?: emptyList()
            println("Подключено к серверу с помощью инструментов: ${tools.joinToString(", ") { it.tool().get().name() }}")
        } catch (e: Exception) {
            println("Не удалось подключиться к серверу MCP: $e")
            бросить e
        }
    }
    ```

    Также создайте вспомогательную функцию для преобразования из `JsonObject` в `JsonValue` для Anthropic:

    ```kotlin theme={null}
    private fun JsonObject.toJsonValue(): JsonValue {
        val mapper = ObjectMapper()
        val node = mapper.readTree(this.toString())
        return JsonValue.fromJsonNode(node)
    }
    ```

    ### Логика обработки запросов

    Теперь добавим основной функционал для обработки запросов и вызовов инструментов:

    ```kotlin theme={null}
    private val messageParamsBuilder: MessageCreateParams.Builder = MessageCreateParams.builder()
        .model(Model.CLAUDE_SONNET_4_20250514)
        .maxTokens(1024)

    suspend fun processQuery(query: String): String {
        val messages = mutableListOf(
            MessageParam.builder()
                .role(MessageParam.Role.USER)
                .content(query)
                .строить()
        )

        val response = anthropic.messages().create(
            messageParamsBuilder
                .messages(messages)
                .tools(tools)
                .строить()
        )

        val FinalText = mutableListOf<String>()
        response.content().forEach { content ->
            когда {
                content.isText() -> FinalText.add(content.text().getOrNull()?.text() ?: "")

                content.isToolUse() -> {
                    val toolName = content.toolUse().get().name()
                    val toolArgs =
                        content.toolUse().get()._input().convert(object : TypeReference<Map<String, JsonValue>>() {})

                    val result = mcp.callTool(
                        имя = toolName,
                        arguments = toolArgs ?: emptyMap()
                    )
                    finalText.add("[Вызывающий инструмент $toolName с аргументами $toolArgs]")

                    messages.add(
                        MessageParam.builder()
                            .role(MessageParam.Role.USER)
                            .содержание(
                                """
                                    "type": "tool_result",
                                    "tool_name": $toolName,
                                    "result": ${result?.content?.joinToString("\n") { (it as TextContent).text ?: "" }}
                                """.trimIndent()
                            )
                            .строить()
                    )

                    val aiResponse = anthropic.messages().create(
                        messageParamsBuilder
                            .messages(messages)
                            .строить()
                    )

                    FinalText.add(aiResponse.content().first().text().getOrNull()?.text() ?: "")
                }
            }
        }

        return finalText.joinToString("\n", prefix = "", postfix = "")
    }
    ```

    ### Интерактивный чат

    Мы добавим цикл чата:

    ```kotlin theme={null}
    suspend fun chatLoop() {
        println("\nКлиент MCP запущен!")
        println("Введите ваши запросы или 'quit' для выхода.")

        пока (true) {
            print("\nЗапрос: ")
            val message = readLine() ?: break
            if (message.lowercase() == "quit") break
            val response = processQuery(message)
            println("\n$response")
        }
    }
    ```

    ### Главный вход

    Наконец, добавим основную функцию выполнения:

    ```kotlin theme={null}
    fun main(args: Array<String>) = runBlocking {
        if (args.isEmpty()) throw IllegalArgumentException("Usage: java -jar <your_path>/build/libs/kotlin-mcp-client-0.1.0-all.jar <path_to_server_script>")
        val serverPath = args.first()
        val client = MCPClient()
        client.use {
            client.connectToServer(serverPath)
            client.chatLoop()
        }
    }
    ```

    ## Запуск клиента

    Для запуска клиента на любом сервере MCP:

    ```bash theme={null}
    ./gradlew build

    # Запуск клиента
    java -jar build/libs/<your-jar-name>.jar path/to/server.jar # jvm server
    java -jar build/libs/<your-jar-name>.jar path/to/server.py # python server
    java -jar build/libs/<your-jar-name>.jar path/to/build/index.js # сервер Node
    ```

    <Примечание>
      Если вы продолжаете изучение темы погоды из руководства по быстрому запуску сервера, ваша команда может выглядеть примерно так: `java -jar build/libs/kotlin-mcp-client-0.1.0-all.jar .../samples/weather-stdio-server/build/libs/weather-stdio-server-0.1.0-all.jar`
    </Примечание>

    **Клиент будет:**

    1. Подключитесь к указанному серверу.
    2. Перечислите доступные инструменты.
    3. Начните интерактивный чат, в котором вы сможете:
       * Введите запросы
       * См. выполнение инструментов
       * Получите ответы от Клода

    ## Как это работает

    Вот схема рабочего процесса высокого уровня:

    ```тема русалки={null}
    ---
    конфигурация:
        тема: нейтральная
    ---
    диаграмма последовательности
        актёр Пользователь
        участник Клиент
        участник Клод
        участник MCP_Server как MCP Server
        Инструменты участника

        Пользователь->>Клиент: Отправить запрос
        Клиент <<->> MCP_Сервер: Получить доступные инструменты
        Клиент->>Клод: Отправьте запрос с описанием инструментов.
        Клод-->>Клиент: Принять решение об использовании инструмента
        Клиент->>MCP_Сервер: Запрос на выполнение инструмента
        MCP_Server->>Инструменты: Выполнить выбранные инструменты
        Инструменты-->>MCP_Server: Возврат результатов
        MCP_Server-->>Client: Отправить результаты
        Клиент->>Клод: Отправить результаты работы инструмента
        Клод-->>Клиент: Предоставьте окончательный ответ
        Клиент-->>Пользователь: Отобразить ответ
    ```

    Когда вы отправляете запрос:

    1. Клиент получает список доступных инструментов с сервера.
    2. Ваш запрос отправляется Клоду вместе с описанием инструментов.
    3. Клод решает, какие инструменты (если таковые имеются) использовать.
    4. Клиент выполняет все запрошенные вызовы инструментов через сервер.
    5. Результаты отправляются обратно Клоду.
    6. Клод дает ответ на естественном языке.
    7. Ответ отображается вам.

    ## Передовые методы

    1. **Обработка ошибок**
       * Используйте систему типов Kotlin для явного моделирования ошибок.
       * При возможности возникновения исключений, оборачивайте вызовы внешних инструментов и API в блоки `try-catch`.
       * Предоставляйте четкие и понятные сообщения об ошибках.
       * Корректно обрабатывать таймауты сети и проблемы с подключением.

    2. **Безопасность**
       * Надежно храните ключи и секреты API в файле `local.properties`, переменных окружения или менеджерах секретов.
       * Проверяйте все внешние ответы, чтобы избежать непредвиденного или небезопасного использования данных.
       * Будьте осторожны с правами доступа и границами доверия при использовании инструментов.

    ## Поиск неисправностей

    ### Проблемы с путями к серверу

    * Дважды проверьте правильность пути к вашему серверному скрипту.
    * Используйте абсолютный путь, если относительный путь не работает.
    * Пользователям Windows следует использовать косые черты (/) или экранированные обратные косые черты (\\) в пути.
    * Убедитесь, что установлена ​​необходимая среда выполнения (java для Java, npm для Node.js или uv для Python).
    * Убедитесь, что файл сервера имеет правильное расширение (.jar для Java, .js для Node.js или .py для Python).

    Пример корректного использования пути:

    ```bash theme={null}
    # Относительный путь
    java -jar build/libs/client.jar ./server/build/libs/server.jar

    # Абсолютный путь
    java -jar build/libs/client.jar /Users/username/projects/mcp-server/build/libs/server.jar

    # Путь в Windows (подходит любой формат)
    java -jar build/libs/client.jar C:/projects/mcp-server/build/libs/server.jar
    java -jar build/libs/client.jar C:\\projects\\mcp-server\\build\\libs\\server.jar
    ```

    ### Время отклика

    * Первый ответ может быть получен в течение 30 секунд.
    * Это нормально и происходит в следующих случаях:
      * Сервер инициализируется
      * Клод обрабатывает запрос
      * Инструменты выполняются
    * Последующие ответы обычно поступают быстрее.
    * Не прерывайте процесс в течение этого начального периода ожидания.

    ### Типичные сообщения об ошибках

    Если вы видите:

    * `Соединение отклонено`: Убедитесь, что сервер запущен и путь указан правильно.
    * `Выполнение инструмента завершилось с ошибкой`: Убедитесь, что установлены необходимые переменные среды для инструмента.
    * `ANTHROPIC_API_KEY не установлен`: Проверьте переменные среды.
  </Tab>

  <Tab title="C#">
    [Полный код для этого урока можно найти здесь.](https://github.com/modelcontextprotocol/csharp-sdk/tree/main/samples/QuickstartClient)

    ## Системные требования

    Перед началом убедитесь, что ваша система соответствует следующим требованиям:

    * .NET 8.0 или выше
    * Ключ API для антропологических исследований (Клод)
    * Windows, Linux или macOS

    ## Настройка среды

    Сначала создайте новый проект .NET:

    ```bash theme={null}
    dotnet new console -n QuickstartClient
    cd QuickstartClient
    ```

    Затем добавьте необходимые зависимости в свой проект:

    ```bash theme={null}
    dotnet add package ModelContextProtocol --prerelease
    dotnet add package Anthropic.SDK
    dotnet add package Microsoft.Extensions.Hosting
    dotnet add package Microsoft.Extensions.AI
    ```

    ## Настройка вашего API-ключа

    Вам потребуется ключ API Anthropic из [консоли Anthropic](https://console.anthropic.com/settings/keys).

    ```bash theme={null}
    dotnet user-secrets init
    dotnet user-secrets set "ANTHROPIC_API_KEY" "<ваш ключ здесь>"
    ```

    ## Создание клиента

    ### Базовая структура клиента

    Для начала давайте настроим базовый класс клиента в файле `Program.cs`:

    ```csharp theme={null}
    с использованием Anthropic.SDK;
    с использованием Microsoft.Extensions.AI;
    с использованием Microsoft.Extensions.Configuration;
    с использованием Microsoft.Extensions.Hosting;
    using ModelContextProtocol.Client;
    using ModelContextProtocol.Protocol.Transport;

    var builder = Host.CreateApplicationBuilder(args);

    builder.Configuration
        .AddEnvironmentVariables()
        .AddUserSecrets<Program>();
    ```

    Это закладывает основу для консольного приложения .NET, которое может считывать ключ API из секретных данных пользователя.

    Далее мы настроим клиент MCP:

    ```csharp theme={null}
    var (command, arguments) = GetCommandAndArguments(args);

    вар clientTransport = новый StdioClientTransport(new()
    {
        Имя = "Демо-сервер",
        Команда = команда,
        Аргументы = аргументы,
    });

    await using var mcpClient = await McpClient.CreateAsync(clientTransport);

    var tools = await mcpClient.ListToolsAsync();
    foreach (var tool in tools)
    {
        Console.WriteLine($"Подключено к серверу с помощью инструментов: {tool.Name}");
    }
    ```

    Добавьте эту функцию в конец файла `Program.cs`:

    ```csharp theme={null}
    static (string command, string[] arguments) GetCommandAndArguments(string[] args)
    {
        возвращаемый аргумент переключатель
        {
            [var script] when script.EndsWith(".py") => ("python", args),
            [var script] when script.EndsWith(".js") => ("node", args),
            [var script] when Directory.Exists(script) || (File.Exists(script) && script.EndsWith(".csproj")) => ("dotnet", ["run", "--project", script, "--no-build"]),
            _ => throw new NotSupportedException("Предоставлен неподдерживаемый серверный скрипт. Поддерживаемые скрипты: .py, .js или .csproj")
        };
    }
    ```

    Это создаст клиент MCP, который подключится к серверу, указанному в качестве аргумента командной строки. Затем он отобразит список доступных инструментов с подключенного сервера.

    ### Логика обработки запросов

    Теперь добавим основной функционал для обработки запросов и вызовов инструментов:

    ```csharp theme={null}
    using var anthropicClient = new AnthropicClient(new APIAuthentication(builder.Configuration["ANTHROPIC_API_KEY"]))
        .Сообщения
        .AsBuilder()
        .UseFunctionInvocation()
        .Строить();

    var options = new ChatOptions
    {
        MaxOutputTokens = 1000,
        ModelId = "claude-sonnet-4-20250514",
        Инструменты = [.. инструменты]
    };

    Console.ForegroundColor = ConsoleColor.Green;
    Console.WriteLine("Клиент MCP запущен!");
    Console.ResetColor();

    PromptForInput();
    while(Console.ReadLine() is string query && !"exit".Equals(query, StringComparison.OrdinalIgnoreCase))
    {
        if (string.IsNullOrWhiteSpace(query))
        {
            PromptForInput();
            продолжать;
        }

        await foreach (var message in anthropicClient.GetStreamingResponseAsync(query, options))
        {
            Console.Write(message);
        }
        Console.WriteLine();

        PromptForInput();
    }

    static void PromptForInput()
    {
        Console.WriteLine("Введите команду (или 'exit' для выхода):");
        Console.ForegroundColor = ConsoleColor.Cyan;
        Console.Write("> ");
        Console.ResetColor();
    }
    ```

    ## Объяснение ключевых компонентов

    ### 1. Инициализация клиента

    * Инициализация клиента осуществляется с помощью `McpClient.CreateAsync()`, которая задает тип транспорта и команду для запуска сервера.

    ### 2. Подключение к серверу

    * Поддерживает серверы на Python, Node.js и .NET.
    * Сервер запускается с помощью команды, указанной в аргументах.
    * Настраивает использование стандартного ввода-вывода (stdio) для связи с сервером.
    * Инициализирует сессию и доступные инструменты.

    ### 3. Обработка запросов

    * Использует [Microsoft.Extensions.AI](https://learn.microsoft.com/dotnet/ai/ai-extensions) для чат-клиента.
    * Настраивает `IChatClient` для использования автоматического вызова инструментов (функций).
    * Клиент считывает ввод пользователя и отправляет его на сервер.
    * Сервер обрабатывает запрос и возвращает ответ.
    * Ответ отображается пользователю.

    ## Запуск клиента

    Для запуска клиента на любом сервере MCP:

    ```bash theme={null}
    dotnet run --path/to/server.csproj # dotnet server
    dotnet run --path/to/server.py # сервер Python
    dotnet run --path/to/server.js # сервер Node.js
    ```

    <Примечание>
      Если вы продолжаете изучение темы погоды из руководства по быстрому запуску сервера, ваша команда может выглядеть примерно так: `dotnet run -- path/to/QuickstartWeatherServer`.
    </Примечание>

    Клиент будет:

    1. Подключитесь к указанному серверу.
    2. Перечислите доступные инструменты.
    3. Начните интерактивный чат, в котором вы сможете:
       * Введите запросы
       * См. выполнение инструментов
       * Получите ответы от Клода
    4. Завершите сессию по окончании.

    Вот пример того, как это должно выглядеть при подключении к серверу прогноза погоды (быстрый запуск):

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-dotnet-client.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=fcf28dde150d6db879402ad8150c6b23" data-og-width="1115" width="1115" data-og-height="666" height="666" data-path="images/quickstart-dotnet-client.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-dotnet-client.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0c82cdfe1350b4a924a44d7beaa39f70 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-dotnet-client.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=4fd6f3ed867741b44ae12940788be646 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-dotnet-client.png?w=8 40&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=1b5fcfaf8b63b9ea71bf36aa20388a28 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-dotnet-client.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=cb969889d05ec8771c12b887f2940c7d 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-dotnet-client.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=81b2cb62f60a9f3afb2d66cf3ee3df79 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-dotnet-client.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=ac9271a3dd0d7b424bb390ad0c31e14e 2500 Вт" />
    </Frame>
  </Tab>
</Вкладки>

## Следующие шаги

<CardGroup cols={2}>
  <Card title="Примеры серверов" icon="grid" href="/examples">
    Ознакомьтесь с нашей галереей официальных серверов и реализаций MCP.
  </Карточка>

  <Card title="Примеры клиентов" icon="кубы" href="/клиенты">
    Просмотрите список клиентов, поддерживающих интеграцию с MCP.
  </Карточка>
</CardGroup>