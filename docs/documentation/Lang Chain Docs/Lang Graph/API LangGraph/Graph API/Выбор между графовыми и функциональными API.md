> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Выбор между графовым и функциональным API

LangGraph предоставляет два разных API для построения рабочих процессов агентов: **Graph API** и **Functional API**. Оба API используют одну и ту же базовую среду выполнения и могут использоваться вместе в одном приложении, но они разработаны для разных сценариев использования и предпочтений разработки.

Это руководство поможет вам понять, когда следует использовать каждый API в зависимости от ваших конкретных требований.

## Краткое руководство по принятию решений

Используйте **Graph API**, когда это необходимо:

* **Визуализация сложных рабочих процессов** для отладки и документирования.
* **Явное управление состоянием** с использованием общих данных на нескольких узлах
* **Условное ветвление** с несколькими точками принятия решения
* **Пути параллельного выполнения**, которые необходимо объединить позже
* **Командная работа**, где визуальное представление способствует пониманию

Используйте **функциональный API**, когда вам это необходимо:

* **Минимальные изменения кода** в существующем процедурном коде
* **Стандартный поток управления** (условные операторы if/else, циклы, вызовы функций)
* **Состояние, ограниченное областью действия функции**, без явного управления состоянием
* **Быстрое прототипирование** с меньшим количеством шаблонного кода
* **Линейные рабочие процессы** с простой логикой ветвления

## Подробное сравнение

### Когда использовать Graph API

API для работы с графами (Graph API) использует декларативный подход, при котором вы определяете узлы, ребра и общее состояние для создания визуальной структуры графа.

**1. Сложные деревья решений и разветвленная логика**

Когда в вашем рабочем процессе есть несколько точек принятия решений, зависящих от различных условий, Graph API делает эти ветви явными и легко визуализируемыми.

```python theme={null}
# Graph API: Наглядная визуализация путей принятия решений
from langgraph.graph import StateGraph
from typing import TypedDict

class AgentState(TypedDict):
    сообщения: список
    текущий_инструмент: str
    retry_count: int

def should_continue(state):
    если state["retry_count"] > 3:
        вернуть "конец"
    elif state["current_tool"] == "search":
        return "process_search"
    еще:
        return "call_llm"

рабочий процесс = StateGraph(AgentState)
workflow.add_node("call_llm", call_llm_node)
workflow.add_node("process_search", search_node)
workflow.add_conditional_edges("call_llm", should_continue)
```

**2. Управление состоянием в рамках нескольких компонентов**

Когда вам необходимо обмениваться и координировать состояние между различными частями вашего рабочего процесса, явное управление состоянием в Graph API оказывается очень полезным.

```python theme={null}
# Несколько узлов могут получать доступ к общему состоянию и изменять его.
class WorkflowState(TypedDict):
    user_input: str
    Результаты поиска: список
    generated_response: str
    validation_status: str

def search_node(state):
    # Доступ к общему состоянию
    результаты = поиск(state["user_input"])
    return {"search_results": results}

def validation_node(state):
    # Доступ к результатам из предыдущего узла
    is_valid = validate(state["generated_response"])
    return {"validation_status": "valid" if is_valid else "invalid"}
```

**3. Параллельная обработка с синхронизацией**

Когда вам необходимо выполнить несколько операций параллельно, а затем объединить их результаты, Graph API автоматически решает эту задачу.

```python theme={null}
# Параллельная обработка нескольких источников данных
workflow.add_node("fetch_news", fetch_news)
workflow.add_node("fetch_weather", fetch_weather)
workflow.add_node("fetch_stocks", fetch_stocks)
workflow.add_node("combine_data", combine_all_data)

# Все операции выборки выполняются параллельно
workflow.add_edge(START, "fetch_news")
workflow.add_edge(START, "fetch_weather")
workflow.add_edge(START, "fetch_stocks")

# Функция Combine ожидает завершения всех параллельных операций
workflow.add_edge("fetch_news", "combine_data")
workflow.add_edge("fetch_weather", "combine_data")
workflow.add_edge("fetch_stocks", "combine_data")
```

**4. Развитие команды и документирование**

Визуальный характер Graph API упрощает командам понимание, документирование и поддержку сложных рабочих процессов.

```python theme={null}
# Четкое разделение задач — каждый член команды может работать на разных узлах
workflow.add_node("data_ingestion", data_team_function)
workflow.add_node("ml_processing", ml_team_function)
workflow.add_node("business_logic", product_team_function)
workflow.add_node("output_formatting", frontend_team_function)
```

### Когда использовать функциональный API

Функциональный API (/oss/python/langgraph/functional-api) использует императивный подход, который интегрирует возможности LangGraph в стандартный процедурный код.

**1. Существующий процессуальный код**

Когда у вас есть существующий код, использующий стандартное управление потоком выполнения, и вы хотите добавить возможности LangGraph с минимальной рефакторизацией.

```python theme={null}
# Функциональный API: минимальные изменения в существующем коде
from langgraph.func import entrypoint, task

@задача
def process_user_input(user_input: str) -> dict:
    # Существующая функция с минимальными изменениями
    return {"processed": user_input.lower().strip()}

@entrypoint(checkpointer=checkpointer)
def workflow(user_input: str) -> str:
    # Стандартный поток управления Python
    обработано = process_user_input(user_input).result()

    if "urgent" in processed["processed"]:
        response = handle_urgent_request(processed).result()
    еще:
        response = handle_normal_request(processed).result()

    вернуть ответ
```

