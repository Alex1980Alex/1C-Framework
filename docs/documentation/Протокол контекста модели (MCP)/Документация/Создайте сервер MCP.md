> ## Индекс документации
Полный индекс документации доступен по адресу: https://modelcontextprotocol.io/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Создание сервера MCP

Начните создавать собственный сервер для использования в Claude for Desktop и других клиентских приложениях.

В этом уроке мы создадим простой сервер погоды для MCP и подключим его к хосту Claude for Desktop.

### Что мы будем строить

Мы создадим сервер, который будет предоставлять доступ к двум инструментам: `get_alerts` и `get_forecast`. Затем мы подключим сервер к хосту MCP (в данном случае, Claude for Desktop):

<Рамка>
  <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=dce7b2f8a06c20ba358e4bd2e75fa4c7" data-og-width="2780" width="2780" data-og-height="1849" height="1849" data-path="images/current-weather.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=bbb19f34c5df59f66bc6bbb75d2bc5ed 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=2392d7e765b897c5b78f9f53d41439d4 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=dc349e75341b046d35a649762774da49 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=deeb99214d9383ee4a0c8aaacb120049 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=5c6f948059635e376deeadce3893e9b9 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=3922160478785cc88d5e98d418e8f7dd 2500 Вт" />
</Frame>

<Примечание>
  Серверы могут подключаться к любому клиенту. Для простоты мы выбрали Claude для настольных приложений, но у нас также есть руководства по [созданию собственного клиента](/docs/develop/build-client), а также [список других клиентов здесь](/clients).
</Примечание>

### Основные концепции MCP

Серверы MCP могут предоставлять три основных типа возможностей:

