> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Создание агента SQL

## Обзор

В этом руководстве вы узнаете, как создать агента, способного отвечать на вопросы о базе данных SQL с помощью LangChain [agents](/oss/python/langchain/agents).

В общих чертах, агент будет:

<Шаги>
  <Заголовок шага: "Получить доступные таблицы и схемы из базы данных" />

  <Заголовок шага: Определите, какие таблицы имеют отношение к вопросу</заголовок>

  <Заголовок шага="Получение схем для соответствующих таблиц" />

  <Заголовок шага: Сгенерируйте запрос на основе вопроса и информации из схем</Заголовок шага>

  <Шаг title="Дважды проверьте запрос на наличие распространенных ошибок, используя LLM" />

  <Заголовок шага: "Выполнить запрос и получить результаты" />

  <Step title="Исправление ошибок, выявленных механизмом базы данных, до тех пор, пока запрос не будет выполнен успешно" />

  <Заголовок шага: Сформулируйте ответ на основе полученных результатов</заголовок>
</Шаги>

<Предупреждение>
  Создание систем вопросов и ответов на основе баз данных SQL требует выполнения SQL-запросов, сгенерированных моделью. Это сопряжено с определенными рисками. Убедитесь, что права доступа к базе данных всегда максимально ограничены потребностями вашего агента. Это позволит снизить, хотя и не устранить полностью, риски, связанные с созданием системы, управляемой моделью.
</Предупреждение>

### Концепции

Мы рассмотрим следующие понятия:

* [Инструменты](/oss/python/langchain/tools) для чтения из баз данных SQL
* LangChain [agents](/oss/python/langchain/agents)
* [Процессы с участием человека](/oss/python/langchain/human-in-the-loop)

## Настраивать

### Установка

<CodeGroup>
  ```bash pip theme={null}
  pip install langchain langgraph langchain-community
  ```
</CodeGroup>

### ЛангСмит

