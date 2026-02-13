> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Обзор Claude Code

> Узнайте о Claude Code, инструменте агентивного кодирования Anthropic, который работает в вашем терминале и помогает вам превращать идеи в код быстрее, чем когда-либо.

## Начните за 30 секунд

Предварительные требования:

* Аккаунт [Claude.ai](https://claude.ai) (рекомендуется) или [Claude Console](https://console.anthropic.com/)

**Установите Claude Code:**

To install Claude Code, use one of the following methods:

<Tabs>
  <Tab title="Native Install (Recommended)">
    **macOS, Linux, WSL:**

    ```bash  theme={null}
    curl -fsSL https://claude.ai/install.sh | bash
    ```

    **Windows PowerShell:**

    ```powershell  theme={null}
    irm https://claude.ai/install.ps1 | iex
    ```

    **Windows CMD:**

    ```batch  theme={null}
    curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
    ```

    <Info>
      Native installations automatically update in the background to keep you on the latest version.
    </Info>
  </Tab>

  <Tab title="Homebrew">
    ```sh  theme={null}
    brew install --cask claude-code
    ```

    <Info>
      Homebrew installations do not auto-update. Run `brew upgrade claude-code` periodically to get the latest features and security fixes.
    </Info>
  </Tab>

  <Tab title="WinGet">
    ```powershell  theme={null}
    winget install Anthropic.ClaudeCode
    ```

    <Info>
      WinGet installations do not auto-update. Run `winget upgrade Anthropic.ClaudeCode` periodically to get the latest features and security fixes.
    </Info>
  </Tab>
</Tabs>

**Начните использовать Claude Code:**

```bash  theme={null}
cd your-project
claude
```

При первом использовании вам будет предложено войти. Вот и всё! [Продолжите с Быстрым началом (5 минут) →](/ru/quickstart)

<Tip>
  Claude Code автоматически обновляет себя. Смотрите [расширенную настройку](/ru/setup) для опций установки, ручных обновлений или инструкций по удалению. Посетите [устранение неполадок](/ru/troubleshooting), если у вас возникнут проблемы.
</Tip>

## Что Claude Code делает для вас

* **Создавайте функции из описаний**: Расскажите Claude, что вы хотите создать на простом английском языке. Он составит план, напишет код и убедится, что он работает.
* **Отлаживайте и исправляйте проблемы**: Опишите ошибку или вставьте сообщение об ошибке. Claude Code проанализирует вашу кодовую базу, определит проблему и реализует исправление.
* **Навигируйте по любой кодовой базе**: Спросите что-нибудь о кодовой базе вашей команды и получите вдумчивый ответ. Claude Code поддерживает осведомленность о всей структуре вашего проекта, может найти актуальную информацию из веб-сети и с помощью [MCP](/ru/mcp) может извлекать данные из внешних источников, таких как Google Drive, Figma и Slack.
* **Автоматизируйте утомительные задачи**: Исправляйте сложные проблемы с линтером, разрешайте конфликты слияния и пишите заметки о выпуске. Делайте всё это в одной команде с ваших машин разработчика или автоматически в CI.

## Почему разработчики любят Claude Code

* **Работает в вашем терминале**: Не ещё одно окно чата. Не ещё один IDE. Claude Code встречает вас там, где вы уже работаете, с инструментами, которые вы уже любите.
* **Принимает меры**: Claude Code может напрямую редактировать файлы, запускать команды и создавать коммиты. Нужно больше? [MCP](/ru/mcp) позволяет Claude читать ваши документы дизайна в Google Drive, обновлять ваши задачи в Jira или использовать *ваши* пользовательские инструменты разработчика.
* **Философия Unix**: Claude Code является составным и скриптуемым. `tail -f app.log | claude -p "Slack me if you see any anomalies appear in this log stream"` *работает*. Ваш CI может запустить `claude -p "If there are new text strings, translate them into French and raise a PR for @lang-fr-team to review"`.
* **Готово для предприятия**: Используйте Claude API или разместите на AWS или GCP. Безопасность, конфиденциальность и соответствие требованиям корпоративного уровня встроены.

## Следующие шаги

<CardGroup>
  <Card title="Быстрый старт" icon="rocket" href="/ru/quickstart">
    Посмотрите Claude Code в действии с практическими примерами
  </Card>

  <Card title="Общие рабочие процессы" icon="graduation-cap" href="/ru/common-workflows">
    Пошаговые руководства для общих рабочих процессов
  </Card>

  <Card title="Устранение неполадок" icon="wrench" href="/ru/troubleshooting">
    Решения для распространённых проблем с Claude Code
  </Card>

  <Card title="Настройка IDE" icon="laptop" href="/ru/vs-code">
    Добавьте Claude Code в ваш IDE
  </Card>
</CardGroup>

## Дополнительные ресурсы

<CardGroup>
  <Card title="О Claude Code" icon="sparkles" href="https://claude.com/product/claude-code">
    Узнайте больше о Claude Code на claude.com
  </Card>

  <Card title="Создавайте с помощью Agent SDK" icon="code-branch" href="https://docs.claude.com/en/docs/agent-sdk/overview">
    Создавайте пользовательские AI-агентов с помощью Claude Agent SDK
  </Card>

  <Card title="Разместите на AWS или GCP" icon="cloud" href="/ru/third-party-integrations">
    Настройте Claude Code с Amazon Bedrock или Google Vertex AI
  </Card>

  <Card title="Параметры" icon="gear" href="/ru/settings">
    Настройте Claude Code для вашего рабочего процесса
  </Card>

  <Card title="Команды" icon="terminal" href="/ru/cli-reference">
    Узнайте о командах CLI и элементах управления
  </Card>

  <Card title="Эталонная реализация" icon="code" href="https://github.com/anthropics/claude-code/tree/main/.devcontainer">
    Клонируйте нашу эталонную реализацию контейнера разработки
  </Card>

  <Card title="Безопасность" icon="shield" href="/ru/security">
    Откройте для себя защиту Claude Code и лучшие практики для безопасного использования
  </Card>

  <Card title="Конфиденциальность и использование данных" icon="lock" href="/ru/data-usage">
    Поймите, как Claude Code обрабатывает ваши данные
  </Card>
</CardGroup>
