> ## Documentation Index
> Fetch the complete documentation index at: https://code.claude.com/docs/llms.txt
> Use this file to discover all available pages before exploring further.

# Использование Claude Code в VS Code

> Установите и настройте расширение Claude Code для VS Code. Получите помощь в написании кода с встроенными diff, @-упоминаниями, проверкой плана и сочетаниями клавиш.

<img src="https://mintcdn.com/claude-code/-YhHHmtSxwr7W8gy/images/vs-code-extension-interface.jpg?fit=max&auto=format&n=-YhHHmtSxwr7W8gy&q=85&s=300652d5678c63905e6b0ea9e50835f8" alt="Редактор VS Code с открытой панелью расширения Claude Code справа, показывающей беседу с Claude" data-og-width="2500" width="2500" data-og-height="1155" height="1155" data-path="images/vs-code-extension-interface.jpg" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/claude-code/-YhHHmtSxwr7W8gy/images/vs-code-extension-interface.jpg?w=280&fit=max&auto=format&n=-YhHHmtSxwr7W8gy&q=85&s=87630c671517a3d52e9aee627041696e 280w, https://mintcdn.com/claude-code/-YhHHmtSxwr7W8gy/images/vs-code-extension-interface.jpg?w=560&fit=max&auto=format&n=-YhHHmtSxwr7W8gy&q=85&s=716b093879204beec8d952649ef75292 560w, https://mintcdn.com/claude-code/-YhHHmtSxwr7W8gy/images/vs-code-extension-interface.jpg?w=840&fit=max&auto=format&n=-YhHHmtSxwr7W8gy&q=85&s=c1525d1a01513acd9d83d8b5a8fe2fc8 840w, https://mintcdn.com/claude-code/-YhHHmtSxwr7W8gy/images/vs-code-extension-interface.jpg?w=1100&fit=max&auto=format&n=-YhHHmtSxwr7W8gy&q=85&s=1d90021d58bbb51f871efec13af955c3 1100w, https://mintcdn.com/claude-code/-YhHHmtSxwr7W8gy/images/vs-code-extension-interface.jpg?w=1650&fit=max&auto=format&n=-YhHHmtSxwr7W8gy&q=85&s=7babdd25440099886f193cfa99af88ae 1650w, https://mintcdn.com/claude-code/-YhHHmtSxwr7W8gy/images/vs-code-extension-interface.jpg?w=2500&fit=max&auto=format&n=-YhHHmtSxwr7W8gy&q=85&s=08c92eedfb56fe61a61e480fb63784b6 2500w" />

Расширение VS Code предоставляет собственный графический интерфейс для Claude Code, интегрированный непосредственно в вашу IDE. Это рекомендуемый способ использования Claude Code в VS Code.

С расширением вы можете просматривать и редактировать планы Claude перед их принятием, автоматически принимать правки по мере их внесения, использовать @-упоминания файлов с определёнными диапазонами строк из вашего выделения, получать доступ к истории беседы и открывать несколько бесед в отдельных вкладках или окнах.

## Предварительные требования

