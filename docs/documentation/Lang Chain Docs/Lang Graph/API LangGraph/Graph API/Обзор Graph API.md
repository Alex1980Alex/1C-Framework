> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Обзор Graph API

## Графики

В основе LangGraph лежит моделирование рабочих процессов агентов в виде графов. Вы определяете поведение своих агентов, используя три ключевых компонента:

1. [`State`](#state): Общая структура данных, представляющая текущий снимок вашего приложения. Она может быть любого типа данных, но обычно определяется с помощью общей схемы состояния.

2. [`Узлы`](#nodes): Функции, которые кодируют логику ваших агентов. Они получают текущее состояние в качестве входных данных, выполняют некоторые вычисления или побочные эффекты и возвращают обновленное состояние.

3. [`Ребра`](#edges): Функции, определяющие, какой `Узел` следует выполнить следующим в зависимости от текущего состояния. Они могут быть условными переходами или фиксированными переходами.

Составляя комбинации `узлов` и ​​`ребер`, вы можете создавать сложные циклические рабочие процессы, в которых состояние изменяется со временем. Однако настоящая мощь заключается в том, как LangGraph управляет этим состоянием.

Подчеркну: «Узлы» и «Ребра» — это не что иное, как функции — они могут содержать LLM или просто старый добрый код.

Короче говоря: *узлы выполняют работу, ребра указывают, что делать дальше*.

В основе алгоритма обработки графов LangGraph лежит [передача сообщений](https://en.wikipedia.org/wiki/Message_passing) для определения общей программы. Когда узел завершает свою операцию, он отправляет сообщения по одному или нескольким ребрам другим узлам. Затем эти узлы-получатели выполняют свои функции, передают полученные сообщения следующему набору узлов, и процесс продолжается. Вдохновленная системой Google [Pregel](https://research.google/pubs/pregel-a-system-for-large-scale-graph-processing/), программа выполняется дискретными «супершагами».

Супершаг можно рассматривать как одну итерацию по узлам графа. Узлы, работающие параллельно, являются частью одного и того же супершага, тогда как узлы, работающие последовательно, относятся к разным супершагам. В начале выполнения графа все узлы находятся в «неактивном» состоянии. Узел становится «активным», когда получает новое сообщение (состояние) по любому из своих входящих ребер (или «каналов»). Затем активный узел выполняет свою функцию и отвечает обновлениями. В конце каждого супершага узлы, не имеющие входящих сообщений, голосуют за «остановку», помечая себя как «неактивные». Выполнение графа завершается, когда все узлы становятся «неактивными» и нет сообщений в пути.

### StateGraph

Класс [`StateGraph`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph) является основным классом для работы с графами. Он параметризуется определяемым пользователем объектом `State`.

### Составление графика

Для построения графа сначала определяется состояние (#state), затем добавляются узлы (#nodes) и ребра (#edges), после чего граф компилируется. Что именно подразумевается под компиляцией графа и зачем она нужна?

Компиляция — довольно простой шаг. Она выполняет несколько базовых проверок структуры вашего графа (отсутствие «осиротевших» узлов и т. д.). Здесь же можно указать аргументы времени выполнения, такие как [контрольные точки](/oss/python/langgraph/persistence) и точки останова. Компиляция графа осуществляется простым вызовом метода `.compile`:

```python theme={null}
graph = graph_builder.compile(...)
```

<Предупреждение>
  Вы ОБЯЗАТЕЛЬНО должны составить свой график, прежде чем сможете его использовать.
</Предупреждение>

## Состояние

Первое, что вы делаете при определении графа, — это определяете его состояние. Состояние состоит из [схемы графа](#schema), а также [функций-редукторов](#reducers), которые определяют, как применять обновления к состоянию. Схема состояния будет входной схемой для всех узлов и ребер графа и может представлять собой либо типизированный словарь (TypedDict), либо пидантический словарь (Pydantic). Все узлы будут генерировать обновления состояния, которые затем применяются с помощью указанной функции-редуктора.

Схема

Основной документированный способ задания схемы графа — использование [`TypedDict`](https://docs.python.org/3/library/typing.html#typing.TypedDict). Если вы хотите задать значения по умолчанию для состояния, используйте [`dataclass`](https://docs.python.org/3/library/dataclasses.html). Мы также поддерживаем использование Pydantic [`BaseModel`](/oss/python/langgraph/use-graph-api#use-pydantic-models-for-graph-state) в качестве состояния графа, если вам нужна рекурсивная проверка данных (хотя следует отметить, что Pydantic менее производительен, чем `TypedDict` или `dataclass`).

По умолчанию граф будет иметь одинаковые схемы ввода и вывода. Если вы хотите это изменить, вы также можете указать схемы ввода и вывода напрямую. Это полезно, когда у вас много ключей, и некоторые из них явно предназначены для ввода, а другие — для вывода. Дополнительную информацию см. в [руководстве](/oss/python/langgraph/use-graph-api#define-input-and-output-schemas).

#### Множественные схемы

Как правило, все узлы графа взаимодействуют по одной схеме. Это означает, что они будут читать и записывать данные в одни и те же каналы состояния. Но бывают случаи, когда нам нужен больший контроль над этим:

* Внутренние узлы могут передавать информацию, которая не требуется на входе/выходе графа.
* Также может потребоваться использовать различные схемы ввода/вывода для графа. Например, выходные данные могут содержать только один релевантный ключ.

Можно настроить узлы таким образом, чтобы они записывали данные в закрытые каналы состояния внутри графа для внутренней связи между узлами. Для этого достаточно определить закрытую схему `PrivateState`.

Также можно определить явные схемы ввода и вывода для графа. В этих случаях мы определяем «внутреннюю» схему, содержащую *все* ключи, относящиеся к операциям с графом. Но мы также определяем схемы ввода и вывода, которые являются подмножествами «внутренней» схемы, чтобы ограничить ввод и вывод графа. Подробнее см. [это руководство](/oss/python/langgraph/graph-api#define-input-and-output-schemas).

Рассмотрим пример:

```python theme={null}
class InputState(TypedDict):
    user_input: str

class OutputState(TypedDict):
    graph_output: str

class OverallState(TypedDict):
    foo: str
    user_input: str
    graph_output: str

class PrivateState(TypedDict):
    бар: стр

def node_1(state: InputState) -> OverallState:
    # Запись в OverallState
    return {"foo": state["user_input"] + " name"}

def node_2(state: OverallState) -> PrivateState:
    # Чтение из OverallState, запись в PrivateState
    return {"bar": state["foo"] + " is"}

def node_3(state: PrivateState) -> OutputState:
    # Чтение из PrivateState, запись в OutputState
    return {"graph_output": state["bar"] + " Lance"}

builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_node("node_3", node_3)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
builder.add_edge("node_2", "node_3")
builder.add_edge("node_3", END)

graph = builder.compile()
graph.invoke({"user_input":"My"})
# {'graph_output': 'Меня зовут Лэнс'}
```

Здесь следует отметить два важных, но важных момента:

1. Мы передаем `state: InputState` в качестве входной схемы `node_1`. Но при этом мы записываем данные в `foo`, канал в `OverallState`. Как можно записывать данные в канал состояния, который не включен во входную схему? Это происходит потому, что узел *может записывать данные в любой канал состояния в графе*. Граф состояния представляет собой объединение каналов состояния, определенных при инициализации, включая `OverallState` и фильтры `InputState` и `OutputState`.

2. Мы инициализируем граф следующим образом:

   ```python theme={null}
   StateGraph(
       В целом, штат
       input_schema=InputState,
       output_schema=OutputState
   )
   ```

   Итак, как же мы можем записывать данные в `PrivateState` в `node_2`? Как граф получает доступ к этой схеме, если она не была передана при инициализации `StateGraph`?

   Мы можем это сделать, потому что `_nodes` также могут объявлять дополнительные `каналы_` состояния, если существует определение схемы состояния. В данном случае схема `PrivateState` определена, поэтому мы можем добавить `bar` в качестве нового канала состояния в граф и записывать в него данные.

### Редукторы

Редукторы играют ключевую роль в понимании того, как обновления от узлов применяются к `State`. Каждый ключ в `State` имеет свою собственную независимую функцию редуктора. Если функция редуктора явно не указана, предполагается, что все обновления этого ключа должны переопределять её. Существует несколько различных типов редукторов, начиная с редуктора по умолчанию:

#### Редуктор по умолчанию

Эти два примера демонстрируют, как использовать редуктор по умолчанию:

Пример на Python: theme={null}
from typing_extensions import TypedDict

class State(TypedDict):
    foo: int
    bar: list[str]
```

В этом примере для каждого ключа не указаны функции-редукторы. Предположим, что входными данными для графа являются:

`{"foo": 1, "bar": ["hi"]}`. Предположим, что первый `Узел` возвращает `{"foo": 2}`. Это рассматривается как обновление состояния. Обратите внимание, что `Узел` не обязан возвращать всю схему `State` — только обновление. После применения этого обновления `State` будет `{"foo": 2, "bar": ["hi"]}`. Если второй узел возвращает `{"bar": ["bye"]}`, то `State` будет `{"foo": 2, "bar": ["bye"]}`.

Пример Python B theme={null}
from typing import Annotated
from typing_extensions import TypedDict
из оператора импорт добавить

class State(TypedDict):
    foo: int
    bar: Annotated[list[str], add]
```

В этом примере мы использовали тип `Annotated` для указания функции редуктора (`operator.add`) для второго ключа (`bar`). Обратите внимание, что первый ключ остается неизменным. Предположим, что входными данными для графа являются `{"foo": 1, "bar": ["hi"]}`. Тогда предположим, что первый `Node` возвращает `{"foo": 2}`. Это рассматривается как обновление состояния. Обратите внимание, что `Node` не обязательно должен возвращать всю схему `State` — только обновление. После применения этого обновления `State` будет `{"foo": 2, "bar": ["hi"]}`. Если второй узел возвращает `{"bar": ["bye"]}`, то `State` будет `{"foo": 2, "bar": ["hi", "bye"]}`. Обратите внимание, что ключ `bar` обновляется путем сложения двух списков.

#### Перезапись

<Совет>
  В некоторых случаях может потребоваться обойти редуктор и напрямую перезаписать значение состояния. LangGraph предоставляет для этой цели тип [`Overwrite`](https://reference.langchain.com/python/langgraph/types/). [Узнайте, как использовать `Overwrite` здесь](/oss/python/langgraph/use-graph-api#bypass-reducers-with-overwrite).
</Совет>

### Работа с сообщениями в состоянии графа

#### Зачем использовать сообщения?

Большинство современных поставщиков LLM-систем имеют интерфейс модели чата, который принимает список сообщений в качестве входных данных. В частности, [интерфейс модели чата](/oss/python/langchain/models) LangChain принимает список объектов сообщений в качестве входных данных. Эти сообщения поступают в различных формах, таких как [`HumanMessage`](https://reference.langchain.com/python/langchain/messages/#langchain.messages.HumanMessage) (ввод пользователя) или [`AIMessage`](https://reference.langchain.com/python/langchain/messages/#langchain.messages.AIMessage) (ответ LLM-системы).

Чтобы узнать больше о том, что такое объекты сообщений, обратитесь к [концептуальному руководству по сообщениям](/oss/python/langchain/messages).

#### Использование сообщений в вашем графе

Во многих случаях полезно хранить историю предыдущих разговоров в виде списка сообщений в состоянии графа. Для этого можно добавить в состояние графа ключ (канал), который хранит список объектов `Message`, и аннотировать его функцией-редуктором (см. ключ `messages` в примере ниже). Функция-редуктор крайне важна для того, чтобы указать графу, как обновлять список объектов `Message` в состоянии при каждом обновлении состояния (например, когда узел отправляет обновление). Если вы не укажете редуктор, каждое обновление состояния будет перезаписывать список сообщений самым последним предоставленным значением. Если вы хотите просто добавить сообщения к существующему списку, вы можете использовать `operator.add` в качестве редуктора.

Однако, возможно, вам также потребуется вручную обновлять сообщения в состоянии графа (например, в режиме "человек в цикле"). Если вы используете `operator.add`, то отправленные вами вручную обновления состояния будут добавляться к существующему списку сообщений, а не обновлять уже существующие сообщения. Чтобы этого избежать, вам нужен редуктор, который может отслеживать идентификаторы сообщений и перезаписывать существующие сообщения при их обновлении. Для этого вы можете использовать встроенную функцию [`add_messages`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.message.add_messages). Для совершенно новых сообщений она просто добавит их к существующему списку, но также корректно обработает обновления для уже существующих сообщений.

#### Сериализация

Помимо отслеживания идентификаторов сообщений, функция [`add_messages`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.message.add_messages) также попытается десериализовать сообщения в объекты LangChain `Message` всякий раз, когда в канале `messages` будет получено обновление состояния.

Более подробную информацию о сериализации/десериализации в LangChain можно найти [здесь](https://python.langchain.com/docs/how_to/serialization/). Это позволяет отправлять входные данные графа / обновления состояния в следующем формате:

```python theme={null}
# Это поддерживается
{"messages": [HumanMessage(content="message")]}

# и это также поддерживается
{"messages": [{"type": "human", "content": "message"}]}
```

Поскольку обновления состояния всегда десериализуются в объекты LangChain `Messages` при использовании [`add_messages`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.message.add_messages), для доступа к атрибутам сообщений следует использовать точечную нотацию, например `state["messages"][-1].content`.

Ниже приведён пример графа, в котором в качестве функции-редуктора используется [`add_messages`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.message.add_messages).

```python theme={null}
from langchain.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing import Annotated
from typing_extensions import TypedDict

class GraphState(TypedDict):
    сообщения: Аннотированные[список[AnyMessage], add_messages]
```

#### MessagesState

Поскольку наличие списка сообщений в состоянии является распространенной практикой, существует встроенное состояние под названием `MessagesState`, которое упрощает использование сообщений. `MessagesState` определяется с помощью одного ключа `messages`, представляющего собой список объектов `AnyMessage`, и использует редуктор [`add_messages`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.message.add_messages). Как правило, отслеживается не только состояние, но и другие данные, поэтому мы видим, как люди создают подклассы этого состояния и добавляют дополнительные поля, например:

```python theme={null}
from langgraph.graph import MessagesState

class State(MessagesState):
    документы: список[str]
```

## Узлы

В LangGraph узлы представляют собой функции Python (синхронные или асинхронные), которые принимают следующие аргументы:

1. `state` – Состояние графа (#state).
2. `config` – объект [`RunnableConfig`](https://reference.langchain.com/python/langchain_core/runnables/#langchain_core.runnables.RunnableConfig), содержащий информацию о конфигурации, такую ​​как `thread_id`, и информацию о трассировке, такую ​​как `tags`.
3. `runtime` – объект `Runtime`, содержащий [контекст времени выполнения`](#runtime-context) и другую информацию, такую ​​как `store` и `stream_writer`.

Аналогично `NetworkX`, вы добавляете эти узлы в граф с помощью метода [`add_node`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_node):

```python theme={null}
from dataclasses import dataclass
from typing_extensions import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.runtime import Runtime

class State(TypedDict):
    ввод: строка
    результаты: стр.

@dataclass
Контекст класса:
    user_id: str

builder = StateGraph(State)

def plain_node(state: State):
    состояние возврата

def node_with_runtime(state: State, runtime: Runtime[Context]):
    print("В узле: ", runtime.context.user_id)
    return {"results": f"Привет, {state['input']}!"}

def node_with_config(state: State, config: RunnableConfig):
    print("В узле с thread_id: ", config["configurable"]["thread_id"])
    return {"results": f"Привет, {state['input']}!"}


builder.add_node("plain_node", plain_node)
builder.add_node("node_with_runtime", node_with_runtime)
builder.add_node("node_with_config", node_with_config)
...
```

За кулисами функции преобразуются в [`RunnableLambda`](https://reference.langchain.com/python/langchain_core/runnables/#langchain_core.runnables.base.RunnableLambda), что добавляет поддержку пакетной и асинхронной обработки, а также нативную трассировку и отладку.

Если добавить узел в граф, не указав имя, ему будет присвоено имя по умолчанию, эквивалентное имени функции.

```python theme={null}
builder.add_node(my_node)
# Затем вы можете создавать ребра, ведущие к этому узлу и от него, ссылаясь на него как на «мой_узел»`.
```

### Узел `START`

Узел [`START`](https://reference.langchain.com/python/langgraph/constants/#langgraph.constants.START) — это специальный узел, представляющий собой узел, отправляющий пользовательский ввод в граф. Основная цель обращения к этому узлу — определить, какие узлы следует вызывать первыми.

```python theme={null}
from langgraph.graph import START

graph.add_edge(START, "node_a")
```

### `END` узел

Узел `END` — это специальный узел, представляющий собой конечный узел. Этот узел используется, когда необходимо указать, какие ребра не имеют действий после завершения.

```python theme={null}
from langgraph.graph import END

graph.add_edge("node_a", END)
```

### Кэширование узлов

LangGraph поддерживает кэширование задач/узлов на основе входных данных для узла. Для использования кэширования:

* Укажите кэш при компиляции графа (или укажите точку входа).
* Укажите политику кэширования для узлов. Каждая политика кэширования поддерживает:
  * Функция `key_func` используется для генерации ключа кэша на основе входных данных узла; по умолчанию это `хеш` входных данных с помощью pickle.
  * `ttl` — время жизни кэша в секундах. Если не указано, кэш никогда не истечет.

Например:

```python theme={null}
время импорта
from typing_extensions import TypedDict
from langgraph.graph import StateGraph
from langgraph.cache.memory import InMemoryCache
from langgraph.types import CachePolicy


class State(TypedDict):
    x: int
    результат: целое число


builder = StateGraph(State)


def expensive_node(state: State) -> dict[str, int]:
    # дорогостоящие вычисления
    time.sleep(2)
    return {"result": state["x"] * 2}


builder.add_node("expensive_node", expensive_node, cache_policy=CachePolicy(ttl=3))
builder.set_entry_point("expensive_node")
builder.set_finish_point("expensive_node")

graph = builder.compile(cache=InMemoryCache())

print(graph.invoke({"x": 5}, stream_mode='updates')) # [!code highlight]
# [{'expensive_node': {'result': 10}}]
print(graph.invoke({"x": 5}, stream_mode='updates')) # [!code highlight]
# [{'expensive_node': {'result': 10}, '__metadata__': {'cached': True}}]
```

1. Первый запуск занимает две секунды (из-за имитируемых ресурсоемких вычислений).
2. Второй запуск использует кэш и быстро возвращает результат.

## Ребра

Ребра определяют маршрутизацию логики и способ остановки графа. Это важная часть работы ваших агентов и взаимодействия различных узлов друг с другом. Существует несколько основных типов ребер:

* Обычные ребра: Переход от одной вершины к другой напрямую.
* Условные ребра: Вызов функции для определения того, к какому узлу (узлам) следует перейти далее.
* Точка входа: Какой узел следует вызвать первым при поступлении пользовательского ввода.
* Условная точка входа: вызов функции для определения того, какой(ие) узел(ы) следует вызвать первым(и) при поступлении пользовательского ввода.

У узла может быть несколько исходящих ребер. Если у узла несколько исходящих ребер, **все** из этих целевых узлов будут выполняться параллельно в рамках следующего супершага.

### Нормальные ребра

Если вам **всегда** нужно переходить от узла A к узлу B, вы можете использовать метод [`add_edge`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_edge) напрямую.

```python theme={null}
graph.add_edge("node_a", "node_b")
```

### Условные ребра

Если вы хотите **при необходимости** проложить маршрут к одному или нескольким ребрам (или, при необходимости, завершить маршрут), вы можете использовать метод [`add_conditional_edges`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_conditional_edges). Этот метод принимает имя узла и «функцию маршрутизации», которую нужно вызвать после выполнения этого узла:

```python theme={null}
graph.add_conditional_edges("node_a", routing_function)
```

Подобно узлам, функция маршрутизации принимает текущее состояние графа и возвращает значение.

По умолчанию возвращаемое значение `routing_function` используется в качестве имени узла (или списка узлов), которому будет отправлено состояние. Все эти узлы будут выполняться параллельно в рамках следующего супершага.

При желании вы можете предоставить словарь, который сопоставляет выходные данные функции `routing_function` с именем следующего узла.

```python theme={null}
graph.add_conditional_edges("node_a", routing_function, {True: "node_b", False: "node_c"})
```

<Совет>
  Используйте [`Command`](#command) вместо условных ребер, если хотите объединить обновления состояния и маршрутизацию в одной функции.
</Совет>

### Точка входа

Точкой входа является первый(е) узел(ы), которые запускаются при запуске графа. Вы можете использовать метод [`add_edge`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_edge) из виртуального узла [`START`](https://reference.langchain.com/python/langgraph/constants/#langgraph.constants.START), который применяется к первому выполняемому узлу, чтобы указать, где следует войти в граф.

```python theme={null}
from langgraph.graph import START

graph.add_edge(START, "node_a")
```

### Точка условного входа

Условная точка входа позволяет начинать с разных узлов в зависимости от пользовательской логики. Для этого можно использовать [`add_conditional_edges`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_conditional_edges) из виртуального узла [`START`](https://reference.langchain.com/python/langgraph/constants/#langgraph.constants.START).

```python theme={null}
from langgraph.graph import START

graph.add_conditional_edges(START, routing_function)
```

При желании вы можете предоставить словарь, который сопоставляет выходные данные функции `routing_function` с именем следующего узла.

```python theme={null}
graph.add_conditional_edges(START, routing_function, {True: "node_b", False: "node_c"})
```

## `Отправить`

По умолчанию узлы (Nodes) и ребра (Edges) определяются заранее и работают с одним и тем же общим состоянием. Однако могут быть случаи, когда точное количество ребер заранее неизвестно и/или вам может потребоваться одновременное существование разных версий состояния (State). Распространенный пример этого — шаблон проектирования [map-reduce](/oss/python/langgraph/graph-api#map-reduce-and-the-send-api). В этом шаблоне проектирования первый узел может генерировать список объектов, и вам может потребоваться применить другой узел ко всем этим объектам. Количество объектов может быть неизвестно заранее (то есть количество ребер может быть неизвестно), и входное состояние (State) для последующего узла должно быть разным (по одному для каждого сгенерированного объекта).

Для поддержки этого шаблона проектирования LangGraph поддерживает возврат объектов [`Send`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Send) из условных ребер. `Send` принимает два аргумента: первый — это имя узла, а второй — состояние, которое нужно передать этому узлу.

```python theme={null}
def continue_to_jokes(state: OverallState):
    return [Send("generate_joke", {"subject": s}) for s in state['subjects']]

graph.add_conditional_edges("node_a", continue_to_jokes)
```

## `Команда`

Полезно комбинировать управление потоком выполнения (ребра) и обновление состояния (узлы). Например, вам может потребоваться как обновление состояния, так и определение следующего узла в рамках ОДНОГО И ТОГО ЖЕ узла. LangGraph предоставляет способ сделать это, возвращая объект [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) из функций узлов:

```python theme={null}
def my_node(state: State) -> Command[Literal["my_other_node"]]:
    return Command(
        # обновление состояния
        update={"foo": "bar"},
        # управление потоком
        goto="my_other_node"
    )
```

С помощью [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) вы также можете добиться динамического управления потоком выполнения (идентичного [conditional edges](#conditional-edges)):

```python theme={null}
def my_node(state: State) -> Command[Literal["my_other_node"]]:
    if state["foo"] == "bar":
        return Command(update={"foo": "baz"}, goto="my_other_node")
```

Обратите внимание, что [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) добавляет только динамические ребра, в то время как статические ребра будут по-прежнему выполняться. Другими словами, [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) не переопределяет статические ребра.

```python theme={null}
def node_a(state: State) -> Command[Literal["my_other_node"]]:
   if state["foo"] == "bar":
       return Command(update={"foo": "baz"}, goto="my_other_node")

# Добавить статическое ребро от "node_a" к "node_b"
graph.add_edge("node_a", "node_b")

# Эта команда НЕ предотвратит переход "node_a" к "node_b"
```

В приведенном выше примере **"узел\_a"** будет направлен как на **"узел\_b"**, так и на **"мой\_другой\_узел"**.

<Примечание>
  При возврате [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) в функциях узлов необходимо добавить аннотации типа возвращаемого значения со списком имен узлов, к которым ведет маршрутизация, например, `Command[Literal["my_other_node"]]`. Это необходимо для отрисовки графа и сообщает LangGraph, что `my_node` может перейти к `my_other_node`.
</Примечание>

Ознакомьтесь с этим [руководством](/oss/python/langgraph/use-graph-api#combine-control-flow-and-state-updates-with-command), чтобы увидеть полный пример использования [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command).

### Когда следует использовать команду вместо условных ребер?

* Используйте [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command), когда вам нужно **и** одновременно** обновить состояние графа, **и** перенаправить запрос к другому узлу. Например, при реализации [многоагентных передач данных](/oss/python/langchain/multi-agent/handoffs), где важно перенаправить запрос к другому агенту и передать ему некоторую информацию.
* Используйте [условные ребра](#conditional-edges) для маршрутизации между узлами в зависимости от условий без обновления состояния.

### Переход к узлу в родительском графе

Если вы используете [подграфы](/oss/python/langgraph/use-subgraphs), вам может потребоваться перейти от узла внутри подграфа к другому подграфу (т.е. к другому узлу в родительском графе). Для этого вы можете указать `graph=Command.PARENT` в [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command):

```python theme={null}
def my_node(state: State) -> Command[Literal["other_subgraph"]]:
    return Command(
        update={"foo": "bar"},
        goto="other_subgraph", # где `other_subgraph` — узел в родительском графе
        graph=Command.PARENT
    )
```

<Примечание>
  Установка параметра `graph` в значение `Command.PARENT` приведет к переходу к ближайшему родительскому графу.

  При отправке обновлений от узла подграфа к узлу родительского графа для ключа, общего для схем состояния родительского и подграфа, необходимо определить редуктор для обновляемого ключа в состоянии родительского графа. См. этот пример.
</Примечание>

Это особенно полезно при реализации [передачи управления между несколькими агентами](/oss/python/langchain/multi-agent/handoffs).

Для получения более подробной информации ознакомьтесь с [этим руководством](/oss/python/langgraph/use-graph-api#navigate-to-a-node-in-a-parent-graph).

### Использование внутренних инструментов

Один из распространенных сценариев использования — обновление состояния графа изнутри инструмента. Например, в приложении для поддержки клиентов может потребоваться поиск информации о клиенте по номеру его счета или идентификатору в начале разговора.

Для получения более подробной информации обратитесь к [этому руководству](/oss/python/langgraph/use-graph-api#use-inside-tools).

### Человек в процессе

Функция `Command` (https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) является важной частью рабочих процессов с участием человека: при использовании `interrupt()` для сбора пользовательского ввода, `Command` (https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) используется для передачи входных данных и возобновления выполнения с помощью `Command(resume="User input")`. Для получения дополнительной информации ознакомьтесь с [этим концептуальным руководством](/oss/python/langgraph/interrupts).

## Миграции графов

LangGraph легко справляется с миграцией определений графа (узлов, ребер и состояния), даже при использовании контрольной точки для отслеживания состояния.

* Для потоков в конце графа (т.е. не прерывающихся) можно изменить всю топологию графа (т.е. все узлы и ребра, удалить, добавить, переименовать и т.д.).
* Для потоков, работа которых в данный момент прервана, мы поддерживаем все изменения топологии, кроме переименования/удаления узлов (поскольку этот поток может сейчас войти в узел, которого больше не существует) — если это является препятствием, пожалуйста, свяжитесь с нами, и мы сможем определить приоритетность решения.
* Для изменения состояния мы обеспечиваем полную обратную и прямую совместимость при добавлении и удалении клавиш.
* Переименованные ключи состояния теряют сохраненное состояние в существующих потоках.
* Изменения типов ключей состояния, которые происходят несовместимым образом, в настоящее время могут вызывать проблемы в потоках, содержащих состояние до внесения изменений. Если это является критической проблемой, пожалуйста, свяжитесь с нами, и мы сможем определить приоритетность решения.

## Контекст выполнения

При создании графа можно указать `context_schema` для контекста времени выполнения, передаваемого узлам. Это полезно для передачи
Информация, передаваемая узлам, не являющаяся частью состояния графа. Например, вам может потребоваться передать зависимости, такие как имя модели или подключение к базе данных.

```python theme={null}
@dataclass
class ContextScheme:
    llm_provider: str = "openai"

graph = StateGraph(State, context_schema=ContextSchema)
```

Затем вы можете передать этот контекст в граф, используя параметр `context` метода `invoke`.

```python theme={null}
graph.invoke(inputs, context={"llm_provider": "anthropic"})
```

Затем вы можете получить доступ к этому контексту и использовать его внутри узла или условного ребра:

```python theme={null}
from langgraph.runtime import Runtime

def node_a(state: State, runtime: Runtime[ContextSchema]):
    llm = get_llm(runtime.context.llm_provider)
    # ...
```

Подробное описание конфигурации см. в [этом руководстве](/oss/python/langgraph/use-graph-api#add-runtime-configuration).

### Ограничение на рекурсию

Ограничение рекурсии устанавливает максимальное количество [супершагов](#графов), которое граф может выполнить за один запуск. После достижения лимита LangGraph вызовет исключение `GraphRecursionError`. Начиная с версии 1.0.6, ограничение рекурсии по умолчанию установлено на 1000 шагов. Ограничение рекурсии может быть установлено для любого графа во время выполнения и передается в `invoke`/`stream` через словарь конфигурации. Важно отметить, что `recursion_limit` является отдельным ключом `config` и не должен передаваться внутри ключа `configurable`, как все остальные определяемые пользователем параметры конфигурации. См. пример ниже:

```python theme={null}
graph.invoke(inputs, config={"recursion_limit": 5}, context={"llm": "anthropic"})
```

Прочитайте [это руководство](/oss/python/langgraph/graph-api#impose-a-recursion-limit), чтобы узнать больше о том, как работает ограничение рекурсии.

### Доступ к счетчику рекурсии и его обработка

Текущий счетчик шагов доступен в `config["metadata"]["langgraph_step"]` в любом узле, что позволяет заблаговременно обрабатывать рекурсию до достижения лимита рекурсии. Это дает возможность реализовать стратегии плавной деградации в логике вашего графа.

#### Как это работает

Счетчик шагов хранится в `config["metadata"]["langgraph_step"]`. Проверка на превышение лимита рекурсии выполняется по следующей логике: `step > stop`, где `stop = step + recursion_limit + 1`. При превышении лимита LangGraph генерирует ошибку `GraphRecursionError`.

#### Доступ к текущему счетчику шагов

В любом узле можно получить доступ к текущему счетчику шагов для отслеживания хода выполнения.

```python theme={null}
from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph

def my_node(state: dict, config: RunnableConfig) -> dict:
    current_step = config["metadata"]["langgraph_step"]
    print(f"Текущий шаг: {current_step}")
    состояние возврата
```

#### Проактивная обработка рекурсии

LangGraph предоставляет управляемое значение `RemainingSteps`, которое отслеживает, сколько шагов осталось до достижения предела рекурсии. Это позволяет плавно снижать сложность графа.

```python theme={null}
from typing import Annotated, Literal
from langgraph.graph import StateGraph, START, END
from langgraph.managed import RemainingSteps

class State(TypedDict):
    сообщения: Аннотированные[список, лямбда x, y: x + y]
    remaining_steps: RemainingSteps # Управляемое значение - отслеживает количество шагов до достижения лимита

def reasoning_node(state: State) -> dict:
    # Оставшееся количество шагов заполняется автоматически программой LangGraph.
    оставшееся = состояние["remaining_steps"]

    # Проверьте, не заканчиваются ли у нас ступеньки
    если осталось <= 2:
        return {"messages": ["Приближаемся к пределу, завершаем..."]}

    # Обычная обработка
    return {"messages": ["размышляю..."]}

def route_decision(state: State) -> Literal["reasoning_node", "fallback_node"]:
    «Маршрут, основанный на оставшихся шагах»
    если state["remaining_steps"] <= 2:
        return "fallback_node"
    return "reasoning_node"

def fallback_node(state: State) -> dict:
    «Обрабатывать случаи, когда приближается предел рекурсии»
    return {"messages": ["Достигнут предел сложности, предлагаем наилучший возможный ответ"]}

# Построение графика
builder = StateGraph(State)
builder.add_node("reasoning_node", reasoning_node)
builder.add_node("fallback_node", fallback_node)
builder.add_edge(START, "reasoning_node")
builder.add_conditional_edges("reasoning_node", route_decision)
builder.add_edge("fallback_node", END)

graph = builder.compile()

# RemainingSteps работает с любым значением recursion_limit
result = graph.invoke({"messages": []}, {"recursion_limit": 10})
```

#### Проактивный и реактивный подходы

Существует два основных подхода к обработке ограничений рекурсии: проактивный (мониторинг внутри графа) и реактивный (выявление ошибок извне).

```python theme={null}
from typing import Annotated, Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.managed import RemainingSteps
from langgraph.errors import GraphRecursionError

class State(TypedDict):
    сообщения: Аннотированные[список, лямбда x, y: x + y]
    remaining_steps: RemainingSteps

# Проактивный подход (рекомендуется) - с использованием RemainingSteps
def agent_with_monitoring(state: State) -> dict:
    «Проактивно отслеживайте и обрабатывайте рекурсию внутри графа»
    оставшееся = состояние["remaining_steps"]

    # Раннее выявление - путь к внутренней обработке
    если осталось <= 2:
        возвращаться {
            "messages": ["Приближаемся к пределу, возвращаем частичный результат"]
        }

    # Обычная обработка
    return {"messages": [f"Обработка... ({remaining} steps remaining)"]}

def route_decision(state: State) -> Literal["agent", END]:
    если state["remaining_steps"] <= 2:
        возврат КОНЕЦ
    вернуть "агент"

# Построение графика
builder = StateGraph(State)
builder.add_node("agent", agent_with_monitoring)
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", route_decision)
graph = builder.compile()

# Проактивный подход: Граф завершается корректно
result = graph.invoke({"messages": []}, {"recursion_limit": 10})

# Реактивный подход (резервный вариант) - перехват ошибок извне
пытаться:
    result = graph.invoke({"messages": []}, {"recursion_limit": 10})
except GraphRecursionError as e:
    # Обработка ошибок после сбоя выполнения графа выполняется извне
    результат = {"сообщения": ["Резервный вариант: превышен лимит рекурсии"]}
```

Основные различия между этими подходами заключаются в следующем:

| Подход                                                 | Обнаружение             | Обработка                                 | Управление потоком                   |
| ------------------------------------------------------ | ----------------------- | ----------------------------------------- | ------------------------------------ |
| Проактивный подход (с использованием `RemainingSteps`) | До достижения лимита    | Внутри графа через условную маршрутизацию | Граф продолжается до узла завершения |
| Реактивный (перехват `GraphRecursionError`)            | После превышения лимита | За пределами графа в блоке try/catch      | Выполнение графа прервано            |

**Преимущества проактивного подхода:**

* Плавное снижение качества изображения в пределах графика
* Возможность сохранения промежуточного состояния в контрольных точках
* Улучшенное взаимодействие с пользователем благодаря частичному отображению результатов.
* График завершается корректно (без исключений)

**Преимущества реактивного подхода:**

* Более простая реализация
* Нет необходимости изменять логику графа.
* Централизованная обработка ошибок

#### Другие доступные метаданные

Наряду с `langgraph_step`, в `config["metadata"]` также доступны следующие метаданные:

```python theme={null}
def inspect_metadata(state: dict, config: RunnableConfig) -> dict:
    метаданные = config["метаданные"]

    print(f"Шаг: {метаданные['langgraph_step']}")
    print(f"Узел: {метаданные['langgraph_node']}")
    print(f"Триггеры: {metadata['langgraph_triggers']}")
    print(f"Путь: {метаданные['langgraph_path']}")
    print(f"Контрольная точка NS: {metadata['langgraph_checkpoint_ns']}")

    состояние возврата
```

## Визуализация

Визуализация графов часто бывает очень полезна, особенно когда они становятся более сложными. LangGraph предоставляет несколько встроенных способов визуализации графов. Подробнее см. [это руководство](/oss/python/langgraph/use-graph-api#visualize-your-graph).

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langgraph/graph-api.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Всплывающее сообщение>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>