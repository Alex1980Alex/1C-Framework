> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Используйте функциональный API

Функциональный API позволяет добавить ключевые возможности LangGraph — сохранение данных (persistence), добавление памяти (memory), прерывания (human-in-the-loop) и потоковую передачу (streaming) — в ваши приложения с минимальными изменениями в существующем коде.

<Совет>
  Для получения концептуальной информации о функциональном API см. [Функциональный API](/oss/python/langgraph/functional-api).
</Совет>

## Создание простого рабочего процесса

При определении точки входа (entrypoint) ввод ограничивается первым аргументом функции. Для передачи нескольких входных данных можно использовать словарь.

```python theme={null}
@entrypoint(checkpointer=checkpointer)
def my_workflow(inputs: dict) -> int:
    значение = inputs["значение"]
    another_value = inputs["another_value"]
    ...

my_workflow.invoke({"value": 1, "another_value": 2})
```

<Заголовок аккордеона="Расширенный пример: простой рабочий процесс">
  ```python theme={null}
  импорт uuid
  from langgraph.func import entrypoint, task
  from langgraph.checkpoint.memory import InMemorySaver

  # Задача, проверяющая, является ли число четным
  @задача
  def is_even(number: int) -> bool:
      возвращаемое число % 2 == 0

  # Задача, форматирующая сообщение
  @задача
  def format_message(is_even: bool) -> str:
      return "Число четное." if is_even else "Число нечетное."

  # Создание контрольной точки для сохранения данных
  checkpointer = InMemorySaver()

  @entrypoint(checkpointer=checkpointer)
  def workflow(inputs: dict) -> str:
      «Простой алгоритм классификации чисел».
      even = is_even(inputs["number"]).result()
      return format_message(even).result()

  # Запустите рабочий процесс с уникальным идентификатором потока
  config = {"configurable": {"thread_id": str(uuid.uuid4())}}
  result = workflow.invoke({"number": 7}, config=config)
  print(result)
  ```
</Аккордеон>

<Заголовок аккордеона="Расширенный пример: напишите эссе, имея степень магистра права">
  В этом примере показано, как использовать декораторы `@task` и `@entrypoint`.
  синтаксически. При наличии контрольной точки результаты рабочего процесса будут следующими.
  сохранить в контрольной точке.

  ```python theme={null}
  импорт uuid
  from langchain.chat_models import init_chat_model
  from langgraph.func import entrypoint, task
  from langgraph.checkpoint.memory import InMemorySaver

  model = init_chat_model('gpt-3.5-turbo')

  # Задание: написать эссе, используя LLM
  @задача
  def compose_essay(topic: str) -> str:
      «Напишите эссе на заданную тему».
      return model.invoke([
          {"role": "system", "content": "Вы — полезный помощник, который пишет эссе."},
          {"role": "user", "content": f"Напишите эссе на тему {topic}."}
      ]).содержание

  # Создание контрольной точки для сохранения данных
  checkpointer = InMemorySaver()

  @entrypoint(checkpointer=checkpointer)
  def workflow(topic: str) -> str:
      «Простой алгоритм, позволяющий создать эссе с дипломом магистра права».
      return compose_essay(topic).result()

  # Выполнить рабочий процесс
  config = {"configurable": {"thread_id": str(uuid.uuid4())}}
  result = workflow.invoke("История полетов", config=config)
  print(result)
  ```
</Аккордеон>

## Параллельное выполнение

Задачи можно выполнять параллельно, вызывая их одновременно и ожидая результатов. Это полезно для повышения производительности в задачах, требующих большого объема ввода-вывода (например, при вызове API для LLM).

```python theme={null}
@задача
def add_one(number: int) -> int:
    возвращаемое число + 1

@entrypoint(checkpointer=checkpointer)
def graph(numbers: list[int]) -> list[str]:
    фьючерсы = [add_one(i) for i in numbers]
    return [f.result() for f in futures]
```

