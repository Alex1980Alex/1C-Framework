> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Создайте SQL-помощника с навыками по запросу

В этом руководстве показано, как использовать **прогрессивное раскрытие информации** — метод управления контекстом, при котором агент загружает информацию по запросу, а не заранее, — для реализации **навыков** (специализированных инструкций на основе подсказок). Агент загружает навыки посредством вызовов инструментов, а не динамически изменяя системную подсказку, обнаруживая и загружая только те навыки, которые ему необходимы для каждой задачи.

**Пример использования:** Представьте себе создание агента, который поможет писать SQL-запросы для различных бизнес-направлений в крупном предприятии. В вашей организации могут быть отдельные хранилища данных для каждого направления или единая монолитная база данных с тысячами таблиц. В любом случае, предварительная загрузка всех схем перегрузит контекстное окно. Прогрессивное раскрытие решает эту проблему, загружая только необходимую схему по мере необходимости. Эта архитектура также позволяет различным владельцам продуктов и заинтересованным сторонам независимо вносить свой вклад и поддерживать навыки для своих конкретных бизнес-направлений.

**Что вы будете создавать:** Помощник по SQL-запросам с двумя навыками (аналитика продаж и управление запасами). Агент видит упрощенные описания навыков в командной строке системы, а затем загружает полные схемы баз данных и бизнес-логику с помощью вызовов инструментов только тогда, когда это необходимо для запроса пользователя.

<Примечание>
  Более подробный пример SQL-агента с выполнением запросов, исправлением ошибок и проверкой данных см. в нашем [руководстве по SQL-агенту](/oss/python/langchain/sql-agent). В этом руководстве основное внимание уделяется шаблону постепенного раскрытия информации, который может быть применен к любой области.
</Примечание>

<Совет>
  Метод постепенного раскрытия информации был популяризирован компанией Anthropic как способ построения масштабируемых систем навыков агентов. Этот подход использует трехуровневую архитектуру (метаданные → основной контент → подробные ресурсы), где агенты загружают информацию только по мере необходимости. Подробнее об этом методе см. [Оснащение агентов для реального мира навыками агентов](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills).
</Совет>

## Как это работает

Вот как происходит процесс, когда пользователь запрашивает SQL-запрос:

```тема русалки={null}
%%{init: {'theme':'base', 'themeVariables': { 'primaryColor':'#4CAF50','primaryTextColor':'#fff','primaryBorderColor':'#2E7D32','lineColor':'#666','secondaryColor':'#FF9800','tertiaryColor':'#2196F3','tertiaryBorderColor':'#1565C0','tertiaryTextColor':'#fff'}}}%%
блок-схема TD
    Start([💬 Пользователь: Напишите SQL-запрос<br/>для ценных клиентов]) --> SystemPrompt[📋 Агент видит описания навыков:<br/>• аналитика продаж<br/>• управление запасами]

    SystemPrompt --> Decide{🤔 Need sales schema}

    Решить --> LoadSkill[🔧 load_skill<br/>'sales_analytics']

    LoadSkill --> Схема[📊 Загружена схема:<br/>таблицы клиентов, заказов<br/>+ бизнес-логика]

    Схема --> WriteQuery[✍️ Агент пишет SQL-запрос, используя знания схемы]

    WriteQuery --> Response([✅ Возвращает корректный SQL-запрос, соответствующий бизнес-правилам])

    %% Стилизация для светлого и темного режимов
    classDef startEnd fill:#4CAF50,stroke:#2E7D32,stroke-width:2px,color:#fff
    classDef process fill:#FF9800,stroke:#E65100,stroke-width:2px,color:#fff
    classDef decision fill:#2196F3,stroke:#1565C0,stroke-width:2px,color:#fff
    classDef enrichment fill:#9C27B0,stroke:#6A1B9A,stroke-width:2px,color:#fff

    класс Start,Response startEnd
    class SystemPrompt,LoadSkill,WriteQuery process
    класс Принять решение
    обогащение схемы класса
```

**Почему важна прогрессивная система раскрытия информации:**

* **Уменьшает использование контекста** — загружаются только 2-3 навыка, необходимые для выполнения задачи, а не все доступные навыки.
* **Обеспечивает автономию команды** — разные команды могут самостоятельно развивать специализированные навыки (аналогично другим многоагентным архитектурам).
* **Эффективное масштабирование** — добавляйте десятки или сотни навыков, не перегружая контекст.
* **Упрощает историю переписки** - один агент с одной веткой разговора

**Что такое навыки:** Навыки, популяризированные Клодом Кодом, в основном основаны на подсказках: это самодостаточные блоки специализированных инструкций для выполнения конкретных бизнес-задач. В коде Клода навыки представлены в виде каталогов с файлами в файловой системе, которые обнаруживаются посредством файловых операций. Навыки направляют поведение с помощью подсказок и могут предоставлять информацию об использовании инструментов или включать примеры кода для выполнения программистом.

<Совет>
  Навыки с поэтапным раскрытием информации можно рассматривать как форму [RAG (Retrieval-Augmented Generation)](/oss/python/langchain/rag), где каждый навык представляет собой единицу поиска — хотя и не обязательно подкрепленную эмбеддингами или поиском по ключевым словам, а инструментами для просмотра контента (например, операциями с файлами или, в этом руководстве, прямым поиском).
