"""Doc-to-Cache: сканирование документации и подготовка к кешированию.

Вспомогательный скрипт для скилла doc-to-cache.
Сканирует файлы, группирует по темам, генерирует заготовки topic-файлов.

Usage:
    python scripts/doc_to_cache.py <path>           # Сканировать файл или папку
    python scripts/doc_to_cache.py <path> --dry-run  # Только показать план
    python scripts/doc_to_cache.py <path> --scaffold  # Создать заготовки
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".claude" / "skills" / "tech-research" / "cache"
INDEX_PATH = CACHE_DIR / "_index.json"
TEMPLATE_PATH = CACHE_DIR / "_topic_template.md"

# Domain detection rules: (pattern in path or content) -> domain
DOMAIN_RULES = [
    (r"claude.code|hooks?|skills?", "tools"),
    (r"langchain|chains?|prompt", "python"),
    (r"langgraph|agents?|state.machine", "agents"),
    (r"mcp|model.context.protocol", "tools"),
    (r"lsp|language.server", "tools"),
    (r"qdrant|vector.db|faiss|chroma", "vector-db"),
    (r"embed|sentence.transform|e5|bge", "embeddings"),
    (r"rag|retriev|search|rerank|bm25", "rag"),
    (r"llm|claude.api|anthropic|gpt", "llm"),
    (r"python|pip|poetry|pytest", "python"),
    (r"ml|machine.learn|neural|torch", "ml"),
]

# Category detection
CATEGORY_RULES = [
    (r"protocol|spec|api.ref", "api"),
    (r"library|framework|sdk|package", "library"),
    (r"pattern|practice|approach", "pattern"),
    (r"algorithm|method|technique", "algorithm"),
    (r"concept|overview|intro", "concept"),
    (r"tool|util|cli|command", "tool"),
]


def normalize_topic_name(name: str) -> str:
    """Normalize a topic name: lowercase, dashes, no special chars."""
    # Remove file extension
    name = re.sub(r"\.(md|txt|rst)$", "", name, flags=re.IGNORECASE)
    # Remove parenthetical content
    name = re.sub(r"\([^)]*\)", "", name)
    # Replace special chars with dashes
    name = re.sub(r"[^a-zA-Zа-яА-ЯёЁ0-9]+", "-", name)
    # Transliterate common Russian folder names
    translit = {
        "протокол-контекста-модели": "mcp-protocol",
        "документация": "docs",
        "начало-работы": "getting-started",
        "создавайте-с": "building-with",
        "конфигурация": "configuration",
        "администрирование": "administration",
        "справка": "reference",
        "основные-компоненты": "core-components",
        "стриминг": "streaming",
        "разработка-агентов": "agent-development",
        "расширенное-использование": "advanced-usage",
        "многоагентный": "multi-agent",
        "возможности": "features",
        "производство": "production",
        "интеграции": "integrations",
        "учиться": "learn",
        "концептуальные-обзоры": "concepts",
        "коммунальные-услуги": "utilities",
        "функции-клиента": "client-features",
        "функции-сервера": "server-features",
        "спецификация": "specification",
        "промежуточное-программное-обеспечение": "middleware",
        "развертывание-с-помощью": "deployment-with",
    }
    result = name.lower().strip("-")
    for ru, en in translit.items():
        result = result.replace(ru, en)
    # Collapse multiple dashes
    result = re.sub(r"-+", "-", result).strip("-")
    return result


def detect_domain(path: str, content: str = "") -> str:
    """Detect knowledge domain from path and content."""
    text = (path + " " + content[:2000]).lower()
    for pattern, domain in DOMAIN_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return domain
    return "python"  # default


def detect_category(path: str, content: str = "") -> str:
    """Detect knowledge category from path and content."""
    text = (path + " " + content[:2000]).lower()
    for pattern, category in CATEGORY_RULES:
        if re.search(pattern, text, re.IGNORECASE):
            return category
    return "library"  # default


def scan_path(target: Path) -> dict[str, list[Path]]:
    """
    Scan a file or directory, return grouped files by topic.

    Returns:
        dict: topic_name -> list of files
    """
    groups: dict[str, list[Path]] = {}

    if target.is_file():
        # Single file = single topic
        topic = normalize_topic_name(target.stem)
        groups[topic] = [target]
    elif target.is_dir():
        # Check if this dir has subdirectories
        subdirs = [d for d in target.iterdir() if d.is_dir()]
        files_here = [f for f in target.iterdir() if f.is_file() and f.suffix in (".md", ".txt")]

        if subdirs:
            # Group by subdirectory
            for subdir in sorted(subdirs):
                topic = normalize_topic_name(subdir.name)
                md_files = sorted(subdir.rglob("*.md")) + sorted(subdir.rglob("*.txt"))
                if md_files:
                    groups[topic] = md_files

        if files_here:
            # Files at this level = topic from dir name
            topic = normalize_topic_name(target.name)
            if topic in groups:
                groups[topic].extend(files_here)
            else:
                groups[topic] = files_here
    else:
        print(f"Error: {target} is not a file or directory")
        sys.exit(1)

    return groups


def load_index() -> dict:
    """Load the current cache index."""
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    return {"domains": [], "last_updated": "", "topics": {}}


def extract_keywords(content: str, max_keywords: int = 10) -> list[str]:
    """Extract likely keywords from content."""
    # Find capitalized terms, code terms, etc.
    words = re.findall(r"\b[A-Z][a-zA-Z]{2,}\b", content)
    # Find backtick-enclosed terms
    code_terms = re.findall(r"`([^`]+)`", content)
    # Combine and deduplicate
    all_terms = []
    seen = set()
    for term in words + code_terms:
        normalized = term.lower().strip()
        if normalized not in seen and len(normalized) > 2:
            seen.add(normalized)
            all_terms.append(normalized)
    return all_terms[:max_keywords]


def generate_scaffold(topic: str, files: list[Path], domain: str, category: str) -> str:
    """Generate a scaffold topic file from the template."""
    today = date.today().isoformat()
    source_urls = [str(f.relative_to(PROJECT_ROOT)) for f in files]

    # Read first file for keywords
    content = ""
    for f in files[:3]:
        try:
            content += f.read_text(encoding="utf-8")[:5000]
        except Exception:
            pass

    keywords = extract_keywords(content)

    scaffold = f"""---
