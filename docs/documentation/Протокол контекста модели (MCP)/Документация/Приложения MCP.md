> ## Индекс документации
Полный индекс документации доступен по адресу: https://modelcontextprotocol.io/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Приложения MCP

> Создавайте интерактивные приложения с пользовательским интерфейсом, которые отображаются внутри хостов MCP, таких как Claude Desktop.

<Совет>
  Для получения исчерпывающей документации по API, расширенных шаблонов и полной спецификации посетите [официальную документацию MCP Apps](https://modelcontextprotocol.github.io/ext-apps).
</Совет>

Текстовые ответы имеют свои ограничения. Иногда пользователям необходимо взаимодействовать с данными, а не...
Только что прочитал об этом. Приложения MCP позволяют серверам возвращать интерактивные HTML-интерфейсы (данные).
визуализации, формы, панели мониторинга), которые отображаются непосредственно в чате.

## Почему бы просто не создать веб-приложение?

Вы могли бы создать автономное веб-приложение и отправлять пользователям ссылку. Однако приложения MCP
Мы предлагаем следующие ключевые преимущества, которые не может обеспечить отдельная страница:

**Сохранение контекста.** Приложение работает внутри диалога. Пользователи не...
Переключаться между вкладками, терять место, где остановились, или гадать, в каком чате находилась эта панель управления.
Пользовательский интерфейс представлен здесь же, рядом с обсуждением, которое к нему привело.

**Двунаправленный поток данных.** Ваше приложение может вызывать любой инструмент на сервере MCP, и
Хостинг может передавать свежие результаты в ваше приложение. Автономному веб-приложению потребуется его
Собственный API, аутентификация и управление состоянием. Приложения MCP получают это через существующие API.
Узоры MCP.
**Интеграция с возможностями хоста**. Приложение может делегировать действия хосту, который затем может вызывать возможности и инструменты, уже подключенные пользователем (при условии согласия пользователя). Вместо того чтобы каждое приложение внедряло и поддерживало прямую интеграцию (например, с почтовыми сервисами), приложение может запросить результат (например, «запланировать эту встречу»), а хост перенаправит его через уже подключенные возможности пользователя.
**Гарантии безопасности.** Приложения MCP работают в изолированном iframe, управляемом системой.
хост. Они не могут получить доступ к родительской странице, украсть файлы cookie или выйти за пределы своего хоста.
контейнер. Это означает, что хосты могут безопасно отображать сторонние приложения, не доверяя им.
Автор сервера полностью.

Если ваши задачи не требуют использования этих свойств, то обычное веб-приложение может оказаться более подходящим вариантом.
Было бы проще. Но если вы хотите тесной интеграции с дискуссией на основе магистерской программы,
MCP Apps — гораздо более эффективный инструмент.

## Как работают приложения MCP

Традиционные инструменты MCP возвращают текст, изображения, ресурсы или структурированные данные, которые хост отображает в виде
часть разговора. Приложения MCP расширяют эту модель, позволяя инструментам...
укажите ссылку на интерактивный пользовательский интерфейс в описании инструмента, который хост должен указать.
Рендеринг на месте.

Основной шаблон объединяет два примитива MCP: инструмент, объявляющий ресурс пользовательского интерфейса.
в его описании, а также ресурс пользовательского интерфейса, который отображает данные в виде интерактивного HTML-кода.
интерфейс.

Когда большая языковая модель (LLM) решает вызвать инструмент, поддерживающий приложения MCP,
Вот что происходит:

1. **Предварительная загрузка пользовательского интерфейса**: В описании инструмента указан объект `_meta.ui.resourceUri`.
   Поле, указывающее на ресурс `ui://`. Хост может предварительно загрузить этот ресурс перед использованием.
   Этот инструмент даже так называется, что позволяет использовать такие функции, как потоковая передача входных данных инструмента в систему.
   приложение.

2. **Получение ресурса**: Хост получает ресурс пользовательского интерфейса с сервера.
   Ресурс содержит HTML-страницу, часто в комплекте с JavaScript и CSS для
   Простота. Приложения также могут загружать внешние скрипты и ресурсы из источников.
   указано в `_meta.ui.csp`.

