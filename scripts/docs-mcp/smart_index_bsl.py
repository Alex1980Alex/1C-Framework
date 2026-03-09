#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Language Smart Indexer - индексация файлов разных языков
Поддержка: BSL, JavaScript, TypeScript, Python, Markdown

Использование:
    python smart_index_bsl.py                           # Список проектов
    python smart_index_bsl.py --list                   # Список проектов
    python smart_index_bsl.py --project 260304_GKSTCPLK-2182  # Индексировать проект
    python smart_index_bsl.py --path "полный/путь"     # Индексировать по пути
    python smart_index_bsl.py --languages bsl,js,py    # Указать языки

Migrated from D:\\1C-Enterprise_Framework to D:\\1С-Framework
"""

import sys
import time
import argparse
import traceback
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))


# ============================================================================
# CONFIGURATION
# ============================================================================

SUPPORTED_EXTENSIONS: Dict[str, Dict[str, str]] = {
    ".bsl": {"type": "bsl", "doc_type": "bsl", "name": "BSL", "method": "index_bsl_file"},
    ".js": {"type": "javascript", "doc_type": "javascript", "name": "JavaScript", "method": "index_javascript_file"},
    ".ts": {"type": "typescript", "doc_type": "typescript", "name": "TypeScript", "method": "index_javascript_file"},
    ".py": {"type": "python", "doc_type": "python", "name": "Python", "method": "index_document"},
    ".md": {"type": "markdown", "doc_type": "markdown", "name": "Markdown", "method": "index_document"},
}

LANGUAGE_TO_EXTENSION: Dict[str, str] = {
    "bsl": ".bsl",
    "javascript": ".js",
    "typescript": ".ts",
    "python": ".py",
    "markdown": ".md",
}

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

# Auto-detect framework root from script location
FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent.parent


def find_all_projects():
    """Находит все проекты в папке configuration"""
    base_path = FRAMEWORK_ROOT / "src" / "projects" / "configuration"
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
    """Получить все исходные файлы поддерживаемых типов"""
    if languages is None:
        languages = DEFAULT_LANGUAGES

    if skip_patterns is None:
        skip_patterns = SKIP_PATTERNS_BY_TYPE

    all_files = []

    for lang in languages:
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
    """Проверить, нужно ли пропустить файл"""
    path_str = str(file_path)

    if check_global:
        for pattern in GLOBAL_SKIP_PATTERNS:
            if pattern in path_str:
                return True

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
    """Индексирует файлы проекта разных языков"""
    if languages is None:
        languages = DEFAULT_LANGUAGES

    engine = HybridSearchEngine()
    project_root = Path(project_path)

    if not project_root.exists():
        print(f"[ERROR] Проект не найден: {project_path}")
        return

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

    is_configuration_project = "projects" in str(project_root) and "configuration" in str(project_root)
    filter_global = not is_configuration_project

    if is_configuration_project:
        print(f"[INFO] Индексация проекта из configuration - глобальный фильтр ОТКЛЮЧЕН")

    print(f"[SCAN] Сканирование файлов в {project_root}...", flush=True)
    all_files = get_all_source_files(project_root, languages, filter_global=filter_global)
    total_files = len(all_files)
    print(f"[SCAN] Найдено {total_files} файлов для обработки")

    stats_by_lang = {lang: {"files": 0, "documents": 0, "errors": 0, "skipped": 0} for lang in languages}
    total_stats = {"files": 0, "documents": 0, "errors": 0, "skipped": 0}
    error_types: Dict[str, int] = {}

    print(f"[INFO] Найдено файлов: {total_files}")

    for file_info in all_files:
        lang = file_info["type"]
        stats_by_lang[lang]["files"] = stats_by_lang.get(lang, {}).get("files", 0) + 1

    for lang, lang_stat in stats_by_lang.items():
        if lang_stat["files"] > 0:
            ext_names = [k for k, v in SUPPORTED_EXTENSIONS.items() if v["type"] == lang]
            print(f"  - {SUPPORTED_EXTENSIONS[ext_names[0]]['name']}: {lang_stat['files']} файлов")

    print()

    for i, file_info in enumerate(all_files, 1):
        file_path = file_info["path"]
        file_type = file_info["type"]
        lang_name = file_info["lang_name"]
        method_name = file_info["method"]

        if not full_index:
            if should_skip_file(file_path, file_type, SKIP_PATTERNS_BY_TYPE):
                stats_by_lang[file_type]["skipped"] += 1
                total_stats["skipped"] += 1
                continue

        try:
            index_method = getattr(engine, method_name)

            if method_name == "index_bsl_file":
                docs = index_method(str(file_path), chunk_mode=chunk_mode, force=force)
            elif method_name == "index_javascript_file":
                docs = index_method(str(file_path), chunk_mode=chunk_mode, force=force)
            else:
                doc_type = file_info.get("doc_type", "markdown")
                docs = index_method(str(file_path), doc_type=doc_type, force=force)

            stats_by_lang[file_type]["files"] += 1
            stats_by_lang[file_type]["documents"] += docs
            total_stats["files"] += 1
            total_stats["documents"] += docs

            if total_stats["files"] % 50 == 0 or (total_files > 0 and (i * 100 // total_files) % 10 == 0):
                pct = i * 100 // total_files
                print(f"[{pct:3d}%] {total_stats['files']} файлов, {total_stats['documents']} док. обработано")

            time.sleep(delay_seconds)

        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e) if str(e) else "No message"
            print(f"[ERROR] {lang_name} {file_path.name}")
            print(f"        Type: {error_type}")
            print(f"        Message: {error_msg[:200]}...")
            print(f"        Path: {file_path}")
            tb_lines = traceback.format_exc().strip().split('\n')
            if len(tb_lines) > 3:
                for line in tb_lines[-3:]:
                    print(f"        {line}")
            stats_by_lang[file_type]["errors"] += 1
            total_stats["errors"] += 1
            error_types[error_type] = error_types.get(error_type, 0) + 1

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

    if error_types:
        print("\nСводка по типам ошибок:")
        for err_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
            print(f"  {err_type}: {count}")

    return total_stats


smart_index_important_only = smart_index_multi_language


def ast_index_bsl(project_path: str, delay_seconds: float = 0.1, full_index: bool = False):
    """AST-based symbol-level indexing for BSL files (Phase 59).

    Uses BSLASTParser + BSLChunker to create symbol-level chunks
    with rich metadata (params, calls, regions, directives).
    Inserts directly into SQLite documents table (trigger populates FTS5).
    """
    import hashlib
    from datetime import datetime
    from src.bsl.parser.bsl_ast_parser import BSLASTParser
    from src.bsl.parser.bsl_chunker import BSLChunker

    parser = BSLASTParser()
    chunker = BSLChunker()
    engine = HybridSearchEngine()
    project_root = Path(project_path)

    bsl_files = list(project_root.rglob("*.bsl"))
    if not full_index:
        bsl_files = [f for f in bsl_files if not should_skip_file(f, "bsl", SKIP_PATTERNS_BY_TYPE)]

    print(f"[AST] Found {len(bsl_files)} BSL files for symbol-level indexing")

    total_chunks = 0
    total_symbols = 0
    errors = 0
    conn = engine.conn
    now = datetime.now().isoformat()

    for i, bsl_file in enumerate(bsl_files, 1):
        try:
            module = parser.parse_file(str(bsl_file))
            chunks = chunker.chunk_module(module)
            total_symbols += len(module.symbols)

            for chunk in chunks:
                meta = chunk.metadata
                # Build title from symbol name and type
                symbol_name = meta.get("symbol_name", "")
                symbol_type = meta.get("symbol_type", "")
                module_path = meta.get("module_path", str(bsl_file))
                title = f"{symbol_name} ({symbol_type})" if symbol_name else bsl_file.stem

                # Build tags
                tags_parts = ["bsl", "ast-symbol", symbol_type.lower()]
                if meta.get("is_export"):
                    tags_parts.append("export")
                if meta.get("compilation_directive"):
                    tags_parts.append(meta["compilation_directive"])
                tags = " ".join(t for t in tags_parts if t)

                content_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()

                conn.execute(
                    "INSERT OR REPLACE INTO documents "
                    "(id, title, path, content, content_preview, size, modified, tags, doc_type, content_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        chunk.chunk_id,
                        title,
                        module_path,
                        chunk.content,
                        chunk.content[:200],
                        len(chunk.content),
                        now,
                        tags,
                        "bsl-symbol",
                        content_hash,
                    ),
                )
                total_chunks += 1

            if i % 100 == 0:
                conn.commit()
                pct = i * 100 // len(bsl_files)
                print(f"[{pct:3d}%] {i}/{len(bsl_files)} files, {total_symbols} symbols, {total_chunks} chunks")

        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"[ERROR] {bsl_file.name}: {e}")

    conn.commit()
    print(f"\n[AST-DONE] Symbol-level indexing complete")
    print(f"  Files: {len(bsl_files)}")
    print(f"  Symbols: {total_symbols}")
    print(f"  Chunks: {total_chunks}")
    print(f"  Errors: {errors}")
    return {"files": len(bsl_files), "symbols": total_symbols, "chunks": total_chunks, "errors": errors}


def main():
    """Main entry point for the Multi-Language Smart Indexer CLI."""
    parser = argparse.ArgumentParser(
        description="Multi-Language Smart Indexer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s --list                           # Список всех проектов
  %(prog)s --project 260304_GKSTCPLK-2182   # Индексировать проект
  %(prog)s --path "полный/путь/к/проекту"   # Индексировать по полному пути
  %(prog)s --framework --languages js,ts    # Индексировать фреймворк
        """
    )

    parser.add_argument("--list", "-l", action="store_true", help="Список проектов")
    parser.add_argument("--project", "-p", type=str, help="Имя проекта")
    parser.add_argument("--path", type=str, help="Полный путь к проекту")
    parser.add_argument("--framework", action="store_true", help="Индексировать фреймворк")
    parser.add_argument("--languages", type=str, help="Языки (bsl,javascript,python,markdown,typescript)")
    parser.add_argument("--chunk-mode", type=str, choices=["full", "procedures", "smart"], default="smart")
    parser.add_argument("--delay", type=float, default=0.5, help="Задержка между файлами (сек)")
    parser.add_argument("--full", "-f", action="store_true", help="Полная индексация")
    parser.add_argument("--force", action="store_true", help="Принудительная переиндексация")
    parser.add_argument("--ast", action="store_true", help="AST-based symbol-level indexing for BSL (Phase 59)")

    args = parser.parse_args()

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
        else:
            print("[ERROR] Проекты не найдены в папке configuration")
        return

    languages = DEFAULT_LANGUAGES
    if args.languages:
        lang_input = args.languages.lower().replace(" ", "").split(",")
        valid_langs = set()
        for lang in lang_input:
            for ext, config in SUPPORTED_EXTENSIONS.items():
                if config["type"] == lang or lang in config["type"]:
                    valid_langs.add(config["type"])
        if valid_langs:
            languages = list(valid_langs)
        else:
            print(f"[ERROR] Некорректные языки: {args.languages}")
            return

    project_path = args.path
    if args.framework:
        project_path = str(FRAMEWORK_ROOT)
    elif args.project:
        base_path = FRAMEWORK_ROOT / "src" / "projects" / "configuration"
        project_path = str(base_path / args.project)

    if not project_path:
        print("[ERROR] Укажите --project, --path или --framework")
        return

    if not Path(project_path).exists():
        print(f"[ERROR] Путь не найден: {project_path}")
        return

    target_name = "Framework" if args.framework else Path(project_path).name
    print(f"[INFO] Индексация: {target_name}")
    print(f"[INFO] Путь: {project_path}")

    if args.ast:
        print(f"[INFO] Режим: AST symbol-level indexing (Phase 59)\n")
        ast_index_bsl(
            project_path=project_path,
            delay_seconds=args.delay,
            full_index=args.full,
        )
        return

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