</Совет>

**Компромиссы:**

* **Задержка**: Загрузка навыков по запросу требует дополнительных вызовов инструментов, что увеличивает задержку при первом запросе, требующем каждый навык.
* **Управление рабочим процессом**: Базовые реализации полагаются на подсказки для управления использованием навыков — вы не можете установить жесткие ограничения, такие как «всегда пробуйте навык A перед навыком B», без пользовательской логики.

<Совет>
  **Внедрение собственной системы навыков**

  При создании собственной системы реализации навыков (как мы это делаем в этом руководстве) ключевой концепцией является поэтапное раскрытие информации — загрузка данных по запросу. Помимо этого, у вас есть полная свобода в реализации:

  * **Хранилище**: базы данных, S3, структуры данных в оперативной памяти или любой другой бэкэнд.
  * **Обнаружение**: прямой поиск (в этом руководстве), RAG для больших наборов навыков, сканирование файловой системы или вызовы API.
  * **Логика загрузки**: настройка характеристик задержки и добавление логики поиска по содержимому навыков или ранжированию релевантности.
  * **Побочные эффекты**: определяют, что происходит при загрузке навыка, например, отображение инструментов, связанных с этим навыком (рассмотрено в разделе 8).

  Такая гибкость позволяет оптимизировать систему в соответствии с вашими конкретными требованиями к производительности, объему памяти и управлению рабочими процессами.
</Совет>

## Настраивать

### Установка

Для выполнения этого руководства необходим пакет `langchain`:

<CodeGroup>
  ```bash pip theme={null}
  pip install langchain
  ```

  ```bash uv theme={null}
  uv add langchain
  ```

  ```bash conda theme={null}
  установка conda langchain -c conda-forge
  ```
</CodeGroup>

Для получения более подробной информации см. наше [руководство по установке](/oss/python/langchain/install).

### ЛангСмит