Настройте [LangSmith](https://smith.langchain.com), чтобы отслеживать происходящее внутри вашей цепочки или агента. Затем установите следующие переменные среды:

```shell theme={null}
export LANGSMITH_TRACING="true"
export LANGSMITH_API_KEY="..."
```

## 1. Выберите программу магистратуры в области права (LLM).

Выберите модель, которая поддерживает [вызов инструментов](/oss/python/integrations/providers/overview):

<Вкладки>
  <Tab title="OpenAI">
    👉 Ознакомьтесь с документацией по интеграции модели чата OpenAI (/oss/python/integrations/chat/openai/)

    ```shell theme={null}
    pip install -U "langchain[openai]"
    ```

    <CodeGroup>
      ```python init_chat_model theme={null}
      импорт os
      from langchain.chat_models import init_chat_model

      os.environ["OPENAI_API_KEY"] = "sk-..."

      model = init_chat_model("gpt-4.1")
      ```

      ```python Model Class theme={null}
      импорт os
      from langchain_openai import ChatOpenAI

      os.environ["OPENAI_API_KEY"] = "sk-..."

      model = ChatOpenAI(model="gpt-4.1")
      ```
    </CodeGroup>
  </Tab>

  <Tab title="Антропический">
    👉 Ознакомьтесь с документацией по интеграции модели антропного чата [/oss/python/integrations/chat/anthropic/](/oss/python/integrations/chat/anthropic/)

    ```shell theme={null}
    pip install -U "langchain[anthropic]"
    ```

    <CodeGroup>
      ```python init_chat_model theme={null}
      импорт os
      from langchain.chat_models import init_chat_model

      os.environ["ANTHROPIC_API_KEY"] = "sk-..."

      model = init_chat_model("claude-sonnet-4-5-20250929")
      ```

      ```python Model Class theme={null}
      импорт os
      from langchain_anthropic import ChatAnthropic

      os.environ["ANTHROPIC_API_KEY"] = "sk-..."

      model = ChatAnthropic(model="claude-sonnet-4-5-20250929")
      ```
    </CodeGroup>
  </Tab>

  <Tab title="Azure">
    👉 Ознакомьтесь с документацией по интеграции модели чата Azure (/oss/python/integrations/chat/azure_chat_openai/)

    ```shell theme={null}
    pip install -U "langchain[openai]"
    ```

    <CodeGroup>
      ```python init_chat_model theme={null}
      импорт os
      from langchain.chat_models import init_chat_model

      os.environ["AZURE_OPENAI_API_KEY"] = "..."
      os.environ["AZURE_OPENAI_ENDPOINT"] = "..."
      os.environ["OPENAI_API_VERSION"] = "2025-03-01-предварительный просмотр"

      модель = init_chat_model(
          "azure_openai:gpt-4.1",
          azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"],
      )
      ```

      ```python Model Class theme={null}
      импорт os
      from langchain_openai import AzureChatOpenAI

      os.environ["AZURE_OPENAI_API_KEY"] = "..."
      os.environ["AZURE_OPENAI_ENDPOINT"] = "..."
      os.environ["OPENAI_API_VERSION"] = "2025-03-01-предварительный просмотр"

      модель = AzureChatOpenAI(
          model="gpt-4.1",
          azure_deployment=os.environ["AZURE_OPENAI_DEPLOYMENT_NAME"]
      )
      ```
    </CodeGroup>
  </Tab>

  <Tab title="Google Gemini">
    👉 Ознакомьтесь с документацией по интеграции модели чата Google GenAI (/oss/python/integrations/chat/google_generative_ai/)

    ```shell theme={null}
    pip install -U "langchain[google-genai]"
    ```

    <CodeGroup>
      ```python init_chat_model theme={null}
      импорт os
      from langchain.chat_models import init_chat_model

      os.environ["GOOGLE_API_KEY"] = "..."

      model = init_chat_model("google_genai:gemini-2.5-flash-lite")
      ```

      ```python Model Class theme={null}
      импорт os
      from langchain_google_genai import ChatGoogleGenerativeAI

      os.environ["GOOGLE_API_KEY"] = "..."

      модель = ChatGoogleGenerativeAI(model="gemini-2.5-flash-lite")
      ```
    </CodeGroup>
  </Tab>

  <Tab title="AWS Bedrock">
    👉 Ознакомьтесь с документацией по интеграции модели чата AWS Bedrock (/oss/python/integrations/chat/bedrock/)

    ```shell theme={null}
    pip install -U "langchain[aws]"
    ```

    <CodeGroup>
      ```python init_chat_model theme={null}
      from langchain.chat_models import init_chat_model

      # Следуйте инструкциям здесь, чтобы настроить свои учетные данные:
      # https://docs.aws.amazon.com/bedrock/latest/userguide/getting-started.html

      модель = init_chat_model(
          "anthropic.claude-3-5-sonnet-20240620-v1:0",
          model_provider="bedrock_converse",
      )
      ```

      ```python Model Class theme={null}
      from langchain_aws import ChatBedrock

      model = ChatBedrock(model="anthropic.claude-3-5-sonnet-20240620-v1:0")
      ```
    </CodeGroup>
  </Tab>

  <Tab title="HuggingFace">
    👉 Ознакомьтесь с документацией по интеграции модели чата HuggingFace (/oss/python/integrations/chat/huggingface/)

    ```shell theme={null}
    pip install -U "langchain[huggingface]"
    ```

    <CodeGroup>
      ```python init_chat_model theme={null}
      импорт os
      from langchain.chat_models import init_chat_model

      os.environ["HUGGINGFACEHUB_API_TOKEN"] = "hf_..."

      модель = init_chat_model(
          "Microsoft/Phi-3-мини-4k-инструкция",
          model_provider="huggingface",
          температура = 0,7,
          max_tokens=1024,
      )
      ```

      ```python Model Class theme={null}
      импорт os
      from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint

      os.environ["HUGGINGFACEHUB_API_TOKEN"] = "hf_..."

      llm = HuggingFaceEndpoint(
          repo_id="microsoft/Phi-3-mini-4k-instruct",
          температура = 0,7,
          max_length=1024,
      )
      модель = ChatHuggingFace(llm=llm)
      ```
    </CodeGroup>
  </Tab>
</Вкладки>

В приведенных ниже примерах показаны результаты, полученные с помощью OpenAI.

## 2. Настройка базы данных

Для этого урока вы создадите базу данных [SQLite](https://www.sqlitetutorial.net/sqlite-sample-database/). SQLite — это легковесная база данных, которую легко настроить и использовать. Мы загрузим базу данных `chinook`, которая является примером базы данных, представляющей собой магазин цифровых медиафайлов.

Для удобства мы разместили базу данных (`Chinook.db`) в общедоступном хранилище GCS.

```python theme={null}
импорт запросов, pathlib

url = "https://storage.googleapis.com/benchmarks-artifacts/chinook/Chinook.db"
local_path = pathlib.Path("Chinook.db")

если local_path.exists():
    print(f"{local_path} уже существует, загрузка пропускается.")
еще:
    response = requests.get(url)
    если response.status_code == 200:
        local_path.write_bytes(response.content)
        print(f"Файл загружен и сохранен как {local_path}")
    еще:
        print(f"Не удалось загрузить файл. Код состояния: {response.status_code}")
```

Для взаимодействия с базой данных мы будем использовать удобную оболочку для SQL-запросов, доступную в пакете `langchain_community`. Эта оболочка предоставляет простой интерфейс для выполнения SQL-запросов и получения результатов:

```python theme={null}
from langchain_community.utilities import SQLDatabase

db = SQLDatabase.from_uri("sqlite:///Chinook.db")

print(f"Диалект: {db.dialect}")
print(f"Доступные таблицы: {db.get_usable_table_names()}")
print(f'Пример вывода: {db.run("SELECT * FROM Artist LIMIT 5;")}')
```

```
Диалект: sqlite
Доступные таблицы: ['Album', 'Artist', 'Customer', 'Employee', 'Genre', 'Invoice', 'InvoiceLine', 'MediaType', 'Playlist', 'PlaylistTrack', 'Track']
Пример выходных данных: [(1, 'AC/DC'), (2, 'Accept'), (3, 'Aerosmith'), (4, 'Alanis Morissette'), (5, 'Alice In Chains')]
```

## 3. Добавить инструменты для взаимодействия с базой данных

Для взаимодействия с базой данных используйте оболочку `SQLDatabase`, доступную в пакете `langchain_community`. Оболочка предоставляет простой интерфейс для выполнения SQL-запросов и получения результатов:

```python theme={null}
from langchain_community.agent_toolkits import SQLDatabaseToolkit

toolkit = SQLDatabaseToolkit(db=db, llm=model)

инструменты = toolkit.get_tools()

для инструмента в инструментах:
    print(f"{tool.name}: {tool.description}\n")
```

```
sql_db_query: Входными данными для этого инструмента является подробный и корректный SQL-запрос, выходными данными — результат из базы данных. Если запрос некорректен, будет возвращено сообщение об ошибке. В случае ошибки перепишите запрос, проверьте его и попробуйте снова. Если вы столкнулись с проблемой «Неизвестный столбец 'xxxx' в списке полей», используйте sql_db_schema для запроса правильных полей таблицы.

sql_db_schema: Входные данные для этого инструмента — список таблиц, разделенных запятыми; выходные данные — схема и примеры строк для этих таблиц. Убедитесь, что таблицы действительно существуют, предварительно вызвав функцию sql_db_list_tables! Пример входных данных: table1, table2, table3

sql_db_list_tables: Входные данные — пустая строка, выходные данные — список таблиц в базе данных, разделенных запятыми.

sql_db_query_checker: Используйте этот инструмент, чтобы дважды проверить правильность вашего запроса перед его выполнением. Всегда используйте этот инструмент перед выполнением запроса с параметром sql_db_query!
```

## 4. Используйте `create_agent`

Используйте [`create_agent`](https://reference.langchain.com/python/langchain/agents/#langchain.agents.create_agent) для создания [агента ReAct](https://arxiv.org/pdf/2210.03629) с минимальным количеством кода. Агент интерпретирует запрос и сгенерирует SQL-команду, которую выполнят инструменты. Если команда содержит ошибку, сообщение об ошибке возвращается модели. Затем модель может проанализировать исходный запрос и новое сообщение об ошибке и сгенерировать новую команду. Это может продолжаться до тех пор, пока LLM не сгенерирует команду успешно или не достигнет заданного значения. Такой подход к предоставлению модели обратной связи — в данном случае, сообщений об ошибках — очень эффективен.

Для настройки поведения агента выполните инициализацию с помощью системного запроса с описанием:

```python theme={null}
system_prompt = """
Вы являетесь агентом, предназначенным для взаимодействия с базой данных SQL.
Получив на вход вопрос, создайте синтаксически корректный запрос на {диалект} для выполнения.
Затем просмотрите результаты запроса и верните ответ. Если пользователь не...
Если указано конкретное количество примеров, которые они хотят получить, всегда ограничивайте их.
Запрос выдает не более {top_k} результатов.

Вы можете отсортировать результаты по соответствующему столбцу, чтобы отобразить наиболее интересные из них.
Примеры можно найти в базе данных. Никогда не выполняйте запрос ко всем столбцам конкретной таблицы.
Запрашивайте только соответствующие столбцы, исходя из заданного вопроса.

Перед выполнением запроса ОБЯЗАТЕЛЬНО перепроверьте его. Если при выполнении возникает ошибка,
При выполнении запроса перепишите его и попробуйте снова.

НЕ выполняйте никаких операторов DML (INSERT, UPDATE, DELETE, DROP и т. д.) в...
база данных.

Для начала вам ВСЕГДА следует просматривать таблицы в базе данных, чтобы увидеть, что вам нужно.
Можно выполнить запрос. НЕ пропускайте этот шаг.

Затем следует запросить схему наиболее релевантных таблиц.
""".формат(
    dialect=db.dialect,
    top_k=5,
)
```

Теперь создайте агента, указав модель, инструменты и подсказку:

```python theme={null}
from langchain.agents import create_agent


агент = create_agent(
    модель,
    инструменты,
    system_prompt=system_prompt,
)
```

## 5. Запустите агента

Запустите агент на тестовом запросе и понаблюдайте за его поведением:

```python theme={null}
Вопрос: «В каком жанре в среднем самые длинные треки?»

for step in agent.stream(
    {"messages": [{"role": "user", "content": question}]},
    stream_mode="values",
):
    шаг["сообщения"][-1].pretty_print()
```

```
================================ Сообщение от человека ==================================

В каком жанре в среднем самые длинные треки?
================================ Сообщение Ai ================================
Вызовы инструментов:
  sql_db_list_tables (call_BQsWg8P65apHc8BTJ1NPDvnM)
 Идентификатор вызова: call_BQsWg8P65apHc8BTJ1NPDvnM
  Аргументы:
================================= Сообщение инструмента =================================
Имя: sql_db_list_tables

Альбом, Исполнитель, Клиент, Сотрудник, Жанр, Счет, Строка счета, Тип носителя, Плейлист, Трек плейлиста, Трек
================================ Сообщение Ai ================================
Вызовы инструментов:
  sql_db_schema (call_i89tjKECFSeERbuACYm4w0cU)
 Идентификатор вызова: call_i89tjKECFSeERbuACYm4w0cU
  Аргументы:
    table_names: Track, Genre
================================= Сообщение инструмента =================================
Имя: sql_db_schema


СОЗДАТЬ ТАБЛИЦУ "Жанр" (
	"GenreId" INTEGER NOT NULL,
	"Имя" NVARCHAR(120),
	ПЕРВИЧНЫЙ КЛЮЧ ("GenreId")
)

/*
3 строки из таблицы «Жанры»:
GenreId Name
1 Скала
2 Джаз
3 Металл
*/


СОЗДАТЬ ТАБЛИЦУ "Track" (
	"TrackId" INTEGER NOT NULL,
	"Имя" NVARCHAR(200 NOT NULL,
	"AlbumId" INTEGER,
	"MediaTypeId" INTEGER NOT NULL,
	"GenreId" INTEGER,
	«Композитор» НВАРЧАР(220),
	"Миллисекунды" INTEGER NOT NULL,
	"Байты" — целое число,
	"UnitPrice" NUMERIC(10, 2) NOT NULL,
	ПЕРВИЧНЫЙ КЛЮЧ ("TrackId"),
	ВНЕШНИЙ КЛЮЧ("MediaTypeId") ССЫЛКИ "MediaType" ("MediaTypeId"),
	Иностранный ключ("GenreId") Ссылки "Жанр" ("GenreId"),
	FOREIGN KEY("AlbumId") ССЫЛКИ "Альбом" ("AlbumId")
)

/*
3 строки из таблицы Track:
TrackId Name AlbumId MediaTypeId GenreId Composer Milliseconds Bytes UnitPrice
1 Для тех, кто собирается зажечь (Мы приветствуем вас) 1 1 1 Ангус Янг, Малкольм Янг, Брайан Джонсон 343719 11170334 0.99
2 Balls to the Wall 2 2 1 U. Dirkschneider, W. Hoffmann, H. Frank, P. Baltes, S. Kaufmann, G. Hoffmann 342562 5510424 0.99
3 Быстрый как акула 3 2 1 Ф. Балтес, С. Кауфман, У. Диркшнайдер и В. Хоффман 230619 3990994 0.99
*/
================================ Сообщение Ai ================================
Вызовы инструментов:
  sql_db_query_checker (call_G64yYm6R6UauiVPCXJZMA49b)
 Идентификатор вызова: call_G64yYm6R6UauiVPCXJZMA49b
  Аргументы:
    Запрос: SELECT Genre.Name, AVG(Track.Milliseconds) AS AverageLength FROM Track INNER JOIN Genre ON Track.GenreId = Genre.GenreId GROUP BY Genre.Name ORDER BY AverageLength DESC LIMIT 5;
================================= Сообщение инструмента =================================
Имя: sql_db_query_checker

SELECT Genre.Name, AVG(Track.Milliseconds) AS AverageLength FROM Track INNER JOIN Genre ON Track.GenreId = Genre.GenreId GROUP BY Genre.Name ORDER BY AverageLength DESC LIMIT 5;
================================ Сообщение Ai ================================
Вызовы инструментов:
  sql_db_query (call_AnO3SrhD0ODJBxh6dHMwvHwZ)
 Идентификатор вызова: call_AnO3SrhD0ODJBxh6dHMwvHwZ
  Аргументы:
    Запрос: SELECT Genre.Name, AVG(Track.Milliseconds) AS AverageLength FROM Track INNER JOIN Genre ON Track.GenreId = Genre.GenreId GROUP BY Genre.Name ORDER BY AverageLength DESC LIMIT 5;
================================= Сообщение инструмента =================================
Имя: sql_db_query

[('Научная фантастика и фэнтези', 2911783.0384615385), ('Научная фантастика', 2625549.076923077), ('Драма', 2575283.78125), ('Телешоу', 2145041.0215053763), ('Комедия', 1585263.705882353)]
================================ Сообщение Ai ================================

В среднем, жанром с самыми длинными треками является «Научная фантастика и фэнтези» со средней продолжительностью примерно 2 911 783 миллисекунды. За ним следуют «Научная фантастика», «Драма», «Телешоу» и «Комедия».
```

Агент корректно сформулировал запрос, проверил его и выполнил, чтобы получить окончательный ответ.

<Примечание>
  Вы можете просмотреть все аспекты описанного выше запуска, включая предпринятые шаги, задействованные инструменты, какие подсказки были увидены LLM и многое другое в [трассировке LangSmith](https://smith.langchain.com/public/cd2ce887-388a-4bb1-a29d-48208ce50d15/r).
</Примечание>

### (Необязательно) Используйте Studio

[Studio](/langsmith/studio) предоставляет цикл "на стороне клиента", а также память, поэтому вы можете использовать его как чат-интерфейс и запрашивать данные из базы данных. Вы можете задавать вопросы, например: "Расскажите мне схему базы данных" или "Покажите мне счета-фактуры для 5 самых популярных клиентов". Вы увидите сгенерированную SQL-команду и результат выполнения. Подробности о том, как начать работу, приведены ниже.

<Заголовок аккордеона="Запустите своего агента в Studio">
  Помимо упомянутых ранее пакетов, вам потребуется:

  ```shell theme={null}
  pip install -U langgraph-cli[inmem]>=0.4.0
  ```

  В директории, где вы будете запускать программу, вам понадобится файл `langgraph.json` со следующим содержимым:

  ```json theme={null}
  {
    "зависимости": ["."],
    "графики": {
        "agent": "./sql_agent.py:agent",
        "graph": "./sql_agent_langgraph.py:graph"
    },
    "env": ".env"
  }
  ```

  Создайте файл `sql_agent.py` и вставьте в него следующий код:

  ```python theme={null}
  #sql_agent.py для Studio
  импорт pathlib

  from langchain.agents import create_agent
  from langchain.chat_models import init_chat_model
  from langchain_community.agent_toolkits import SQLDatabaseToolkit
  from langchain_community.utilities import SQLDatabase
  импорт запросов


  # Инициализация LLM
  model = init_chat_model("gpt-4.1")

  # Получаем базу данных и сохраняем её локально
  url = "https://storage.googleapis.com/benchmarks-artifacts/chinook/Chinook.db"
  local_path = pathlib.Path("Chinook.db")

  если local_path.exists():
      print(f"{local_path} уже существует, загрузка пропускается.")
  еще:
      response = requests.get(url)
      если response.status_code == 200:
          local_path.write_bytes(response.content)
          print(f"Файл загружен и сохранен как {local_path}")
      еще:
          print(f"Не удалось загрузить файл. Код состояния: {response.status_code}")

  db = SQLDatabase.from_uri("sqlite:///Chinook.db")

  # Создание инструментов
  toolkit = SQLDatabaseToolkit(db=db, llm=model)

  инструменты = toolkit.get_tools()

  для инструмента в инструментах:
      print(f"{tool.name}: {tool.description}\n")

  # Используйте create_agent
  system_prompt = """
  Вы являетесь агентом, предназначенным для взаимодействия с базой данных SQL.
  Получив на вход вопрос, создайте синтаксически корректный запрос на {диалект} для выполнения.
  Затем просмотрите результаты запроса и верните ответ. Если пользователь не...
  Если указано конкретное количество примеров, которые они хотят получить, всегда ограничивайте их.
  Запрос выдает не более {top_k} результатов.

  Вы можете отсортировать результаты по соответствующему столбцу, чтобы отобразить наиболее интересные из них.
  Примеры можно найти в базе данных. Никогда не выполняйте запрос ко всем столбцам конкретной таблицы.
  Запрашивайте только соответствующие столбцы, исходя из заданного вопроса.

  Перед выполнением запроса ОБЯЗАТЕЛЬНО перепроверьте его. Если при выполнении возникает ошибка,
  При выполнении запроса перепишите его и попробуйте снова.

  НЕ выполняйте никаких операторов DML (INSERT, UPDATE, DELETE, DROP и т. д.) в...
  база данных.

  Для начала вам ВСЕГДА следует просматривать таблицы в базе данных, чтобы увидеть, что вам нужно.
  Можно выполнить запрос. НЕ пропускайте этот шаг.

  Затем следует запросить схему наиболее релевантных таблиц.
  """.формат(
      dialect=db.dialect,
      top_k=5,
  )

  агент = create_agent(
      модель,
      инструменты,
      system_prompt=system_prompt,
  )
  ```
</Аккордеон>

## 6. Внедрить проверку с участием человека

Перед выполнением SQL-запросов агента целесообразно проверить их на предмет возможных непредвиденных действий или неэффективности.

Агенты LangChain поддерживают встроенное промежуточное ПО для контроля за вызовами инструментов агента. Давайте настроим агента так, чтобы он приостанавливал вызов инструмента `sql_db_query` для проверки человеком:

```python theme={null}
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware # [!code highlight]
from langgraph.checkpoint.memory import InMemorySaver # [!code highlight]


агент = create_agent(
    модель,
    инструменты,
    system_prompt=system_prompt,
    промежуточное ПО=[ # [!подсветка кода]
        HumanInTheLoopMiddleware( # [!code highlight]
            interrupt_on={"sql_db_query": True}, # [!code highlight]
            description_prefix="Выполнение инструмента ожидает подтверждения", # [!code highlight]
        ), # [!выделение кода]
    ], # [!подсветка кода]
    checkpointer=InMemorySaver(), # [!code highlight]
)
```

<Примечание>
  Мы добавили в наш агент [контрольную точку](/oss/python/langchain/short-term-memory), чтобы позволить приостанавливать и возобновлять выполнение. Подробности об этом, а также о доступных конфигурациях промежуточного ПО, см. в [руководстве по управлению с участием человека](/oss/python/langchain/human-in-the-loop).
</Примечание>

При запуске агента он приостановит выполнение для проверки перед запуском инструмента `sql_db_query`:

```python theme={null}
Вопрос: «В каком жанре в среднем самые длинные треки?»
config = {"configurable": {"thread_id": "1"}} # [!code highlight]

for step in agent.stream(
    {"messages": [{"role": "user", "content": question}]},
    конфигурация, # [!подсветка кода]
    stream_mode="values",
):
    если "__interrupt__" на шаге: # [!подсветка кода]
        print("ПРЕРЫВАЛСЯ:") # [!подсветка кода]
        прерывание = шаг["__interrupt__"][0] # [!подсветка кода]
        for request in interrupt.value["action_requests"]: # [!code highlight]
            print(request["description"]) # [!code highlight]
    elif "messages" in step:
        шаг["сообщения"][-1].pretty_print()
    еще:
        проходить
```

```
...

ПРЕРВАНО:
Выполнение инструмента ожидается после утверждения.

Инструмент: sql_db_query
Аргументы: {'query': 'SELECT g.Name AS Genre, AVG(t.Milliseconds) AS AvgTrackLength FROM Track t JOIN Genre g ON t.GenreId = g.GenreId GROUP BY g.Name ORDER BY AvgTrackLength DESC LIMIT 1;'}
```

Мы можем возобновить выполнение, в данном случае приняв запрос, используя [Команду](/oss/python/langgraph/use-graph-api#combine-control-flow-and-state-updates-with-command):

```python theme={null}
from langgraph.types import Command # [!code highlight]

for step in agent.stream(
    Command(resume={"decisions": [{"type": "approve"}]}), # [!code highlight]
    конфигурация,
    stream_mode="values",
):
    если "сообщения" на шаге:
        шаг["сообщения"][-1].pretty_print()
    elif "__interrupt__" in step:
        print("ПРЕРЫВАЛОСЬ:")
        прерывание = шаг["__прерывание__"][0]
        for request in interrupt.value["action_requests"]:
            print(request["description"])
    еще:
        проходить
```

```
================================ Сообщение Ai ================================
Вызовы инструментов:
  sql_db_query (call_7oz86Epg7lYRqi9rQHbZPS1U)
 Идентификатор вызова: call_7oz86Epg7lYRqi9rQHbZPS1U
  Аргументы:
    Запрос: SELECT Genre.Name, AVG(Track.Milliseconds) AS AvgDuration FROM Track JOIN Genre ON Track.GenreId = Genre.GenreId GROUP BY Genre.Name ORDER BY AvgDuration DESC LIMIT 5;
================================= Сообщение инструмента =================================
Имя: sql_db_query

[('Научная фантастика и фэнтези', 2911783.0384615385), ('Научная фантастика', 2625549.076923077), ('Драма', 2575283.78125), ('Телешоу', 2145041.0215053763), ('Комедия', 1585263.705882353)]
================================ Сообщение Ai ================================

Жанр с самой длинной средней продолжительностью треков — «Научная фантастика и фэнтези» со средней длительностью около 2 911 783 миллисекунд, за ним следуют «Научная фантастика» и «Драма».
```

Для получения более подробной информации обратитесь к [руководству по взаимодействию человека с системой обратной связи](/oss/python/langchain/human-in-the-loop).

## Следующие шаги

Для более глубокой настройки ознакомьтесь с [этим руководством](/oss/python/langgraph/sql-agent), в котором описывается реализация SQL-агента непосредственно с использованием примитивов LangGraph.

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langchain/sql-agent.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Callout>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>