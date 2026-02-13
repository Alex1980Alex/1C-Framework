> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Настройка агентов глубокого доступа

Узнайте, как настраивать агентов с расширенными возможностями, используя системные подсказки, инструменты, субагентов и многое другое.

```тема русалки={null}
график LR
    Create[create_deep_agent] --> Core[Core Config]
    Создать --> Функции[Функции]

    Ядро --> Модель[Модель]
    Core --> Prompt[System Prompt]
    Ядро --> Инструменты[Инструменты]

    Функции --> Бэкенд[Бэкенд]
    Характеристики --> Подсубъекты
    Функции --> Прерывание[Прерывания]

    Модель --> Агент [Настраиваемый агент]
    Подсказка --> Агент
    Инструменты --> Агент
    Бэкенд --> Агент
    Суб-агент -->
    Прерывание --> Агент
```

## Модель

По умолчанию `deepagents` использует [`claude-sonnet-4-5-20250929`](https://platform.claude.com/docs/en/about-claude/models/overview). Вы можете настроить используемую модель, передав любую поддерживаемую строку идентификатора модели <Tooltip tip="Строка, соответствующая формату `provider:model` (например, openai:gpt-5)" cta="См. сопоставления" href="https://reference.langchain.com/python/langchain/models/#langchain.chat_models.init_chat_model(model)">или [объект модели LangChain](/oss/python/integrations/chat).

<Совет>
  Используйте формат `provider:model` (например, `openai:gpt-5`), чтобы быстро переключаться между моделями.
</Совет>

<CodeGroup>
  ```python Model string theme={null}
  from langchain.chat_models import init_chat_model
  from deepagents import create_deep_agent

  модель = init_chat_model(model="openai:gpt-5")
  agent = create_deep_agent(model=model)
  ```

  ```python LangChain model object theme={null}
  # оллама тянет ламу3.1
  from langchain_ollama import ChatOllama
  from langchain.chat_models import init_chat_model
  from deepagents import create_deep_agent

  модель = init_chat_model(
      model=ChatOllama(
          model="llama3.1",
          температура = 0,
          # другие параметры...
      )
  )
  agent = create_deep_agent(model=model)
  ```
</CodeGroup>

## Системная подсказка

Агенты Deep поставляются со встроенной системной командной строкой, созданной по образцу командной строки Клода Кода. Системная командная строка по умолчанию содержит подробные инструкции по использованию встроенного инструмента планирования, инструментов файловой системы и субагентов.

Каждый агент, настроенный под конкретный сценарий использования, должен включать в себя пользовательское системное уведомление, специфичное для этого сценария.

```python theme={null}
from deepagents import create_deep_agent

research_instructions = """\
Вы — опытный исследователь. Ваша работа заключается в проведении...
Проведите тщательное исследование, а затем напишите безупречный отчет.
"""

agent = create_deep_agent(
    system_prompt=research_instructions,
)
```

## Инструменты

В дополнение к предоставленным вами пользовательским инструментам, глубокие агенты включают в себя [встроенные инструменты](/oss/python/deepagents/overview#core-capabilities) для планирования, управления файлами и запуска подателей.

```python theme={null}
импорт os
from typing import Literal
from tavily import TavilyClient
from deepagents import create_deep_agent

tavily_client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])

def internet_search(
    запрос: str,
    max_results: int = 5,
    тема: Буквальный ["общий", "новости", "финансы"] = "общий",
    include_raw_content: bool = False,
):
    """Выполнить поиск в интернете"""
    return tavily_client.search(
        запрос,
        max_results=max_results,
        include_raw_content=include_raw_content,
        тема=тема,
    )

agent = create_deep_agent(
    инструменты=[интернет_поиск]
)
```

## Навыки

Вы можете использовать [skills](/oss/python/deepagents/overview), чтобы наделить своего глубокого агента новыми возможностями и экспертными знаниями.
В то время как [инструменты](/oss/python/deepagents/customization#tools) обычно охватывают функциональность более низкого уровня, например, действия с файловой системой или планирование, навыки могут содержать подробные инструкции по выполнению задач, справочную информацию и другие ресурсы, такие как шаблоны.
Эти файлы загружаются агентом только тогда, когда он определяет, что данный навык полезен для текущего запроса.
Поэтапное раскрытие информации уменьшает количество токенов и контекста, которые агенту необходимо учитывать при запуске.

Примеры навыков см. в [Примеры навыков Deep Agent](https://github.com/langchain-ai/deepagentsjs/tree/main/examples/skills).

Чтобы добавить навыки к вашему глубокому агенту, передайте их в качестве аргумента функции `create_deep_agent`:

<Вкладки>
  <Tab title="StateBackend">
    ```python theme={null}
    из urllib.request импортировать urlopen
    from deepagents import create_deep_agent
    from langgraph.checkpoint.memory import MemorySaver

    checkpointer = MemorySaver()

    skill_url = "https://raw.githubusercontent.com/langchain-ai/deepagentsjs/refs/heads/main/examples/skills/langgraph-docs/SKILL.md"
    с ответом urlopen(skill_url):
        skill_content = response.read().decode('utf-8')

    skills_files = {
        "/skills/langgraph-docs/SKILL.md": skill_content
    }

    agent = create_deep_agent(
        навыки=["./skills/"],
        checkpointer=checkpointer,
    )

    результат = agent.invoke(
        {
            "сообщения": [
                {
                    "роль": "пользователь",
                    «Содержание»: «Что такое Langgraph?»
                }
            ],
            # Заполните файловую систему StateBackend по умолчанию (виртуальные пути должны начинаться с "/").
            "файлы": файлы навыков
        },
        config={"configurable": {"thread_id": "12345"}},
    )
    ```
  </Tab>

  <Tab title="StoreBackend">
    ```python theme={null}
    из urllib.request импортировать urlopen
    from deepagents import create_deep_agent
    from deepagents.backends import StoreBackend
    from langgraph.store.memory import InMemoryStore


    store = InMemoryStore()

    skill_url = "https://raw.githubusercontent.com/langchain-ai/deepagentsjs/refs/heads/main/examples/skills/langgraph-docs/SKILL.md"
    с ответом urlopen(skill_url):
        skill_content = response.read().decode('utf-8')

    store.put(
        namespace=("filesystem",),
        key="/skills/langgraph-docs/SKILL.md",
        значение=навык_содержание
    )

    agent = create_deep_agent(
        backend=(лямбда rt: StoreBackend(rt)),
        магазин=магазин,
        навыки=["./skills/"]
    )

    результат = agent.invoke(
        {
            "сообщения": [
                {
                    "роль": "пользователь",
                    «Содержание»: «Что такое Langgraph?»
                }
            ]
        },
        config={"configurable": {"thread_id": "12345"}},
    )
    ```
  </Tab>

  <Tab title="FilesystemBackend">
    ```python theme={null}
    from deepagents import create_deep_agent
    from langgraph.checkpoint.memory import MemorySaver
    from deepagents.backends.filesystem import FilesystemBackend

    # Для обеспечения участия человека в процессе необходима поддержка Checkpointer.
    checkpointer = MemorySaver()

    agent = create_deep_agent(
        backend=FilesystemBackend(root_dir="/Users/user/{project}"),
        skills=["/Users/user/{project}/skills/"],
        interrupt_on={
            "write_file": True, # По умолчанию: одобрить, отредактировать, отклонить
            "read_file": False, # Прерывания не требуются
            "edit_file": True # По умолчанию: утвердить, отредактировать, отклонить
        },
        checkpointer=checkpointer, # Обязательно!
    )

    результат = agent.invoke(
        {
            "сообщения": [
                {
                    "роль": "пользователь",
                    «Содержание»: «Что такое Langgraph?»
                }
            ]
        },
        config={"configurable": {"thread_id": "12345"}},
    )
    ```
  </Tab>
</Вкладки>

## Память

Используйте файлы [`AGENTS.md`](https://agents.md/), чтобы предоставить вашему агенту дополнительный контекст.

При создании агента глубокого обучения вы можете передать один или несколько путей к файлам в параметр `memory`:

<Вкладки>
  <Tab title="StateBackend">
    ```python theme={null}
    из urllib.request импортировать urlopen

    from deepagents import create_deep_agent
    from deepagents.backends.utils import create_file_data
    from langgraph.checkpoint.memory import MemorySaver

    с помощью urlopen("https://raw.githubusercontent.com/langchain-ai/deepagents/refs/heads/master/examples/text-to-sql-agent/AGENTS.md") в качестве ответа:
        agents_md = response.read().decode("utf-8")
    checkpointer = MemorySaver()

    agent = create_deep_agent(
        память=[
            "/AGENTS.md"
        ],
        checkpointer=checkpointer,
    )

    результат = agent.invoke(
        {
            "сообщения": [
                {
                    "роль": "пользователь",
                    "Содержание": "Пожалуйста, расскажите, что находится в ваших файлах памяти."
                }
            ],
            # Заполните файловую систему StateBackend по умолчанию (виртуальные пути должны начинаться с "/").
            "файлы": {"/AGENTS.md": create_file_data(agents_md)},
        },
        config={"configurable": {"thread_id": "123456"}},
    )
    ```
  </Tab>

  <Tab title="StoreBackend">
    ```python theme={null}
    из urllib.request импортировать urlopen

    from deepagents import create_deep_agent
    from deepagents.backends import StoreBackend
    from deepagents.backends.utils import create_file_data
    from langgraph.store.memory import InMemoryStore

    с помощью urlopen("https://raw.githubusercontent.com/langchain-ai/deepagents/refs/heads/master/examples/text-to-sql-agent/AGENTS.md") в качестве ответа:
        agents_md = response.read().decode("utf-8")

    # Создайте магазин и добавьте в него файл
    store = InMemoryStore()
    file_data = create_file_data(agents_md)
    store.put(
        namespace=("filesystem",),
        key="/AGENTS.md",
        значение=файл_данные
    )

    agent = create_deep_agent(
        backend=(лямбда rt: StoreBackend(rt)),
        магазин=магазин,
        память=[
            "/AGENTS.md"
        ]
    )

    результат = agent.invoke(
        {
            "сообщения": [
                {
                    "роль": "пользователь",
                    "Содержание": "Пожалуйста, расскажите, что находится в ваших файлах памяти."
                }
            ],
            "файлы": {"/AGENTS.md": create_file_data(agents_md)},
        },
        config={"configurable": {"thread_id": "12345"}},
    )
    ```
  </Tab>

  <Tab title="FilesystemBackend">
    ```python theme={null}
    from deepagents import create_deep_agent
    from langgraph.checkpoint.memory import MemorySaver
    from deepagents.backends import FilesystemBackend

    # Для обеспечения участия человека в процессе необходима поддержка Checkpointer.
    checkpointer = MemorySaver()

    agent = create_deep_agent(
        backend=FilesystemBackend(root_dir="/Users/user/{project}"),
        память=[
            "./AGENTS.md"
        ],
        interrupt_on={
            "write_file": True, # По умолчанию: одобрить, отредактировать, отклонить
            "read_file": False, # Прерывания не требуются
            "edit_file": True # По умолчанию: утвердить, отредактировать, отклонить
        },
        checkpointer=checkpointer, # Обязательно!
    )
    ```
  </Tab>
</Вкладки>

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/deepagents/customization.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Всплывающее сообщение>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>