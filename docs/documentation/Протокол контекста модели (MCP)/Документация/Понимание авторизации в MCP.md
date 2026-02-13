> ## Индекс документации
Полный индекс документации доступен по адресу: https://modelcontextprotocol.io/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Понимание авторизации в MCP

Узнайте, как реализовать безопасную авторизацию для серверов MCP с использованием OAuth 2.1 для защиты конфиденциальных ресурсов и операций.

Авторизация в протоколе контекстной модели (MCP) обеспечивает безопасный доступ к конфиденциальным ресурсам и операциям, предоставляемым серверами MCP. Если ваш сервер MCP обрабатывает пользовательские данные или административные действия, авторизация гарантирует, что доступ к его конечным точкам смогут получить только авторизованные пользователи.

MCP использует стандартизированные потоки авторизации для построения доверия между клиентами MCP и серверами MCP. Его архитектура не фокусируется на какой-либо конкретной системе авторизации или идентификации, а скорее следует соглашениям, изложенным для [OAuth 2.1](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13). Для получения подробной информации см. [спецификацию авторизации](/specification/latest/basic/authorization).

## Когда следует использовать авторизацию?

Хотя авторизация на серверах MCP является **необязательной**, она настоятельно рекомендуется в следующих случаях:

* Ваш сервер получает доступ к данным, специфичным для каждого пользователя (электронная почта, документы, базы данных).
* Необходимо провести аудит того, кто какие действия выполнял.
* Ваш сервер предоставляет доступ к своим API, для использования которых требуется согласие пользователя.
* Вы разрабатываете решение для корпоративных сред со строгим контролем доступа.
* Вы хотите внедрить ограничение скорости запросов или отслеживание использования для каждого пользователя.