3. **Изолированная отрисовка**: Веб-хостинги обычно отрисовывают HTML внутри
   в изолированной среде [iframe](https://developer.mozilla.org/en-US/docs/Web/HTML/Element/iframe)
   в рамках беседы. Песочница ограничивает доступ приложения к родительскому процессу.
   страница, обеспечивающая безопасность. Объект `_meta.ui` ресурса может включать в себя:
   «Разрешения» на запрос дополнительных возможностей (например, микрофона, камеры)
   а также `csp` для управления тем, из каких внешних источников приложение может загружать ресурсы.

4. **Двусторонняя связь**: Приложение и хост обмениваются данными через
   Протокол JSON-RPC, формирующий собственный диалект MCP. Некоторые запросы и
   Уведомления передаются в основной протокол MCP (например, `tools/call`), некоторые из них
   Они похожи (например, `ui/initialize`), и большинство из них являются новыми и имеют название метода `ui/`.
   префикс. Приложение может запрашивать вызовы инструментов, отправлять сообщения, обновлять модель.
   контекст и получать данные от хоста.

```тема русалки={null}
диаграмма последовательности
    участник Пользователь
    участник Агент
    Приложение участника в формате iframe приложения MCP
    Участник выступает в роли сервера MCP.

    Пользователь->>Агент: "показать аналитику"
    Примечание к приложению User: интерактивное приложение отображается в чате.
    Агент->>Сервер: инструменты/вызов
    Сервер-->>Агент: ввод/результат инструмента
    Агент-->>Приложение: результат работы инструмента передан в приложение
    Пользователь->>Приложение: взаимодействие пользователя
    Приложение -> Агент: инструменты/запрос на звонок
    Агент->>Сервер: инструменты/вызов (переадресован)
    Сервер-->>Агент: свежие данные
    Агент-->>Приложение: свежие данные
    Примечание для пользователя/приложения: приложение обновляется с учетом новых данных.
    Приложение-->>Агент: обновление контекста
```

Приложение остается изолированным от хоста, но при этом может вызывать инструменты MCP.
защищенный канал postMessage.

## Когда использовать приложения MCP

Приложения MCP хорошо подходят, если ваш сценарий использования включает в себя:

**Изучение сложных данных.** Пользователь спрашивает: «Покажите мне продажи по регионам». Текст
В ответном сообщении могут быть перечислены цифры, но приложение MCP может отобразить интерактивную карту, где
Пользователи щелкают по регионам, чтобы детализировать информацию, наводят курсор для просмотра подробностей и переключаются между ними.
метрики, и всё это без дополнительных запросов.

**Настройка с множеством параметров.** Настройка развертывания включает в себя десятки параметров.
Взаимозависимые решения. Вместо диалога типа («Какой?»
регион?" "Какой размер экземпляра?" "Включить автомасштабирование?"), приложение MCP представляет собой
Форма, в которой пользователи видят все варианты сразу, с проверкой данных и значениями по умолчанию.

**Просмотр мультимедийного контента.** Когда пользователь запрашивает просмотр PDF-файла, 3D-модели или
Предварительный просмотр сгенерированных изображений и текстовых описаний недостаточен. Приложение MCP встраивает...
Реальный зритель (панорамирование, масштабирование, вращение) непосредственно в разговоре.

**Мониторинг в реальном времени.** Панель мониторинга, отображающая метрики, журналы или данные системы в режиме реального времени.
Статус требует постоянного обновления. Приложение MCP поддерживает постоянное соединение.
Обновление отображения по мере изменения данных без необходимости для пользователя спрашивать: «Что происходит?»
Какова ситуация на данный момент?

**Многоэтапные рабочие процессы.** Утверждение отчетов о расходах, проверка изменений в коде или
Сортировка вопросов включает в себя проверку каждого элемента по отдельности. Приложение MCP предоставляет...
элементы управления навигацией, кнопки действий и состояние, сохраняющееся на протяжении всего процесса.
взаимодействия.

## Начиная

Вам потребуется Node.js версии 18 или выше. Знание Node.js не требуется.
с помощью [инструментов MCP](/specification/2025-11-25/server/tools) и
[ресурсы](/specification/2025-11-25/server/resources) рекомендуется, поскольку MCP
Приложения сочетают в себе оба основных принципа. Опыт работы с ними.
[MCP TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk)
Это поможет вам лучше понять шаблоны работы на стороне сервера.

Самый быстрый способ создать приложение MCP — использовать агента программирования на основе искусственного интеллекта вместе с MCP.
Навык «Приложения». Если вы предпочитаете настраивать проект вручную, перейдите к следующему шагу.
[Ручная настройка](#manual-setup).

### Использование агента программирования на основе ИИ

Агенты ИИ-программирования с поддержкой навыков могут создать полноценный проект приложения MCP для
Навыки — это папки с инструкциями и ресурсами, которые ваш агент загружает, когда...
актуально. Они обучают ИИ выполнению специализированных задач, таких как создание MCP.
Приложения.

Навык `create-mcp-app` включает в себя рекомендации по архитектуре, лучшие практики и многое другое.
Рабочие примеры, которые агент использует для создания вашего проекта.

<Шаги>
  <Заголовок шага="Установка навыка">
    Если вы используете Claude Code, вы можете установить навык напрямую с помощью следующей команды:

    ```
    /plugin marketplace add modelcontextprotocol/ext-apps
    /plugin install mcp-apps@modelcontextprotocol-ext-apps
    ```

    Вы также можете использовать [Vercel Skills CLI](https://skills.sh/) для установки навыков в различных агентах ИИ-программирования:

    ```bash theme={null}
    npx skills add modelcontextprotocol/ext-apps
    ```

    В качестве альтернативы вы можете установить навык вручную, клонировав репозиторий ext-apps:

    ```bash theme={null}
    git clone https://github.com/modelcontextprotocol/ext-apps.git
    ```

    А затем скопировать навык в соответствующее место для вашего агента:

    | Агент                                                                                                                                                                      | Каталог навыков (macOS/Linux) | Каталог навыков (Windows)             |
    | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------- | ------------------------------------- |
    | [Код Клода](https://docs.anthropic.com/en/docs/claude-code/skills)                                                                                                         | `~/.claude/skills/`           | `%USERPROFILE%\.claude\skills\`       |
    | [VS Code](https://code.visualstudio.com/docs/copilot/customization/agent-skills) и [GitHub Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) | `~/.copilot/skills/`          | `%USERPROFILE%\.copilot\skills\`      |
    | [Gemini CLI](https://geminicli.com/docs/cli/skills/)                                                                                                                       | `~/.gemini/skills/`           | `%USERPROFILE%\.gemini\skills\`       |
    | [Cline](https://cline.bot/blog/cline-3-48-0-skills-and-websearch-make-cline-smarter)                                                                                       | `~/.cline/skills/`            | `%USERPROFILE%\.cline\skills\`        |
    | [Goose](https://block.github.io/goose/docs/guides/context-engineering/using-skills/)                                                                                       | `~/.config/goose/skills/`     | `%USERPROFILE%\.config\goose\skills\` |
    | [Codex](https://developers.openai.com/codex/skills/)                                                                                                                       | `~/.codex/skills/`            | `%USERPROFILE%\.codex\skills\`        |

    <Примечание>
      Этот список не является исчерпывающим. Другие агенты могут предоставлять услуги в других регионах; проверьте документацию вашего агента.
    </Примечание>

    Например, с помощью Claude Code вы можете установить навык глобально (он доступен во всех проектах):

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      cp -r ext-apps/plugins/mcp-apps/skills/create-mcp-app ~/.claude/skills/create-mcp-app
      ```

      ```Тема Windows PowerShell={null}
      Copy-Item -Recurse ext-apps\plugins\mcp-apps\skills\create-mcp-app $env:USERPROFILE\.claude\skills\create-mcp-app
      ```
    </CodeGroup>

    Или установите его только для одного проекта, скопировав в `.claude/skills/` в каталоге вашего проекта:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      mkdir -p .claude/skills && cp -r ext-apps/plugins/mcp-apps/skills/create-mcp-app .claude/skills/create-mcp-app
      ```

      ```Тема Windows PowerShell={null}
      New-Item -ItemType Directory -Force -Path .claude\skills | Out-Null; Copy-Item -Recurse ext-apps\plugins\mcp-apps\skills\create-mcp-app .claude\skills\create-mcp-app
      ```
    </CodeGroup>

    Чтобы убедиться, что навык установлен, спросите у своего агента: «К каким навыкам у вас есть доступ?» — вы должны увидеть `create-mcp-app` в списке доступных навыков.
  </Шаг>

  <Шаг title="Создайте свое приложение">
    Попросите своего ИИ-программиста создать это:

    ```
    Создайте приложение MCP, отображающее палитру цветов.
    ```

    Агент распознает, что навык `create-mcp-app` актуален, загрузит его инструкции, а затем создаст полноценный проект, включающий серверные, пользовательские и конфигурационные файлы.

    <Frame caption="Создание нового приложения MCP с помощью Claude Code">
      <img src="https://mintcdn.com/mcp/GU_E-622SLWFdCrP/images/quickstart-apps/create-mcp-app-skill.gif?s=6c3a3b8a7590b5e97b5c3d8480a9ab12" alt="Создание нового приложения MCP с помощью Claude Code" data-og-width="800" width="800" data-og-height="563" height="563" data-path="images/quickstart-apps/create-mcp-app-skill.gif" data-optimize="true" data-opv="3" />
    </Frame>
  </Шаг>

  <Шаг title="Запустите приложение">
    <CodeGroup>
      ```bash macOS/Linux theme={null}
      npm install && npm run build && npm run serve
      ```

      ```Тема Windows PowerShell={null}
      npm install; npm run build; npm run serve
      ```
    </CodeGroup>

    <Совет>
      Возможно, вам потребуется убедиться, что вы находитесь в папке **приложения**, прежде чем выполнять указанные выше команды.
    </Совет>
  </Шаг>

  <Шаг title="Протестируйте ваше приложение">
    Следуйте инструкциям в разделе [Тестирование вашего приложения](#testing-your-app) ниже. В примере с палитрой цветов начните новый чат и попросите Клода предоставить вам палитру цветов.

    <Frame caption="Тестирование палитры цветов в Claude">
      <img src="https://mintcdn.com/mcp/GU_E-622SLWFdCrP/images/quickstart-apps/test-color-picker.gif?s=09413b99bc31d7edc7f9aa22df4faa6a" alt="Testing the color picker in Claude" data-og-width="800" width="800" data-og-height="544" height="544" data-path="images/quickstart-apps/test-color-picker.gif" data-optimize="true" data-opv="3" />
    </Frame>
  </Шаг>
</Шаги>

### Ручная настройка

Если вы не используете агента для программирования на основе ИИ или предпочитаете разобраться в настройке.
Для выполнения этого процесса следуйте этим шагам.

<Шаги>
  <Заголовок шага: Создание структуры проекта">
    В типичном проекте MCP App серверный код отделен от кода пользовательского интерфейса:

    <Дерево>
      <Tree.Folder name="my-mcp-app" defaultOpen>
        <Tree.File name="package.json" />

        <Tree.File name="tsconfig.json" />

        <Tree.File name="vite.config.ts" />

        <Tree.File name="server.ts" comment="MCP server with tool + resource" />

        <Tree.File name="mcp-app.html" comment="UI entry point" />

        <Tree.Folder name="src" defaultOpen>
          <Tree.File name="mcp-app.ts" comment="UI logic" />
        </Tree.Folder>
      </Tree.Folder>
    </Tree>

    Сервер регистрирует инструмент и предоставляет ресурс пользовательского интерфейса. Файлы пользовательского интерфейса объединяются в один HTML-файл, который сервер возвращает при запросе ресурса хостом.
  </Шаг>

  <Шаг title="Установка зависимостей">
    ```bash theme={null}
    npm install @modelcontextprotocol/ext-apps @modelcontextprotocol/sdk
    npm install -D typescript vite vite-plugin-singlefile express cors @types/express @types/cors tsx
    ```

    Пакет `ext-apps` предоставляет вспомогательные функции как для серверной части (регистрация инструментов и ресурсов), так и для клиентской части (класс `App` для связи пользовательского интерфейса с хостом). Vite с плагином `vite-plugin-singlefile` объединяет ваш пользовательский интерфейс в один HTML-файл, который можно использовать в качестве ресурса.
  </Шаг>

  <Шаг title="Настройка проекта">
    <Вкладки>
      <Tab title="package.json">
        Параметр `"type": "module"` включает синтаксис модулей ES. Скрипт `build` использует переменную среды `INPUT`, чтобы указать Vite, какой HTML-файл следует включить в сборку. Скрипт `serve` запускает ваш сервер с использованием `tsx` для выполнения TypeScript.

        ```json theme={null}
        {
          "type": "module",
          "scripts": {
            "build": "INPUT=mcp-app.html vite build",
            "serve": "npx tsx server.ts"
          }
        }
        ```
      </Tab>

      <Tab title="tsconfig.json">
        Конфигурация TypeScript ориентирована на современный JavaScript (`ES2022`) и использует модули ESNext с разрешением сборки, что хорошо работает с Vite. Массив `include` охватывает как серверный код в корневом каталоге, так и код пользовательского интерфейса в `src/`.

        ```json theme={null}
        {
          "compilerOptions": {
            "цель": "ES2022",
            "модуль": "ESNext",
            "moduleResolution": "bundler",
            "строгий": истинный,
            "esModuleInterop": true,
            "skipLibCheck": true,
            "outDir": "dist"
          },
          "include": ["*.ts", "src/**/*.ts"]
        }
        ```
      </Tab>

      <Tab title="vite.config.ts">
        ```typescript theme={null}
        import { defineConfig } from "vite";
        import { viteSingleFile } from "vite-plugin-singlefile";

        export default defineConfig({
          плагины: [viteSingleFile()],
          строить: {
            outDir: "dist",
            rollupOptions: {
              вход: process.env.INPUT,
            },
          },
        });
        ```
      </Tab>
    </Вкладки>
  </Шаг>

  <Заголовок шага="Создайте проект">
    После того, как структура и конфигурация проекта будут настроены, перейдите к разделу [Создание приложения MCP](#building-an-mcp-app) ниже, чтобы реализовать сервер и пользовательский интерфейс.
  </Шаг>
</Шаги>

## Создание приложения MCP

Давайте создадим простое приложение, которое отображает текущее время сервера. Вот пример.
демонстрируется полная схема: регистрация инструмента с метаданными пользовательского интерфейса, предоставление доступа к нему.
Встроенный HTML-код в качестве ресурса и создание пользовательского интерфейса, взаимодействующего с сервером.

### Реализация сервера

Серверу необходимо сделать две вещи: зарегистрировать инструмент, который включает в себя
поле `_meta.ui.resourceUri` и зарегистрировать обработчик ресурсов, который будет обслуживать
Скомпилированный HTML-код. Вот полный файл сервера:

```typescript theme={null}
// server.ts
console.log("Запуск сервера приложений MCP...");

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
импорт {
  registerAppTool,
  registerAppResource,
  RESOURCE_MIME_TYPE,
} из "@modelcontextprotocol/ext-apps/server";
импортировать cors из "cors";
импортировать express из "express";
import fs from "node:fs/promises";
импортируем путь из "node:path";

const server = new McpServer({
  имя: "Мой сервер приложений MCP",
  версия: "1.0.0",
});

// Схема ui:// сообщает хостам, что это ресурс приложения MCP.
// Структура путей произвольная; организуйте их так, как это имеет смысл для вашего приложения.
const resourceUri = "ui://get-time/mcp-app.html";

// Зарегистрируйте инструмент, который возвращает текущее время
registerAppTool(
  сервер,
  "получить время",
  {
    заголовок: "Получить время",
    Описание: "Возвращает текущее серверное время."
    inputScheme: {},
    _meta: { ui: {resourceUri } },
  },
  async () => {
    const time = new Date().toISOString();
    возвращаться {
      содержимое: [{ тип: "текст", текст: время }],
    };
  },
);

// Зарегистрируйте ресурс, который предоставляет упакованный HTML-код
registerAppResource(
  сервер,
  ресурсUri,
  ресурсUri,
  { mimeType: RESOURCE_MIME_TYPE },
  async () => {
    const html = await fs.readFile(
      path.join(import.meta.dirname, "dist", "mcp-app.html"),
      "utf-8",
    );
    возвращаться {
      Содержание: [
        { uri: resourceUri, mimeType: RESOURCE_MIME_TYPE, text: html },
      ],
    };
  },
);

// Предоставляем доступ к серверу MCP по протоколу HTTP
const expressApp = express();
expressApp.use(cors());
expressApp.use(express.json());

expressApp.post("/mcp", async (req, res) => {
  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: undefined,
    enableJsonResponse: true,
  });
  res.on("close", () => transport.close());
  Ожидание выполнения server.connect(transport);
  await transport.handleRequest(req, res, req.body);
});

expressApp.listen(3001, (err) => {
  если (ошибка) {
    console.error("Ошибка запуска сервера:", err);
    process.exit(1);
  }
  console.log("Сервер прослушивает http://localhost:3001/mcp");
});
```

Давайте разберем ключевые моменты:

* **`resourceUri`**: Схема `ui://` сообщает хостам, что это ресурс приложения MCP.
  Структура пути произвольна.
* **`registerAppTool`**: Регистрирует инструмент с полем `_meta.ui.resourceUri`.
  Когда хост вызывает этот инструмент, пользовательский интерфейс загружается и отображается, а результат работы инструмента передается ему по прибытии.
* **`registerAppResource`**: Предоставляет упакованный HTML-код, когда хост запрашивает ресурс пользовательского интерфейса.
* **Сервер Express**: Предоставляет доступ к серверу MCP по протоколу HTTP через порт 3001.

### Реализация пользовательского интерфейса

Пользовательский интерфейс состоит из HTML-страницы и модуля TypeScript, использующего `App`.
Класс для связи с хостом. Вот HTML-код:

```html theme={null}
<!-- mcp-app.html -->
<!DOCTYPE html>
<html lang="en">
  <голова>
    <meta charset="UTF-8" />
    <title>Приложение Get Time</title>
  </head>
  <тело>
    <p>
      <strong>Время сервера:</strong>
      <code id="server-time">Загрузка...</code>
    </p>
    <button id="get-time-btn">Получить серверное время</button>
    <script type="module" src="/src/mcp-app.ts"></script>
  </body>
</html>
```

А также модуль TypeScript:

```typescript theme={null}
// src/mcp-app.ts
import { App } from "@modelcontextprotocol/ext-apps";

const serverTimeEl = document.getElementById("server-time")!;
const getTimeBtn = document.getElementById("get-time-btn")!;

const app = new App({ name: "Приложение для получения времени", version: "1.0.0" });

// Установить связь с хостом
app.connect();

// Обработка первоначального результата работы инструмента, отправленного хостом
app.ontoolresult = (result) => {
  const time = result.content?.find((c) => c.type === "text")?.text;
  serverTimeEl.textContent = время ?? "[ОШИБКА]";
};

// Активно вызывать инструменты при взаимодействии пользователей с пользовательским интерфейсом
getTimeBtn.addEventListener("click", async () => {
  const result = await app.callServerTool({
    имя: "get-time",
    аргументы: {},
  });
  const time = result.content?.find((c) => c.type === "text")?.text;
  serverTimeEl.textContent = время ?? "[ОШИБКА]";
});
```

Ключевые моменты:

* **`app.connect()`**: Устанавливает связь с хостом. Вызовите эту функцию один раз.
  при инициализации вашего приложения.
* **`app.ontoolresult`**: Функция обратного вызова, которая срабатывает, когда хост отправляет инструмент.
  результат для вашего приложения (например, при первом вызове инструмента и отрисовке пользовательского интерфейса).
* **`app.callServerTool()`**: Позволяет вашему приложению заблаговременно вызывать инструменты на сервере.
  Учитывайте, что каждый вызов включает в себя обмен данными с сервером и обратно, поэтому проектируйте свои запросы соответствующим образом.
  Пользовательский интерфейс для корректной обработки задержек.

Класс `App` предоставляет дополнительные методы для ведения журналов, открытия URL-адресов и т. д.
Обновление контекста модели с помощью структурированных данных из вашего приложения. См. полный текст.
[Документация по API](https://modelcontextprotocol.github.io/ext-apps/api/).

## Тестирование вашего приложения

Чтобы протестировать ваше MCP-приложение, соберите пользовательский интерфейс и запустите локальный сервер:

<CodeGroup>
  ```bash macOS/Linux theme={null}
  npm run build && npm run serve
  ```

  ```Тема Windows PowerShell={null}
  npm run build; npm run serve
  ```
</CodeGroup>

В конфигурации по умолчанию ваш сервер будет доступен по адресу:
`http://localhost:3001/mcp`. Однако для отображения вашего приложения вам потребуется MCP.
Хостинг, поддерживающий приложения MCP. У вас есть несколько вариантов.

### Тестирование с помощью Клода

[Claude](https://claude.ai) (веб-версия) и [Claude Desktop](https://claude.ai/download)
Поддерживаются приложения MCP. Для локальной разработки вам потребуется предоставить доступ к вашему серверу.
Интернет. Вы можете запустить локальный сервер MCP и использовать такие инструменты, как `cloudflared`.
для прокладки туннельного транспорта.

В отдельном терминале выполните следующую команду:

```bash theme={null}
npx cloudflared tunnel --url http://localhost:3001
```

Скопируйте сгенерированный URL (например, `https://random-name.trycloudflare.com`) и добавьте его.
в качестве [пользовательского коннектора](https://support.anthropic.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp)
В Claude — перейдите в свой профиль, затем в **Настройки**, **Коннекторы** и
Наконец, **добавьте пользовательский коннектор**.

<Примечание>
  Пользовательские коннекторы доступны в платных тарифных планах Claude (Pro, Max или Team).
</Примечание>

<Frame caption="Добавление пользовательского коннектора в Claude">
  <img src="https://mintcdn.com/mcp/GU_E-622SLWFdCrP/images/quickstart-apps/add-custom-connector.gif?s=c4ec0750413ff7575c7f9492e2713212" alt="Добавление пользовательского коннектора в Claude" data-og-width="800" width="800" data-og-height="543" height="543" data-path="images/quickstart-apps/add-custom-connector.gif" data-optimize="true" data-opv="3" />
</Frame>

### Тестирование с использованием базового хоста

В репозитории `ext-apps` находится тестовый хост для разработки. Клонируйте репозиторий и
установить зависимости:

<CodeGroup>
  ```bash macOS/Linux theme={null}
  git clone https://github.com/modelcontextprotocol/ext-apps.git
  cd ext-apps/examples/basic-host
  npm install
  ```

  ```Тема Windows PowerShell={null}
  git clone https://github.com/modelcontextprotocol/ext-apps.git
  cd ext-apps\examples\basic-host
  npm install
  ```
</CodeGroup>

Запуск команды `npm start` из `ext-apps/examples/basic-host/` запустит basic-host.
тестовый интерфейс. Для подключения к конкретному серверу (например, к тому, который вы разрабатываете).
Передайте переменную среды `SERVERS` непосредственно в коде:

<CodeGroup>
  ```bash macOS/Linux theme={null}
  SERVERS='["http://localhost:3001/mcp"]' npm start
  ```

  ```Тема Windows PowerShell={null}
  $env:SERVERS='["http://localhost:3001/mcp"]'; npm start
  ```
</CodeGroup>

Перейдите по адресу `http://localhost:8080`. Вы увидите простой интерфейс, где сможете...
Выберите инструмент и вызовите его. При вызове инструмента хост загружает пользовательский интерфейс.
ресурс отображается в изолированном iframe. Затем вы можете взаимодействовать с ним.
Проверьте приложение и убедитесь, что вызовы инструментов работают корректно.

<Frame caption="Тестирование приложения MCP для QR-кодов с помощью базового хоста">
  <img src="https://mintcdn.com/mcp/GU_E-622SLWFdCrP/images/quickstart-apps/qr-code-server.gif?s=48a3b47239b8394017c0949162d63de9" alt="Пример работы приложения MCP с QR-кодом на базовом хосте" data-og-width="800" width="800" data-og-height="596" height="596" data-path="images/quickstart-apps/qr-code-server.gif" data-optimize="true" data-opv="3" />
</Frame>

## Модель безопасности

Приложения MCP работают в изолированной среде.
[iframe](https://developer.mozilla.org/docs/Web/HTML/Element/iframe), который
обеспечивает надежную изоляцию от основного приложения. Песочница предотвращает ваши
приложение не может получить доступ к родительскому окну
[DOM](https://developer.mozilla.org/docs/Web/API/Document_Object_Model), чтение
файлы cookie хоста или локальное хранилище, переход на родительскую страницу или выполнение
скрипты в родительском контексте.

Вся связь между вашим приложением и хостом осуществляется через
[API postMessage](https://developer.mozilla.org/docs/Web/API/Window/postMessage),
Класс `App`, показанный выше, абстрагирует для вас этот процесс. Хост управляет тем, какой из них...
возможности, к которым ваше приложение может получить доступ. Например, хостинг-провайдер может ограничить доступ к определенным инструментам.
Приложение может вызывать или отключать функцию `sendOpenLink`.

Песочница предназначена для предотвращения выхода приложений за пределы системы и доступа к данным хоста или пользователя.

## Поддержка фреймворков

Приложения MCP используют собственный диалект MCP, построенный на основе JSON-RPC, как и основной протокол.
Некоторые сообщения передаются в обычный MCP (например, `tools/call`), а другие — нет.
специфично для приложений (например, `ui/initialize`). Транспорт —
[postMessage](https://developer.mozilla.org/docs/Web/API/Window/postMessage)
вместо stdio или HTTP. Поскольку это все стандартные веб-примитивы, вы можете использовать любой из них.
либо никакой структуры, либо её отсутствие.

Класс `App` из `@modelcontextprotocol/ext-apps` — это удобная обертка.
Это не обязательное требование. Вы можете реализовать это самостоятельно.
[протокол postMessage](https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/draft/apps.mdx)
Если вы предпочитаете избегать зависимостей или нуждаетесь в более жестком контроле, вы можете использовать прямой доступ.

Каталог [примеров](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples)
Включает стартовые шаблоны для React, Vue, Svelte, Preact, Solid и чистого JavaScript.
JavaScript. Здесь представлены рекомендуемые шаблоны для каждой системы фреймворка.
Но это лишь примеры, а не обязательные требования. Вы можете выбрать то, что вам подходит.
Лучший вариант для вашего случая.

## Поддержка клиентов

<Примечание>
  MCP Apps — это расширение [основной спецификации MCP](/спецификации). Поддержка хоста зависит от клиента.
</Примечание>

В настоящее время приложения MCP поддерживаются [Claude](https://claude.ai).
[Claude Desktop](https://claude.ai/download),
[Visual Studio Code (Insiders)](https://code.visualstudio.com/insiders), [Goose](https://block.github.io/goose/), [Postman](https://postman.com) и [MCPJam](https://www.mcpjam.com/). См.
[Страница клиентов](/clients) содержит полный список клиентов MCP и информацию об их поддержке.
функции.

Если вы разрабатываете клиентское приложение для MCP и хотите поддерживать приложения MCP, у вас есть два варианта:

1. **Используйте фреймворк**: [`@mcp-ui/client`](https://github.com/MCP-UI-Org/mcp-ui)
   Этот пакет предоставляет компоненты React для рендеринга и взаимодействия с приложениями MCP.
   представления в вашем основном приложении. См.
   [Документация MCP-UI](https://mcpui.dev/) содержит подробную информацию об использовании.

2. **Создание на AppBridge**: SDK включает в себя
   [**App Bridge**](https://modelcontextprotocol.github.io/ext-apps/api/modules/app-bridge.html)
   модуль, отвечающий за отрисовку приложений в изолированных iframe, передачу сообщений, инструмент.
   Проксирование звонков и обеспечение соблюдения политик безопасности.
   [Пример использования базового хоста](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-host)
   показывает, как его интегрировать.

См. [документацию по API](https://modelcontextprotocol.github.io/ext-apps/api/)
Подробности реализации см. здесь.

## Примеры

Репозиторий [ext-apps](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples)
Включает готовые к запуску примеры, демонстрирующие различные варианты использования:

* **3D-моделирование и визуализация**:
  [map-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/map-server)
  (Глобус из CesiumJS),
  [threejs-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/threejs-server)
  (Сцены на Three.js),
  [shadertoy-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/shadertoy-server)
  (эффекты шейдера)
* **Исследование данных**:
  [cohort-heatmap-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/cohort-heatmap-server),
  [customer-segmentation-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/customer-segmentation-server),
  [wiki-explorer-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/wiki-explorer-server)
* **Бизнес-приложения**:
  [scenario-modeler-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/scenario-modeler-server),
  [budget-allocator-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/budget-allocator-server)
* **СМИ**:
  [pdf-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/pdf-server),
  [video-resource-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/video-resource-server),
  [sheet-music-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/sheet-music-server),
  [say-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/say-server)
  (преобразование текста в речь)
* **Утилиты**:
  [qr-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/qr-server),
  [system-monitor-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/system-monitor-server),
  [transcript-server](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/transcript-server)
  (преобразование речи в текст)
* **Стартовые шаблоны**:
  [React](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-server-react),
  [Vue](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-server-vue),
  [Svelte](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-server-svelte),
  [Preact](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-server-preact),
  [Solid](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-server-solid),
  [чистый JavaScript](https://github.com/modelcontextprotocol/ext-apps/tree/main/examples/basic-server-vanillajs)

Чтобы запустить любой пример:

<CodeGroup>
  ```bash macOS/Linux theme={null}
  git clone https://github.com/modelcontextprotocol/ext-apps
  cd ext-apps/examples/<example-name>
  npm install && npm start
  ```

  ```Тема Windows PowerShell={null}
  git clone https://github.com/modelcontextprotocol/ext-apps
  cd ext-apps\examples\<example-name>
  npm install; npm start
  ```
</CodeGroup>

## Узнать больше

<CardGroup cols={2}>
  <Card title="Документация API" icon="book" href="https://modelcontextprotocol.github.io/ext-apps/api/">
    Полная справочная информация по SDK и API.
  </Карточка>

  <Card title="GitHub Repository" icon="github" href="https://github.com/modelcontextprotocol/ext-apps">
    Исходный код, примеры и система отслеживания ошибок.
  </Карточка>

  <Card title="Specification" icon="file-lines" href="https://github.com/modelcontextprotocol/ext-apps/blob/main/specification/draft/apps.mdx">
    Технические требования для разработчиков
  </Карточка>
</CardGroup>

## Обратная связь

MCP Apps находится в активной разработке. Если у вас возникнут проблемы или появятся идеи по улучшению, пожалуйста, сообщите нам.
Для внесения улучшений откройте соответствующую заявку.
[Репозиторий GitHub](https://github.com/modelcontextprotocol/ext-apps/issues).
Для более широкого обсуждения направления развития расширения присоединяйтесь к беседе.
в [Обсуждениях на GitHub](https://github.com/modelcontextprotocol/ext-apps/discussions).