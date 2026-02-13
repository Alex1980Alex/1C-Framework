> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Claude Code GitHub Actions

> Узнайте об интеграции Claude Code в ваш рабочий процесс разработки с помощью Claude Code GitHub Actions

Claude Code GitHub Actions привносит автоматизацию на основе ИИ в ваш рабочий процесс GitHub. С простым упоминанием `@claude` в любом PR или issue, Claude может анализировать ваш код, создавать pull requests, реализовывать функции и исправлять ошибки - всё при соблюдении стандартов вашего проекта.

<Note>
  Claude Code GitHub Actions построен на основе [Claude Code
  SDK](https://docs.claude.com/ru/docs/agent-sdk), который обеспечивает программную интеграцию
  Claude Code в ваши приложения. Вы можете использовать SDK для создания пользовательских
  рабочих процессов автоматизации за пределами GitHub Actions.
</Note>

<Info>
  **Claude Opus 4.5 теперь доступен.** Claude Code GitHub Actions по умолчанию используют Sonnet. Чтобы использовать Opus 4.5, настройте [параметр модели](#breaking-changes-reference) на использование `claude-opus-4-5-20251101`.
</Info>

## Почему использовать Claude Code GitHub Actions?

* **Мгновенное создание PR**: Опишите, что вам нужно, и Claude создаст полный PR со всеми необходимыми изменениями
* **Автоматизированная реализация кода**: Превратите issues в рабочий код одной командой
* **Соблюдение ваших стандартов**: Claude уважает ваши рекомендации `CLAUDE.md` и существующие паттерны кода
* **Простая настройка**: Начните работу за несколько минут с нашим установщиком и API ключом
* **Безопасность по умолчанию**: Ваш код остаётся на серверах Github

## Что может делать Claude?

Claude Code предоставляет мощное GitHub Action, которое трансформирует способ работы с кодом:

### Claude Code Action

Это GitHub Action позволяет вам запускать Claude Code в ваших рабочих процессах GitHub Actions. Вы можете использовать это для создания любого пользовательского рабочего процесса на основе Claude Code.

[Просмотреть репозиторий →](https://github.com/anthropics/claude-code-action)

## Настройка

## Быстрая настройка

Самый простой способ настроить это действие - через Claude Code в терминале. Просто откройте claude и запустите `/install-github-app`.

Эта команда проведёт вас через процесс настройки GitHub app и необходимых секретов.

<Note>
  * Вы должны быть администратором репозитория для установки GitHub app и добавления секретов
  * GitHub app будет запрашивать права на чтение и запись для Contents, Issues и Pull requests
  * Этот метод быстрого старта доступен только для прямых пользователей Claude API. Если
    вы используете AWS Bedrock или Google Vertex AI, пожалуйста, см. раздел [Использование с AWS
    Bedrock и Google Vertex AI](#using-with-aws-bedrock-%26-google-vertex-ai).
</Note>

## Ручная настройка

Если команда `/install-github-app` не сработала или вы предпочитаете ручную настройку, пожалуйста, следуйте этим инструкциям ручной настройки:

1. **Установите Claude GitHub app** в ваш репозиторий: [https://github.com/apps/claude](https://github.com/apps/claude)

   Claude GitHub app требует следующих прав доступа к репозиторию:

   * **Contents**: Чтение и запись (для изменения файлов репозитория)
   * **Issues**: Чтение и запись (для ответов на issues)
   * **Pull requests**: Чтение и запись (для создания PR и отправки изменений)

   Для получения дополнительной информации о безопасности и разрешениях см. [документацию по безопасности](https://github.com/anthropics/claude-code-action/blob/main/docs/security.md).
2. **Добавьте ANTHROPIC\_API\_KEY** в секреты вашего репозитория ([Узнайте, как использовать секреты в GitHub Actions](https://docs.github.com/en/actions/security-guides/using-secrets-in-github-actions))
3. **Скопируйте файл рабочего процесса** из [examples/claude.yml](https://github.com/anthropics/claude-code-action/blob/main/examples/claude.yml) в папку `.github/workflows/` вашего репозитория

<Tip>
  После завершения быстрой настройки или ручной настройки протестируйте действие, отметив `@claude` в комментарии issue или PR.
</Tip>

## Обновление с бета-версии

<Warning>
  Claude Code GitHub Actions v1.0 вводит критические изменения, которые требуют обновления ваших файлов рабочих процессов для обновления с бета-версии на v1.0.
</Warning>

Если вы в настоящее время используете бета-версию Claude Code GitHub Actions, мы рекомендуем обновить ваши рабочие процессы для использования версии GA. Новая версия упрощает конфигурацию, добавляя мощные новые функции, такие как автоматическое обнаружение режима.

### Существенные изменения

Все пользователи бета-версии должны внести эти изменения в свои файлы рабочих процессов для обновления:

1. **Обновите версию действия**: Измените `@beta` на `@v1`
2. **Удалите конфигурацию режима**: Удалите `mode: "tag"` или `mode: "agent"` (теперь автоматически обнаруживается)
3. **Обновите входные данные prompt**: Замените `direct_prompt` на `prompt`
4. **Переместите параметры CLI**: Преобразуйте `max_turns`, `model`, `custom_instructions` и т.д. в `claude_args`

### Справочник критических изменений

| Старый вход бета-версии | Новый вход v1.0                            |
| ----------------------- | ------------------------------------------ |
| `mode`                  | *(Удалено - автоматически обнаруживается)* |
| `direct_prompt`         | `prompt`                                   |
| `override_prompt`       | `prompt` с переменными GitHub              |
| `custom_instructions`   | `claude_args: --system-prompt`             |
| `max_turns`             | `claude_args: --max-turns`                 |
| `model`                 | `claude_args: --model`                     |
| `allowed_tools`         | `claude_args: --allowedTools`              |
| `disallowed_tools`      | `claude_args: --disallowedTools`           |
| `claude_env`            | `settings` формат JSON                     |

### Пример до и после

**Бета-версия:**

```yaml  theme={null}
- uses: anthropics/claude-code-action@beta
  with:
    mode: "tag"
    direct_prompt: "Review this PR for security issues"
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    custom_instructions: "Follow our coding standards"
    max_turns: "10"
    model: "claude-sonnet-4-5-20250929"
```

**Версия GA (v1.0):**

```yaml  theme={null}
- uses: anthropics/claude-code-action@v1
  with:
    prompt: "Review this PR for security issues"
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    claude_args: |
      --system-prompt "Follow our coding standards"
      --max-turns 10
      --model claude-sonnet-4-5-20250929
```

<Tip>
  Действие теперь автоматически обнаруживает, следует ли запускаться в интерактивном режиме (отвечает на упоминания `@claude`) или режиме автоматизации (запускается немедленно с prompt) на основе вашей конфигурации.
</Tip>

## Примеры использования

Claude Code GitHub Actions может помочь вам с различными задачами. [Каталог примеров](https://github.com/anthropics/claude-code-action/tree/main/examples) содержит готовые к использованию рабочие процессы для различных сценариев.

### Базовый рабочий процесс

```yaml  theme={null}
name: Claude Code
on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
jobs:
  claude:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          # Responds to @claude mentions in comments
```

### Использование slash команд

```yaml  theme={null}
name: Code Review
on:
  pull_request:
    types: [opened, synchronize]
jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "/review"
          claude_args: "--max-turns 5"
```

### Пользовательская автоматизация с prompts

```yaml  theme={null}
name: Daily Report
on:
  schedule:
    - cron: "0 9 * * *"
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          prompt: "Generate a summary of yesterday's commits and open issues"
          claude_args: "--model claude-opus-4-5-20251101"
```

### Распространённые случаи использования

В комментариях issue или PR:

```
@claude implement this feature based on the issue description
@claude how should I implement user authentication for this endpoint?
@claude fix the TypeError in the user dashboard component
```

Claude автоматически проанализирует контекст и ответит соответствующим образом.

## Лучшие практики

### Конфигурация CLAUDE.md

Создайте файл `CLAUDE.md` в корне вашего репозитория для определения рекомендаций по стилю кода, критериев проверки, правил, специфичных для проекта, и предпочитаемых паттернов. Этот файл направляет понимание Claude стандартов вашего проекта.

### Соображения безопасности

<Warning>Никогда не коммитьте API ключи непосредственно в ваш репозиторий.</Warning>

Для получения полного руководства по безопасности, включая разрешения, аутентификацию и лучшие практики, см. [документацию по безопасности Claude Code Action](https://github.com/anthropics/claude-code-action/blob/main/docs/security.md).

Всегда используйте GitHub Secrets для API ключей:

* Добавьте ваш API ключ как секрет репозитория с именем `ANTHROPIC_API_KEY`
* Ссылайтесь на него в рабочих процессах: `anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}`
* Ограничьте разрешения действия только необходимыми
* Проверьте предложения Claude перед слиянием

Всегда используйте GitHub Secrets (например, `${{ secrets.ANTHROPIC_API_KEY }}`) вместо жёсткого кодирования API ключей непосредственно в ваши файлы рабочих процессов.

### Оптимизация производительности

Используйте шаблоны issues для предоставления контекста, держите ваш `CLAUDE.md` кратким и сосредоточенным, и настройте соответствующие тайм-ауты для ваших рабочих процессов.

### Затраты CI

При использовании Claude Code GitHub Actions помните о связанных затратах:

**Затраты GitHub Actions:**

* Claude Code работает на GitHub-hosted runners, которые потребляют ваши минуты GitHub Actions
* См. [документацию по выставлению счётов GitHub](https://docs.github.com/en/billing/managing-billing-for-your-products/managing-billing-for-github-actions/about-billing-for-github-actions) для получения подробной информации о ценах и лимитах минут

**Затраты API:**

* Каждое взаимодействие Claude потребляет токены API на основе длины prompts и ответов
* Использование токенов варьируется в зависимости от сложности задачи и размера кодовой базы
* См. [страницу ценообразования Claude](https://claude.com/platform/api) для получения текущих ставок токенов

**Советы по оптимизации затрат:**

* Используйте специфичные команды `@claude` для уменьшения ненужных вызовов API
* Настройте соответствующий `--max-turns` в `claude_args` для предотвращения чрезмерных итераций
* Установите тайм-ауты на уровне рабочего процесса, чтобы избежать неконтролируемых заданий
* Рассмотрите использование элементов управления параллелизмом GitHub для ограничения параллельных запусков

## Примеры конфигурации

Claude Code Action v1 упрощает конфигурацию с унифицированными параметрами:

```yaml  theme={null}
- uses: anthropics/claude-code-action@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    prompt: "Your instructions here" # Optional
    claude_args: "--max-turns 5" # Optional CLI arguments
```

Ключевые функции:

* **Унифицированный интерфейс prompt** - Используйте `prompt` для всех инструкций
* **Slash команды** - Встроенные prompts, такие как `/review` или `/fix`
* **Passthrough CLI** - Любой аргумент Claude Code CLI через `claude_args`
* **Гибкие триггеры** - Работает с любым событием GitHub

Посетите [каталог примеров](https://github.com/anthropics/claude-code-action/tree/main/examples) для получения полных файлов рабочих процессов.

<Tip>
  При ответе на комментарии issue или PR, Claude автоматически отвечает на упоминания @claude. Для других событий используйте параметр `prompt` для предоставления инструкций.
</Tip>

## Использование с AWS Bedrock и Google Vertex AI

Для корпоративных сред вы можете использовать Claude Code GitHub Actions с вашей собственной облачной инфраструктурой. Этот подход даёт вам контроль над местоположением данных и выставлением счётов при сохранении той же функциональности.

### Предварительные требования

Перед настройкой Claude Code GitHub Actions с облачными провайдерами вам нужно:

#### Для Google Cloud Vertex AI:

1. Проект Google Cloud с включённым Vertex AI
2. Workload Identity Federation, настроенный для GitHub Actions
3. Сервисный аккаунт с необходимыми разрешениями
4. GitHub App (рекомендуется) или использование стандартного GITHUB\_TOKEN

#### Для AWS Bedrock:

1. Аккаунт AWS с включённым Amazon Bedrock
2. GitHub OIDC Identity Provider, настроенный в AWS
3. IAM роль с разрешениями Bedrock
4. GitHub App (рекомендуется) или использование стандартного GITHUB\_TOKEN

<Steps>
  <Step title="Создайте пользовательское GitHub App (Рекомендуется для 3P провайдеров)">
    Для лучшего контроля и безопасности при использовании 3P провайдеров, таких как Vertex AI или Bedrock, мы рекомендуем создать ваше собственное GitHub App:

    1. Перейдите на [https://github.com/settings/apps/new](https://github.com/settings/apps/new)
    2. Заполните основную информацию:
       * **GitHub App name**: Выберите уникальное имя (например, "YourOrg Claude Assistant")
       * **Homepage URL**: Веб-сайт вашей организации или URL репозитория
    3. Настройте параметры приложения:
       * **Webhooks**: Снимите флажок "Active" (не требуется для этой интеграции)
    4. Установите необходимые разрешения:
       * **Repository permissions**:
         * Contents: Read & Write
         * Issues: Read & Write
         * Pull requests: Read & Write
    5. Нажмите "Create GitHub App"
    6. После создания нажмите "Generate a private key" и сохраните загруженный файл `.pem`
    7. Запишите ваш App ID со страницы параметров приложения
    8. Установите приложение в ваш репозиторий:
       * Со страницы параметров вашего приложения нажмите "Install App" в левой боковой панели
       * Выберите ваш аккаунт или организацию
       * Выберите "Only select repositories" и выберите конкретный репозиторий
       * Нажмите "Install"
    9. Добавьте приватный ключ как секрет в ваш репозиторий:
       * Перейдите в Settings вашего репозитория → Secrets and variables → Actions
       * Создайте новый секрет с именем `APP_PRIVATE_KEY` с содержимым файла `.pem`
    10. Добавьте App ID как секрет:

    * Создайте новый секрет с именем `APP_ID` с ID вашего GitHub App

    <Note>
      Это приложение будет использоваться с действием [actions/create-github-app-token](https://github.com/actions/create-github-app-token) для генерации токенов аутентификации в ваших рабочих процессах.
    </Note>

    **Альтернатива для Claude API или если вы не хотите настраивать свой Github app**: Используйте официальное приложение Anthropic:

    1. Установите из: [https://github.com/apps/claude](https://github.com/apps/claude)
    2. Никаких дополнительных конфигураций не требуется для аутентификации
  </Step>

  <Step title="Настройте аутентификацию облачного провайдера">
    Выберите вашего облачного провайдера и установите безопасную аутентификацию:

    <AccordionGroup>
      <Accordion title="AWS Bedrock">
        **Настройте AWS, чтобы разрешить GitHub Actions безопасно аутентифицироваться без хранения учётных данных.**

        > **Примечание по безопасности**: Используйте конфигурации, специфичные для репозитория, и предоставляйте только минимально необходимые разрешения.

        **Требуемая настройка**:

        1. **Включите Amazon Bedrock**:
           * Запросите доступ к моделям Claude в Amazon Bedrock
           * Для моделей в нескольких регионах запросите доступ во всех необходимых регионах

        2. **Установите GitHub OIDC Identity Provider**:
           * Provider URL: `https://token.actions.githubusercontent.com`
           * Audience: `sts.amazonaws.com`

        3. **Создайте IAM Role для GitHub Actions**:
           * Trusted entity type: Web identity
           * Identity provider: `token.actions.githubusercontent.com`
           * Permissions: политика `AmazonBedrockFullAccess`
           * Настройте политику доверия для вашего конкретного репозитория

        **Требуемые значения**:

        После настройки вам понадобятся:

        * **AWS\_ROLE\_TO\_ASSUME**: ARN IAM роли, которую вы создали

        <Tip>
          OIDC более безопасен, чем использование статических AWS ключей доступа, потому что учётные данные временные и автоматически ротируются.
        </Tip>

        См. [документацию AWS](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_providers_create_oidc.html) для получения подробных инструкций по настройке OIDC.
      </Accordion>

      <Accordion title="Google Vertex AI">
        **Настройте Google Cloud, чтобы разрешить GitHub Actions безопасно аутентифицироваться без хранения учётных данных.**

        > **Примечание по безопасности**: Используйте конфигурации, специфичные для репозитория, и предоставляйте только минимально необходимые разрешения.

        **Требуемая настройка**:

        1. **Включите API** в вашем проекте Google Cloud:
           * IAM Credentials API
           * Security Token Service (STS) API
           * Vertex AI API

        2. **Создайте ресурсы Workload Identity Federation**:
           * Создайте Workload Identity Pool
           * Добавьте GitHub OIDC провайдера с:
             * Issuer: `https://token.actions.githubusercontent.com`
             * Сопоставления атрибутов для репозитория и владельца
             * **Рекомендация по безопасности**: Используйте условия атрибутов, специфичные для репозитория

        3. **Создайте сервисный аккаунт**:
           * Предоставьте только роль `Vertex AI User`
           * **Рекомендация по безопасности**: Создайте выделенный сервисный аккаунт для каждого репозитория

        4. **Настройте IAM привязки**:
           * Разрешите Workload Identity Pool выдавать себя за сервисный аккаунт
           * **Рекомендация по безопасности**: Используйте наборы принципалов, специфичные для репозитория

        **Требуемые значения**:

        После настройки вам понадобятся:

        * **GCP\_WORKLOAD\_IDENTITY\_PROVIDER**: Полное имя ресурса провайдера
        * **GCP\_SERVICE\_ACCOUNT**: Адрес электронной почты сервисного аккаунта

        <Tip>
          Workload Identity Federation исключает необходимость в загружаемых ключах сервисного аккаунта, улучшая безопасность.
        </Tip>

        Для получения подробных инструкций по настройке обратитесь к [документации Google Cloud Workload Identity Federation](https://cloud.google.com/iam/docs/workload-identity-federation).
      </Accordion>
    </AccordionGroup>
  </Step>

  <Step title="Добавьте требуемые секреты">
    Добавьте следующие секреты в ваш репозиторий (Settings → Secrets and variables → Actions):

    #### Для Claude API (Direct):

    1. **Для аутентификации API**:
       * `ANTHROPIC_API_KEY`: Ваш Claude API ключ из [console.anthropic.com](https://console.anthropic.com)

    2. **Для GitHub App (если используете ваше собственное приложение)**:
       * `APP_ID`: ID вашего GitHub App
       * `APP_PRIVATE_KEY`: Содержимое приватного ключа (.pem)

    #### Для Google Cloud Vertex AI

    1. **Для аутентификации GCP**:
       * `GCP_WORKLOAD_IDENTITY_PROVIDER`
       * `GCP_SERVICE_ACCOUNT`

    2. **Для GitHub App (если используете ваше собственное приложение)**:
       * `APP_ID`: ID вашего GitHub App
       * `APP_PRIVATE_KEY`: Содержимое приватного ключа (.pem)

    #### Для AWS Bedrock

    1. **Для аутентификации AWS**:
       * `AWS_ROLE_TO_ASSUME`

    2. **Для GitHub App (если используете ваше собственное приложение)**:
       * `APP_ID`: ID вашего GitHub App
       * `APP_PRIVATE_KEY`: Содержимое приватного ключа (.pem)
  </Step>

  <Step title="Создайте файлы рабочих процессов">
    Создайте файлы рабочих процессов GitHub Actions, которые интегрируются с вашим облачным провайдером. Примеры ниже показывают полные конфигурации как для AWS Bedrock, так и для Google Vertex AI:

    <AccordionGroup>
      <Accordion title="AWS Bedrock workflow">
        **Предварительные требования:**

        * Доступ AWS Bedrock включён с разрешениями модели Claude
        * GitHub настроен как OIDC identity provider в AWS
        * IAM роль с разрешениями Bedrock, которая доверяет GitHub Actions

        **Требуемые GitHub секреты:**

        | Имя секрета          | Описание                                                 |
        | -------------------- | -------------------------------------------------------- |
        | `AWS_ROLE_TO_ASSUME` | ARN IAM роли для доступа к Bedrock                       |
        | `APP_ID`             | Ваш GitHub App ID (из параметров приложения)             |
        | `APP_PRIVATE_KEY`    | Приватный ключ, который вы создали для вашего GitHub App |

        ```yaml  theme={null}
        name: Claude PR Action

        permissions:
          contents: write
          pull-requests: write
          issues: write
          id-token: write

        on:
          issue_comment:
            types: [created]
          pull_request_review_comment:
            types: [created]
          issues:
            types: [opened, assigned]

        jobs:
          claude-pr:
            if: |
              (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
              (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
              (github.event_name == 'issues' && contains(github.event.issue.body, '@claude'))
            runs-on: ubuntu-latest
            env:
              AWS_REGION: us-west-2
            steps:
              - name: Checkout repository
                uses: actions/checkout@v4

              - name: Generate GitHub App token
                id: app-token
                uses: actions/create-github-app-token@v2
                with:
                  app-id: ${{ secrets.APP_ID }}
                  private-key: ${{ secrets.APP_PRIVATE_KEY }}

              - name: Configure AWS Credentials (OIDC)
                uses: aws-actions/configure-aws-credentials@v4
                with:
                  role-to-assume: ${{ secrets.AWS_ROLE_TO_ASSUME }}
                  aws-region: us-west-2

              - uses: anthropics/claude-code-action@v1
                with:
                  github_token: ${{ steps.app-token.outputs.token }}
                  use_bedrock: "true"
                  claude_args: '--model us.anthropic.claude-sonnet-4-5-20250929-v1:0 --max-turns 10'
        ```

        <Tip>
          Формат ID модели для Bedrock включает префикс региона (например, `us.anthropic.claude...`) и суффикс версии.
        </Tip>
      </Accordion>

      <Accordion title="Google Vertex AI workflow">
        **Предварительные требования:**

        * Vertex AI API включён в вашем проекте GCP
        * Workload Identity Federation настроена для GitHub
        * Сервисный аккаунт с разрешениями Vertex AI

        **Требуемые GitHub секреты:**

        | Имя секрета                      | Описание                                                           |
        | -------------------------------- | ------------------------------------------------------------------ |
        | `GCP_WORKLOAD_IDENTITY_PROVIDER` | Имя ресурса workload identity provider                             |
        | `GCP_SERVICE_ACCOUNT`            | Адрес электронной почты сервисного аккаунта с доступом к Vertex AI |
        | `APP_ID`                         | Ваш GitHub App ID (из параметров приложения)                       |
        | `APP_PRIVATE_KEY`                | Приватный ключ, который вы создали для вашего GitHub App           |

        ```yaml  theme={null}
        name: Claude PR Action

        permissions:
          contents: write
          pull-requests: write
          issues: write
          id-token: write

        on:
          issue_comment:
            types: [created]
          pull_request_review_comment:
            types: [created]
          issues:
            types: [opened, assigned]

        jobs:
          claude-pr:
            if: |
              (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
              (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
              (github.event_name == 'issues' && contains(github.event.issue.body, '@claude'))
            runs-on: ubuntu-latest
            steps:
              - name: Checkout repository
                uses: actions/checkout@v4

              - name: Generate GitHub App token
                id: app-token
                uses: actions/create-github-app-token@v2
                with:
                  app-id: ${{ secrets.APP_ID }}
                  private-key: ${{ secrets.APP_PRIVATE_KEY }}

              - name: Authenticate to Google Cloud
                id: auth
                uses: google-github-actions/auth@v2
                with:
                  workload_identity_provider: ${{ secrets.GCP_WORKLOAD_IDENTITY_PROVIDER }}
                  service_account: ${{ secrets.GCP_SERVICE_ACCOUNT }}

              - uses: anthropics/claude-code-action@v1
                with:
                  github_token: ${{ steps.app-token.outputs.token }}
                  trigger_phrase: "@claude"
                  use_vertex: "true"
                  claude_args: '--model claude-sonnet-4@20250514 --max-turns 10'
                env:
                  ANTHROPIC_VERTEX_PROJECT_ID: ${{ steps.auth.outputs.project_id }}
                  CLOUD_ML_REGION: us-east5
                  VERTEX_REGION_CLAUDE_3_7_SONNET: us-east5
        ```

        <Tip>
          ID проекта автоматически извлекается из шага аутентификации Google Cloud, поэтому вам не нужно жёстко кодировать его.
        </Tip>
      </Accordion>
    </AccordionGroup>
  </Step>
</Steps>

## Устранение неполадок

### Claude не отвечает на команды @claude

Проверьте, что GitHub App установлен правильно, убедитесь, что рабочие процессы включены, убедитесь, что API ключ установлен в секретах репозитория, и подтвердите, что комментарий содержит `@claude` (не `/claude`).

### CI не запускается на коммитах Claude

Убедитесь, что вы используете GitHub App или пользовательское приложение (не пользователя Actions), проверьте, что триггеры рабочего процесса включают необходимые события, и проверьте, что разрешения приложения включают триггеры CI.

### Ошибки аутентификации

Подтвердите, что API ключ действителен и имеет достаточные разрешения. Для Bedrock/Vertex проверьте конфигурацию учётных данных и убедитесь, что секреты правильно названы в рабочих процессах.

## Расширенная конфигурация

### Параметры действия

Claude Code Action v1 использует упрощённую конфигурацию:

| Параметр            | Описание                                                  | Требуется |
| ------------------- | --------------------------------------------------------- | --------- |
| `prompt`            | Инструкции для Claude (текст или slash команда)           | Нет\*     |
| `claude_args`       | Аргументы CLI, передаваемые в Claude Code                 | Нет       |
| `anthropic_api_key` | Claude API ключ                                           | Да\*\*    |
| `github_token`      | GitHub токен для доступа к API                            | Нет       |
| `trigger_phrase`    | Пользовательская фраза триггера (по умолчанию: "@claude") | Нет       |
| `use_bedrock`       | Использовать AWS Bedrock вместо Claude API                | Нет       |
| `use_vertex`        | Использовать Google Vertex AI вместо Claude API           | Нет       |

\*Prompt опционален - когда опущен для комментариев issue/PR, Claude отвечает на фразу триггера\
\*\*Требуется для прямого Claude API, не требуется для Bedrock/Vertex

#### Передайте аргументы CLI

Параметр `claude_args` принимает любые аргументы Claude Code CLI:

```yaml  theme={null}
claude_args: "--max-turns 5 --model claude-sonnet-4-5-20250929 --mcp-config /path/to/config.json"
```

Распространённые аргументы:

* `--max-turns`: Максимальное количество ходов разговора (по умолчанию: 10)
* `--model`: Модель для использования (например, `claude-sonnet-4-5-20250929`)
* `--mcp-config`: Путь к конфигурации MCP
* `--allowed-tools`: Список разрешённых инструментов, разделённый запятыми
* `--debug`: Включить вывод отладки

### Альтернативные методы интеграции

Хотя команда `/install-github-app` является рекомендуемым подходом, вы также можете:

* **Пользовательское GitHub App**: Для организаций, нуждающихся в фирменных именах пользователей или пользовательских потоках аутентификации. Создайте своё собственное GitHub App с необходимыми разрешениями (contents, issues, pull requests) и используйте действие actions/create-github-app-token для генерации токенов в ваших рабочих процессах.
* **Ручные GitHub Actions**: Прямая конфигурация рабочего процесса для максимальной гибкости
* **Конфигурация MCP**: Динамическая загрузка серверов Model Context Protocol

См. [документацию Claude Code Action](https://github.com/anthropics/claude-code-action/blob/main/docs) для получения подробных руководств по аутентификации, безопасности и расширенной конфигурации.

### Настройка поведения Claude

Вы можете настроить поведение Claude двумя способами:

1. **CLAUDE.md**: Определите стандарты кодирования, критерии проверки и правила, специфичные для проекта, в файле `CLAUDE.md` в корне вашего репозитория. Claude будет следовать этим рекомендациям при создании PR и ответе на запросы. Ознакомьтесь с нашей [документацией по памяти](/ru/memory) для получения дополнительной информации.
2. **Пользовательские prompts**: Используйте параметр `prompt` в файле рабочего процесса для предоставления инструкций, специфичных для рабочего процесса. Это позволяет вам настроить поведение Claude для различных рабочих процессов или задач.

Claude будет следовать этим рекомендациям при создании PR и ответе на запросы.