topic: "{topic}"
domain: "{domain}"
category: "{category}"
created: "{today}"
last_verified: "{today}"
version: ""
source_urls: {json.dumps(source_urls, ensure_ascii=False)}
keywords: {json.dumps(keywords, ensure_ascii=False)}
---

# {topic}

## 1. Идентификация

> Заполни из исходных файлов: {', '.join(f.name for f in files[:5])}

**Что это:** [TODO: извлечь из документации]
**Для чего:** [TODO]
**Когда использовать:** [TODO]
**Альтернативы:** [TODO]
**Домен:** {domain}

---

## 2. Установка и настройка

> Извлечь команды установки и конфигурацию

**Установка:**
```bash
# TODO
```

**Зависимости:** [TODO]
**Конфигурация:**
```python
# TODO
```

---

## 3. Core API

> Основные классы, методы, параметры

### Ключевые классы/функции

| Класс/Функция | Назначение | Ключевые параметры |
|---------------|-----------|-------------------|
| TODO | | |

---

## 4. Паттерны использования

> Готовые сценарии из документации

### Сценарий 1: [TODO]

```python
# TODO
```

---

## 5. Архитектура

> Как работает внутри, ограничения

**Как работает:** [TODO]
**Ключевые абстракции:** [TODO]
**Ограничения:** [TODO]

---

## 6. Диагностика

> Частые ошибки, антипаттерны

### Частые ошибки

| Проблема | Причина | Решение |
|----------|---------|---------|
| TODO | | |

---

## 7. Источники

> Полная атрибуция

