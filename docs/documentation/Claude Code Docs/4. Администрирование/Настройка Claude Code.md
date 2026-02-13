> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Настройка Claude Code

> Установите, аутентифицируйте и начните использовать Claude Code на вашей машине разработки.

## Системные требования

* **Операционные системы**: macOS 13.0+, Ubuntu 20.04+/Debian 10+ или Windows 10+ (с WSL 1, WSL 2 или Git для Windows)
* **Оборудование**: 4 ГБ+ ОЗУ
* **Сеть**: требуется подключение к Интернету (см. [конфигурация сети](/ru/network-config#network-access-requirements))
* **Оболочка**: лучше всего работает в Bash или Zsh
* **Местоположение**: [поддерживаемые Anthropic страны](https://www.anthropic.com/supported-countries)

### Дополнительные зависимости

* **ripgrep**: обычно включается в Claude Code. Если поиск не работает, см. [устранение неполадок поиска](/ru/troubleshooting#search-and-discovery-issues).
* **[Node.js 18+](https://nodejs.org/en/download)**: требуется только для [устаревшей установки npm](#npm-installation-deprecated)

## Установка

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

После завершения процесса установки перейдите в ваш проект и запустите Claude Code:

```bash  theme={null}
cd your-awesome-project
claude
```

Если вы столкнулись с какими-либо проблемами во время установки, обратитесь к [руководству по устранению неполадок](/ru/troubleshooting).

<Tip>
  Запустите `claude doctor` после установки, чтобы проверить тип и версию вашей установки.
</Tip>

<Note>
  **Alpine Linux и другие дистрибутивы на основе musl/uClibc**: встроенный установщик требует `libgcc`, `libstdc++` и `ripgrep`. Для Alpine: `apk add libgcc libstdc++ ripgrep`. Установите `USE_BUILTIN_RIPGREP=0`.
</Note>

### Аутентификация

#### Для отдельных лиц

1. **План Claude Pro или Max** (рекомендуется): подпишитесь на [план Pro или Max](https://claude.ai/pricing) Claude для единой подписки, которая включает как Claude Code, так и Claude в веб-версии. Управляйте своей учетной записью в одном месте и входите с помощью своей учетной записи Claude.ai.
2. **Claude Console**: подключитесь через [Claude Console](https://console.anthropic.com) и завершите процесс OAuth. Требует активное выставление счетов в Anthropic Console. Рабочее пространство "Claude Code" автоматически создается для отслеживания использования и управления затратами. Вы не можете создавать ключи API для рабочего пространства Claude Code; оно предназначено исключительно для использования Claude Code.

#### Для команд и организаций

1. **Claude для команд или Enterprise** (рекомендуется): подпишитесь на [Claude для команд](https://claude.com/pricing#team-&-enterprise) или [Claude для Enterprise](https://anthropic.com/contact-sales) для централизованного выставления счетов, управления командой и доступа как к Claude Code, так и к Claude в веб-версии. Члены команды входят со своими учетными записями Claude.ai.
2. **Claude Console с командным выставлением счетов**: установите общую организацию [Claude Console](https://console.anthropic.com) с командным выставлением счетов. Пригласите членов команды и назначьте роли для отслеживания использования.
3. **Облачные провайдеры**: настройте Claude Code для использования [Amazon Bedrock, Google Vertex AI или Microsoft Foundry](/ru/third-party-integrations) для развертываний с вашей существующей облачной инфраструктурой.

### Установка определенной версии

Встроенный установщик принимает либо конкретный номер версии, либо канал выпуска (`latest` или `stable`). Канал, который вы выбираете во время установки, становится вашим значением по умолчанию для автоматических обновлений. Дополнительную информацию см. в разделе [Настройка канала выпуска](#configure-release-channel).

Для установки последней версии (по умолчанию):

<Tabs>
  <Tab title="macOS, Linux, WSL">
    ```bash  theme={null}
    curl -fsSL https://claude.ai/install.sh | bash
    ```
  </Tab>

  <Tab title="Windows PowerShell">
    ```powershell  theme={null}
    irm https://claude.ai/install.ps1 | iex
    ```
  </Tab>

  <Tab title="Windows CMD">
    ```batch  theme={null}
    curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd && del install.cmd
    ```
  </Tab>
</Tabs>

Для установки стабильной версии:

<Tabs>
  <Tab title="macOS, Linux, WSL">
    ```bash  theme={null}
    curl -fsSL https://claude.ai/install.sh | bash -s stable
    ```
  </Tab>

  <Tab title="Windows PowerShell">
    ```powershell  theme={null}
    & ([scriptblock]::Create((irm https://claude.ai/install.ps1))) stable
    ```
  </Tab>

  <Tab title="Windows CMD">
    ```batch  theme={null}
    curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd stable && del install.cmd
    ```
  </Tab>
</Tabs>

Для установки определенного номера версии:

<Tabs>
  <Tab title="macOS, Linux, WSL">
    ```bash  theme={null}
    curl -fsSL https://claude.ai/install.sh | bash -s 1.0.58
    ```
  </Tab>

  <Tab title="Windows PowerShell">
    ```powershell  theme={null}
    & ([scriptblock]::Create((irm https://claude.ai/install.ps1))) 1.0.58
    ```
  </Tab>

  <Tab title="Windows CMD">
    ```batch  theme={null}
    curl -fsSL https://claude.ai/install.cmd -o install.cmd && install.cmd 1.0.58 && del install.cmd
    ```
  </Tab>
</Tabs>

### Целостность двоичного файла и подписание кода

* Контрольные суммы SHA256 для всех платформ опубликованы в манифестах выпуска, в настоящее время расположенные по адресу `https://storage.googleapis.com/claude-code-dist-86c565f3-f756-42ad-8dfa-d59b1c096819/claude-code-releases/{VERSION}/manifest.json` (пример: замените `{VERSION}` на `2.0.30`)
* Подписанные двоичные файлы распространяются для следующих платформ:
  * macOS: подписано "Anthropic PBC" и заверено Apple
  * Windows: подписано "Anthropic, PBC"

## Установка NPM (устаревшая)

Установка NPM устаревшая. Используйте метод [встроенной установки](#installation) когда это возможно. Для миграции существующей установки npm на встроенную запустите `claude install`.

**Глобальная установка npm**

```sh  theme={null}
npm install -g @anthropic-ai/claude-code
```

<Warning>
  НЕ используйте `sudo npm install -g`, так как это может привести к проблемам с разрешениями и рискам безопасности.
  Если вы столкнулись с ошибками разрешений, см. [устранение неполадок с разрешениями](/ru/troubleshooting#command-not-found-claude-or-permission-errors) для рекомендуемых решений.
</Warning>

## Настройка Windows

**Вариант 1: Claude Code в WSL**

* Поддерживаются как WSL 1, так и WSL 2

**Вариант 2: Claude Code на нативном Windows с Git Bash**

* Требует [Git для Windows](https://git-scm.com/downloads/win)
* Для портативных установок Git укажите путь к вашему `bash.exe`:
  ```powershell  theme={null}
  $env:CLAUDE_CODE_GIT_BASH_PATH="C:\Program Files\Git\bin\bash.exe"
  ```

## Обновление Claude Code

### Автоматические обновления

Claude Code автоматически обновляется, чтобы убедиться, что у вас есть последние функции и исправления безопасности.

* **Проверки обновлений**: выполняются при запуске и периодически во время работы
* **Процесс обновления**: загружает и устанавливает автоматически в фоновом режиме
* **Уведомления**: вы увидите уведомление при установке обновлений
* **Применение обновлений**: обновления вступают в силу при следующем запуске Claude Code

<Note>
  Установки Homebrew и WinGet не обновляются автоматически. Используйте `brew upgrade claude-code` или `winget upgrade Anthropic.ClaudeCode` для ручного обновления.

  **Известная проблема:** Claude Code может уведомить вас об обновлениях до того, как новая версия будет доступна в этих менеджерах пакетов. Если обновление не удается, подождите и попробуйте позже.
</Note>

### Настройка канала выпуска

Настройте, какой канал выпуска Claude Code следует для автоматических обновлений и `claude update` с помощью параметра `autoUpdatesChannel`:

* `"latest"` (по умолчанию): получайте новые функции сразу после их выпуска
* `"stable"`: используйте версию, которая обычно примерно неделю старше, пропуская выпуски с серьезными регрессиями

Настройте это через `/config` → **Auto-update channel**, или добавьте это в ваш [файл settings.json](/ru/settings):

```json  theme={null}
{
  "autoUpdatesChannel": "stable"
}
```

Для корпоративных развертываний вы можете обеспечить согласованный канал выпуска во всей вашей организации, используя [управляемые параметры](/ru/iam#managed-settings).

### Отключение автоматических обновлений

Установите переменную окружения `DISABLE_AUTOUPDATER` в вашей оболочке или [файле settings.json](/ru/settings):

```bash  theme={null}
export DISABLE_AUTOUPDATER=1
```

### Ручное обновление

```bash  theme={null}
claude update
```

## Удаление Claude Code

Если вам нужно удалить Claude Code, следуйте инструкциям для вашего метода установки.

### Встроенная установка

Удалите двоичный файл Claude Code и файлы версии:

**macOS, Linux, WSL:**

```bash  theme={null}
rm -f ~/.local/bin/claude
rm -rf ~/.local/share/claude
```

**Windows PowerShell:**

```powershell  theme={null}
Remove-Item -Path "$env:USERPROFILE\.local\bin\claude.exe" -Force
Remove-Item -Path "$env:USERPROFILE\.local\share\claude" -Recurse -Force
```

**Windows CMD:**

```batch  theme={null}
del "%USERPROFILE%\.local\bin\claude.exe"
rmdir /s /q "%USERPROFILE%\.local\share\claude"
```

### Установка Homebrew

```bash  theme={null}
brew uninstall --cask claude-code
```

### Установка WinGet

```powershell  theme={null}
winget uninstall Anthropic.ClaudeCode
```

### Установка NPM

```bash  theme={null}
npm uninstall -g @anthropic-ai/claude-code
```

### Очистка файлов конфигурации (необязательно)

<Warning>
  Удаление файлов конфигурации удалит все ваши параметры, разрешенные инструменты, конфигурации сервера MCP и историю сеансов.
</Warning>

Для удаления параметров Claude Code и кэшированных данных:

**macOS, Linux, WSL:**

```bash  theme={null}
# Удалить пользовательские параметры и состояние
rm -rf ~/.claude
rm ~/.claude.json

# Удалить параметры, специфичные для проекта (запустите из каталога вашего проекта)
rm -rf .claude
rm -f .mcp.json
```

**Windows PowerShell:**

```powershell  theme={null}
# Удалить пользовательские параметры и состояние
Remove-Item -Path "$env:USERPROFILE\.claude" -Recurse -Force
Remove-Item -Path "$env:USERPROFILE\.claude.json" -Force

# Удалить параметры, специфичные для проекта (запустите из каталога вашего проекта)
Remove-Item -Path ".claude" -Recurse -Force
Remove-Item -Path ".mcp.json" -Force
```

**Windows CMD:**

```batch  theme={null}
REM Удалить пользовательские параметры и состояние
rmdir /s /q "%USERPROFILE%\.claude"
del "%USERPROFILE%\.claude.json"

REM Удалить параметры, специфичные для проекта (запустите из каталога вашего проекта)
rmdir /s /q ".claude"
del ".mcp.json"
```
