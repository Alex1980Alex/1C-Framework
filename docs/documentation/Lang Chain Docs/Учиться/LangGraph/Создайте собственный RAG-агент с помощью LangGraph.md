> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Создание пользовательского агента RAG с помощью LangGraph

## Обзор

В этом уроке мы создадим агент для поиска информации с использованием LangGraph.

LangChain предлагает встроенные реализации агентов, реализованные с использованием примитивов LangGraph. Если требуется более глубокая настройка, агенты могут быть реализованы непосредственно в LangGraph. В этом руководстве показан пример реализации агента поиска. Агенты поиска полезны, когда вам нужно, чтобы LLM принимал решение о том, следует ли получать контекст из векторного хранилища или отвечать пользователю напрямую.

К концу урока мы выполним следующие действия:

1. Получение и предварительная обработка документов, которые будут использоваться для поиска.
2. Проиндексируйте эти документы для семантического поиска и создайте инструмент для поиска информации для агента.
3. Создайте агентную систему RAG, которая сможет определять, когда использовать инструмент извлечения.

<img src="https://mintcdn.com/langchain-5e9cc07a/I6RpA28iE233vhYX/images/langgraph-hybrid-rag-tutorial.png?fit=max&auto=format&n=I6RpA28iE233vhYX&q=85&s=855348219691485642b22a1419939ea7" alt="Hybrid RAG" data-og-width="1615" width="1615" data-og-height="589" height="589" data-path="images/langgraph-hybrid-rag-tutorial.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/I6RpA28iE233vhYX/images/langgraph-hybrid-rag-tutorial.png?w=280&fit=max&auto=format&n=I6RpA28iE233vhYX&q=85&s=09097cb9a1dc57b16d33f084641ea93f 280w, https://mintcdn.com/langchain-5e9cc07a/I6RpA28iE233vhYX/images/langgraph-hybrid-rag-tutori al.png?w=560&fit=max&auto=format&n=I6RpA28iE233vhYX&q=85&s=d0bf85cfa36ac7e1a905593a4688f2d2 560 Вт, https://mintcdn.com/langchain-5e9cc07a/I6RpA28iE233vhYX/images/langgraph-hybrid-rag-tutorial.png?w=840&fit=max&auto=format&n=I6RpA28iE233vhYX&q=85&s=b7626e6ae3cb94fb90a61e6fad69c8ba 840w, https://mintcdn.com/langchain-5e9cc07a/I6RpA28iE233vhYX/images/langgraph-hybrid-rag-tutorial.png?w=1100&fit=max&auto=format&n=I6RpA28iE233vhYX&q=85&s=2425baddda7209901bdde4425c23292c 1100w, https://mintcdn.com/langchain-5e9cc07a/I6RpA28iE233vhYX/images/langgraph-hybrid-rag-tutorial.png?w=1650&fit=max&auto=format&n=I6RpA28iE233vhYX&q=85&s=4e5f030034237589f651b704d0377a76 1650w, https://mintcdn.com/langchain-5e9cc07a/I6RpA28iE233vhYX/images/langgraph-hybrid-rag-tutorial.png?w=2500&fit=max&auto=format&n=I6RpA28iE233vhYX&q=85&s=3ec3c7c91fd2be4d749b1c267027ac1e 2500w" />

### Концепции

Мы рассмотрим следующие понятия:

* [Поиск информации](/oss/python/langchain/retrieval) с использованием [загрузчиков документов](/oss/python/integrations/document_loaders), [разделителей текста](/oss/python/integrations/splitters), [встраиваний](/oss/python/integrations/text_embedding) и [хранилищ векторов](/oss/python/integrations/vectorstores)
* LangGraph [Graph API](/oss/python/langgraph/graph-api), включая состояние, узлы, ребра и условные ребра.

## Настраивать

Давайте загрузим необходимые пакеты и настроим наши API-ключи:

```python theme={null}
pip install -U langgraph "langchain[openai]" langchain-community langchain-text-splitters bs4
```

```python theme={null}
импортировать getpass
импорт os


def _set_env(key: str):
    если ключ отсутствует в os.environ:
        os.environ[key] = getpass.getpass(f"{key}:")


_set_env("OPENAI_API_KEY")
```

