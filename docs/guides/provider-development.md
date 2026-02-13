# Руководство: Добавление нового провайдера

Фреймворк использует **Provider Pattern** — все ключевые компоненты определяют абстрактный интерфейс (ABC), а конкретные реализации подключаются через фабричные функции.

## Структура провайдера

```
src/pdf_framework/<module>/
├── __init__.py          # Фабричная функция get_*()
├── base.py              # Абстрактный базовый класс
└── providers/
    ├── __init__.py
    └── my_provider.py   # Ваша реализация
```

## Пример: добавление Qdrant Vector Store

### Шаг 1. Создайте файл провайдера

`src/pdf_framework/vector_store/providers/qdrant_store.py`:

```python
from typing import Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

from src.pdf_framework.config import VectorStoreSettings
from src.pdf_framework.schemas.documents import DocumentChunk, SearchResult
from src.pdf_framework.vector_store.base import BaseVectorStore


class QdrantVectorStore(BaseVectorStore):
    """Qdrant-backed vector store."""

    def __init__(self, settings: VectorStoreSettings | None = None):
        self._settings = settings or VectorStoreSettings()
        self._client: QdrantClient | None = None

    async def initialize(self) -> None:
        self._client = QdrantClient(path=str(self._settings.persist_dir))
        # Создать коллекцию если не существует
        ...

    async def add_documents(
        self,
        chunks: list[DocumentChunk],
        embeddings: list[list[float]],
    ) -> list[str]:
        # Реализация через self._client.upsert()
        ...

    async def search(
        self,
        query_embedding: list[float],
        k: int = 5,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        # Реализация через self._client.search()
        ...

    # ... остальные абстрактные методы
```

### Шаг 2. Обновите фабричную функцию

`src/pdf_framework/vector_store/__init__.py`:

```python
def get_vector_store(settings: VectorStoreSettings | None = None) -> BaseVectorStore:
    settings = settings or VectorStoreSettings()
    if settings.provider == "chroma":
        from src.pdf_framework.vector_store.providers.chroma import ChromaVectorStore
        return ChromaVectorStore(settings)
    if settings.provider == "qdrant":                                    # <-- NEW
        from src.pdf_framework.vector_store.providers.qdrant_store import QdrantVectorStore
        return QdrantVectorStore(settings)
    raise ValueError(f"Unsupported vector store provider: {settings.provider}")
```

### Шаг 3. Обновите конфигурацию

`src/pdf_framework/config.py` — добавьте `"qdrant"` в Literal:

```python
class VectorStoreSettings(BaseSettings):
    provider: Literal["chroma", "qdrant", "faiss"] = "chroma"  # уже есть
```

### Шаг 4. Активируйте через .env

```ini
VECTOR_STORE__PROVIDER=qdrant
```

---

## Доступные базовые классы

### BaseLoader (`loaders/base.py`)

```python
class BaseLoader(ABC):
    async def load(self, source: str | Path) -> ProcessedDocument
    async def load_batch(self, sources: list[str | Path]) -> list[ProcessedDocument]
    def supported_extensions(self) -> list[str]
```

### BaseEmbeddingEngine (`embeddings/engine.py`)

```python
class BaseEmbeddingEngine(ABC):
    async def embed_text(self, text: str) -> list[float]
    async def embed_batch(self, texts: list[str]) -> list[list[float]]
    def get_dimensions(self) -> int
    def get_model_name(self) -> str
```

### BaseVectorStore (`vector_store/base.py`)

```python
class BaseVectorStore(ABC):
    async def initialize(self) -> None
    async def add_documents(self, chunks, embeddings) -> list[str]
    async def search(self, query_embedding, k, filter) -> list[SearchResult]
    async def search_mmr(self, query_embedding, k, fetch_k, lambda_mult, filter) -> list[SearchResult]
    async def delete(self, ids: list[str]) -> None
    async def get_by_ids(self, ids: list[str]) -> list[DocumentChunk]
    async def count(self) -> int
    async def clear(self) -> None
```

### BaseGraphStore (`graph_store/base.py`)

```python
class BaseGraphStore(ABC):
    async def initialize(self) -> None
    async def add_entity(self, entity: Entity) -> str
    async def add_relation(self, relation: Relation) -> str
    async def get_entity(self, entity_id: str) -> Entity | None
    async def find_entities(self, name, entity_type, limit) -> list[Entity]
    async def get_neighbors(self, entity_id, relation_type, depth) -> SubGraph
    async def find_path(self, source_id, target_id, max_depth) -> SubGraph
    async def query(self, query_str, params) -> SubGraph
    async def get_statistics(self) -> dict[str, Any]
    async def delete_entity(self, entity_id: str) -> None
    async def clear(self) -> None
```

## Правила

1. **Все I/O — async.** Если библиотека синхронная, оберните в `asyncio.to_thread()`.
2. **Принимайте Settings в конструкторе.** Не читайте конфигурацию напрямую.
3. **Ленивая инициализация.** Тяжёлые подключения — в `initialize()`, не в `__init__()`.
4. **Возвращайте стандартные модели.** Используйте `DocumentChunk`, `SearchResult`, `Entity` из `schemas/`.
5. **Фабрика — ленивый импорт.** Импортируйте провайдер внутри `if`, чтобы не требовать установку всех зависимостей.
