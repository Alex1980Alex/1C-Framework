#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Language Smart Indexer - индексация файлов разных языков
Поддержка: BSL, JavaScript, TypeScript, Python, Markdown

Использование:
    python smart_index_bsl.py                           # Список проектов
    python smart_index_bsl.py --list                   # Список проектов
    python smart_index_bsl.py --project 251229_GKS     # Индексировать проект по имени
    python smart_index_bsl.py --path "полный/путь"     # Индексировать по пути
    python smart_index_bsl.py --languages bsl,js,py    # Указать языки для индексации
"""

import sys
import time
import argparse
import traceback
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))


# ============================================================================
# KONFIGURATSIIYA MULTI-LANGUAGE INDEKSATSII
# ============================================================================

SUPPORTED_EXTENSIONS: Dict[str, Dict[str, str]] = {
    ".bsl": {"type": "bsl", "doc_type": "bsl", "name": "BSL", "method": "index_bsl_file"},
    ".js": {"type": "javascript", "doc_type": "javascript", "name": "JavaScript", "method": "index_javascript_file"},
    ".ts": {"type": "typescript", "doc_type": "typescript", "name": "TypeScript", "method": "index_javascript_file"},
    ".py": {"type": "python", "doc_type": "python", "name": "Python", "method": "index_document"},
    ".md": {"type": "markdown", "doc_type": "markdown", "name": "Markdown", "method": "index_document"},
}

# Маппинг имени языка к расширению файла
LANGUAGE_TO_EXTENSION: Dict[str, str] = {
    "bsl": ".bsl",
    "javascript": ".js",
    "typescript": ".ts",
    "python": ".py",
    "markdown": ".md",
}

# Глобальные паттерны пропуска (для всех языков)
GLOBAL_SKIP_PATTERNS: List[str] = [
    "src\\projects\\configuration",
    "src/projects/configuration",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    "dist",
    "build",
]

SKIP_PATTERNS_BY_TYPE: Dict[str, List[str]] = {
    "bsl": [
        "CommonModules/БСП",
        "CommonModules/СтандартныеПодсистемы",
        "CommonModules/ОбменДанными",
        "__",
        "test",
        "Test",
        "тест",
        "Тест",
    ],
    "javascript": [
        "node_modules",
        "dist",
        "build",
        ".min.js",
        "vendor",
        "coverage",
    ],
    "typescript": [
        "node_modules",
        "dist",
        "build",
        ".d.ts",
        "vendor",
    ],
    "python": [
        "__pycache__",
        ".venv",
        "venv",
        "site-packages",
        "test",
        "tests",
    ],
    "markdown": [],
}

DEFAULT_LANGUAGES: List[str] = ["bsl", "javascript", "python", "markdown"]


def find_all_projects():
    """Находит все проекты в папке configuration"""
    base_path = Path(r"D:\1С-Framework\src\projects\configuration")
    if not base_path.exists():
        return []

    projects = []
    for item in base_path.iterdir():
        if item.is_dir() and (item / "src").exists():
            projects.append(item.name)

    return sorted(projects)


from hybrid_search_engine import HybridSearchEngine


# ============================================================================
# MULTI-LANGUAGE FILE DISCOVERY
# ============================================================================

def get_all_source_files(
    project_root: Path,
    languages: List[str] = None,
    skip_patterns: Dict[str, List[str]] = None,
    filter_global: bool = True
) -> List[Dict[str, Any]]:
    """
    Получить все исходные файлы поддерживаемых типов

    Args:
        project_root: Корневая папка проекта
        languages: Список языков для индексации (bsl, javascript, python, markdown)
        skip_patterns: Паттерны для пропуска по типам файлов
        filter_global: Фильтровать по глобальным паттернам (src/projects/configuration и т.д.)

    Returns:
        Список словарей: [{"path": Path, "type": str, "doc_type": str, "lang_name": str}]
    """
    if languages is None:
        languages = DEFAULT_LANGUAGES

    if skip_patterns is None:
        skip_patterns = SKIP_PATTERNS_BY_TYPE

    all_files = []

    for lang in languages:
        # Находим расширения для языка
        extensions = [
            ext for ext, config in SUPPORTED_EXTENSIONS.items()
            if config["type"] == lang
        ]

        for ext in extensions:
            print(f"  [SCAN] Поиск *{ext} файлов...", end=" ", flush=True)
            files = list(project_root.rglob(f"*{ext}"))
            config = SUPPORTED_EXTENSIONS[ext]
            found_count = 0

            for f in files:
                # Фильтруем по глобальным паттернам при сборе (быстрее)
                if filter_global:
                    path_str = str(f)
                    skip = False
                    for pattern in GLOBAL_SKIP_PATTERNS:
                        if pattern in path_str:
                            skip = True
                            break
                    if skip:
                        continue

                file_info = {
                    "path": f,
                    "type": config["type"],
                    "doc_type": config["doc_type"],
                    "lang_name": config["name"],
                    "method": config["method"],
                    "extension": ext
                }
                all_files.append(file_info)
                found_count += 1

            print(f"найдено {found_count} (всего {len(files)}, пропущено {len(files) - found_count})")

    return all_files


def should_skip_file(file_path: Path, file_type: str, skip_patterns: Dict[str, List[str]], check_global: bool = True) -> bool:
    """
    Проверить, нужно ли пропустить файл

    Args:
        file_path: Путь к файлу
        file_type: Тип файла (bsl, javascript, etc.)
        skip_patterns: Паттерны для пропуска
        check_global: Проверять глобальные паттерны (src/projects/configuration и т.д.)

    Returns:
        True если файл нужно пропустить
    """
    path_str = str(file_path)

    # Проверяем глобальные паттерны (например, src/projects/configuration)
    if check_global:
        for pattern in GLOBAL_SKIP_PATTERNS:
            if pattern in path_str:
                return True

    # Проверяем паттерны по типу файла
    patterns = skip_patterns.get(file_type, [])
    for pattern in patterns:
        if pattern in path_str:
            return True

    return False


def smart_index_multi_language(
    project_path: str,
    languages: List[str] = None,
    chunk_mode: str = "smart",
    delay_seconds: float = 0.5,
    full_index: bool = False,
    force: bool = False
):
    """
    Индексирует файлы проекта разных языков

    Args:
        project_path: Путь к проекту (папка с src/)
        languages: Список языков для индексации (bsl, javascript, python, markdown)
        chunk_mode: Режим разбиения
        delay_seconds: Задержка между файлами
        full_index: Если True - индексировать ВСЕ файлы, иначе только важные
        force: Если True - принудительная переиндексация (игнорирует hash)
    """
    if languages is None:
        languages = DEFAULT_LANGUAGES

    engine = HybridSearchEngine()
    project_root = Path(project_path)

    if not project_root.exists():
        print(f"[ERROR] Проект не найден: {project_path}")
        return

    # Формируем список языков для логирования
    lang_names = ", ".join([
        SUPPORTED_EXTENSIONS[LANGUAGE_TO_EXTENSION[l]]["name"]
        for l in languages if l in LANGUAGE_TO_EXTENSION
    ])

    if full_index:
        print(f"[INFO] ПОЛНАЯ индексация: все файлы ({lang_names})")
    else:
        print(f"[INFO] Оптимизированная индексация: только важные модули ({lang_names})")
        print(f"[SKIP] Пропускаем: БСП, node_modules, тесты и т.д.")

    if force:
        print(f"[FORCE] Принудительная переиндексация (игнорируем hash)")

    # Определяем, индексируем ли мы проект из configuration
    # Если да - отключаем глобальный фильтр (иначе все файлы пропускаются)
    is_configuration_project = "projects" in str(project_root) and "configuration" in str(project_root)
    filter_global = not is_configuration_project

    if is_configuration_project:
        print(f"[INFO] Индексация проекта из configuration - глобальный фильтр ОТКЛЮЧЕН")

    # Находим все файлы
    print(f"[SCAN] Сканирование файлов в {project_root}...", flush=True)
    all_files = get_all_source_files(project_root, languages, filter_global=filter_global)
    total_files = len(all_files)
    print(f"[SCAN] Найдено {total_files} файлов для обработки")

    # Статистика по языкам
    stats_by_lang = {lang: {"files": 0, "documents": 0, "errors": 0, "skipped": 0} for lang in languages}
    total_stats = {"files": 0, "documents": 0, "errors": 0, "skipped": 0}
    error_types: Dict[str, int] = {}  # Сводка по типам ошибок

    print(f"[INFO] Найдено файлов: {total_files}")

    # Вывод статистики по языкам
    for file_info in all_files:
        lang = file_info["type"]
        stats_by_lang[lang]["files"] = stats_by_lang.get(lang, {}).get("files", 0) + 1

    for lang, lang_stat in stats_by_lang.items():
        if lang_stat["files"] > 0:
            ext_names = [k for k, v in SUPPORTED_EXTENSIONS.items() if v["type"] == lang]
            print(f"  - {SUPPORTED_EXTENSIONS[ext_names[0]]['name']}: {lang_stat['files']} файлов")

    print()

    # Индексируем файлы
    for i, file_info in enumerate(all_files, 1):
        file_path = file_info["path"]
        file_type = file_info["type"]
        lang_name = file_info["lang_name"]
        method_name = file_info["method"]

        # В режиме smart - пропускаем по паттернам
        if not full_index:
            if should_skip_file(file_path, file_type, SKIP_PATTERNS_BY_TYPE):
                stats_by_lang[file_type]["skipped"] += 1
                total_stats["skipped"] += 1
                continue

        try:
            # Вызываем соответствующий метод индексации
            index_method = getattr(engine, method_name)

            if method_name == "index_bsl_file":
                docs = index_method(str(file_path), chunk_mode=chunk_mode, force=force)
            elif method_name == "index_javascript_file":
                docs = index_method(str(file_path), chunk_mode=chunk_mode, force=force)
            else:  # index_document (markdown, python)
                doc_type = file_info.get("doc_type", "markdown")
                docs = index_method(str(file_path), doc_type=doc_type, force=force)

            stats_by_lang[file_type]["files"] += 1
            stats_by_lang[file_type]["documents"] += docs
            total_stats["files"] += 1
            total_stats["documents"] += docs

            # Прогресс каждые 50 файлов или каждые 10%
            if total_stats["files"] % 50 == 0 or (i * 100 // total_files) % 10 == 0:
                pct = i * 100 // total_files
                print(f"[{pct:3d}%] {total_stats['files']} файлов, {total_stats['documents']} док. обработано")

            # Небольшая задержка чтобы не перегрузить систему
            time.sleep(delay_seconds)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else "No message"
            print(f"[ERROR] {lang_name} {file_path.name}")
            print(f"        Type: {error_type}")
            print(f"        Message: {error_msg[:200]}...")  # Ограничиваем длину
            print(f"        Path: {file_path}")
            # Выводим краткий traceback (последние 3 строки)
            tb_lines = traceback.format_exc().strip().split('\n')
            if len(tb_lines) > 3:
                for line in tb_lines[-3:]:
                    print(f"        {line}")
            stats_by_lang[file_type]["errors"] += 1
            total_stats["errors"] += 1
            # Собираем статистику по типам ошибок
            error_types[error_type] = error_types.get(error_type, 0) + 1

    # Финальная статистика
    mode_str = "Полная" if full_index else "Оптимизированная"
    print(f"\n[DONE] {mode_str} индексация завершена")
    print(f"  Всего файлов проиндексировано: {total_stats['files']}")
    print(f"  Всего документов создано: {total_stats['documents']}")
    if not full_index:
        print(f"  Всего пропущено: {total_stats['skipped']}")
    print(f"  Всего ошибок: {total_stats['errors']}")

    print("\nСтатистика по языкам:")
    for lang in languages:
        lang_stat = stats_by_lang.get(lang, {"files": 0, "documents": 0, "errors": 0, "skipped": 0})
        if lang_stat["files"] > 0 or lang_stat["skipped"] > 0:
            ext_names = [k for k, v in SUPPORTED_EXTENSIONS.items() if v["type"] == lang]
            lang_display = SUPPORTED_EXTENSIONS[ext_names[0]]["name"]
            print(f"  {lang_display}: {lang_stat['files']} файлов, {lang_stat['documents']} док., {lang_stat['errors']} ошибок, {lang_stat['skipped']} пропущено")

    # Сводка по типам ошибок
    if error_types:
        print("\nСводка по типам ошибок:")
        for err_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"  {err_type}: {count}")

    return total_stats


# Backward compatibility alias
smart_index_important_only = smart_index_multi_language


def main():
    """
    Main entry point for the Multi-Language Smart Indexer CLI.

    Parses command-line arguments to list projects or index files by project name/path,
    with optional language filtering.

    Returns:
        None
    """
    parser = argparse.ArgumentParser(
        description="Multi-Language Smart Indexer - индексация файлов разных языков",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s --list                           # Список всех проектов
  %(prog)s --project 251229_GKS             # Индексировать проект по имени
  %(prog)s --path "полный/путь/к/проекту"   # Индексировать по полному пути
  %(prog)s --project 251229_GKS --languages bsl,js,py  # Только BSL, JS, Python
  %(prog)s --framework --languages js,ts    # Индексировать фреймворк (JS/TS)
        """
    )

    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="Показать список доступных проектов"
    )

    parser.add_argument(
        "--project", "-p",
        type=str,
        help="Имя проекта (например: 251229_GKS-Управление транспортом)"
    )

    parser.add_argument(
        "--path",
        type=str,
        help="Полный путь к проекту"
    )

    parser.add_argument(
        "--framework",
        action="store_true",
        help="Индексировать фреймворк (вместо проекта)"
    )

    parser.add_argument(
        "--languages",
        type=str,
        help="Языки для индексации через запятую (bsl,javascript,python,markdown,typescript). Default: bsl,javascript,python,markdown"
    )

    parser.add_argument(
        "--chunk-mode",
        type=str,
        choices=["full", "procedures", "smart"],
        default="smart",
        help="Режим разбиения файлов (default: smart)"
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Задержка между файлами в секундах (default: 0.5)"
    )

    parser.add_argument(
        "--full", "-f",
        action="store_true",
        help="Полная индексация (все файлы, без фильтрации)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Принудительная переиндексация (игнорировать hash, переиндексировать все файлы)"
    )

    args = parser.parse_args()

    # Показать список проектов
    if args.list or not (args.project or args.path or args.framework):
        projects = find_all_projects()
        if projects:
            print("[INFO] Доступные проекты для индексации:")
            for i, proj in enumerate(projects, 1):
                print(f"  {i}. {proj}")
            print(f"\nВсего проектов: {len(projects)}")
            print("\nПоддерживаемые языки:")
            for ext, config in SUPPORTED_EXTENSIONS.items():
                print(f"  - {config['name']} (*{ext})")
            print("\nИспользование:")
            print(f"  python {Path(__file__).name} --project ИМЯ_ПРОЕКТА")
            print(f"  python {Path(__file__).name} --project ИМЯ_ПРОЕКТА --languages bsl,js")
            print(f"  python {Path(__file__).name} --framework --languages js,ts,py")
        else:
            print("[ERROR] Проекты не найдены в папке configuration")
        return

    # Парсим языки
    languages = DEFAULT_LANGUAGES
    if args.languages:
        lang_input = args.languages.lower().replace(" ", "").split(",")
        # Валидация языков
        valid_langs = set()
        for lang in lang_input:
            # Проверяем по типу
            for ext, config in SUPPORTED_EXTENSIONS.items():
                if config["type"] == lang or lang in config["type"]:
                    valid_langs.add(config["type"])
        if valid_langs:
            languages = list(valid_langs)
        else:
            print(f"[ERROR] Некорректные языки: {args.languages}")
            print(f"[INFO] Доступные языки: {', '.join(set([v['type'] for v in SUPPORTED_EXTENSIONS.values()]))}")
            return

    # Определяем путь к проекту/фреймворку
    project_path = args.path
    if args.framework:
        project_path = r"D:\1С-Framework"
    elif args.project:
        base_path = Path(r"D:\1С-Framework\src\projects\configuration")
        project_path = str(base_path / args.project)

    if not project_path:
        print("[ERROR] Укажите --project, --path или --framework")
        return

    # Проверяем существование
    if not Path(project_path).exists():
        print(f"[ERROR] Путь не найден: {project_path}")
        return

    # Запускаем индексацию
    target_name = "Framework" if args.framework else Path(project_path).name
    print(f"[INFO] Индексация: {target_name}")
    print(f"[INFO] Путь: {project_path}")
    mode_info = "ПОЛНАЯ" if args.full else "smart (только важные)"
    lang_names = ", ".join([SUPPORTED_EXTENSIONS[LANGUAGE_TO_EXTENSION[l]]["name"] for l in languages if l in LANGUAGE_TO_EXTENSION])
    print(f"[INFO] Языки: {lang_names}")
    print(f"[INFO] Режим: {mode_info}, chunk: {args.chunk_mode}, Задержка: {args.delay} сек\n")

    smart_index_multi_language(
        project_path=project_path,
        languages=languages,
        chunk_mode=args.chunk_mode,
        delay_seconds=args.delay,
        full_index=args.full,
        force=args.force
    )


if __name__ == "__main__":
    main()

