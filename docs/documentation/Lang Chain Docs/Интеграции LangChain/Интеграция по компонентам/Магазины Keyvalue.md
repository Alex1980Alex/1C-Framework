> ## Индекс документации
Полный индекс документации доступен по адресу: https://docs.langchain.com/llms.txt
Используйте этот файл, чтобы просмотреть все доступные страницы, прежде чем продолжить изучение.

# Хранилища типа «ключ-значение»

## Обзор

LangChain предоставляет интерфейс хранилища типа «ключ-значение» для хранения и извлечения данных по ключу. Интерфейс хранилища типа «ключ-значение» в LangChain в основном используется для кэширования [встраиваний](/oss/python/integrations/text_embedding).

## Интерфейс

Все [`BaseStores`](https://python.langchain.com/api_reference/core/stores/langchain_core.stores.BaseStore.html) поддерживают следующий интерфейс:

* `mget(key: Sequence[str]) -> List[Optional[bytes]]`: получает содержимое нескольких ключей, возвращая `None`, если ключ не существует.
* `mset(key_value_pairs: Sequence[Tuple[str, bytes]]) -> None`: установить содержимое нескольких ключей
* `mdelete(key: Sequence[str]) -> None`: удаление нескольких ключей
* `yield_keys(prefix: Optional[str] = None) -> Iterator[str]`: возвращает все ключи в хранилище, при необходимости фильтруя по префиксу.

<Примечание>
  Базовые хранилища данных предназначены для одновременной обработки **нескольких** пар ключ-значение для повышения эффективности. Это позволяет сократить количество сетевых запросов и может обеспечить более эффективную пакетную обработку в базовом хранилище.
</Примечание>

## Встроенные магазины для развития местного производства

<Columns cols={2}>
  <Card title="InMemoryByteStore" icon="link" href="/oss/python/integrations/stores/in_memory" arrow="true" cta="View guide" />

  <Card title="LocalFileStore" icon="link" href="/oss/python/integrations/stores/file_system" arrow="true" cta="View guide" />
</Столбцы>

## Магазины на заказ

Вы также можете реализовать собственное хранилище, расширив класс [`BaseStore`](https://reference.langchain.com/python/langgraph/store/#langgraph.store.base.BaseStore). Более подробную информацию см. в [документации по интерфейсу хранилища](https://python.langchain.com/api_reference/core/stores/langchain_core.stores.BaseStore.html).

## Все хранилища типа «ключ-значение»

<Columns cols={3}>
  <Card title="AstraDBByteStore" icon="link" href="/oss/python/integrations/stores/astradb" arrow="true" cta="View guide" />

  <Card title="CassandraByteStore" icon="link" href="/oss/python/integrations/stores/cassandra" arrow="true" cta="View guide" />

  <Card title="ElasticsearchEmbeddingsCache" icon="link" href="/oss/python/integrations/stores/elasticsearch" arrow="true" cta="View guide" />

  <Card title="RedisStore" icon="link" href="/oss/python/integrations/stores/redis" arrow="true" cta="View guide" />

  <Card title="UpstashRedisByteStore" icon="link" href="/oss/python/integrations/stores/upstash_redis" arrow="true" cta="View guide" />

  <Card title="BigtableByteStore" icon="link" href="/oss/python/integrations/stores/bigtable" arrow="true" cta="View guide" />
</Столбцы>

***

<Callout icon="pen-to-square" iconType="regular">
  [Отредактируйте эту страницу на GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/stores/index.mdx) или [сообщите о проблеме](https://github.com/langchain-ai/docs/issues/new/choose).
</Всплывающее сообщение>

<Tip icon="terminal" iconType="regular">
  [Подключите эти документы](/use-these-docs) к Claude, VSCode и другим сервисам через MCP для получения ответов в режиме реального времени.
</Совет>