<Совет>
  **Авторизация для локальных серверов MCP**

  Для MCP-серверов, использующих транспорт [STDIO](/specification/latest/basic/transports#stdio), можно использовать учетные данные, основанные на окружении, или учетные данные, предоставляемые сторонними библиотеками, встроенными непосредственно в MCP-сервер. Поскольку MCP-сервер, использующий STDIO, работает локально, он имеет доступ к ряду гибких вариантов получения учетных данных пользователя, которые могут зависеть или не зависеть от процессов аутентификации и авторизации в браузере.

  В свою очередь, потоки OAuth предназначены для HTTP-транспорта, где сервер MCP размещен удаленно, а клиент использует OAuth для подтверждения авторизации пользователя на доступ к указанному удаленному серверу.
</Совет>

## Процесс авторизации: пошаговая инструкция

Давайте рассмотрим, что происходит, когда клиент пытается подключиться к вашему защищенному MCP-серверу:

<Шаги>
  <Шаг title="Первоначальное рукопожатие">
    Когда ваш MCP-клиент впервые пытается подключиться, ваш сервер отвечает ошибкой `401 Unauthorized` и сообщает клиенту, где найти информацию об авторизации, содержащуюся в документе [Protected Resource Metadata (PRM)](https://datatracker.ietf.org/doc/html/rfc9728). Этот документ размещается на MCP-сервере, имеет предсказуемый путь и предоставляется клиенту в параметре `resource_metadata` в заголовке `WWW-Authenticate`.

    ```http theme={null}
    HTTP/1.1 401 Несанкционированный доступ
    WWW-Authenticate: Bearer realm="mcp",
      resource_metadata="https://your-server.com/.well-known/oauth-protected-resource"
    ```

    Это сообщает клиенту, что для работы с сервером MCP требуется авторизация, и указывает, где получить необходимую информацию для запуска процесса авторизации.
  </Шаг>

  <Шаг title="Обнаружение метаданных защищенных ресурсов">
    Используя URI-указатель на документ PRM, клиент получает метаданные, чтобы узнать об авторизационном сервере, поддерживаемых областях действия и другой информации о ресурсах. Данные обычно инкапсулированы в JSON-объект, подобный приведенному ниже.

    ```json theme={null}
    {
      "ресурс": "https://your-server.com/mcp",
      "authorization_servers": ["https://auth.your-server.com"],
      "scopes_supported": ["mcp:tools", "mcp:resources"]
    }
    ```

    Более подробный пример можно найти в [разделе 3.2 RFC 9728](https://datatracker.ietf.org/doc/html/rfc9728#name-protected-resource-metadata-r).
  </Шаг>

  <Заголовок шага="Обнаружение сервера авторизации">
    Далее клиент узнает, что может делать сервер авторизации, получив его метаданные. Если в документе PRM указано более одного сервера авторизации, клиент может выбрать, какой из них использовать.

    После выбора сервера авторизации клиент сформирует стандартный URI метаданных и отправит запрос к конечным точкам [OpenID Connect (OIDC) Discovery](https://openid.net/specs/openid-connect-discovery-1_0.html) или [OAuth 2.0 Auth Server Metadata](https://datatracker.ietf.org/doc/html/rfc8414) (в зависимости от поддержки сервера авторизации).
    и получить еще один набор метаданных, которые позволят определить конечные точки, необходимые для завершения процесса авторизации.

    ```json theme={null}
    {
      "issuer": "https://auth.your-server.com",
      "authorization_endpoint": "https://auth.your-server.com/authorize",
      "token_endpoint": "https://auth.your-server.com/token",
      "registration_endpoint": "https://auth.your-server.com/register"
    }
    ```
  </Шаг>

  <Шаг title="Регистрация клиента">
    После обработки всех метаданных клиенту необходимо убедиться, что он зарегистрирован на сервере авторизации. Это можно сделать двумя способами.

    Во-первых, клиент может быть **предварительно зарегистрирован** на данном сервере авторизации, в этом случае в него может быть встроена информация о регистрации клиента, которая используется для завершения процесса авторизации.

    В качестве альтернативы клиент может использовать **динамическую регистрацию клиента** (DCR) для динамической регистрации на сервере авторизации. Последний сценарий требует, чтобы сервер авторизации поддерживал DCR. Если сервер авторизации поддерживает DCR, клиент отправит запрос на `registration_endpoint` со своей информацией:

    ```json theme={null}
    {
      "client_name": "Мой клиент MCP",
      "redirect_uris": ["http://localhost:3000/callback"],
      "grant_types": ["authorization_code", "refresh_token"],
      "response_types": ["code"]
    }
    ```

    В случае успешной регистрации сервер авторизации вернет JSON-объект с информацией о регистрации клиента.

    <Совет>
      **Без регистрации в DCR и предварительной регистрации**

      В случае, если клиент MCP подключается к серверу MCP, который не использует сервер авторизации, поддерживающий DCR, и клиент не предварительно зарегистрирован на указанном сервере авторизации, ответственность за предоставление конечному пользователю возможности вводить информацию о клиенте вручную лежит на разработчике клиента.
    </Совет>
  </Шаг>

  <Шаг title="Авторизация пользователя">
    Теперь клиенту необходимо открыть в браузере конечную точку `/authorize`, где пользователь сможет войти в систему и предоставить необходимые разрешения. Затем сервер авторизации перенаправит клиента обратно с кодом авторизации, который клиент обменяет на токены:

    ```json theme={null}
    {
      "access_token": "eyJhbGciOiJSUzI1NiIs...",
      "refresh_token": "def502...",
      "token_type": "Bearer",
      "expires_in": 3600
    }
    ```

    Токен доступа — это токен, который клиент будет использовать для аутентификации запросов к серверу MCP. Этот шаг соответствует стандартным соглашениям [кода авторизации OAuth 2.1 с PKCE](https://oauth.net/2/grant-types/authorization-code/).
  </Шаг>

  <Шаг title="Выполнение аутентифицированных запросов">
    Наконец, клиент может отправлять запросы на ваш MCP-сервер, используя токен доступа, встроенный в заголовок `Authorization`:

    ```http theme={null}
    GET /mcp HTTP/1.1
    Хостинг: your-server.com
    Авторизация: Предъявитель eyJhbGciOiJSUzI1NiIs...
    ```

    Сервер MCP должен будет проверить токен и обработать запрос, если токен действителен и обладает необходимыми правами доступа.
  </Шаг>
</Шаги>

## Пример реализации

Для начала практической реализации мы будем использовать сервер авторизации [Keycloak](https://www.keycloak.org/), размещенный в контейнере Docker. Keycloak — это сервер авторизации с открытым исходным кодом, который легко развернуть локально для тестирования и экспериментов.

Убедитесь, что вы скачали и установили [Docker Desktop](https://www.docker.com/products/docker-desktop/). Он понадобится нам для развертывания Keycloak на нашей машине для разработки.

### Настройка Keycloak

Для запуска контейнера Keycloak выполните следующую команду в терминале:

```bash theme={null}
docker run -p 127.0.0.1:8080:8080 -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=admin quay.io/keycloak/keycloak start-dev
```

Эта команда загрузит образ контейнера Keycloak локально и инициализирует базовую конфигурацию. Она будет запущена на порту `8080` и будет иметь пользователя `admin` с паролем `admin`.

<Предупреждение>
  **Не для производства**

  Приведенная выше конфигурация может подойти для тестирования и экспериментов; однако ее никогда не следует использовать в производственной среде. Для получения дополнительной информации о развертывании сервера авторизации для сценариев, требующих надежности, безопасности и высокой доступности, обратитесь к руководству [Настройка Keycloak для производственной среды](https://www.keycloak.org/server/configuration-production).
</Предупреждение>

Вы сможете получить доступ к серверу авторизации Keycloak из своего браузера по адресу `http://localhost:8080`.

<Рамка>
  <img src="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-browser.png?fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=cba689d986e113cbe937d732ac0558b6" alt="Диалоговое окно аутентификации в панели администратора Keycloak." data-og-width="1834" width="1834" data-og-height="1450" height="1450" data-path="images/tutorial-authorization/keycloak-browser.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-browser.png?w=280&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=6f32c1c9aa75a0533213ef708e0486f9 280w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-browser.png?w=560&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=a93c454733e5d23dea996ac4243b5ba7 560 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-browser.png?w=840&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=08f456b670f8c07ec91489abd44e1102 840 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-browser.png?w=1100&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=6f38eebb04db868078b62adc377c673d 1100w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-browser.png?w=1650&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=5e6ab1e9d62b82781152096fe6ee4c62 1650w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-browser.png?w=2500&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=26faaf97617cb789b0492ea580245dc0 2500w" />
</Frame>

При использовании конфигурации по умолчанию Keycloak уже поддерживает многие возможности, необходимые для серверов MCP, включая динамическую регистрацию клиентов. Вы можете проверить это, посмотрев конфигурацию OIDC, доступную по адресу:

```http theme={null}
http://localhost:8080/realms/master/.well-known/openid-configuration
```

Нам также потребуется настроить Keycloak для поддержки наших областей действия и разрешить нашему хосту (локальной машине) динамически регистрировать клиентов, поскольку политики по умолчанию ограничивают анонимную динамическую регистрацию клиентов.

Перейдите в раздел **Области доступа клиента** на панели управления Keycloak и создайте новую область доступа `mcp:tools`. Мы будем использовать её для доступа ко всем инструментам на нашем сервере MCP.

<Рамка>
  <img src="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-scopes.png?fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=3cd49dc2e070027609ae495751e0db58" alt="Настройка областей действия Keycloak." data-og-width="1999" width="1999" data-og-height="1710" height="1710" data-path="images/tutorial-authorization/keycloak-scopes.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-scopes.png?w=280&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=63647c72d96cc867eff23f6f193c97a3 280w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-scopes.png?w=560&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=d28690bb063e22a3f677c23df8a338bf 560 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-scopes.png?w=840&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=4e9dc9972f1449f20c2a5559fbfdde06 840 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-scopes.png?w=1100&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=b3a21b321612781d41ab018fcd19bca0 1100w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-scopes.png?w=1650&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=345993151f644fe6aca724a605c168f6 1650w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-scopes.png?w=2500&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=ac6152d64434b7cf8a8e74a4128b0f4f 2500w" />
</Frame>

После создания области действия убедитесь, что вы присвоили ей тип **По умолчанию** и включили переключатель **Включить в область действия токена**, поскольку это потребуется для проверки токена.

Теперь давайте также настроим **аудиторию** для наших токенов, выданных Keycloak. Настройка аудитории важна, поскольку она напрямую встраивает предполагаемое место назначения в выданный токен доступа. Это помогает вашему MCP-серверу убедиться, что полученный токен действительно предназначен для него, а не для какого-либо другого API. Это ключевой момент для предотвращения сценариев сквозной передачи токенов.

Для этого откройте область действия клиента `mcp:tools` и нажмите **Mappers**, затем **Configure a new mapper**. Выберите **Audience**.

<Рамка>
  <img src="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/scope-add-audience.gif?s=6ea9cf20c397f4c79c491c2e39019272" alt="Настройка аудитории для токена в Keycloak." data-og-width="1080" width="1080" data-og-height="921" height="921" data-path="images/tutorial-authorization/scope-add-audience.gif" data-optimize="true" data-opv="3" />
</Frame>

Для поля **Имя** используйте `audience-config`. Добавьте значение для **Включенная пользовательская аудитория**, установив его на `http://localhost:3000`. Это будет URI нашего тестового сервера.

<Предупреждение>
  **Не для производства**

  Приведенная выше конфигурация аудитории предназначена для тестирования. Для производственных сценариев потребуется дополнительная настройка и конфигурация, чтобы обеспечить надлежащее ограничение аудитории для выпущенных токенов. В частности, аудитория должна основываться на параметре ресурса, передаваемом от клиента, а не на фиксированном значении.
</Предупреждение>

Теперь перейдите в раздел **Клиенты**, затем **Регистрация клиентов** и **Доверенные хосты**. Отключите параметр **Объекты URI должны совпадать** и добавьте хосты, с которых вы проводите тестирование. Вы можете получить текущий IP-адрес хоста, выполнив команду `ifconfig` в Linux или macOS, или `ipconfig` в Windows. Вы можете увидеть IP-адрес, который необходимо добавить, просмотрев логи Keycloak и найдя строку, похожую на `Failed to verify remote host : 192.168.215.1`. Убедитесь, что IP-адрес связан с вашим хостом. В зависимости от вашей конфигурации Docker, это может быть мостовая сеть.

<Рамка>
  <img src="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-client.gif?s=b5d40b36a5f1ea1e818821bb8ea77f6b" alt="Настройка данных регистрации клиента в Keycloak." data-og-width="1199" width="1199" data-og-height="1027" height="1027" data-path="images/tutorial-authorization/keycloak-client.gif" data-optimize="true" data-opv="3" />
</Frame>

<Предупреждение>
  **Как найти организатора**

  Если вы запускаете Keycloak из контейнера, вы также сможете увидеть IP-адрес хоста в логах контейнера через терминал.
</Предупреждение>

Наконец, нам нужно зарегистрировать новый клиент, который мы сможем использовать с самим **сервером MCP** для взаимодействия с Keycloak, например, для [проверки токенов](https://oauth.net/2/token-introspection/). Для этого:

1. Перейдите в раздел **Клиенты**.
2. Нажмите **Создать клиента**.
3. Присвойте клиенту уникальный **идентификатор клиента** и нажмите **Далее**.
4. Включите **аутентификацию клиента** и нажмите **Далее**.
5. Нажмите **Сохранить**.

Стоит отметить, что интроспекция токенов — это лишь *один* из доступных подходов к проверке токенов. Это также можно сделать с помощью отдельных библиотек, специфичных для каждого языка и платформы.

При открытии сведений о клиенте перейдите в раздел **Учетные данные** и запишите **Секретный ключ клиента**.

<Рамка>
  <img src="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-client-auth.gif?s=7152c41a5746994fd399024bc4659e40" alt="Создание нового клиента в Keycloak." data-og-width="1200" width="1200" data-og-height="1023" height="1023" data-path="images/tutorial-authorization/keycloak-client-auth.gif" data-optimize="true" data-opv="3" />
</Frame>

<Предупреждение>
  **Секреты обращения**

  Никогда не встраивайте учетные данные клиента непосредственно в код. Мы рекомендуем использовать переменные среды или специализированные решения для хранения секретной информации.
</Предупреждение>

При правильной настройке Keycloak каждый раз при запуске процесса авторизации ваш MCP-сервер будет получать токен следующего вида:

```text theme={null}
eyJhbGciOiJSUzI1NiIsInR5cCIgOiAiSldUIiwia2lkIiA6ICI1TjcxMGw1WW5MWk13WGZ1VlJKWGtCS3ZZMzZzb3JnRG5scmlyZ2tlTHlzIn0.eyJleHAiOjE3NTU1NDA4MTcsImlhdCI6MTc1NTU0MDc1NywiYXV0aF90aW1lIjoxNzU1NTM4ODg4LCJqdGkiOiJvbnJ0YWM6YjM0MDgwZmYtODQwNC02ODY 3LTgxYmUtMTIzMWI1MDU5M2E4IiwiaXNzIjoiaHR0cDovL2xvY2FsaG9zdDo4MDgwL3JlYWxtcy9tYXN0ZXIiLCJhdWQiOiJodHRwOi8vbG9jYWxob3N0OjMwMDAiLCJzdWIiOiIzM2VkNmM2Yi1jNmUwLTQ5MjgtYTE2MS1mMmY2OWM3YTAzYjkiLCJ0eXAiOiJCZWFyZXIiLCJhenAiOiI3OTc1YTViNi04YjU 5LTRhODUtOWNiYS04ZmFlYmRhYjg5NzQiLCJzaWQiOiI4ZjdlYzI3Ni0zNThmLTRjY2MtYjMxMy1kYjA4MjkwZjM3NmYiLCJzY29wZSI6Im1jcDp0b29scyJ9.P5xCRtXORly0R0EXjyqRCUx-z3J4uAOWNAvYtLPXroykZuVCCJ-K1haiQSwbURqfsVOMbL7jiV-sD6miuPzI1tmKOkN_Yct0Vp-azvj7U5rEj7 U6tvPfMkg2Uj_jrIX0KOskyU2pVvGZ-5BgqaSvwTEdsGu_V3_E0xDuSBq2uj_wmhqiyTFm5lJ1WkM3Hnxxx1_AAnTj7iOKMFZ4VCwMmk8hhSC7clnDau ORc0sutxiJuYUZzxNiNPkmNeQtMCGqWdP1igcbWbrfnNXhJ6NswBOuRbh97_QraET3hl-CNmyS6C72Xc0aOwR_uJ7xVSBTD02OaQ1JA6kjCATz30kGYg
```

В расшифрованном виде это будет выглядеть так:

```json theme={null}
{
  "alg": "RS256",
  "typ": "JWT",
  "kid": "5N710l5YnLZMwXfuVRJXkBKvY36sorgDnlrirgkeLys"
}.{
  "exp": 1755540817,
  "iat": 1755540757,
  "auth_time": 1755538888,
  "jti": "onrtac:b34080ff-8404-6867-81be-1231b50593a8",
  "iss": "http://localhost:8080/realms/master",
  "aud": "http://localhost:3000",
  "sub": "33ed6c6b-c6e0-4928-a161-f2f69c7a03b9",
  "тип": "Носитель",
  "azp": "7975a5b6-8b59-4a85-9cba-8faebdab8974",
  "sid": "8f7ec276-358f-4ccc-b313-db08290f376f",
  "scope": "mcp:tools"
}.[Подпись]
```

<Предупреждение>
  **Встроенная аудитория**

  Обратите внимание на утверждение `aud`, встроенное в токен — в данный момент оно установлено как URI тестового MCP-сервера и определяется на основе ранее настроенной области действия. Это будет важно для проверки в нашей реализации.
</Предупреждение>

### Настройка сервера MCP

Теперь мы настроим наш MCP-сервер для использования локально работающего сервера авторизации Keycloak. В зависимости от предпочтений в языке программирования, вы можете использовать один из поддерживаемых [MCP SDK](/docs/sdk).

Для целей тестирования мы создадим предельно простой MCP-сервер, предоставляющий доступ к двум инструментам — одному для сложения и другому для умножения. Для доступа к ним серверу потребуется авторизация.

<Вкладки>
  <Tab title="TypeScript">
    Полный проект на TypeScript можно посмотреть в [репозитории примеров](https://github.com/localden/min-ts-mcp-auth).

    Перед запуском приведенного ниже кода убедитесь, что у вас есть файл `.env` со следующим содержимым:

    ```env theme={null}
    # Хост/порт сервера
    HOST=localhost
    ПОРТ=3000

    # Расположение сервера аутентификации
    AUTH_HOST=localhost
    AUTH_PORT=8080
    AUTH_REALM=master

    # Учетные данные клиента Keycloak OAuth
    OAUTH_CLIENT_ID=<ВАШ_СЕРИАЛЬНЫЙ_ИД_КЛИЕНТА_СЕРВЕРА>
    OAUTH_CLIENT_SECRET=<YOUR_SERVER_CLIENT_SECRET>
    ```

    `OAUTH_CLIENT_ID` и `OAUTH_CLIENT_SECRET` связаны с клиентским приложением MCP-сервера, которое мы создали ранее.

    В дополнение к реализации спецификации авторизации MCP, сервер, представленный ниже, также выполняет проверку токенов через Keycloak, чтобы убедиться в действительности токена, полученного от клиента. Он также реализует базовое логирование, позволяющее легко диагностировать любые проблемы.

    ```typescript theme={null}
    импортировать "dotenv/config";
    импортировать express из "express";
    import { randomUUID } from "node:crypto";
    import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
    import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
    import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
    import { z } from "zod";
    импортировать cors из "cors";
    импорт {
      mcpAuthMetadataRouter,
      getOAuthProtectedResourceMetadataUrl,
    } из "@modelcontextprotocol/sdk/server/auth/router.js";
    import { requireBearerAuth } from "@modelcontextprotocol/sdk/server/auth/middleware/bearerAuth.js";
    import { OAuthMetadata } from "@modelcontextprotocol/sdk/shared/auth.js";
    import { checkResourceAllowed } from "@modelcontextprotocol/sdk/shared/auth-utils.js";
    const CONFIG = {
      хост: process.env.HOST || "localhost",
      порт: Number(process.env.PORT) || 3000,
      аутентификация: {
        хост: process.env.AUTH_HOST || process.env.HOST || "localhost",
        порт: Number(process.env.AUTH_PORT) || 8080,
        область: process.env.AUTH_REALM || "master",
        clientId: process.env.OAUTH_CLIENT_ID || "mcp-server",
        clientSecret: process.env.OAUTH_CLIENT_SECRET || "",
      },
    };

    function createOAuthUrls() {
      const authBaseUrl = new URL(
        `http://${CONFIG.auth.host}:${CONFIG.auth.port}/realms/${CONFIG.auth.realm}/`,
      );
      возвращаться {
        эмитент: authBaseUrl.toString(),
        introspection_endpoint: new URL(
          "protocol/openid-connect/token/introspect",
          authBaseUrl,
        ).toString(),
        authorization_endpoint: new URL(
          "protocol/openid-connect/auth",
          authBaseUrl,
        ).toString(),
        token_endpoint: new URL(
          "protocol/openid-connect/token",
          authBaseUrl,
        ).toString(),
      };
    }

    function createRequestLogger() {
      return (req: any, res: any, next: any) => {
        const start = Date.now();
        res.on("finish", () => {
          const ms = Date.now() - start;
          console.log(
            `${req.method} ${req.originalUrl} -> ${res.statusCode} ${ms}ms`,
          );
        });
        следующий();
      };
    }

    const app = express();

    app.use(
      express.json({
        verify: (req: any, _res, buf) => {
          req.rawBody = buf?.toString() ?? "";
        },
      }),
    );

    app.use(
      cors({
        источник: "*",
        exposedHeaders: ["Mcp-Session-Id"],
      }),
    );

    app.use(createRequestLogger());

    const mcpServerUrl = new URL(`http://${CONFIG.host}:${CONFIG.port}`);
    const oauthUrls = createOAuthUrls();

    const oauthMetadata: OAuthMetadata = {
      ...oauthUrls,
      response_types_supported: ["code"],
    };

    const tokenVerifier = {
      verifyAccessToken: async (token: string) => {
        const endpoint = oauthMetadata.introspection_endpoint;

        если (!конечная точка) {
          console.error("[auth] no introspection endpoint in metadata");
          throw new Error("В метаданных отсутствует доступная конечная точка проверки токена");
        }

        const params = new URLSearchParams({
          жетон: жетон,
          client_id: CONFIG.auth.clientId,
        });

        if (CONFIG.auth.clientSecret) {
          params.set("client_secret", CONFIG.auth.clientSecret);
        }

        пусть ответ: Ответ;
        пытаться {
          response = await fetch(endpoint, {
            метод: "POST",
            заголовки: {
              "Content-Type": "application/x-www-form-urlencoded",
            },
            тело запроса: params.toString(),
          });
        } catch (e) {
          console.error("[auth] introspection fetch threw", e);
          бросить e;
        }

        if (!response.ok) {
          const txt = await response.text();
          console.error("[auth] introspection non-OK", { status: response.status });

          пытаться {
            const obj = JSON.parse(txt);
            console.log(JSON.stringify(obj, null, 2));
          } ловить {
            console.error(txt);
          }
          throw new Error(`Недействительный или просроченный токен: ${txt}`);
        }

        let data: any;
        пытаться {
          data = await response.json();
        } catch (e) {
          const txt = await response.text();
          console.error("[auth] failed to parse introspection JSON", {
            ошибка: Строка(e),
            тело: текст,
          });
          бросить e;
        }

        if (data.active === false) {
          throw new Error("Неактивный токен");
        }

        if (!data.aud) {
          throw new Error("Отсутствует индикатор ресурса (aud)");
        }

        const audiences: string[] = Array.isArray(data.aud) ? data.aud : [data.aud];
        const allowed = audiences.some((a) =>
          checkResourceAllowed({
            запрошенный ресурс: a,
            configuredResource: mcpServerUrl,
          }),
        );
        если (!разрешено) {
          throw new Error(
            `Ни одна из указанных аудиторий не допускается. Ожидалось ${mcpServerUrl}, получено: ${audiences.join(", ")}`,
          );
        }

        возвращаться {
          токен,
          clientId: data.client_id,
          области видимости: data.scope ? data.scope.split(" ") : [],
          expiresAt: data.exp,
        };
      },
    };
    app.use(
      mcpAuthMetadataRouter({
        oauthMetadata,
        resourceServerUrl: mcpServerUrl,
        scopesSupported: ["mcp:tools"],
        resourceName: "Демонстрационный сервер MCP",
      }),
    );

    const authMiddleware = requireBearerAuth({
      верификатор: tokenVerifier,
      requiredScopes: [],
      resourceMetadataUrl: getOAuthProtectedResourceMetadataUrl(mcpServerUrl),
    });

    const transports: { [sessionId: string]: StreamableHTTPServerTransport } = {};

    function createMcpServer() {
      const server = new McpServer({
        имя: "example-server",
        версия: "1.0.0",
      });

      server.registerTool(
        "добавлять",
        {
          заголовок: "Инструмент сложения",
          Описание: "Сложить два числа",
          inputSchema: {
            a: z.number().describe("Первое число для сложения"),
            b: z.number().describe("Второе число для сложения"),
          },
        },
        async ({ a, b }) => ({
          content: [{ type: "text", text: `${a} + ${b} = ${a + b}` }],
        }),
      );

      server.registerTool(
        "умножить",
        {
          Заголовок: "Инструмент умножения"
          описание: "Умножить два числа",
          inputSchema: {
            x: z.number().describe("Первое число для умножения"),
            y: z.number().describe("Второе число для умножения"),
          },
        },
        async ({ x, y }) => ({
          содержимое: [{ тип: "текст", текст: `${x} × ${y} = ${x * y}` }],
        }),
      );

      сервер возврата;
    }

    const mcpPostHandler = async (req: express.Request, res: express.Response) => {
      const sessionId = req.headers["mcp-session-id"] as string | undefined;
      let transport: StreamableHTTPServerTransport;

      if (sessionId && transports[sessionId]) {
        транспорт = transports[sessionId];
      } else if (!sessionId && isInitializeRequest(req.body)) {
        транспорт = new StreamableHTTPServerTransport({
          sessionIdGenerator: () => randomUUID(),
          onsessioninitialized: (sessionId) => {
            transports[sessionId] = transport;
          },
        });

        transport.onclose = () => {
          if (transport.sessionId) {
            удалить транспорты[transport.sessionId];
          }
        };

        const server = createMcpServer();
        Ожидание выполнения server.connect(transport);
      } еще {
        res.status(400).json({
          jsonrpc: "2.0",
          ошибка: {
            код: -32000,
            сообщение: "Неверный запрос: не предоставлен действительный идентификатор сессии",
          },
          id: null,
        });
        возвращаться;
      }

      await transport.handleRequest(req, res, req.body);
    };

    const handleSessionRequest = async (
      req: express.Request,
      res: express.Response,
    ) => {
      const sessionId = req.headers["mcp-session-id"] as string | undefined;
      if (!sessionId || !transports[sessionId]) {
        res.status(400).send("Неверный или отсутствующий идентификатор сессии");
        возвращаться;
      }

      const transport = transports[sessionId];
      await transport.handleRequest(req, res);
    };

    app.post("/", authMiddleware, mcpPostHandler);
    app.get("/", authMiddleware, handleSessionRequest);
    app.delete("/", authMiddleware, handleSessionRequest);

    app.listen(CONFIG.port, CONFIG.host, () => {
      console.log(`🚀 Сервер MCP работает на ${mcpServerUrl.origin}`);
      console.log(`📡 Конечная точка MCP доступна по адресу ${mcpServerUrl.origin}`);
      console.log(
        `🔐 Метаданные OAuth доступны по адресу ${getOAuthProtectedResourceMetadataUrl(mcpServerUrl)}`,
      );
    });
    ```

    При запуске сервера вы можете добавить его в свой клиент MCP, например Visual Studio Code, указав конечную точку сервера MCP.

    Для получения более подробной информации о реализации MCP-серверов в TypeScript обратитесь к [документации TypeScript SDK](https://github.com/modelcontextprotocol/typescript-sdk).
  </Tab>

  <Tab title="Python">
    Полный проект на Python можно посмотреть в [репозитории примеров](https://github.com/localden/min-py-mcp-auth).

    Для упрощения взаимодействия при авторизации в сценариях на Python мы используем [FastMCP](https://gofastmcp.com/getting-started/welcome). Многие из соглашений, касающихся авторизации, такие как конечные точки и логика проверки токенов, являются согласованными во всех языках, но некоторые предлагают более простые способы их интеграции в производственные сценарии.

    Перед написанием самого сервера необходимо настроить его конфигурацию в файле `config.py` — его содержимое полностью зависит от настроек вашего локального сервера:

    ```python theme={null}
    «Настройки конфигурации сервера аутентификации MCP».

    импорт os
    из набора текста импорт Необязательный


    class Config:
        «Класс конфигурации, загружающий данные из переменных окружения с разумными значениями по умолчанию».

        # Настройки сервера
        HOST: str = os.getenv("HOST", "localhost")
        ПОРТ: int = int(os.getenv("ПОРТ", "3000"))

        # Настройки сервера аутентификации
        AUTH_HOST: str = os.getenv("AUTH_HOST", "localhost")
        AUTH_PORT: int = int(os.getenv("AUTH_PORT", "8080"))
        AUTH_REALM: str = os.getenv("AUTH_REALM", "master")

        # Настройки клиента OAuth
        OAUTH_CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "mcp-server")
        OAUTH_CLIENT_SECRET: str = os.getenv("OAUTH_CLIENT_SECRET", "UO3rmozkFFkXr0QxPTkzZ0LMXDidIikB")

        # Настройки сервера
        MCP_SCOPE: str = os.getenv("MCP_SCOPE", "mcp:tools")
        OAUTH_STRICT: bool = os.getenv("OAUTH_STRICT", "false").lower() in ("true", "1", "yes")
        TRANSPORT: str = os.getenv("TRANSPORT", "streamable-http")

        @свойство
        def server_url(self) -> str:
            """Создать URL-адрес сервера.""
            return f"http://{self.HOST}:{self.PORT}"

        @свойство
        def auth_base_url(self) -> str:
            """Создайте базовый URL-адрес сервера аутентификации.""
            return f"http://{self.AUTH_HOST}:{self.AUTH_PORT}/realms/{self.AUTH_REALM}/"

        def validate(self) -> None:
            «Проверить конфигурацию».
            if self.TRANSPORT not in ["sse", "streamable-http"]:
                raise ValueError(f"Недопустимый транспорт: {self.TRANSPORT}. Должен быть 'sse' или 'streamable-http'")


    # Экземпляр глобальной конфигурации
    config = Config()

    ```

    Реализация сервера выглядит следующим образом:

    ```python theme={null}
    импорт даты и времени
    импорт логирования
    из набора текста импортировать Any

    from pydantic import AnyHttpUrl

    from mcp.server.auth.settings import AuthSettings
    from mcp.server.fastmcp.server import FastMCP

    from .config import config
    from .token_verifier import IntrospectionTokenVerifier

    logger = logging.getLogger(__name__)


    def create_oauth_urls() -> dict[str, str]:
        «Создание URL-адресов OAuth на основе конфигурации (в стиле Keycloak)».
        from urllib.parse import urljoin

        auth_base_url = config.auth_base_url

        возвращаться {
            "issuer": auth_base_url,
            "introspection_endpoint": urljoin(auth_base_url, "protocol/openid-connect/token/introspect"),
            "authorization_endpoint": urljoin(auth_base_url, "protocol/openid-connect/auth"),
            "token_endpoint": urljoin(auth_base_url, "protocol/openid-connect/token"),
        }


    def create_server() -> FastMCP:
        «Создайте и настройте сервер FastMCP».

        config.validate()

        oauth_urls = create_oauth_urls()

        token_verifier = IntrospectionTokenVerifier(
            introspection_endpoint=oauth_urls["introspection_endpoint"],
            server_url=config.server_url,
            client_id=config.OAUTH_CLIENT_ID,
            client_secret=config.OAUTH_CLIENT_SECRET,
        )

        приложение = FastMCP(
            name="Сервер ресурсов MCP",
            инструкции="Сервер ресурсов, проверяющий токены посредством интроспекции сервера авторизации",
            host=config.HOST,
            port=config.PORT,
            debug=True,
            streamable_http_path="/",
            token_verifier=token_verifier,
            auth=AuthSettings(
                issuer_url=AnyHttpUrl(oauth_urls["issuer"]),
                required_scopes=[config.MCP_SCOPE],
                resource_server_url=AnyHttpUrl(config.server_url),
            ),
        )

        @app.tool()
        async def add_numbers(a: float, b: float) -> dict[str, Any]:
            """
            Сложите два числа.
            Этот инструмент демонстрирует основные арифметические операции с использованием аутентификации OAuth.

            Аргументы:
                а: Первое число, которое нужно сложить
                б: Второе число для сложения
            """
            результат = a + b
            возвращаться {
                «операция»: «добавление»,
                "operand_a": a,
                "operand_b": b,
                "результат": результат,
                "timestamp": datetime.datetime.now().isoformat()
            }

        @app.tool()
        async def multiply_numbers(x: float, y: float) -> dict[str, Any]:
            """
            Перемножьте два числа.
            Этот инструмент демонстрирует основные арифметические операции с использованием аутентификации OAuth.

            Аргументы:
                x: Первое число, которое нужно умножить
                y: Второе число, которое нужно умножить.
            """
            результат = x * y
            возвращаться {
                «Операция»: «умножение»,
                "operand_x": x,
                "operand_y": y,
                "результат": результат,
                "timestamp": datetime.datetime.now().isoformat()
            }

        вернуть приложение


    def main() -> int:
        """
        Запустите сервер ресурсов MCP.

        Этот сервер:
        — Предоставляет защищенные метаданные ресурсов согласно RFC 9728.
        - Проверяет токены посредством интроспекции сервера авторизации.
        - Обслуживает инструменты MCP, требующие аутентификации.

        Конфигурация загружается из файла config.py и переменных окружения.
        """
        logging.basicConfig(level=logging.INFO)

        пытаться:
            config.validate()
            oauth_urls = create_oauth_urls()

        except ValueError as e:
            logger.error("Ошибка конфигурации: %s", e)
            вернуть 1

        пытаться:
            mcp_server = create_server()

            logger.info("Запуск сервера MCP на %s:%s", config.HOST, config.PORT)
            logger.info("Сервер авторизации: %s", oauth_urls["issuer"])
            logger.info("Транспорт: %s", config.TRANSPORT)

            mcp_server.run(transport=config.TRANSPORT)
            вернуть 0

        за исключением исключения:
            logger.exception("Ошибка сервера")
            вернуть 1


    если __name__ == "__main__":
        exit(main())
    ```

    Наконец, логика проверки токенов полностью делегирована файлу `token_verifier.py`, что гарантирует возможность использования конечной точки интроспекции Keycloak для проверки действительности любых учетных данных.

    ```python theme={null}
    «Реализация верификатора токенов с использованием интроспекции токенов OAuth 2.0 (RFC 7662)».

    импорт логирования
    из набора текста импортировать Any

    from mcp.server.auth.provider import AccessToken, TokenVerifier
    from mcp.shared.auth_utils import check_resource_allowed, resource_url_from_server_url

    logger = logging.getLogger(__name__)


    class IntrospectionTokenVerifier(TokenVerifier):
        «Проверщик токенов, использующий интроспекцию токенов OAuth 2.0 (RFC 7662).»
        """

        def __init__(
            себя,
            introspection_endpoint: str,
            server_url: str,
            client_id: str,
            client_secret: str,
        ):
            self.introspection_endpoint = introspection_endpoint
            self.server_url = server_url
            self.client_id = client_id
            self.client_secret = client_secret
            self.resource_url = resource_url_from_server_url(server_url)

        async def verify_token(self, token: str) -> AccessToken | None:
            «Проверка токена через конечную точку интроспекции».
            импорт httpx

            if not self.introspection_endpoint.startswith(("https://", "http://localhost", "http://127.0.0.1")):
                вернуть None

            timeout = httpx.Timeout(10.0, connect=5.0)
            limits = httpx.Limits(max_connections=10, max_keepalive_connections=5)

            асинхронно с помощью httpx.AsyncClient(
                timeout=timeout,
                limits=limits,
                verify=True,
            ) как клиент:
                пытаться:
                    form_data = {
                        «токен»: жетон,
                        "client_id": self.client_id,
                        "client_secret": self.client_secret,
                    }
                    headers = {"Content-Type": "application/x-www-form-urlencoded"}

                    response = await client.post(
                        self.introspection_endpoint,
                        data=form_data,
                        headers=headers,
                    )

                    если response.status_code != 200:
                        вернуть None

                    data = response.json()
                    if not data.get("active", False):
                        вернуть None

                    if not self._validate_resource(data):
                        вернуть None

                    return AccessToken(
                        токен = токен,
                        client_id=data.get("client_id", "unknown"),
                        scopes=data.get("scope", "").split() if data.get("scope") else [],
                        expires_at=data.get("exp"),
                        resource=data.get("aud"), # Включить ресурс в токен
                    )

                за исключением исключения как e:
                    вернуть None

        def _validate_resource(self, token_data: dict[str, Any]) -> bool:
            Для этого ресурсного сервера был выдан токен подтверждения.

            Правила:
            — Отклонить, если отсутствует 'aud'.
            - Принять, если какая-либо запись аудитории соответствует URL-адресу производного ресурса.
            - Поддерживает строковые или списковые формы в соответствии со спецификацией JWT.
            """
            если не self.server_url или не self.resource_url:
                вернуть False

            aud: list[str] | str | None = token_data.get("aud")
            if isinstance(aud, list):
                return any(self._is_valid_resource(a) for a in ud)
            if isinstance(aud, str):
                return self._is_valid_resource(aud)
            вернуть False

        def _is_valid_resource(self, resource: str) -> bool:
            «Проверьте, соответствует ли указанный ресурс нашему серверу».
            return check_resource_allowed(self.resource_url, resource)
    ```

    Для получения более подробной информации см. [документацию Python SDK](https://github.com/modelcontextprotocol/python-sdk).
  </Tab>

  <Tab title="C#">
    Полный проект на C# можно посмотреть в [репозитории примеров](https://github.com/localden/min-cs-mcp-auth).

    Для настройки авторизации на сервере MCP с использованием MCP C# SDK вы можете использовать стандартный шаблон проектирования ASP.NET Core. Вместо использования конечной точки интроспекции, предоставляемой Keycloak, мы будем использовать встроенные возможности ASP.NET Core для проверки токенов.

    ```csharp theme={null}
    using Microsoft.AspNetCore.Authentication.JwtBearer;
    с использованием Microsoft.IdentityModel.Tokens;
    using ModelContextProtocol.AspNetCore.Authentication;
    с использованием ProtectedMcpServer.Tools;
    с использованием System.Security.Claims;

    var builder = WebApplication.CreateBuilder(args);

    var serverUrl = "http://localhost:3000/";
    var authorizationServerUrl = "http://localhost:8080/realms/master/";

    builder.Services.AddAuthentication(options =>
    {
        options.DefaultChallengeScheme = McpAuthenticationDefaults.AuthenticationScheme;
        options.DefaultAuthenticateScheme = JwtBearerDefaults.AuthenticationScheme;
    })
    .AddJwtBearer(options =>
    {
        options.Authority = authorizationServerUrl;
        var normalizedServerAudience = serverUrl.TrimEnd('/');
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidIsuer = authorizationServerUrl,
            ValidAudiences = new[] { normalizedServerAudience, serverUrl },
            AudienceValidator = (audiences, securityToken, validationParameters) =>
            {
                Если количество аудиторий равно null, вернуть false;
                foreach (var aud in audiences)
                {
                    if (string.Equals(aud.TrimEnd('/'), normalizedServerAudience, StringComparison.OrdinalIgnoreCase))
                    {
                        вернуть true;
                    }
                }
                вернуть false;
            }
        };

        options.RequireHttpsMetadata = false; // В производственной среде установите значение true

        options.Events = new JwtBearerEvents
        {
            OnTokenValidated = context =>
            {
                var name = context.Principal?.Identity?.Name ?? "unknown";
                var email = context.Principal?.FindFirstValue("preferred_username") ?? "unknown";
                Console.WriteLine($"Токен подтвержден для: {имя} ({email})");
                return Task.CompletedTask;
            },
            OnAuthenticationFailed = context =>
            {
                Console.WriteLine($"Ошибка аутентификации: {context.Exception.Message}");
                return Task.CompletedTask;
            },
        };
    })
    .AddMcp(options =>
    {
        options.ResourceMetadata = new()
        {
            Resource = new Uri(serverUrl),
            ResourceDocumentation = new Uri("https://docs.example.com/api/math"),
            AuthorizationServers = { new Uri(authorizationServerUrl) },
            ScopesSupported = ["mcp:tools"]
        };
    });

    builder.Services.AddAuthorization();

    builder.Services.AddHttpContextAccessor();
    builder.Services.AddMcpServer()
        .WithTools<MathTools>()
        .WithHttpTransport();

    var app = builder.Build();

    app.UseAuthentication();
    app.UseAuthorization();

    app.MapMcp().RequireAuthorization();

    Console.WriteLine($"Запуск сервера MCP с авторизацией по адресу {serverUrl}");
    Console.WriteLine($"Используется сервер Keycloak по адресу {authorizationServerUrl}");
    Console.WriteLine($"URL метаданных защищенного ресурса: {serverUrl}.well-known/oauth-protected-resource");
    Console.WriteLine("Доступные математические инструменты: сложение, умножение");
    Console.WriteLine("Нажмите Ctrl+C, чтобы остановить сервер");

    app.Run(serverUrl);
    ```

    Для получения более подробной информации см. [документацию по C# SDK](https://github.com/modelcontextprotocol/csharp-sdk).
  </Tab>
</Вкладки>

## Тестирование сервера MCP

Для целей тестирования мы будем использовать [Visual Studio Code](https://code.visualstudio.com), но подойдет любой клиент, поддерживающий MCP и новую спецификацию авторизации.

Нажмите <kbd>Cmd</kbd> + <kbd>Shift</kbd> + <kbd>P</kbd> и выберите **MCP: Добавить сервер...**. Выберите **HTTP** и введите `http://localhost:3000`. Присвойте серверу уникальное имя, которое будет использоваться в Visual Studio Code. В файле `mcp.json` теперь должна отображаться запись примерно такого вида:

```json theme={null}
"my-mcp-server-18676652": {
  "url": "http://localhost:3000",
  "type": "http"
}
```

После подключения вы будете перенаправлены в браузер, где вам будет предложено дать согласие на предоставление Visual Studio Code доступа к области действия `mcp:tools`.

<Рамка>
  <img src="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-vscode.png?fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=d5183fb7c257993aed1b2246f0bbbb27" alt="Форма согласия Keycloak для VS Code." data-og-width="1915" width="1915" data-og-height="1536" height="1536" data-path="images/tutorial-authorization/keycloak-vscode.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-vscode.png?w=280&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=93bb132878b75189c0cf198a59d3b053 280w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-vscode. png?w=560&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=155520f0a1b88422247d9910cb59899f 560 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-vscode. png?w=840&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=4fd24398061374fd940b05d97701dcbc 840w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-vscode.png?w=1100&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=e949784fc78e1f44bc8d3edeb218220b 1100w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-vscode.png?w=1650&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=30fc4dbf14307aac8a2ae938b112ef5b 1650 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/keycloak-vscode.png?w=2500&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=3a0b543da5988dd95b1a447b138c83be 2500 Вт" />
</Frame>

После подтверждения согласия вы увидите список инструментов, расположенный непосредственно над записью о сервере в файле `mcp.json`.

<Рамка>
  <img src="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code.png?fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=f7c34d1bf115fe6934e01b4a5a91168b" alt="Инструменты, перечисленные в VS Code." data-og-width="496" width="496" data-og-height="160" height="160" data-path="images/tutorial-authorization/tools-vs-code.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code.png?w=280&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=9e66d87c84323d4efafb9fa80b58b611 280w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code.png?w=560&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=4b2ef221709a1696272241badcfd7c42 560 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code.png?w=840&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=ce16053621cc5b24a5f5a83fe541feaa 840 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code.png?w=1100&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=59f05ee1ee685b60b0b3fe884cd732f8 1100w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code.png?w=1650&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=ea1afa55bd8f26278d2317ef0ef1a8fb 1650 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code.png?w=2500&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=1f6dd6a4d23ee579f73421689c4c2daa 2500 Вт" />
</Frame>

Вы сможете вызывать отдельные инструменты с помощью символа `#` в окне чата.

<Рамка>
  <img src="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code-invoke.png?fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=76cbef68e48821a3c5467bd20c7e89fe" alt="Вызов инструментов MCP в VS Code." data-og-width="1276" width="1276" data-og-height="396" height="396" data-path="images/tutorial-authorization/tools-vs-code-invoke.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code-invoke.png?w=280&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=7f5687389fe8bf48369a45738ec07795 280w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code-invok e.png?w=560&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=dcc4a1857264bda9f2566e50db51704f 560 Вт, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code-invoke.png?w=840&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=2774a73e612220975ee6d491430b9ee5 840w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code-invoke.png?w=1100&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=014f88a40adddb9faf5f93306dea376c 1100w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code-invoke.png?w=1650&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=d938978e4507cd933695cce01ee49901 1650w, https://mintcdn.com/mcp/sAd4SGUO-cEUqgzn/images/tutorial-authorization/tools-vs-code-invoke.png?w=2500&fit=max&auto=format&n=sAd4SGUO-cEUqgzn&q=85&s=0250d29b2e115324e0b94a4796938bad 2500w" />
</Frame>

## Распространенные ошибки и как их избежать

Для получения исчерпывающих рекомендаций по безопасности, включая векторы атак, стратегии смягчения последствий и лучшие практики внедрения, обязательно ознакомьтесь с [Рекомендациями по обеспечению безопасности](/specification/draft/basic/security_best_practices). Ниже указаны несколько ключевых вопросов.

* **Не реализовывайте логику проверки токенов или авторизации самостоятельно**. Используйте готовые, хорошо протестированные и безопасные библиотеки для таких задач, как проверка токенов или принятие решений об авторизации. Разработка всего с нуля повышает вероятность ошибок, если вы не являетесь экспертом по безопасности.
* **Используйте кратковременные токены доступа**. В зависимости от используемого сервера авторизации этот параметр может быть изменен. Мы рекомендуем не использовать долговременные токены — если злоумышленник их украдет, он сможет сохранять доступ в течение более длительного времени.
* **Всегда проверяйте токены**. Тот факт, что ваш сервер получил токен, не означает, что токен действителен или предназначен именно для вашего сервера. Всегда проверяйте, соответствует ли токен, получаемый вашим MCP-сервером от клиента, требуемым ограничениям.
* **Храните токены в защищенном, зашифрованном хранилище**. В некоторых случаях может потребоваться кэширование токенов на стороне сервера. В этом случае убедитесь, что хранилище имеет надлежащие средства контроля доступа и не может быть легко похищено злоумышленниками, имеющими доступ к вашему серверу. Также следует внедрить надежные политики удаления кэшированных токенов, чтобы гарантировать, что ваш сервер MCP не будет повторно использовать просроченные или иным образом недействительные токены.
* **В производственной среде обязательно используйте HTTPS**. Во время разработки не принимайте токены и не используйте переадресацию по протоколу HTTP, за исключением `localhost`.
* **Области доступа с минимальными привилегиями**. Не используйте универсальные области доступа. Разделяйте доступ по инструментам или возможностям, где это возможно, и проверяйте необходимые области доступа для каждого маршрута/инструмента на сервере ресурсов.
* **Не регистрируйте учетные данные**. Никогда не регистрируйте заголовки, токены, коды или секреты `Authorization`. Проверяйте строки запросов и заголовки. Удаляйте конфиденциальные поля из структурированных журналов.
* **Разделите учетные данные приложения и сервера ресурсов**. Не используйте повторно секрет клиента вашего MCP-сервера для пользовательских сценариев. Храните все секреты в соответствующем менеджере секретов, а не в системе контроля версий.
* **Возвращать корректные запросы аутентификации**. При ошибке 401 включать `WWW-Authenticate` с `Bearer`, `realm` и `resource_metadata`, чтобы клиенты могли узнать, как пройти аутентификацию.
* **Управление динамической регистрацией клиентов (DCR)**. Если эта функция включена, учитывайте ограничения, специфичные для вашей организации, такие как доверенные хосты, обязательная проверка и аудит регистраций. Неаутентифицированная DCR означает, что любой может зарегистрировать любого клиента на вашем сервере авторизации.
* **Случаи путаницы с многопользовательскими системами/областями авторизации**. Привязывайте токены к одному эмитенту/арендатору, если явно не указана многопользовательская система. Отклоняйте токены из других областей авторизации, даже если они подписаны одним и тем же сервером авторизации.
* **Неправильное использование индикаторов аудитории/ресурса**. Не настраивайте и не принимайте общие аудитории (например, `api`) или несвязанные ресурсы. Требуйте, чтобы аудитория/ресурс соответствовали настроенному вами серверу.
* **Утечка подробной информации об ошибке**. Возвращать клиентам общие сообщения, но регистрировать подробные причины с идентификаторами корреляции внутри системы для облегчения поиска и устранения неисправностей без раскрытия внутренней информации.
* **Усиление защиты идентификатора сессии**. Рассматривайте `Mcp-Session-Id` как ненадежный входной параметр; никогда не привязывайте к нему авторизацию. Перегенерируйте идентификатор при изменении аутентификации и проверяйте жизненный цикл на стороне сервера.

## Соответствующие стандарты и документация

Авторизация MCP основана на этих хорошо зарекомендовавших себя стандартах:

* **[OAuth 2.1](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-v2-1-13)**: Основная структура авторизации
* **[RFC 8414](https://datatracker.ietf.org/doc/html/rfc8414)**: Обнаружение метаданных сервера авторизации
* **[RFC 7591](https://datatracker.ietf.org/doc/html/rfc7591)**: Динамическая регистрация клиента
* **[RFC 9728](https://datatracker.ietf.org/doc/html/rfc9728)**: Защищенные метаданные ресурса
* **[RFC 8707](https://datatracker.ietf.org/doc/html/rfc8707)**: Индикаторы ресурсов

Для получения дополнительной информации см.:

* [Спецификация авторизации](/specation/draft/basic/authorization)
* [Рекомендации по обеспечению безопасности](/specification/draft/basic/security_best_practices)
* [Доступные SDK MCP](/docs/sdk)

Понимание этих стандартов поможет вам правильно внедрить систему авторизации и устранять возникающие проблемы.