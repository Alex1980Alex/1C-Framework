> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Установка LangChain

Для установки пакета LangChain:

<CodeGroup>
  ```bash pip theme={null}
  pip install -U langchain
  # Требуется Python 3.10+
  ```

  ```bash uv theme={null}
  uv add langchain
  # Требуется Python 3.10+
  ```
</CodeGroup>

LangChain предоставляет интеграции с сотнями программ магистратуры в области права и тысячами других интеграций. Все они работают в рамках независимых пакетов от разных поставщиков.

<CodeGroup>
  ```bash pip theme={null}
  # Установка интеграции OpenAI
  pip install -U langchain-openai

  # Установка интеграции с Anthropic
  pip install -U langchain-anthropic
  ```

  ```bash uv theme={null}
  # Установка интеграции OpenAI
  uv add langchain-openai

  # Установка интеграции с Anthropic
  uv add langchain-anthropic
  ```
</CodeGroup>

<Совет>
  Полный список доступных интеграций см. на вкладке [Интеграции](/oss/python/integrations/providers/overview).
</Совет>

Теперь, когда у вас установлен LangChain, вы можете начать работу, следуя [руководству по быстрому запуску](/oss/python/langchain/quickstart).

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/langchain/install.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Всплывающее сообщение>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>