<Совет>
  Зарегистрируйтесь в LangSmith, чтобы быстро выявлять проблемы и улучшать производительность ваших проектов LangGraph. [LangSmith](https://docs.smith.langchain.com) позволяет использовать данные трассировки для отладки, тестирования и мониторинга ваших приложений LLM, созданных с помощью LangGraph.
</Совет>

## 1. Предварительная обработка документов

1. Получение документов для использования в нашей системе RAG. Мы будем использовать три самые последние страницы из [прекрасного блога Лилиан Венг](https://lilianweng.github.io/). Начнем с получения содержимого страниц с помощью утилиты `WebBaseLoader`:

```python theme={null}
from langchain_community.document_loaders import WebBaseLoader

urls = [
    "https://lilianweng.github.io/posts/2024-11-28-reward-hacking/",
    "https://lilianweng.github.io/posts/2024-07-07-hallucination/",
    "https://lilianweng.github.io/posts/2024-04-12-diffusion-video/",
]

docs = [WebBaseLoader(url).load() for url in urls]
```

```python theme={null}
docs[0][0].page_content.strip()[:1000]
```

2. Разделите полученные документы на более мелкие фрагменты для индексации в нашем векторном хранилище:

```python theme={null}
from langchain_text_splitters import RecursiveCharacterTextSplitter

docs_list = [item for sublist in docs for item in sublist]

text_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
    chunk_size=100, chunk_overlap=50
)
doc_splits = text_splitter.split_documents(docs_list)
```

```python theme={null}
doc_splits[0].page_content.strip()
```

## 2. Создайте инструмент для извлечения данных

Теперь, когда у нас есть разделенные документы, мы можем проиндексировать их в векторном хранилище, которое будем использовать для семантического поиска.

1. Используйте хранилище векторов в оперативной памяти и эмбеддинги OpenAI:

```python theme={null}
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings

vectorstore = InMemoryVectorStore.from_documents(
    documents=doc_splits, embedding=OpenAIEmbeddings()
)
retriever = vectorstore.as_retriever()
```

2. Создайте инструмент для извлечения данных, используя декоратор `@tool`:

```python theme={null}
from langchain.tools import tool

@инструмент
def retrieve_blog_posts(query: str) -> str:
    «Найдите и получите информацию о сообщениях в блоге Лилиан Венг».
    docs = retriever.invoke(query)
    return "\n\n".join([doc.page_content for doc in docs])

retriever_tool = retrieve_blog_posts
```

3. Протестируйте инструмент:

```python theme={null}
retriever_tool.invoke({"query": "types of reward hacking"})
```

## 3. Сгенерировать запрос

Теперь мы начнём создавать компоненты ([узлы](/oss/python/langgraph/graph-api#nodes) и [рёбра](/oss/python/langgraph/graph-api#edges)) для нашего агентного RAG-графа.

Обратите внимание, что компоненты будут работать с [`MessagesState`](/oss/python/langgraph/graph-api#messagesstate) — состоянием графа, содержащим ключ `messages` со списком [сообщений чата](https://python.langchain.com/docs/concepts/messages/).

1. Создайте узел `generate_query_or_respond`. Он будет вызывать LLM для генерации ответа на основе текущего состояния графа (списка сообщений). Получив входные сообщения, он решит, использовать ли инструмент получения данных или ответить пользователю напрямую. Обратите внимание, что мы предоставляем модели чата доступ к созданному ранее инструменту `retriever_tool` через `.bind_tools`:

```python theme={null}
from langgraph.graph import MessagesState
from langchain.chat_models import init_chat_model

response_model = init_chat_model("gpt-4.1", temperature=0)


def generate_query_or_respond(state: MessagesState):
    """Вызовите модель для генерации ответа на основе текущего состояния. Дано
    В ответ на вопрос система решит, использовать ли инструмент поиска или просто ответить пользователю.
    """
    ответ = (
        response_model
        .bind_tools([retriever_tool]).invoke(state["messages"]) # [!code highlight]
    )
    return {"messages": [response]}
```

2. Попробуйте на случайном входном значении:

```python theme={null}
input = {"messages": [{"role": "user", "content": "hello!"}]}
generate_query_or_respond(input)["messages"][-1].pretty_print()
```

**Выход:**

```
================================ Сообщение Ai ================================

Здравствуйте! Чем я могу вам сегодня помочь?
```

3. Задайте вопрос, требующий семантического поиска:

```python theme={null}
ввод = {
    "сообщения": [
        {
            "роль": "пользователь",
            «Содержание»: «Что говорит Лилиан Венг о различных видах взлома системы вознаграждений?»
        }
    ]
}
generate_query_or_respond(input)["messages"][-1].pretty_print()
```

**Выход:**

```
================================ Сообщение Ai ================================
Вызовы инструментов:
retrieve_blog_posts (call_tYQxgfIlnQUDMdtAhdbXNwIM)
Идентификатор вызова: call_tYQxgfIlnQUDMdtAhdbXNwIM
Аргументы:
    запрос: виды взлома вознаграждений
```

## 4. Документы с оценками

1. Добавьте [условное ребро](/oss/python/langgraph/graph-api#conditional-edges) — `grade_documents` — чтобы определить, соответствуют ли полученные документы вопросу. Для оценки документов мы будем использовать модель со структурированной схемой вывода `GradeDocuments`. Функция `grade_documents` вернет имя узла, к которому следует перейти в зависимости от решения об оценке (`generate_answer` или `rewrite_question`):

```python theme={null}
from pydantic import BaseModel, Field
from typing import Literal

GRADE_PROMPT = (
    «Вы — эксперт, оценивающий соответствие полученного документа вопросу пользователя.»
    "Вот полученный документ: \n\n {контекст} \n\n"
    «Вот вопрос пользователя: {вопрос} \n»
    Если документ содержит ключевые слова или семантическое значение, относящиеся к вопросу пользователя, оцените его как релевантный.
    "Присвойте документу бинарную оценку «да» или «нет», чтобы указать, относится ли он к вопросу."
)


class GradeDocuments(BaseModel): # [!подсветка кода]
    «Оценивайте документы, используя бинарную шкалу для проверки релевантности».

    binary_score: str = Field(
        description="Оценка релевантности: 'да', если релевантно, или 'нет', если не релевантно"
    )


grader_model = init_chat_model("gpt-4.1", temperature=0)


def grade_documents(
    состояние: MessagesState,
) -> Literal["generate_answer", "rewrite_question"]:
    «Определите, имеют ли полученные документы отношение к заданному вопросу».
    вопрос = состояние["сообщения"][0].контент
    контекст = состояние["сообщения"][-1].контент

    prompt = GRADE_PROMPT.format(question=question, context=context)
    ответ = (
        grader_model
        .with_structured_output(GradeDocuments).invoke( # [!code highlight]
            [{"role": "user", "content": prompt}]
        )
    )
    score = response.binary_score

    если оценка == "да":
        return "generate_answer"
    еще:
        return "rewrite_question"
```

2. Запустите это, используя в ответе инструмента нерелевантные документы:

```python theme={null}
from langchain_core.messages import convert_to_messages

ввод = {
    "messages": convert_to_messages(
        [
            {
                "роль": "пользователь",
                «Содержание»: «Что говорит Лилиан Венг о различных видах взлома системы вознаграждений?»
            },
            {
                "роль": "ассистент",
                "содержание": "",
                "tool_calls": [
                    {
                        "id": "1",
                        "name": "retrieve_blog_posts",
                        "args": {"query": "types of reward hacking"},
                    }
                ],
            },
            {"role": "tool", "content": "meow", "tool_call_id": "1"},
        ]
    )
}
grade_documents(input)
```

3. Убедитесь, что соответствующие документы классифицированы следующим образом:

```python theme={null}
ввод = {
    "messages": convert_to_messages(
        [
            {
                "роль": "пользователь",
                «Содержание»: «Что говорит Лилиан Венг о различных видах взлома системы вознаграждений?»
            },
            {
                "роль": "ассистент",
                "содержание": "",
                "tool_calls": [
                    {
                        "id": "1",
                        "name": "retrieve_blog_posts",
                        "args": {"query": "types of reward hacking"},
                    }
                ],
            },
            {
                "роль": "инструмент",
                «Содержание»: «Взлом системы вознаграждений можно разделить на два типа: неправильное определение среды или цели и подделка системы вознаграждений».
                "tool_call_id": "1",
            },
        ]
    )
}
grade_documents(input)
```

## 5. Переформулируйте вопрос

1. Создайте узел `rewrite_question`. Инструмент поиска может возвращать потенциально нерелевантные документы, что указывает на необходимость улучшения исходного вопроса пользователя. Для этого мы вызовем узел `rewrite_question`:

```python theme={null}
from langchain.messages import HumanMessage

REWRITE_PROMPT = (
    «Проанализируйте входные данные и попытайтесь понять их семантический смысл/намерение».
    «Вот первоначальный вопрос:»
    "\n ------- \n"
    "{вопрос}"
    "\n ------- \n"
    «Сформулируйте более точный вопрос:»
)


def rewrite_question(state: MessagesState):
    «Переформулируйте исходный вопрос пользователя».
    сообщения = состояние["сообщения"]
    вопрос = сообщения[0].контент
    prompt = REWRITE_PROMPT.format(question=question)
    response = response_model.invoke([{"role": "user", "content": prompt}])
    return {"messages": [HumanMessage(content=response.content)]}
```

2. Попробуйте:

```python theme={null}
ввод = {
    "messages": convert_to_messages(
        [
            {
                "роль": "пользователь",
                «Содержание»: «Что говорит Лилиан Венг о различных видах взлома системы вознаграждений?»
            },
            {
                "роль": "ассистент",
                "содержание": "",
                "tool_calls": [
                    {
                        "id": "1",
                        "name": "retrieve_blog_posts",
                        "args": {"query": "types of reward hacking"},
                    }
                ],
            },
            {"role": "tool", "content": "meow", "tool_call_id": "1"},
        ]
    )
}

response = rewrite_question(input)
print(response["messages"][-1].content)
```

**Выход:**

```
Какие существуют различные типы взлома системы вознаграждений, описанные Лилиан Вэн, и как она их объясняет?
```

## 6. Сгенерируйте ответ

1. Создайте узел `generate_answer`: если мы пройдем проверку оценщика, мы сможем сгенерировать окончательный ответ на основе исходного вопроса и полученного контекста:

```python theme={null}
GENERATE_PROMPT = (
    «Вы являетесь помощником в задачах по ответам на вопросы».
    «Используйте следующие фрагменты полученной информации, чтобы ответить на вопрос».
    «Если вы не знаете ответа, просто скажите, что не знаете».
    «Ответ должен состоять максимум из трех предложений и быть кратким».
    "Вопрос: {вопрос} \n"
    "Контекст: {контекст}"
)


def generate_answer(state: MessagesState):
    """Сгенерируйте ответ.""
    вопрос = состояние["сообщения"][0].контент
    контекст = состояние["сообщения"][-1].контент
    prompt = GENERATE_PROMPT.format(question=question, context=context)
    response = response_model.invoke([{"role": "user", "content": prompt}])
    return {"messages": [response]}
```

2. Попробуйте:

```python theme={null}
ввод = {
    "messages": convert_to_messages(
        [
            {
                "роль": "пользователь",
                «Содержание»: «Что говорит Лилиан Венг о различных видах взлома системы вознаграждений?»
            },
            {
                "роль": "ассистент",
                "содержание": "",
                "tool_calls": [
                    {
                        "id": "1",
                        "name": "retrieve_blog_posts",
                        "args": {"query": "types of reward hacking"},
                    }
                ],
            },
            {
                "роль": "инструмент",
                «Содержание»: «Взлом системы вознаграждений можно разделить на два типа: неправильное определение среды или цели и подделка системы вознаграждений».
                "tool_call_id": "1",
            },
        ]
    )
}

response = generate_answer(input)
response["messages"][-1].pretty_print()
```

**Выход:**

```
================================ Сообщение Ai ================================

Лилиан Вэн делит взлом системы вознаграждений на два типа: неправильное определение среды или цели и подтасовка вознаграждения. Она рассматривает взлом системы вознаграждений как широкое понятие, включающее обе эти категории. Взлом системы вознаграждений происходит, когда агент использует недостатки или неоднозначности в функции вознаграждения для получения высоких вознаграждений, не выполняя при этом запланированных действий.
```

## 7. Соберите график

Теперь мы соберем все узлы и ребра в полный граф:

* Начнём с вызова `generate_query_or_respond` и определим, нужно ли вызывать `retriever_tool`.
* Переход к следующему шагу с использованием `tools_condition`:
  * Если `generate_query_or_respond` вернул `tool_calls`, вызовите `retriever_tool` для получения контекста.
  * В противном случае, отвечайте пользователю напрямую.
* Оцените содержание полученного документа на предмет соответствия вопросу («grade_documents») и перейдите к следующему шагу:
  * Если это неактуально, переформулируйте вопрос, используя `rewrite_question`, а затем снова вызовите `generate_query_or_respond`.
  * При необходимости перейдите к `generate_answer` и сгенерируйте окончательный ответ, используя [`ToolMessage`](https://reference.langchain.com/python/langchain/messages/#langchain.messages.ToolMessage) с контекстом полученного документа.

```python theme={null}
from langgraph.graph import StateGraph, START, END
из langgraph.prebuilt импорт ToolNode, Tools_condition

рабочий процесс = StateGraph(MessagesState)

# Определяем узлы, между которыми мы будем циклически переключаться
workflow.add_node(generate_query_or_respond)
workflow.add_node("retrieve", ToolNode([retriever_tool]))
workflow.add_node(rewrite_question)
workflow.add_node(generate_answer)

workflow.add_edge(START, "generate_query_or_respond")

# Решите, следует ли извлекать данные
workflow.add_conditional_edges(
    "generate_query_or_respond",
    # Оценить решение LLM (вызвать инструмент `retriever_tool` или ответить пользователю)
    tools_condition,
    {
        # Преобразуем выходные данные условий в узлы нашего графа
        "инструменты": "извлечь",
        КОНЕЦ: КОНЕЦ,
    },
)

# Ребра, полученные после вызова узла `action`.
workflow.add_conditional_edges(
    "забрать",
    # Оценка решения агента
    grade_documents,
)
workflow.add_edge("generate_answer", END)
workflow.add_edge("rewrite_question", "generate_query_or_respond")

# Компиляция
graph = workflow.compile()
```

Визуализируйте график:

```python theme={null}
from IPython.display import Image, display

display(Image(graph.get_graph().draw_mermaid_png())
```

<img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/agentic-rag-output.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=ddedbd57514888e614ece260092201df" alt="SQL agent graph" style={{ height: "800px" }} data-og-width="1245" width="1245" data-og-height="1395" height="1395" data-path="oss/images/agentic-rag-output.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/agentic-rag-output.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=e8ade9698046fa97bd4600ffc0ee2ffd 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/agentic-rag-output.png?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=67cd8edf5fac7f5a2d23cc4aadaecd20 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/agentic-rag-output.p ng?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=7c415b76149654aeec54f321e199e5b2 840 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/agentic-rag-output.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=0c7527bf22c7378c2001fba2bbc3ebad 1100w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/agentic-rag-output.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=194746e6bf4e46aaadcf32b8f941a736 1650w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/agentic-rag-output.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=952697cbb31285db207d11a075a2167f 2500w" />

## 8. Запустите агентический RAG

Теперь давайте проверим весь граф, запустив его с помощью вопроса:

```python theme={null}
for chunk in graph.stream(
    {
        "сообщения": [
            {
                "роль": "пользователь",
                «Содержание»: «Что говорит Лилиан Венг о различных видах взлома системы вознаграждений?»
            }
        ]
    }
):
    Для узла выполните обновление в методе chunk.items():
        print("Обновление от узла", node)
        update["messages"][-1].pretty_print()
        print("\n\n")
```

**Выход:**

```
Обновление из узла generate_query_or_respons
================================ Сообщение Ai ================================
Вызовы инструментов:
  retrieve_blog_posts (call_NYu2vq4km9nNNEFqJwefWKu1)
 Идентификатор вызова: call_NYu2vq4km9nNNEFqJwefWKu1
  Аргументы:
    запрос: виды взлома вознаграждений



Обновление из узла получения
================================= Сообщение инструмента ==================================
Название: retrieve_blog_posts

(Примечание: В некоторых работах подтасовка вознаграждения определяется как отдельная категория поведения, нарушающего согласованность, и отличается от взлома системы вознаграждения. Но я рассматриваю взлом системы вознаграждения как более широкое понятие.)
В общих чертах, взлом системы вознаграждений можно разделить на два типа: неправильное определение среды или цели и фальсификация системы вознаграждений.

Зачем существует взлом системы вознаграждений?

Пан и др. (2022) исследовали взлом системы вознаграждений как функцию возможностей агента, включая (1) размер модели, (2) разрешение пространства действий, (3) шум в пространстве наблюдений и (4) время обучения. Они также предложили таксономию трех типов неправильно заданных прокси-вознаграждений:

Давайте определим, что такое взлом системы вознаграждений.
Формирование вознаграждения в обучении с подкреплением представляет собой сложную задачу. Взлом системы вознаграждения происходит, когда агент обучения с подкреплением использует недостатки или неоднозначности в функции вознаграждения для получения высоких вознаграждений, не изучив должным образом желаемое поведение и не выполнив задачу так, как было задумано. В последние годы было предложено несколько связанных концепций, все они относятся к той или иной форме взлома системы вознаграждения:



Обновление из узла generate_answer
================================ Сообщение Ai ================================

Лилиан Вэн делит взлом системы вознаграждений на два типа: неправильное определение среды или цели и подтасовка вознаграждения. Она рассматривает взлом системы вознаграждений как широкое понятие, включающее обе эти категории. Взлом системы вознаграждений происходит, когда агент использует недостатки или неоднозначности в функции вознаграждения для получения высоких вознаграждений, не выполняя при этом запланированных действий.
```

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langgraph/agentic-rag.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Callout>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>