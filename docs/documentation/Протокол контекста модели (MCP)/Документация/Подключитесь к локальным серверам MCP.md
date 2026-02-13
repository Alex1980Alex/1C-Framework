> ## Индекс документации
Полный индекс документации доступен по адресу: https://modelcontextprotocol.io/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Подключение к локальным серверам MCP

Узнайте, как расширить функциональность Claude Desktop с помощью локальных серверов MCP, чтобы обеспечить доступ к файловой системе и другие мощные интеграции.

Серверы протокола контекста модели (MCP) расширяют возможности приложений искусственного интеллекта, обеспечивая безопасный и контролируемый доступ к локальным ресурсам и инструментам. Многие клиенты поддерживают MCP, что открывает разнообразные возможности интеграции на различных платформах и в приложениях.

В этом руководстве показано, как подключиться к локальным серверам MCP, используя в качестве примера Claude Desktop, один из [многих клиентов, поддерживающих MCP](/clients). Хотя мы сосредоточимся на реализации в Claude Desktop, изложенные концепции в целом применимы и к другим MCP-совместимым клиентам. К концу этого руководства Claude сможет взаимодействовать с файлами на вашем компьютере, создавать новые документы, организовывать папки и осуществлять поиск по файловой системе — и всё это с вашим явным разрешением на каждое действие.

<Рамка>
  <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=629d7e754dc358d71a408d6ce970c1b1" alt="Рабочий стол Claude с интеграцией файловой системы, демонстрирующий возможности управления файлами" data-og-width="1732" width="1732" data-og-height="2060" height="2060" data-path="images/quickstart-filesystem.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0758ee60aee8acc3035727957612351f 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=3bc6d3ea4a3cd38b6d031ac386700c62 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=9d75e8729b08b452f2e0d08bff8ce393 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=b35c6b531daa84b4ba4b06c9223b1ee2 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c4bb491d17a65e038120b5c39031ab7f 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-filesystem.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=ea7a0ad5ae5eeb866222f4020dc7bba3 2500 Вт" />
</Frame>

## Предварительные условия

Перед началом этого руководства убедитесь, что на вашей системе установлены следующие компоненты:

### Рабочий стол Клода