<Заголовок аккордеона="Расширенный пример: параллельные вызовы LLM">
  В этом примере показано, как выполнять несколько вызовов LLM параллельно с помощью `@task`. Каждый вызов генерирует абзац на отдельную тему, а результаты объединяются в один текстовый вывод.

  ```python theme={null}
  импорт uuid
  from langchain.chat_models import init_chat_model
  from langgraph.func import entrypoint, task
  from langgraph.checkpoint.memory import InMemorySaver

  # Инициализация модели LLM
  model = init_chat_model("gpt-3.5-turbo")

  # Задача, которая генерирует абзац на заданную тему
  @задача
  def generate_paragraph(topic: str) -> str:
      response = model.invoke([
          {"role": "system", "content": "Вы — полезный помощник, который пишет образовательные абзацы."},
          {"role": "user", "content": f"Напишите абзац на тему {topic}."}
      ])
      return response.content

  # Создание контрольной точки для сохранения данных
  checkpointer = InMemorySaver()

  @entrypoint(checkpointer=checkpointer)
  def workflow(topics: list[str]) -> str:
      «Создает несколько абзацев параллельно и объединяет их».
      futures = [generate_paragraph(topic) for topic in topics]
      абзацы = [f.result() for f in futures]
      return "\n\n".join(paragraphs)

  # Запуск рабочего процесса
  config = {"configurable": {"thread_id": str(uuid.uuid4())}}
  result = workflow.invoke(["квантовые вычисления", "изменение климата", "история авиации"], config=config)
  print(result)
  ```

  В этом примере используется модель параллельного выполнения LangGraph для улучшения времени выполнения, особенно когда задачи включают операции ввода-вывода, такие как автозавершение LLM.
</Аккордеон>

## Вызов графов

**Функциональный API** и [**Graph API**](/oss/python/langgraph/graph-api) можно использовать вместе в одном приложении, поскольку они используют одну и ту же базовую среду выполнения.

```python theme={null}
from langgraph.func import entrypoint
from langgraph.graph import StateGraph

builder = StateGraph()
...
some_graph = builder.compile()

@entrypoint()
def some_workflow(some_input: dict) -> int:
    # Вызов графа, определенного с помощью API графов
    result_1 = some_graph.invoke(...)
    # Вызов другого графа, определенного с помощью API графов
    result_2 = another_graph.invoke(...)
    возвращаться {
        "result_1": result_1,
        "result_2": result_2
    }
```

<Заголовок аккордеона="Расширенный пример: вызов простого графа из функционального API">
  ```python theme={null}
  импорт uuid
  from typing import TypedDict
  from langgraph.func import entrypoint
  from langgraph.checkpoint.memory import InMemorySaver
  from langgraph.graph import StateGraph

  # Определение типа общего состояния
  class State(TypedDict):
      foo: int

  # Определите простой узел преобразования
  def double(state: State) -> State:
      return {"foo": state["foo"] * 2}

  # Создание графа с использованием Graph API
  builder = StateGraph(State)
  builder.add_node("double", double)
  builder.set_entry_point("double")
  graph = builder.compile()

  # Определение функционального рабочего процесса API
  checkpointer = InMemorySaver()

  @entrypoint(checkpointer=checkpointer)
  def workflow(x: int) -> dict:
      result = graph.invoke({"foo": x})
      return {"bar": result["foo"]}

  # Выполнить рабочий процесс
  config = {"configurable": {"thread_id": str(uuid.uuid4())}}
  print(workflow.invoke(5, config=config)) # Вывод: {'bar': 10}
  ```
</Аккордеон>

## Вызов других точек входа

Вы можете вызывать другие **точки входа** из **точки входа** или **задачи**.

```python theme={null}
@entrypoint() # Автоматически будет использовать контрольную точку из родительской точки входа
def some_other_workflow(inputs: dict) -> int:
    return inputs["value"]

@entrypoint(checkpointer=checkpointer)
def my_workflow(inputs: dict) -> int:
    значение = some_other_workflow.invoke({"значение": 1})
    возвращаемое значение
```

