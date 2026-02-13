> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Подключите Claude Code к инструментам через MCP

> Узнайте, как подключить Claude Code к вашим инструментам с помощью Model Context Protocol.

export const MCPServersTable = ({platform = "all"}) => {
  const ifYouAreAnAiAgentReadingThisYouShouldInsteadFetch = 'https://api.anthropic.com/mcp-registry/docs';
  const [servers, setServers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  useEffect(() => {
    const fetchServers = async () => {
      try {
        setLoading(true);
        const allServers = [];
        let cursor = null;
        do {
          const url = new URL('https://api.anthropic.com/mcp-registry/v0/servers');
          url.searchParams.set('version', 'latest');
          url.searchParams.set('limit', '100');
          if (cursor) {
            url.searchParams.set('cursor', cursor);
          }
          const response = await fetch(url);
          if (!response.ok) {
            throw new Error(`Failed to fetch MCP registry: ${response.status}`);
          }
          const data = await response.json();
          allServers.push(...data.servers);
          cursor = data.metadata?.nextCursor || null;
        } while (cursor);
        const transformedServers = allServers.map(item => {
          const server = item.server;
          const meta = item._meta?.['com.anthropic.api/mcp-registry'] || ({});
          const worksWith = meta.worksWith || [];
          const availability = {
            claudeCode: worksWith.includes('claude-code'),
            mcpConnector: worksWith.includes('claude-api'),
            claudeDesktop: worksWith.includes('claude-desktop')
          };
          const remotes = server.remotes || [];
          const httpRemote = remotes.find(r => r.type === 'streamable-http');
          const sseRemote = remotes.find(r => r.type === 'sse');
          const preferredRemote = httpRemote || sseRemote;
          const remoteUrl = preferredRemote?.url || meta.url;
          const remoteType = preferredRemote?.type;
          const isTemplatedUrl = remoteUrl?.includes('{');
          let setupUrl;
          if (isTemplatedUrl && meta.requiredFields) {
            const urlField = meta.requiredFields.find(f => f.field === 'url');
            setupUrl = urlField?.sourceUrl || meta.documentation;
          }
          const urls = {};
          if (!isTemplatedUrl) {
            if (remoteType === 'streamable-http') {
              urls.http = remoteUrl;
            } else if (remoteType === 'sse') {
              urls.sse = remoteUrl;
            }
          }
          let envVars = [];
          if (server.packages && server.packages.length > 0) {
            const npmPackage = server.packages.find(p => p.registryType === 'npm');
            if (npmPackage) {
              urls.stdio = `npx -y ${npmPackage.identifier}`;
              if (npmPackage.environmentVariables) {
                envVars = npmPackage.environmentVariables;
              }
            }
          }
          return {
            name: meta.displayName || server.title || server.name,
            description: meta.oneLiner || server.description,
            documentation: meta.documentation,
            urls: urls,
            envVars: envVars,
            availability: availability,
            customCommands: meta.claudeCodeCopyText ? {
              claudeCode: meta.claudeCodeCopyText
            } : undefined,
            setupUrl: setupUrl
          };
        });
        setServers(transformedServers);
        setError(null);
      } catch (err) {
        setError(err.message);
        console.error('Error fetching MCP registry:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchServers();
  }, []);
  const generateClaudeCodeCommand = server => {
    if (server.customCommands && server.customCommands.claudeCode) {
      return server.customCommands.claudeCode;
    }
    const serverSlug = server.name.toLowerCase().replace(/[^a-z0-9]/g, '-');
    if (server.urls.http) {
      return `claude mcp add ${serverSlug} --transport http ${server.urls.http}`;
    }
    if (server.urls.sse) {
      return `claude mcp add ${serverSlug} --transport sse ${server.urls.sse}`;
    }
    if (server.urls.stdio) {
      const envFlags = server.envVars && server.envVars.length > 0 ? server.envVars.map(v => `--env ${v.name}=YOUR_${v.name}`).join(' ') : '';
      const baseCommand = `claude mcp add ${serverSlug} --transport stdio`;
      return envFlags ? `${baseCommand} ${envFlags} -- ${server.urls.stdio}` : `${baseCommand} -- ${server.urls.stdio}`;
    }
    return null;
  };
  if (loading) {
    return <div>Loading MCP servers...</div>;
  }
  if (error) {
    return <div>Error loading MCP servers: {error}</div>;
  }
  const filteredServers = servers.filter(server => {
    if (platform === "claudeCode") {
      return server.availability.claudeCode;
    } else if (platform === "mcpConnector") {
      return server.availability.mcpConnector;
    } else if (platform === "claudeDesktop") {
      return server.availability.claudeDesktop;
    } else if (platform === "all") {
      return true;
    } else {
      throw new Error(`Unknown platform: ${platform}`);
    }
  });
  return <>
      <style jsx>{`
        .cards-container {
          display: grid;
          gap: 1rem;
          margin-bottom: 2rem;
        }
        .server-card {
          border: 1px solid var(--border-color, #e5e7eb);
          border-radius: 6px;
          padding: 1rem;
        }
        .command-row {
          display: flex;
          align-items: center;
          gap: 0.25rem;
        }
        .command-row code {
          font-size: 0.75rem;
          overflow-x: auto;
        }
      `}</style>

      <div className="cards-container">
        {filteredServers.map(server => {
    const claudeCodeCommand = generateClaudeCodeCommand(server);
    const mcpUrl = server.urls.http || server.urls.sse;
    const commandToShow = platform === "claudeCode" ? claudeCodeCommand : mcpUrl;
    return <div key={server.name} className="server-card">
              <div>
                {server.documentation ? <a href={server.documentation}>
                    <strong>{server.name}</strong>
                  </a> : <strong>{server.name}</strong>}
              </div>

              <p style={{
      margin: '0.5rem 0',
      fontSize: '0.9rem'
    }}>
                {server.description}
              </p>

              {server.setupUrl && <p style={{
      margin: '0.25rem 0',
      fontSize: '0.8rem',
      fontStyle: 'italic',
      opacity: 0.7
    }}>
                  Requires user-specific URL.{' '}
                  <a href={server.setupUrl} style={{
      textDecoration: 'underline'
    }}>
                    Get your URL here
                  </a>.
                </p>}

              {commandToShow && !server.setupUrl && <>
                <p style={{
      display: 'block',
      fontSize: '0.75rem',
      fontWeight: 500,
      minWidth: 'fit-content',
      marginTop: '0.5rem',
      marginBottom: 0
    }}>
                  {platform === "claudeCode" ? "Command" : "URL"}
                </p>
                <div className="command-row">
                  <code>
                    {commandToShow}
                  </code>
                </div>
              </>}
            </div>;
  })}
      </div>
    </>;
};

Claude Code может подключаться к сотням внешних инструментов и источников данных через [Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction), открытый стандарт для интеграции AI с инструментами. MCP серверы предоставляют Claude Code доступ к вашим инструментам, базам данных и API.

## Что вы можете делать с MCP

С подключенными MCP серверами вы можете попросить Claude Code:

* **Реализовать функции из трекеров проблем**: "Добавьте функцию, описанную в JIRA задаче ENG-4521, и создайте PR на GitHub."
* **Анализировать данные мониторинга**: "Проверьте Sentry и Statsig, чтобы проверить использование функции, описанной в ENG-4521."
* **Запрашивать базы данных**: "Найдите адреса электронной почты 10 случайных пользователей, которые использовали функцию ENG-4521, на основе нашей базы данных PostgreSQL."
* **Интегрировать дизайны**: "Обновите наш стандартный шаблон электронного письма на основе новых дизайнов Figma, которые были опубликованы в Slack"
* **Автоматизировать рабочие процессы**: "Создайте черновики Gmail, приглашающие этих 10 пользователей на сеанс обратной связи о новой функции."

## Популярные MCP серверы

Вот некоторые часто используемые MCP серверы, которые вы можете подключить к Claude Code:

<Warning>
  Используйте MCP серверы третьих сторон на свой риск - Anthropic не проверил
  корректность или безопасность всех этих серверов.
  Убедитесь, что вы доверяете MCP серверам, которые устанавливаете.
  Будьте особенно осторожны при использовании MCP серверов, которые могут получать ненадежный
  контент, так как это может подвергнуть вас риску внедрения подсказок.
</Warning>

<MCPServersTable platform="claudeCode" />

<Note>
  **Нужна конкретная интеграция?** [Найдите сотни других MCP серверов на GitHub](https://github.com/modelcontextprotocol/servers), или создайте свой собственный, используя [MCP SDK](https://modelcontextprotocol.io/quickstart/server).
</Note>

## Установка MCP серверов

MCP серверы можно настроить тремя различными способами в зависимости от ваших потребностей:

### Вариант 1: Добавить удаленный HTTP сервер

HTTP серверы - это рекомендуемый вариант для подключения к удаленным MCP серверам. Это наиболее широко поддерживаемый транспорт для облачных сервисов.

```bash  theme={null}
# Базовый синтаксис
claude mcp add --transport http <name> <url>

# Реальный пример: Подключение к Notion
claude mcp add --transport http notion https://mcp.notion.com/mcp

# Пример с токеном Bearer
claude mcp add --transport http secure-api https://api.example.com/mcp \
  --header "Authorization: Bearer your-token"
```

### Вариант 2: Добавить удаленный SSE сервер

<Warning>
  Транспорт SSE (Server-Sent Events) устарел. Используйте вместо этого HTTP серверы, где они доступны.
</Warning>

```bash  theme={null}
# Базовый синтаксис
claude mcp add --transport sse <name> <url>

# Реальный пример: Подключение к Asana
claude mcp add --transport sse asana https://mcp.asana.com/sse

# Пример с заголовком аутентификации
claude mcp add --transport sse private-api https://api.company.com/sse \
  --header "X-API-Key: your-key-here"
```

### Вариант 3: Добавить локальный stdio сервер

Stdio серверы работают как локальные процессы на вашей машине. Они идеальны для инструментов, которым нужен прямой доступ к системе или пользовательские скрипты.

```bash  theme={null}
# Базовый синтаксис
claude mcp add [options] <name> -- <command> [args...]

# Реальный пример: Добавить сервер Airtable
claude mcp add --transport stdio --env AIRTABLE_API_KEY=YOUR_KEY airtable \
  -- npx -y airtable-mcp-server
```

<Note>
  **Важно: Порядок опций**

  Все опции (`--transport`, `--env`, `--scope`, `--header`) должны идти **перед** именем сервера. Затем `--` (двойной дефис) отделяет имя сервера от команды и аргументов, которые передаются MCP серверу.

  Например:

  * `claude mcp add --transport stdio myserver -- npx server` → запускает `npx server`
  * `claude mcp add --transport stdio --env KEY=value myserver -- python server.py --port 8080` → запускает `python server.py --port 8080` с `KEY=value` в окружении

  Это предотвращает конфликты между флагами Claude и флагами сервера.
</Note>

### Управление вашими серверами

После настройки вы можете управлять своими MCP серверами с помощью этих команд:

```bash  theme={null}
# Список всех настроенных серверов
claude mcp list

# Получить детали для конкретного сервера
claude mcp get github

# Удалить сервер
claude mcp remove github

# (внутри Claude Code) Проверить статус сервера
/mcp
```

### Динамические обновления инструментов

Claude Code поддерживает MCP уведомления `list_changed`, позволяя MCP серверам динамически обновлять свои доступные инструменты, подсказки и ресурсы без необходимости отключения и переподключения. Когда MCP сервер отправляет уведомление `list_changed`, Claude Code автоматически обновляет доступные возможности от этого сервера.

<Tip>
  Советы:

  * Используйте флаг `--scope` для указания места хранения конфигурации:
    * `local` (по умолчанию): Доступно только вам в текущем проекте (в старых версиях называлось `project`)
    * `project`: Общее для всех в проекте через файл `.mcp.json`
    * `user`: Доступно вам во всех проектах (в старых версиях называлось `global`)
  * Установите переменные окружения с флагами `--env` (например, `--env KEY=value`)
  * Настройте время ожидания запуска MCP сервера, используя переменную окружения MCP\_TIMEOUT (например, `MCP_TIMEOUT=10000 claude` устанавливает тайм-аут в 10 секунд)
  * Claude Code отобразит предупреждение, когда выход инструмента MCP превышает 10 000 токенов. Чтобы увеличить это ограничение, установите переменную окружения `MAX_MCP_OUTPUT_TOKENS` (например, `MAX_MCP_OUTPUT_TOKENS=50000`)
  * Используйте `/mcp` для аутентификации с удаленными серверами, которые требуют аутентификацию OAuth 2.0
</Tip>

<Warning>
  **Пользователи Windows**: На нативной Windows (не WSL) локальные MCP серверы, которые используют `npx`, требуют обертки `cmd /c` для обеспечения правильного выполнения.

  ```bash  theme={null}
  # Это создает command="cmd", который Windows может выполнить
  claude mcp add --transport stdio my-server -- cmd /c npx -y @some/package
  ```

  Без обертки `cmd /c` вы столкнетесь с ошибками "Connection closed", потому что Windows не может напрямую выполнить `npx`. (См. примечание выше для объяснения параметра `--`.)
</Warning>

### MCP серверы, предоставляемые плагинами

[Плагины](/ru/plugins) могут включать MCP серверы, автоматически предоставляя инструменты и интеграции при включении плагина. MCP серверы плагинов работают идентично пользовательским настроенным серверам.

**Как работают MCP серверы плагинов**:

* Плагины определяют MCP серверы в `.mcp.json` в корне плагина или встроенные в `plugin.json`
* Когда плагин включен, его MCP серверы запускаются автоматически
* Инструменты MCP плагина появляются рядом с вручную настроенными инструментами MCP
* Серверы плагинов управляются через установку плагина (не через команды `/mcp`)

**Пример конфигурации MCP плагина**:

В `.mcp.json` в корне плагина:

```json  theme={null}
{
  "database-tools": {
    "command": "${CLAUDE_PLUGIN_ROOT}/servers/db-server",
    "args": ["--config", "${CLAUDE_PLUGIN_ROOT}/config.json"],
    "env": {
      "DB_URL": "${DB_URL}"
    }
  }
}
```

Или встроенные в `plugin.json`:

```json  theme={null}
{
  "name": "my-plugin",
  "mcpServers": {
    "plugin-api": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/api-server",
      "args": ["--port", "8080"]
    }
  }
}
```

**Функции MCP плагинов**:

* **Автоматический жизненный цикл**: Серверы запускаются при включении плагина, но вы должны перезагрузить Claude Code, чтобы применить изменения MCP сервера (включение или отключение)
* **Переменные окружения**: Используйте `${CLAUDE_PLUGIN_ROOT}` для путей относительно плагина
* **Доступ к переменным окружения пользователя**: Доступ к тем же переменным окружения, что и вручную настроенные серверы
* **Несколько типов транспорта**: Поддержка stdio, SSE и HTTP транспортов (поддержка транспорта может варьироваться в зависимости от сервера)

**Просмотр MCP серверов плагинов**:

```bash  theme={null}
# Внутри Claude Code, см. все MCP серверы, включая серверы плагинов
/mcp
```

Серверы плагинов появляются в списке с индикаторами, показывающими, что они поступают из плагинов.

**Преимущества MCP серверов плагинов**:

* **Упакованное распространение**: Инструменты и серверы упакованы вместе
* **Автоматическая настройка**: Не требуется ручная конфигурация MCP
* **Согласованность команды**: Все получают одинаковые инструменты при установке плагина

См. [справочник компонентов плагинов](/ru/plugins-reference#mcp-servers) для деталей по упаковке MCP серверов с плагинами.

## Области установки MCP

MCP серверы можно настроить на трех различных уровнях области, каждый служит отдельным целям для управления доступностью сервера и совместного использования. Понимание этих областей помогает вам определить лучший способ настройки серверов для ваших конкретных потребностей.

### Локальная область

Серверы с локальной областью представляют уровень конфигурации по умолчанию и хранятся в `~/.claude.json` в пути вашего проекта. Эти серверы остаются приватными для вас и доступны только при работе в текущем каталоге проекта. Эта область идеальна для личных серверов разработки, экспериментальных конфигураций или серверов, содержащих чувствительные учетные данные, которые не должны быть общими.

```bash  theme={null}
# Добавить сервер с локальной областью (по умолчанию)
claude mcp add --transport http stripe https://mcp.stripe.com

# Явно указать локальную область
claude mcp add --transport http stripe --scope local https://mcp.stripe.com
```

### Область проекта

Серверы с областью проекта позволяют командной работе, сохраняя конфигурации в файле `.mcp.json` в корневом каталоге вашего проекта. Этот файл предназначен для проверки в систему контроля версий, обеспечивая, чтобы все члены команды имели доступ к одним и тем же инструментам MCP и сервисам. Когда вы добавляете сервер с областью проекта, Claude Code автоматически создает или обновляет этот файл с соответствующей структурой конфигурации.

```bash  theme={null}
# Добавить сервер с областью проекта
claude mcp add --transport http paypal --scope project https://mcp.paypal.com/mcp
```

Результирующий файл `.mcp.json` следует стандартизированному формату:

```json  theme={null}
{
  "mcpServers": {
    "shared-server": {
      "command": "/path/to/server",
      "args": [],
      "env": {}
    }
  }
}
```

По соображениям безопасности Claude Code запрашивает одобрение перед использованием серверов с областью проекта из файлов `.mcp.json`. Если вам нужно сбросить эти выборы одобрения, используйте команду `claude mcp reset-project-choices`.

### Область пользователя

Серверы с областью пользователя хранятся в `~/.claude.json` и обеспечивают доступность между проектами, делая их доступными во всех проектах на вашей машине, оставаясь приватными для вашей учетной записи пользователя. Эта область хорошо подходит для личных служебных серверов, инструментов разработки или сервисов, которые вы часто используете в разных проектах.

```bash  theme={null}
# Добавить сервер пользователя
claude mcp add --transport http hubspot --scope user https://mcp.hubspot.com/anthropic
```

### Выбор правильной области

Выберите вашу область на основе:

* **Локальная область**: Личные серверы, экспериментальные конфигурации или чувствительные учетные данные, специфичные для одного проекта
* **Область проекта**: Серверы, общие для команды, инструменты, специфичные для проекта, или сервисы, необходимые для сотрудничества
* **Область пользователя**: Личные утилиты, необходимые в нескольких проектах, инструменты разработки или часто используемые сервисы

<Note>
  **Где хранятся MCP серверы?**

  * **Область пользователя и локальная**: `~/.claude.json` (в поле `mcpServers` или в путях проекта)
  * **Область проекта**: `.mcp.json` в корне вашего проекта (проверено в систему контроля версий)
  * **Управляемые**: `managed-mcp.json` в системных каталогах (см. [Управляемая конфигурация MCP](#managed-mcp-configuration))
</Note>

### Иерархия области и приоритет

Конфигурации MCP сервера следуют четкой иерархии приоритета. Когда серверы с одинаковым именем существуют в нескольких областях, система разрешает конфликты, приоритизируя серверы с локальной областью в первую очередь, затем серверы с областью проекта и, наконец, серверы с областью пользователя. Этот дизайн гарантирует, что личные конфигурации могут переопределять общие, когда это необходимо.

### Расширение переменных окружения в `.mcp.json`

Claude Code поддерживает расширение переменных окружения в файлах `.mcp.json`, позволяя командам делиться конфигурациями, сохраняя гибкость для путей, специфичных для машины, и чувствительных значений, таких как ключи API.

**Поддерживаемый синтаксис:**

* `${VAR}` - Расширяется до значения переменной окружения `VAR`
* `${VAR:-default}` - Расширяется до `VAR`, если установлена, иначе использует `default`

**Места расширения:**
Переменные окружения могут быть расширены в:

* `command` - Путь исполняемого файла сервера
* `args` - Аргументы командной строки
* `env` - Переменные окружения, передаваемые серверу
* `url` - Для типов HTTP сервера
* `headers` - Для аутентификации HTTP сервера

**Пример с расширением переменной:**

```json  theme={null}
{
  "mcpServers": {
    "api-server": {
      "type": "http",
      "url": "${API_BASE_URL:-https://api.example.com}/mcp",
      "headers": {
        "Authorization": "Bearer ${API_KEY}"
      }
    }
  }
}
```

Если требуемая переменная окружения не установлена и не имеет значения по умолчанию, Claude Code не сможет разобрать конфигурацию.

## Практические примеры

{/* ### Пример: Автоматизировать тестирование браузера с помощью Playwright

  ```bash
  # 1. Добавить MCP сервер Playwright
  claude mcp add --transport stdio playwright -- npx -y @playwright/mcp@latest

  # 2. Написать и запустить тесты браузера
  > "Test if the login flow works with test@example.com"
  > "Take a screenshot of the checkout page on mobile"
  > "Verify that the search feature returns results"
  ``` */}

### Пример: Мониторить ошибки с помощью Sentry

```bash  theme={null}
# 1. Добавить MCP сервер Sentry
claude mcp add --transport http sentry https://mcp.sentry.dev/mcp

# 2. Используйте /mcp для аутентификации с вашей учетной записью Sentry
> /mcp

# 3. Отладка проблем в production
> "What are the most common errors in the last 24 hours?"
> "Show me the stack trace for error ID abc123"
> "Which deployment introduced these new errors?"
```

### Пример: Подключиться к GitHub для проверки кода

```bash  theme={null}
# 1. Добавить MCP сервер GitHub
claude mcp add --transport http github https://api.githubcopilot.com/mcp/

# 2. В Claude Code, аутентифицируйтесь, если необходимо
> /mcp
# Выберите "Authenticate" для GitHub

# 3. Теперь вы можете попросить Claude работать с GitHub
> "Review PR #456 and suggest improvements"
> "Create a new issue for the bug we just found"
> "Show me all open PRs assigned to me"
```

### Пример: Запрос к базе данных PostgreSQL

```bash  theme={null}
# 1. Добавить сервер базы данных с вашей строкой подключения
claude mcp add --transport stdio db -- npx -y @bytebase/dbhub \
  --dsn "postgresql://readonly:pass@prod.db.com:5432/analytics"

# 2. Запрашивайте вашу базу данных естественным образом
> "What's our total revenue this month?"
> "Show me the schema for the orders table"
> "Find customers who haven't made a purchase in 90 days"
```

## Аутентификация с удаленными MCP серверами

Многие облачные MCP серверы требуют аутентификации. Claude Code поддерживает OAuth 2.0 для безопасных соединений.

<Steps>
  <Step title="Добавить сервер, который требует аутентификации">
    Например:

    ```bash  theme={null}
    claude mcp add --transport http sentry https://mcp.sentry.dev/mcp
    ```
  </Step>

  <Step title="Используйте команду /mcp внутри Claude Code">
    В Claude Code используйте команду:

    ```
    > /mcp
    ```

    Затем следуйте шагам в вашем браузере для входа.
  </Step>
</Steps>

<Tip>
  Советы:

  * Токены аутентификации хранятся безопасно и автоматически обновляются
  * Используйте "Clear authentication" в меню `/mcp` для отзыва доступа
  * Если ваш браузер не открывается автоматически, скопируйте предоставленный URL
  * Аутентификация OAuth работает с HTTP серверами
</Tip>

## Добавить MCP серверы из конфигурации JSON

Если у вас есть конфигурация JSON для MCP сервера, вы можете добавить ее напрямую:

<Steps>
  <Step title="Добавить MCP сервер из JSON">
    ```bash  theme={null}
    # Базовый синтаксис
    claude mcp add-json <name> '<json>'

    # Пример: Добавление HTTP сервера с конфигурацией JSON
    claude mcp add-json weather-api '{"type":"http","url":"https://api.weather.com/mcp","headers":{"Authorization":"Bearer token"}}'

    # Пример: Добавление stdio сервера с конфигурацией JSON
    claude mcp add-json local-weather '{"type":"stdio","command":"/path/to/weather-cli","args":["--api-key","abc123"],"env":{"CACHE_DIR":"/tmp"}}'
    ```
  </Step>

  <Step title="Проверить, что сервер был добавлен">
    ```bash  theme={null}
    claude mcp get weather-api
    ```
  </Step>
</Steps>

<Tip>
  Советы:

  * Убедитесь, что JSON правильно экранирован в вашей оболочке
  * JSON должен соответствовать схеме конфигурации MCP сервера
  * Вы можете использовать `--scope user` для добавления сервера в вашу конфигурацию пользователя вместо конфигурации, специфичной для проекта
</Tip>

## Импортировать MCP серверы из Claude Desktop

Если вы уже настроили MCP серверы в Claude Desktop, вы можете их импортировать:

<Steps>
  <Step title="Импортировать серверы из Claude Desktop">
    ```bash  theme={null}
    # Базовый синтаксис 
    claude mcp add-from-claude-desktop 
    ```
  </Step>

  <Step title="Выберите, какие серверы импортировать">
    После запуска команды вы увидите интерактивный диалог, который позволяет вам выбрать, какие серверы вы хотите импортировать.
  </Step>

  <Step title="Проверить, что серверы были импортированы">
    ```bash  theme={null}
    claude mcp list 
    ```
  </Step>
</Steps>

<Tip>
  Советы:

  * Эта функция работает только на macOS и Windows Subsystem for Linux (WSL)
  * Она читает файл конфигурации Claude Desktop из его стандартного местоположения на этих платформах
  * Используйте флаг `--scope user` для добавления серверов в вашу конфигурацию пользователя
  * Импортированные серверы будут иметь те же имена, что и в Claude Desktop
  * Если серверы с одинаковыми именами уже существуют, они получат числовой суффикс (например, `server_1`)
</Tip>

## Использовать Claude Code как MCP сервер

Вы можете использовать Claude Code сам как MCP сервер, к которому могут подключаться другие приложения:

```bash  theme={null}
# Запустить Claude как stdio MCP сервер
claude mcp serve
```

Вы можете использовать это в Claude Desktop, добавив эту конфигурацию в claude\_desktop\_config.json:

```json  theme={null}
{
  "mcpServers": {
    "claude-code": {
      "type": "stdio",
      "command": "claude",
      "args": ["mcp", "serve"],
      "env": {}
    }
  }
}
```

<Warning>
  **Настройка пути исполняемого файла**: Поле `command` должно ссылаться на исполняемый файл Claude Code. Если команда `claude` не находится в PATH вашей системы, вам нужно указать полный путь к исполняемому файлу.

  Чтобы найти полный путь:

  ```bash  theme={null}
  which claude
  ```

  Затем используйте полный путь в вашей конфигурации:

  ```json  theme={null}
  {
    "mcpServers": {
      "claude-code": {
        "type": "stdio",
        "command": "/full/path/to/claude",
        "args": ["mcp", "serve"],
        "env": {}
      }
    }
  }
  ```

  Без правильного пути исполняемого файла вы столкнетесь с ошибками, такими как `spawn claude ENOENT`.
</Warning>

<Tip>
  Советы:

  * Сервер предоставляет доступ к инструментам Claude, таким как View, Edit, LS и т.д.
  * В Claude Desktop попробуйте попросить Claude прочитать файлы в каталоге, внести правки и многое другое.
  * Обратите внимание, что этот MCP сервер только предоставляет инструменты Claude Code вашему MCP клиенту, поэтому ваш собственный клиент отвечает за реализацию подтверждения пользователя для отдельных вызовов инструментов.
</Tip>

## Ограничения выходных данных MCP и предупреждения

Когда инструменты MCP производят большие выходные данные, Claude Code помогает управлять использованием токенов, чтобы предотвратить перегрузку контекста вашего разговора:

* **Порог предупреждения выходных данных**: Claude Code отображает предупреждение, когда выход любого инструмента MCP превышает 10 000 токенов
* **Настраиваемое ограничение**: Вы можете отрегулировать максимальное количество разрешенных токенов выходных данных MCP, используя переменную окружения `MAX_MCP_OUTPUT_TOKENS`
* **Ограничение по умолчанию**: Максимум по умолчанию составляет 25 000 токенов

Чтобы увеличить ограничение для инструментов, которые производят большие выходные данные:

```bash  theme={null}
# Установить более высокое ограничение для выходных данных инструментов MCP
export MAX_MCP_OUTPUT_TOKENS=50000
claude
```

Это особенно полезно при работе с MCP серверами, которые:

* Запрашивают большие наборы данных или базы данных
* Генерируют подробные отчеты или документацию
* Обрабатывают обширные файлы журналов или информацию отладки

<Warning>
  Если вы часто сталкиваетесь с предупреждениями выходных данных с конкретными MCP серверами, рассмотрите возможность увеличения ограничения или настройки сервера для разбиения на страницы или фильтрации его ответов.
</Warning>

## Использовать ресурсы MCP

MCP серверы могут предоставлять ресурсы, на которые вы можете ссылаться, используя упоминания @, аналогично тому, как вы ссылаетесь на файлы.

### Ссылка на ресурсы MCP

<Steps>
  <Step title="Список доступных ресурсов">
    Введите `@` в вашу подсказку, чтобы увидеть доступные ресурсы из всех подключенных MCP серверов. Ресурсы появляются рядом с файлами в меню автозаполнения.
  </Step>

  <Step title="Ссылка на конкретный ресурс">
    Используйте формат `@server:protocol://resource/path` для ссылки на ресурс:

    ```
    > Can you analyze @github:issue://123 and suggest a fix?
    ```

    ```
    > Please review the API documentation at @docs:file://api/authentication
    ```
  </Step>

  <Step title="Несколько ссылок на ресурсы">
    Вы можете ссылаться на несколько ресурсов в одной подсказке:

    ```
    > Compare @postgres:schema://users with @docs:file://database/user-model
    ```
  </Step>
</Steps>

<Tip>
  Советы:

  * Ресурсы автоматически получаются и включаются как вложения при ссылке
  * Пути ресурсов поддерживают нечеткий поиск в автозаполнении упоминания @
  * Claude Code автоматически предоставляет инструменты для списка и чтения ресурсов MCP, когда серверы их поддерживают
  * Ресурсы могут содержать любой тип контента, который предоставляет MCP сервер (текст, JSON, структурированные данные и т.д.)
</Tip>

## Использовать подсказки MCP как команды слэша

MCP серверы могут предоставлять подсказки, которые становятся доступными как команды слэша в Claude Code.

### Выполнить подсказки MCP

<Steps>
  <Step title="Обнаружить доступные подсказки">
    Введите `/` для просмотра всех доступных команд, включая те из MCP серверов. Подсказки MCP появляются с форматом `/mcp__servername__promptname`.
  </Step>

  <Step title="Выполнить подсказку без аргументов">
    ```
    > /mcp__github__list_prs
    ```
  </Step>

  <Step title="Выполнить подсказку с аргументами">
    Многие подсказки принимают аргументы. Передайте их через пробел после команды:

    ```
    > /mcp__github__pr_review 456
    ```

    ```
    > /mcp__jira__create_issue "Bug in login flow" high
    ```
  </Step>
</Steps>

<Tip>
  Советы:

  * Подсказки MCP динамически обнаруживаются из подключенных серверов
  * Аргументы анализируются на основе определенных параметров подсказки
  * Результаты подсказки вводятся непосредственно в разговор
  * Имена сервера и подсказки нормализуются (пробелы становятся подчеркиваниями)
</Tip>

## Управляемая конфигурация MCP

Для организаций, которым требуется централизованный контроль над MCP серверами, Claude Code поддерживает два варианта конфигурации:

1. **Исключительный контроль с `managed-mcp.json`**: Развернуть фиксированный набор MCP серверов, которые пользователи не могут изменять или расширять
2. **Контроль на основе политики с разрешенными/запрещенными списками**: Позволить пользователям добавлять свои собственные серверы, но ограничить, какие из них разрешены

Эти опции позволяют IT администраторам:

* **Контролировать, какие MCP серверы могут использовать сотрудники**: Развернуть стандартный набор одобренных MCP серверов по всей организации
* **Предотвратить неавторизованные MCP серверы**: Ограничить пользователей от добавления неодобренных MCP серверов
* **Отключить MCP полностью**: Полностью удалить функциональность MCP, если необходимо

### Вариант 1: Исключительный контроль с managed-mcp.json

Когда вы развертываете файл `managed-mcp.json`, он берет **исключительный контроль** над всеми MCP серверами. Пользователи не могут добавлять, изменять или использовать какие-либо MCP серверы, кроме определенных в этом файле. Это самый простой подход для организаций, которые хотят полный контроль.

Системные администраторы развертывают файл конфигурации в системный каталог:

* macOS: `/Library/Application Support/ClaudeCode/managed-mcp.json`
* Linux и WSL: `/etc/claude-code/managed-mcp.json`
* Windows: `C:\Program Files\ClaudeCode\managed-mcp.json`

<Note>
  Это системные пути (не домашние каталоги пользователя, такие как `~/Library/...`), которые требуют привилегий администратора. Они предназначены для развертывания IT администраторами.
</Note>

Файл `managed-mcp.json` использует тот же формат, что и стандартный файл `.mcp.json`:

```json  theme={null}
{
  "mcpServers": {
    "github": {
      "type": "http",
      "url": "https://api.githubcopilot.com/mcp/"
    },
    "sentry": {
      "type": "http",
      "url": "https://mcp.sentry.dev/mcp"
    },
    "company-internal": {
      "type": "stdio",
      "command": "/usr/local/bin/company-mcp-server",
      "args": ["--config", "/etc/company/mcp-config.json"],
      "env": {
        "COMPANY_API_URL": "https://internal.company.com"
      }
    }
  }
}
```

### Вариант 2: Контроль на основе политики с разрешенными и запрещенными списками

Вместо того, чтобы брать исключительный контроль, администраторы могут позволить пользователям настраивать свои собственные MCP серверы, одновременно применяя ограничения на то, какие серверы разрешены. Этот подход использует `allowedMcpServers` и `deniedMcpServers` в [файле управляемых настроек](/ru/settings#settings-files).

<Note>
  **Выбор между вариантами**: Используйте Вариант 1 (`managed-mcp.json`), когда вы хотите развернуть фиксированный набор серверов без настройки пользователем. Используйте Вариант 2 (разрешенные/запрещенные списки), когда вы хотите позволить пользователям добавлять свои собственные серверы в рамках ограничений политики.
</Note>

#### Опции ограничения

Каждая запись в разрешенном или запрещенном списке может ограничивать серверы тремя способами:

1. **По имени сервера** (`serverName`): Соответствует настроенному имени сервера
2. **По команде** (`serverCommand`): Соответствует точной команде и аргументам, используемым для запуска stdio серверов
3. **По шаблону URL** (`serverUrl`): Соответствует URL удаленных серверов с поддержкой подстановочных символов

**Важно**: Каждая запись должна иметь ровно одно из `serverName`, `serverCommand` или `serverUrl`.

#### Пример конфигурации

```json  theme={null}
{
  "allowedMcpServers": [
    // Разрешить по имени сервера
    { "serverName": "github" },
    { "serverName": "sentry" },

    // Разрешить по точной команде (для stdio серверов)
    { "serverCommand": ["npx", "-y", "@modelcontextprotocol/server-filesystem"] },
    { "serverCommand": ["python", "/usr/local/bin/approved-server.py"] },

    // Разрешить по шаблону URL (для удаленных серверов)
    { "serverUrl": "https://mcp.company.com/*" },
    { "serverUrl": "https://*.internal.corp/*" }
  ],
  "deniedMcpServers": [
    // Заблокировать по имени сервера
    { "serverName": "dangerous-server" },

    // Заблокировать по точной команде (для stdio серверов)
    { "serverCommand": ["npx", "-y", "unapproved-package"] },

    // Заблокировать по шаблону URL (для удаленных серверов)
    { "serverUrl": "https://*.untrusted.com/*" }
  ]
}
```

#### Как работают ограничения на основе команд

**Точное совпадение**:

* Массивы команд должны совпадать **точно** - как команда, так и все аргументы в правильном порядке
* Пример: `["npx", "-y", "server"]` НЕ будет совпадать с `["npx", "server"]` или `["npx", "-y", "server", "--flag"]`

**Поведение stdio сервера**:

* Когда разрешенный список содержит **любые** записи `serverCommand`, stdio серверы **должны** совпадать с одной из этих команд
* Stdio серверы не могут пройти только по имени, когда присутствуют ограничения команд
* Это гарантирует, что администраторы могут применить, какие команды разрешены для запуска

**Поведение удаленного сервера**:

* Удаленные серверы (HTTP, SSE, WebSocket) используют совпадение на основе URL, когда в разрешенном списке существуют записи `serverUrl`
* Если записей URL не существует, удаленные серверы возвращаются к совпадению на основе имени
* Ограничения команд не применяются к удаленным серверам

#### Как работают ограничения на основе URL

Шаблоны URL поддерживают подстановочные символы, используя `*` для совпадения с любой последовательностью символов. Это полезно для разрешения целых доменов или поддоменов.

**Примеры подстановочных символов**:

* `https://mcp.company.com/*` - Разрешить все пути на конкретном домене
* `https://*.example.com/*` - Разрешить любой поддомен example.com
* `http://localhost:*/*` - Разрешить любой порт на localhost

**Поведение удаленного сервера**:

* Когда разрешенный список содержит **любые** записи `serverUrl`, удаленные серверы **должны** совпадать с одним из этих шаблонов URL
* Удаленные серверы не могут пройти только по имени, когда присутствуют ограничения URL
* Это гарантирует, что администраторы могут применить, какие удаленные конечные точки разрешены

<Accordion title="Пример: Разрешенный список только для URL">
  ```json  theme={null}
  {
    "allowedMcpServers": [
      { "serverUrl": "https://mcp.company.com/*" },
      { "serverUrl": "https://*.internal.corp/*" }
    ]
  }
  ```

  **Результат**:

  * HTTP сервер в `https://mcp.company.com/api`: ✅ Разрешен (совпадает с шаблоном URL)
  * HTTP сервер в `https://api.internal.corp/mcp`: ✅ Разрешен (совпадает с подстановочным поддоменом)
  * HTTP сервер в `https://external.com/mcp`: ❌ Заблокирован (не совпадает с шаблоном URL)
  * Stdio сервер с любой командой: ❌ Заблокирован (нет записей имени или команды для совпадения)
</Accordion>

<Accordion title="Пример: Разрешенный список только для команд">
  ```json  theme={null}
  {
    "allowedMcpServers": [
      { "serverCommand": ["npx", "-y", "approved-package"] }
    ]
  }
  ```

  **Результат**:

  * Stdio сервер с `["npx", "-y", "approved-package"]`: ✅ Разрешен (совпадает с командой)
  * Stdio сервер с `["node", "server.js"]`: ❌ Заблокирован (не совпадает с командой)
  * HTTP сервер с именем "my-api": ❌ Заблокирован (нет записей имени для совпадения)
</Accordion>

<Accordion title="Пример: Смешанный разрешенный список имени и команды">
  ```json  theme={null}
  {
    "allowedMcpServers": [
      { "serverName": "github" },
      { "serverCommand": ["npx", "-y", "approved-package"] }
    ]
  }
  ```

  **Результат**:

  * Stdio сервер с именем "local-tool" и `["npx", "-y", "approved-package"]`: ✅ Разрешен (совпадает с командой)
  * Stdio сервер с именем "local-tool" и `["node", "server.js"]`: ❌ Заблокирован (записи команд существуют, но не совпадают)
  * Stdio сервер с именем "github" и `["node", "server.js"]`: ❌ Заблокирован (stdio серверы должны совпадать с командами, когда записи команд существуют)
  * HTTP сервер с именем "github": ✅ Разрешен (совпадает с именем)
  * HTTP сервер с именем "other-api": ❌ Заблокирован (имя не совпадает)
</Accordion>

<Accordion title="Пример: Разрешенный список только для имени">
  ```json  theme={null}
  {
    "allowedMcpServers": [
      { "serverName": "github" },
      { "serverName": "internal-tool" }
    ]
  }
  ```

  **Результат**:

  * Stdio сервер с именем "github" и любой командой: ✅ Разрешен (нет ограничений команд)
  * Stdio сервер с именем "internal-tool" и любой командой: ✅ Разрешен (нет ограничений команд)
  * HTTP сервер с именем "github": ✅ Разрешен (совпадает с именем)
  * Любой сервер с именем "other": ❌ Заблокирован (имя не совпадает)
</Accordion>

#### Поведение разрешенного списка (`allowedMcpServers`)

* `undefined` (по умолчанию): Нет ограничений - пользователи могут настроить любой MCP сервер
* Пустой массив `[]`: Полная блокировка - пользователи не могут настроить какие-либо MCP серверы
* Список записей: Пользователи могут настроить только серверы, которые совпадают по имени, команде или шаблону URL

#### Поведение запрещенного списка (`deniedMcpServers`)

* `undefined` (по умолчанию): Никакие серверы не заблокированы
* Пустой массив `[]`: Никакие серверы не заблокированы
* Список записей: Указанные серверы явно заблокированы во всех областях

#### Важные примечания

* **Вариант 1 и Вариант 2 можно комбинировать**: Если `managed-mcp.json` существует, он имеет исключительный контроль и пользователи не могут добавлять серверы. Разрешенные/запрещенные списки все еще применяются к управляемым серверам.
* **Запрещенный список имеет абсолютный приоритет**: Если сервер совпадает с записью запрещенного списка (по имени, команде или URL), он будет заблокирован, даже если он находится в разрешенном списке
* **Ограничения на основе имени, команды и URL работают вместе**: Сервер проходит, если он совпадает с **либо** записью имени, записью команды, либо шаблоном URL (если не заблокирован запрещенным списком)

<Note>
  **При использовании `managed-mcp.json`**: Пользователи не могут добавлять MCP серверы через `claude mcp add` или файлы конфигурации. Параметры `allowedMcpServers` и `deniedMcpServers` все еще применяются для фильтрации, какие управляемые серверы фактически загружаются.
</Note>