1. **[Ресурсы](/docs/learn/server-concepts#resources)**: Файлоподобные данные, которые могут быть прочитаны клиентами (например, ответы API или содержимое файлов).
2. **[Инструменты](/docs/learn/server-concepts#tools)**: Функции, которые могут быть вызваны LLM (с согласия пользователя)
3. **[Подсказки](/docs/learn/server-concepts#prompts)**: Предварительно написанные шаблоны, помогающие пользователям выполнять определенные задачи.

В этом руководстве основное внимание будет уделено инструментам.

<Вкладки>
  <Tab title="Python">
    Давайте начнём создавать наш сервер погоды! [Полный код того, что мы будем создавать, вы найдёте здесь.](https://github.com/modelcontextprotocol/quickstart-resources/tree/main/weather-server-python)

    ### Необходимые предварительные знания

    Данное краткое руководство предполагает, что вы знакомы со следующими темами:

    * Python
    * Магистранты, такие как Клод

    ### Вход на серверы MCP

    При внедрении MCP-серверов следует внимательно относиться к обработке логов:

    **Для серверов, использующих STDIO:** Никогда не записывайте данные в стандартный вывод (stdout). Это включает в себя:

    * Операторы `print()` в Python
    * `console.log()` в JavaScript
    * `fmt.Println()` в Go
    * Аналогичные функции вывода в стандартный поток вывода в других языках

    Запись в стандартный вывод приведет к искажению сообщений JSON-RPC и поломке вашего сервера.

    **Для HTTP-серверов:** Стандартное логирование вполне подходит, поскольку оно не мешает HTTP-ответам.

    ### Передовые методы

    1. Используйте библиотеку для ведения журналов, которая записывает данные в стандартный поток ошибок (stderr) или файлы.
    2. В Python следует быть особенно осторожным — функция `print()` по умолчанию выводит данные в стандартный поток вывода.

    ### Краткие примеры

    ```python theme={null}
    # ❌ Плохо (STDIO)
    print("Обработка запроса")

    # ✅ Хорошо (STDIO)
    импорт логирования
    logging.info("Обработка запроса")
    ```

    ### Системные требования

    * Установлен Python 3.10 или более поздней версии.
    * Необходимо использовать Python MCP SDK версии 1.2.0 или выше.

    ### Настройка среды

    Для начала установим `uv` и настроим наш проект и среду Python:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      curl -LsSf https://astral.sh/uv/install.sh | sh
      ```

      ```Тема Windows PowerShell={null}
      powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
      ```
    </CodeGroup>

    После этого обязательно перезапустите терминал, чтобы команда `uv` была успешно выполнена.

    Теперь давайте создадим и настроим наш проект:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      # Создаем новую директорию для нашего проекта
      УФ-излучение и начальная погода
      погода на компакт-диске

      # Создать виртуальное окружение и активировать его
      uv venv
      источник .venv/bin/activate

      # Установка зависимостей
      uv add "mcp[cli]" httpx

      # Создайте файл сервера
      touch weather.py
      ```

      ```Тема Windows PowerShell={null}
      # Создаем новую директорию для нашего проекта
      УФ-излучение и начальная погода
      погода на компакт-диске

      # Создать виртуальное окружение и активировать его
      uv venv
      .venv\Scripts\activate

      # Установка зависимостей
      uv add mcp[cli] httpx

      # Создайте файл сервера
      новый элемент weather.py
      ```
    </CodeGroup>

    Теперь давайте перейдем к созданию вашего сервера.

    ## Создание вашего сервера

    ### Импорт пакетов и настройка экземпляра

    Добавьте это в начало файла `weather.py`:

    ```python theme={null}
    из набора текста импортировать Any

    импорт httpx
    from mcp.server.fastmcp import FastMCP

    # Инициализация сервера FastMCP
    mcp = FastMCP("weather")

    # Константы
    NWS_API_BASE = "https://api.weather.gov"
    USER_AGENT = "weather-app/1.0"
    ```

    Класс FastMCP использует подсказки типов Python и строки документации для автоматической генерации определений инструментов, что упрощает создание и поддержку инструментов MCP.

    ### Вспомогательные функции

    Далее добавим вспомогательные функции для запроса и форматирования данных из API Национальной метеорологической службы:

    ```python theme={null}
    async def make_nws_request(url: str) -> dict[str, Any] | None:
        «Отправьте запрос к API NWS с надлежащей обработкой ошибок».
        headers = {"User-Agent": USER_AGENT, "Accept": "application/geo+json"}
        асинхронный режим с использованием httpx.AsyncClient() в качестве клиента:
            пытаться:
                response = await client.get(url, headers=headers, timeout=30.0)
                response.raise_for_status()
                return response.json()
            за исключением исключения:
                вернуть None


    def format_alert(feature: dict) -> str:
        «Преобразовать функцию оповещения в читаемую строку».
        props = feature["properties"]
        return f"""
    Событие: {props.get("event", "Unknown")}
    Площадь: {props.get("areaDesc", "Unknown")}
    Уровень серьезности: {props.get("severity", "Unknown")}
    Описание: {props.get("description", "Описание отсутствует")}
    Инструкции: {props.get("инструкция", "Конкретные инструкции не предоставлены")}
    """
    ```

    ### Реализация выполнения инструмента

    Обработчик выполнения инструментов отвечает за фактическое выполнение логики каждого инструмента. Давайте добавим его:

    ```python theme={null}
    @mcp.tool()
    async def get_alerts(state: str) -> str:
        Получайте оповещения о погоде для штата США.

        Аргументы:
            Штат: Двухбуквенный код штата США (например, Калифорния, Нью-Йорк)
        """
        url = f"{NWS_API_BASE}/alerts/active/area/{state}"
        data = await make_nws_request(url)

        если данные отсутствуют или "признаки" отсутствуют в данных:
            Возвращается сообщение "Не удалось получить оповещения или оповещения не найдены."

        if not data["features"]:
            Возвращается сообщение "В этом штате нет активных оповещений."

        alerts = [format_alert(feature) for feature in data["features"]]
        return "\n---\n".join(alerts)


    @mcp.tool()
    async def get_forecast(latitude: float, longitude: float) -> str:
        «Получите прогноз погоды для выбранного места.»

        Аргументы:
            широта: Широта местоположения
            долгота: Долгота местоположения
        """
        # Сначала получите конечную точку сетки прогноза
        points_url = f"{NWS_API_BASE}/points/{latitude},{longitude}"
        points_data = await make_nws_request(points_url)

        if not points_data:
            return "Не удалось получить данные прогноза для этого местоположения."

        # Получаем URL-адрес прогноза из ответа с данными о точках
        forecast_url = points_data["properties"]["forecast"]
        forecast_data = await make_nws_request(forecast_url)

        if not forecast_data:
            Возвращается сообщение "Не удалось получить подробный прогноз."

        # Преобразовать периоды в удобочитаемый прогноз
        periods = forecast_data["properties"]["periods"]
        прогнозы = []
        for period in periods[:5]: # Отображать только следующие 5 периодов
            прогноз = f"""
    {period["name"]}:
    Температура: {period["temperature"]}°{period["temperatureUnit"]}
    Ветер: {период["windSpeed"]} {период["windDirection"]}
    Прогноз: {period["detailedForecast"]}
    """
            forecasts.append(forecast)

        return "\n---\n".join(forecasts)
    ```

    ### Запуск сервера

    Наконец, давайте инициализируем и запустим сервер:

    ```python theme={null}
    def main():
        # Инициализация и запуск сервера
        mcp.run(transport="stdio")


    если __name__ == "__main__":
        основной()
    ```

    Ваш сервер готов! Запустите `uv run weather.py`, чтобы запустить сервер MCP, который будет принимать сообщения от хостов MCP.

    Теперь давайте протестируем ваш сервер, используя уже имеющийся хост MCP, Claude for Desktop.

    ## Тестирование вашего сервера с помощью Claude for Desktop

    <Примечание>
      Claude for Desktop пока недоступен для Linux. Пользователи Linux могут перейти к руководству [Создание клиента](/docs/develop/build-client), чтобы создать клиент MCP, который будет подключаться к только что созданному серверу.
    </Примечание>

    Для начала убедитесь, что у вас установлена ​​программа Claude для настольных компьютеров. [Вы можете установить последнюю версию]
    [Здесь.](https://claude.ai/download) Если у вас уже установлена ​​версия Claude для настольных компьютеров, **убедитесь, что она обновлена ​​до последней версии.**

    Нам потребуется настроить Claude for Desktop для тех серверов MCP, которые вы хотите использовать. Для этого откройте файл конфигурации приложения Claude for Desktop по адресу `~/Library/Application Support/Claude/claude_desktop_config.json` в текстовом редакторе. Убедитесь, что файл создан, если он еще не существует.

    Например, если у вас установлен [VS Code](https://code.visualstudio.com/):

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      код ~/Library/Application\ Support/Claude/claude_desktop_config.json
      ```

      ```Тема Windows PowerShell={null}
      код $env:AppData\Claude\claude_desktop_config.json
      ```
    </CodeGroup>

    Затем вам нужно будет добавить свои серверы в ключ `mcpServers`. Элементы пользовательского интерфейса MCP отобразятся в Claude for Desktop только в том случае, если хотя бы один сервер будет правильно настроен.

    В этом случае мы добавим наш единственный сервер погоды следующим образом:

    <CodeGroup>
      ```json macOS/Linux theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "uv",
            "args": [
              "--каталог",
              "/АБСОЛЮТНЫЙ/ПУТЬ/К/РОДИТЕЛЬСКОЙ/ПАПКЕ/погода",
              "бегать",
              "weather.py"
            ]
          }
        }
      }
      ```

      ```json Windows theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "uv",
            "args": [
              "--каталог",
              "C:\\ABSOLUTE\\PATH\\TO\\PARENT\\FOLDER\\weather",
              "бегать",
              "weather.py"
            ]
          }
        }
      }
      ```
    </CodeGroup>

    <Предупреждение>
      Возможно, вам потребуется указать полный путь к исполняемому файлу `uv` в поле `command`. Это можно сделать, выполнив команду `which uv` в macOS/Linux или `where uv` в Windows.
    </Предупреждение>

    <Примечание>
      Убедитесь, что вы указываете абсолютный путь к вашему серверу. Это можно сделать, запустив команду `pwd` в macOS/Linux или `cd` в командной строке Windows. В Windows не забудьте использовать двойные обратные косые черты (`\\`) или прямые косые черты (`/`) в пути JSON.
    </Примечание>

    Это сообщает Claude for Desktop:

    1. Существует сервер MCP под названием "weather".
    2. Чтобы запустить его, выполните команду `uv --directory /ABSOLUTE/PATH/TO/PARENT/FOLDER/weather run weather.py`

    Сохраните файл и перезапустите **Claude for Desktop**.
  </Tab>

  <Tab title="TypeScript">
    Давайте начнём создавать наш сервер погоды! [Полный код того, что мы будем создавать, вы найдёте здесь.](https://github.com/modelcontextprotocol/quickstart-resources/tree/main/weather-server-typescript)

    ### Необходимые предварительные знания

    Данное краткое руководство предполагает, что вы знакомы со следующими темами:

    * TypeScript
    * Магистранты, такие как Клод

    ### Вход на серверы MCP

    При внедрении MCP-серверов следует внимательно относиться к обработке логов:

    **Для серверов, использующих STDIO:** Никогда не записывайте данные в стандартный вывод (stdout). Это включает в себя:

    * Операторы `print()` в Python
    * `console.log()` в JavaScript
    * `fmt.Println()` в Go
    * Аналогичные функции вывода в стандартный поток вывода в других языках

    Запись в стандартный вывод приведет к искажению сообщений JSON-RPC и поломке вашего сервера.

    **Для HTTP-серверов:** Стандартное логирование вполне подходит, поскольку оно не мешает HTTP-ответам.

    ### Передовые методы

    1. Используйте библиотеку для логирования, которая записывает данные в stderr или файлы, например `logging` в Python.
    2. В случае с JavaScript следует быть особенно осторожным — `console.log()` по умолчанию выводит данные в стандартный поток вывода.

    ### Краткие примеры

    ```javascript theme={null}
    // ❌ Плохо (STDIO)
    console.log("Сервер запущен");

    // ✅ Хорошо (STDIO)
    console.error("Сервер запущен"); // stderr безопасен
    ```

    ### Системные требования

    Для работы с TypeScript убедитесь, что у вас установлена ​​последняя версия Node.

    ### Настройка среды

    Для начала, если вы ещё этого не сделали, давайте установим Node.js и npm. Вы можете скачать их с сайта [nodejs.org](https://nodejs.org/).
    Проверьте правильность установки Node.js:

    ```bash theme={null}
    node --version
    npm --version
    ```

    Для этого урока вам потребуется Node.js версии 16 или выше.

    Теперь давайте создадим и настроим наш проект:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      # Создаем новую директорию для нашего проекта
      погода mkdir
      погода на компакт-диске

      # Инициализация нового проекта npm
      npm init -y

      # Установка зависимостей
      npm install @modelcontextprotocol/sdk zod@3
      npm install -D @types/node typescript

      # Создайте наши файлы
      mkdir src
      touch src/index.ts
      ```

      ```Тема Windows PowerShell={null}
      # Создаем новую директорию для нашего проекта
      погода в штате Мэриленд
      погода на компакт-диске

      # Инициализация нового проекта npm
      npm init -y

      # Установка зависимостей
      npm install @modelcontextprotocol/sdk zod@3
      npm install -D @types/node typescript

      # Создайте наши файлы
      md src
      new-item src\index.ts
      ```
    </CodeGroup>

    Обновите файл package.json, добавив type: "module" и скрипт сборки:

    ```json package.json theme={null}
    {
      "type": "module",
      "bin": {
        "погода": "./build/index.js"
      },
      "scripts": {
        "build": "tsc && chmod 755 build/index.js"
      },
      "файлы": ["сборка"]
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
        "rootDir": "./src",
        "строгий": истинный,
        "esModuleInterop": true,
        "skipLibCheck": true,
        "forceConsistentCasingInFileNames": true
      },
      "include": ["src/**/*"],
      "исключить": ["node_modules"]
    }
    ```

    Теперь давайте перейдем к созданию вашего сервера.

    ## Создание вашего сервера

    ### Импорт пакетов и настройка экземпляра

    Добавьте эти строки в начало файла `src/index.ts`:

    ```typescript theme={null}
    import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
    import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
    import { z } from "zod";

    const NWS_API_BASE = "https://api.weather.gov";
    const USER_AGENT = "weather-app/1.0";

    // Создать экземпляр сервера
    const server = new McpServer({
      имя: "погода",
      версия: "1.0.0",
    });
    ```

    ### Вспомогательные функции

    Далее добавим вспомогательные функции для запроса и форматирования данных из API Национальной метеорологической службы:

    ```typescript theme={null}
    // Вспомогательная функция для выполнения запросов к NWS API
    async function makeNWSRequest<T>(url: string): Promise<T | null> {
      const headers = {
        "User-Agent": USER_AGENT,
        Принять: "application/geo+json",
      };

      пытаться {
        const response = await fetch(url, { headers });
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }
        return (await response.json()) as T;
      } catch (error) {
        console.error("Ошибка при выполнении запроса NWS:", error);
        вернуть null;
      }
    }

    интерфейс AlertFeature {
      характеристики: {
        событие?: строка;
        areaDesc?: string;
        серьезность?: строка;
        статус?: строка;
        заголовок?: строка;
      };
    }

    // Форматирование данных оповещения
    function formatAlert(feature: AlertFeature): string {
      const props = feature.properties;
      возвращаться [
        `Событие: ${props.event || "Неизвестно"}`,
        `Area: ${props.areaDesc || "Unknown"}`,
        `Уровень серьезности: ${props.severity || "Неизвестно"}`,
        `Статус: ${props.status || "Неизвестно"}`,
        `Заголовок: ${props.headline || "Нет заголовка"}`,
        "---",
      ].join("\n");
    }

    интерфейс ForecastPeriod {
      имя?: строка;
      температура?: число;
      temperatureUnit?: string;
      windSpeed?: string;
      windDirection?: string;
      shortForecast?: string;
    }

    интерфейс AlertsResponse {
      features: AlertFeature[];
    }

    интерфейс PointsResponse {
      характеристики: {
        прогноз?: строка;
      };
    }

    интерфейс ForecastResponse {
      характеристики: {
        периоды: ForecastPeriod[];
      };
    }
    ```

    ### Реализация выполнения инструмента

    Обработчик выполнения инструментов отвечает за фактическое выполнение логики каждого инструмента. Давайте добавим его:

    ```typescript theme={null}
    // Регистрация инструментов для работы с погодой

    server.registerTool(
      "get_alerts",
      {
        описание: "Получайте оповещения о погоде для штата",
        inputSchema: {
          состояние: z
            .нить()
            .length(2)
            .describe("Двухбуквенный код штата (например, CA, NY)"),
        },
      },
      async ({ state }) => {
        const stateCode = state.toUpperCase();
        const alertsUrl = `${NWS_API_BASE}/alerts?area=${stateCode}`;
        const alertsData = await makeNWSRequest<AlertsResponse>(alertsUrl);

        if (!alertsData) {
          возвращаться {
            содержание: [
              {
                тип: "текст",
                Текст: "Не удалось получить данные оповещений",
              },
            ],
          };
        }

        const features = alertsData.features || [];
        if (features.length === 0) {
          возвращаться {
            содержание: [
              {
                тип: "текст",
                текст: `Нет активных оповещений для ${stateCode}`,
              },
            ],
          };
        }

        const formattedAlerts = features.map(formatAlert);
        const alertsText = `Активные оповещения для ${stateCode}:\n\n${formattedAlerts.join("\n")}`;

        возвращаться {
          содержание: [
            {
              тип: "текст",
              текст: alertText,
            },
          ],
        };
      },
    );

    server.registerTool(
      "get_forecast",
      {
        Описание: "Получить прогноз погоды для указанного места",
        inputSchema: {
          широта: z
            .число()
            .мин(-90)
            .max(90)
            .describe("Широта местоположения"),
          долгота: z
            .число()
            .мин(-180)
            .max(180)
            .describe("Долгота местоположения"),
        },
      },
      async ({ latitude, longitude }) => {
        // Получение данных по точкам сетки
        const pointsUrl = `${NWS_API_BASE}/points/${latitude.toFixed(4)},${longitude.toFixed(4)}`;
        const pointsData = await makeNWSRequest<PointsResponse>(pointsUrl);

        if (!pointsData) {
          возвращаться {
            содержание: [
              {
                тип: "текст",
                Текст: `Не удалось получить данные о точках сетки для координат: ${широта}, ${долгота}. Это местоположение может не поддерживаться API NWS (поддерживаются только местоположения в США).`
              },
            ],
          };
        }

        const forecastUrl = pointsData.properties?.forecast;
        if (!forecastUrl) {
          возвращаться {
            содержание: [
              {
                тип: "текст",
                Текст: "Не удалось получить URL-адрес прогноза из данных по точкам сетки".
              },
            ],
          };
        }

        // Получить данные прогноза
        const forecastData = await makeNWSRequest<ForecastResponse>(forecastUrl);
        if (!forecastData) {
          возвращаться {
            содержание: [
              {
                тип: "текст",
                Текст: "Не удалось получить данные прогноза",
              },
            ],
          };
        }

        const periods = forecastData.properties?.periods || [];
        if (periods.length === 0) {
          возвращаться {
            содержание: [
              {
                тип: "текст",
                Текст: "Прогнозные периоды отсутствуют",
              },
            ],
          };
        }

        // Форматирование периодов прогнозирования
        const formattedForecast = periods.map((period: ForecastPeriod) =>
          [
            `${period.name || "Unknown"}:`,
            `Температура: ${period.temperature || "Неизвестно"}°${period.temperatureUnit || "F"}`,
            `Ветер: ${period.windSpeed ​​|| "Неизвестно"} ${period.windDirection || ""}`,
            `${period.shortForecast || "Прогноз недоступен"}`,
            "---",
          ].join("\n"),
        );

        const forecastText = `Прогноз погоды для ${широты}, ${долготы}:\n\n${formattedForecast.join("\n")}`;

        возвращаться {
          содержание: [
            {
              тип: "текст",
              текст: forecastText,
            },
          ],
        };
      },
    );
    ```

    ### Запуск сервера

    Наконец, реализуйте основную функцию для запуска сервера:

    ```typescript theme={null}
    асинхронная функция main() {
      const transport = new StdioServerTransport();
      Ожидание выполнения server.connect(transport);
      console.error("Сервер Weather MCP работает на стандартном вводе/выводе");
    }

    main().catch((error) => {
      console.error("Фатальная ошибка в функции main():", error);
      process.exit(1);
    });
    ```

    Обязательно выполните команду `npm run build` для сборки сервера! Это очень важный шаг для обеспечения подключения вашего сервера.

    Теперь давайте протестируем ваш сервер, используя уже имеющийся хост MCP, Claude for Desktop.

    ## Тестирование вашего сервера с помощью Claude for Desktop

    <Примечание>
      Claude for Desktop пока недоступен для Linux. Пользователи Linux могут перейти к руководству [Создание клиента](/docs/develop/build-client), чтобы создать клиент MCP, который будет подключаться к только что созданному серверу.
    </Примечание>

    Для начала убедитесь, что у вас установлена ​​программа Claude для настольных компьютеров. [Вы можете установить последнюю версию]
    [Здесь.](https://claude.ai/download) Если у вас уже установлена ​​версия Claude для настольных компьютеров, **убедитесь, что она обновлена ​​до последней версии.**

    Нам потребуется настроить Claude for Desktop для тех серверов MCP, которые вы хотите использовать. Для этого откройте файл конфигурации приложения Claude for Desktop по адресу `~/Library/Application Support/Claude/claude_desktop_config.json` в текстовом редакторе. Убедитесь, что файл создан, если он еще не существует.

    Например, если у вас установлен [VS Code](https://code.visualstudio.com/):

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      код ~/Library/Application\ Support/Claude/claude_desktop_config.json
      ```

      ```Тема Windows PowerShell={null}
      код $env:AppData\Claude\claude_desktop_config.json
      ```
    </CodeGroup>

    Затем вам нужно будет добавить свои серверы в ключ `mcpServers`. Элементы пользовательского интерфейса MCP отобразятся в Claude for Desktop только в том случае, если хотя бы один сервер будет правильно настроен.

    В этом случае мы добавим наш единственный сервер погоды следующим образом:

    <CodeGroup>
      ```json macOS/Linux theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "узел",
            "args": ["/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather/build/index.js"]
          }
        }
      }
      ```

      ```json Windows theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "узел",
            "args": ["C:\\PATH\\TO\\PARENT\\FOLDER\\weather\\build\\index.js"]
          }
        }
      }
      ```
    </CodeGroup>

    Это сообщает Claude for Desktop:

    1. Существует сервер MCP под названием "weather".
    2. Запустите его, выполнив команду `node /ABSOLUTE/PATH/TO/PARENT/FOLDER/weather/build/index.js`

    Сохраните файл и перезапустите **Claude for Desktop**.
  </Tab>

  <Tab title="Java">
    <Примечание>
      Это демонстрационная версия для быстрого запуска, основанная на автоматической настройке и загрузочных шаблонах Spring AI MCP.
      Чтобы узнать, как создавать синхронные и асинхронные MCP-серверы вручную, обратитесь к документации [Java SDK Server](/sdk/java/mcp-server).
    </Примечание>

    Давайте начнём создавать наш сервер погоды!
    [Полный код того, что мы будем создавать, можно найти здесь.](https://github.com/spring-projects/spring-ai-examples/tree/main/model-context-protocol/weather/starter-stdio-server)

    Для получения дополнительной информации см. справочную документацию по [MCP Server Boot Starter](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-server-boot-starter-docs.html).
    Для ручной реализации MCP Server обратитесь к документации [MCP Server Java SDK](/sdk/java/mcp-server).

    ### Вход на серверы MCP

    При внедрении MCP-серверов следует внимательно относиться к обработке логов:

    **Для серверов, использующих STDIO:** Никогда не записывайте данные в стандартный вывод (stdout). Это включает в себя:

    * Операторы `print()` в Python
    * `console.log()` в JavaScript
    * `fmt.Println()` в Go
    * Аналогичные функции вывода в стандартный поток вывода в других языках

    Запись в стандартный вывод приведет к искажению сообщений JSON-RPC и поломке вашего сервера.

    **Для HTTP-серверов:** Стандартное логирование вполне подходит, поскольку оно не мешает HTTP-ответам.

    ### Передовые методы

    1. Используйте библиотеку для ведения журналов, которая записывает данные в стандартный поток ошибок (stderr) или файлы.
    2. Убедитесь, что ни одна настроенная библиотека логирования не будет записывать данные в стандартный вывод (STDOUT).

    ### Системные требования

    * Установлена ​​Java 17 или более поздней версии.
    * [Spring Boot 3.3.x](https://docs.spring.io/spring-boot/installing.html) или выше

    ### Настройка среды

    Используйте [инициализатор Spring](https://start.spring.io/) для инициализации проекта.

    Вам потребуется добавить следующие зависимости:

    <CodeGroup>
      ```xml Maven theme={null}
      <зависимости>
            <зависимость>
                <groupId>org.springframework.ai</groupId>
                <artifactId>spring-ai-starter-mcp-server</artifactId>
            </зависимость>

            <зависимость>
                <groupId>org.springframework</groupId>
                <artifactId>spring-web</artifactId>
            </зависимость>
      </dependencies>
      ```

      ```groovy Gradle theme={null}
      зависимости {
        implementation platform("org.springframework.ai:spring-ai-starter-mcp-server")
        implementation platform("org.springframework:spring-web")
      }
      ```
    </CodeGroup>

    Затем настройте приложение, задав его свойства:

    <CodeGroup>
      ```bash application.properties theme={null}
      spring.main.bannerMode=off
      logging.pattern.console=
      ```

      ```yaml application.yml theme={null}
      ведение журнала:
        шаблон:
          консоль:
      весна:
        основной:
          banner-mode: off
      ```
    </CodeGroup>

    В документе [Свойства конфигурации сервера](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-server-boot-starter-docs.html#_configuration_properties) описаны все доступные свойства.

    Теперь давайте перейдем к созданию вашего сервера.

    ## Создание вашего сервера

    ### Метеорологическая служба

    Давайте реализуем файл [WeatherService.java](https://github.com/spring-projects/spring-ai-examples/blob/main/model-context-protocol/weather/starter-stdio-server/src/main/java/org/springframework/ai/mcp/sample/server/WeatherService.java), который использует REST-клиент для запроса данных из API Национальной метеорологической службы:

    ```java theme={null}
    @Услуга
    public class WeatherSoft {

    	private final RestClient restClient;

    	public Weather() {
    		this.restClient = RestClient.builder()
    			.baseUrl("https://api.weather.gov")
    			.defaultHeader("Accept", "application/geo+json")
    			.defaultHeader("User-Agent", "WeatherApiClient/1.0 (your@email.com)")
    			.строить();
    	}

      @Tool(description = "Получить прогноз погоды для определенной широты/долготы")
      public String getWeatherForecastByLocation(
          двойная широта, // Координата широты
          двойная долгота // Координата долготы
      ) {
          // Возвращает подробный прогноз, включая:
          // - Температура и единица измерения
          // - Скорость и направление ветра
          // - Подробное описание прогноза
      }

      @Tool(description = "Получать оповещения о погоде для штата США")
      public String getAlerts(
          @ToolParam(description = "Двухбуквенный код штата США (например, CA, NY)") String state
      ) {
          // Возвращает активные оповещения, включая:
          // - Тип события
          // - Затронутая область
          // - Уровень серьезности
          // - Описание
          // - Инструкции по технике безопасности
      }

      // ......
    }
    ```

    Аннотация `@Service` автоматически зарегистрирует сервис в контексте вашего приложения.
    Аннотация `@Tool` в Spring AI упрощает создание и поддержку инструментов MCP.

    Автоматическая настройка автоматически зарегистрирует эти инструменты на сервере MCP.

    ### Создайте ваше загрузочное приложение

    ```java theme={null}
    @SpringBootApplication
    public class McpServerApplication {

    	public static void main(String[] args) {
    		SpringApplication.run(McpServerApplication.class, args);
    	}

    	@Bean
    	public ToolCallbackProvider weatherTools(WeatherService weatherService) {
    		return MethodToolCallbackProvider.builder().toolObjects(weatherService).build();
    	}
    }
    ```

    Использует утилиту `MethodToolCallbackProvider` для преобразования `@Tools` в обратные вызовы, используемые сервером MCP.

    ### Запуск сервера

    Наконец, давайте создадим сервер:

    ```bash theme={null}
    ./mvnw чистая установка
    ```

    В результате в папке `target` будет создан файл `mcp-weather-stdio-server-0.0.1-SNAPSHOT.jar`.

    Теперь давайте протестируем ваш сервер, используя уже имеющийся хост MCP, Claude for Desktop.

    ## Тестирование вашего сервера с помощью Claude for Desktop

    <Примечание>
      Приложение Claude for Desktop пока недоступно для Linux.
    </Примечание>

    Во-первых, убедитесь, что у вас установлен Claude for Desktop.
    [Вы можете установить последнюю версию здесь.](https://claude.ai/download) Если у вас уже установлена ​​версия Claude для настольных компьютеров, **убедитесь, что она обновлена ​​до последней версии.**

    Нам потребуется настроить Claude for Desktop для тех серверов MCP, которые вы хотите использовать.
    Для этого откройте файл конфигурации вашего приложения Claude for Desktop по адресу `~/Library/Application Support/Claude/claude_desktop_config.json` в текстовом редакторе.
    Если файл еще не существует, обязательно создайте его.

    Например, если у вас установлен [VS Code](https://code.visualstudio.com/):

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      код ~/Library/Application\ Support/Claude/claude_desktop_config.json
      ```

      ```Тема Windows PowerShell={null}
      код $env:AppData\Claude\claude_desktop_config.json
      ```
    </CodeGroup>

    Затем вам нужно будет добавить свои серверы в ключ `mcpServers`.
    Элементы пользовательского интерфейса MCP будут отображаться в Claude for Desktop только в том случае, если хотя бы один сервер правильно настроен.

    В этом случае мы добавим наш единственный сервер погоды следующим образом:

    <CodeGroup>
      ```json macOS/Linux theme={null}
      {
        "mcpServers": {
          "spring-ai-mcp-weather": {
            "команда": "java",
            "args": [
              "-Dspring.ai.mcp.server.stdio=true",
              "-банка",
              "/ABSOLUTE/PATH/TO/PARENT/FOLDER/mcp-weather-stdio-server-0.0.1-SNAPSHOT.jar"
            ]
          }
        }
      }
      ```

      ```json Windows theme={null}
      {
        "mcpServers": {
          "spring-ai-mcp-weather": {
            "команда": "java",
            "args": [
              "-Dspring.ai.mcp.server.transport=STDIO",
              "-банка",
              "C:\\ABSOLUTE\\PATH\\TO\\PARENT\\FOLDER\\weather\\mcp-weather-stdio-server-0.0.1-SNAPSHOT.jar"
            ]
          }
        }
      }
      ```
    </CodeGroup>

    <Примечание>
      Обязательно укажите абсолютный путь к вашему серверу.
    </Примечание>

    Это сообщает Claude for Desktop:

    1. Существует MCP-сервер с именем "my-weather-server".
    2. Для запуска выполните команду `java -jar /ABSOLUTE/PATH/TO/PARENT/FOLDER/mcp-weather-stdio-server-0.0.1-SNAPSHOT.jar`.

    Сохраните файл и перезапустите **Claude for Desktop**.

    ## Тестирование сервера с помощью Java-клиента

    ### Создание клиента MCP вручную

    Для подключения к серверу используйте `McpClient`:

    ```java theme={null}
    var stdioParams = ServerParameters.builder("java")
      .args("-jar", "/ABSOLUTE/PATH/TO/PARENT/FOLDER/mcp-weather-stdio-server-0.0.1-SNAPSHOT.jar")
      .строить();

    вар stdioTransport = новый StdioClientTransport (stdioParams);

    var mcpClient = McpClient.sync(stdioTransport).build();

    mcpClient.initialize();

    ListToolsResult toolsList = mcpClient.listTools();

    CallToolResult weather = mcpClient.callTool(
      new CallToolRequest("getWeatherForecastByLocation",
          Map.of("широта", "47.6062", "долгота", "-122.3321")));

    CallToolResult alert = mcpClient.callTool(
      new CallToolRequest("getAlerts", Map.of("state", "NY")));

    mcpClient.closeGracefully();
    ```

    ### Использовать MCP Client Boot Starter

    Создайте новое загрузочное приложение, используя зависимость `spring-ai-starter-mcp-client`:

    ```xml theme={null}
    <зависимость>
        <groupId>org.springframework.ai</groupId>
        <artifactId>spring-ai-starter-mcp-client</artifactId>
    </зависимость>
    ```

    и установите свойство `spring.ai.mcp.client.stdio.servers-configuration` так, чтобы оно указывало на ваш файл `claude_desktop_config.json`.
    Вы можете повторно использовать существующую конфигурацию Anthropic Desktop:

    ```properties theme={null}
    spring.ai.mcp.client.stdio.servers-configuration=file:PATH/TO/claude_desktop_config.json
    ```

    При запуске клиентского приложения функция автоматической настройки автоматически создаст клиенты MCP на основе файла claude\_desktop\_config.json.

    Для получения дополнительной информации см. справочную документацию по [MCP Client Boot Starters](https://docs.spring.io/spring-ai/reference/api/mcp/mcp-server-boot-client-docs.html).

    ## Дополнительные примеры работы Java MCP Server

    В примере [starter-webflux-server](https://github.com/spring-projects/spring-ai-examples/tree/main/model-context-protocol/weather/starter-webflux-server) показано, как создать MCP-сервер с использованием транспорта SSE.
    В нем показано, как определять и регистрировать инструменты, ресурсы и подсказки MCP, используя возможности автоматической настройки Spring Boot.
  </Tab>

  <Tab title="Kotlin">
    Давайте начнём создавать наш сервер погоды! [Полный код того, что мы будем создавать, вы найдёте здесь.](https://github.com/modelcontextprotocol/kotlin-sdk/tree/main/samples/weather-stdio-server)

    ### Необходимые предварительные знания

    Данное краткое руководство предполагает, что вы знакомы со следующими темами:

    * Котлин
    * Магистранты, такие как Клод

    ### Системные требования

    * Установлена ​​Java 17 или более поздней версии.

    ### Настройка среды

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
      погода mkdir
      погода на компакт-диске

      # Инициализация нового проекта Kotlin
      gradle init
      ```

      ```Тема Windows PowerShell={null}
      # Создаем новую директорию для нашего проекта
      погода в штате Мэриленд
      погода на компакт-диске

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
      val ktorVersion = "3.1.1"

      зависимости {
          implementation("io.modelcontextprotocol:kotlin-sdk:$mcpVersion")
          implementation("org.slf4j:slf4j-nop:$slf4jVersion")
          реализация("io.ktor:ktor-client-content-negotiation:$ktorVersion")
          реализация("io.ktor:ktor-serialization-kotlinx-json:$ktorVersion")
      }
      ```

      ```groovy build.gradle theme={null}
      def mcpVersion = '0.3.0'
      def slf4jVersion = '2.0.9'
      def ktorVersion = '3.1.1'

      зависимости {
          реализация "io.modelcontextprotocol:kotlin-sdk:$mcpVersion"
          реализация "org.slf4j:slf4j-nop:$slf4jVersion"
          реализация "io.ktor:ktor-client-content-negotiation:$ktorVersion"
          реализация "io.ktor:ktor-serialization-kotlinx-json:$ktorVersion"
      }
      ```
    </CodeGroup>

    Кроме того, добавьте следующие плагины в свой скрипт сборки:

    <CodeGroup>
      ```kotlin build.gradle.kts theme={null}
      плагины {
          kotlin("plugin.serialization") version "your_version_of_kotlin"
          id("com.gradleup.shadow") version "8.3.9"
      }
      ```

      ```groovy build.gradle theme={null}
      плагины {
          id 'org.jetbrains.kotlin.plugin.serialization' version 'your_version_of_kotlin'
          id 'com.gradleup.shadow' version '8.3.9'
      }
      ```
    </CodeGroup>

    Теперь давайте перейдем к созданию вашего сервера.

    ## Создание вашего сервера

    ### Настройка экземпляра

    Добавьте функцию инициализации сервера:

    ```kotlin theme={null}
    // Основная функция для запуска сервера MCP
    fun `run mcp server`() {
        // Создание экземпляра сервера MCP с базовой реализацией
        val server = Server(
            Выполнение(
                name = "weather", // Название инструмента - "weather"
                версия = "1.0.0" // Версия реализации
            ),
            Параметры сервера (
                capabilities = ServerCapabilities(tools = ServerCapabilities.Tools(listChanged = true))
            )
        )

        // Создание транспортного механизма с использованием стандартного ввода-вывода для связи с сервером
        val transport = StdioServerTransport(
            System.`in`.asInput(),
            System.out.asSink().buffered()
        )

        runBlocking {
            server.connect(transport)
            val done = Job()
            server.onClose {
                done.complete()
            }
            done.join()
        }
    }
    ```

    ### Вспомогательные функции API погоды

    Далее добавим функции и классы данных для запроса и преобразования ответов от API Национальной метеорологической службы:

    ```kotlin theme={null}
    // Функция расширения для получения прогнозной информации для заданных широты и долготы
    suspend fun HttpClient.getForecast(latitude: Double, longitude: Double): List<String> {
        val points = this.get("/points/$latitude,$longitude").body<Points>()
        val forecast = this.get(points.properties.forecast).body<Forecast>()
        return forecast.properties.periods.map { period ->
            """
                ${period.name}:
                Температура: ${period.temperature} ${period.temperatureUnit}
                Ветер: ${ period.windSpeed} ${ period.windDirection}
                Прогноз: ${period.detailedForecast}
            """.trimIndent()
        }
    }

    // Функция расширения для получения оповещений о погоде для заданного штата
    suspend fun HttpClient.getAlerts(state: String): List<String> {
        val alerts = this.get("/alerts/active/area/$state").body<Alert>()
        return alerts.features.map { feature ->
            """
                Событие: ${feature.properties.event}
                Площадь: ${feature.properties.areaDesc}
                Уровень серьезности: ${feature.properties.severity}
                Описание: ${feature.properties.description}
                Инструкция: ${feature.properties.instruction}
            """.trimIndent()
        }
    }

    @Serializable
    класс данных Points(
        val properties: Properties
    ) {
        @Serializable
        класс данных Properties(val forecast: String)
    }

    @Serializable
    класс данных Прогноз
        val properties: Properties
    ) {
        @Serializable
        класс данных Properties(val periods: List<Period>)

        @Serializable
        класс данных Период(
            val number: Int, val name: String, val startTime: String, val endTime: String,
            val isDaytime: Boolean, val temperature: Int, val temperatureUnit: String,
            val temperatureTrend: String, val probabilityOfPrecipitation: JsonObject,
            val WindSpeed: String, val WindDirection: String,
            val shortForecast: String, val detailedForecast: String,
        )
    }

    @Serializable
    класс данных Alert(
        val features: List<Feature>
    ) {
        @Serializable
        класс данных Feature(
            val properties: Properties
        )

        @Serializable
        свойства класса данных
            val event: String, val areaDesc: String, val severity: String,
            val description: String, val instruction: String?,
        )
    }
    ```

    ### Реализация выполнения инструмента

    Обработчик выполнения инструментов отвечает за фактическое выполнение логики каждого инструмента. Давайте добавим его:

    ```kotlin theme={null}
    // Создание HTTP-клиента с конфигурацией запроса по умолчанию и согласованием содержимого JSON.
    val httpClient = HttpClient {
        defaultRequest {
            url("https://api.weather.gov")
            заголовки {
                append("Accept", "application/geo+json")
                append("User-Agent", "WeatherApiClient/1.0")
            }
            contentType(ContentType.Application.Json)
        }
        // Установка плагина согласования содержимого для сериализации/десериализации JSON
        install(ContentNegotiation) { json(Json { ignoreUnknownKeys = true }) }
    }

    // Зарегистрируйте инструмент для получения оповещений о погоде по штатам
    server.addTool(
        имя = "get_alerts",
        описание = """
            Получайте оповещения о погоде для штата США. Введите двухбуквенный код штата США (например, CA, NY).
        """.trimIndent(),
        inputSchema = Tool.Input(
            свойства = buildJsonObject {
                putJsonObject("state") {
                    put("type", "string")
                    put("description", "Двухбуквенный код штата США (например, Калифорния, Нью-Йорк)")
                }
            },
            required = listOf("state")
        )
    ) { запрос ->
        val state = request.arguments["state"]?.jsonPrimitive?.content
        если (state == null) {
            return@addTool CallToolResult(
                content = listOf(TextContent("Параметр 'state' обязателен."))
            )
        }

        val alerts = httpClient.getAlerts(state)

        CallToolResult(content = alerts.map { TextContent(it) })
    }

    // Зарегистрируйте инструмент для получения прогноза погоды по широте и долготе
    server.addTool(
        имя = "get_forecast",
        описание = """
            Получите прогноз погоды для конкретной широты/долготы.
        """.trimIndent(),
        inputSchema = Tool.Input(
            свойства = buildJsonObject {
                putJsonObject("latitude") { put("type", "number") }
                putJsonObject("longitude") { put("type", "number") }
            },
            required = listOf("latitude", "longitude")
        )
    ) { запрос ->
        val latitude = request.arguments["latitude"]?.jsonPrimitive?.doubleOrNull
        val longitude = request.arguments["longitude"]?.jsonPrimitive?.doubleOrNull
        if (latitude == null || longitude == null) {
            return@addTool CallToolResult(
                content = listOf(TextContent("Параметры 'широта' и 'долгота' обязательны."))
            )
        }

        val forecast = httpClient.getForecast(latitude, longitude)

        CallToolResult(content = forecast.map { TextContent(it) })
    }
    ```

    ### Запуск сервера

    Наконец, реализуйте основную функцию для запуска сервера:

    ```kotlin theme={null}
    fun main() = `run mcp server`()
    ```

    Обязательно запустите `./gradlew build` для сборки сервера. Это очень важный шаг для обеспечения подключения вашего сервера.

    Теперь давайте протестируем ваш сервер, используя уже имеющийся хост MCP, Claude for Desktop.

    ## Тестирование вашего сервера с помощью Claude for Desktop

    <Примечание>
      Claude for Desktop пока недоступен для Linux. Пользователи Linux могут перейти к руководству [Создание клиента](/docs/develop/build-client), чтобы создать клиент MCP, который будет подключаться к только что созданному серверу.
    </Примечание>

    Для начала убедитесь, что у вас установлена ​​программа Claude для настольных компьютеров. [Вы можете установить последнюю версию]
    [Здесь.](https://claude.ai/download) Если у вас уже установлена ​​версия Claude для настольных компьютеров, **убедитесь, что она обновлена ​​до последней версии.**

    Нам потребуется настроить Claude for Desktop для тех серверов MCP, которые вы хотите использовать.
    Для этого откройте файл конфигурации вашего приложения Claude for Desktop по адресу `~/Library/Application Support/Claude/claude_desktop_config.json` в текстовом редакторе.
    Если файл еще не существует, обязательно создайте его.

    Например, если у вас установлен [VS Code](https://code.visualstudio.com/):

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      код ~/Library/Application\ Support/Claude/claude_desktop_config.json
      ```

      ```Тема Windows PowerShell={null}
      код $env:AppData\Claude\claude_desktop_config.json
      ```
    </CodeGroup>

    Затем вам нужно будет добавить свои серверы в ключ `mcpServers`.
    Элементы пользовательского интерфейса MCP будут отображаться в Claude for Desktop только в том случае, если хотя бы один сервер правильно настроен.

    В этом случае мы добавим наш единственный сервер погоды следующим образом:

    <CodeGroup>
      ```json macOS/Linux theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "java",
            "args": [
              "-банка",
              "/ABSOLUTE/PATH/TO/PARENT/FOLDER/weather/build/libs/weather-0.1.0-all.jar"
            ]
          }
        }
      }
      ```

      ```json Windows theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "java",
            "args": [
              "-банка",
              "C:\\PATH\\TO\\PARENT\\FOLDER\\weather\\build\\libs\\weather-0.1.0-all.jar"
            ]
          }
        }
      }
      ```
    </CodeGroup>

    Это сообщает Claude for Desktop:

    1. Существует сервер MCP под названием "weather".
    2. Запустите его, выполнив команду `java -jar /ABSOLUTE/PATH/TO/PARENT/FOLDER/weather/build/libs/weather-0.1.0-all.jar`.

    Сохраните файл и перезапустите **Claude for Desktop**.
  </Tab>

  <Tab title="C#">
    Давайте начнём создавать наш сервер погоды! [Полный код того, что мы будем создавать, вы найдёте здесь.](https://github.com/modelcontextprotocol/csharp-sdk/tree/main/samples/QuickstartWeatherServer)

    ### Необходимые предварительные знания

    Данное краткое руководство предполагает, что вы знакомы со следующими темами:

    * C#
    * Магистранты, такие как Клод
    * .NET 8 или выше

    ### Вход на серверы MCP

    При внедрении MCP-серверов следует внимательно относиться к обработке логов:

    **Для серверов, использующих STDIO:** Никогда не записывайте данные в стандартный вывод (stdout). Это включает в себя:

    * Операторы `print()` в Python
    * `console.log()` в JavaScript
    * `fmt.Println()` в Go
    * Аналогичные функции вывода в стандартный поток вывода в других языках

    Запись в стандартный вывод приведет к искажению сообщений JSON-RPC и поломке вашего сервера.

    **Для HTTP-серверов:** Стандартное логирование вполне подходит, поскольку оно не мешает HTTP-ответам.

    ### Передовые методы

    1. Используйте библиотеку для ведения журналов, которая записывает данные в стандартный поток ошибок (stderr) или файлы.

    ### Системные требования

    * Установлен [.NET 8 SDK](https://dotnet.microsoft.com/download/dotnet/8.0) или более поздней версии.

    ### Настройка среды

    Для начала, если вы еще этого не сделали, давайте установим `dotnet`. Вы можете скачать `dotnet` с [официального сайта Microsoft .NET](https://dotnet.microsoft.com/download/). Проверьте правильность установки `dotnet`:

    ```bash theme={null}
    dotnet --version
    ```

    Теперь давайте создадим и настроим ваш проект:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      # Создаем новую директорию для нашего проекта
      погода mkdir
      погода на компакт-диске
      # Инициализация нового проекта C#
      dotnet новая консоль
      ```

      ```Тема Windows PowerShell={null}
      # Создаем новую директорию для нашего проекта
      погода mkdir
      погода на компакт-диске
      # Инициализация нового проекта C#
      dotnet новая консоль
      ```
    </CodeGroup>

    После выполнения команды `dotnet new console` перед вами откроется новый проект на C#.
    Вы можете открыть проект в своей любимой IDE, например, в [Visual Studio](https://visualstudio.microsoft.com/) или [Rider](https://www.jetbrains.com/rider/).
    В качестве альтернативы вы можете создать приложение на C# с помощью [мастера создания проектов Visual Studio](https://learn.microsoft.com/en-us/visualstudio/get-started/csharp/tutorial-console?view=vs-2022).
    После создания проекта добавьте пакет NuGet для SDK протокола контекста модели и хостинга:

    ```bash theme={null}
    # Добавьте пакет NuGet Model Context Protocol SDK
    dotnet add package ModelContextProtocol --prerelease
    # Добавьте пакет NuGet для хостинга .NET
    dotnet add package Microsoft.Extensions.Hosting
    ```

    Теперь давайте перейдем к созданию вашего сервера.

    ## Создание вашего сервера

    Откройте файл `Program.cs` в вашем проекте и замените его содержимое следующим кодом:

    ```csharp theme={null}
    с использованием Microsoft.Extensions.DependencyInjection;
    с использованием Microsoft.Extensions.Hosting;
    с использованием ModelContextProtocol;
    using System.Net.Http.Headers;

    var builder = Host.CreateEmptyApplicationBuilder(settings: null);

    builder.Services.AddMcpServer()
        .WithStdioServerTransport()
        .WithToolsFromAssembly();

    builder.Services.AddSingleton(_ =>
    {
        var client = new HttpClient() { BaseAddress = new Uri("https://api.weather.gov") };
        client.DefaultRequestHeaders.UserAgent.Add(new ProductInfoHeaderValue("weather-tool", "1.0"));
        вернуть клиента;
    });

    var app = builder.Build();

    await app.RunAsync();
    ```

    <Примечание>
      При создании объекта `ApplicationHostBuilder` убедитесь, что вы используете `CreateEmptyApplicationBuilder` вместо `CreateDefaultBuilder`. Это гарантирует, что сервер не будет выводить дополнительные сообщения в консоль. Это необходимо только для серверов, использующих STDIO-транспорт.
    </Примечание>

    Этот код создает базовое консольное приложение, использующее SDK протокола контекста модели (MCP) для создания MCP-сервера со стандартным транспортом ввода-вывода.

    ### Вспомогательные функции API погоды

    Создайте класс расширения для `HttpClient`, который упростит обработку JSON-запросов:

    ```csharp theme={null}
    using System.Text.Json;

    внутренний статический класс HttpClientExt
    {
        public static async Task<JsonDocument> ReadJsonDocumentAsync(this HttpClient client, string requestUri)
        {
            using var response = await client.GetAsync(requestUri);
            response.EnsureSuccessStatusCode();
            return await JsonDocument.ParseAsync(await response.Content.ReadAsStreamAsync());
        }
    }
    ```

    Далее определите класс с обработчиками выполнения инструментов для запроса и преобразования ответов от API Национальной метеорологической службы:

    ```csharp theme={null}
    с использованием ModelContextProtocol.Server;
    using System.ComponentModel;
    с использованием System.Globalization;
    using System.Text.Json;

    пространство имен QuickstartWeatherServer.Tools;

    [McpServerToolType]
    public static class WeatherTools
    {
        [McpServerTool, Description("Получать оповещения о погоде для кода штата США.")]
        public static async Task<string> GetAlerts(
            HttpClient клиент,
            [Description("Код штата США, для которого нужно получать оповещения."] string state)
        {
            using var jsonDocument = await client.ReadJsonDocumentAsync($"/alerts/active/area/{state}");
            вар jsonElement = jsonDocument.RootElement;
            var alerts = jsonElement.GetProperty("features").EnumerateArray();

            если (!alerts.Any())
            {
                Возвращает "В этом штате нет активных оповещений.";
            }

            return string.Join("\n--\n", alerts.Select(alert =>
            {
                JsonElement properties = alert.GetProperty("properties");
                возврат $"""
                        Событие: {properties.GetProperty("event").GetString()}
                        Площадь: {properties.GetProperty("areaDesc").GetString()}
                        Уровень серьезности: {properties.GetProperty("severity").GetString()}
                        Описание: {properties.GetProperty("description").GetString()}
                        Инструкция: {properties.GetProperty("instruction").GetString()}
                        """;
            }));
        }

        [McpServerTool, Description("Получить прогноз погоды для указанного местоположения.")]
        public static async Task<string> GetForecast(
            HttpClient клиент,
            [Описание("Широта местоположения.")] двойная широта,
            [Описание("Долгота местоположения."] двойная долгота)
        {
            var pointUrl = string.Create(CultureInfo.InvariantCulture, $"/points/{latitude},{longitude}");
            using var jsonDocument = await client.ReadJsonDocumentAsync(pointUrl);
            var forecastUrl = jsonDocument.RootElement.GetProperty("properties").GetProperty("forecast").GetString()
                ?? throw new Exception($"No forecast URL provided by {client.BaseAddress}points/{latitude},{longitude}");

            using var forecastDocument = await client.ReadJsonDocumentAsync(forecastUrl);
            var periods = forecastDocument.RootElement.GetProperty("properties").GetProperty("periods").EnumerateArray();

            return string.Join("\n---\n", periods.Select(period => $"""
                    {period.GetProperty("name").GetString()}
                    Температура: {period.GetProperty("temperature").GetInt32()}°F
                    Ветер: {period.GetProperty("windSpeed").GetString()} {period.GetProperty("windDirection").GetString()}
                    Прогноз: {period.GetProperty("detailedForecast").GetString()}
                    """));
        }
    }
    ```

    ### Запуск сервера

    Наконец, запустите сервер, используя следующую команду:

    ```bash theme={null}
    dotnet run
    ```

    Это запустит сервер и начнёт прослушивать входящие запросы через стандартный ввод/вывод.

    ## Тестирование вашего сервера с помощью Claude for Desktop

    <Примечание>
      Claude for Desktop пока недоступен для Linux. Пользователи Linux могут перейти к руководству [Создание клиента](/docs/develop/build-client), чтобы создать клиент MCP, который будет подключаться к только что созданному серверу.
    </Примечание>

    Для начала убедитесь, что у вас установлена ​​программа Claude для настольных компьютеров. [Вы можете установить последнюю версию]
    [Здесь.](https://claude.ai/download) Если у вас уже установлена ​​версия Claude для настольных компьютеров, **убедитесь, что она обновлена ​​до последней версии.**
    Нам потребуется настроить Claude for Desktop для тех серверов MCP, которые вы хотите использовать. Для этого откройте файл конфигурации приложения Claude for Desktop по адресу `~/Library/Application Support/Claude/claude_desktop_config.json` в текстовом редакторе. Убедитесь, что файл создан, если он еще не существует.
    Например, если у вас установлен [VS Code](https://code.visualstudio.com/):

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      код ~/Library/Application\ Support/Claude/claude_desktop_config.json
      ```

      ```Тема Windows PowerShell={null}
      код $env:AppData\Claude\claude_desktop_config.json
      ```
    </CodeGroup>

    Затем вам нужно будет добавить свои серверы в ключ `mcpServers`. Элементы пользовательского интерфейса MCP отобразятся в Claude for Desktop только в том случае, если хотя бы один сервер будет правильно настроен.
    В этом случае мы добавим наш единственный сервер погоды следующим образом:

    <CodeGroup>
      ```json macOS/Linux theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "dotnet",
            "args": ["run", "--project", "/ABSOLUTE/PATH/TO/PROJECT", "--no-build"]
          }
        }
      }
      ```

      ```json Windows theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "dotnet",
            "args": [
              "бегать",
              "--проект",
              "C:\\ABSOLUTE\\PATH\\TO\\PROJECT",
              "--нет-строительства"
            ]
          }
        }
      }
      ```
    </CodeGroup>

    Это сообщает Claude for Desktop:

    1. Существует сервер MCP под названием "weather".
    2. Запустите его, выполнив команду `dotnet run /ABSOLUTE/PATH/TO/PROJECT`.
       Сохраните файл и перезапустите **Claude for Desktop**.
  </Tab>

  <Tab title="Rust">
    Давайте начнём создавать наш сервер погоды! [Полный код того, что мы будем создавать, вы найдёте здесь.](https://github.com/modelcontextprotocol/quickstart-resources/tree/main/weather-server-rust)

    ### Необходимые предварительные знания

    Данное краткое руководство предполагает, что вы знакомы со следующими темами:

    * Язык программирования Rust
    * Асинхронный режим/ожидание в Rust
    * Магистранты, такие как Клод

    ### Вход на серверы MCP

    При внедрении MCP-серверов следует внимательно относиться к обработке логов:

    **Для серверов, использующих STDIO:** Никогда не записывайте данные в стандартный вывод (stdout). Это включает в себя:

    * Операторы `print()` в Python
    * `console.log()` в JavaScript
    * `println!()` в Rust
    * Аналогичные функции вывода в стандартный поток вывода в других языках

    Запись в стандартный вывод приведет к искажению сообщений JSON-RPC и поломке вашего сервера.

    **Для HTTP-серверов:** Стандартное логирование вполне подходит, поскольку оно не мешает HTTP-ответам.

    ### Передовые методы

    1. Используйте библиотеку для логирования, которая записывает данные в stderr или файлы, например `tracing` или `log` в Rust.
    2. Настройте свою систему логирования таким образом, чтобы избежать вывода в стандартный поток вывода (stdout).

    ### Краткие примеры

    ```rust theme={null}
    // ❌ Плохо (STDIO)
    println!("Обработка запроса");

    // ✅ Хорошо (STDIO)
    использовать трассировку::информацию;
    info!("Обработка запроса"); // записывает в stderr
    ```

    ### Системные требования

    * Установлен уровень ржавчины 1.70 или выше.
    * Грузовой отсек (поставляется с установкой Rust).

    ### Настройка среды

    Для начала, если вы ещё этого не сделали, давайте установим Rust. Вы можете установить Rust с сайта [rust-lang.org](https://www.rust-lang.org/tools/install):

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
      ```

      ```Тема Windows PowerShell={null}
      # Загрузите и запустите rustup-init.exe с сайта https://rustup.rs/
      ```
    </CodeGroup>

    Проверьте правильность установки Rust:

    ```bash theme={null}
    rustc --version
    груз --версия
    ```

    Теперь давайте создадим и настроим наш проект:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      # Создать новый проект Rust
      груз новая погода
      погода на компакт-диске
      ```

      ```Тема Windows PowerShell={null}
      # Создать новый проект Rust
      груз новая погода
      погода на компакт-диске
      ```
    </CodeGroup>

    Обновите файл `Cargo.toml`, добавив необходимые зависимости:

    ```toml Cargo.toml theme={null}
    [упаковка]
    имя = "погода"
    версия = "0.1.0"
    издание = "2024"

    [зависимости]
    rmcp = { version = "0.3", features = ["server", "macros", "transport-io"] }
    tokio = { version = "1.46", features = ["full"] }
    reqwest = { version = "0.12", features = ["json"] }
    serde = { version = "1.0", features = ["derive"] }
    serde_json = "1.0"
    в любом случае = "1.0"
    трассировка = "0.1"
    tracing-subscriber = { version = "0.3", features = ["env-filter", "std", "fmt"] }
    ```

    Теперь давайте перейдем к созданию вашего сервера.

    ## Создание вашего сервера

    ### Импорт пакетов и констант

    Откройте файл `src/main.rs` и добавьте в начало следующие импорты и константы:

    ```rust theme={null}
    использовать anyhow::Result;
    использовать rmcp::{
        ServerHandler, ServiceExt,
        handler::server::{router::tool::ToolRouter, tool::Parameters},
        модель::*,
        схемы, инструмент, обработчик инструмента, маршрутизатор инструмента,
    };
    использовать serde::Deserialize;
    use serde::de::DeserializeOwned;

    const NWS_API_BASE: &str = "https://api.weather.gov";
    const USER_AGENT: &str = "weather-app/1.0";
    ```

    Библиотека `rmcp` предоставляет SDK протокола контекста модели для Rust, включающий функции для реализации сервера, процедурных макросов и передачи данных через стандартный ввод-вывод.

    ### Структуры данных

    Далее определим структуры данных для десериализации ответов от API Национальной метеорологической службы:

    ```rust theme={null}
    #[derive(Debug, Deserialize)]
    struct AlertsResponse {
        характеристики: Vec<AlertFeature>,
    }

    #[derive(Debug, Deserialize)]
    структура AlertFeature {
        свойства: AlertProperties,
    }

    #[derive(Debug, Deserialize)]
    структура AlertProperties {
        событие: Option<String>,
        #[serde(rename = "areaDesc")]
        area_desc: Option<String>,
        серьезность: Option<String>,
        описание: Option<String>,
        инструкция: Option<String>,
    }

    #[derive(Debug, Deserialize)]
    struct PointsResponse {
        свойства: PointsProperties,
    }

    #[derive(Debug, Deserialize)]
    struct PointsProperties {
        прогноз: Строка,
    }

    #[derive(Debug, Deserialize)]
    структура ForecastResponse {
        свойства: ForecastProperties,
    }

    #[derive(Debug, Deserialize)]
    структура ForecastProperties {
        периоды: Vec<ПериодПрогноза>,
    }

    #[derive(Debug, Deserialize)]
    структура ForecastPeriod {
        имя: Строка,
        температура: i32,
        #[serde(rename = "temperatureUnit")]
        temperature_unit: String,
        #[serde(rename = "windSpeed")]
        wind_speed: Строка,
        #[serde(rename = "windDirection")]
        направление ветра: Строка,
        #[serde(rename = "detailedForecast")]
        detailed_forecast: String,
    }
    ```

    Теперь определим типы запросов, которые будут отправлять клиенты MCP:

    ```rust theme={null}
    #[derive(serde::Deserialize, Schemars::JsonSchema)]
    pub struct MCPForecastRequest {
        широта: f32,
        долгота: f32,
    }

    #[derive(serde::Deserialize, Schemars::JsonSchema)]
    pub struct MCPalertRequest {
        состояние: Строка,
    }
    ```

    ### Вспомогательные функции

    Добавить вспомогательные функции для выполнения API-запросов и форматирования ответов:

    ```rust theme={null}
    async fn make_nws_request<T: DeserializeOwned>(url: &str) -> Result<T> {
        let client = reqwest::Client::new();
        let rsp = client
            .get(url)
            .header(reqwest::header::USER_AGENT, USER_AGENT)
            .header(reqwest::header::ACCEPT, "application/geo+json")
            .отправлять()
            .await?
            .error_for_status()?;
        Ok(rsp.json::<T>().await?)
    }

    fn format_alert(feature: &AlertFeature) -> String {
        let props = &feature.properties;
        формат!(
            "Событие: {}\nОбласть: {}\nСерьезность: {}\nОписание: {}\nИнструкции: {}",
            props.event.as_deref().unwrap_or("Unknown"),
            props.area_desc.as_deref().unwrap_or("Unknown"),
            props.severity.as_deref().unwrap_or("Unknown"),
            реквизит
                .описание
                .as_deref()
                .unwrap_or("Описание отсутствует"),
            реквизит
                .инструкция
                .as_deref()
                .unwrap_or("Конкретные инструкции не предоставлены")
        )
    }

    fn format_period(period: &ForecastPeriod) -> String {
        формат!(
            "{}:\nТемпература: {}°{}\nВетер: {} {}\nПрогноз: {}",
            период.имя,
            период.температура,
            период.единица_температуры,
            период.скорость_ветра,
            период.направление_ветра,
            период.подробный_прогноз
        )
    }
    ```

    ### Внедрение сервера погоды и инструментов

    Теперь давайте реализуем основную структуру сервера погоды с обработчиками инструментов:

    ```rust theme={null}
    pub struct Weather {
        tool_router: ToolRouter<Weather>,
    }

    #[tool_router]
    impl Weather {
        fn new() -> Self {
            Себя {
                tool_router: Self::tool_router(),
            }
        }

        #[tool(description = "Получайте оповещения о погоде для штата США."]
        async fn get_alerts(
            &себя,
            Parameters(MCPAlertRequest { state }): Parameters<MCPAlertRequest>,
        ) -> Строка {
            let url = format!(
                "{}/alerts/active/area/{}",
                NWS_API_BASE,
                state.to_uppercase()
            );

            match make_nws_request::<AlertsResponse>(&url).await {
                Ok(data) => {
                    if data.features.is_empty() {
                        "В этом штате нет активных оповещений.".to_string()
                    } еще {
                        данные.функции
                            .iter()
                            .map(format_alert)
                            .collect::<Vec<_>>()
                            .join("\n---\n")
                    }
                }
                Err(_) => "Не удалось получить оповещения или оповещения не найдены."to_string(),
            }
        }

        #[tool(description = "Получить прогноз погоды для определенного места.")]
        async fn get_forecast(
            &себя,
            Параметры(MCPForecastRequest {
                широта,
                долгота,
            }): Параметры<MCPForecastRequest>,
        ) -> Строка {
            let points_url = format!("{NWS_API_BASE}/points/{latitude},{longitude}");
            let Ok(points_data) = make_nws_request::<PointsResponse>(&points_url).await else {
                return "Не удалось получить данные прогноза для этого местоположения.".to_string();
            };

            let forecast_url = points_data.properties.forecast;

            let Ok(forecast_data) = make_nws_request::<ForecastResponse>(&forecast_url).await else {
                return "Не удалось получить данные прогноза для этого местоположения.".to_string();
            };

            let periods = &forecast_data.properties.periods;
            let forecast_summary: String = periods
                .iter()
                .take(5) // Только следующие 5 периодов
                .map(format_period)
                .collect::<Vec<String>>()
                .join("\n---\n");
            прогноз_сводка
        }
    }
    ```

    Макрос `#[tool_router]` автоматически генерирует логику маршрутизации, а атрибут `#[tool]` помечает методы как инструменты MCP.

    ### Реализация ServerHandler

    Реализуйте трейт `ServerHandler` для определения возможностей сервера:

    ```rust theme={null}
    #[tool_handler]
    реализовать обработчик сервера для погоды {
        fn get_info(&self) -> ServerInfo {
            ServerInfo {
                возможности: ServerCapabilities::builder().enable_tools().build(),
                ..Default::default()
            }
        }
    }
    ```

    ### Запуск сервера

    Наконец, реализуйте основную функцию для запуска сервера с использованием стандартного ввода-вывода:

    ```rust theme={null}
    #[tokio::main]
    async fn main() -> Result<()> {
        let Transport = (tokio::io::stdin(), tokio::io::stdout());
        let service = Weather::new().serv(transport).await?;
        service.waiting().await?;
        Хорошо(())
    }
    ```

    Создайте свой сервер с помощью:

    ```bash theme={null}
    cargo build --release
    ```

    Скомпилированный исполняемый файл будет находиться в папке `target/release/weather`.

    Теперь давайте протестируем ваш сервер, используя уже имеющийся хост MCP, Claude for Desktop.

    ## Тестирование вашего сервера с помощью Claude for Desktop

    <Примечание>
      Claude for Desktop пока недоступен для Linux. Пользователи Linux могут перейти к руководству [Создание клиента](/docs/develop/build-client), чтобы создать клиент MCP, который будет подключаться к только что созданному серверу.
    </Примечание>

    Для начала убедитесь, что у вас установлена ​​программа Claude для настольных компьютеров. [Вы можете установить последнюю версию здесь.](https://claude.ai/download) Если у вас уже установлена ​​программа Claude для настольных компьютеров, **убедитесь, что она обновлена ​​до последней версии.**

    Нам потребуется настроить Claude for Desktop для тех серверов MCP, которые вы хотите использовать. Для этого откройте файл конфигурации приложения Claude for Desktop по адресу `~/Library/Application Support/Claude/claude_desktop_config.json` в текстовом редакторе. Убедитесь, что файл создан, если он еще не существует.

    Например, если у вас установлен [VS Code](https://code.visualstudio.com/):

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      код ~/Library/Application\ Support/Claude/claude_desktop_config.json
      ```

      ```Тема Windows PowerShell={null}
      код $env:AppData\Claude\claude_desktop_config.json
      ```
    </CodeGroup>

    Затем вам нужно будет добавить свои серверы в ключ `mcpServers`. Элементы пользовательского интерфейса MCP отобразятся в Claude for Desktop только в том случае, если хотя бы один сервер будет правильно настроен.

    В этом случае мы добавим наш единственный сервер погоды следующим образом:

    <CodeGroup>
      ```json macOS/Linux theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "/АБСОЛЮТНЫЙ/ПУТЬ/К/РОДИТЕЛЬНОЙ/ПАПКЕ/погода/цель/освобождение/погода"
          }
        }
      }
      ```

      ```json Windows theme={null}
      {
        "mcpServers": {
          "погода": {
            "команда": "C:\\ABSOLUTE\\PATH\\TO\\PARENT\\FOLDER\\weather\\target\\release\\weather.exe"
          }
        }
      }
      ```
    </CodeGroup>

    <Примечание>
      Убедитесь, что вы указали абсолютный путь к скомпилированному исполняемому файлу. Получить его можно, запустив команду `pwd` в macOS/Linux или `cd` в командной строке Windows из каталога вашего проекта. В Windows не забудьте использовать двойные обратные косые черты (`\\`) или прямые косые черты (`/`) в пути JSON и добавить расширение `.exe`.
    </Примечание>

    Это сообщает Claude for Desktop:

    1. Существует сервер MCP под названием "weather".
    2. Запустите его, выполнив скомпилированный исполняемый файл по указанному пути.

    Сохраните файл и перезапустите **Claude for Desktop**.
  </Tab>
</Вкладки>

### Тестирование с помощью команд

Давайте убедимся, что Claude for Desktop распознает два инструмента, которые мы добавили на наш сервер `weather`. Это можно сделать, найдя "Добавить файлы, коннекторы и многое другое /" <img src="https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/claude-add-files-connectors-and-more.png?fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=eb7ecdd7bb5698946f0c6a25284fd988" style={{display: 'inline', margin: 0, height: '1.3em'}} data-og-width="33" width="33" data-og-height="33" height="33" data-path="images/claude-add-files-connectors-and-more.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/claude-add-files-connectors-and-more.png?w=280&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=f78b3570f4eb719bbc233a9d231e3458 280w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/claude-add-files-connectors-and-more.png?w=560&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=3b3ea07c9d70f7c424b4910607e8fbe6 560 Вт, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/claude-add-files-connectors-and-more.png?w=840&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=392f46cd7983dc4a1449a7c966116d33 840w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/claude-add-files-connectors-and-more.png?w=1100&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=f28f1a2257cf0af9bf06aefaea396b92 1100w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/claude-add-files-connectors-and-more.png?w=1650&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=a132d04ddafdf8ecf8c3b43089546ba5 1650w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/claude-add-files-connectors-and-more.png?w=2500&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=e6e69cd36d8f221bd79d5816e5ee0aac 2500w" /> icon:

<Рамка>
  <img src="https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/visual-indicator-mcp-tools.png?fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=1bf23a2cfc5f6dd3dac1c7574cceebc9" data-og-width="684" width="684" data-og-height="133" height="133" data-path="images/visual-indicator-mcp-tools.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/visual-indicator-mcp-tools.png?w=280&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=7f648b81b43a635211f064bda6bede29 280w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/visual-indicator-mcp-tools.png?w=560&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=f437a99616b681a00d255d38854bb5e2 560 Вт, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/visual-indicator-mcp-tools.png?w=840&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=a769ef2f26ea1997abd03c739ace306b 840 Вт, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/visual-indicator-mcp-tools.png?w=1100&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=a2981e9e32ef2c4ba1b2c1aa87051ebe 1100 Вт, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/visual-indicator-mcp-tools.png?w=1650&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=fbacd0692cf460cab039786342be752d 1650w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/visual-indicator-mcp-tools.png?w=2500&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=f6414d3ad85dfc1e37ab2dffe278c6de 2500 Вт" />
</Frame>

После нажатия на значок плюса наведите курсор на меню «Коннекторы». Вы должны увидеть список серверов, предоставляющих информацию о погоде:

<Рамка>
  <img src="https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/available-mcp-tools.png?fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=e2ace1ac88895a5fe30ebd8d01456bc3" data-og-width="437" width="437" data-og-height="244" height="244" data-path="images/available-mcp-tools.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/available-mcp-tools.png?w=280&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=12d67941b4c5df8f6056d0ff4d2d26ca 280w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/available-mcp-tools.png?w=560&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=a2de446a63c24ac0a0576a3e0c7ee30a 560w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/available-mcp-tools.png?w=840&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=8566e1a245f7f2d204b540cca63d101f 840 Вт, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/available-mcp-tools.png?w=1100&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=5d7bbe45b2ae68166b10eebd8984170f 1100 Вт, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/available-mcp-tools.png?w=1650&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=9ea7ccce0e935df48d950adb976c5f03 1650w, https://mintcdn.com/mcp/zNouQwo2h8cbxlDS/images/available-mcp-tools.png?w=2500&fit=max&auto=format&n=zNouQwo2h8cbxlDS&q=85&s=8298981f84cb55c6e477006cb8bf873b 2500w" />
</Frame>

Если Claude for Desktop не распознает ваш сервер, перейдите к разделу [Устранение неполадок](#troubleshooting) для получения советов по отладке.

Если сервер отобразился в меню «Коннекторы», вы можете проверить его работу, выполнив следующие команды в Claude for Desktop:

Какая погода в Сакраменто?
* Какие действующие предупреждения о погоде действуют в Техасе?

<Рамка>
  <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=dce7b2f8a06c20ba358e4bd2e75fa4c7" data-og-width="2780" width="2780" data-og-height="1849" height="1849" data-path="images/current-weather.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=bbb19f34c5df59f66bc6bbb75d2bc5ed 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=2392d7e765b897c5b78f9f53d41439d4 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=dc349e75341b046d35a649762774da49 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=deeb99214d9383ee4a0c8aaacb120049 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=5c6f948059635e376deeadce3893e9b9 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/current-weather.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=3922160478785cc88d5e98d418e8f7dd 2500 Вт" />
</Frame>

<Рамка>
  <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/weather-alerts.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c4762bf2bd84a8781846d2965af3e4a4" data-og-width="2809" width="2809" data-og-height="1850" height="1850" data-path="images/weather-alerts.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/weather-alerts.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=e25afdd84f6ae9c612b898c6eb9c518d 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/weather-alerts.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=1e7ef678cbc93c0966789e61d5209092 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/weather-alerts.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=4dbaeb8840a7b1aeb73b188804877d71 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/weather-alerts.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=68f5e0cb428c8b9cb53d28ec1108073b 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/weather-alerts.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=56025243c2b8c6413f8da087122e848d 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/weather-alerts.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=12f50039e4a1c9544a22a9bdae46f719 2500w" />
</Frame>

<Примечание>
  Поскольку это Национальная метеорологическая служба США, запросы будут работать только для населенных пунктов на территории США.
</Примечание>

## Что происходит под капотом

Когда вы задаёте вопрос:

1. Клиент отправляет ваш вопрос Клоду.
2. Клод анализирует имеющиеся инструменты и решает, какой (какие) из них использовать.
3. Клиент запускает выбранный инструмент (или инструменты) через сервер MCP.
4. Результаты отправляются обратно Клоду.
5. Клод формулирует ответ на естественном языке.
6. Ответ отображается вам!

## Поиск неисправностей

<AccordionGroup>
  <Заголовок аккордеона: "Клод по вопросам интеграции с рабочим столом">
    **Получение логов из Claude for Desktop**

    Сообщения Claude.app, относящиеся к MCP, записываются в файлы журналов в каталоге `~/Library/Logs/Claude`:

    * Файл `mcp.log` будет содержать общие сведения о соединениях MCP и сбоях соединения.
    * Файлы с именем `mcp-server-SERVERNAME.log` будут содержать сообщения об ошибках (stderr) с указанного сервера.

    Вы можете выполнить следующую команду, чтобы просмотреть последние записи в логах и отслеживать появление новых:

    ```bash theme={null}
    # Проверьте журналы Клода на наличие ошибок
    tail -n 20 -f ~/Library/Logs/Claude/mcp*.log
    ```

    **Сервер не отображается в Клоде**

    1. Проверьте синтаксис файла `claude_desktop_config.json`.
    2. Убедитесь, что путь к вашему проекту является абсолютным, а не относительным.
    3. Полностью перезапустите Claude для рабочего стола.

    <Предупреждение>
      Для корректного перезапуска приложения Claude for Desktop необходимо полностью закрыть это приложение:

      * **Windows**: Щелкните правой кнопкой мыши значок Клода в системном трее (он может быть скрыт в меню «Скрытые значки») и выберите «Выход» или «Завершить».
      * **macOS**: Используйте Cmd+Q или выберите «Выйти из Claude» в строке меню.

      Простое закрытие окна не приводит к полному завершению работы приложения, и изменения конфигурации вашего сервера MCP не вступят в силу.
    </Предупреждение>

    **Вызовы инструментов завершаются с ошибкой без уведомления**

    Если Клод попытается использовать инструменты, но они окажутся неэффективными:

    1. Проверьте журналы Клода на наличие ошибок.
    2. Убедитесь, что ваш сервер собирается и работает без ошибок.
    3. Попробуйте перезапустить Claude for Desktop.

    **Ничего из этого не работает. Что мне делать?**

    Для получения более совершенных инструментов отладки и подробных инструкций обратитесь к нашему [руководству по отладке](/legacy/tools/debugging).
  </Аккордеон>

  <Заголовок аккордеона="Проблемы с API погоды">
    **Ошибка: Не удалось получить данные о точках сетки**

    Обычно это означает одно из следующего:

    1. Координаты находятся за пределами США.
    2. В работе API NWS наблюдаются проблемы.
    3. У вас установлено ограничение на количество запросов.

    Исправить:

    * Убедитесь, что вы используете координаты США.
    * Добавить небольшую задержку между запросами
    * Проверьте страницу состояния API NWS

    **Ошибка: Нет активных оповещений для [ШТАТА]**

    Это не ошибка — это просто означает, что для этого штата нет текущих предупреждений о погоде. Попробуйте проверить другой штат или проверьте во время сильной непогоды.
  </Аккордеон>
</AccordionGroup>

<Примечание>
  Для более продвинутого устранения неполадок ознакомьтесь с нашим руководством по отладке MCP (/legacy/tools/debugging).
</Примечание>

## Следующие шаги

<CardGroup cols={2}>
  <Card title="Создание клиента" icon="outlet" href="/docs/develop/build-client">
    Узнайте, как создать собственный MCP-клиент, способный подключаться к вашему серверу.
  </Карточка>

  <Card title="Примеры серверов" icon="grid" href="/examples">
    Ознакомьтесь с нашей галереей официальных серверов и реализаций MCP.
  </Карточка>

  <Card title="Руководство по отладке" icon="bug" href="/legacy/tools/debugging">
    Узнайте, как эффективно отлаживать серверы и интеграции MCP.
  </Карточка>

  <Card title="Building MCP with LLMs" icon="comments" href="/tutorials/building-mcp-with-llms">
    Узнайте, как использовать программы магистратуры в области права, такие как программа Клода, чтобы ускорить разработку вашей программы MCP.
  </Карточка>
</CardGroup>