<Заголовок аккордеона="Расширенный пример: вызов другой точки входа">
  ```python theme={null}
  импорт uuid
  from langgraph.func import entrypoint
  from langgraph.checkpoint.memory import InMemorySaver

  # Инициализация контрольной точки
  checkpointer = InMemorySaver()

  # Многократно используемый подпроцесс, который умножает число
  @entrypoint()
  def multiply(inputs: dict) -> int:
      return inputs["a"] * inputs["b"]

  # Основной рабочий процесс, запускающий подпроцесс
  @entrypoint(checkpointer=checkpointer)
  def main(inputs: dict) -> dict:
      result = multiply.invoke({"a": inputs["x"], "b": inputs["y"]})
      return {"product": result}

  # Выполнить основной рабочий процесс
  config = {"configurable": {"thread_id": str(uuid.uuid4())}}
  print(main.invoke({"x": 6, "y": 7}, config=config)) # Вывод: {'product': 42}
  ```
</Аккордеон>

## Потоковое вещание

**Функциональный API** использует тот же механизм потоковой передачи, что и **Graph API**. Пожалуйста,
Для получения более подробной информации ознакомьтесь с разделом [**streaming guide**](/oss/python/langgraph/streaming).

Пример использования потокового API для потоковой передачи как обновлений, так и пользовательских данных.

```python theme={null}
from langgraph.func import entrypoint
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.config import get_stream_writer # [!code highlight]

checkpointer = InMemorySaver()

@entrypoint(checkpointer=checkpointer)
def main(inputs: dict) -> int:
    writer = get_stream_writer() # [!подсветка кода]
    writer("Начата обработка") # [!подсветка кода]
    результат = входные данные["x"] * 2
    writer(f"Результат: {result}") # [!подсветка кода]
    вернуть результат

config = {"configurable": {"thread_id": "abc"}}

для режима, фрагмент в main.stream( # [!подсветка кода]
    {"x": 5},
    stream_mode=["custom", "updates"], # [!code highlight]
    config=config
):
    print(f"{mode}: {chunk}")
```