* VS Code 1.98.0 или выше
* Учётная запись Anthropic (вы войдёте при первом открытии расширения). Если вы используете поставщика услуг третьей стороны, такого как Amazon Bedrock или Google Vertex AI, см. раздел [Использование поставщиков третьей стороны](#use-third-party-providers).

<Tip>
  Расширение включает CLI (интерфейс командной строки), который вы можете использовать из встроенного терминала VS Code для расширенных функций. Подробнее см. в разделе [Расширение VS Code и Claude Code CLI](#vs-code-extension-vs-claude-code-cli).
</Tip>

## Установка расширения

Нажмите на ссылку для вашей IDE, чтобы установить напрямую:

* [Установить для VS Code](vscode:extension/anthropic.claude-code)
* [Установить для Cursor](cursor:extension/anthropic.claude-code)

Или в VS Code нажмите `Cmd+Shift+X` (Mac) или `Ctrl+Shift+X` (Windows/Linux), чтобы открыть представление расширений, найдите "Claude Code" и нажмите **Установить**.

<Note>Если расширение не появляется после установки, перезагрузите VS Code или выполните "Developer: Reload Window" из палитры команд.</Note>

## Начало работы

После установки вы можете начать использовать Claude Code через интерфейс VS Code:

<Steps>
  <Step title="Откройте панель Claude Code">
    По всему VS Code значок Spark указывает на Claude Code: <img src="https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-spark-icon.svg?fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=a734d84e785140016672f08e0abb236c" alt="Spark icon" style={{display: "inline", height: "0.85em", verticalAlign: "middle"}} data-og-width="16" width="16" data-og-height="16" height="16" data-path="images/vs-code-spark-icon.svg" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-spark-icon.svg?w=280&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=9a45aad9a84b9fa1701ac99a1f9aa4e9 280w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-spark-icon.svg?w=560&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=3f4cb9254c4d4e93989c4b6bf9292f4b 560w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-spark-icon.svg?w=840&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=e75ccc9faa3e572db8f291ceb65bb264 840w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-spark-icon.svg?w=1100&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=f147bd81a381a62539a4ce361fac41c7 1100w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-spark-icon.svg?w=1650&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=78fe68efaee5d6e844bbacab1b442ed5 1650w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-spark-icon.svg?w=2500&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=efb8dbe1dfa722d094edc6ad2ad4bedb 2500w" />

    Самый быстрый способ открыть Claude — нажать на значок Spark в **панели инструментов редактора** (верхний правый угол редактора). Значок появляется только при открытом файле.

        <img src="https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-editor-icon.png?fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=eb4540325d94664c51776dbbfec4cf02" alt="Редактор VS Code, показывающий значок Spark в панели инструментов редактора" data-og-width="2796" width="2796" data-og-height="734" height="734" data-path="images/vs-code-editor-icon.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-editor-icon.png?w=280&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=56f218d5464359d6480cfe23f70a923e 280w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-editor-icon.png?w=560&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=344a8db024b196c795a80dc85cacb8d1 560w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-editor-icon.png?w=840&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=f30bf834ee0625b2a4a635d552d87163 840w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-editor-icon.png?w=1100&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=81fdf984840e43a9f08ae42729d1484d 1100w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-editor-icon.png?w=1650&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=8b60fb32de54717093d512afaa99785c 1650w, https://mintcdn.com/claude-code/mfM-EyoZGnQv8JTc/images/vs-code-editor-icon.png?w=2500&fit=max&auto=format&n=mfM-EyoZGnQv8JTc&q=85&s=893e6bda8f2e9d42c8a294d394f0b736 2500w" />

    Другие способы открыть Claude Code:

    * **Палита команд**: `Cmd+Shift+P` (Mac) или `Ctrl+Shift+P` (Windows/Linux), введите "Claude Code" и выберите опцию, например "Open in New Tab"
    * **Строка состояния**: Нажмите **✱ Claude Code** в нижнем правом углу окна. Это работает даже при отсутствии открытого файла.

    Вы можете перетащить панель Claude в любое место в VS Code. Подробнее см. в разделе [Настройка вашего рабочего процесса](#customize-your-workflow).
  </Step>

  <Step title="Отправьте запрос">
    Попросите Claude помочь с вашим кодом или файлами, будь то объяснение того, как что-то работает, отладка проблемы или внесение изменений.

    <Tip>Claude автоматически видит ваш выделенный текст. Нажмите `Option+K` (Mac) / `Alt+K` (Windows/Linux), чтобы также вставить ссылку @-упоминания (например, `@file.ts#5-10`) в ваш запрос.</Tip>

    Вот пример вопроса о конкретной строке в файле:

        <img src="https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-send-prompt.png?fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=ede3ed8d8d5f940e01c5de636d009cfd" alt="Редактор VS Code с выделенными строками 2-3 в файле Python и панелью Claude Code, показывающей вопрос об этих строках со ссылкой @-упоминания" data-og-width="3288" width="3288" data-og-height="1876" height="1876" data-path="images/vs-code-send-prompt.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-send-prompt.png?w=280&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=f40bde7b2c245fe8f0f5b784e8106492 280w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-send-prompt.png?w=560&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=fad66a27a9a6faa23b05370aa4f398b2 560w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-send-prompt.png?w=840&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=4539c8a3823ca80a5c8771f6c088ce9e 840w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-send-prompt.png?w=1100&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=fae8ebf300c7853409a562ffa46d9c71 1100w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-send-prompt.png?w=1650&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=22e4462bb8cf0c0ca20f8102bc4c971a 1650w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-send-prompt.png?w=2500&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=739bfd045f70fe7be1a109a53494590e 2500w" />
  </Step>

  <Step title="Проверьте изменения">
    Когда Claude хочет отредактировать файл, он показывает сравнение оригинала и предложенных изменений рядом, а затем просит разрешение. Вы можете принять, отклонить или сказать Claude, что делать вместо этого.

        <img src="https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-edits.png?fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=e005f9b41c541c5c7c59c082f7c4841c" alt="VS Code, показывающий diff предложенных Claude изменений с запросом разрешения на внесение правки" data-og-width="3292" width="3292" data-og-height="1876" height="1876" data-path="images/vs-code-edits.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-edits.png?w=280&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=cb5d41b81087f79b842a56b5a3304660 280w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-edits.png?w=560&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=90bb691960decdc06393c3c21cd62c75 560w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-edits.png?w=840&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=9a11bf878ba619e850380904ff4f38e8 840w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-edits.png?w=1100&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=6dddbf596b4f69ec6245bdc5eb6dd487 1100w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-edits.png?w=1650&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=ef2713b8cbfd2cee97af817d813d64c7 1650w, https://mintcdn.com/claude-code/FVYz38sRY-VuoGHA/images/vs-code-edits.png?w=2500&fit=max&auto=format&n=FVYz38sRY-VuoGHA&q=85&s=1f7e1c52919cdfddf295f32a2ec7ae59 2500w" />
  </Step>
</Steps>

Для получения дополнительных идей о том, что вы можете делать с Claude Code, см. [Типичные рабочие процессы](/ru/common-workflows).

<Tip>
  Расширение включает два встроенных учебника:

  * **Пошаговое руководство VS Code**: Выполните "Claude Code: Open Walkthrough" из палитры команд для экскурсии по основам.
  * **Интерактивный контрольный список**: Нажмите на значок выпускной шапки в заголовке панели Claude, чтобы пройти функции, такие как написание кода, использование режима Plan и настройка правил.
</Tip>

## Использование поля ввода запроса

Поле ввода запроса поддерживает несколько функций:

* **Режимы разрешений**: Нажмите на индикатор режима в нижней части поля ввода запроса, чтобы переключать режимы. В обычном режиме Claude просит разрешение перед каждым действием. В режиме Plan Claude описывает, что он будет делать, и ждёт одобрения перед внесением изменений. В режиме автоматического принятия Claude вносит правки без запроса. Установите значение по умолчанию в параметрах VS Code в разделе `claudeCode.initialPermissionMode`.
* **Меню команд**: Нажмите `/` или введите `/`, чтобы открыть меню команд. Опции включают присоединение файлов, переключение моделей, переключение расширенного мышления и просмотр использования плана (`/usage`). Раздел "Настройка" предоставляет доступ к MCP servers, hooks, памяти, разрешениям и plugins. Элементы со значком терминала открываются во встроенном терминале.
* **Индикатор контекста**: Поле ввода запроса показывает, сколько контекстного окна Claude вы используете. Claude автоматически компактирует при необходимости, или вы можете запустить `/compact` вручную.
* **Расширенное мышление**: Позволяет Claude потратить больше времени на рассуждение о сложных проблемах. Включите его через меню команд (`/`). Подробнее см. в разделе [Расширенное мышление](/ru/common-workflows#use-extended-thinking-thinking-mode).
* **Многострочный ввод**: Нажмите `Shift+Enter`, чтобы добавить новую строку без отправки.

### Ссылка на файлы и папки

Используйте @-упоминания, чтобы дать Claude контекст о конкретных файлах или папках. Когда вы вводите `@` с последующим именем файла или папки, Claude читает это содержимое и может ответить на вопросы о нём или внести в него изменения. Claude Code поддерживает нечёткое совпадение, поэтому вы можете вводить частичные имена, чтобы найти то, что вам нужно:

```
> Explain the logic in @auth (fuzzy matches auth.js, AuthService.ts, etc.)
> What's in @src/components/ (include a trailing slash for folders)
```

Когда вы выделяете текст в редакторе, Claude может видеть ваш выделенный код автоматически. Нижняя часть поля ввода запроса показывает, сколько строк выделено. Нажмите `Option+K` (Mac) / `Alt+K` (Windows/Linux), чтобы вставить @-упоминание с путём файла и номерами строк (например, `@app.ts#5-10`). Нажмите на индикатор выделения, чтобы переключить, может ли Claude видеть ваш выделенный текст — значок с перечёркиванием глаза означает, что выделение скрыто от Claude.

Вы также можете удерживать `Shift` при перетаскивании файлов в поле ввода запроса, чтобы добавить их как вложения. Нажмите X на любом вложении, чтобы удалить его из контекста.

### Возобновление прошлых бесед

Нажмите на раскрывающееся меню в верхней части панели Claude Code, чтобы получить доступ к истории ваших бесед. Вы можете искать по ключевому слову или просматривать по времени (Сегодня, Вчера, Последние 7 дней и т. д.). Нажмите на любую беседу, чтобы возобновить её с полной историей сообщений. Подробнее о возобновлении сеансов см. в разделе [Типичные рабочие процессы](/ru/common-workflows#resume-previous-conversations).

### Возобновление удалённых сеансов из Claude.ai

Если вы используете [Claude Code в веб-версии](/ru/claude-code-on-the-web), вы можете возобновить эти удалённые сеансы непосредственно в VS Code. Это требует входа с помощью **Claude.ai Subscription**, а не Anthropic Console.

<Steps>
  <Step title="Откройте прошлые беседы">
    Нажмите на раскрывающееся меню **Past Conversations** в верхней части панели Claude Code.
  </Step>

  <Step title="Выберите вкладку Remote">
    Диалог показывает две вкладки: Local и Remote. Нажмите **Remote**, чтобы увидеть сеансы из claude.ai.
  </Step>

  <Step title="Выберите сеанс для возобновления">
    Просмотрите или найдите ваши удалённые сеансы. Нажмите на любой сеанс, чтобы загрузить его и продолжить беседу локально.
  </Step>
</Steps>

<Note>
  Только веб-сеансы, начатые с репозитория GitHub, появляются на вкладке Remote. Возобновление загружает историю беседы локально; изменения не синхронизируются обратно в claude.ai.
</Note>

## Настройка вашего рабочего процесса

После того как вы начнёте работать, вы можете переместить панель Claude, запустить несколько сеансов или переключиться в режим терминала.

### Выберите, где находится Claude

Вы можете перетащить панель Claude в любое место в VS Code. Возьмите вкладку или заголовок панели и перетащите её в:

* **Вторичная боковая панель**: Правая сторона окна. Держит Claude видимым во время кодирования.
* **Основная боковая панель**: Левая боковая панель со значками для Explorer, Search и т. д.
* **Область редактора**: Открывает Claude как вкладку рядом с вашими файлами. Полезно для побочных задач.

<Tip>
  Используйте боковую панель для вашего основного сеанса Claude и открывайте дополнительные вкладки для побочных задач. Claude запоминает ваше предпочтительное местоположение. Обратите внимание, что значок Spark появляется в Activity Bar только при закреплении панели Claude слева. Поскольку Claude по умолчанию находится справа, используйте значок в панели инструментов редактора, чтобы открыть Claude.
</Tip>

### Запуск нескольких бесед

Используйте **Open in New Tab** или **Open in New Window** из палитры команд, чтобы начать дополнительные беседы. Каждая беседа сохраняет свою собственную историю и контекст, позволяя вам работать над различными задачами параллельно.

При использовании вкладок небольшая цветная точка на значке spark указывает статус: синий означает, что ожидается запрос разрешения, оранжевый означает, что Claude закончил, пока вкладка была скрыта.

### Переключение в режим терминала

По умолчанию расширение открывает графическую панель чата. Если вы предпочитаете интерфейс в стиле CLI, откройте [параметр Use Terminal](vscode://settings/claudeCode.useTerminal) и установите флажок.

Вы также можете открыть параметры VS Code (`Cmd+,` на Mac или `Ctrl+,` на Windows/Linux), перейти в Extensions → Claude Code и установить флажок **Use Terminal**.

## Управление plugins

Расширение VS Code включает графический интерфейс для установки и управления [plugins](/ru/plugins). Введите `/plugins` в поле ввода запроса, чтобы открыть интерфейс **Manage plugins**.

### Установка plugins

Диалог plugin показывает две вкладки: **Plugins** и **Marketplaces**.

На вкладке Plugins:

* **Установленные plugins** появляются в верхней части с переключателями для их включения или отключения
* **Доступные plugins** из ваших настроенных marketplaces появляются ниже
* Используйте поиск для фильтрации plugins по имени или описанию
* Нажмите **Install** на любом доступном plugin

Когда вы устанавливаете plugin, выберите область установки:

* **Install for you**: Доступно во всех ваших проектах (область пользователя)
* **Install for this project**: Общее с сотрудниками проекта (область проекта)
* **Install locally**: Только для вас, только в этом репозитории (локальная область)

### Управление marketplaces

Переключитесь на вкладку **Marketplaces**, чтобы добавить или удалить источники plugins:

* Введите репозиторий GitHub, URL или локальный путь, чтобы добавить новый marketplace
* Нажмите на значок обновления, чтобы обновить список plugins marketplace
* Нажмите на значок корзины, чтобы удалить marketplace

После внесения изменений баннер предложит вам перезагрузить Claude Code, чтобы применить обновления.

<Note>
  Управление plugins в VS Code использует те же команды CLI под капотом. Plugins и marketplaces, которые вы настраиваете в расширении, также доступны в CLI, и наоборот.
</Note>

Подробнее о системе plugins см. в разделах [Plugins](/ru/plugins) и [Plugin marketplaces](/ru/plugin-marketplaces).

## Команды и сочетания клавиш VS Code

Откройте палитру команд (`Cmd+Shift+P` на Mac или `Ctrl+Shift+P` на Windows/Linux) и введите "Claude Code", чтобы увидеть все доступные команды VS Code для расширения Claude Code.

Некоторые сочетания клавиш зависят от того, какая панель "сфокусирована" (получает ввод с клавиатуры). Когда ваш курсор находится в файле кода, редактор сфокусирован. Когда ваш курсор находится в поле ввода запроса Claude, Claude сфокусирован. Используйте `Cmd+Esc` / `Ctrl+Esc`, чтобы переключаться между ними.

<Note>
  Это команды VS Code для управления расширением. Не все встроенные команды Claude Code доступны в расширении. Подробнее см. в разделе [Расширение VS Code и Claude Code CLI](#vs-code-extension-vs-claude-code-cli).
</Note>

| Команда                    | Сочетание клавиш                                         | Описание                                                               |
| -------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------- |
| Focus Input                | `Cmd+Esc` (Mac) / `Ctrl+Esc` (Windows/Linux)             | Переключение фокуса между редактором и Claude                          |
| Open in Side Bar           | -                                                        | Открыть Claude в левой боковой панели                                  |
| Open in Terminal           | -                                                        | Открыть Claude в режиме терминала                                      |
| Open in New Tab            | `Cmd+Shift+Esc` (Mac) / `Ctrl+Shift+Esc` (Windows/Linux) | Открыть новую беседу как вкладку редактора                             |
| Open in New Window         | -                                                        | Открыть новую беседу в отдельном окне                                  |
| New Conversation           | `Cmd+N` (Mac) / `Ctrl+N` (Windows/Linux)                 | Начать новую беседу (требует фокуса Claude)                            |
| Insert @-Mention Reference | `Option+K` (Mac) / `Alt+K` (Windows/Linux)               | Вставить ссылку на текущий файл и выделение (требует фокуса редактора) |
| Show Logs                  | -                                                        | Просмотр журналов отладки расширения                                   |
| Logout                     | -                                                        | Выход из учётной записи Anthropic                                      |

## Настройка параметров

Расширение имеет два типа параметров:

* **Параметры расширения** в VS Code: Управляют поведением расширения в VS Code. Откройте с помощью `Cmd+,` (Mac) или `Ctrl+,` (Windows/Linux), затем перейдите в Extensions → Claude Code. Вы также можете ввести `/` и выбрать **General Config**, чтобы открыть параметры.
* **Параметры Claude Code** в `~/.claude/settings.json`: Общие для расширения и CLI. Используйте для разрешённых команд, переменных окружения, hooks и MCP servers. Подробнее см. в разделе [Параметры](/ru/settings).

### Параметры расширения

| Параметр                          | По умолчанию | Описание                                                                                                                    |
| --------------------------------- | ------------ | --------------------------------------------------------------------------------------------------------------------------- |
| `selectedModel`                   | `default`    | Модель для новых бесед. Измените для каждого сеанса с помощью `/model`.                                                     |
| `useTerminal`                     | `false`      | Запустить Claude в режиме терминала вместо графической панели                                                               |
| `initialPermissionMode`           | `default`    | Управляет запросами одобрения: `default` (спросить каждый раз), `plan`, `acceptEdits` или `bypassPermissions`               |
| `preferredLocation`               | `panel`      | Где открывается Claude: `sidebar` (справа) или `panel` (новая вкладка)                                                      |
| `autosave`                        | `true`       | Автоматически сохранять файлы перед тем, как Claude их читает или пишет                                                     |
| `useCtrlEnterToSend`              | `false`      | Использовать Ctrl/Cmd+Enter вместо Enter для отправки запросов                                                              |
| `enableNewConversationShortcut`   | `true`       | Включить Cmd/Ctrl+N для начала новой беседы                                                                                 |
| `hideOnboarding`                  | `false`      | Скрыть контрольный список адаптации (значок выпускной шапки)                                                                |
| `respectGitIgnore`                | `true`       | Исключить шаблоны .gitignore из поиска файлов                                                                               |
| `environmentVariables`            | `[]`         | Установить переменные окружения для процесса Claude. Используйте параметры Claude Code вместо этого для общей конфигурации. |
| `disableLoginPrompt`              | `false`      | Пропустить запросы аутентификации (для настроек поставщиков третьей стороны)                                                |
| `allowDangerouslySkipPermissions` | `false`      | Обойти все запросы разрешений. **Используйте с крайней осторожностью.**                                                     |
| `claudeProcessWrapper`            | -            | Путь исполняемого файла, используемый для запуска процесса Claude                                                           |

## Расширение VS Code и Claude Code CLI

Claude Code доступен как расширение VS Code (графическая панель), так и CLI (интерфейс командной строки в терминале). Некоторые функции доступны только в CLI. Если вам нужна функция, доступная только в CLI, запустите `claude` во встроенном терминале VS Code.

| Функция                 | CLI                                           | Расширение VS Code                                  |
| ----------------------- | --------------------------------------------- | --------------------------------------------------- |
| Команды и skills        | [Все](/ru/interactive-mode#built-in-commands) | Подмножество (введите `/`, чтобы увидеть доступные) |
| Конфигурация MCP server | Да                                            | Нет (настройте через CLI, используйте в расширении) |
| Checkpoints             | Да                                            | Скоро                                               |
| `!` bash shortcut       | Да                                            | Нет                                                 |
| Tab completion          | Да                                            | Нет                                                 |

### Запуск CLI в VS Code

Чтобы использовать CLI, оставаясь в VS Code, откройте встроенный терминал (`` Ctrl+` `` на Windows/Linux или `` Cmd+` `` на Mac) и запустите `claude`. CLI автоматически интегрируется с вашей IDE для функций, таких как просмотр diff и обмен диагностикой.

Если вы используете внешний терминал, запустите `/ide` внутри Claude Code, чтобы подключить его к VS Code.

### Переключение между расширением и CLI

Расширение и CLI используют одну и ту же историю бесед. Чтобы продолжить беседу расширения в CLI, запустите `claude --resume` в терминале. Это открывает интерактивный выбор, где вы можете искать и выбирать вашу беседу.

### Включение вывода терминала в запросы

Ссылайтесь на вывод терминала в ваших запросах, используя `@terminal:name`, где `name` — это название терминала. Это позволяет Claude видеть вывод команды, сообщения об ошибках или журналы без копирования и вставки.

### Мониторинг фоновых процессов

Когда Claude запускает долгоживущие команды, расширение показывает прогресс в строке состояния. Однако видимость фоновых задач ограничена по сравнению с CLI. Для лучшей видимости попросите Claude вывести команду, чтобы вы могли запустить её во встроенном терминале VS Code.

### Подключение к внешним инструментам с помощью MCP

MCP (Model Context Protocol) servers дают Claude доступ к внешним инструментам, базам данных и API. Настройте их через CLI, затем используйте как в расширении, так и в CLI.

Чтобы добавить MCP server, откройте встроенный терминал (`` Ctrl+` `` или `` Cmd+` ``) и запустите:

```bash  theme={null}
claude mcp add --transport http github https://api.githubcopilot.com/mcp/
```

После настройки попросите Claude использовать инструменты (например, "Review PR #456"). Некоторые servers требуют аутентификации: запустите `claude` в терминале, затем введите `/mcp` для аутентификации. Подробнее см. в [документации MCP](/ru/mcp).

## Работа с git

Claude Code интегрируется с git, чтобы помочь с рабочими процессами контроля версий непосредственно в VS Code. Попросите Claude зафиксировать изменения, создать pull requests или работать между ветвями.

### Создание commits и pull requests

Claude может подготовить изменения, написать сообщения commit и создать pull requests на основе вашей работы:

```
> commit my changes with a descriptive message
> create a pr for this feature
> summarize the changes I've made to the auth module
```

При создании pull requests Claude генерирует описания на основе фактических изменений кода и может добавить контекст о тестировании или решениях по реализации.

### Использование git worktrees для параллельных задач

Git worktrees позволяют нескольким сеансам Claude Code работать на отдельных ветвях одновременно, каждый с изолированными файлами:

```bash  theme={null}
# Create a worktree for a new feature
git worktree add ../project-feature-a -b feature-a

# Run Claude Code in each worktree
cd ../project-feature-a && claude
```

Каждый worktree сохраняет независимое состояние файлов при совместном использовании истории git. Это предотвращает вмешательство экземпляров Claude друг в друга при работе над различными задачами.

Подробнее о рабочих процессах git, включая проверку PR и управление ветвями, см. в разделе [Типичные рабочие процессы](/ru/common-workflows#create-pull-requests).

## Использование поставщиков третьей стороны

По умолчанию Claude Code подключается непосредственно к API Anthropic. Если ваша организация использует Amazon Bedrock, Google Vertex AI или Microsoft Foundry для доступа к Claude, настройте расширение для использования вашего поставщика вместо этого:

<Steps>
  <Step title="Отключите запрос входа">
    Откройте [параметр Disable Login Prompt](vscode://settings/claudeCode.disableLoginPrompt) и установите флажок.

    Вы также можете открыть параметры VS Code (`Cmd+,` на Mac или `Ctrl+,` на Windows/Linux), найти "Claude Code login" и установить флажок **Disable Login Prompt**.
  </Step>

  <Step title="Настройте вашего поставщика">
    Следуйте руководству по настройке для вашего поставщика:

    * [Claude Code на Amazon Bedrock](/ru/amazon-bedrock)
    * [Claude Code на Google Vertex AI](/ru/google-vertex-ai)
    * [Claude Code на Microsoft Foundry](/ru/microsoft-foundry)

    Эти руководства охватывают настройку вашего поставщика в `~/.claude/settings.json`, что обеспечивает совместное использование ваших параметров между расширением VS Code и CLI.
  </Step>
</Steps>

## Безопасность и конфиденциальность

Ваш код остаётся приватным. Claude Code обрабатывает ваш код для предоставления помощи, но не использует его для обучения моделей. Подробнее об обработке данных и о том, как отказаться от логирования, см. в разделе [Данные и конфиденциальность](/ru/data-usage).

С включёнными разрешениями на автоматическое редактирование Claude Code может изменять файлы конфигурации VS Code (такие как `settings.json` или `tasks.json`), которые VS Code может выполнять автоматически. Чтобы снизить риск при работе с ненадёжным кодом:

* Включите [VS Code Restricted Mode](https://code.visualstudio.com/docs/editor/workspace-trust#_restricted-mode) для ненадёжных рабочих пространств
* Используйте режим ручного одобрения вместо автоматического принятия для правок
* Тщательно проверяйте изменения перед их принятием

## Исправление типичных проблем

### Расширение не устанавливается

* Убедитесь, что у вас совместимая версия VS Code (1.98.0 или выше)
* Проверьте, что VS Code имеет разрешение на установку расширений
* Попробуйте установить напрямую из [VS Code Marketplace](https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code)

### Значок Spark не виден

Значок Spark появляется в **панели инструментов редактора** (верхний правый угол редактора) при открытом файле. Если вы его не видите:

1. **Откройте файл**: Значок требует открытого файла. Просто открытая папка недостаточна.
2. **Проверьте версию VS Code**: Требуется 1.98.0 или выше (Help → About)
3. **Перезагрузите VS Code**: Выполните "Developer: Reload Window" из палитры команд
4. **Отключите конфликтующие расширения**: Временно отключите другие расширения AI (Cline, Continue и т. д.)
5. **Проверьте доверие рабочего пространства**: Расширение не работает в режиме Restricted Mode

Альтернативно, нажмите "✱ Claude Code" в **строке состояния** (нижний правый угол). Это работает даже без открытого файла. Вы также можете использовать **палитру команд** (`Cmd+Shift+P` / `Ctrl+Shift+P`) и ввести "Claude Code".

### Claude Code никогда не отвечает

Если Claude Code не отвечает на ваши запросы:

1. **Проверьте подключение к интернету**: Убедитесь, что у вас стабильное подключение к интернету
2. **Начните новую беседу**: Попробуйте начать свежую беседу, чтобы увидеть, сохраняется ли проблема
3. **Попробуйте CLI**: Запустите `claude` из терминала, чтобы увидеть более подробные сообщения об ошибках

Если проблемы сохраняются, [создайте issue на GitHub](https://github.com/anthropics/claude-code/issues) с подробностями об ошибке.

## Удаление расширения

Чтобы удалить расширение Claude Code:

1. Откройте представление расширений (`Cmd+Shift+X` на Mac или `Ctrl+Shift+X` на Windows/Linux)
2. Найдите "Claude Code"
3. Нажмите **Uninstall**

Чтобы также удалить данные расширения и сбросить все параметры:

```bash  theme={null}
rm -rf ~/.vscode/globalStorage/anthropic.claude-code
```

Для получения дополнительной помощи см. [руководство по устранению неполадок](/ru/troubleshooting).

## Следующие шаги

Теперь, когда у вас установлен Claude Code в VS Code:

* [Изучите типичные рабочие процессы](/ru/common-workflows), чтобы максимально использовать Claude Code
* [Настройте MCP servers](/ru/mcp), чтобы расширить возможности Claude с помощью внешних инструментов. Настройте servers с помощью CLI, затем используйте их в расширении.
* [Настройте параметры Claude Code](/ru/settings), чтобы настроить разрешённые команды, hooks и многое другое. Эти параметры общие для расширения и CLI.
