> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Google

На этой странице описаны все интеграции LangChain с [Google Gemini](https://ai.google.dev/gemini-api/docs), [Google Cloud](https://cloud.google.com/) и другими продуктами Google (такими как Google Maps, YouTube и [другие](#другие-продукты-google)).

<Примечание>
  **Единый SDK и консолидация пакетов**

  Начиная с версии `langchain-google-genai` 4.0.0, этот пакет использует объединенный SDK [`google-genai`](https://googleapis.github.io/python-genai/) и теперь поддерживает **как Gemini Developer API, так и бэкенд Vertex AI**.

  Пакет `langchain-google-vertexai` продолжает поддерживаться для функций, специфичных для платформы Vertex AI (Model Garden, Vector Search, сервисы оценки и т. д.).

  Ознакомьтесь с [полным объявлением и руководством по миграции](https://github.com/langchain-ai/langchain-google/discussions/1422).
</Примечание>

Не знаете, какой пакет использовать?

<AccordionGroup>
  <Accordion title="Google Generative AI (Gemini API & Vertex AI)">
    Доступ к моделям Google Gemini осуществляется через **[Gemini Developer API](https://ai.google.dev/)** или **[Vertex AI](https://cloud.google.com/vertex-ai)**. Выбор бэкенда осуществляется автоматически в зависимости от вашей конфигурации.

    * **Gemini Developer API**: Быстрая настройка с помощью ключа API, идеально подходит для индивидуальных разработчиков и быстрого прототипирования.
    * **Vertex AI**: Корпоративные функции с интеграцией с Google Cloud (требуется проект GCP)

    Для работы с моделями чата, LLM-моделями и эмбеддингами используйте пакет `langchain-google-genai`.

    [См. интеграции.](#google-generative-ai)
  </Аккордеон>

  <Accordion title="Google Cloud (Vertex AI Platform Services)">
    Воспользуйтесь доступом к специализированным сервисам платформы Vertex AI, выходящим за рамки моделей Gemini: Model Garden (Llama, Mistral, Anthropic), сервисы оценки и специализированные модели компьютерного зрения.

    Для доступа к платформенным сервисам используйте пакет `langchain-google-vertexai`, а для других облачных сервисов, таких как базы данных и хранилища, — специальные пакеты (например, `langchain-google-community`, `langchain-google-cloud-sql-pg`).

    [См. интеграции.](#google-cloud)
  </Аккордеон>
</AccordionGroup>

Для получения более подробной информации о различиях см. руководство Google по [миграции с Gemini API на Vertex AI](https://ai.google.dev/gemini-api/docs/migrate-to-cloud).

<Примечание>
  Интеграционные пакеты для моделей Gemini и платформы Vertex AI поддерживаются в репозитории [`langchain-google`](https://github.com/langchain-ai/langchain-google).

  Множество интеграций LangChain с другими API и сервисами Google можно найти в пакете `langchain-google-community` (указанном на этой странице) и в организации GitHub [`googleapis`](https://github.com/orgs/googleapis/repositories?q=langchain).
</Примечание>

***

## Генеративный ИИ Google

Доступ к моделям Google Gemini осуществляется через [Gemini Developer API](https://ai.google.dev/gemini-api/docs) или [Vertex AI](https://cloud.google.com/vertex-ai) с помощью унифицированного пакета `langchain-google-genai`.

<Примечание>
  **Объединение посылок**

  Некоторые классы `langchain-google-vertexai` для моделей Gemini устаревают в пользу унифицированного пакета `langchain-google-genai`. Пожалуйста, перейдите на новые классы.

  Ознакомьтесь с [полным объявлением и руководством по миграции](https://github.com/langchain-ai/langchain-google/discussions/1422).
</Примечание>

### Модели чата

<Columns cols={1}>
  <Card title="ChatGoogleGenerativeAI" href="/oss/python/integrations/chat/google_generative_ai" cta="Начать работу" icon="message" arrow>
    Модели чата Google Gemini доступны через **Gemini Developer API** или **Vertex AI**.
  </Карточка>
</Столбцы>

### Магистратура по праву

<Columns cols={1}>
  <Card title="GoogleGenerativeAI" href="/oss/python/integrations/llms/google_ai" cta="Начать работу" icon="i-cursor" arrow>
    Доступ к тем же моделям Gemini (через **Gemini Developer API** или **Vertex AI**) осуществляется с помощью (устаревшего) интерфейса автозаполнения текста LLM.
  </Карточка>
</Столбцы>

### Встраивание моделей

<Columns cols={1}>
  <Card title="GoogleGenerativeAIEmbeddings" href="/oss/python/integrations/text_embedding/google_generative_ai" cta="Начать работу" icon="layer-group" arrow>
    Встраивание моделей Gemini через **Gemini Developer API** или **Vertex AI**.
  </Карточка>
</Столбцы>

***

## Облако Google

Воспользуйтесь доступом к специализированным сервисам платформы Vertex AI, включая Model Garden (Llama, Mistral, Anthropic), Vector Search, услуги оценки и специализированные модели компьютерного зрения.

### Модели чата

<Примечание>
  **Для моделей Gemini** используйте [`ChatGoogleGenerativeAI`](/oss/python/integrations/chat/google_generative_ai) из `langchain-google-genai` вместо `ChatVertexAI`. Он поддерживает как Gemini Developer API, так и бэкенды Vertex AI.

  Приведенные ниже классы посвящены **сервисам платформы Vertex AI**, которые *не* доступны в объединенном SDK.

  Ознакомьтесь с [полным объявлением и руководством по миграции](https://github.com/langchain-ai/langchain-google/discussions/1422).
</Примечание>

<Columns cols={2}>
  <Card title="ChatVertexAI" icon="comments" href="/oss/python/integrations/chat/google_vertex_ai" cta="Начать работу" arrow>
    **Устарело** – Используйте [`ChatGoogleGenerativeAI`](/oss/python/integrations/chat/google_generative_ai) для моделей Gemini вместо этого.
  </Карточка>

  <Card title="ChatAnthropicVertex" icon="comments" href="/oss/python/integrations/chat/google_anthropic_vertex" cta="Начать работу" arrow>
    Антропический сад на базе искусственного интеллекта Vertex.
  </Карточка>
</Столбцы>

<AccordionGroup>
  <Accordion title="VertexModelGardenLlama">
    Лама на модели сада Vertex AI

    ```python wrap theme={null}
    from langchain_google_vertexai.model_garden_maas.llama import VertexModelGardenLlama
    ```
  </Аккордеон>

  <Accordion title="VertexModelGardenMistral">
    Mistral на модели сада Vertex AI

    ```python wrap theme={null}
    from langchain_google_vertexai.model_garden_maas.mistral import VertexModelGardenMistral
    ```
  </Аккордеон>

  <Accordion title="GemmaChatLocalHF">
    Локальная модель Джеммы загружена из HuggingFace.

    ```python wrap theme={null}
    из langchain_google_vertexai.gemma импортировать GemmaChatLocalHF
    ```
  </Аккордеон>

  <Accordion title="GemmaChatLocalKaggle">
    Локальная модель Gemma загружена с Kaggle.

    ```python wrap theme={null}
    from langchain_google_vertexai.gemma import GemmaChatLocalKaggle
    ```
  </Аккордеон>

  <Accordion title="GemmaChatVertexAIModelGarden">
    Джемма о модели сада Vertex AI

    ```python wrap theme={null}
    из langchain_google_vertexai.gemma импортировать GemmaChatVertexAIModelGarden
    ```
  </Аккордеон>

  <Accordion title="VertexAIImageCaptioningChat">
    Реализация модели создания подписей к изображениям в виде чата.

    ```python wrap theme={null}
    from langchain_google_vertexai.vision_models import VertexAIImageCaptioningChat
    ```
  </Аккордеон>

  <Accordion title="VertexAIImageEditorChat">
    Получив изображение и подсказку, отредактируйте изображение. В настоящее время поддерживается только редактирование без маски.

    ```python wrap theme={null}
    from langchain_google_vertexai.vision_models import VertexAIImageEditorChat
    ```
  </Аккордеон>

  <Accordion title="VertexAIImageGeneratorChat">
    Генерирует изображение по запросу.

    ```python wrap theme={null}
    from langchain_google_vertexai.vision_models import VertexAIImageGeneratorChat
    ```
  </Аккордеон>

  <Accordion title="VertexAIVisualQnAChat">
    Реализация визуальной модели вопросов и ответов в формате чата.

    ```python wrap theme={null}
    from langchain_google_vertexai.vision_models import VertexAIVisualQnAChat
    ```
  </Аккордеон>
</AccordionGroup>

### Магистратура по праву

(Устаревший) интерфейс LLM с вводом и выводом строк.

<Columns cols={2}>
  <Card title="VertexAIModelGarden" icon="i-cursor" href="/oss/python/integrations/llms/google_vertex_ai#vertex-model-garden" cta="Начать работу" arrow>
    Получите доступ к Gemini и сотням моделей с открытым исходным кодом через сервис Vertex AI Model Garden.
  </Карточка>

  <Card title="VertexAI" icon="i-cursor" href="/oss/python/integrations/llms/google_vertex_ai" cta="Начать работу" arrow>
    **Устарело** – Используйте [`GoogleGenerativeAI`](/oss/python/integrations/llms/google_generative_ai) для моделей Gemini вместо этого.
  </Карточка>
</Столбцы>

Джемма:

<AccordionGroup>
  <Заголовок аккордеона="Джемма, местная жительница из Hugging Face">
    Локальная модель Джеммы загружена из HuggingFace.

    ```python wrap theme={null}
    from langchain_google_vertexai.gemma import GemmaLocalHF
    ```
  </Аккордеон>

  <Заголовок аккордеона="Джемма, местный житель с Kaggle">
    Локальная модель Gemma загружена с Kaggle.

    ```python wrap theme={null}
    from langchain_google_vertexai.gemma import GemmaLocalKaggle
    ```
  </Аккордеон>

  <Заголовок аккордеона="Джемма о модельном саду Vertex AI">
    ```python wrap theme={null}
    from langchain_google_vertexai.gemma import GemmaVertexAIModelGarden
    ```
  </Аккордеон>

  <Заголовок аккордеона="Подпись к изображениям с помощью Vertex AI">
    Реализация модели создания подписей к изображениям в виде LLM.

    ```python wrap theme={null}
    from langchain_google_vertexai.vision_models import VertexAIImageCaptioning
    ```
  </Аккордеон>
</AccordionGroup>

### Встраивание моделей

<Columns cols={2}>
  <Card title="VertexAIEmbeddings" icon="layer-group" href="/oss/python/integrations/text_embedding/google_vertex_ai" cta="Начать работу" arrow>
    **Устарело** – Используйте [`GenerativeAIEmbeddings`](/oss/python/integrations/text_embedding/google_generative_ai) вместо этого.
  </Карточка>
</Столбцы>

### Загрузчики документов

Загружайте документы из различных источников Google Cloud.

<Columns cols={2}>
  <Card title="AlloyDB for PostgreSQL" href="/oss/python/integrations/document_loaders/google_alloydb" cta="Get started" arrow>
    Google Cloud AlloyDB — это полностью управляемый сервис баз данных, совместимый с PostgreSQL.
  </Карточка>

  <Card title="BigQuery" href="/oss/python/integrations/document_loaders/google_bigquery" cta="Начать работу" arrow>
    Google Cloud BigQuery — это бессерверное хранилище данных.
  </Карточка>

  <Card title="Bigtable" href="/oss/python/integrations/document_loaders/google_bigtable" cta="Начать работу" arrow>
    Google Cloud Bigtable — это масштабируемое, полностью управляемое хранилище данных типа «ключ-значение» и с широкими столбцами, идеально подходящее для быстрого доступа к структурированным, полуструктурированным или неструктурированным данным.
  </Карточка>

  <Card title="Cloud SQL for MySQL" href="/oss/python/integrations/document_loaders/google_cloud_sql_mysql" cta="Начать работу" arrow>
    Google Cloud SQL for MySQL — это полностью управляемый сервис баз данных MySQL.
  </Карточка>

  <Card title="Cloud SQL for SQL Server" href="/oss/python/integrations/document_loaders/google_cloud_sql_mssql" cta="Начать работу" arrow>
    Google Cloud SQL для SQL Server — это полностью управляемый сервис баз данных SQL Server.
  </Карточка>

  <Card title="Cloud SQL for PostgreSQL" href="/oss/python/integrations/document_loaders/google_cloud_sql_pg" cta="Начать работу" arrow>
    Google Cloud SQL for PostgreSQL — это полностью управляемый сервис баз данных PostgreSQL.
  </Карточка>

  <Card title="Облачное хранилище (каталог)" href="/oss/python/integrations/document_loaders/google_cloud_storage_directory" cta="Начать работу" arrow>
    Google Cloud Storage — это управляемый сервис для хранения неструктурированных данных.
  </Карточка>

  <Card title="Облачное хранилище (файл)" href="/oss/python/integrations/document_loaders/google_cloud_storage_file" cta="Начать работу" arrow>
    Google Cloud Storage — это управляемый сервис для хранения неструктурированных данных.
  </Карточка>

  <Card title="El Carro for Oracle Workloads" href="/oss/python/integrations/document_loaders/google_el_carro" cta="Get started" arrow>
    Google El Carro Oracle Operator запускает базы данных Oracle в Kubernetes.
  </Карточка>

  <Card title="Firestore (Native Mode)" href="/oss/python/integrations/document_loaders/google_firestore" cta="Начать работу" arrow>
    Google Cloud Firestore — это документоориентированная база данных NoSQL.
  </Карточка>

  <Card title="Firestore (Datastore Mode)" href="/oss/python/integrations/document_loaders/google_datastore" cta="Начать работу" arrow>
    Google Cloud Firestore в режиме хранилища данных
  </Карточка>

  <Card title="Memorystore for Redis" href="/oss/python/integrations/document_loaders/google_memorystore_redis" cta="Get started" arrow>
    Google Cloud Memorystore for Redis — это полностью управляемый сервис Redis.
  </Карточка>

  <Card title="Spanner" href="/oss/python/integrations/document_loaders/google_spanner" cta="Начать работу" arrow>
    Google Cloud Spanner — это полностью управляемый, глобально распределенный сервис реляционных баз данных.
  </Карточка>

  <Card title="Преобразование речи в текст" href="/oss/python/integrations/document_loaders/google_speech_to_text" cta="Начать работу" arrow>
    Функция Google Cloud Speech-to-Text преобразует аудиофайлы в текст.
  </Карточка>
</Столбцы>

<Card title="Загрузчик облачного зрения">
  Загрузка данных с использованием Google Cloud Vision API.

  ```python theme={null}
  from langchain_google_community.vision import CloudVisionLoader
  ```
</Карточка>

### Трансформаторы документов

Преобразовывать документы с помощью облачных сервисов Google.

<Columns cols={2}>
  <Card title="Document AI" href="/oss/python/integrations/document_transformers/google_docai" cta="Начать работу" arrow>
    Преобразуйте неструктурированные данные из документов в структурированные, чтобы их было легче понимать, анализировать и использовать.
  </Карточка>

  <Card title="Google Translate" href="/oss/python/integrations/document_transformers/google_translate" cta="Начать работу" arrow>
    Переводите текст и HTML с помощью API Google Cloud Translation.
  </Карточка>
</Столбцы>

### Магазины Vector

Храните и ищите векторные данные, используя базы данных Google Cloud и систему векторного поиска Vertex AI Vector Search.

<Columns cols={2}>
  <Card title="AlloyDB for PostgreSQL" href="/oss/python/integrations/vectorstores/google_alloydb" cta="Get started" arrow>
    Google Cloud AlloyDB — это полностью управляемая реляционная база данных, обеспечивающая высокую производительность, бесшовную интеграцию и впечатляющую масштабируемость в Google Cloud. AlloyDB на 100% совместима с PostgreSQL.
  </Карточка>

  <Card title="BigQuery Vector Search" href="/oss/python/integrations/vectorstores/google_bigquery_vector_search" cta="Начать работу" arrow>
    Векторный поиск BigQuery позволяет использовать GoogleSQL для семантического поиска, применяя векторные индексы для быстрых, но приблизительных результатов, или используя метод перебора для получения точных результатов.
  </Карточка>

  <Card title="Memorystore for Redis" href="/oss/python/integrations/vectorstores/google_memorystore_redis" cta="Get started" arrow>
    Vector store использует Memorystore для Redis
  </Карточка>

  <Card title="Spanner" href="/oss/python/integrations/vectorstores/google_spanner" cta="Начать работу" arrow>
    Магазин векторной графики с использованием Cloud Spanner
  </Карточка>

  <Card title="Bigtable" href="/oss/python/integrations/vectorstores/google_bigtable" cta="Начать работу" arrow>
    Магазин векторной графики использует Cloud Bigtable
  </Карточка>

  <Card title="Firestore (Native Mode)" href="/oss/python/integrations/vectorstores/google_firestore" cta="Начать работу" arrow>
    Магазин Vector, использующий Firestore
  </Карточка>

  <Card title="Cloud SQL for MySQL" href="/oss/python/integrations/vectorstores/google_cloud_sql_mysql" cta="Начать работу" arrow>
    Магазин Vector использует Cloud SQL для MySQL.
  </Карточка>

  <Card title="Cloud SQL for PostgreSQL" href="/oss/python/integrations/vectorstores/google_cloud_sql_pg" cta="Get started" arrow>
    Vector Store использует Cloud SQL для PostgreSQL.
  </Карточка>

  <Card title="Vertex AI Vector Search" href="/oss/python/integrations/vectorstores/google_vertex_ai_vector_search" cta="Начать работу" arrow>
    Ранее известная как Vertex AI Matching Engine, эта система предоставляет базу данных векторов с низкой задержкой. Такие базы данных векторов обычно называют системами сопоставления векторного сходства или системами приближенного поиска ближайшего соседа (ANN).
  </Карточка>

  <Card title="С бэкэндом DataStore" href="/oss/python/integrations/vectorstores/google_vertex_ai_vector_search/#optional--you-can-also-create-vectore-and-store-chunks-in-a-datastore" cta="Начать работу" arrow>
    Векторный поиск с использованием хранилища данных для хранения документов.
  </Карточка>
</Столбцы>

### Ретриверы

Получение информации с помощью облачных сервисов Google.

<Columns cols={2}>
  <Card title="Vertex AI Search" icon="magnifying-glass" href="/oss/python/integrations/retrievers/google_vertex_ai_search" cta="Get started" arrow>
    Создавайте поисковые системы на основе генеративного искусственного интеллекта с помощью Vertex AI Search.
  </Карточка>

  <Card title="Document AI Warehouse" icon="warehouse" href="https://cloud.google.com/document-ai-warehouse" cta="Начать работу" arrow>
    Используйте Document AI Warehouse для поиска, хранения и управления документами.
  </Карточка>
</Столбцы>

```python Другие ретриверы theme={null}
from langchain_google_community import VertexAIMultiTurnSearchRetriever
from langchain_google_community import VertexAISearchRetriever
from langchain_google_community import VertexAISearchSummaryTool
```

### Инструменты

Интегрируйте агентов с различными сервисами Google Cloud.

<Columns cols={2}>
  <Card title="Преобразование текста в речь" icon="volume-high" href="/oss/python/integrations/tools/google_cloud_texttospeech" cta="Начать работу" arrow>
    Технология Google Cloud Text-to-Speech синтезирует естественную речь, используя более 100 голосов на разных языках.
  </Карточка>
</Столбцы>

### Обратные вызовы

Отслеживайте использование модели LLM/чата.

<AccordionGroup>
  <Accordion title="Обработчик обратного вызова Vertex AI">
    Обработчик обратного вызова, отслеживающий информацию об использовании `VertexAI`.

    ```python wrap theme={null}
    from langchain_google_vertexai.callbacks import VertexAICallbackHandler
    ```
  </Аккордеон>

  <Accordion title="Google BigQuery">
    Более подробную информацию см. в [документации](/oss/python/integrations/callbacks/google_bigquery).

    ```python wrap theme={null}
    from langchain_google_community.callbacks.bigquery_callback import BigQueryCallbackHandler
    ```
  </Аккордеон>
</AccordionGroup>

### Оценщики

Оцените результаты работы модели с помощью Vertex AI.

<AccordionGroup>
  <Accordion title="VertexPairWiseStringEvaluator">
    Попарная оценка с использованием моделей искусственного интеллекта Vertex.

    ```python wrap theme={null}
    from langchain_google_vertexai.evaluators.evaluation import VertexPairWiseStringEvaluator
    ```
  </Аккордеон>

  <Accordion title="VertexStringEvaluator">
    Оцените одну строку прогнозов с помощью моделей искусственного интеллекта Vertex.

    ```python wrap theme={null}
    from langchain_google_vertexai.evaluators.evaluation import VertexStringEvaluator
    ```
  </Аккордеон>
</AccordionGroup>

***

## Другие продукты Google

Интеграция с различными сервисами Google, выходящими за рамки основной облачной платформы.

### Загрузчики документов

<Columns cols={1}>
  <Card title="Google Drive" href="/oss/python/integrations/document_loaders/google_drive" cta="Начать работу" arrow>
    Файловое хранилище Google Drive. В настоящее время поддерживается Google Docs.
  </Карточка>
</Столбцы>

### Магазины Vector

<Columns cols={1}>
  <Card title="ScaNN (Local Index)" href="/oss/python/integrations/vectorstores/google_scann" cta="Get started" arrow>
    ScaNN — это метод эффективного поиска сходства векторов в больших масштабах.
  </Карточка>
</Столбцы>

### Ретриверы

<Columns cols={1}>
  <Card title="Google Drive" href="/oss/python/integrations/retrievers/google_drive" cta="Начать работу" arrow>
    Извлекать документы из Google Диска.
  </Карточка>
</Столбцы>

### Инструменты

<Columns cols={2}>
  <Card title="Google Search" href="/oss/python/integrations/tools/google_search" cta="Начать работу" arrow>
    Выполняйте поиск в интернете с помощью пользовательской поисковой системы Google (CSE).
  </Карточка>

  <Card title="Google Drive" href="/oss/python/integrations/tools/google_drive" cta="Начать работу" arrow>
    Инструменты для взаимодействия с Google Drive.
  </Карточка>

  <Card title="Google Finance" href="/oss/python/integrations/tools/google_finance" cta="Начать работу" arrow>
    Запрос финансовых данных.
  </Карточка>

  <Card title="Google Jobs" href="/oss/python/integrations/tools/google_jobs" cta="Get started" arrow>
    Поиск вакансий.
  </Карточка>

  <Card title="Google Lens" href="/oss/python/integrations/tools/google_lens" cta="Начать работу" arrow>
    Проведите визуальный поиск.
  </Карточка>

  <Card title="Google Places" href="/oss/python/integrations/tools/google_places" cta="Начать работу" arrow>
    Поиск информации о местах.
  </Карточка>

  <Card title="Google Scholar" href="/oss/python/integrations/tools/google_scholar" cta="Начать работу" arrow>
    Поиск научных статей.
  </Карточка>

  <Card title="Google Trends" href="/oss/python/integrations/tools/google_trends" cta="Начать работу" arrow>
    Запросите данные Google Trends.
  </Карточка>
</Столбцы>

### MCP

<Columns cols={1}>
  <Card title="MCP Toolbox" href="/oss/python/integrations/tools/mcp_toolbox" cta="Начать работу" arrow>
    Простой и эффективный способ подключения к вашим базам данных, в том числе к базам данных Google Cloud, таким как Cloud SQL и AlloyDB.
  </Карточка>
</Столбцы>

### Наборы инструментов

Наборы инструментов для конкретных сервисов Google.

<Columns cols={2}>
  <Card title="Gmail" icon="envelope" href="/oss/python/integrations/tools/google_gmail" cta="Начать работу" arrow>
    Набор инструментов для создания, получения, поиска и отправки электронных писем с использованием API Gmail.
  </Карточка>
</Столбцы>

### Загрузчики чата

<Columns cols={2}>
  <Card title="Gmail" icon="envelope" href="/oss/python/integrations/chat_loaders/google_gmail" cta="Начать работу" arrow>
    Загрузить историю чата из переписки в Gmail.
  </Карточка>
</Столбцы>

***

## Интеграция со сторонними сервисами

Получите доступ к сервисам Google через неофициальные API сторонних разработчиков.

### Поиск

<Columns cols={2}>
  <Card title="SearchApi" icon="magnifying-glass" href="/oss/python/integrations/tools/searchapi" cta="Get started" arrow>
    searchapi.io предоставляет доступ к результатам поиска Google, YouTube и многому другому через API.
  </Карточка>

  <Card title="SerpApi" icon="magnifying-glass" href="/oss/python/integrations/tools/serpapi" cta="Начать работу" arrow>
    SerpApi предоставляет доступ к результатам поиска Google через API.
  </Карточка>

  <Card title="Serper.dev" icon="magnifying-glass" href="/oss/python/integrations/tools/google_serper" cta="Начать работу" arrow>
    serper.dev предоставляет доступ к API для просмотра результатов поиска Google.
  </Карточка>
</Столбцы>

### YouTube

<Columns cols={2}>
  <Card title="Инструмент поиска" icon="youtube" href="/oss/python/integrations/tools/youtube" cta="Начать работу" arrow>
    Ищите видео на YouTube без использования официального API.
  </Карточка>

  <Card title="Загрузчик аудио" icon="youtube" href="/oss/python/integrations/document_loaders/youtube_audio" cta="Начать работу" arrow>
    Скачивайте аудио из видео на YouTube.
  </Карточка>

  <Card title="Загрузчик транскриптов" icon="youtube" href="/oss/python/integrations/document_loaders/youtube_transcript" cta="Начать работу" arrow>
    Загрузите расшифровку видео.
  </Карточка>
</Столбцы>

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/providers/google.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Всплывающее сообщение>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>