Загрузите и установите [Claude Desktop](https://claude.ai/download) для вашей операционной системы. Claude Desktop доступен для macOS и Windows.

Если у вас уже установлена ​​программа Claude Desktop, убедитесь, что вы используете последнюю версию, щелкнув меню Claude и выбрав «Проверить наличие обновлений...».

### Node.js

Для работы Filesystem Server и многих других серверов MCP требуется Node.js. Проверьте наличие установленного Node.js, открыв терминал или командную строку и выполнив следующую команду:

```bash theme={null}
node --version
```

Если Node.js не установлен, скачайте его с сайта [nodejs.org](https://nodejs.org/). Для обеспечения стабильности мы рекомендуем версию с долгосрочной поддержкой (LTS).

## Понимание работы MCP-серверов

Серверы MCP — это программы, работающие на вашем компьютере и предоставляющие Claude Desktop определенные возможности через стандартизированный протокол. Каждый сервер предоставляет инструменты, которые Claude может использовать для выполнения действий с вашего согласия. Устанавливаемый нами сервер файловой системы предоставляет инструменты для:

* Чтение содержимого файлов и структуры каталогов
* Создание новых файлов и каталогов
* Перемещение и переименование файлов
* Поиск файлов по имени или содержимому

Все действия требуют вашего явного согласия перед выполнением, что гарантирует вам полный контроль над тем, к чему Клод имеет доступ и что может изменять.

## Установка файлового сервера

Процесс включает в себя настройку Claude Desktop таким образом, чтобы сервер файловой системы автоматически запускался при каждом запуске приложения. Эта настройка выполняется с помощью JSON-файла, который указывает Claude Desktop, какие серверы следует запустить и как к ним подключиться.

<Шаги>
  <Шаг title="Открыть настройки рабочего стола Claude">
    Для начала откройте настройки рабочего стола Claude. Щелкните меню Claude в строке меню вашей системы (не настройки в самом окне Claude) и выберите «Настройки...».

    В macOS это отображается в верхней строке меню:

    <Frame style={{ textAlign: "center" }}>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0c8b57e0e17af3624b6762a3ea944c8e" width="400" alt="Меню рабочего стола Клода, показывающее параметр «Настройки»" data-og-width="644" data-og-height="568" data-path="images/quickstart-menu.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=f997b6f31398840d3a824fa0eb9fec43 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=062b0b3c342e4e02a8f2d690a48bcb24 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=ae9b08052b7ea30b31d27432d8edf19e 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7962cc4fb841fa0a04a3c6de03cf4d3d 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=86bd79431e35b133d0ae4f74265f3d60 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-menu.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=1b300ae527efb4744aa08d5df94299a0 2500w" />
    </Frame>

    Это откроет окно конфигурации Claude Desktop, которое отделено от настроек вашей учетной записи Claude.
  </Шаг>

  <Шаг title="Доступ к настройкам разработчика">
    В окне настроек перейдите на вкладку «Разработчик» в левой боковой панели. В этом разделе находятся параметры для настройки серверов MCP и других функций для разработчиков.

    Нажмите кнопку «Редактировать конфигурацию», чтобы открыть файл конфигурации:

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0fb595490a2f9e15c0301e771a57446c" alt="Настройки разработчика, отображающие кнопку «Редактировать конфигурацию»" data-og-width="1688" width="1688" data-og-height="534" height="534" data-path="images/quickstart-developer.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0a7e615ee50a27a4e514668f7cbd9f57 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=16d6d4721219afd7e2bfa41f0795e7e0 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=612b1de5516ed7321d5b6939b5b3c823 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=840a428450dc0ec97538eb4e05050bcd 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=59ae3a95918ff7f7b15e777c2d606496 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-developer.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7838d7f023a281053786870336914f03 2500w" />
    </Frame>

    Это действие создаст новый файл конфигурации, если он не существует, или откроет существующий файл конфигурации. Файл находится по адресу:

    * **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
    * **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
  </Шаг>

  <Шаг title="Настройка сервера файловой системы">
    Замените содержимое конфигурационного файла следующей JSON-структурой. Эта конфигурация указывает Claude Desktop запускать сервер файловой системы с доступом к определенным каталогам:

    <CodeGroup>
      ```json macOS theme={null}
      {
        "mcpServers": {
          "файловая система": {
            "команда": "npx",
            "args": [
              "-y",
              "@modelcontextprotocol/server-filesystem",
              "/Users/username/Desktop",
              "/Users/username/Downloads"
            ]
          }
        }
      }
      ```

      ```json Windows theme={null}
      {
        "mcpServers": {
          "файловая система": {
            "команда": "npx",
            "args": [
              "-y",
              "@modelcontextprotocol/server-filesystem",
              "C:\\Users\\username\\Desktop",
              "C:\\Users\\username\\Downloads"
            ]
          }
        }
      }
      ```
    </CodeGroup>

    Замените `username` на фактическое имя пользователя вашего компьютера. Пути, указанные в массиве `args`, определяют, к каким каталогам может получить доступ файловый сервер. Вы можете изменить эти пути или добавить дополнительные каталоги по мере необходимости.

    <Совет>
      **Понимание конфигурации**

      * `"filesystem"`: Удобное для пользователя имя сервера, отображаемое в Claude Desktop.
      * `"command": "npx"`: Использует инструмент npx из Node.js для запуска сервера.
      * `"-y"`: Автоматически подтверждает установку серверного пакета
      * `"@modelcontextprotocol/server-filesystem"`: Имя пакета сервера файловой системы
      * Остальные аргументы: каталоги, к которым серверу разрешен доступ.
    </Совет>

    <Предупреждение>
      **Вопросы безопасности**

      Предоставляйте Клоду доступ только к тем каталогам, которые вы можете читать и изменять без вашего ведома. Сервер работает с правами вашей учетной записи, поэтому он может выполнять любые файловые операции, которые вы можете выполнять вручную.
    </Предупреждение>
  </Шаг>

  <Шаг title="Перезапустите рабочий стол Клода">
    После сохранения файла конфигурации полностью закройте Claude Desktop и перезапустите его. Приложение необходимо перезапустить, чтобы загрузить новую конфигурацию и запустить сервер MCP.

    После успешного перезапуска вы увидите индикатор сервера MCP <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=2742ec3fb97067e8591e68546c90221e" style={{display: 'inline', margin: 0, height: '1.3em'}} data-og-width="24" width="24" data-og-height="24" height="24" data-path="images/claude-desktop-mcp-slider.svg" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=52839f8519f476623c4fb5bb87ee24bd 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=5 60&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=f0491976e108286441fc6554309c5c4f 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=08e83eb102eda755a7db1eb27d16ebff 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=2524a80752928b0206e68e8e1890d1aa 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=3c0dc88dadad5ed8e8af316965d00e0b 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/claude-desktop-mcp-slider.svg?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=702363a955a631c40c342f9557d5cfdd 2500w" /> в правом нижнем углу поля ввода диалога:

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=f80a38b720fc0519079bae26e2aae312" alt="Интерфейс рабочего стола Клода, показывающий индикатор сервера MCP" data-og-width="1414" width="1414" data-og-height="410" height="410" data-path="images/quickstart-slider.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=24a0dc6f30664e953cc185ed0c7abc64 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=d670a5fd82405775d7bc1e5f20a9a847 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=5f66fa4bcaaf50ca905415f15af2e276 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=4aecd3c4b45c3aaac75a118d2d6edda5 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c7d321e2d25aa34552057a8866782549 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-slider.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=25dc1761b40b11ccb727b36183efa57f 2500w" />
    </Frame>

    Нажмите на этот индикатор, чтобы просмотреть доступные инструменты, предоставляемые файловым сервером:

    <Frame style={{ textAlign: "center" }}>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=18f045f27f31f40896d3710ce9a4a0a0" width="400" alt="Доступные инструменты файловой системы в Claude Desktop" data-og-width="978" data-og-height="902" data-path="images/quickstart-tools.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=298fc5cf79822ee781d15cf6374d8542 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c1e39ca66d9191dbe493cdcb52ad3fcb 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=d797f46eb55126de14328ede4b735967 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=fcb9d89b6cef95bf9a3ffcd9231a4026 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=23097f8f8b52a255246aeb83f85f949d 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-tools.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0007b81f22a6a9b9a117981091e0221f 2500w" />
    </Frame>

    Если индикатор сервера не отображается, обратитесь к разделу [Устранение неполадок](#устранение неполадок) для получения инструкций по отладке.
  </Шаг>
</Шаги>

## Использование файлового сервера

После подключения к серверу файловой системы Клод может взаимодействовать с вашей файловой системой. Попробуйте выполнить следующие примеры запросов, чтобы изучить возможности:

### Примеры управления файлами

* **«Можете написать стихотворение и сохранить его на мой рабочий стол?»** — Клод сочинит стихотворение и создаст новый текстовый файл на вашем рабочем столе.
* **«Какие рабочие файлы находятся в моей папке загрузок?»** - Клод просканирует ваши загрузки и определит документы, относящиеся к работе.
* **«Пожалуйста, упорядочьте все изображения на моем рабочем столе в новую папку под названием «Изображения»»** — Клод создаст папку и переместит в нее файлы изображений.

### Как работает процесс утверждения

Перед выполнением любой операции с файловой системой Клод запросит ваше подтверждение. Это гарантирует, что вы сохраняете контроль над всеми действиями:

<Frame style={{ textAlign: "center" }}>
  <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-approve.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=98cc6e9dfe885fbd6e9bfae40601e494" width="500" alt="Клод запрашивает разрешение на выполнение операции с файлом" data-og-width="962" data-og-height="464" data-path="images/quickstart-approve.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-approve.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=d5ab1456f7728dcf93652b6542377ca3 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-approve.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=06809ba885f94726178efefed355395c 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-approve.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=a437dd1dd46c0d7cae1767f846eb100a 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-approve.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=d4323361de72398163de4500fd398cf3 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-approve.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=b7f5117fb238e9e7e455b58e1637cca1 1650 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-approve.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=ab48fb927eaaf919c5ccf063a958bab6 2500 Вт" />
</Frame>

Внимательно изучите каждый запрос перед его одобрением. Вы всегда можете отклонить запрос, если вас не устраивает предложенное действие.

## Поиск неисправностей

Если у вас возникли проблемы с настройкой или использованием файлового сервера, следующие решения помогут устранить распространенные неполадки:

<AccordionGroup>
  <Заголовок аккордеона: Сервер не отображается в Claude / отсутствует значок молотка">
    1. Полностью перезагрузите рабочий стол Клода.
    2. Проверьте синтаксис файла `claude_desktop_config.json`.
    3. Убедитесь, что пути к файлам, указанные в `claude_desktop_config.json`, действительны и являются абсолютными, а не относительными.
    4. Просмотрите [логи](#получение-логов-из-claude-for-desktop), чтобы узнать, почему сервер не подключается.
    5. Попробуйте вручную запустить сервер в командной строке (заменив `username`, как вы это сделали в `claude_desktop_config.json`), чтобы проверить, не возникнут ли какие-либо ошибки:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      npx -y @modelcontextprotocol/server-filesystem /Users/username/Desktop /Users/username/Downloads
      ```

      ```Тема Windows PowerShell={null}
      npx -y @modelcontextprotocol/server-filesystem C:\Users\username\Desktop C:\Users\username\Downloads
      ```
    </CodeGroup>
  </Аккордеон>

  <Заголовок аккордеона="Получение журналов из Claude Desktop">
    Логи приложения Claude.app, связанные с MCP, записываются в файлы журналов по следующим адресам:

    * macOS: `~/Library/Logs/Claude`

    * Windows: `%APPDATA%\Claude\logs`

    * Файл `mcp.log` будет содержать общие сведения о соединениях MCP и сбоях соединения.

    * Файлы с именем `mcp-server-SERVERNAME.log` будут содержать сообщения об ошибках (stderr) с указанного сервера.

    Для просмотра последних записей в логах и отслеживания новых (в Windows будут отображаться только последние записи) можно выполнить следующую команду:

    <CodeGroup>
      ```bash macOS/Linux theme={null}
      tail -n 20 -f ~/Library/Logs/Claude/mcp*.log
      ```

      ```Тема Windows PowerShell={null}
      тип "%APPDATA%\Claude\logs\mcp*.log"
      ```
    </CodeGroup>
  </Аккордеон>

  <Заголовок аккордеона: "Сбои при вызовах инструментов происходят незаметно">
    Если Клод попытается использовать инструменты, но они окажутся неэффективными:

    1. Проверьте журналы Клода на наличие ошибок.
    2. Убедитесь, что ваш сервер собирается и работает без ошибок.
    3. Попробуйте перезапустить Claude Desktop.
  </Аккордеон>

  <Заголовок аккордеона: Ничего из этого не работает. Что мне делать?">
    Для получения более совершенных инструментов отладки и подробных инструкций обратитесь к нашему [руководству по отладке](/legacy/tools/debugging).
  </Аккордеон>

  <Заголовок аккордеона="Ошибка ENOENT и `${APPDATA}` в путях в Windows">
    Если настроенный вами сервер не загружается, и в его логах вы видите ошибку, ссылающуюся на `${APPDATA}` в пути, вам может потребоваться добавить расширенное значение `%APPDATA%` в ключ `env` в файле `claude_desktop_config.json`:

    ```json theme={null}
    {
      "brave-search": {
        "команда": "npx",
        "args": ["-y", "@modelcontextprotocol/server-brave-search"],
        "env": {
          "APPDATA": "C:\\Users\\user\\AppData\\Roaming\\",
          "BRAVE_API_KEY": "..."
        }
      }
    }
    ```

    После внесения этих изменений запустите Claude Desktop еще раз.

    <Предупреждение>
      **npm следует установить глобально.**

      Команда `npx` может продолжать завершаться с ошибкой, если вы не установили npm глобально. Если npm уже установлен глобально, вы обнаружите, что `%APPDATA%\npm` существует в вашей системе. В противном случае вы можете установить npm глобально, выполнив следующую команду:

      ```bash theme={null}
      npm install -g npm
      ```
    </Предупреждение>
  </Аккордеон>
</AccordionGroup>

## Следующие шаги

Теперь, когда вы успешно подключили Claude Desktop к локальному серверу MCP, изучите следующие варианты расширения вашей конфигурации:

<CardGroup cols={2}>
  <Card title="Explore other servers" icon="grid" href="https://github.com/modelcontextprotocol/servers">
    Просмотрите нашу коллекцию официальных и созданных сообществом серверов MCP для
    дополнительные возможности
  </Карточка>

  <Card title="Создайте свой собственный сервер" icon="code" href="/docs/develop/build-server">
    Создавайте пользовательские MCP-серверы, адаптированные под ваши конкретные рабочие процессы.
    интеграции
  </Карточка>

  <Card title="Подключение к удаленным серверам" icon="cloud" href="/docs/develop/connect-remote-servers">
    Узнайте, как подключить Клода к удаленным серверам MCP для использования облачных инструментов.
    услуги
  </Карточка>

  <Card title="Understand the protocol" icon="book" href="/docs/learn/architecture">
    Узнайте больше о том, как работает MCP и его архитектуре.
  </Карточка>
</CardGroup>