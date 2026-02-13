> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Используйте API Graph

В этом руководстве показаны основы Graph API LangGraph. Рассматриваются операции [state](#define-and-update-state), а также создание распространенных структур графа, таких как [sequences](#create-a-sequence-of-steps), [branches](#create-branches) и [loops](#create-and-control-loops). Также описаны функции управления LangGraph, включая [Send API](#map-reduce-and-the-send-api) для рабочих процессов map-reduce и [Command API](#combine-control-flow-and-state-updates-with-command) для объединения обновлений состояния с «переходами» между узлами.

## Настраивать

Установите `langgraph`:

<CodeGroup>
  ```bash pip theme={null}
  pip install -U langgraph
  ```

  ```bash uv theme={null}
  uv add langgraph
  ```
</CodeGroup>

<Совет>
  **Настройте LangSmith для более эффективной отладки**

  Зарегистрируйтесь в [LangSmith](https://smith.langchain.com), чтобы быстро выявлять проблемы и улучшать производительность ваших проектов LangGraph. LangSmith позволяет использовать данные трассировки для отладки, тестирования и мониторинга ваших приложений LLM, созданных с помощью LangGraph — подробнее о том, как начать работу, читайте в [документации](/langsmith/observability).
</Совет>

## Определение и обновление состояния

Здесь мы покажем, как определить и обновить [state](/oss/python/langgraph/graph-api#state) в LangGraph. Мы продемонстрируем:

1. Как использовать состояние для определения [схемы]графа в Python: [/oss/python/langgraph/graph-api#schema]
2. Как использовать [редукторы](/oss/python/langgraph/graph-api#reducers) для управления обработкой обновлений состояния.

### Определение состояния

В LangGraph [State](/oss/python/langgraph/graph-api#state) может быть объектом типа `TypedDict`, моделью `Pydantic` или классом данных. Ниже мы будем использовать `TypedDict`. Подробнее об использовании Pydantic см. в [этом разделе](#use-pydantic-models-for-graph-state).

По умолчанию графы будут иметь одинаковую схему ввода и вывода, и эта схема определяется состоянием. См. [этот раздел](#define-input-and-output-schemas), чтобы узнать, как определить разные схемы ввода и вывода.

Рассмотрим простой пример с использованием [messages](/oss/python/langgraph/graph-api#messagesstate). Это представляет собой универсальную формулировку состояния для многих приложений LLM. Подробнее см. на нашей странице [concepts](/oss/python/langgraph/graph-api#working-with-messages-in-graph-state).

```python theme={null}
from langchain.messages import AnyMessage
from typing_extensions import TypedDict

class State(TypedDict):
    сообщения: список[AnyMessage]
    extra_field: int
```

В этом состоянии отслеживается список объектов [message](https://python.langchain.com/docs/concepts/messages/), а также дополнительное целочисленное поле.

### Обновление состояния

Давайте построим пример графа с одним узлом. Наш [узел](/oss/python/langgraph/graph-api#nodes) — это просто функция Python, которая считывает состояние нашего графа и вносит в него обновления. Первым аргументом этой функции всегда будет состояние:

```python theme={null}
из langchain.messages импортировать AIMessage

def node(state: State):
    сообщения = состояние["сообщения"]
    new_message = AIMessage("Привет!")
    return {"messages": messages + [new_message], "extra_field": 10}
```

Этот узел просто добавляет сообщение в наш список сообщений и заполняет дополнительное поле.

<Предупреждение>
  Узлы должны возвращать обновления состояния напрямую, а не изменять его.
</Предупреждение>

Далее определим простой граф, содержащий этот узел. Используем [`StateGraph`](/oss/python/langgraph/graph-api#stategraph) для определения графа, работающего с этим состоянием. Затем используем [`add_node`](/oss/python/langgraph/graph-api#nodes) для заполнения нашего графа.

```python theme={null}
from langgraph.graph import StateGraph

builder = StateGraph(State)
builder.add_node(node)
builder.set_entry_point("node")
graph = builder.compile()
```

LangGraph предоставляет встроенные утилиты для визуализации вашего графа. Давайте рассмотрим наш граф. Подробнее о визуализации см. в [этом разделе](#visualize-your-graph).

```python theme={null}
from IPython.display import Image, display

display(Image(graph.get_graph().draw_mermaid_png())
```

<img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_1.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=cf3d978b707847e166d5ed15bc7cbbe4" alt="Simple graph with single node" data-og-width="107" width="107" data-og-height="134" height="134" data-path="oss/images/graph_api_image_1.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_1.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=498bbdb0192eb26ab115d51b53fcb64c 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_1.p ng?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=94cbad4b92d5b887dff2bfbb6f8e0c6c 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_1.p ng?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=d90d58640d49e3fd4e558ab56acf4817 840 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_1.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=cad59990b0c551a2aa96b684b102b953 1100 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_1.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=318736f22c69f66c48f4189db3e39235 1650w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_1.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=6740141ec001a9a4275cecfac67b9c55 2500w" />

В данном случае наш граф обрабатывает только один узел. Давайте перейдем к простому вызову:

```python theme={null}
from langchain.messages import HumanMessage

result = graph.invoke({"messages": [HumanMessage("Hi")]})
результат
```

```
{'messages': [HumanMessage(content='Hi'), AIMessage(content='Hello!')], 'extra_field': 10}
```

Обратите внимание, что:

* Мы начали выполнение вызова с обновления одного ключа состояния.
* Мы получаем полное состояние в результате вызова.

Для удобства мы часто проверяем содержимое [объектов сообщений](https://python.langchain.com/docs/concepts/messages/) с помощью форматированного вывода:

```python theme={null}
for message in result["messages"]:
    message.pretty_print()
```

```
================================ Сообщение от человека ================================

Привет
================================ Сообщение Ai ================================

Привет!
```

### Обработка обновлений состояния с помощью редукторов

Каждый ключ в состоянии может иметь свою собственную независимую функцию [редуктора](/oss/python/langgraph/graph-api#reducers), которая управляет применением обновлений от узлов. Если функция редуктора явно не указана, предполагается, что все обновления ключа должны переопределять её.

Для схем состояний `TypedDict` мы можем определить редукторы, аннотируя соответствующее поле состояния функцией редуктора.

В предыдущем примере наш узел обновил ключ «messages» в состоянии, добавив к нему сообщение. Ниже мы добавляем редуктор к этому ключу, чтобы обновления добавлялись автоматически:

```python theme={null}
from typing_extensions import Annotated

def add(left, right):
    «Также можно импортировать `add` из встроенного оператора `operator`».
    вернуть влево + вправо

class State(TypedDict):
    сообщения: Аннотированные[список[AnyMessage], добавить] # [!подсветка кода]
    extra_field: int
```

Теперь наш узел можно упростить:

```python theme={null}
def node(state: State):
    new_message = AIMessage("Привет!")
    return {"messages": [new_message], "extra_field": 10} # [!code highlight]
```

```python theme={null}
from langgraph.graph import START

graph = StateGraph(State).add_node(node).add_edge(START, "node").compile()

result = graph.invoke({"messages": [HumanMessage("Hi")]})

for message in result["messages"]:
    message.pretty_print()
```

```
================================ Сообщение от человека ================================

Привет
================================ Сообщение Ai ================================

Привет!
```

#### MessagesState

На практике при обновлении списков сообщений необходимо учитывать дополнительные факторы:

* Возможно, нам потребуется обновить существующее сообщение в этом штате.
* Возможно, нам потребуется принимать сокращенные обозначения для [форматов сообщений](/oss/python/langgraph/graph-api#using-messages-in-your-graph), например, [формат OpenAI](https://python.langchain.com/docs/concepts/messages/#openai-format).

LangGraph включает в себя встроенный редуктор [`add_messages`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.message.add_messages), который учитывает следующие моменты:

```python theme={null}
from langgraph.graph.message import add_messages

class State(TypedDict):
    сообщения: Аннотированные[список[AnyMessage], add_messages] # [!подсветка кода]
    extra_field: int

def node(state: State):
    new_message = AIMessage("Привет!")
    return {"messages": [new_message], "extra_field": 10}

graph = StateGraph(State).add_node(node).set_entry_point("node").compile()
```

```python theme={null}
input_message = {"role": "user", "content": "Hi"} # [!code highlight]

result = graph.invoke({"messages": [input_message]})

for message in result["messages"]:
    message.pretty_print()
```

```
================================ Сообщение от человека ================================

Привет
================================ Сообщение Ai ================================

Привет!
```

Это универсальное представление состояния для приложений, использующих [модели чата](https://python.langchain.com/docs/concepts/chat_models/). LangGraph включает в себя предварительно созданный объект `MessagesState` для удобства, так что мы можем получить:

```python theme={null}
from langgraph.graph import MessagesState

class State(MessagesState):
    extra_field: int
```

### Обход редукторов с помощью `Overwrite`

В некоторых случаях может потребоваться обойти редуктор и напрямую перезаписать значение состояния. LangGraph предоставляет для этой цели тип [`Overwrite`](https://reference.langchain.com/python/langgraph/types/). Когда узел возвращает значение, обернутое в `Overwrite`, редуктор обходится, и канал напрямую устанавливается на это значение.

Это полезно, когда вы хотите сбросить или заменить накопленное состояние, а не объединить его с существующими значениями.

```python theme={null}
from langgraph.graph import StateGraph, START, END
from langgraph.types import Overwrite
from typing_extensions import Annotated, TypedDict
импортный оператор

class State(TypedDict):
    сообщения: Аннотированные[список, оператор.добавить]

def add_message(state: State):
    return {"messages": ["first message"]}

def replace_messages(state: State):
    # Обходим редуктор и заменяем весь список сообщений
    return {"messages": Overwrite(["replacement message"])}

builder = StateGraph(State)
builder.add_node("add_message", add_message)
builder.add_node("replace_messages", replace_messages)
builder.add_edge(START, "add_message")
builder.add_edge("add_message", "replace_messages")
builder.add_edge("replace_messages", END)

graph = builder.compile()

result = graph.invoke({"messages": ["initial"]})
print(result["messages"])
```

```
['заменяющее сообщение']
```

Также можно использовать формат JSON со специальным ключом `"__overwrite__"`:

```python theme={null}
def replace_messages(state: State):
    return {"messages": {"__overwrite__": ["replacement message"]}}
```

<Предупреждение>
  При параллельном выполнении узлов только один узел может использовать операцию `Overwrite` для одного и того же ключа состояния на данном супершаге. Если несколько узлов попытаются перезаписать один и тот же ключ на одном и том же супершаге, будет сгенерировано исключение `InvalidUpdateError`.
</Предупреждение>

### Определение схем ввода и вывода

По умолчанию `StateGraph` работает с одной схемой, и ожидается, что все узлы будут взаимодействовать, используя эту схему. Однако также можно определить отдельные схемы ввода и вывода для графа.

При указании различных схем для обмена данными между узлами по-прежнему будет использоваться внутренняя схема. Входная схема гарантирует, что предоставленные входные данные соответствуют ожидаемой структуре, а выходная схема фильтрует внутренние данные, возвращая только релевантную информацию в соответствии с определенной выходной схемой.

Ниже мы рассмотрим, как определить отдельные схемы ввода и вывода.

```python theme={null}
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# Определяем схему для входных данных
class InputState(TypedDict):
    вопрос: стр.

# Определяем схему для выходных данных
class OutputState(TypedDict):
    ответ: стр.

# Определяем общую схему, объединяющую входные и выходные данные.
class OverallState(InputState, OutputState):
    проходить

# Определите узел, который обрабатывает входные данные и генерирует ответ.
def answer_node(state: InputState):
    # Пример ответа и дополнительная ключевая часть
    return {"answer": "bye", "question": state["question"]}

# Построение графа с указанием входных и выходных схем
builder = StateGraph(OverallState, input_schema=InputState, output_schema=OutputState)
builder.add_node(answer_node) # Добавить узел ответа
builder.add_edge(START, "answer_node") # Определяем начальное ребро
builder.add_edge("answer_node", END) # Определяем конечное ребро
graph = builder.compile() # Компиляция графа

# Вызываем граф с входными данными и выводим результат.
print(graph.invoke({"question": "hi"}))
```

```
{'answer': 'bye'}
```

Обратите внимание, что вывод команды invoke включает только схему вывода.

### Передача приватного состояния между узлами

В некоторых случаях может потребоваться обмен информацией между узлами, имеющей решающее значение для промежуточной логики, но не обязательно входящей в основную схему графа. Эти конфиденциальные данные не имеют отношения к общему вводу/выводу графа и должны передаваться только между определенными узлами.

Ниже мы создадим пример последовательного графа, состоящего из трех узлов (узел 1, узел 2 и узел 3), где частные данные передаются между первыми двумя шагами (узел 1 и узел 2), в то время как третий шаг (узел 3) имеет доступ только к общему общедоступному состоянию.

```python theme={null}
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict

# Общее состояние графа (это общедоступное состояние, разделяемое между узлами)
class OverallState(TypedDict):
    а: стр

# Выходные данные с узла node_1 содержат конфиденциальную информацию, не являющуюся частью общего состояния.
class Node1Output(TypedDict):
    private_data: str

# Личные данные передаются только между узлами node_1 и node_2
def node_1(state: OverallState) -> Node1Output:
    output = {"private_data": "set by node_1"}
    print(f"Вход в узел `node_1`:\n\tВходные данные: {state}.\n\tВозвращено: {output}")
    возврат выходных данных

# Ввод данных на узле 2 запрашивает только закрытые данные, доступные после узла 1.
class Node2Input(TypedDict):
    private_data: str

def node_2(state: Node2Input) -> OverallState:
    output = {"a": "set by node_2"}
    print(f"Вход в узел `node_2`:\n\tВходные данные: {state}.\n\tВозвращено: {output}")
    возврат выходных данных

# Узел 3 имеет доступ только к общему состоянию (у узла 1 нет доступа к личным данным)
def node_3(state: OverallState) -> OverallState:
    output = {"a": "set by node_3"}
    print(f"Вход в узел `node_3`:\n\tВходные данные: {state}.\n\tВозвращено: {output}")
    возврат выходных данных

# Соединяйте узлы в последовательности
# node_2 принимает приватные данные от node_1, тогда как
# node_3 не видит приватные данные.
builder = StateGraph(OverallState).add_sequence([node_1, node_2, node_3])
builder.add_edge(START, "node_1")
graph = builder.compile()

# Вызываем граф с начальным состоянием
response = graph.invoke(
    {
        "a": "устанавливается в начале",
    }
)

print()
print(f"Вывод вызова графа: {response}")
```

```
Вошел в узел `node_1`:
    Ввод: {'a': 'устанавливается в начале'}.
    Возвращено: {'private_data': 'set by node_1'}
Вошел в узел `node_2`:
    Входные данные: {'private_data': 'set by node_1'}.
    Возвращено: {'a': 'set by node_2'}
Вошел в узел `node_3`:
    Входные данные: {'a': 'установлено узлом_2'}.
    Возвращено: {'a': 'set by node_3'}

Результат вызова графа: {'a': 'set by node_3'}
```

### Используйте модели pydantic для состояния графа

Объект [StateGraph](https://langchain-ai.github.io/langgraph/reference/graphs.md#langgraph.graph.StateGraph) при инициализации принимает аргумент [`state_schema`](https://reference.langchain.com/python/langchain/middleware/#langchain.agents.middleware.AgentMiddleware.state_schema), который определяет «структуру» состояния, к которому узлы графа могут обращаться и которое могут обновлять.

В наших примерах мы обычно используем встроенный в Python `TypedDict` или [`dataclass`](https://docs.python.org/3/library/dataclasses.html) для `state_schema`, но [`state_schema`](https://reference.langchain.com/python/langchain/middleware/#langchain.agents.middleware.AgentMiddleware.state_schema) может быть любым [type](https://docs.python.org/3/library/stdtypes.html#type-objects).

Здесь мы рассмотрим, как [базовая модель Pydantic](https://docs.pydantic.dev/latest/api/base_model/) может быть использована для [`state_schema`](https://reference.langchain.com/python/langchain/middleware/#langchain.agents.middleware.AgentMiddleware.state_schema) для добавления проверки входных данных во время выполнения.

<Примечание>
  **Известные ограничения**

  * В настоящее время выходные данные графа **НЕ** будут представлять собой экземпляр пидантической модели.
  * Проверка во время выполнения выполняется только для входных данных первого узла графа, а не для последующих узлов или выходных данных.
  * Трассировка ошибок проверки из pydantic не показывает, в каком узле возникла ошибка.
  * Рекурсивная проверка в Pydantic может быть медленной. Для приложений, чувствительных к производительности, возможно, стоит рассмотреть использование `dataclass` вместо этого.
</Примечание>

```python theme={null}
from langgraph.graph import StateGraph, START, END
from typing_extensions import TypedDict
from pydantic import BaseModel

# Общее состояние графа (это общедоступное состояние, разделяемое между узлами)
class OverallState(BaseModel):
    а: стр

def node(state: OverallState):
    return {"a": "до свидания"}

# Построение графа состояний
builder = StateGraph(OverallState)
builder.add_node(node) # node_1 — первый узел
builder.add_edge(START, "node") # Начинаем граф с узла node_1
builder.add_edge("node", END) # Завершение графа после node_1
graph = builder.compile()

# Проверка графа с использованием допустимых входных данных
graph.invoke({"a": "hello"})
```

Вызовите граф, используя **недопустимые** входные данные.

```python theme={null}
пытаться:
    graph.invoke({"a": 123}) # Должна быть строка
за исключением исключения как e:
    print("Возникло исключение, поскольку `a` является целым числом, а не строкой.")
    print(e)
```

```
Возникло исключение, поскольку `a` является целым числом, а не строкой.
1 ошибка проверки для OverallState
а
  Входные данные должны представлять собой допустимую строку [type=string_type, input_value=123, input_type=int]
    Для получения дополнительной информации посетите https://errors.pydantic.dev/2.9/v/string_type
```

Дополнительные возможности модели состояния Pydantic описаны ниже:

<Accordion title="Поведение сериализации">
  При использовании моделей Pydantic в качестве схем состояний важно понимать, как работает сериализация, особенно в следующих случаях:

  * Передача объектов Pydantic в качестве входных данных
  * Получение выходных данных из графа
  * Работа с вложенными пидантическими моделями

  Давайте посмотрим, как эти модели поведения проявляются на практике.

  ```python theme={null}
  from langgraph.graph import StateGraph, START, END
  from pydantic import BaseModel

  class NestedModel(BaseModel):
      значение: строка

  class ComplexState(BaseModel):
      текст: строка
      количество: целое число
      вложенный: ВложеннаяМодель

  def process_node(state: ComplexState):
      # Узел получает проверенный объект Pydantic
      print(f"Тип входного состояния: {type(state)}")
      print(f"Вложенный тип: {type(state.nested)}")
      # Возвращает обновление словаря
      return {"text": state.text + " processed", "count": state.count + 1}

  # Построение графика
  builder = StateGraph(ComplexState)
  builder.add_node("process", process_node)
  builder.add_edge(START, "process")
  builder.add_edge("process", END)
  graph = builder.compile()

  # Создание экземпляра Pydantic для ввода данных
  input_state = ComplexState(text="hello", count=0, nested=NestedModel(value="test"))
  print(f"Тип входного объекта: {type(input_state)}")

  # Вызов графа с использованием экземпляра Pydantic
  result = graph.invoke(input_state)
  print(f"Тип выходных данных: {type(result)}")
  print(f"Выходное содержимое: {result}")

  # При необходимости вернитесь к модели Pydantic.
  output_model = ComplexState(**result)
  print(f"Преобразовано обратно в Pydantic: {type(output_model)}")
  ```
</Аккордеон>

<Accordion title="Приведение типов во время выполнения">
  Pydantic выполняет приведение типов данных к исходным значениям во время выполнения. Это может быть полезно, но также может привести к неожиданному поведению, если вы об этом не знаете.

  ```python theme={null}
  from langgraph.graph import StateGraph, START, END
  from pydantic import BaseModel

  class CoercionExample(BaseModel):
      Pydantic преобразует строковые числа в целые числа.
      число: целое число
      # Pydantic преобразует строковые логические значения в логические.
      флаг: логическое значение

  def inspect_node(state: CoercionExample):
      print(f"number: {state.number} (type: {type(state.number)})")
      print(f"flag: {state.flag} (type: {type(state.flag)})")
      возвращаться {}

  builder = StateGraph(CoercionExample)
  builder.add_node("inspect", inspect_node)
  builder.add_edge(START, "inspect")
  builder.add_edge("inspect", END)
  graph = builder.compile()

  # Демонстрация преобразования типов с использованием строковых входных данных, которые будут преобразованы.
  result = graph.invoke({"number": "42", "flag": "true"})

  # Это приведет к ошибке проверки.
  пытаться:
      graph.invoke({"number": "not-a-number", "flag": "true"})
  за исключением исключения как e:
      print(f"\nОжидаемая ошибка проверки: {e}")
  ```
</Аккордеон>

<Заголовок аккордеона="Работа с моделями сообщений">
  При работе с типами сообщений LangChain в вашей схеме состояния необходимо учитывать важные моменты сериализации. Для корректной сериализации/десериализации при передаче объектов сообщений по сети следует использовать `AnyMessage` (а не `BaseMessage`).

  ```python theme={null}
  from langgraph.graph import StateGraph, START, END
  from pydantic import BaseModel
  from langchain.messages import HumanMessage, AIMessage, AnyMessage
  из набора текста импортировать Список

  class ChatState(BaseModel):
      сообщения: Список[AnyMessage]
      контекст: строка

  def add_message(state: ChatState):
      return {"messages": state.messages + [AIMessage(content="Привет!")]}

  builder = StateGraph(ChatState)
  builder.add_node("add_message", add_message)
  builder.add_edge(START, "add_message")
  builder.add_edge("add_message", END)
  graph = builder.compile()

  # Создать поле ввода с сообщением
  initial_state = ChatState(
      messages=[HumanMessage(content="Привет")], context="Чат службы поддержки клиентов"
  )

  result = graph.invoke(initial_state)
  print(f"Вывод: {результат}")

  # Чтобы увидеть типы сообщений, вернитесь к модели Pydantic.
  output_model = ChatState(**result)
  for i, msg in enumerate(output_model.messages):
      print(f"Сообщение {i}: {type(msg).__name__} - {msg.content}")
  ```
</Аккордеон>

## Добавить конфигурацию во время выполнения

Иногда возникает необходимость настраивать граф непосредственно при его вызове. Например, может потребоваться указать, какой LLM или системную подсказку использовать во время выполнения, *не загрязняя состояние графа этими параметрами*.

Для добавления конфигурации во время выполнения:

1. Укажите схему для вашей конфигурации.
2. Добавьте конфигурацию в сигнатуру функции для узлов или условных ребер.
3. Передайте конфигурацию в граф.

Ниже приведён простой пример:

```python theme={null}
from langgraph.graph import END, StateGraph, START
from langgraph.runtime import Runtime
from typing_extensions import TypedDict

# 1. Укажите схему конфигурации
class ContextSchema(TypedDict):
    my_runtime_value: str

# 2. Определите граф, который обращается к конфигурации в узле.
class State(TypedDict):
    my_state_value: str

def node(state: State, runtime: Runtime[ContextSchema]): # [!code highlight]
    if runtime.context["my_runtime_value"] == "a": # [!подсветка кода]
        return {"my_state_value": 1}
    elif runtime.context["my_runtime_value"] == "b": # [!code highlight]
        return {"my_state_value": 2}
    еще:
        raise ValueError("Неизвестные значения.")

builder = StateGraph(State, context_schema=ContextSchema) # [!code highlight]
builder.add_node(node)
builder.add_edge(START, "node")
builder.add_edge("node", END)

graph = builder.compile()

# 3. Передача конфигурации во время выполнения:
print(graph.invoke({}, context={"my_runtime_value": "a"})) # [!code highlight]
print(graph.invoke({}, context={"my_runtime_value": "b"})) # [!code highlight]
```

```
{'my_state_value': 1}
{'my_state_value': 2}
```

<Заголовок аккордеона="Расширенный пример: указание LLM во время выполнения">
  Ниже мы приведем практический пример, в котором настроим, какую модель LLM использовать во время выполнения. Мы будем использовать как модели OpenAI, так и антропные модели.

  ```python theme={null}
  from dataclasses import dataclass

  from langchain.chat_models import init_chat_model
  from langgraph.graph import MessagesState, END, StateGraph, START
  from langgraph.runtime import Runtime
  from typing_extensions import TypedDict

  @dataclass
  class ContextScheme:
      model_provider: str = "anthropic"

  МОДЕЛИ = {
      "антропический": init_chat_model("claude-haiku-4-5-20251001"),
      "openai": init_chat_model("gpt-4.1-mini"),
  }

  def call_model(state: MessagesState, runtime: Runtime[ContextSchema]):
      модель = MODELS[runtime.context.model_provider]
      response = model.invoke(state["messages"])
      return {"messages": [response]}

  builder = StateGraph(MessagesState, context_schema=ContextSchema)
  builder.add_node("model", call_model)
  builder.add_edge(START, "model")
  builder.add_edge("model", END)

  graph = builder.compile()

  # Использование
  input_message = {"role": "user", "content": "hi"}
  # Без настроек используется значение по умолчанию (антропический)
  response_1 = graph.invoke({"messages": [input_message]}, context=ContextSchema())["messages"][-1]
  # Или можно установить OpenAI
  response_2 = graph.invoke({"messages": [input_message]}, context={"model_provider": "openai"})["messages"][-1]

  print(response_1.response_metadata["model_name"])
  print(response_2.response_metadata["model_name"])
  ```

  ```
  claude-haiku-4-5-20251001
  gpt-4.1-mini-2025-04-14
  ```
</Аккордеон>

<Заголовок аккордеона="Расширенный пример: указание модели и системного сообщения во время выполнения">
  Ниже мы приведем практический пример, в котором настраиваем два параметра: LLM и системное сообщение для использования во время выполнения.

  ```python theme={null}
  from dataclasses import dataclass
  from langchain.chat_models import init_chat_model
  from langchain.messages import SystemMessage
  from langgraph.graph import END, MessagesState, StateGraph, START
  from langgraph.runtime import Runtime
  from typing_extensions import TypedDict

  @dataclass
  class ContextScheme:
      model_provider: str = "anthropic"
      system_message: str | None = None

  МОДЕЛИ = {
      "антропический": init_chat_model("claude-haiku-4-5-20251001"),
      "openai": init_chat_model("gpt-4.1-mini"),
  }

  def call_model(state: MessagesState, runtime: Runtime[ContextSchema]):
      модель = MODELS[runtime.context.model_provider]
      сообщения = состояние["сообщения"]
      if (system_message := runtime.context.system_message):
          сообщения = [SystemMessage(system_message)] + сообщения
      response = model.invoke(messages)
      return {"messages": [response]}

  builder = StateGraph(MessagesState, context_schema=ContextSchema)
  builder.add_node("model", call_model)
  builder.add_edge(START, "model")
  builder.add_edge("model", END)

  graph = builder.compile()

  # Использование
  input_message = {"role": "user", "content": "hi"}
  response = graph.invoke({"messages": [input_message]}, context={"model_provider": "openai", "system_message": "Ответьте на итальянском."})
  для сообщения в ответе["messages"]:
      message.pretty_print()
  ```

  ```
  ================================ Сообщение от человека ================================

  привет
  ================================ Сообщение Ai ================================

  Чао! Можно ли помочь вам?
  ```
</Аккордеон>

## Добавить правила повторных попыток

Существует множество сценариев использования, в которых вам может потребоваться настроить политику повторных попыток для вашего узла, например, при вызове API, запросе к базе данных или вызове LLM и т. д. LangGraph позволяет добавлять политики повторных попыток к узлам.

Для настройки политики повторных попыток передайте параметр `retry_policy` в [`add_node`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_node). Параметр `retry_policy` принимает объект `RetryPolicy` в виде кортежа. Ниже мы создаем объект `RetryPolicy` с параметрами по умолчанию и связываем его с узлом:

```python theme={null}
from langgraph.types import RetryPolicy

builder.add_node(
    "node_name",
    функция узла,
    retry_policy=RetryPolicy(),
)
```

По умолчанию параметр `retry_on` использует функцию `default_retry_on`, которая повторяет попытку при возникновении любого исключения, за исключением следующих:

* `ValueError`
* `TypeError`
* `ArithmeticError`
* `ImportError`
* `LookupError`
* `NameError`
* `SyntaxError`
* `RuntimeError`
* `ReferenceError`
* `StopIteration`
* `StopAsyncIteration`
* `OSError`

Кроме того, для исключений, возникающих при использовании популярных библиотек для обработки HTTP-запросов, таких как `requests` и `httpx`, повторная попытка выполняется только при кодах состояния 5xx.

<Заголовок аккордеона="Расширенный пример: настройка правил повторных попыток">
  Рассмотрим пример чтения данных из базы данных SQL. Ниже мы передаем узлам две разные политики повторных попыток:

  ```python theme={null}
  импорт sqlite3
  from typing_extensions import TypedDict
  from langchain.chat_models import init_chat_model
  from langgraph.graph import END, MessagesState, StateGraph, START
  from langgraph.types import RetryPolicy
  from langchain_community.utilities import SQLDatabase
  из langchain.messages импортировать AIMessage

  db = SQLDatabase.from_uri("sqlite:///:memory:")
  model = init_chat_model("claude-haiku-4-5-20251001")

  def query_database(state: MessagesState):
      query_result = db.run("SELECT * FROM Artist LIMIT 10;")
      return {"messages": [AIMessage(content=query_result)]}

  def call_model(state: MessagesState):
      response = model.invoke(state["messages"])
      return {"messages": [response]}

  # Определить новый граф
  builder = StateGraph(MessagesState)
  builder.add_node(
      "query_database",
      база_запросов,
      retry_policy=RetryPolicy(retry_on=sqlite3.OperationalError),
  )
  builder.add_node("model", call_model, retry_policy=RetryPolicy(max_attempts=5))
  builder.add_edge(START, "model")
  builder.add_edge("model", "query_database")
  builder.add_edge("query_database", END)
  graph = builder.compile()
  ```
</Аккордеон>

## Добавить кэширование узлов

Кэширование узлов полезно в случаях, когда необходимо избежать повторения операций, например, при выполнении ресурсоемких действий (как по времени, так и по стоимости). LangGraph позволяет добавлять индивидуальные политики кэширования к узлам в графе.

Для настройки политики кэширования передайте параметр `cache_policy` функции `add_node`. В следующем примере создается объект `CachePolicy` с временем жизни 120 секунд и генератором `key_func` по умолчанию. Затем он связывается с узлом:

```python theme={null}
from langgraph.types import CachePolicy

builder.add_node(
    "node_name",
    функция узла,
    cache_policy=CachePolicy(ttl=120),
)
```

Чтобы включить кэширование на уровне узлов для графа, задайте аргумент `cache` при компиляции графа. В приведенном ниже примере используется `InMemoryCache` для настройки графа с кэшированием в оперативной памяти, но также доступен `SqliteCache`.

```python theme={null}
from langgraph.cache.memory import InMemoryCache

graph = builder.compile(cache=InMemoryCache())
```

## Создание последовательности шагов

<Информация>
  **Предварительные требования**
  Данное руководство предполагает ознакомление с разделом [state](#define-and-update-state), приведенным выше.
</Info>

Здесь мы покажем, как построить простую последовательность шагов. Мы продемонстрируем:

1. Как построить последовательный граф
2. Встроенная сокращенная запись для построения подобных графов.

Для добавления последовательности узлов мы используем методы [`add_node`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_node) и [`add_edge`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_edge) нашего [graph](/oss/python/langgraph/graph-api#stategraph):

```python theme={null}
from langgraph.graph import START, StateGraph

builder = StateGraph(State)

# Добавить узлы
builder.add_node(step_1)
builder.add_node(step_2)
builder.add_node(step_3)

# Добавить рёбра
builder.add_edge(START, "step_1")
builder.add_edge("step_1", "step_2")
builder.add_edge("step_2", "step_3")
```

Мы также можем использовать встроенную сокращенную запись `.add_sequence`:

```python theme={null}
builder = StateGraph(State).add_sequence([step_1, step_2, step_3])
builder.add_edge(START, "step_1")
```

<Заголовок аккордеона: "Зачем разделять этапы приложения на последовательность с помощью LangGraph?">
  LangGraph упрощает добавление базового уровня хранения данных в ваше приложение.
  Это позволяет сохранять состояние между выполнениями узлов, так что ваши узлы LangGraph управляют:

  * Как происходит [контрольное сохранение](/oss/python/langgraph/persistence) при обновлении состояния
  * Как возобновляются прерывания в рабочих процессах [с участием человека](/oss/python/langgraph/interrupts)
  * Как мы можем «отмотать назад» и разветвить выполнение, используя возможности LangGraph для [путешествия во времени](/oss/python/langgraph/use-time-travel)

  Они также определяют, как передаются шаги выполнения в потоковом режиме (/oss/python/langgraph/streaming), а также как визуализируется и отлаживается ваше приложение с помощью Studio (/langsmith/studio).

  Давайте продемонстрируем сквозной пример. Мы создадим последовательность из трех шагов:

  1. Заполните значением ключ состояния.
  2. Обновите то же значение.
  3. Введите другое значение.

  Давайте сначала определим наше [состояние](/oss/python/langgraph/graph-api#state). Оно управляет [схемой графа](/oss/python/langgraph/graph-api#schema) и может также определять, как применять обновления. Подробнее см. [этот раздел](#process-state-updates-with-reducers).

  В нашем случае мы будем отслеживать только два значения:

  ```python theme={null}
  from typing_extensions import TypedDict

  class State(TypedDict):
      значение_1: строка
      значение_2: целое число
  ```

  Наши [узлы](/oss/python/langgraph/graph-api#nodes) — это просто функции Python, которые считывают состояние нашего графа и вносят в него обновления. Первым аргументом этой функции всегда будет состояние:

  ```python theme={null}
  def step_1(state: State):
      return {"value_1": "a"}

  def step_2(state: State):
      current_value_1 = state["value_1"]
      return {"value_1": f"{current_value_1} b"}

  def step_3(state: State):
      return {"value_2": 10}
  ```

  <Примечание>
    Обратите внимание, что при обновлении состояния каждый узел может просто указать значение ключа, который он хочет обновить.

    По умолчанию это **перезапишет** значение соответствующего ключа. Вы также можете использовать [редукторы](/oss/python/langgraph/graph-api#reducers) для управления обработкой обновлений — например, вы можете добавлять последовательные обновления к ключу. Подробнее см. [этот раздел](#process-state-updates-with-reducers).
  </Примечание>

  Наконец, мы определяем граф. Мы используем [StateGraph](/oss/python/langgraph/graph-api#stategraph) для определения графа, который работает с этим состоянием.

  Затем мы воспользуемся функциями [`add_node`](/oss/python/langgraph/graph-api#messagesstate) и [`add_edge`](/oss/python/langgraph/graph-api#edges), чтобы заполнить наш граф и определить поток управления.

  ```python theme={null}
  from langgraph.graph import START, StateGraph

  builder = StateGraph(State)

  # Добавить узлы
  builder.add_node(step_1)
  builder.add_node(step_2)
  builder.add_node(step_3)

  # Добавить рёбра
  builder.add_edge(START, "step_1")
  builder.add_edge("step_1", "step_2")
  builder.add_edge("step_2", "step_3")
  ```

  <Совет>
    **Указание пользовательских имен**
    Вы можете указать пользовательские имена для узлов, используя [`add_node`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_node):

    ```python theme={null}
    builder.add_node("my_node", step_1)
    ```
  </Совет>

  Обратите внимание, что:

  * [`add_edge`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_edge) принимает имена узлов, которые для функций по умолчанию равны `node.__name__`.
  * Необходимо указать точку входа в граф. Для этого добавляем ребро с узлом [START](/oss/python/langgraph/graph-api#start-node).
  * Граф останавливается, когда больше нет узлов для выполнения.

  Далее мы [компилируем](/oss/python/langgraph/graph-api#compiling-your-graph) наш граф. Это обеспечивает несколько базовых проверок структуры графа (например, выявление осиротевших узлов). Если бы мы добавляли механизм сохранения данных в наше приложение через [контрольную точку](/oss/python/langgraph/persistence), он также был бы передан сюда.

  ```python theme={null}
  graph = builder.compile()
  ```

  LangGraph предоставляет встроенные утилиты для визуализации вашего графа. Давайте рассмотрим нашу последовательность. Подробности о визуализации см. в [этом руководстве](#visualize-your-graph).

  ```python theme={null}
  from IPython.display import Image, display

  display(Image(graph.get_graph().draw_mermaid_png())
  ```

    <img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_2.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=fa0376786cc89d704a5435abba178804" alt="Граф последовательности шагов" data-og-width="107" width="107" data-og-height="333" height="333" data-path="oss/images/graph_api_image_2.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_2.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=e2d4ec28fa1b03fab44cbcfccd19aa16 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_2.p ng?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=5ab128ae8f12f766384f48e03fa2c35c 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_2.p ng?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=db4260bece32ab8f5045ea7b9b151c45 840 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_2.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=8a93a6970742a83f06fb1a5288668eef 1100 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_2.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=269956fccda17f64def8a69db847d4aa 1650w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_2.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=40f495cb5fbca4aa2c960083a50af52e 2500w" />

  Давайте перейдём к простому вызову:

  ```python theme={null}
  graph.invoke({"value_1": "c"})
  ```

  ```
  {'value_1': 'a b', 'value_2': 10}
  ```

  Обратите внимание, что:

  * Мы начали вызов, указав значение для одного ключа состояния. Мы всегда должны указывать значение как минимум для одного ключа.
  * Переданное нами значение было перезаписано первым узлом.
  * Второй узел обновил значение.
  * Третий узел заполнил другое значение.

  <Совет>
    **Встроенная стенография**
    В версии `langgraph>=0.2.46` есть встроенная сокращенная запись `add_sequence` для добавления последовательностей узлов. Вы можете скомпилировать тот же граф следующим образом:

    ```python theme={null}
    builder = StateGraph(State).add_sequence([step_1, step_2, step_3]) # [!code highlight]
    builder.add_edge(START, "step_1")

    graph = builder.compile()

    graph.invoke({"value_1": "c"})
    ```
  </Совет>
</Аккордеон>

## Создание ветвей

Параллельное выполнение узлов имеет решающее значение для ускорения общей работы графа. LangGraph предлагает встроенную поддержку параллельного выполнения узлов, что может значительно повысить производительность рабочих процессов на основе графов. Эта параллелизация достигается с помощью механизмов разветвления и присоединения, используя как стандартные ребра, так и [условные ребра](https://langchain-ai.github.io/langgraph/reference/graphs.md#langgraph.graph.MessageGraph.add_conditional_edges). Ниже приведены несколько примеров, демонстрирующих, как добавить и создать разветвленные потоки данных, которые подойдут именно вам.

### Запуск узлов графа параллельно

В этом примере мы расходимся от `Узел A` к `B и C`, а затем расходимся к `D`. В нашем состоянии [мы указываем операцию добавления редуктора](/oss/python/langgraph/graph-api#reducers). Это объединит или накопит значения для конкретного ключа в состоянии, а не просто перезапишет существующее значение. Для списков это означает конкатенацию нового списка с существующим. Более подробную информацию об обновлении состояния с помощью редукторов см. в разделе выше о [редукторах состояния](#process-state-updates-with-reducers).

```python theme={null}
импортный оператор
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    # Функция редуктора operator.add делает этот код только добавляемым.
    aggregate: Annotated[list, operator.add]

def a(state: State):
    print(f'Добавление "A" к {state["aggregate"]}')
    return {"aggregate": ["A"]}

def b(state: State):
    print(f'Добавление "B" к {state["aggregate"]}')
    return {"aggregate": ["B"]}

def c(state: State):
    print(f'Добавление "C" к {state["aggregate"]}')
    return {"aggregate": ["C"]}

def d(state: State):
    print(f'Добавление "D" к {state["aggregate"]}')
    return {"aggregate": ["D"]}

builder = StateGraph(State)
builder.add_node(a)
builder.add_node(b)
builder.add_node(c)
builder.add_node(d)
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("a", "c")
builder.add_edge("b", "d")
builder.add_edge("c", "d")
builder.add_edge("d", END)
graph = builder.compile()
```

```python theme={null}
from IPython.display import Image, display

display(Image(graph.get_graph().draw_mermaid_png())
```

<img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_3.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=8359f2e8d9dde03d7cc25f9d755a428d" alt="График параллельного выполнения" data-og-width="143" width="143" data-og-height="432" height="432" data-path="oss/images/graph_api_image_3.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_3.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=75695e23f3e5e7eddb985785376108c4 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_3.p ng?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=cf45dc47fcfcf30ef39922a44119d815 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_3.png?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=92b3e0a7d06b07becf4deab660ff3717 840w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_3.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=8c0e296783bde688d32b36e7e8fb669c 1100w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_3.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=a4ff2db4eea2ab57343b329f6e21949c 1650w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_3.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=99b0250accefffa610c67662ca4be2a2 2500 Вт" />

С помощью редуктора можно увидеть, что значения, добавленные в каждом узле, накапливаются.

```python theme={null}
graph.invoke({"aggregate": []}, {"configurable": {"thread_id": "foo"}})
```

```
Добавление буквы «А» к []
Прибавление буквы «B» к ['A']
Добавление буквы «С» к ['А']
Добавление "D" к ['A', 'B', 'C']
```

<Примечание>
  В приведенном выше примере узлы `"b"` и `"c"` выполняются одновременно на одном и том же [супершаге](/oss/python/langgraph/graph-api#graphs). Поскольку они находятся на одном и том же шаге, узел `"d"` выполняется после завершения работы как `"b"`, так и `"c"`.

  Важно отметить, что обновления из параллельного супершага могут быть непоследовательно упорядочены. Если вам необходим последовательный, заранее определенный порядок обновлений из параллельного супершага, следует записывать выходные данные в отдельное поле состояния вместе со значением, по которому будет осуществляться их упорядочивание.
</Примечание>

<Заголовок аккордеона="Обработка исключений?"">
  LangGraph выполняет узлы внутри [супершагов](/oss/python/langgraph/graph-api#graphs), это означает, что хотя параллельные ветви выполняются параллельно, весь супершаг является **транзакционным**. Если какая-либо из этих ветвей вызывает исключение, **ни одно** из обновлений не применяется к состоянию (весь супершаг выдает ошибку).

  Важно отметить, что при использовании [контрольной точки](/oss/python/langgraph/persistence) результаты успешных узлов в рамках супершага сохраняются и не повторяются при возобновлении работы.

  Если у вас есть подверженные ошибкам процессы (например, вам нужно обрабатывать нестабильные вызовы API), LangGraph предлагает два способа решения этой проблемы:

  1. Вы можете писать обычный код на Python внутри своего узла для перехвата и обработки исключений.
  2. Вы можете установить **[retry_policy](https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.RetryPolicy)**, чтобы граф повторял попытки для узлов, вызывающих определенные типы исключений. Повторные попытки выполняются только для ветвей, завершившихся с ошибкой, поэтому вам не нужно беспокоиться о выполнении избыточной работы.

  Вместе они позволяют выполнять параллельное выполнение и полностью контролировать обработку исключений.
</Аккордеон>

<Совет>
  **Установить максимальное количество одновременных операций**
  Вы можете контролировать максимальное количество одновременно выполняемых задач, установив параметр `max_concurrency` в [конфигурационном файле](https://python.langchain.com/api_reference/core/runnables/langchain_core.runnables.config.RunnableConfig.html) при вызове графа.

  ```python theme={null}
  graph.invoke({"value_1": "c"}, {"configurable": {"max_concurrency": 10}})
  ```
</Совет>

### Отложить выполнение узла

Отсрочка выполнения узла полезна, когда необходимо отложить выполнение узла до завершения всех остальных ожидающих задач. Это особенно актуально, когда ветви имеют разную длину, что часто встречается в таких рабочих процессах, как потоки MapReduce.

Приведенный выше пример показал, как разветвлять и сближать ветви, когда каждая ветвь состоит всего из одного шага. Но что, если одна ветвь содержит более одного шага? Давайте добавим узел «b_2» в ветвь «b»:

```python theme={null}
импортный оператор
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    # Функция редуктора operator.add делает этот код только добавляемым.
    aggregate: Annotated[list, operator.add]

def a(state: State):
    print(f'Добавление "A" к {state["aggregate"]}')
    return {"aggregate": ["A"]}

def b(state: State):
    print(f'Добавление "B" к {state["aggregate"]}')
    return {"aggregate": ["B"]}

def b_2(state: State):
    print(f'Добавление "B_2" в {state["aggregate"]}')
    return {"aggregate": ["B_2"]}

def c(state: State):
    print(f'Добавление "C" к {state["aggregate"]}')
    return {"aggregate": ["C"]}

def d(state: State):
    print(f'Добавление "D" к {state["aggregate"]}')
    return {"aggregate": ["D"]}

builder = StateGraph(State)
builder.add_node(a)
builder.add_node(b)
builder.add_node(b_2)
builder.add_node(c)
builder.add_node(d, defer=True) # [!code highlight]
builder.add_edge(START, "a")
builder.add_edge("a", "b")
builder.add_edge("a", "c")
builder.add_edge("b", "b_2")
builder.add_edge("b_2", "d")
builder.add_edge("c", "d")
builder.add_edge("d", END)
graph = builder.compile()
```

```python theme={null}
from IPython.display import Image, display

display(Image(graph.get_graph().draw_mermaid_png())
```

<img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_4.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=44cd97f020dfefeaffbe2b012514f343" alt="График отложенного выполнения" data-og-width="161" width="161" data-og-height="531" height="531" data-path="oss/images/graph_api_image_4.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_4.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=645690182cd1ed41151da17c7d103d47 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_4.p ng?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=51cdd5ba95c2285baa2b7dc5236c8b63 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_4.png?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=e99de6c886526afdb2e7a538e3d23705 840w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_4.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=92aba13b5bbc8428e42f2ad50ba7b607 1100 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_4.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=14fda3686ef277c3f72a3ed8618c5e58 1650 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_4.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=65c543b4b79c53b9224c74631b959e0b 2500w" />

```python theme={null}
graph.invoke({"aggregate": []})
```

```
Добавление буквы «А» к []
Прибавление буквы «B» к ['A']
Добавление буквы «С» к ['А']
Добавление "B_2" к ['A', 'B', 'C']
Добавление "D" к ['A', 'B', 'C', 'B_2']
```

В приведенном выше примере узлы `"b"` и `"c"` выполняются одновременно в одном и том же супершаге. Мы устанавливаем `defer=True` для узла `d`, чтобы он не выполнялся до завершения всех ожидающих задач. В данном случае это означает, что `"d"` ожидает завершения всей ветви `"b"`.

### Условное ветвление

Если разветвление маршрута должно меняться во время выполнения в зависимости от состояния, вы можете использовать [`add_conditional_edges`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph.add_conditional_edges), чтобы выбрать один или несколько путей, используя состояние графа. См. пример ниже, где узел `a` генерирует обновление состояния, определяющее следующий узел.

```python theme={null}
импортный оператор
from typing import Annotated, Literal, Sequence
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    aggregate: Annotated[list, operator.add]
    # Добавляем ключ к состоянию. Мы будем устанавливать этот ключ для определения
    # как мы разветвляемся.
    который: стр.

def a(state: State):
    print(f'Добавление "A" к {state["aggregate"]}')
    return {"aggregate": ["A"], "which": "c"} # [!code highlight]

def b(state: State):
    print(f'Добавление "B" к {state["aggregate"]}')
    return {"aggregate": ["B"]}

def c(state: State):
    print(f'Добавление "C" к {state["aggregate"]}')
    return {"aggregate": ["C"]}

builder = StateGraph(State)
builder.add_node(a)
builder.add_node(b)
builder.add_node(c)
builder.add_edge(START, "a")
builder.add_edge("b", END)
builder.add_edge("c", END)

def conditional_edge(state: State) -> Literal["b", "c"]:
    # Здесь можно вставить произвольную логику, использующую состояние.
    # для определения следующего узла
    возвращаем состояние["который"]

builder.add_conditional_edges("a", conditional_edge) # [!code highlight]

graph = builder.compile()
```

```python theme={null}
from IPython.display import Image, display

display(Image(graph.get_graph().draw_mermaid_png())
```

<img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_5.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=3373a383d5acc3e4d6a4d1575e849146" alt="Условный ветвящийся граф" data-og-width="143" width="143" data-og-height="333" height="333" data-path="oss/images/graph_api_image_5.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_5.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=addc707d8e23e088279d93e61cd4429c 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_5.p ng?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=9b0779c2c5444a984a67617640449b26 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_5.png?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=77a82cd36bc56637b4c3bdd0bccc656a 840w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_5.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=fd83ca7056bb93a4a72187b4aeed3873 1100w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_5.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=5c57aebb9c69aa7bce3f77adcaee11a4 1650 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_5.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=0e256ff324997275e003ee62809e030d 2500 Вт" />

```python theme={null}
result = graph.invoke({"aggregate": []})
print(result)
```

```
Добавление буквы «А» к []
Добавление буквы «С» к ['А']
{'aggregate': ['A', 'C'], 'which': 'c'}
```

<Совет>
  Ваши условные ребра могут направлять трафик к нескольким целевым узлам. Например:

  ```python theme={null}
  def route_bc_or_cd(state: State) -> Sequence[str]:
      если state["which"] == "cd":
          return ["c", "d"]
      return ["b", "c"]
  ```
</Совет>

## MapReduce и API отправки

LangGraph поддерживает map-reduce и другие сложные схемы ветвления с помощью Send API. Вот пример его использования:

```python theme={null}
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from typing_extensions import TypedDict, Annotated
импортный оператор

class OverallState(TypedDict):
    тема: строка
    темы: список[str]
    шутки: Аннотированные[список[строка], оператор.добавить]
    best_selected_joke: str

def generate_topics(state: OverallState):
    return {"subjects": ["lions", "elephants", "penguins"]}

def generate_joke(state: OverallState):
    joke_map = {
        «Львы»: «Почему львы не любят фастфуд? Потому что они не могут его поймать!»
        «Слоны»: «Почему слоны не пользуются компьютерами? Они боятся мышей!»
        «Пингвины»: «Почему пингвины не любят разговаривать с незнакомцами на вечеринках? Потому что им трудно завязать разговор».
    }
    return {"jokes": [joke_map[state["subject"]]]}

def continue_to_jokes(state: OverallState):
    return [Send("generate_joke", {"subject": s}) for s in state["subjects"]]

def best_joke(state: OverallState):
    return {"best_selected_joke": "penguins"}

builder = StateGraph(OverallState)
builder.add_node("generate_topics", generate_topics)
builder.add_node("generate_joke", generate_joke)
builder.add_node("best_joke", best_joke)
builder.add_edge(START, "generate_topics")
builder.add_conditional_edges("generate_topics", continue_to_jokes, ["generate_joke"])
builder.add_edge("generate_joke", "best_joke")
builder.add_edge("best_joke", END)
graph = builder.compile()
```

```python theme={null}
from IPython.display import Image, display

display(Image(graph.get_graph().draw_mermaid_png())
```

<img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_6.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=48249d2085e8bfc63a142ccfba5082f5" alt="Граф Map-reduce с разветвлением" data-og-width="160" width="160" data-og-height="432" height="432" data-path="oss/images/graph_api_image_6.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_6.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=f37fee0612923f1363e110025a9b9727 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_6.p ng?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=83f39ecd3959718bbe11e2a3eaa6d8ef 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_6.p ng?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=9edacf5d4a433e39922b4bc003906b9d 840 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_6.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=3627608cc06068c975bff51e98247889 1100 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_6.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=70d18d5cb2ed9e706aea7792723d6891 1650w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_6.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=03f4b27152e455d84d589c0c46c2324d 2500w" />

```python theme={null}
# Вызов графа: здесь мы вызываем его для генерации списка шуток
for step in graph.stream({"topic": "animals"}):
    print(step)
```

```
{'generate_topics': {'subjects': ['lions', 'elephants', 'penguins']}}
{'generate_joke': {'jokes': ["Почему львы не любят фастфуд? Потому что они не могут его поймать!"]}}
{'generate_joke': {'jokes': ["Почему слоны не пользуются компьютерами? Они боятся мыши!"]}}
{'generate_joke': {'jokes': ['Почему пингвины не любят разговаривать с незнакомцами на вечеринках? Потому что им трудно завязать разговор.']}}
{'best_joke': {'best_selected_joke': 'penguins'}}
```

## Создание и управление циклами

При создании графа с циклом нам необходим механизм для завершения выполнения. Чаще всего это делается путем добавления [условного ребра](/oss/python/langgraph/graph-api#conditional-edges), которое перенаправляет к узлу [END](/oss/python/langgraph/graph-api#end-node) после достижения определенного условия завершения.

Вы также можете установить ограничение на рекурсию графа при его вызове или потоковой передаче. Ограничение на рекурсию определяет количество [супершагов](/oss/python/langgraph/graph-api#graphs), которые граф может выполнить до того, как выдаст ошибку. Подробнее о концепции ограничений на рекурсию можно прочитать [здесь](/oss/python/langgraph/graph-api#recursion-limit).

Рассмотрим простой граф с петлей, чтобы лучше понять, как работают эти механизмы.

<Совет>
  Чтобы вместо ошибки ограничения рекурсии получить последнее значение вашего состояния, см. [следующий раздел](#impose-a-recursion-limit).
</Совет>

При создании цикла можно включить условное ребро, определяющее условие завершения:

```python theme={null}
builder = StateGraph(State)
builder.add_node(a)
builder.add_node(b)

def route(state: State) -> Literal["b", END]:
    если termination_condition(state):
        возврат КОНЕЦ
    еще:
        вернуть "b"

builder.add_edge(START, "a")
builder.add_conditional_edges("a", route)
builder.add_edge("b", "a")
graph = builder.compile()
```

Для управления ограничением рекурсии укажите `recursionLimit` в конфигурации. Это вызовет ошибку `GraphRecursionError`, которую вы можете перехватить и обработать:

```python theme={null}
from langgraph.errors import GraphRecursionError

пытаться:
    graph.invoke(inputs, {"recursion_limit": 3})
за исключением GraphRecursionError:
    print("Ошибка рекурсии")
```

Давайте определим граф с простым циклом. Обратите внимание, что для реализации условия завершения мы используем условное ребро.

```python theme={null}
импортный оператор
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END

class State(TypedDict):
    # Функция редуктора operator.add делает этот код только добавляемым.
    aggregate: Annotated[list, operator.add]

def a(state: State):
    print(f'Узел A видит {state["aggregate"]}')
    return {"aggregate": ["A"]}

def b(state: State):
    print(f'Узел B видит {state["aggregate"]}')
    return {"aggregate": ["B"]}

# Определение узлов
builder = StateGraph(State)
builder.add_node(a)
builder.add_node(b)

# Определение ребер
def route(state: State) -> Literal["b", END]:
    если len(state["aggregate"]) < 7:
        вернуть "b"
    еще:
        возврат КОНЕЦ

builder.add_edge(START, "a")
builder.add_conditional_edges("a", route)
builder.add_edge("b", "a")
graph = builder.compile()
```

```python theme={null}
from IPython.display import Image, display

display(Image(graph.get_graph().draw_mermaid_png())
```

<img src="https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_7.png?fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=e1b99e7efe45b1fdc5836d590d5fbbc3" alt="Simple loop graph" data-og-width="188" width="188" data-og-height="249" height="249" data-path="oss/images/graph_api_image_7.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_7.png?w=280&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=a443c1ddc2f6a4e7c73f4482c7d63912 280w, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_7.p ng?w=560&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=f65d82d8aaeb024beb5da1aa2948bcdb 560 Вт, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_7.png?w=840&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=b95f4df2fb69f28779a1d8dd113409d0 840w, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_7.png?w=1100&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=bdb4011d05756c10a1c7b5dea683fdb7 1100w, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_7.png?w=1650&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=dde791caa4279a6248b59b70df99dd2c 1650w, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_7.png?w=2500&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=e4d568719f1761ff3a3d2ea9175241d8 2500w" />

Эта архитектура похожа на [агент ReAct](/oss/python/langgraph/workflows-agents), в котором узел «a» представляет собой модель вызова инструментов, а узел «b» — сами инструменты.

В нашем условном ребре `route` мы указываем, что маршрут должен завершиться после того, как длина списка `"aggregate"` в состоянии превысит пороговое значение.

Обращаясь к графу, мы видим, что чередуем узлы «a» и «b», прежде чем завершить работу, достигнув условия завершения.

```python theme={null}
graph.invoke({"aggregate": []})
```

```
Узел А видит []
Узел B видит ['A']
Узел А видит ['A', 'B']
Узел B видит ['A', 'B', 'A']
Узел A видит ['A', 'B', 'A', 'B']
Узел B видит ['A', 'B', 'A', 'B', 'A']
Узел A видит ['A', 'B', 'A', 'B', 'A', 'B']
```

### Установить ограничение на рекурсию

В некоторых приложениях у нас может не быть гарантии достижения заданного условия завершения. В таких случаях мы можем установить [лимит рекурсии](/oss/python/langgraph/graph-api#recursion-limit) для графа. Это вызовет ошибку `GraphRecursionError` после заданного количества [супершагов](/oss/python/langgraph/graph-api#graphs). Затем мы можем перехватить и обработать это исключение:

```python theme={null}
from langgraph.errors import GraphRecursionError

пытаться:
    graph.invoke({"aggregate": []}, {"recursion_limit": 4})
за исключением GraphRecursionError:
    print("Ошибка рекурсии")
```

```
Узел А видит []
Узел B видит ['A']
Узел C видит ['A', 'B']
Узел D видит ['A', 'B']
Узел A видит ['A', 'B', 'C', 'D']
Ошибка рекурсии
```

<Заголовок аккордеона="Расширенный пример: возврат состояния при достижении лимита рекурсии">
  Вместо того чтобы вызывать `GraphRecursionError`, мы можем ввести в состояние новый ключ, который будет отслеживать количество оставшихся шагов до достижения лимита рекурсии. Затем мы можем использовать этот ключ, чтобы определить, следует ли завершить выполнение.

  LangGraph использует специальную аннотацию `RemainingSteps`. Внутри она создает канал `ManagedValue` — канал состояния, который будет существовать на протяжении всего выполнения графа и не будет существовать дольше.

  ```python theme={null}
  импортный оператор
  from typing import Annotated, Literal
  from typing_extensions import TypedDict
  from langgraph.graph import StateGraph, START, END
  from langgraph.managed.is_last_step import RemainingSteps

  class State(TypedDict):
      aggregate: Annotated[list, operator.add]
      remaining_steps: RemainingSteps

  def a(state: State):
      print(f'Узел A видит {state["aggregate"]}')
      return {"aggregate": ["A"]}

  def b(state: State):
      print(f'Узел B видит {state["aggregate"]}')
      return {"aggregate": ["B"]}

  # Определение узлов
  builder = StateGraph(State)
  builder.add_node(a)
  builder.add_node(b)

  # Определение ребер
  def route(state: State) -> Literal["b", END]:
      если state["remaining_steps"] <= 2:
          возврат КОНЕЦ
      еще:
          вернуть "b"

  builder.add_edge(START, "a")
  builder.add_conditional_edges("a", route)
  builder.add_edge("b", "a")
  graph = builder.compile()

  # Проверьте это
  result = graph.invoke({"aggregate": []}, {"recursion_limit": 4})
  print(result)
  ```

  ```
  Узел А видит []
  Узел B видит ['A']
  Узел А видит ['A', 'B']
  {'aggregate': ['A', 'B', 'A']}
  ```
</Аккордеон>

<Accordion title="Расширенный пример: циклы с ветвлениями">
  Чтобы лучше понять, как работает ограничение на рекурсию, рассмотрим более сложный пример. Ниже мы реализуем цикл, но один шаг разветвляется на два узла:

  ```python theme={null}
  импортный оператор
  from typing import Annotated, Literal
  from typing_extensions import TypedDict
  from langgraph.graph import StateGraph, START, END

  class State(TypedDict):
      aggregate: Annotated[list, operator.add]

  def a(state: State):
      print(f'Узел A видит {state["aggregate"]}')
      return {"aggregate": ["A"]}

  def b(state: State):
      print(f'Узел B видит {state["aggregate"]}')
      return {"aggregate": ["B"]}

  def c(state: State):
      print(f'Узел C видит {state["aggregate"]}')
      return {"aggregate": ["C"]}

  def d(state: State):
      print(f'Узел D видит {state["aggregate"]}')
      return {"aggregate": ["D"]}

  # Определение узлов
  builder = StateGraph(State)
  builder.add_node(a)
  builder.add_node(b)
  builder.add_node(c)
  builder.add_node(d)

  # Определение ребер
  def route(state: State) -> Literal["b", END]:
      если len(state["aggregate"]) < 7:
          вернуть "b"
      еще:
          возврат КОНЕЦ

  builder.add_edge(START, "a")
  builder.add_conditional_edges("a", route)
  builder.add_edge("b", "c")
  builder.add_edge("b", "d")
  builder.add_edge(["c", " d"], "a")
  graph = builder.compile()
  ```

  ```python theme={null}
  from IPython.display import Image, display

  display(Image(graph.get_graph().draw_mermaid_png())
  ```

    <img src="https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_8.png?fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=20e2a9e8c15760eb9ecb07fc411aa70e" alt="Сложный петлевой граф с ветвями" data-og-width="297" width="297" data-og-height="348" height="348" data-path="oss/images/graph_api_image_8.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_8.png?w=280&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=65ee62a3adb7bedaf7571d9ecdacb908 280w, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_8.p ng?w=560&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=e7c4c3341baeed9c747082f69d2b3ded 560 Вт, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_8.png?w=840&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=b64849cfc877d1b32422f6666d5f93a0 840w, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_8.png?w=1100&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=3d384eba95e1082504c7ef1d5309dfae 1100w, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_8.png?w=1650&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=2fef71e345a90e5c2321c0dfda15d91b 1650w, https://mintcdn.com/langchain-5e9cc07a/dL5Sn6Cmy9pwtY0V/oss/images/graph_api_image_8.png?w=2500&fit=max&auto=format&n=dL5Sn6Cmy9pwtY0V&q=85&s=09cf8e8ac3215e359e6e4304c09b3a9f 2500w" />

  Этот граф выглядит сложным, но его можно представить как цикл из [супершагов](/oss/python/langgraph/graph-api#graphs):

  1. Узел А
  2. Узел B
  3. Узлы C и D
  4. Узел А
  5. ...

  У нас есть цикл из четырех супершагов, в котором узлы C и D выполняются одновременно.

  Как и прежде, открыв граф, мы видим, что проходим два полных «круга», прежде чем достигаем условия завершения:

  ```python theme={null}
  result = graph.invoke({"aggregate": []})
  ```

  ```
  Узел А видит []
  Узел B видит ['A']
  Узел D видит ['A', 'B']
  Узел C видит ['A', 'B']
  Узел A видит ['A', 'B', 'C', 'D']
  Узел B видит ['A', 'B', 'C', 'D', 'A']
  Узел D видит ['A', 'B', 'C', 'D', 'A', 'B']
  Узел C видит ['A', 'B', 'C', 'D', 'A', 'B']
  Узел A видит ['A', 'B', 'C', 'D', 'A', 'B', 'C', 'D']
  ```

  Однако, если мы установим ограничение на количество повторений равным четырем, мы выполним только один круг, поскольку каждый круг состоит из четырех супершагов:

  ```python theme={null}
  from langgraph.errors import GraphRecursionError

  пытаться:
      result = graph.invoke({"aggregate": []}, {"recursion_limit": 4})
  за исключением GraphRecursionError:
      print("Ошибка рекурсии")
  ```

  ```
  Узел А видит []
  Узел B видит ['A']
  Узел C видит ['A', 'B']
  Узел D видит ['A', 'B']
  Узел A видит ['A', 'B', 'C', 'D']
  Ошибка рекурсии
  ```
</Аккордеон>

## Асинхронный

Использование парадигмы асинхронного программирования может значительно повысить производительность при одновременном выполнении кода, связанного с вводом-выводом (например, при одновременном выполнении запросов к API-провайдеру модели чата).

Для преобразования `синхронной` реализации графа в `асинхронную` реализацию вам потребуется:

1. При обновлении `nodes` используйте `async def` вместо `def`.
2. Обновите код внутри, чтобы использовать `await` надлежащим образом.
3. Вызовите граф с помощью `.ainvoke` или `.astream` по своему усмотрению.

Поскольку многие объекты LangChain реализуют протокол [Runnable Protocol](https://python.langchain.com/docs/expression_language/interface/), который имеет асинхронные варианты всех синхронных методов, обычно довольно быстро происходит преобразование графа с синхронными методами в граф с асинхронными методами.

См. пример ниже. Для демонстрации асинхронных вызовов базовых LLM мы включим модель чата:

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

```python theme={null}
from langchain.chat_models import init_chat_model
from langgraph.graph import MessagesState, StateGraph

async def node(state: MessagesState): # [!code highlight]
    new_message = await llm.ainvoke(state["messages"]) # [!code highlight]
    return {"messages": [new_message]}

builder = StateGraph(MessagesState).add_node(node).set_entry_point("node")
graph = builder.compile()

input_message = {"role": "user", "content": "Hello"}
result = await graph.ainvoke({"messages": [input_message]}) # [!code highlight]
```

<Совет>
  **Асинхронная потоковая передача**
  Примеры потоковой передачи с использованием асинхронных операций см. в [руководстве по потоковой передаче](/oss/python/langgraph/streaming).
</Совет>

## Объединение управления потоком выполнения и обновления состояния с помощью команды `Command`

Полезно комбинировать управление потоком выполнения (ребра) и обновление состояния (узлы). Например, вам может потребоваться как обновление состояния, так и определение следующего узла в рамках ОДНОГО И ТОГО ЖЕ узла. LangGraph предоставляет способ сделать это, возвращая объект [Command](https://langchain-ai.github.io/langgraph/reference/types/#langgraph.types.Command) из функций узлов:

```python theme={null}
def my_node(state: State) -> Command[Literal["my_other_node"]]:
    return Command(
        # обновление состояния
        update={"foo": "bar"},
        # управление потоком
        goto="my_other_node"
    )
```

Ниже мы приводим сквозной пример. Давайте создадим простой граф с тремя узлами: A, B и C. Сначала мы выполним операцию на узле A, а затем, исходя из результата работы узла A, решим, к какому узлу перейти дальше — к узлу B или к узлу C.

```python theme={null}
импорт случайных чисел
from typing_extensions import TypedDict, Literal
from langgraph.graph import StateGraph, START
from langgraph.types import Command

# Определение состояния графа
class State(TypedDict):
    foo: str

# Определение узлов

def node_a(state: State) -> Command[Literal["node_b", "node_c"]]:
    print("Called A")
    значение = случайный выбор (["b", "c"])
    # Это замена функции условного ребра
    если значение == "b":
        goto = "node_b"
    еще:
        goto = "node_c"

    Обратите внимание, что команда позволяет одновременно обновлять состояние графа и прокладывать маршрут к следующему узлу.
    return Command(
        # Это обновление состояния
        update={"foo": value},
        # Это замена для края
        перейти = перейти,
    )

def node_b(state: State):
    print("Called B")
    return {"foo": state["foo"] + "b"}

def node_c(state: State):
    print("Вызвано C")
    return {"foo": state["foo"] + "c"}
```

Теперь мы можем создать [`StateGraph`](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph) с указанными выше узлами. Обратите внимание, что в графе отсутствуют [условные ребра](/oss/python/langgraph/graph-api#conditional-edges) для маршрутизации! Это связано с тем, что управление потоком выполнения определяется с помощью [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) внутри `node_a`.

```python theme={null}
builder = StateGraph(State)
builder.add_edge(START, "node_a")
builder.add_node(node_a)
builder.add_node(node_b)
builder.add_node(node_c)
# ПРИМЕЧАНИЕ: между узлами A, B и C нет ребер!

graph = builder.compile()
```

<Предупреждение>
  Возможно, вы заметили, что мы использовали [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) в качестве аннотации типа возвращаемого значения, например, `Command[Literal["node_b", "node_c"]]`. Это необходимо для отрисовки графа и сообщает LangGraph, что `node_a` может переходить к `node_b` и `node_c`.
</Предупреждение>

```python theme={null}
from IPython.display import display, Image

display(Image(graph.get_graph().draw_mermaid_png())
```

<img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_11.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=f11e5cddedbf2760d40533f294c44aea" alt="Навигация по графу на основе команд" data-og-width="232" width="232" data-og-height="333" height="333" data-path="oss/images/graph_api_image_11.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_11.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=c1b27d92b257a6c4ac57f34f007d0ee1 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_11.p ng?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=695d0062e5fb8ebea5525379edbba476 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_11.png?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=7bd3f779df628beba60a397674f85b59 840w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_11.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=85a9194e8b4d9df2d01d10784dcf75d0 1100w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_11.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=efd9118d4bcd6d1eb92760c573645fbd 1650w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_11.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=1eb2a132386a64d18582af6978e4ac24 2500w" />

Если мы запустим граф несколько раз, то увидим, что он будет следовать по разным путям (A -> B или A -> C) в зависимости от случайного выбора в узле A.

```python theme={null}
graph.invoke({"foo": ""})
```

```
Называется А
Называется С
```

### Переход к узлу в родительском графе

Если вы используете [подграфы](/oss/python/langgraph/use-subgraphs), вам может потребоваться перейти от узла внутри подграфа к другому подграфу (т.е. к другому узлу в родительском графе). Для этого вы можете указать `graph=Command.PARENT` в `Command`:

```python theme={null}
def my_node(state: State) -> Command[Literal["my_other_node"]]:
    return Command(
        update={"foo": "bar"},
        goto="other_subgraph", # где `other_subgraph` — узел в родительском графе
        graph=Command.PARENT
    )
```

Давайте продемонстрируем это на примере выше. Для этого мы изменим `nodeA` в приведенном выше примере на граф с одним узлом, который мы добавим в качестве подграфа к нашему родительскому графу.

<Предупреждение>
  **Обновление состояния с помощью `Command.PARENT`**
  При отправке обновлений от узла подграфа к узлу родительского графа для ключа, общего для схем состояний родительского и подграфа, необходимо **определить** редуктор для обновляемого ключа в состоянии родительского графа. См. пример ниже.
</Предупреждение>

```python theme={null}
импортный оператор
from typing_extensions import Annotated

class State(TypedDict):
    # ПРИМЕЧАНИЕ: здесь мы определяем редуктор
    foo: Annotated[str, operator.add] # [!code highlight]

def node_a(state: State):
    print("Called A")
    значение = случайный выбор (["a", "b"])
    # Это замена функции условного ребра
    если значение == "a":
        goto = "node_b"
    еще:
        goto = "node_c"

    Обратите внимание, что команда позволяет одновременно обновлять состояние графа и прокладывать маршрут к следующему узлу.
    return Command(
        update={"foo": value},
        перейти = перейти,
        # Это указывает LangGraph перейти к узлу node_b или node_c в родительском графе.
        # ПРИМЕЧАНИЕ: это перенаправит вас к ближайшему родительскому графу относительно подграфа.
        graph=Command.PARENT, # [!code highlight]
    )

subgraph = StateGraph(State).add_node(node_a).add_edge(START, "node_a").compile()

def node_b(state: State):
    print("Called B")
    # ПРИМЕЧАНИЕ: поскольку мы определили редуктор, нам не нужно добавлять его вручную.
    # Добавляем новые символы к существующему значению 'foo'. Вместо этого редуктор будет добавлять их.
    # автоматически (через operator.add)
    return {"foo": "b"} # [!подсветка кода]

def node_c(state: State):
    print("Вызвано C")
    return {"foo": "c"} # [!подсветка кода]

builder = StateGraph(State)
builder.add_edge(START, "subgraph")
builder.add_node("subgraph", subgraph)
builder.add_node(node_b)
builder.add_node(node_c)

graph = builder.compile()
```

```python theme={null}
graph.invoke({"foo": ""})
```

```
Называется А
Называется С
```

### Используйте внутренние инструменты

Распространенный сценарий использования — обновление состояния графа изнутри инструмента. Например, в приложении службы поддержки клиентов может потребоваться поиск информации о клиенте по номеру его счета или идентификатору в начале разговора. Чтобы обновить состояние графа из инструмента, можно вернуть `Command(update={"my_custom_key": "foo", "messages": [...]})` из инструмента:

```python theme={null}
@инструмент
def lookup_user_info(tool_call_id: Annotated[str, InjectedToolCallId], config: RunnableConfig):
    «Используйте это для поиска информации о пользователях, чтобы лучше помогать им с их вопросами».
    user_info = get_user_info(config.get("configurable", {}).get("user_id"))
    return Command(
        обновление={
            # Обновить ключи состояния
            "user_info": user_info,
            # Обновить историю сообщений
            "messages": [ToolMessage("Информация о пользователе успешно найдена", tool_call_id=tool_call_id)]
        }
    )
```

<Предупреждение>
  При возврате команды [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) из инструмента ОБЯЗАТЕЛЬНО необходимо включить `messages` (или любой ключ состояния, используемый для истории сообщений) в `Command.update`, а список сообщений в `messages` ДОЛЖЕН содержать `ToolMessage`. Это необходимо для корректности результирующей истории сообщений (поставщики LLM требуют, чтобы сообщения ИИ с вызовами инструментов сопровождались сообщениями о результатах работы инструмента).
</Предупреждение>

Если вы используете инструменты, которые обновляют состояние через [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command), мы рекомендуем использовать предварительно созданный [`ToolNode`](https://reference.langchain.com/python/langgraph/agents/#langgraph.prebuilt.tool_node.ToolNode), который автоматически обрабатывает возвращаемые инструментами объекты [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command) и передает их в состояние графа. Если вы пишете собственный узел, который вызывает инструменты, вам потребуется вручную передавать объекты [`Command`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.Command), возвращаемые инструментами, в качестве обновления от узла.

## Визуализируйте свой график

Здесь мы покажем, как визуализировать созданные вами графики.

Вы можете визуализировать любой произвольный [граф](https://langchain-ai.github.io/langgraph/reference/graphs/), включая [граф состояний](https://langchain-ai.github.io/langgraph/reference/graphs/#langgraph.graph.state.StateGraph).

Давайте повеселимся, рисуя фракталы :).

```python theme={null}
импорт случайных чисел
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

class State(TypedDict):
    сообщения: Аннотированные[список, добавить_сообщения]

класс MyNode:
    def __init__(self, name: str):
        self.name = name
    def __call__(self, state: State):
        return {"messages": [("assistant", f"Called node {self.name}")]}

def route(state) -> Literal["entry_node", END]:
    если len(state["messages"]) > 10:
        возврат КОНЕЦ
    return "entry_node"

def add_fractal_nodes(builder, current_node, level, max_level):
    если уровень > max_level:
        возвращаться
    # Количество узлов, которые необходимо создать на этом уровне
    num_nodes = random.randint(1, 3) # При необходимости отрегулируйте случайность
    for i in range(num_nodes):
        nm = ["A", "B", "C"][i]
        node_name = f"node_{current_node}_{nm}"
        builder.add_node(node_name, MyNode(node_name))
        builder.add_edge(current_node, node_name)
        # Рекурсивно добавляем больше узлов
        r = random.random()
        если r > 0,2 и level + 1 < max_level:
            add_fractal_nodes(builder, node_name, level + 1, max_level)
        elif r > 0.05:
            builder.add_conditional_edges(node_name, route, node_name)
        еще:
            # Конец
            builder.add_edge(node_name, END)

def build_fractal_graph(max_level: int):
    builder = StateGraph(State)
    entry_point = "entry_node"
    builder.add_node(entry_point, MyNode(entry_point))
    builder.add_edge(START, entry_point)
    add_fractal_nodes(builder, entry_point, 1, max_level)
    # Необязательно: при необходимости укажите конечную точку
    builder.add_edge(entry_point, END) # или любой конкретный узел
    return builder.compile()

app = build_fractal_graph(3)
```

### Русалка

Мы также можем преобразовать класс графа в синтаксис Mermaid.

```python theme={null}
print(app.get_graph().draw_mermaid())
```

```
%%{init: {'flowchart': {'curve': 'linear'}}}%%
график TD;
    tart__([<p>__start__</p>]):::first
    ry_node(entry_node)
    e_entry_node_A(node_entry_node_A)
    e_entry_node_B(node_entry_node_B)
    e_node_entry_node_B_A(node_node_entry_node_B_A)
    e_node_entry_node_B_B(node_node_entry_node_B_B)
    e_node_entry_node_B_C(node_node_entry_node_B_C)
    nd__([<p>__end__</p>]):::last
    tart__ --> entry_node;
    ry_node --> __end__;
    ry_node --> node_entry_node_A;
    ry_node --> node_entry_node_B;
    e_entry_node_B --> node_node_entry_node_B_A;
    e_entry_node_B --> node_node_entry_node_B_B;
    e_entry_node_B --> node_node_entry_node_B_C;
    e_entry_node_A -.-> entry_node;
    e_entry_node_A -.-> __end__;
    e_node_entry_node_B_A -.-> entry_node;
    e_node_entry_node_B_A -.-> __end__;
    e_node_entry_node_B_B -.-> entry_node;
    e_node_entry_node_B_B -.-> __end__;
    e_node_entry_node_B_C -.-> entry_node;
    e_node_entry_node_B_C -.-> __end__;
    ssDef default fill:#f2f0ff,line-height:1.2
    ssDef first fill-opacity:0
    ssDef last fill:#bfb6fc
```

### PNG

При желании мы можем отобразить график в формате `.png`. Здесь мы можем использовать три варианта:

* Используется API Mermaid.ink (не требует дополнительных пакетов)
* Используется Mermaid + Pyppeteer (требуется `pip install pyppeteer`)
* Используется graphviz (для этого требуется `pip install graphviz`)

**Используется Mermaid.Ink**

По умолчанию функция `draw_mermaid_png()` использует API Mermaid.Ink для генерации диаграммы.

```python theme={null}
from IPython.display import Image, display
from langchain_core.runnables.graph import CurveStyle, MermaidDrawMethod, NodeStyles

display(Image(app.get_graph().draw_mermaid_png()))
```

<img src="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_10.png?fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=6cb916b7c627e81c2816cc74ebf3f913" alt="Визуализация фрактального графа" data-og-width="2382" width="2382" data-og-height="1131" height="1131" data-path="oss/images/graph_api_image_10.png" data-optimize="true" data-opv="3" srcset="https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_10.png?w=280&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=01b02e6994b97c652851bf1a5be524b5 280w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_10.p ng?w=560&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=9ac63a57750ff509e5bcf0662a141092 560 Вт, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_10.png?w=840&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=5458c09f31e42d0fd8f58ba85626d89c 840w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_10.png?w=1100&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=feb0a463b249cd838ad31105ef695214 1100w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_10.png?w=1650&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=1a83b92a2d3b428d9b788720a7e54184 1650w, https://mintcdn.com/langchain-5e9cc07a/-_xGPoyjhyiDWTPJ/oss/images/graph_api_image_10.png?w=2500&fit=max&auto=format&n=-_xGPoyjhyiDWTPJ&q=85&s=8bf42c6ee15584253dc036ff9b60191a 2500w" />

**Используя Mermaid + Pyppeteer**

```python theme={null}
import nest_asyncio

nest_asyncio.apply() # Необходимо для запуска асинхронных функций в Jupyter Notebook

отображать(
    Изображение(
        app.get_graph().draw_mermaid_png(
            curve_style=CurveStyle.LINEAR,
            node_colors=NodeStyles(first ffdfba", last ffdfbf9", default ffdf ...
            wrap_label_n_words=9,
            output_file_path=None,
            draw_method=MermaidDrawMethod.PYPPETEER,
            background_color="white",
            padding=10,
        )
    )
)
```

**Использование Graphviz**

```python theme={null}
пытаться:
    display(Image(app.get_graph().draw_png())
за исключением ImportError:
    print(
        «Вам, вероятно, потребуется установить зависимости для pygraphviz. Подробнее см. здесь: https://github.com/pygraphviz/pygraphviz/blob/main/INSTALL.txt»
    )
```

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langgraph/use-graph-api.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Callout>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>