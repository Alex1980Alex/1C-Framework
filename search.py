"""
Простой скрипт для поиска по проиндексированным PDF
Использование: python search.py "ваш запрос"
"""
import asyncio
import sys
from src.api.dependencies.components import Components


async def search(query: str, strategy: str = "vector", k: int = 3):
    """Поиск по документам"""
    components = Components()
    await components.initialize()

    response = await components.search_manager.search(
        query=query,
        strategy=strategy,
        k=k
    )

    return response


def format_results(response, query):
    """Форматировать результаты для вывода"""
    output = []
    output.append(f"\nПоиск: '{query}'")
    output.append(f"Найдено: {response.total_found} результатов за {response.elapsed_ms:.0f}мс")
    output.append("=" * 70)

    for i, result in enumerate(response.results, 1):
        output.append(f"\n[{i}] Релевантность: {result.score:.3f}")
        output.append(f"Документ: {result.chunk.document_id}, chunk #{result.chunk.chunk_index}")
        output.append("-" * 70)
        # Показываем контент
        content = result.chunk.content.strip()
        output.append(content)
        output.append("-" * 70)

    return "\n".join(output)


async def main():
    if len(sys.argv) < 2:
        print("Использование: python search.py 'ваш запрос' [strategy] [k]")
        print("Примеры:")
        print("  python search.py 'что такое 1С'")
        print("  python search.py 'конфигурация' vector 5")
        sys.exit(1)

    query = sys.argv[1]
    strategy = sys.argv[2] if len(sys.argv) > 2 else "vector"
    k = int(sys.argv[3]) if len(sys.argv) > 3 else 3

    response = await search(query, strategy, k)
    result_text = format_results(response, query)

    print(result_text)


if __name__ == "__main__":
    asyncio.run(main())
