> ## Индекс документации
Полный индекс документации доступен по адресу: https://modelcontextprotocol.io/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Подключение к удаленным серверам MCP

Узнайте, как подключить Claude к удаленным серверам MCP и расширить его возможности с помощью инструментов и источников данных, размещенных в интернете.

Удаленные серверы MCP расширяют возможности приложений ИИ за пределы вашей локальной среды, предоставляя доступ к размещенным в интернете инструментам, сервисам и источникам данных. Подключаясь к удаленным серверам MCP, вы превращаете помощников ИИ из полезных инструментов в компетентных членов команды, способных справляться со сложными многоэтапными проектами, имея доступ к внешним ресурсам в режиме реального времени.

В настоящее время многие клиенты поддерживают удаленные MCP-серверы, что открывает широкий спектр возможностей интеграции. В этом руководстве показано, как подключиться к удаленным MCP-серверам, используя в качестве примера [Claude](https://claude.ai/), один из [многих клиентов, поддерживающих MCP](/clients). Хотя мы сосредоточимся на реализации Claude через пользовательские коннекторы, эти концепции в целом применимы и к другим MCP-совместимым клиентам.

## Понимание работы удаленных MCP-серверов

Удаленные MCP-серверы функционируют аналогично локальным MCP-серверам, но размещаются в интернете, а не на вашем локальном компьютере. Они предоставляют инструменты, подсказки и ресурсы, которые Клод может использовать для выполнения задач от вашего имени. Эти серверы могут интегрироваться с различными сервисами, такими как инструменты управления проектами, системы документации, репозитории кода и любые другие сервисы с поддержкой API.

Ключевое преимущество удалённых серверов MCP — их доступность. В отличие от локальных серверов, требующих установки и настройки на каждом устройстве, удалённые серверы доступны с любого клиента MCP, имеющего подключение к интернету. Это делает их идеальными для веб-приложений на основе ИИ, интеграций, ориентированных на простоту использования, и сервисов, требующих обработки на стороне сервера или аутентификации.

## Что такое пользовательские коннекторы?

Пользовательские коннекторы служат мостом между Claude и удаленными серверами MCP. Они позволяют напрямую подключать Claude к инструментам и источникам данных, наиболее важным для ваших рабочих процессов, что дает возможность Claude работать в рамках вашего любимого программного обеспечения и извлекать полезную информацию из полного контекста ваших внешних инструментов.

С помощью пользовательских коннекторов вы можете:

* [Подключение Клода к существующим удаленным серверам MCP](https://support.anthropic.com/en/articles/11175166-getting-started-with-custom-connectors-using-remote-mcp), предоставляемым сторонними разработчиками
* [Создавайте собственные удаленные MCP-серверы для подключения к любому инструменту](https://support.anthropic.com/en/articles/11503834-building-custom-connectors-via-remote-mcp-servers)

## Подключение к удаленному серверу MCP

Процесс подключения Claude к удаленному серверу MCP включает в себя добавление пользовательского коннектора через [интерфейс Claude](https://claude.ai/). Это устанавливает защищенное соединение между Claude и выбранным вами удаленным сервером.

<Шаги>
  <Заголовок шага: Перейдите к настройкам коннектора">
    Откройте Claude в браузере и перейдите на страницу настроек. Для этого нажмите на значок своего профиля и выберите «Настройки» в выпадающем меню. В настройках найдите и нажмите на раздел «Коннекторы» на боковой панели.

    Здесь отобразятся ваши текущие настроенные коннекторы и будут предоставлены параметры для добавления новых.
  </Шаг>

  <Заголовок шага="Добавить пользовательский коннектор">
    В разделе «Коннекторы» прокрутите страницу вниз, где вы найдете кнопку «Добавить пользовательский коннектор». Нажмите эту кнопку, чтобы начать процесс подключения.

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/1-add-connector.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=b5ae9b23164875bbaa3aff4c178cdc64" alt="Добавить кнопку пользовательского коннектора в настройках Claude" data-og-width="1038" width="1038" data-og-height="809" height="809" data-path="images/quickstart-remote/1-add-connector.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/1-add-connector.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=df494c13492290da8cbf33320405bc60 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/1-add-connector.png ?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=a2dce224fb5e1636218ea2806962c89f 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/1-add-connector.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=de18294dd3cad23989c04cedbacff74f 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/1-add-connector.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c55cb3531701df2b5dfd721dcd3f48dc 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/1-add-connector.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=b0d3e56c4c445ba6896d49997dcdf2c0 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/1-add-connector.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=9d83f4f2db7441a39ff8733d97243ab9 2500w" />
    </Frame>

    Появится диалоговое окно с запросом на ввод URL-адреса удаленного MCP-сервера. Этот URL-адрес должен быть предоставлен разработчиком или администратором сервера. Введите полный URL-адрес, убедившись, что он включает правильный протокол (https\://) и все необходимые компоненты пути.

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/2-connect.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=0934f16d8e016cade8e560c8f89d011b" alt="Диалоговое окно для ввода URL-адреса удаленного MCP-сервера" data-og-width="1616" width="1616" data-og-height="282" height="282" data-path="images/quickstart-remote/2-connect.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/2-connect.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=e3d7318b0b8e691d25e1887e80200b60 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/2-connect.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=be3edc7b361eecaabf688c2058b5e466 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/2-connect.png?w= 840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=31be86114b31e1c5e813d92a4c0cb1c3 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/2-connect.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=15b6cd3819fabd3655a52b930d384b51 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/2-connect.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=5ef180101a7fb0901f7ecf1b5efd254f 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/2-connect.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=c024f625ec6ee3f7959513ba15adf524 2500 Вт" />
    </Frame>

    После ввода URL-адреса нажмите «Добавить», чтобы продолжить подключение.
  </Шаг>

  <Шаг title="Завершение аутентификации">
    Большинство удалённых серверов MCP требуют аутентификации для обеспечения безопасного доступа к своим ресурсам. Процесс аутентификации варьируется в зависимости от реализации сервера, но обычно включает OAuth, ключи API или комбинации имени пользователя и пароля.

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/3-auth.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=89af6e1b85718637231388697cc7b015" alt="Экран аутентификации для удаленного сервера MCP" data-og-width="490" width="490" data-og-height="806" height="806" data-path="images/quickstart-remote/3-auth.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/3-auth.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=cde1e30b4c3b99b5edc5575c5958e9e7 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/3-auth.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=e2cef2daadce577ce335949d3f425257 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/3-auth.png?w=8 40&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=4e06599391ebf6bcb521cb4000469844 840 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/3-auth.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=e78e71303fd5bb7d1e5c1602dca7641b 1100 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/3-auth.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=2e49d390bddf2a37fef4cba409e9950f 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/3-auth.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=47ec70901a76a3209267b2078f9f8011 2500w" />
    </Frame>

    Следуйте инструкциям по аутентификации, предоставленным сервером. Это может перенаправить вас к стороннему поставщику услуг аутентификации или отобразить форму внутри Claude. После завершения аутентификации Claude установит защищенное соединение с удаленным сервером.
  </Шаг>

  <Заголовок шага="Доступ к ресурсам и подсказкам">
    После успешного подключения ресурсы и подсказки удаленного сервера станут доступны в ваших диалогах с Клодом. Вы можете получить к ним доступ, щелкнув значок скрепки в области ввода сообщения, который открывает меню вложений.

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/4-select-resources-menu.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=ecc6234b0fe5625e24cc2b02b7893c67" alt="Меню вложений, показывающее доступные ресурсы" data-og-width="735" width="735" data-og-height="666" height="666" data-path="images/quickstart-remote/4-select-resources-menu.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/4-select-resources-menu.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=6e853446286f2c2caf1c7137e4293db4 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/4-select-resources-menu .png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7c3c5b7d2f8d078bc263b0603a4136d1 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/4-select-resources-menu.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=280e1d1547925f73f33fcf404eac5ba2 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/4-select-resources-menu.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=00fc5842c2d6592f41f96c2051b016e2 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/4-select-resources-menu.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=505d4ec95d83f4e52cf9c60780b225fe 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/4-select-resources-menu.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=07178c22a89472b962639854dc029953 2500w" />
    </Frame>

    В меню отображаются все доступные ресурсы и подсказки с подключенных серверов. Выберите элементы, которые хотите включить в разговор. Эти ресурсы предоставляют Клоду контекст и информацию из ваших внешних инструментов.

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/5-select-prompts-resources.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=30c522540c7ff5abd8617d20b329eca2" alt="Выбор конкретных ресурсов и подсказок из меню" data-og-width="648" width="648" data-og-height="920" height="920" data-path="images/quickstart-remote/5-select-prompts-resources.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/5-select-prompts-resources.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7361585026d3dd1f0c218232ce475d59 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/5-select-prompts-resourcec es.png?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=eb5162947ac8110569225e4ff36ac54c 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/5-select-prompts-resources.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=93b0b1de76b11785deb6cd2b8bbbb33e 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/5-select-prompts-resources.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=19d1f1de9b7b38dff6fabaea260fc700 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/5-select-prompts-resources.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=587ee6b0f0831f7b9c827db58e4c53a6 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/5-select-prompts-resources.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=a875a3599b478977e1322c07b82a5879 2500w" />
    </Frame>
  </Шаг>

  <Заголовок шага: Настройка разрешений для инструментов">
    Удаленные MCP-серверы часто предоставляют доступ к нескольким инструментам с различными возможностями. Вы можете контролировать, какие инструменты Клод может использовать, настроив права доступа в параметрах коннектора. Это гарантирует, что Клод будет выполнять только те действия, которые вы явно разрешили.

    <Рамка>
      <img src="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/6-configure-tools.png?fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=1e55fd2f7da85150bfcf9dfbd7a31f44" alt="Интерфейс конфигурации разрешений инструментов" data-og-width="604" width="604" data-og-height="745" height="745" data-path="images/quickstart-remote/6-configure-tools.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/6-configure-tools.png?w=280&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=6ece557353a2b8227cfc033ee7533fbc 280w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/6-configure-tools.pn g?w=560&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=aa954f4a018077d6a4a3c9406cdd4a63 560 Вт, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/6-configure-tools.png?w=840&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=309fd1583dd23081ed93eca4fb85c5e0 840w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/6-configure-tools.png?w=1100&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=8b7ea5b326ea5cf8947e9b9aba28f2f7 1100w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/6-configure-tools.png?w=1650&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=7e02024cdcae2b7c41aab3d5c4f4e75e 1650w, https://mintcdn.com/mcp/4ZXF1PrDkEaJvXpn/images/quickstart-remote/6-configure-tools.png?w=2500&fit=max&auto=format&n=4ZXF1PrDkEaJvXpn&q=85&s=f953404ab1cb149e160eaa139c53d701 2500w" />
    </Frame>

    Вернитесь в настройки коннекторов и щелкните по подключенному серверу. Здесь вы можете включить или отключить определенные инструменты, установить ограничения на использование и настроить другие параметры безопасности в соответствии с вашими потребностями.
  </Шаг>
</Шаги>

## Рекомендации по использованию удалённых серверов MCP

При работе с удаленными серверами MCP учитывайте следующие рекомендации для обеспечения безопасной и эффективной работы:

**Вопросы безопасности**: Всегда проверяйте подлинность удаленных серверов MCP перед подключением. Подключайтесь только к серверам из надежных источников и проверяйте запрашиваемые разрешения во время аутентификации. Будьте осторожны при предоставлении доступа к конфиденциальным данным или системам.

**Управление несколькими коннекторами**: Вы можете одновременно подключаться к нескольким удаленным серверам MCP. Организуйте свои коннекторы по назначению или проекту для поддержания порядка. Регулярно проверяйте и удаляйте коннекторы, которые вы больше не используете, чтобы поддерживать порядок и безопасность в рабочем пространстве.

## Следующие шаги

Теперь, когда вы подключили Клода к удаленному серверу MCP, вы можете изучить его возможности в своих беседах. Попробуйте использовать подключенные инструменты для автоматизации задач, доступа к внешним данным или интеграции с существующими рабочими процессами.

<CardGroup cols={2}>
  <Card title="Создайте свой собственный удаленный сервер" icon="cloud" href="https://support.anthropic.com/en/articles/11503834-building-custom-connectors-via-remote-mcp-servers">
    Создавайте собственные удалённые MCP-серверы для интеграции с проприетарными инструментами и
    услуги
  </Карточка>

  <Card title="Explore available servers" icon="grid" href="https://github.com/modelcontextprotocol/servers">
    Ознакомьтесь с нашей коллекцией официальных и созданных сообществом серверов MCP.
  </Карточка>

  <Card title="Подключение к локальным серверам" icon="computer" href="/docs/develop/connect-local-servers">
    Узнайте, как подключить Claude Desktop к локальным серверам MCP для прямого доступа к системе.
    доступ
  </Карточка>

  <Card title="Understand the architecture" icon="book" href="/docs/learn/architecture">
    Узнайте больше о том, как работает MCP и его архитектуре.
  </Карточка>
</CardGroup>

Удаленные серверы MCP открывают широкие возможности для расширения функционала Claude. По мере освоения этих интеграций вы откроете для себя новые способы оптимизации рабочих процессов и более эффективного выполнения сложных задач.