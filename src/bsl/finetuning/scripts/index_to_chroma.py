"""
Скрипт индексации BSL кода в ChromaDB для RAG
"""
import json
import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from pathlib import Path


def load_rag_chunks(json_file: str) -> list:
    """Загрузка чанков из JSON файла"""
    with open(json_file, 'r', encoding='utf-8') as f:
        return json.load(f)


def index_to_chroma(
    chunks: list,
    collection_name: str = "bsl_code",
    persist_directory: str = None,
    embedding_model: str = "all-MiniLM-L6-v2",
    batch_size: int = 100
):
    """Индексация чанков в ChromaDB"""

    print(f"Загрузка модели эмбеддингов: {embedding_model}")
    model = SentenceTransformer(embedding_model)

    print(f"Инициализация ChromaDB...")
    if persist_directory:
        client = chromadb.PersistentClient(path=persist_directory)
    else:
        client = chromadb.Client()

    # Удаляем коллекцию если существует (для переиндексации)
    try:
        client.delete_collection(collection_name)
        print(f"Удалена существующая коллекция: {collection_name}")
    except:
        pass

    collection = client.create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    print(f"Индексация {len(chunks)} чанков...")

    for i in tqdm(range(0, len(chunks), batch_size)):
        batch = chunks[i:i + batch_size]

        # Подготовка данных
        documents = [chunk['content'] for chunk in batch]
        metadatas = [chunk['metadata'] for chunk in batch]
        ids = [f"bsl_{i + j}" for j in range(len(batch))]

        # Генерация эмбеддингов
        embeddings = model.encode(documents).tolist()

        # Добавление в коллекцию
        collection.add(
            documents=documents,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids
        )

    print(f"\nИндексация завершена!")
    print(f"Коллекция: {collection_name}")
    print(f"Документов: {collection.count()}")

    return collection


def test_search(collection, model, query: str, n_results: int = 3):
    """Тестовый поиск"""
    print(f"\nТестовый запрос: '{query}'")

    query_embedding = model.encode(query).tolist()

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=n_results,
        include=['documents', 'metadatas', 'distances']
    )

    print(f"Найдено {len(results['documents'][0])} результатов:\n")

    for i, (doc, meta, dist) in enumerate(zip(
        results['documents'][0],
        results['metadatas'][0],
        results['distances'][0]
    )):
        print(f"--- Результат {i+1} (distance: {dist:.4f}) ---")
        print(f"Файл: {meta.get('file', 'N/A')}")
        print(f"Функция: {meta.get('name', 'N/A')} ({meta.get('type', 'N/A')})")
        print(f"Код (первые 200 символов):\n{doc[:200]}...")
        print()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Использование: python index_to_chroma.py <rag_json_file> [chroma_path]")
        print("Пример: python index_to_chroma.py D:\\1C-Enterprise_Framework\\data\\datasets\\bsl_rag.json D:\\1C-Enterprise_Framework\\data\\chroma_db")
        sys.exit(1)

    rag_file = sys.argv[1]
    chroma_path = sys.argv[2] if len(sys.argv) > 2 else "D:\\1C-Enterprise_Framework\\data\\chroma_db"

    # Загрузка данных
    print(f"Загрузка данных из {rag_file}")
    chunks = load_rag_chunks(rag_file)
    print(f"Загружено {len(chunks)} чанков")

    # Индексация
    model = SentenceTransformer('all-MiniLM-L6-v2')
    collection = index_to_chroma(chunks, persist_directory=chroma_path)

    # Тестовый поиск
    test_queries = [
        "проверка ИНН",
        "запрос к справочнику",
        "обработка исключений"
    ]

    for query in test_queries:
        test_search(collection, model, query)
