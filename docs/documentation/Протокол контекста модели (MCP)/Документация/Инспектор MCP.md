> ## Индекс документации
Полный индекс документации доступен по адресу: https://modelcontextprotocol.io/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Инспектор MCP

> Подробное руководство по использованию инспектора MCP для тестирования и отладки серверов протокола контекста модели.

[Инспектор MCP](https://github.com/modelcontextprotocol/inspector) — это интерактивный инструмент разработчика для тестирования и отладки серверов MCP. Хотя [Руководство по отладке](/legacy/tools/debugging) описывает Инспектор как часть общего набора инструментов отладки, в этом документе подробно рассматриваются его функции и возможности.

## Начиная

### Установка и базовое использование

Инспектор запускается напрямую через `npx` без необходимости установки:

```bash theme={null}
npx @modelcontextprotocol/inspector <command>
```

```bash theme={null}
npx @modelcontextprotocol/inspector <command> <arg1> <arg2>
```

#### Проверка серверов из npm или PyPI

Распространенный способ запуска серверных пакетов из [npm](https://npmjs.com) или [PyPI](https://pypi.org).

<Вкладки>
  <Tab title="npm package">
    ```bash theme={null}
    npx -y @modelcontextprotocol/inspector npx <package-name> <args>
    # Например
    npx -y @modelcontextprotocol/inspector npx @modelcontextprotocol/server-filesystem /Users/username/Desktop
    ```
  </Tab>

  <Tab title="Пакет PyPI">
    ```bash theme={null}
    npx @modelcontextprotocol/inspector uvx <package-name> <args>
    # Например
    npx @modelcontextprotocol/inspector uvx mcp-server-git --repository ~/code/mcp/servers.git
    ```
  </Tab>
</Вкладки>

#### Проверка локально разработанных серверов

Для проверки серверов, разработанных локально или загруженных в виде репозитория, наиболее распространенным является следующий способ:
Способ таков:

<Вкладки>
  <Tab title="TypeScript">
    ```bash theme={null}
    npx @modelcontextprotocol/inspector node path/to/server/index.js args...
    ```
  </Tab>

  <Tab title="Python">
    ```bash theme={null}
    npx @modelcontextprotocol/inspector \
      uv \
      --путь к каталогу/серверу \
      бегать \
      имя-пакета
      аргументы...
    ```
  </Tab>
</Вкладки>

Внимательно прочтите прилагаемый файл README для получения наиболее точных инструкций.

## Обзор функций

<Frame caption="Интерфейс инспектора MCP">
  <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/mcp-inspector.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=83b12e2a457c96ef4ad17c7357236290" data-og-width="2888" width="2888" data-og-height="1761" height="1761" data-path="images/mcp-inspector.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/mcp-inspector.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=63e7263fbdf5f473064f37dac99ae8e5 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/mcp-inspector.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=78dcf971172e8790fc672f19ead2796d 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/mcp-inspector.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=8c4ce11c7901888cd967f461df66a0f3 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/mcp-inspector.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=279b84d4729737f1241514cb30de3b40 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/mcp-inspector.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=ac5dcc45e291ba2f2954d3a22c918029 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/mcp-inspector.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=4fbcddae467e84daef4739e0816ab698 2500 Вт" />
</Frame>

Инспектор предоставляет ряд функций для взаимодействия с вашим сервером MCP:

### Панель подключения к серверу

* Позволяет выбрать [транспорт](/legacy/concepts/transports) для подключения к серверу
* Для локальных серверов поддерживается настройка аргументов командной строки и среды.

### Вкладка «Ресурсы»

* Отображает все доступные ресурсы
* Отображает метаданные ресурса (типы MIME, описания)
* Позволяет проверять содержимое ресурсов
* Поддерживает тестирование подписки

### Вкладка «Подсказки»

* Отображает доступные шаблоны подсказок
* Отображает аргументы и описания подсказок.
* Включает экспресс-тестирование с пользовательскими аргументами
* Предварительный просмотр сгенерированных сообщений

### Вкладка «Инструменты»

* Список доступных инструментов
* Отображает схемы и описания инструментов.
* Позволяет проводить тестирование инструментов с использованием пользовательских входных данных.
* Отображает результаты выполнения инструмента

### Панель уведомлений

* Отображает все журналы, записанные с сервера.
* Отображает уведомления, полученные от сервера.

## Передовые методы

### Рабочий процесс разработки

1. Начать разработку
   * Запустите инспектор вместе с вашим сервером
   * Проверьте базовое подключение
   * Проверка согласования возможностей

2. Итеративное тестирование
   * Внесите изменения на сервер
   * Пересобрать сервер
   * Переподключите инспектор
   * Тестирование затронутых функций
   * Мониторинг сообщений

3. Протестируйте граничные случаи.
   * Неверные данные
   * Отсутствуют аргументы запроса
   * Параллельные операции
   * Проверка обработки ошибок и ответов об ошибках.

## Следующие шаги

<CardGroup cols={2}>
  <Card title="Репозиторий инспектора" icon="github" href="https://github.com/modelcontextprotocol/inspector">
    Ознакомьтесь с исходным кодом инспектора MCP.
  </Карточка>

  <Card title="Руководство по отладке" icon="bug" href="/legacy/tools/debugging">
    Узнайте о более широких стратегиях отладки.
  </Карточка>
</CardGroup>