> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Среда выполнения LangGraph

[`Pregel`](https://reference.langchain.com/python/langgraph/pregel/) реализует среду выполнения LangGraph, управляя выполнением приложений LangGraph.

Компиляция [StateGraph](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph) или создание [`@entrypoint`](https://reference.langchain.com/python/langgraph/func/#langgraph.func.entrypoint) приводит к созданию экземпляра [`Pregel`](https://reference.langchain.com/python/langgraph/pregel/), который можно вызвать с входными данными.

В этом руководстве в общих чертах объясняется работа среды выполнения и приводятся инструкции по непосредственной реализации приложений с помощью Pregel.

> **Примечание:** Среда выполнения [`Pregel`](https://reference.langchain.com/python/langgraph/pregel/) названа в честь [алгоритма Pregel от Google](https://research.google/pubs/pub37252/), который описывает эффективный метод для крупномасштабных параллельных вычислений с использованием графов.

## Обзор

В LangGraph Pregel объединяет [**акторов**](https://en.wikipedia.org/wiki/Actor_model) и **каналы** в единое приложение. **Акторы** считывают данные из каналов и записывают данные в каналы. Pregel организует выполнение приложения в несколько этапов, следуя модели **алгоритма Pregel**/**пакетной синхронной параллельной обработки**.

Каждый этап состоит из трех фаз:

* **План**: Определите, какие **участники** будут задействованы на этом шаге. Например, на первом шаге выберите **участников**, подписанных на специальные **входные** каналы; на последующих шагах выберите **участников**, подписанных на каналы, обновленные на предыдущем шаге.
* **Выполнение**: Выполнение всех выбранных **актеров** параллельно до завершения всех операций, сбоя одного из них или истечения таймаута. На этом этапе обновления каналов невидимы для акторов до следующего шага.
* **Обновление**: Обновите каналы значениями, указанными **актерами** на этом шаге.

Повторять до тех пор, пока для выполнения не будет выбрано ни одного **актера** или пока не будет достигнуто максимальное количество шагов.

## Актеры

**Актор** — это `PregelNode`. Он подписывается на каналы, считывает из них данные и записывает в них данные. Его можно рассматривать как **актора** в алгоритме Pregel. `PregelNodes` реализуют интерфейс Runnable из LangChain.

## Каналы

Каналы используются для связи между акторами (PregelNodes). Каждый канал имеет тип значения, тип обновления и функцию обновления, которая принимает последовательность обновлений и изменяет сохраненное значение. Каналы могут использоваться для передачи данных из одной цепочки в другую или для передачи данных из цепочки самой себе на последующем этапе. LangGraph предоставляет ряд встроенных каналов:

* [`LastValue`](https://reference.langchain.com/python/langgraph/channels/#langgraph.channels.LastValue): Канал по умолчанию, хранит последнее значение, отправленное в канал, полезно для входных и выходных значений или для передачи данных от одного шага к другому.
* [`Тема`](https://reference.langchain.com/python/langgraph/channels/#langgraph.channels.Topic): Настраиваемая тема PubSub, полезная для передачи нескольких значений между **акторами** или для накопления выходных данных. Может быть настроена на удаление дубликатов значений или на накопление значений в течение нескольких шагов.
* [`BinaryOperatorAggregate`](https://reference.langchain.com/python/langgraph/pregel/#langgraph.pregel.Pregel--advanced-channels-context-and-binaryoperatoraggregate): хранит постоянное значение, обновляемое путем применения бинарного оператора к текущему значению и каждому обновлению, отправляемому в канал; полезно для вычисления агрегатов в несколько этапов; например, `total = BinaryOperatorAggregate(int, operator.add)`

## Примеры

Хотя большинство пользователей будут взаимодействовать с Pregel через API [StateGraph](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph) или декоратор [`@entrypoint`](https://reference.langchain.com/python/langgraph/func/#langgraph.func.entrypoint), существует также возможность прямого взаимодействия с Pregel.

Ниже приведены несколько примеров, которые помогут вам составить представление об API Pregel.

<Вкладки>
  <Tab title="Один узел">
    ```python theme={null}
    from langgraph.channels import EphemeralValue
    из langgraph.pregel импортировать Pregel, NodeBuilder

    узел1 = (
        NodeBuilder().subscribe_only("a")
        .do(lambda x: x + x)
        .write_to("b")
    )

    приложение = Pregel(
        nodes={"node1": node1},
        каналы={
            "a": EphemeralValue(str),
            "b": EphemeralValue(str),
        },
        input_channels=["a"],
        output_channels=["b"],
    )

    app.invoke({"a": "foo"})
    ```

    ```con theme={null}
    {'b': 'foofoo'}
    ```
  </Tab>

  <Tab title="Несколько узлов">
    ```python theme={null}
    from langgraph.channels import LastValue, EphemeralValue
    из langgraph.pregel импортировать Pregel, NodeBuilder

    узел1 = (
        NodeBuilder().subscribe_only("a")
        .do(lambda x: x + x)
        .write_to("b")
    )

    узел2 = (
        NodeBuilder().subscribe_only("b")
        .do(lambda x: x + x)
        .write_to("c")
    )


    приложение = Pregel(
        nodes={"node1": node1, "node2": node2},
        каналы={
            "a": EphemeralValue(str),
            "b": LastValue(str),
            "c": EphemeralValue(str),
        },
        input_channels=["a"],
        output_channels=["b", "c"],
    )

    app.invoke({"a": "foo"})
    ```

    ```con theme={null}
    {'b': 'foofoo', 'c': 'foofoofoofoo'}
    ```
  </Tab>

  <Tab title="Тема">
    ```python theme={null}
    from langgraph.channels import EphemeralValue, Topic
    из langgraph.pregel импортировать Pregel, NodeBuilder

    узел1 = (
        NodeBuilder().subscribe_only("a")
        .do(lambda x: x + x)
        .write_to("b", "c")
    )

    узел2 = (
        NodeBuilder().subscribe_to("b")
        .do(lambda x: x["b"] + x["b"])
        .write_to("c")
    )

    приложение = Pregel(
        nodes={"node1": node1, "node2": node2},
        каналы={
            "a": EphemeralValue(str),
            "b": EphemeralValue(str),
            "c": Topic(str, accumulate=True),
        },
        input_channels=["a"],
        output_channels=["c"],
    )

    app.invoke({"a": "foo"})
    ```

    ```pycon theme={null}
    {'c': ['foofoo', 'foofoofoofoo']}
    ```
  </Tab>

  <Tab title="BinaryOperatorAggregate">
    В этом примере показано, как использовать канал [`BinaryOperatorAggregate`](https://reference.langchain.com/python/langgraph/pregel/#langgraph.pregel.Pregel--advanced-channels-context-and-binaryoperatoraggregate) для реализации редуктора.

    ```python theme={null}
    from langgraph.channels import EphemeralValue, BinaryOperatorAggregate
    из langgraph.pregel импортировать Pregel, NodeBuilder


    узел1 = (
        NodeBuilder().subscribe_only("a")
        .do(lambda x: x + x)
        .write_to("b", "c")
    )

    узел2 = (
        NodeBuilder().subscribe_only("b")
        .do(lambda x: x + x)
        .write_to("c")
    )

    def reducer(current, update):
        если актуально:
            return current + " | " + update
        еще:
            возврат обновления

    приложение = Pregel(
        nodes={"node1": node1, "node2": node2},
        каналы={
            "a": EphemeralValue(str),
            "b": EphemeralValue(str),
            "c": BinaryOperatorAggregate(str, operator=reducer),
        },
        input_channels=["a"],
        output_channels=["c"],
    )

    app.invoke({"a": "foo"})
    ```
  </Tab>

  <Tab title="Cycle">
    Этот пример демонстрирует, как ввести цикл в граф, используя
    Выполняется цепочка записей в канал, на который подписано приложение. Выполнение продолжится.
    до тех пор, пока в канал не будет записано значение `None`.

    ```python theme={null}
    from langgraph.channels import EphemeralValue
    from langgraph.pregel import Pregel, NodeBuilder, ChannelWriteEntry

    example_node = (
        NodeBuilder().subscribe_only("value")
        .do(lambda x: x + x if len(x) < 10 else None)
        .write_to(ChannelWriteEntry("value", skip_none=True))
    )

    приложение = Pregel(
        nodes={"example_node": example_node},
        каналы={
            "value": EphemeralValue(str),
        },
        input_channels=["value"],
        output_channels=["value"],
    )

    app.invoke({"value": "a"})
    ```

    ```pycon theme={null}
    {'value': 'aaaaaaaaaaaaaaaa'}
    ```
  </Tab>
</Вкладки>

## API высокого уровня

LangGraph предоставляет два высокоуровневых API для создания приложения Pregel: [StateGraph (Graph API)](/oss/python/langgraph/graph-api) и [Functional API](/oss/python/langgraph/functional-api).

<Вкладки>
  <Tab title="StateGraph (Graph API)">
    [StateGraph (Graph API)](https://reference.langchain.com/python/langgraph/graphs/#langgraph.graph.state.StateGraph) — это абстракция более высокого уровня, упрощающая создание приложений Pregel. Она позволяет определить граф узлов и ребер. При компиляции графа API StateGraph автоматически создаст для вас приложение Pregel.

    ```python theme={null}
    from typing import TypedDict

    from langgraph.constants import START
    from langgraph.graph import StateGraph

    class Essay(TypedDict):
        тема: строка
        содержимое: str | Нет
        оценка: float | Нет

    def write_essay(essay: Essay):
        возвращаться {
            "содержание": f"Эссе о {essay['topic']}",
        }

    def score_essay(essay: Essay):
        возвращаться {
            "счет": 10
        }

    builder = StateGraph(Essay)
    builder.add_node(write_essay)
    builder.add_node(score_essay)
    builder.add_edge(START, "write_essay")
    builder.add_edge("write_essay", "score_essay")

    # Скомпилировать график.
    # Эта команда вернет экземпляр Pregel.
    graph = builder.compile()
    ```

    Скомпилированный экземпляр Pregel будет связан со списком узлов и каналов. Вы можете просмотреть узлы и каналы, распечатав их.

    ```python theme={null}
    print(graph.nodes)
    ```

    Вы увидите что-то подобное:

    ```pycon theme={null}
    {'__start__': <langgraph.pregel.read.PregelNode at 0x7d05e3ba1810>,
     'write_essay': <langgraph.pregel.read.PregelNode at 0x7d05e3ba14d0>,
     'score_essay': <langgraph.pregel.read.PregelNode at 0x7d05e3ba1710>}
    ```

    ```python theme={null}
    print(graph.channels)
    ```

    Вы бы увидели что-то подобное.

    ```pycon theme={null}
    {'topic': <langgraph.channels.last_value.LastValue at 0x7d05e3294d80>,
     'content': <langgraph.channels.last_value.LastValue at 0x7d05e3295040>,
     'score': <langgraph.channels.last_value.LastValue at 0x7d05e3295980>,
     '__start__': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e3297e00>,
     'write_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e32960c0>,
     'score_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e2d8ab80>,
     'branch:__start__:__self__:write_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e32941c0>,
     'branch:__start__:__self__:score_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e2d88800>,
     'branch:write_essay:__self__:write_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e3295ec0>,
     'branch:write_essay:__self__:score_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e2d8ac00>,
     'branch:score_essay:__self__:write_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e2d89700>,
     'branch:score_essay:__self__:score_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e2d8b400>,
     'start:write_essay': <langgraph.channels.ephemeral_value.EphemeralValue at 0x7d05e2d8b280>}
    ```
  </Tab>

  <Tab title="Функциональный API">
    В [функциональном API](/oss/python/langgraph/functional-api) вы можете использовать [`@entrypoint`](https://reference.langchain.com/python/langgraph/func/#langgraph.func.entrypoint) для создания приложения Pregel. Декоратор `entrypoint` позволяет определить функцию, которая принимает входные данные и возвращает выходные.

    ```python theme={null}
    from typing import TypedDict

    from langgraph.checkpoint.memory import InMemorySaver
    from langgraph.func import entrypoint

    class Essay(TypedDict):
        тема: строка
        содержимое: str | Нет
        оценка: float | Нет


    checkpointer = InMemorySaver()

    @entrypoint(checkpointer=checkpointer)
    def write_essay(essay: Essay):
        возвращаться {
            "содержание": f"Эссе о {essay['topic']}",
        }

    print("Узлы: ")
    print(write_essay.nodes)
    print("Каналы: ")
    print(write_essay.channels)
    ```

    ```pycon theme={null}
    Узлы:
    {'write_essay': <langgraph.pregel.read.PregelNode object at 0x7d05e2f9aad0>}
    Каналы:
    {'__start__': <langgraph.channels.ephemeral_value.EphemeralValue object at 0x7d05e2c906c0>, '__end__': <langgraph.channels.last_value.LastValue object at 0x7d05e2c90c40>, '__previous__': <langgraph.channels.last_value.LastValue object at 0x7d05e1007280>}
    ```
  </Tab>
</Вкладки>

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langgraph/pregel.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Всплывающее сообщение>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>