"""
    for url in source_urls:
        scaffold += f"- **[Документация]** `{url}`\n"

    return scaffold


def print_plan(groups: dict[str, list[Path]], index: dict) -> None:
    """Print the processing plan."""
    total_files = sum(len(files) for files in groups.values())
    existing = set(index.get("topics", {}).keys())

    print(f"\n{'='*60}")
    print(f"Doc-to-Cache: План обработки")
    print(f"{'='*60}")
    print(f"Тем: {len(groups)}, Файлов: {total_files}")
    print(f"Существующих тем в кеше: {len(existing)}")
    print()

    for topic, files in sorted(groups.items()):
        status = "[UPDATE]" if topic in existing else "[NEW]"
        content = ""
        for f in files[:1]:
            try:
                content = f.read_text(encoding="utf-8")[:2000]
            except Exception:
                pass
        domain = detect_domain(str(files[0]), content)
        category = detect_category(str(files[0]), content)

        print(f"  {status} {topic} ({domain}/{category})")
        print(f"         {len(files)} файл(ов):")
        for f in files[:5]:
            print(f"           - {f.relative_to(PROJECT_ROOT)}")
        if len(files) > 5:
            print(f"           ... и ещё {len(files) - 5}")
        print()

    print(f"{'='*60}")
    print(f"Выходной каталог: {CACHE_DIR.relative_to(PROJECT_ROOT)}")
    print(f"{'='*60}\n")


def create_scaffolds(groups: dict[str, list[Path]], index: dict) -> None:
    """Create scaffold files and update index."""
    today = date.today().isoformat()
    topics_data = index.get("topics", {})
    created_count = 0

    for topic, files in sorted(groups.items()):
        content = ""
        for f in files[:1]:
            try:
                content = f.read_text(encoding="utf-8")[:2000]
            except Exception:
                pass

        domain = detect_domain(str(files[0]), content)
        category = detect_category(str(files[0]), content)

        output_path = CACHE_DIR / f"{topic}.md"

        if output_path.exists():
            print(f"  [SKIP] {topic}.md уже существует (используй Claude для merge)")
            continue

        scaffold = generate_scaffold(topic, files, domain, category)
        output_path.write_text(scaffold, encoding="utf-8")

        # Update index
        keywords = extract_keywords(content)
        topics_data[topic] = {
            "file": f"{topic}.md",
            "domain": domain,
            "category": category,
            "created": today,
            "keywords": keywords,
            "summary": f"[SCAFFOLD] {len(files)} файлов из docs/documentation. Требует заполнения через Claude."
        }

        created_count += 1
        print(f"  [OK] {topic}.md ({domain}/{category}, {len(files)} файлов)")

    # Save index
    index["topics"] = topics_data
    index["last_updated"] = today
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"\nСоздано заготовок: {created_count}")
    print(f"Индекс обновлён: {INDEX_PATH.relative_to(PROJECT_ROOT)}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/doc_to_cache.py <path> [--dry-run|--scaffold]")
        print()
        print("  <path>      Путь к файлу или папке с документацией")
        print("  --dry-run   Только показать план (без создания файлов)")
        print("  --scaffold  Создать заготовки topic-файлов (шаблоны для заполнения)")
        print()
        print("Примеры:")
        print("  python scripts/doc_to_cache.py docs/documentation/")
        print("  python scripts/doc_to_cache.py docs/documentation/Claude\\ Code\\ Docs --scaffold")
        print("  python scripts/doc_to_cache.py docs/documentation/file.md --dry-run")
        sys.exit(1)

    target = Path(sys.argv[1])
    if not target.is_absolute():
        target = PROJECT_ROOT / target

    dry_run = "--dry-run" in sys.argv
    scaffold = "--scaffold" in sys.argv

    if not target.exists():
        print(f"Error: Path not found: {target}")
        sys.exit(1)

    # Scan
    groups = scan_path(target)
    if not groups:
        print("No .md/.txt files found")
        sys.exit(1)

    # Load index
    index = load_index()

    # Print plan
    print_plan(groups, index)

    if dry_run:
        print("(--dry-run: файлы не создаются)")
        return

    if scaffold:
        create_scaffolds(groups, index)
        return

    # Default: just show plan and suggest next steps
    print("Следующие шаги:")
    print("  1. --scaffold  создать заготовки topic-файлов")
    print("  2. /doc-to-cache <path>  заполнить через Claude (полная конвертация)")
    print()


if __name__ == "__main__":
    main()