Настройте [LangSmith](https://smith.langchain.com), чтобы отслеживать происходящее внутри вашего агента. Затем установите следующие переменные среды:

<CodeGroup>
  ```bash bash theme={null}
  export LANGSMITH_TRACING="true"
  export LANGSMITH_API_KEY="..."
  ```

  ```python python theme={null}
  импортировать getpass
  импорт os

  os.environ["LANGSMITH_TRACING"] = "true"
  os.environ["LANGSMITH_API_KEY"] = getpass.getpass()
  ```
</CodeGroup>

### Выберите программу магистратуры (LLM)

Выберите модель чата из набора интеграций LangChain:

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

## 1. Определение навыков

Сначала определите структуру навыков. Каждый навык имеет название, краткое описание (отображается в системном запросе) и полный контент (загружается по запросу):

```python theme={null}
from typing import TypedDict

class Skill(TypedDict): # [!подсветка кода]
    «Навык, который может постепенно раскрываться агенту».
    имя: str # Уникальный идентификатор навыка
    описание: строка № 1-2, описание из предложения для отображения в системной подсказке
    содержимое: строка # Полный набор навыков с подробными инструкциями
```

Теперь определим примеры навыков для помощника по SQL-запросам. Навыки разработаны таким образом, чтобы быть **легко описываемыми** (показываются агенту сразу), но **подробными по содержанию** (загружаются только при необходимости):

<Заголовок аккордеона="Просмотреть полные определения навыков">
  ```python theme={null}
  НАВЫКИ: список[Навык] = [
      {
          "name": "sales_analytics",
          «Описание»: «Схема базы данных и бизнес-логика для анализа данных о продажах, включая клиентов, заказы и выручку».
          "content": """# Схема аналитики продаж

  ## Таблицы

  ### клиенты
  - customer_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - имя
  - электронная почта
  - signup_date
  - статус (активный/неактивный)
  - уровень клиента (бронзовый/серебряный/золотой/платиновый)

  ### заказы
  - order_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - customer_id (ВНЕШНИЙ КЛЮЧ -> customers)
  - order_date
  - статус (ожидает завершения/завершено/отменено/возмещено)
  - Общая сумма
  - регион продаж (север/юг/восток/запад)

  ### order_items
  - item_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - order_id (ВНЕШНИЙ КЛЮЧ -> orders)
  - product_id
  - количество
  - цена за единицу товара
  - discount_percent

  ## Бизнес-логика

  **Активные клиенты**: статус = 'активный' И дата регистрации <= Текущая дата - интервал '90 дней'

  **Расчет выручки**: Учитывайте только заказы со статусом = 'выполнено'. Используйте значение total_amount из таблицы orders, в которой уже учтены скидки.

  **Пожизненная ценность клиента (CLV)**: Сумма сумм всех выполненных заказов для данного клиента.

  **Заказы с высокой стоимостью**: Заказы с общей суммой > 1000

  ## Пример запроса

  — Получите список 10 лучших клиентов по выручке за последний квартал.
  ВЫБИРАТЬ
      c.customer_id,
      c.name,
      c.customer_tier,
      SUM(o.total_amount) as total_revenue
  ОТ клиентов c
  JOIN orders o ON c.customer_id = o.customer_id
  ГДЕ o.status = 'completed'
    И o.order_date >= CURRENT_DATE - INTERVAL '3 months'
  GROUP BY c.customer_id, c.name, c.customer_tier
  ORDER BY total_revenue DESC
  ОГРАНИЧЕНИЕ 10;
  """,
      },
      {
          "name": "inventory_management",
          «Описание»: «Схема базы данных и бизнес-логика для отслеживания запасов, включая товары, склады и уровни запасов».
          "content": """# Схема управления запасами

  ## Таблицы

  ### продукты
  - product_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - product_name
  - артикул
  - категория
  - unit_cost
  - reorder_point (минимальный уровень запасов перед повторным заказом)
  - прекращено (логическое значение)

  ### склады
  - warehouse_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - warehouse_name
  - расположение
  - емкость

  ### инвентарь
  - inventory_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - product_id (ВНЕШНИЙ КЛЮЧ -> products)
  - warehouse_id (ВНЕШНИЙ КЛЮЧ -> warehouses)
  - количество_в_наличии
  - last_updated

  ### движения_акций
  - movement_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - product_id (ВНЕШНИЙ КЛЮЧ -> products)
  - warehouse_id (ВНЕШНИЙ КЛЮЧ -> warehouses)
  - movement_type (inbound/outbound/transfer/adjustment)
  - количество (положительное для входящих потоков, отрицательное для исходящих потоков)
  - movement_date
  - номер_ссылки

  ## Бизнес-логика

  **Доступный товар на складе**: quantity_on_hand из таблицы inventory, где quantity_on_hand > 0

  **Товары, требующие повторного заказа**: Товары, общее количество которых на складах меньше или равно точке повторного заказа данного товара.

  **Только активные товары**: Исключить товары, для которых "сняты с производства" = true, за исключением случаев, когда анализируются именно снятые с производства товары.

  **Оценка запасов**: количество_на_складе * себестоимость_единицы для каждого товара.

  ## Пример запроса

  — Найдите товары по цене ниже точки повторного заказа на всех складах.
  ВЫБИРАТЬ
      p.product_id,
      p.product_name,
      p.reorder_point,
      SUM(i.quantity_on_hand) as total_stock,
      p.unit_cost,
      (p.reorder_point - SUM(i.quantity_on_hand)) as units_to_reorder
  ОТ продуктов p
  JOIN inventory i ON p.product_id = i.product_id
  ГДЕ p.discontinued = false
  GROUP BY p.product_id, p.product_name, p.reorder_point, p.unit_cost
  ДАЛИ SUM(i.quantity_on_hand) <= p.reorder_point
  ORDER BY units_to_reorder DESC;
  """,
      },
  ]
  ```
</Аккордеон>

## 2. Создайте инструмент для загрузки навыков

Создайте инструмент для загрузки полного содержимого навыков по запросу:

```python theme={null}
from langchain.tools import tool

@tool # [!подсветка кода]
def load_skill(skill_name: str) -> str:
    """Загрузить полное содержимое навыка в контекст агента."

    Используйте это, когда вам нужна подробная информация о том, как поступить в конкретной ситуации.
    это тип запроса. Это предоставит вам подробные инструкции.
    политика и руководящие принципы в данной области навыков.

    Аргументы:
        skill_name: Название загружаемого навыка (например, "expense_reporting", "travel_booking")
    """
    # Найти и вернуть запрошенный навык
    для развития навыков:
        если skill["name"] == skill_name:
            return f"Загружен навык: {skill_name}\n\n{skill['content']}" # [!code highlight]

    # Навык не найден
    available = ", ".join(s["name"] for s in SKILLS)
    return f"Навык '{skill_name}' не найден. Доступные навыки: {available}"
```

Инструмент `load_skill` возвращает полное содержимое навыка в виде строки, которая становится частью диалога в виде сообщения ToolMessage. Более подробную информацию о создании и использовании инструментов см. в [руководстве по инструментам](/oss/python/langchain/tools).

## 3. Создание промежуточного программного обеспечения для навыков

Создайте пользовательское промежуточное ПО, которое будет внедрять описания навыков в системную подсказку. Это промежуточное ПО позволит обнаруживать навыки без предварительной загрузки их полного содержимого.

<Примечание>
  В этом руководстве показано, как создавать пользовательское промежуточное ПО. Подробное руководство по концепциям и шаблонам промежуточного ПО см. в [документации по пользовательскому промежуточному ПО](/oss/python/langchain/middleware/custom).
</Примечание>

```python theme={null}
from langchain.agents.middleware import ModelRequest, ModelResponse, AgentMiddleware
from langchain.messages import SystemMessage
from typing import Callable

class SkillMiddleware(AgentMiddleware): # [!выделение кода]
    «Промежуточное программное обеспечение, которое внедряет описания навыков в системную подсказку».

    # Зарегистрируйте инструмент load_skill в качестве переменной класса
    tools = [load_skill] # [!code highlight]

    def __init__(self):
        """Инициализируйте и сгенерируйте запрос на ввод навыков из раздела "НАВЫКИ".""
        # Создайте подсказку по навыкам из списка НАВЫКОВ
        skills_list = []
        для развития навыков:
            skills_list.append(
                f"- **{skill['name']}**: {skill['description']}"
            )
        self.skills_prompt = "\n".join(skills_list)

    def wrap_model_call(
        себя,
        запрос: ModelRequest,
        обработчик: Callable[[ModelRequest], ModelResponse],
    ) -> ModelResponse:
        «Синхронизация: Вставить описания навыков в системную подсказку».
        # Создать дополнение к описанию навыков
        skills_addentum = ( # [!code highlight]
            f"\n\n## Доступные навыки\n\n{self.skills_prompt}\n\n" # [!code highlight]
            "Используйте инструмент load_skill, когда вам нужна подробная информация" # [!code highlight]
            «Об обработке определенного типа запросов». # [!code highlight]
        )

        # Добавить к блокам содержимого системных сообщений
        new_content = list(request.system_message.content_blocks) + [
            {"type": "text", "text": skills_addenum}
        ]
        new_system_message = SystemMessage(content=new_content)
        modified_request = request.override(system_message=new_system_message)
        return handler(modified_request)
```

Промежуточное ПО добавляет описания навыков к системной подсказке, позволяя агенту узнать о доступных навыках без загрузки их полного содержимого. Инструмент `load_skill` регистрируется как переменная класса, что делает его доступным для агента.

<Примечание>
  **Рекомендации для производственной среды**: В этом руководстве для простоты список навыков загружается в `__init__`. В производственной системе может потребоваться загрузка навыков в хуке `before_agent`, что позволит периодически обновлять их в соответствии с актуальными изменениями (например, при добавлении новых навыков или изменении существующих). Подробности см. в документации по хуку `before_agent` (/oss/python/langchain/middleware/custom#before_agent).
</Примечание>

## 4. Создайте агента с поддержкой навыков

Теперь создайте агента с промежуточным ПО для навыков и контрольной точкой для сохранения состояния:

```python theme={null}
from langchain.agents import create_agent
from langgraph.checkpoint.memory import InMemorySaver

# Создание агента с поддержкой навыков
агент = create_agent(
    модель,
    system_prompt=(
        «Вы — помощник по SQL-запросам, который помогает пользователям».
        «Напишите запросы к бизнес-базам данных».
    ),
    middleware=[SkillMiddleware()], # [!подсветка кода]
    checkpointer=InMemorySaver(),
)
```

Теперь агент имеет доступ к описаниям навыков в командной строке системы и может вызвать `load_skill` для получения полного содержимого навыка при необходимости. Контрольная точка сохраняет историю диалога между ходами.

## 5. Тестирование поэтапного раскрытия информации

Проверьте работу агента, задав вопрос, требующий специальных знаний:

```python theme={null}
импорт uuid

# Настройки для этой ветки обсуждения
thread_id = str(uuid.uuid4())
config = {"configurable": {"thread_id": thread_id}}

# Запрос SQL-запроса
результат = agent.invoke( # [!подсветка кода]
    {
        "сообщения": [
            {
                "роль": "пользователь",
                "содержание": (
                    «Напишите SQL-запрос для поиска всех клиентов».
                    "которые сделали заказы на сумму более 1000 долларов за последний месяц"
                ),
            }
        ]
    },
    конфигурация
)

# Вывести переписку
for message in result["messages"]:
    if hasattr(message, 'pretty_print'):
        message.pretty_print()
    еще:
        print(f"{message.type}: {message.content}")
```

Ожидаемый результат:

```
================================ Сообщение от человека ==================================

Напишите SQL-запрос для поиска всех клиентов, которые совершили заказы на сумму более 1000 долларов за последний месяц.
================================ Сообщение Ai ================================
Вызовы инструментов:
  load_skill (call_abc123)
 Идентификатор вызова: call_abc123
  Аргументы:
    skill_name: sales_analytics
================================= Сообщение инструмента =================================
Имя: load_skill

Навык: аналитика продаж

# Схема аналитики продаж

## Таблицы

### клиенты
- customer_id (ПЕРВИЧНЫЙ КЛЮЧ)
- имя
- электронная почта
- signup_date
- статус (активный/неактивный)
- уровень клиента (бронзовый/серебряный/золотой/платиновый)

### заказы
- order_id (ПЕРВИЧНЫЙ КЛЮЧ)
- customer_id (ВНЕШНИЙ КЛЮЧ -> customers)
- order_date
- статус (ожидает завершения/завершено/отменено/возмещено)
- Общая сумма
- регион продаж (север/юг/восток/запад)

[... остальная часть схемы ...]

## Бизнес-логика

**Заказы с высокой стоимостью**: Заказы с `total_amount > 1000`
**Расчет выручки**: Учитываться только заказы со статусом `status = 'completed'`.

================================ Сообщение Ai ================================

Вот SQL-запрос для поиска всех клиентов, которые совершили заказы на сумму более 1000 долларов за последний месяц:

\`\`\`sql
ВЫБРАТЬ УНИКАЛЬНЫЙ
    c.customer_id,
    c.name,
    c.email,
    c.customer_tier
ОТ клиентов c
JOIN orders o ON c.customer_id = o.customer_id
ГДЕ o.total_amount > 1000
  И o.status = 'завершено'
  И o.order_date >= CURRENT_DATE - INTERVAL '1 month'
ORDER BY c.customer_id;
\`\`\`

Этот запрос:
- Сопровождает клиентов при оформлении заказов.
- Фильтрация заказов с высокой стоимостью (>1000 долларов США) с использованием поля total_amount.
- Включает только выполненные заказы (в соответствии с бизнес-логикой)
- Доступно только для заказов, оформленных в течение последнего месяца.
- Возвращает уникальных клиентов, чтобы избежать дубликатов, если они сделали несколько соответствующих заказов.
```

Агент увидел в командной строке системы описание упрощенного навыка, понял, что для ответа требуется знание базы данных продаж, вызвал функцию `load_skill("sales_analytics")`, чтобы получить полную схему и бизнес-логику, а затем использовал эту информацию для написания корректного запроса в соответствии с соглашениями базы данных.

## 6. Расширенные настройки: Добавление ограничений с пользовательским состоянием

<Заголовок аккордеона="Необязательно: Отслеживание загруженных навыков и обеспечение соблюдения ограничений на инструменты">
  Вы можете добавить ограничения, чтобы гарантировать доступность определенных инструментов только после загрузки конкретных навыков. Для этого необходимо отслеживать, какие навыки были загружены в пользовательском состоянии агента.

  ### Определение пользовательского состояния

  Во-первых, необходимо расширить состояние агента, чтобы отслеживать загруженные навыки:

  ```python theme={null}
  from langchain.agents.middleware import AgentState

  class CustomState(AgentState): # [!code highlight]
      skills_loaded: NotRequired[list[str]] # Отслеживание загруженных навыков # [!code highlight]
  ```

  ### Обновите load\_skill для изменения состояния

  Измените инструмент `load_skill` таким образом, чтобы он обновлял состояние при загрузке навыка:

  ```python theme={null}
  from langgraph.types import Command # [!code highlight]
  from langchain.tools import tool, ToolRuntime
  from langchain.messages import ToolMessage # [!code highlight]

  @инструмент
  def load_skill(skill_name: str, runtime: ToolRuntime) -> Command: # [!code highlight]
      """Загрузить полное содержимое навыка в контекст агента."

      Используйте это, когда вам нужна подробная информация о том, как поступить в конкретной ситуации.
      это тип запроса. Это предоставит вам подробные инструкции.
      политика и руководящие принципы в данной области навыков.

      Аргументы:
          skill_name: Название навыка для загрузки
      """
      # Найти и вернуть запрошенный навык
      для развития навыков:
          если skill["name"] == skill_name:
              skill_content = f"Загружен навык: {skill_name}\n\n{skill['content']}"

              # Обновить состояние для отслеживания загруженного навыка
              return Command( # [!выделение кода]
                  обновление={ # [!подсветка кода]
                      "сообщения": [ # [!подсветка кода]
                          ToolMessage( # [!подсветка кода]
                              content=skill_content, # [!code highlight]
                              tool_call_id=runtime.tool_call_id, # [!code highlight]
                          ) # [!подсветка кода]
                      ], # [!подсветка кода]
                      "skills_loaded": [skill_name], # [!code highlight]
                  } # [!подсветка кода]
              ) # [!подсветка кода]

      # Навык не найден
      available = ", ".join(s["name"] for s in SKILLS)
      return Command(
          обновление={
              "сообщения": [
                  ToolMessage(
                      content=f"Навык '{skill_name}' не найден. Доступные навыки: {available}",
                      tool_call_id=runtime.tool_call_id,
                  )
              ]
          }
      )
  ```

  ### Создание инструмента с ограничениями

  Создайте инструмент, который станет доступен только после загрузки определенного навыка:

  ````python theme={null}
  @инструмент
  def write_sql_query( # [!выделение кода]
      запрос: str,
      вертикальный: стр.,
      среда выполнения: ToolRuntime,
  ) -> str:
      """Напишите и проверьте SQL-запрос для конкретной бизнес-отрасли."

      Этот инструмент помогает форматировать и проверять SQL-запросы. Необходимо загрузить...
      Для понимания схемы базы данных сначала необходимо обладать соответствующими навыками.

      Аргументы:
          Запрос: SQL-запрос, который необходимо написать.
          Вертикаль: Бизнес-вертикаль (аналитика продаж или управление запасами)
      """
      # Проверьте, загружен ли необходимый навык
      skills_loaded = runtime.state.get("skills_loaded", []) # [!code highlight]

      if vertical not in skills_loaded: # [!code highlight]
          return ( # [!выделение кода]
              f"Ошибка: Сначала необходимо загрузить навык '{vertical}'" # [!code highlight]
              f"Чтобы понять схему базы данных перед написанием запросов." # [!code highlight]
              f"Используйте load_skill('{vertical}') для загрузки схемы." # [!code highlight]
          ) # [!подсветка кода]

      # Проверка и форматирование запроса
      возвращаться (
          f"SQL-запрос для {вертикальный}:\n\n"
          f"```sql\n{query}\n```\n\n"
          f"✓ Запрос проверен на соответствие схеме {vertical}\n"
          "Готов к выполнению запроса к базе данных."
      )
  ````

  ### Обновление промежуточного ПО и агента

  Обновите промежуточное ПО, чтобы оно использовало пользовательскую схему состояния:

  ```python theme={null}
  class SkillMiddleware(AgentMiddleware[CustomState]): # [!подсветка кода]
      «Промежуточное программное обеспечение, которое внедряет описания навыков в системную подсказку».

      state_schema = CustomState # [!code highlight]
      tools = [load_skill, write_sql_query] # [!code highlight]

      # ... остальная часть реализации промежуточного ПО остается без изменений
  ```

  Создайте агента с промежуточным ПО, которое регистрирует инструмент с ограниченными правами:

  ```python theme={null}
  агент = create_agent(
      модель,
      system_prompt=(
          «Вы — помощник по SQL-запросам, который помогает пользователям».
          «Напишите запросы к бизнес-базам данных».
      ),
      middleware=[SkillMiddleware()], # [!подсветка кода]
      checkpointer=InMemorySaver(),
  )
  ```

  Теперь, если агент попытается использовать `write_sql_query` до загрузки необходимого навыка, он получит сообщение об ошибке, предлагающее сначала загрузить соответствующий навык (например, `sales_analytics` или `inventory_management`). Это гарантирует, что агент получит необходимые знания о схеме перед попыткой проверки запросов.
</Аккордеон>

## Полный пример

<Заголовок аккордеона="Просмотреть полный исполняемый скрипт">
  Вот полная, работоспособная реализация, объединяющая все компоненты из этого руководства:

  ```python theme={null}
  импорт uuid
  from typing import TypedDict, NotRequired
  from langchain.tools import tool
  from langchain.agents import create_agent
  from langchain.agents.middleware import ModelRequest, ModelResponse, AgentMiddleware
  from langchain.messages import SystemMessage
  from langgraph.checkpoint.memory import InMemorySaver
  from typing import Callable

  # Определение структуры навыков
  class Skill(TypedDict):
      «Навык, который может постепенно раскрываться агенту».
      имя: str
      описание: строка
      содержимое: строка

  # Определение навыков с помощью схем и бизнес-логики
  НАВЫКИ: список[Навык] = [
      {
          "name": "sales_analytics",
          «Описание»: «Схема базы данных и бизнес-логика для анализа данных о продажах, включая клиентов, заказы и выручку».
          "content": """# Схема аналитики продаж

  ## Таблицы

  ### клиенты
  - customer_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - имя
  - электронная почта
  - signup_date
  - статус (активный/неактивный)
  - уровень клиента (бронзовый/серебряный/золотой/платиновый)

  ### заказы
  - order_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - customer_id (ВНЕШНИЙ КЛЮЧ -> customers)
  - order_date
  - статус (ожидает завершения/завершено/отменено/возмещено)
  - Общая сумма
  - регион продаж (север/юг/восток/запад)

  ### order_items
  - item_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - order_id (ВНЕШНИЙ КЛЮЧ -> orders)
  - product_id
  - количество
  - цена за единицу товара
  - discount_percent

  ## Бизнес-логика

  **Активные клиенты**: статус = 'активный' И дата регистрации <= Текущая дата - интервал '90 дней'

  **Расчет выручки**: Учитывайте только заказы со статусом = 'выполнено'. Используйте значение total_amount из таблицы orders, в которой уже учтены скидки.

  **Пожизненная ценность клиента (CLV)**: Сумма сумм всех выполненных заказов для данного клиента.

  **Заказы с высокой стоимостью**: Заказы с общей суммой > 1000

  ## Пример запроса

  — Получите список 10 лучших клиентов по выручке за последний квартал.
  ВЫБИРАТЬ
      c.customer_id,
      c.name,
      c.customer_tier,
      SUM(o.total_amount) as total_revenue
  ОТ клиентов c
  JOIN orders o ON c.customer_id = o.customer_id
  ГДЕ o.status = 'completed'
    И o.order_date >= CURRENT_DATE - INTERVAL '3 months'
  GROUP BY c.customer_id, c.name, c.customer_tier
  ORDER BY total_revenue DESC
  ОГРАНИЧЕНИЕ 10;
  """,
      },
      {
          "name": "inventory_management",
          «Описание»: «Схема базы данных и бизнес-логика для отслеживания запасов, включая товары, склады и уровни запасов».
          "content": """# Схема управления запасами

  ## Таблицы

  ### продукты
  - product_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - product_name
  - артикул
  - категория
  - unit_cost
  - reorder_point (минимальный уровень запасов перед повторным заказом)
  - прекращено (логическое значение)

  ### склады
  - warehouse_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - warehouse_name
  - расположение
  - емкость

  ### инвентарь
  - inventory_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - product_id (ВНЕШНИЙ КЛЮЧ -> products)
  - warehouse_id (ВНЕШНИЙ КЛЮЧ -> warehouses)
  - количество_в_наличии
  - last_updated

  ### движения_акций
  - movement_id (ПЕРВИЧНЫЙ КЛЮЧ)
  - product_id (ВНЕШНИЙ КЛЮЧ -> products)
  - warehouse_id (ВНЕШНИЙ КЛЮЧ -> warehouses)
  - movement_type (inbound/outbound/transfer/adjustment)
  - количество (положительное для входящих потоков, отрицательное для исходящих потоков)
  - movement_date
  - номер_ссылки

  ## Бизнес-логика

  **Доступный товар на складе**: quantity_on_hand из таблицы inventory, где quantity_on_hand > 0

  **Товары, требующие повторного заказа**: Товары, общее количество которых на складах меньше или равно точке повторного заказа данного товара.

  **Только активные товары**: Исключить товары, для которых "сняты с производства" = true, за исключением случаев, когда анализируются именно снятые с производства товары.

  **Оценка запасов**: количество_на_складе * себестоимость_единицы для каждого товара.

  ## Пример запроса

  — Найдите товары по цене ниже точки повторного заказа на всех складах.
  ВЫБИРАТЬ
      p.product_id,
      p.product_name,
      p.reorder_point,
      SUM(i.quantity_on_hand) as total_stock,
      p.unit_cost,
      (p.reorder_point - SUM(i.quantity_on_hand)) as units_to_reorder
  ОТ продуктов p
  JOIN inventory i ON p.product_id = i.product_id
  ГДЕ p.discontinued = false
  GROUP BY p.product_id, p.product_name, p.reorder_point, p.unit_cost
  ДАЛИ SUM(i.quantity_on_hand) <= p.reorder_point
  ORDER BY units_to_reorder DESC;
  """,
      },
  ]

  # Создание инструмента загрузки навыков
  @инструмент
  def load_skill(skill_name: str) -> str:
      """Загрузить полное содержимое навыка в контекст агента."

      Используйте это, когда вам нужна подробная информация о том, как поступить в конкретной ситуации.
      это тип запроса. Это предоставит вам подробные инструкции.
      политика и руководящие принципы в данной области навыков.

      Аргументы:
          skill_name: Название загружаемого навыка (например, "sales_analytics", "inventory_management")
      """
      # Найти и вернуть запрошенный навык
      для развития навыков:
          если skill["name"] == skill_name:
              return f"Загружен навык: {skill_name}\n\n{skill['content']}"

      # Навык не найден
      available = ", ".join(s["name"] for s in SKILLS)
      return f"Навык '{skill_name}' не найден. Доступные навыки: {available}"

  # Создание промежуточного ПО для навыков
  класс SkillMiddleware(AgentMiddleware):
      «Промежуточное программное обеспечение, которое внедряет описания навыков в системную подсказку».

      # Зарегистрируйте инструмент load_skill в качестве переменной класса
      инструменты = [load_skill]

      def __init__(self):
          """Инициализируйте и сгенерируйте запрос на ввод навыков из раздела "НАВЫКИ".""
          # Создайте подсказку по навыкам из списка НАВЫКОВ
          skills_list = []
          для развития навыков:
              skills_list.append(
                  f"- **{skill['name']}**: {skill['description']}"
              )
          self.skills_prompt = "\n".join(skills_list)

      def wrap_model_call(
          себя,
          запрос: ModelRequest,
          обработчик: Callable[[ModelRequest], ModelResponse],
      ) -> ModelResponse:
          «Синхронизация: Вставить описания навыков в системную подсказку».
          # Создать дополнение к описанию навыков
          skills_addentum = (
              f"\n\n## Доступные навыки\n\n{self.skills_prompt}\n\n"
              Используйте инструмент load_skill, когда вам нужна подробная информация.
              «О обработке запросов определенного типа».
          )

          # Добавить к блокам содержимого системных сообщений
          new_content = list(request.system_message.content_blocks) + [
              {"type": "text", "text": skills_addenum}
          ]
          new_system_message = SystemMessage(content=new_content)
          modified_request = request.override(system_message=new_system_message)
          return handler(modified_request)

  # Инициализируйте вашу модель чата (замените на вашу модель)
  # Пример: from langchain_anthropic import ChatAnthropic
  # model = ChatAnthropic(model="claude-3-5-sonnet-20241022")
  from langchain_openai import ChatOpenAI
  model = ChatOpenAI(model="gpt-4")

  # Создание агента с поддержкой навыков
  агент = create_agent(
      модель,
      system_prompt=(
          «Вы — помощник по SQL-запросам, который помогает пользователям».
          «Напишите запросы к бизнес-базам данных».
      ),
      промежуточное ПО=[SkillMiddleware()],
      checkpointer=InMemorySaver(),
  )

  # Пример использования
  если __name__ == "__main__":
      # Настройки для этой ветки обсуждения
      thread_id = str(uuid.uuid4())
      config = {"configurable": {"thread_id": thread_id}}

      # Запрос SQL-запроса
      результат = agent.invoke(
          {
              "сообщения": [
                  {
                      "роль": "пользователь",
                      "содержание": (
                          «Напишите SQL-запрос для поиска всех клиентов».
                          "которые сделали заказы на сумму более 1000 долларов за последний месяц"
                      ),
                  }
              ]
          },
          конфигурация
      )

      # Вывести переписку
      for message in result["messages"]:
          if hasattr(message, 'pretty_print'):
              message.pretty_print()
          еще:
              print(f"{message.type}: {message.content}")
  ```

  В этот полный пример включено:

  * Определения навыков с полными схемами баз данных
  * Инструмент `load_skill` для загрузки по запросу
  * `SkillMiddleware`, который внедряет описания навыков в системную подсказку.
  * Создание агента с использованием промежуточного ПО и контрольных точек
  * Пример использования, демонстрирующий, как агент загружает навыки и пишет SQL-запросы.

  Для запуска этого вам потребуется:

  1. Установите необходимые пакеты: `pip install langchain langchain-openai langgraph`
  2. Укажите свой API-ключ (например, `export OPENAI_API_KEY=...`)
  3. Замените инициализацию модели на искомого вами поставщика LLM.
</Аккордеон>

## Варианты реализации

<Заголовок аккордеона: "Просмотр вариантов реализации и компромиссов">
  В этом руководстве навыки реализованы в виде словарей Python, хранящихся в памяти и загружаемых с помощью вызовов инструментов. Однако существует несколько способов реализации поэтапного раскрытия информации с помощью навыков:

  **Системы хранения данных:**

  * **Работа в оперативной памяти** (в этом руководстве): Навыки определяются как структуры данных Python, быстрый доступ, отсутствие накладных расходов на ввод-вывод.
  * **Файловая система** (подход Клода): Навыки представлены в виде каталогов с файлами, которые обнаруживаются с помощью файловых операций, таких как `read_file`.
  * **Удаленное хранилище**: Навыки работы с S3, базами данных, Notion или API, доступные по запросу.

  **Обнаружение навыков** (способ, с помощью которого агент узнает, какие навыки существуют):

  * **Список системных подсказок**: Описания навыков в системной подсказке (используются в этом руководстве)
  * **Файловый подход**: Выявление навыков путем сканирования каталогов (подход, основанный на коде Клода)
  * **На основе реестра**: Запрос к сервису реестра навыков или API для получения информации о доступных навыках.
  * **Динамический поиск**: Список доступных навыков, вызываемый с помощью инструмента.

  **Стратегии поэтапного раскрытия информации** (способ загрузки содержательного материала):

  * **Единичная загрузка**: Загрузка всего содержимого навыка за один вызов инструмента (используется в этом руководстве)
  * **Постраничная навигация**: Загрузка содержимого навыков на нескольких страницах/фрагментах для больших объемов информации о навыках.
  * **Поиск на основе**: Поиск релевантных разделов в содержимом конкретного навыка (например, с использованием операций grep/read в файлах навыка)
  * **Иерархическая структура**: Сначала загрузите обзор навыков, затем перейдите к конкретным подразделам.

  **Учет размеров** (необоснованная мысленная модель — оптимизируйте под свою систему):

  * **Небольшие навыки** (< 1000 токенов / ~750 слов): Могут быть включены непосредственно в системную подсказку и кэшированы с помощью кэширования подсказок для экономии средств и более быстрого ответа.
  * **Средний уровень навыков** (1-10 тыс. токенов / ~750-7,5 тыс. слов): Воспользуйтесь возможностью загрузки по запросу, чтобы избежать излишней контекстной информации (этот учебник).
  * **Для больших объемов текста** (> 10 000 токенов / ~7 500 слов или > 5-10% контекстного окна): следует использовать методы постепенного раскрытия информации, такие как пагинация, загрузка на основе поиска или иерархическое исследование, чтобы избежать чрезмерного потребления контекста.

  Выбор зависит от ваших требований: хранение в оперативной памяти — самый быстрый вариант, но требует повторного развертывания для обновления навыков, в то время как файловое или удаленное хранилище позволяет динамически управлять навыками без изменения кода.
</Аккордеон>

## Прогрессивное раскрытие информации и контекстная инженерия

<Заголовок аккордеона: "Сочетание с использованием подсказок в течение нескольких попыток и другими методами">
  Постепенное раскрытие информации — это, по сути, метод **[контекстной инженерии](/oss/python/langchain/context-engineering)** — вы управляете тем, какая информация доступна агенту и когда. В этом руководстве основное внимание уделялось загрузке схем баз данных, но те же принципы применимы и к другим типам контекста.

  ### Сочетание с подсказками в течение нескольких попыток

  В случае использования SQL-запросов можно расширить механизм постепенного раскрытия информации, чтобы динамически загружать **несколько примеров**, соответствующих запросу пользователя:

  **Пример подхода:**

  1. Пользователь спрашивает: «Найти клиентов, которые не делали заказов в течение 6 месяцев»
  2. Агент загружает схему `sales_analytics` (как показано в этом руководстве).
  3. Агент также загружает 2-3 релевантных примера запросов (с помощью семантического поиска или поиска по тегам):
     * Запрос для поиска неактивных клиентов
     * Запрос с фильтрацией по дате
     * Запрос, объединяющий таблицы клиентов и заказов.
  4. Агент пишет запрос, используя как знания схемы, так и примеры шаблонов.

  Такое сочетание поэтапного раскрытия информации (загрузка схем по запросу) и динамического кратковременного запроса (загрузка релевантных примеров) создает мощный шаблон проектирования контекста, масштабируемый до больших баз знаний и обеспечивающий высококачественные, обоснованные результаты.
</Аккордеон>

## Следующие шаги

* Узнайте о [промежуточном ПО](/oss/python/langchain/middleware) для более динамичного поведения агентов.
* Изучите методы [контекстной инженерии](/oss/python/langchain/context-engineering) для управления контекстом агентов.
* Изучите шаблон [handoffs pattern](/oss/python/langchain/multi-agent/handoffs-customer-support) для последовательных рабочих процессов.
* Ознакомьтесь с шаблоном [subagents pattern](/oss/python/langchain/multi-agent/subagents-personal-assistant) для маршрутизации параллельных задач.
* См. [шаблоны многоагентных систем](/oss/python/langchain/multi-agent) для других подходов к специализированным агентам
* Используйте [LangSmith](https://smith.langchain.com) для отладки и мониторинга загрузки навыков.

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langchain/multi-agent/skills-sql-assistant.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Callout>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>