1. Импортируйте [`get_stream_writer`](https://reference.langchain.com/python/langgraph/config/#langgraph.config.get_stream_writer) из `langgraph.config`.
2. Получите экземпляр потокового записывающего устройства в точке входа.
3. Перед началом вычислений необходимо вывести пользовательские данные.
4. После вычисления результата отправить еще одно пользовательское сообщение.
5. Используйте `.stream()` для обработки потокового вывода.
6. Укажите, какие режимы потоковой передачи использовать.

```pycon theme={null}
('updates', {'add_one': 2})
('updates', {'add_two': 3})
('custom', 'hello')
('custom', 'world')
('updates', {'main': 5})
```

<Предупреждение>
  **Асинхронная обработка с Python < 3.11**
  Если вы используете Python < 3.11 и пишете асинхронный код, использование [`get_stream_writer`](https://reference.langchain.com/python/langgraph/config/#langgraph.config.get_stream_writer) не сработает. Вместо этого, пожалуйста,
  Используйте класс `StreamWriter` напрямую. Дополнительные сведения см. в разделе [Асинхронные операции в Python < 3.11](/oss/python/langgraph/streaming#async).

  ```python theme={null}
  from langgraph.types import StreamWriter

  @entrypoint(checkpointer=checkpointer)
  async def main(inputs: dict, writer: StreamWriter) -> int: # [!code highlight]
  ...
  ```
</Предупреждение>

## Политика повторных попыток

```python theme={null}
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import RetryPolicy

# Эта переменная используется исключительно в демонстрационных целях для имитации сбоя сети.
# В вашем реальном коде этого не будет.
попыток = 0

# Давайте настроим RetryPolicy для повторной попытки при возникновении ошибки ValueError.
# Политика повторных попыток по умолчанию оптимизирована для повторной отправки сообщений об определенных сетевых ошибках.
retry_policy = RetryPolicy(retry_on=ValueError)

@task(retry_policy=retry_policy)
def get_info():
    глобальные попытки
    попытки += 1

    если попыток < 2:
        вызвать ValueError('Failure')
    вернуть "ОК"

checkpointer = InMemorySaver()

@entrypoint(checkpointer=checkpointer)
def main(inputs, writer):
    return get_info().result()

config = {
    "настраиваемый": {
        "thread_id": "1"
    }
}

main.invoke({'any_input': 'foobar'}, config=config)
```

```pycon theme={null}
'ХОРОШО'
```

## Задачи кэширования

```python theme={null}
время импорта
from langgraph.cache.memory import InMemoryCache
from langgraph.func import entrypoint, task
from langgraph.types import CachePolicy


@task(cache_policy=CachePolicy(ttl=120)) # [!code highlight]
def slow_add(x: int) -> int:
    time.sleep(1)
    вернуть x * 2


@entrypoint(cache=InMemoryCache())
def main(inputs: dict) -> dict[str, int]:
    result1 = slow_add(inputs["x"]).result()
    result2 = slow_add(inputs["x"]).result()
    return {"result1": result1, "result2": result2}


for chunk in main.stream({"x": 5}, stream_mode="updates"):
    print(chunk)

#> {'slow_add': 10}
#> {'slow_add': 10, '__metadata__': {'cached': True}}
#> {'main': {'result1': 10, 'result2': 10}}
```

1. Параметр `ttl` указывается в секундах. По истечении этого времени кэш будет аннулирован.

## Возобновление работы после ошибки

```python theme={null}
время импорта
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.func import entrypoint, task
from langgraph.types import StreamWriter

# Эта переменная используется исключительно в демонстрационных целях для имитации сбоя сети.
# В вашем реальном коде этого не будет.
попыток = 0

@задача()
def get_info():
    """
    Имитирует задачу, которая сначала терпит неудачу, а затем успешно завершается.
    При первой попытке вызывается исключение, затем при последующих попытках возвращается "OK".
    """
    глобальные попытки
    попытки += 1

    если попыток < 2:
        raise ValueError("Failure") # Имитация сбоя при первой попытке
    вернуть "ОК"

# Инициализация контрольной точки в памяти для обеспечения сохранения данных
checkpointer = InMemorySaver()

@задача
def slow_task():
    """
    Имитирует медленно выполняющуюся задачу, вводя задержку в 1 секунду.
    """
    time.sleep(1)
    return "Задача выполняется медленно."

@entrypoint(checkpointer=checkpointer)
def main(inputs, writer: StreamWriter):
    """
    Основная функция рабочего процесса, которая последовательно выполняет задачи slow_task и get_info.

    Параметры:
    - Входные данные: Словарь, содержащий значения входных данных для рабочего процесса.
    - writer: StreamWriter для потоковой передачи пользовательских данных.

    В ходе рабочего процесса сначала выполняется `slow_task`, а затем предпринимается попытка выполнить `get_info`.
    что приведёт к ошибке при первом же вызове.
    """
    slow_task_result = slow_task().result() # Блокирующий вызов slow_task
    get_info().result() # Здесь будет сгенерировано исключение при первой попытке
    return slow_task_result

# Конфигурация выполнения рабочего процесса с уникальным идентификатором потока
config = {
    "настраиваемый": {
        "thread_id": "1" # Уникальный идентификатор для отслеживания выполнения рабочего процесса
    }
}

# Этот вызов займет около 1 секунды из-за выполнения задачи slow_task.
пытаться:
    # Первый вызов вызовет исключение из-за сбоя задачи `get_info`.
    main.invoke({'any_input': 'foobar'}, config=config)
except ValueError:
    проход # Обработка ошибки корректно
```

После возобновления выполнения нам не потребуется повторно запускать задачу `slow_task`, поскольку ее результат уже сохранен в контрольной точке.

```python theme={null}
main.invoke(None, config=config)
```

```pycon theme={null}
«Задание выполнялось медленно».
```

## Человек в процессе

Функциональный API поддерживает рабочие процессы с участием человека (human-in-the-loop) с использованием функции [`interrupt`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.interrupt) и примитива `Command`.

### Базовый рабочий процесс с участием человека

Мы создадим три [задачи](/oss/python/langgraph/functional-api#task):

1. Добавьте «bar».
2. Сделайте паузу для ввода данных пользователем. При возобновлении работы добавьте данные, введенные пользователем.
3. Добавить `"qux"`.

```python theme={null}
from langgraph.func import entrypoint, task
from langgraph.types import Command, interrupt


@задача
def step_1(input_query):
    """Добавить строку.""
    return f"{input_query} bar"


@задача
def human_feedback(input_query):
    «Добавить пользовательский ввод».
    feedback = interrupt(f"Пожалуйста, предоставьте отзыв: {input_query}")
    return f"{input_query} {feedback}"


@задача
def step_3(input_query):
    """Добавить qux."""
    return f"{input_query} qux"
```

Теперь мы можем объединять эти задачи в [точку входа](/oss/python/langgraph/functional-api#entrypoint):

```python theme={null}
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()


@entrypoint(checkpointer=checkpointer)
def graph(input_query):
    result_1 = step_1(input_query).result()
    result_2 = human_feedback(result_1).result()
    result_3 = step_3(result_2).result()

    return result_3
```

Функция [interrupt()](/oss/python/langgraph/interrupts#pause-using-interrupt) вызывается внутри задачи, позволяя пользователю просмотреть и отредактировать результат предыдущей задачи. Результаты предыдущих задач — в данном случае `step_1` — сохраняются, поэтому они не запускаются повторно после вызова [`interrupt`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.interrupt).

Давайте отправим строку запроса:

```python theme={null}
config = {"configurable": {"thread_id": "1"}}

for event in graph.stream("foo", config):
    print(event)
    print("\n")
```

Обратите внимание, что после `step_1` мы приостановили выполнение с помощью прерывания (`interrupt`) (https://reference.langchain.com/python/langgraph/types/#langgraph.types.interrupt). Прерывание содержит инструкции для возобновления выполнения. Для возобновления мы отправляем команду (`Command`) (/oss/python/langgraph/interrupts#resuming-interrupts), содержащую данные, ожидаемые задачей `human_feedback`.

```python theme={null}
# Продолжить выполнение
for event in graph.stream(Command(resume="baz"), config):
    print(event)
    print("\n")
```

После возобновления выполнения программа продолжает работу до оставшегося этапа и завершается, как и ожидалось.

### Вызовы инструментов проверки

Для проверки вызовов инструментов перед выполнением мы добавляем функцию `review_tool_call`, которая вызывает [`interrupt`](/oss/python/langgraph/interrupts#pause-using-interrupt). При вызове этой функции выполнение будет приостановлено до тех пор, пока мы не выдадим команду на его возобновление.

При получении вызова инструмента наша функция прервётся для проверки человеком. В этот момент мы можем либо:

* Принять вызов инструмента
* Измените вызов инструмента и продолжите.
* Сгенерировать пользовательское сообщение для инструмента (например, дать модели указание переформатировать вызов инструмента).

```python theme={null}
из набора текста импорт Union

def review_tool_call(tool_call: ToolCall) -> Union[ToolCall, ToolMessage]:
    «Проверяет вызов инструмента, возвращая проверенную версию».
    human_review = interrupt(
        {
            "Вопрос": "Это правильно?",
            "tool_call": tool_call,
        }
    )
    review_action = human_review["action"]
    review_data = human_review.get("data")
    если review_action == "продолжить":
        return tool_call
    elif review_action == "update":
        updated_tool_call = {**tool_call, **{"args": review_data}}
        return updated_tool_call
    elif review_action == "feedback":
        return ToolMessage(
            content=review_data, name=tool_call["name"], tool_call_id=tool_call["id"]
        )
```

Теперь мы можем обновить наш [entrypoint](/oss/python/langgraph/functional-api#entrypoint), чтобы проверить сгенерированные вызовы инструментов. Если вызов инструмента принят или изменен, мы выполняем его так же, как и раньше. В противном случае мы просто добавляем [`ToolMessage`](https://reference.langchain.com/python/langchain/messages/#langchain.messages.ToolMessage), предоставленный человеком. Результаты предыдущих задач — в данном случае, первоначальный вызов модели — сохраняются, так что они не будут выполняться снова после [`interrupt`](https://reference.langchain.com/python/langgraph/types/#langgraph.types.interrupt).

```python theme={null}
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt


checkpointer = InMemorySaver()


@entrypoint(checkpointer=checkpointer)
def agent(messages, previous):
    если previous не равен None:
        сообщения = add_messages(previous, messages)

    model_response = call_model(messages).result()
    пока истинно:
        if not model_response.tool_calls:
            перерыв

        # Проверка вызовов инструментов
        tool_results = []
        tool_calls = []
        for i, tool_call in enumerate(model_response.tool_calls):
            review = review_tool_call(tool_call)
            if isinstance(review, ToolMessage):
                tool_results.append(review)
            else: # — это проверенный вызов инструмента
                tool_calls.append(review)
                если review != tool_call:
                    model_response.tool_calls[i] = review # обновление сообщения

        # Выполнить оставшиеся вызовы инструментов
        tool_result_futures = [call_tool(tool_call) for tool_call in tool_calls]
        remaining_tool_results = [fut.result() for fut in tool_result_futures]

        # Добавить в список сообщений
        сообщения = add_messages(
            сообщения,
            [model_response, *tool_results, *remaining_tool_results],
        )

        # Вызовите модель еще раз
        model_response = call_model(messages).result()

    # Сгенерировать окончательный ответ
    messages = add_messages(messages, model_response)
    return entrypoint.final(value=model_response, save=messages)
```

## Кратковременная память

Кратковременная память позволяет хранить информацию между различными **вызовами** одного и того же **идентификатора потока**. Подробнее см. [кратковременная память](/oss/python/langgraph/functional-api#short-term-memory).

### Управление контрольными точками

Вы можете просматривать и удалять информацию, сохраненную контрольной точкой.

<a id="checkpoint" />

#### Просмотреть состояние потока

```python theme={null}
config = {
    "настраиваемый": {
        "thread_id": "1", # [!code highlight]
        # При желании можно указать идентификатор для конкретной контрольной точки.
        # В противном случае отображается последняя контрольная точка
        # "checkpoint_id": "1f029ca3-1f5b-6704-8004-820c16b69a5a" # [!code highlight]

    }
}
graph.get_state(config) # [!code highlight]
```

```
Снимок состояния
    values={'messages': [HumanMessage(content="Привет! Я Боб"), AIMessage(content='Привет, Боб! Как дела сегодня?'), HumanMessage(content="Как меня зовут?"), AIMessage(content='Твое имя Боб.')]}, next=(),
    config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1f029ca3-1f5b-6704-8004-820c16b69a5a'}},
    метаданные={
        'источник': 'цикл',
        'writes': {'call_model': {'messages': AIMessage(content='Ваше имя Боб.')}},
        'шаг': 4,
        'родители': {},
        'thread_id': '1'
    },
    created_at='2025-05-05T16:01:24.680462+00:00',
    parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1f029ca3-1790-6b0a-8003-baf965b6a38f'}},
    задачи=(),
    прерывания=()
)
```

<a id="checkpoints" />

#### Просмотреть историю обсуждения

```python theme={null}
config = {
    "настраиваемый": {
        "thread_id": "1" # [!code highlight]
    }
}
list(graph.get_state_history(config)) # [!code highlight]
```

```
[
    Снимок состояния
        values={'messages': [HumanMessage(content="Привет! Я Боб"), AIMessage(content='Привет, Боб! Как дела? Могу я чем-нибудь помочь?'), HumanMessage(content="Как меня зовут?"), AIMessage(content='Твое имя Боб.')]},
        следующий=(),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1f029ca3-1f5b-6704-8004-820c16b69a5a'}},
        metadata={'source': 'loop', 'writes': {'call_model': {'messages': AIMessage(content='Ваше имя Боб.')}}, 'step': 4, 'parents': {}, 'thread_id': '1'},
        created_at='2025-05-05T16:01:24.680462+00:00',
        parent_config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1f029ca3-1790-6b0a-8003-baf965b6a38f'}},
        задачи=(),
        прерывания=()
    ),
    Снимок состояния
        values={'messages': [HumanMessage(content="Привет! Я Боб"), AIMessage(content='Привет, Боб! Как дела сегодня? Могу я чем-нибудь помочь?'), HumanMessage(content="Как меня зовут?")]},
        next=('call_model',),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1f029ca3-1790-6b0a-8003-baf965b6a38f'}},
        метаданные={'source': 'loop', 'writes': None, 'step': 3, 'parents': {}, 'thread_id': '1'},
        created_at='2025-05-05T16:01:23.863421+00:00',
        parent_config={...}
        tasks=(PregelTask(id='8ab4155e-6b15-b885-9ce5-bed69a2c305c', name='call_model', path=('__pregel_pull', 'call_model'), error=None, interrupts=(), state=None, result={'messages': AIMessage(content='Ваше имя Боб.')}),),
        прерывания=()
    ),
    Снимок состояния
        values={'messages': [HumanMessage(content="Привет! Я Боб"), AIMessage(content='Привет, Боб! Как дела сегодня? Могу ли я чем-нибудь тебе помочь?')]},
        next=('__start__',),
        config={...},
        metadata={'source': 'input', 'writes': {'__start__': {'messages': [{'role': 'user', 'content': "Как меня зовут?"}]}}, 'step': 2, 'parents': {}, 'thread_id': '1'},
        created_at='2025-05-05T16:01:23.863173+00:00',
        parent_config={...}
        tasks=(PregelTask(id='24ba39d6-6db1-4c9b-f4c5-682aeaf38dcd', name='__start__', path=('__pregel_pull', '__start__'), error=None, interrupts=(), state=None, result={'messages': [{'role': 'user', 'content': "Как меня зовут?"}]}),),
        прерывания=()
    ),
    Снимок состояния
        values={'messages': [HumanMessage(content="Привет! Я Боб"), AIMessage(content='Привет, Боб! Как дела сегодня? Могу ли я чем-нибудь тебе помочь?')]},
        следующий=(),
        config={...},
        metadata={'source': 'loop', 'writes': {'call_model': {'messages': AIMessage(content='Привет, Боб! Как дела? Могу ли я чем-нибудь тебе помочь?')}}, 'step': 1, 'parents': {}, 'thread_id': '1'},
        created_at='2025-05-05T16:01:23.862295+00:00',
        parent_config={...}
        задачи=(),
        прерывания=()
    ),
    Снимок состояния
        values={'messages': [HumanMessage(content="Привет! Я Боб")]},
        next=('call_model',),
        config={...},
        metadata={'source': 'loop', 'writes': None, 'step': 0, 'parents': {}, 'thread_id': '1'},
        created_at='2025-05-05T16:01:22.278960+00:00',
        parent_config={...}
        tasks=(PregelTask(id='8cbd75e0-3720-b056-04f7-71ac805140a0', name='call_model', path=('__pregel_pull', 'call_model'), error=None, interrupts=(), state=None, result={'messages': AIMessage(content='Привет, Боб! Как дела сегодня? Могу ли я чем-нибудь тебе помочь?')}),),
        прерывания=()
    ),
    Снимок состояния
        значения={'messages': []},
        next=('__start__',),
        config={'configurable': {'thread_id': '1', 'checkpoint_ns': '', 'checkpoint_id': '1f029ca3-0870-6ce2-bfff-1f3f14c3e565'}},
        metadata={'source': 'input', 'writes': {'__start__': {'messages': [{'role': 'user', 'content': "Привет! Я Боб"}]}}, 'step': -1, 'parents': {}, 'thread_id': '1'},
        created_at='2025-05-05T16:01:22.277497+00:00',
        parent_config=None,
        tasks=(PregelTask(id='d458367b-8265-812c-18e2-33001d199ce6', name='__start__', path=('__pregel_pull', '__start__'), error=None, interrupts=(), state=None, result={'messages': [{'role': 'user', 'content': "Привет! Я Боб"}]}),),
        прерывания=()
    )
]
```

### Разделение возвращаемого значения и сохраненного значения

Используйте `entrypoint.final`, чтобы отделить возвращаемые вызывающей стороне данные от данных, сохраненных в контрольной точке. Это полезно в следующих случаях:

* Вы хотите вернуть вычисленный результат (например, сводку или статус), но сохранить другое внутреннее значение для использования при следующем вызове.
* Необходимо контролировать, какие параметры будут переданы предыдущему параметру при следующем запуске.

```python theme={null}
from langgraph.func import entrypoint
from langgraph.checkpoint.memory import InMemorySaver

checkpointer = InMemorySaver()

@entrypoint(checkpointer=checkpointer)
def accumulate(n: int, *, previous: int | None) -> entrypoint.final[int, int]:
    предыдущий = предыдущий или 0
    итого = предыдущий + n
    # Возвращаем *предыдущее* значение вызывающей стороне, но сохраняем *новую* итоговую сумму в контрольной точке.
    return entrypoint.final(value=previous, save=total)

config = {"configurable": {"thread_id": "my-thread"}}

print(accumulate.invoke(1, config=config)) # 0
print(accumulate.invoke(2, config=config)) # 1
print(accumulate.invoke(3, config=config)) # 3
```

### Пример чат-бота

Пример простого чат-бота, использующего функциональный API и контрольную точку [`InMemorySaver`](https://reference.langchain.com/python/langgraph/checkpoints/#langgraph.checkpoint.memory.InMemorySaver).

Бот способен запомнить предыдущий разговор и продолжить с того места, где остановился.

```python theme={null}
from langchain.messages import BaseMessage
from langgraph.graph import add_messages
from langgraph.func import entrypoint, task
from langgraph.checkpoint.memory import InMemorySaver
from langchain_anthropic import ChatAnthropic

model = ChatAnthropic(model="claude-sonnet-4-5-20250929")

@задача
def call_model(messages: list[BaseMessage]):
    response = model.invoke(messages)
    вернуть ответ

checkpointer = InMemorySaver()

@entrypoint(checkpointer=checkpointer)
def workflow(inputs: list[BaseMessage], *, previous: list[BaseMessage]):
    если предыдущий:
        inputs = add_messages(previous, inputs)

    response = call_model(inputs).result()
    return entrypoint.final(value=response, save=add_messages(inputs, response))

config = {"configurable": {"thread_id": "1"}}
input_message = {"role": "user", "content": "hi! I'm bob"}
for chunk in workflow.stream([input_message], config, stream_mode="values"):
    chunk.pretty_print()

input_message = {"role": "user", "content": "what's my name?"}
for chunk in workflow.stream([input_message], config, stream_mode="values"):
    chunk.pretty_print()
```

## Долговременная память

[Долговременная память](/oss/python/concepts/memory#long-term-memory) позволяет хранить информацию в разных **потоках**. Это может быть полезно для получения информации о конкретном пользователе в одном разговоре и использования её в другом.

## Рабочие процессы

* [Рабочие процессы и агенты](/oss/python/langgraph/workflows-agents) руководство содержит дополнительные примеры создания рабочих процессов с использованием функционального API.

## Интеграция с другими библиотеками

* [Добавление функций LangGraph в другие фреймворки с помощью функционального API](/langsmith/deploy-other-frameworks): Добавление функций LangGraph, таких как сохранение данных, работа с памятью и потоковая передача, в другие агентские фреймворки, которые не предоставляют их по умолчанию.

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langgraph/use-functional-api.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Всплывающее сообщение>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>