**2. Линейные рабочие процессы с простой логикой**

Когда ваш рабочий процесс преимущественно последовательный и использует простую условную логику.

```python theme={null}
@entrypoint(checkpointer=checkpointer)
def essay_workflow(topic: str) -> dict:
    # Линейный поток с простым ветвлением
    outline = create_outline(topic).result()

    если len(outline["points"]) < 3:
        outline = expand_outline(outline).result()

    draft = write_draft(outline).result()

    # Контрольная точка проверки человеком
    feedback = interrupt({"draft": draft, "action": "Пожалуйста, проверьте"})

    если feedback == "approve":
        финальное_эссе = черновик
    еще:
        final_essay = revise_essay(draft, feedback).result()

    return {"essay": final_essay}
```

**3. Быстрое прототипирование**

Когда вам нужно быстро проверить идеи, не тратя время на определение схем состояний и структур графов.

```python theme={null}
@entrypoint(checkpointer=checkpointer)
def quick_prototype(data: dict) -> dict:
    # Быстрая итерация — схема состояния не требуется
    step1_result = process_step1(data).result()
    step2_result = process_step2(step1_result).result()

    return {"final_result": step2_result}
```

**4. Управление состоянием в рамках отдельных функций**

Когда ваше состояние по своей природе ограничено отдельными функциями и не требует широкого распространения.

```python theme={null}
@задача
def analyze_document(document: str) -> dict:
    # Управление локальным состоянием внутри функции
    sections = extract_sections(document)
    summarize = [summarize(section) for section in sections]
    key_points = extract_key_points(summaries)

    возвращаться {
        "sections": len(sections),
        "резюме": резюме,
        "ключевые_точки": ключевые_точки
    }

@entrypoint(checkpointer=checkpointer)
def document_processor(document: str) -> dict:
    анализ = analyze_document(document).result()
    # Состояние передается между функциями по мере необходимости
    return generate_report(analysis).result()
```

## Объединение обоих API

Оба API можно использовать одновременно в одном приложении. Это полезно, когда разные части вашей системы имеют разные требования.

```python theme={null}
from langgraph.graph import StateGraph
from langgraph.func import entrypoint

# Сложная координация нескольких агентов с использованием Graph API
coordination_graph = StateGraph(CoordinationState)
coordination_graph.add_node("orchestrator", orchestrator_node)
coordination_graph.add_node("agent_a", agent_a_node)
coordination_graph.add_node("agent_b", agent_b_node)

# Простая обработка данных с использованием функционального API
@entrypoint()
def data_processor(raw_data: dict) -> dict:
    cleaned = clean_data(raw_data).result()
    transformed = transform_data(cleaned).result()
    возвращение трансформированным

# Используйте результат функционального API в графе
def orchestrator_node(state):
    processed_data = data_processor.invoke(state["raw_data"])
    return {"processed_data": processed_data}
```

## Миграция между API

### От функционального API к Graph API

Когда ваш функциональный рабочий процесс становится сложным, вы можете перейти на Graph API:

```python theme={null}
# До: Функциональный API
@entrypoint(checkpointer=checkpointer)
def complex_workflow(input_data: dict) -> dict:
    шаг1 = process_step1(input_data).result()

    если шаг 1["требуется_анализ"]:
        анализ = analyze_data(step1).result()
        если analysis["confidence"] > 0.8:
            результат = high_confidence_path(analysis).result()
        еще:
            результат = low_confidence_path(analysis).result()
    еще:
        результат = simple_path(step1).result()

    вернуть результат

# После: Graph API
class WorkflowState(TypedDict):
    input_data: dict
    step1_result: dict
    анализ: словарь
    final_result: dict

def should_analyze(state):
    return "analyze" if state["step1_result"]["needs_analysis"] else "simple_path"

def confidence_check(state):
    return "high_confidence" if state["analysis"]["confidence"] > 0.8 else "low_confidence"

рабочий процесс = StateGraph(WorkflowState)
workflow.add_node("step1", process_step1_node)
workflow.add_conditional_edges("step1", should_analyze)
workflow.add_node("analyze", analyze_data_node)
workflow.add_conditional_edges("analyze", confidence_check)
# ... добавить оставшиеся узлы и ребра
```

### От графа к функциональному API

Когда ваш график становится чрезмерно сложным для простых линейных процессов:

```python theme={null}
# Ранее: Излишне сложный Graph API
class SimpleState(TypedDict):
    ввод: строка
    шаг 1: стр.
    шаг 2: стр.
    результат: строка

# После: Упрощенный функциональный API
@entrypoint(checkpointer=checkpointer)
def simple_workflow(input_data: str) -> str:
    шаг1 = process_step1(input_data).result()
    шаг2 = process_step2(шаг1).result()
    return finalize_result(step2).result()
```

## Краткое содержание

Выбирайте **Graph API**, если вам необходим явный контроль над структурой рабочего процесса, сложным ветвлением, параллельной обработкой или преимуществами командной работы.

Выберите **функциональный API**, если вам нужно добавить возможности LangGraph в существующий код с минимальными изменениями, если у вас простые линейные рабочие процессы или вам необходимы возможности быстрого прототипирования.

Оба API предоставляют одни и те же основные функции LangGraph (сохранение данных, потоковая передача, участие человека, память), но упакованы в разные парадигмы, чтобы соответствовать различным стилям разработки и сценариям использования.

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langgraph/choosing-apis.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Всплывающее сообщение>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>