#!/usr/bin/env python3
"""
Гибридный поисковый движок для документации фреймворка 1C
Комбинирует полнотекстовый поиск (SQLite FTS5) и семантический поиск (sentence-transformers)
"""

import json
import sqlite3
import os
import hashlib
import threading
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, asdict
import logging
from datetime import datetime
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

def log_stderr(*args, **kwargs):
    """Логирование в stderr (НЕ в stdout - там MCP протокол!)"""
    print(*args, file=sys.stderr, **kwargs)

# File watching imports
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileModifiedEvent, FileDeletedEvent
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False
    log_stderr("Внимание: watchdog не установлен. Автоиндексация недоступна. Установите: pip install watchdog")

try:
    import importlib.util
    _st_spec = importlib.util.find_spec('sentence_transformers')
    EMBEDDINGS_AVAILABLE = _st_spec is not None
    np = None  # Загружается лениво вместе с моделью
    if not EMBEDDINGS_AVAILABLE:
        log_stderr("Внимание: sentence-transformers не установлен. Семантический поиск недоступен.")
except Exception:
    EMBEDDINGS_AVAILABLE = False
    np = None
    log_stderr("Внимание: sentence-transformers не установлен. Семантический поиск недоступен.")


def read_file_with_fallback(path: str, encodings: List[str] = None) -> Tuple[str, str]:
    """
    Читает файл с автоматическим определением кодировки.

    Args:
        path: Путь к файлу
        encodings: Список кодировок для попытки (по умолчанию: utf-8-sig, utf-8, cp1251, cp866, latin-1)

    Returns:
        Tuple[content, encoding]: Содержимое файла и использованная кодировка

    Raises:
        UnicodeDecodeError: Если ни одна кодировка не подошла
    """
    if encodings is None:
        encodings = ['utf-8-sig', 'utf-8', 'cp1251', 'cp866', 'latin-1']

    last_error = None
    for encoding in encodings:
        try:
            with open(path, 'r', encoding=encoding) as f:
                content = f.read()
            return content, encoding
        except UnicodeDecodeError as e:
            last_error = e
            continue

    # Если ничего не подошло, пробуем с errors='replace'
    try:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            content = f.read()
        log_stderr(f"[WARN] Файл {path} прочитан с заменой некорректных символов")
        return content, 'utf-8-replace'
    except Exception:
        pass

    raise last_error or UnicodeDecodeError('utf-8', b'', 0, 1, 'No encoding worked')


@dataclass
class Document:
    """Структура документа"""
    id: str
    title: str
    path: str
    content: str
    content_preview: str
    size: int
    modified: str
    tags: List[str]
    doc_type: str

@dataclass
class SearchResult:
    """Результат поиска"""
    document: Document
    score: float
    match_type: str  # 'fulltext', 'semantic', 'hybrid'
    snippet: str

# Константы для фильтрации
MIN_RELEVANCE_SCORE = 0.3  # Минимальный порог релевантности для semantic search
FTS5_SPECIAL_CHARS = ['?', '!', '*', '^', ':', '"', "'", '(', ')', '[', ']', '{', '}', '+', '-', '~', '@', '#', '$', '%', '&', '|', '\\', '/']

# Паттерны для исключения из индексации (папки и файлы)
EXCLUDE_PATTERNS = [
    'node_modules',
    '.venv',
    '__pycache__',
    '.git',
    '.pytest_cache',
    'dist',
    'build',
    '.tox',
    '.mypy_cache',
    '.ruff_cache',
    'egg-info',
    '.eggs',
    'vendor',
    'bower_components',
    'jspm_packages',
    '.next',
    '.nuxt',
    '.cache',
    'coverage',
    '.nyc_output',
    # Временные и служебные файлы
    'CHANGELOG',
    'LICENSE',
    'package-lock.json',
    'yarn.lock',
    'pnpm-lock.yaml',
]

def should_exclude_path(file_path: str) -> bool:
    """Проверяет, нужно ли исключить путь из индексации"""
    path_lower = file_path.lower().replace('\\', '/')
    for pattern in EXCLUDE_PATTERNS:
        if pattern.lower() in path_lower:
            return True
    return False

def sanitize_fts5_query(query: str) -> str:
    """Очистка запроса от спецсимволов FTS5"""
    sanitized = query
    for char in FTS5_SPECIAL_CHARS:
        sanitized = sanitized.replace(char, ' ')
    # Удаляем множественные пробелы и trim
    sanitized = ' '.join(sanitized.split())
    return sanitized if sanitized.strip() else query  # Возвращаем оригинал если пусто

class HybridSearchEngine:
    """Гибридный поисковый движок"""
    
    def __init__(self, db_path: str = "cache/docs-mcp/hybrid_search.db"):
        """Инициализация поискового движка"""
        # Настройка логирования
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[%(levelname)s] %(asctime)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Инициализация БД: {self.db_path}")
        
        self._embedding_model = None
        self._embedding_model_loaded = False
        if not EMBEDDINGS_AVAILABLE:
            self.logger.warning("sentence-transformers недоступен. Семантический поиск отключен.")
        
        try:
            self._init_database()
        except Exception as e:
            self.logger.error(f"Ошибка инициализации БД: {e}")
            raise

    @property
    def embedding_model(self):
        """Ленивая загрузка модели эмбеддингов при первом обращении"""
        if not self._embedding_model_loaded:
            self._embedding_model_loaded = True
            if EMBEDDINGS_AVAILABLE:
                try:
                    global np
                    from sentence_transformers import SentenceTransformer
                    import numpy as _np
                    np = _np
                    self._embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
                    self.logger.info("Модель эмбеддингов загружена: paraphrase-multilingual-MiniLM-L12-v2")
                except Exception as e:
                    self.logger.warning(f"Не удалось загрузить модель эмбеддингов: {e}")
        return self._embedding_model

    def _get_connection(self) -> sqlite3.Connection:
        """
        Создание соединения с базой данных с настройками для параллельного доступа.

        Настройки WAL режима:
        - journal_mode=WAL: позволяет одновременный доступ (1 writer + N readers)
        - busy_timeout=30000: ожидание 30 сек при блокировке вместо немедленной ошибки
        - synchronous=NORMAL: баланс между производительностью и надёжностью
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA synchronous=NORMAL")
        return conn

    def _migrate_fts_if_needed(self, conn, cursor):
        """Миграция FTS таблицы если схема устарела"""
        try:
            # Проверяем существует ли FTS таблица
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='documents_fts'")
            if not cursor.fetchone():
                return False  # Таблицы нет, миграция не нужна

            # Проверяем схему - в старой версии есть колонка 'path' или 'id'
            cursor.execute("PRAGMA table_info(documents_fts)")
            columns = [row[1] for row in cursor.fetchall()]

            # Новая схема: title, content, tags (без path, без id)
            needs_migration = 'path' in columns or 'id' in columns

            # Проверяем наличие триггеров
            cursor.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND name='documents_ai'")
            has_triggers = cursor.fetchone() is not None

            if needs_migration or not has_triggers:
                log_stderr("[MIGRATION] Обнаружена устаревшая схема FTS, выполняю миграцию...")

                # Удаляем старую FTS таблицу и триггеры
                cursor.execute("DROP TABLE IF EXISTS documents_fts")
                cursor.execute("DROP TRIGGER IF EXISTS documents_ai")
                cursor.execute("DROP TRIGGER IF EXISTS documents_ad")
                cursor.execute("DROP TRIGGER IF EXISTS documents_au")
                conn.commit()

                log_stderr("[MIGRATION] Старая FTS таблица и триггеры удалены")
                return True

            return False
        except Exception as e:
            log_stderr(f"[MIGRATION] Ошибка проверки схемы: {e}")
            return False

    def _init_database(self):
        """Инициализация базы данных"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Проверка и миграция FTS если нужно
        migrated = self._migrate_fts_if_needed(conn, cursor)

        # Таблица документов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                path TEXT UNIQUE NOT NULL,
                content TEXT NOT NULL,
                content_preview TEXT,
                size INTEGER,
                modified TEXT,
                tags TEXT,  -- JSON array
                doc_type TEXT,
                content_hash TEXT
            )
        """)
        
        # FTS5 таблица для полнотекстового поиска (standalone, не external content)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS documents_fts USING fts5(
                title,
                content,
                tags,
                tokenize='unicode61'
            )
        """)

        # Проверяем и создаём триггеры для синхронизации
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_ai AFTER INSERT ON documents BEGIN
                INSERT INTO documents_fts (rowid, title, content, tags)
                VALUES (new.rowid, new.title, new.content, new.tags);
            END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_ad AFTER DELETE ON documents BEGIN
                INSERT INTO documents_fts (documents_fts, rowid, title, content, tags)
                VALUES ('delete', old.rowid, old.title, old.content, old.tags);
            END
        """)
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS documents_au AFTER UPDATE ON documents BEGIN
                INSERT INTO documents_fts (documents_fts, rowid, title, content, tags)
                VALUES ('delete', old.rowid, old.title, old.content, old.tags);
                INSERT INTO documents_fts (rowid, title, content, tags)
                VALUES (new.rowid, new.title, new.content, new.tags);
            END
        """)

        # После миграции нужно пересобрать FTS из существующих документов
        if migrated:
            cursor.execute("SELECT COUNT(*) FROM documents")
            doc_count = cursor.fetchone()[0]
            if doc_count > 0:
                log_stderr(f"[MIGRATION] Пересобираю FTS индекс из {doc_count} документов...")
                cursor.execute("""
                    INSERT INTO documents_fts (rowid, title, content, tags)
                    SELECT rowid, title, content, tags FROM documents
                """)
                conn.commit()
                log_stderr("[MIGRATION] FTS индекс пересобран")

        # Таблица эмбеддингов (если доступны)
        if EMBEDDINGS_AVAILABLE:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS embeddings (
                    document_id TEXT PRIMARY KEY,
                    embedding BLOB,
                    FOREIGN KEY (document_id) REFERENCES documents (id)
                )
            """)
        
        # Индексы для оптимизации
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_type ON documents(doc_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_modified ON documents(modified)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_docs_path ON documents(path)")

        # Таблица метаданных индексации (для инкрементальной индексации)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS index_metadata (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                last_index_time TEXT,
                last_full_scan_time TEXT,
                total_files_indexed INTEGER,
                indexed_paths TEXT  -- JSON array of indexed paths
            )
        """)

        # Инициализация метаданных если нет
        cursor.execute("SELECT COUNT(*) FROM index_metadata")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO index_metadata (id, last_index_time, last_full_scan_time, total_files_indexed, indexed_paths)
                VALUES (1, NULL, NULL, 0, '[]')
            """)

        conn.commit()
        conn.close()

        log_stderr(f"[OK] База данных инициализирована: {self.db_path}")
    
    def _generate_doc_id(self, path: str) -> str:
        """Генерация уникального ID документа"""
        return hashlib.md5(path.encode()).hexdigest()[:12]
    
    def _get_content_hash(self, content: str) -> str:
        """Хеш содержимого для определения изменений"""
        return hashlib.sha256(content.encode()).hexdigest()
    
    def index_document(self, file_path: str, doc_type: str = "markdown", force: bool = False) -> bool:
        """Индексация одного документа

        Args:
            file_path: Путь к файлу
            doc_type: Тип документа (markdown, python, etc.)
            force: Принудительная переиндексация (игнорирует проверку hash)
        """
        path = Path(file_path)

        if not path.exists():
            log_stderr(f"[ERROR] Файл не найден: {file_path}")
            return False

        # Проверяем исключения (node_modules, .venv и т.д.)
        if should_exclude_path(str(path)):
            return False

        try:
            # Читаем содержимое с автоопределением кодировки
            content, used_encoding = read_file_with_fallback(str(path))
            if used_encoding not in ('utf-8', 'utf-8-sig'):
                log_stderr(f"[ENCODING] {path.name}: {used_encoding}")

            # Генерируем метаданные
            doc_id = self._generate_doc_id(str(path))
            content_hash = self._get_content_hash(content)

            # Проверяем, нужно ли обновлять (если не force)
            if not force and self._is_document_current(doc_id, content_hash):
                log_stderr(f"⏭️ Документ актуален: {path.name}")
                return True
            
            # Создаем документ
            document = Document(
                id=doc_id,
                title=path.stem,
                path=str(path),
                content=content,
                content_preview=content[:500] + "..." if len(content) > 500 else content,
                size=len(content),
                modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                tags=self._extract_tags(content, doc_type),
                doc_type=doc_type
            )
            
            # Сохраняем в базу
            self._save_document(document, content_hash)
            
            # Генерируем эмбеддинги если доступны
            if self.embedding_model:
                self._generate_embedding(document)
            
            log_stderr(f"[OK] Проиндексирован: {path.name}")
            return True

        except Exception as e:
            log_stderr(f"[ERROR] Ошибка индексации {file_path}: {e}")
            return False

    def delete_document(self, file_path: str) -> bool:
        """Удаление документа из индекса"""
        try:
            doc_id = self._generate_doc_id(file_path)

            conn = self._get_connection()
            cursor = conn.cursor()

            # Удаляем из основной таблицы (триггер documents_ad удалит из FTS)
            cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

            # Удаляем эмбеддинги если есть
            if self.embedding_model:
                cursor.execute("DELETE FROM embeddings WHERE document_id = ?", (doc_id,))

            rows_deleted = cursor.rowcount
            conn.commit()
            conn.close()

            if rows_deleted > 0:
                log_stderr(f"[OK] Удалён из индекса: {Path(file_path).name}")
                return True
            else:
                log_stderr(f"⏭️ Документ не найден в индексе: {Path(file_path).name}")
                return False

        except Exception as e:
            log_stderr(f"[ERROR] Ошибка удаления {file_path}: {e}")
            return False

    def delete_by_source(self, source_path: str) -> Dict[str, int]:
        """
        Удаление всех документов из индекса по префиксу пути (источнику).
        Используется для удаления всех документов проекта.

        Args:
            source_path: Путь к папке проекта (префикс пути документов)

        Returns:
            Dict с количеством удалённых документов по типам
        """
        stats = {"documents": 0, "fts": 0, "embeddings": 0, "total_files": 0}

        try:
            # Нормализуем путь для сравнения
            source_path_normalized = source_path.replace("\\", "/").rstrip("/")

            conn = self._get_connection()
            cursor = conn.cursor()

            # Находим все документы с путём, начинающимся с source_path
            cursor.execute(
                "SELECT id, path FROM documents WHERE path LIKE ? OR path LIKE ?",
                (f"{source_path_normalized}%", f"{source_path_normalized.replace('/', '\\\\')}%")
            )
            docs_to_delete = cursor.fetchall()

            if not docs_to_delete:
                log_stderr(f"⏭️ Документы с путём '{source_path}' не найдены в индексе")
                conn.close()
                return stats

            stats["total_files"] = len(docs_to_delete)
            log_stderr(f"[INFO] Найдено {len(docs_to_delete)} документов для удаления из источника: {source_path}")

            for doc_id, doc_path in docs_to_delete:
                # Удаляем из основной таблицы (триггер documents_ad автоматически удалит из FTS)
                cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
                if cursor.rowcount > 0:
                    stats["documents"] += 1
                    stats["fts"] += 1  # FTS синхронизируется через триггер

                # Удаляем эмбеддинги
                cursor.execute("DELETE FROM embeddings WHERE document_id = ?", (doc_id,))
                if cursor.rowcount > 0:
                    stats["embeddings"] += 1

            conn.commit()
            conn.close()

            log_stderr(f"[OK] Удалено из индекса: {stats['documents']} документов (FTS синхронизирован), {stats['embeddings']} эмбеддингов")
            return stats

        except Exception as e:
            log_stderr(f"[ERROR] Ошибка удаления по источнику {source_path}: {e}")
            return stats

    def get_indexed_projects(self) -> List[Dict[str, Any]]:
        """
        Получение списка проиндексированных проектов (уникальных source paths).

        Returns:
            List[Dict] с информацией о каждом источнике:
            - source_path: базовый путь
            - doc_count: количество документов
            - doc_types: типы документов
            - last_indexed: дата последней индексации
        """
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # Группируем документы по первым частям пути (до 3-го уровня)
            cursor.execute("""
                SELECT
                    path,
                    doc_type,
                    modified
                FROM documents
                ORDER BY path
            """)

            results = cursor.fetchall()
            conn.close()

            # Группируем по проектам (ищем паттерн src/projects/configuration/*)
            projects = {}

            for path, doc_type, modified_at in results:
                # Нормализуем путь
                path_normalized = path.replace("\\", "/")

                # Ищем проект по паттерну
                # Паттерн: */src/projects/configuration/{PROJECT_NAME}/*
                if "src/projects/configuration/" in path_normalized:
                    parts = path_normalized.split("src/projects/configuration/")
                    if len(parts) > 1:
                        project_parts = parts[1].split("/")
                        if project_parts:
                            project_name = project_parts[0]
                            base_path = parts[0] + "src/projects/configuration/" + project_name

                            if base_path not in projects:
                                projects[base_path] = {
                                    "source_path": base_path,
                                    "project_name": project_name,
                                    "doc_count": 0,
                                    "doc_types": set(),
                                    "last_indexed": modified_at
                                }

                            projects[base_path]["doc_count"] += 1
                            projects[base_path]["doc_types"].add(doc_type)
                            if modified_at and modified_at > projects[base_path]["last_indexed"]:
                                projects[base_path]["last_indexed"] = modified_at
                else:
                    # Для документации - используем базовый путь docs/
                    if "/docs/" in path_normalized:
                        parts = path_normalized.split("/docs/")
                        base_path = parts[0] + "/docs"

                        if base_path not in projects:
                            projects[base_path] = {
                                "source_path": base_path,
                                "project_name": "docs",
                                "doc_count": 0,
                                "doc_types": set(),
                                "last_indexed": modified_at
                            }

                        projects[base_path]["doc_count"] += 1
                        projects[base_path]["doc_types"].add(doc_type)
                        if modified_at and modified_at > projects[base_path]["last_indexed"]:
                            projects[base_path]["last_indexed"] = modified_at

            # Конвертируем set в list для JSON-сериализации
            result = []
            for proj in projects.values():
                proj["doc_types"] = list(proj["doc_types"])
                result.append(proj)

            return sorted(result, key=lambda x: x["doc_count"], reverse=True)

        except Exception as e:
            log_stderr(f"[ERROR] Ошибка получения списка проектов: {e}")
            return []

    def _is_document_current(self, doc_id: str, content_hash: str) -> bool:
        """Проверка актуальности документа"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT content_hash FROM documents WHERE id = ?", 
            (doc_id,)
        )
        result = cursor.fetchone()
        conn.close()
        
        return result and result[0] == content_hash
    
    def _extract_tags(self, content: str, doc_type: str = "markdown") -> List[str]:
        """Извлечение тегов из содержимого"""
        tags = []

        # Простая эвристика для тегов
        if "Task Master" in content:
            tags.append("task-master")
        if "BSL" in content:
            tags.append("bsl")
        if "MCP" in content:
            tags.append("mcp")
        if "Claude" in content:
            tags.append("claude")
        if "1C" in content or "1С" in content:
            tags.append("1c")
        if "API" in content:
            tags.append("api")
        if "integration" in content.lower() or "интеграция" in content.lower():
            tags.append("integration")

        # Специальные теги для BSL кода
        if doc_type == "bsl":
            tags.append("bsl")
            tags.append("1c")
            # Определяем тип модуля
            if "Процедура" in content or "Функция" in content:
                tags.append("code")
            if "ОбработкаПроведения" in content:
                tags.append("posting")
            if "ПриЗаписи" in content or "ПередЗаписью" in content:
                tags.append("events")
            if "Запрос" in content or "ВЫБРАТЬ" in content:
                tags.append("query")
            if "Экспорт" in content:
                tags.append("export")
            if "ОбщийМодуль" in content.lower() or "commonmodule" in content.lower():
                tags.append("common-module")

        return list(set(tags))  # Убираем дубликаты
    
    def _save_document(self, document: Document, content_hash: str):
        """Сохранение документа в базу"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Основная таблица (триггеры автоматически обновят FTS5)
        # tags сохраняем как строку через пробел для FTS-индексации
        tags_str = " ".join(document.tags) if document.tags else ""
        cursor.execute("""
            INSERT OR REPLACE INTO documents
            (id, title, path, content, content_preview, size, modified, tags, doc_type, content_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            document.id, document.title, document.path, document.content,
            document.content_preview, document.size, document.modified,
            tags_str, document.doc_type, content_hash
        ))
        # FTS5 синхронизируется автоматически через триггеры documents_ai/au
        
        conn.commit()
        conn.close()
    
    def _generate_embedding(self, document: Document):
        """Генерация эмбеддинга для документа"""
        if not self.embedding_model:
            return
        
        try:
            # Комбинируем заголовок и содержимое для эмбеддинга
            text_to_embed = f"{document.title} {document.content}"
            
            # Генерируем эмбеддинг
            embedding = self.embedding_model.encode(text_to_embed)
            
            # Сохраняем в базу
            conn = self._get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO embeddings (document_id, embedding)
                VALUES (?, ?)
            """, (document.id, embedding.tobytes()))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            log_stderr(f"[WARNING] Ошибка генерации эмбеддинга для {document.title}: {e}")
    
    def search(self, query: str, limit: int = 10, search_type: str = "hybrid") -> List[SearchResult]:
        """
        Основной метод поиска
        
        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            search_type: Тип поиска ('fulltext', 'semantic', 'hybrid')
        """
        if search_type == "fulltext":
            return self._fulltext_search(query, limit)
        elif search_type == "semantic" and self.embedding_model:
            return self._semantic_search(query, limit)
        elif search_type == "hybrid":
            return self._hybrid_search(query, limit)
        else:
            # Fallback на полнотекстовый поиск
            return self._fulltext_search(query, limit)
    
    def _fulltext_search(self, query: str, limit: int) -> List[SearchResult]:
        """Полнотекстовый поиск через FTS5"""
        try:
            # Санитизация запроса для FTS5
            safe_query = sanitize_fts5_query(query)
            if not safe_query.strip():
                self.logger.warning(f"Запрос '{query}' пуст после санитизации")
                return []

            self.logger.debug(f"Полнотекстовый поиск: '{safe_query}', лимит: {limit}")
            conn = self._get_connection()
            cursor = conn.cursor()

            # FTS5 запрос с правильным синтаксисом bm25
            cursor.execute("""
            SELECT d.*, bm25(documents_fts) as score
            FROM documents_fts
            JOIN documents d ON documents_fts.rowid = d.rowid
            WHERE documents_fts MATCH :query
            ORDER BY score
            LIMIT :limit
            """, {"query": safe_query, "limit": limit})
            
            results = []
            for row in cursor.fetchall():
                try:
                    document = self._row_to_document(row[:-1])  # Исключаем score
                    score = row[-1]
                    
                    # Генерируем snippet
                    snippet = self._generate_snippet(document.content, query)
                    
                    results.append(SearchResult(
                        document=document,
                        score=abs(score),  # BM25 может быть отрицательным
                        match_type="fulltext",
                        snippet=snippet
                    ))
                except Exception as e:
                    self.logger.error(f"Ошибка обработки результата: {e}")
                    continue
            
            conn.close()
            self.logger.info(f"Найдено {len(results)} результатов (fulltext)")
            return results
            
        except sqlite3.Error as e:
            self.logger.error(f"Ошибка SQL в fulltext_search: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка в fulltext_search: {e}")
            return []
    
    def _semantic_search(self, query: str, limit: int) -> List[SearchResult]:
        """Семантический поиск через эмбеддинги (двухфазный)"""
        if not self.embedding_model:
            self.logger.warning("Семантический поиск недоступен: модель не загружена")
            return []

        try:
            self.logger.debug(f"Семантический поиск: '{query}', лимит: {limit}")

            # Генерируем эмбеддинг запроса
            query_embedding = self.embedding_model.encode(query)

            conn = self._get_connection()
            cursor = conn.cursor()

            # === Фаза 1: загружаем ТОЛЬКО id + embedding, вычисляем сходство ===
            cursor.execute("SELECT document_id, embedding FROM embeddings")

            candidates = []  # (document_id, similarity)
            for row in cursor.fetchall():
                try:
                    doc_id = row[0]
                    stored_embedding = np.frombuffer(row[1], dtype=np.float32)

                    similarity = float(np.dot(query_embedding, stored_embedding) / (
                        np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                    ))

                    if similarity >= MIN_RELEVANCE_SCORE:
                        candidates.append((doc_id, similarity))
                except Exception as e:
                    self.logger.error(f"Ошибка обработки эмбеддинга {row[0] if row else 'unknown'}: {e}")
                    continue

            # Сортируем и берём top-N
            candidates.sort(key=lambda x: x[1], reverse=True)
            top_candidates = candidates[:limit]

            if not top_candidates:
                conn.close()
                self.logger.info("Найдено 0 результатов (semantic)")
                return []

            pre_filter_count = len(candidates)
            self.logger.debug(
                f"Фаза 1: {pre_filter_count} кандидатов выше порога {MIN_RELEVANCE_SCORE}, "
                f"берём top-{len(top_candidates)}"
            )

            # === Фаза 2: загружаем полные документы ТОЛЬКО для top-N ===
            top_ids = [c[0] for c in top_candidates]
            score_map = {c[0]: c[1] for c in top_candidates}

            placeholders = ",".join("?" * len(top_ids))
            cursor.execute(f"SELECT * FROM documents WHERE id IN ({placeholders})", top_ids)

            results = []
            for row in cursor.fetchall():
                try:
                    document = self._row_to_document(row)
                    snippet = self._generate_snippet(document.content, query)

                    results.append(SearchResult(
                        document=document,
                        score=score_map[document.id],
                        match_type="semantic",
                        snippet=snippet
                    ))
                except Exception as e:
                    self.logger.error(f"Ошибка обработки документа {row[0] if row else 'unknown'}: {e}")
                    continue

            conn.close()

            # Сортируем финальные результаты (порядок мог измениться после JOIN)
            results.sort(key=lambda x: x.score, reverse=True)

            self.logger.info(f"Найдено {len(results)} результатов (semantic)")
            return results

        except sqlite3.Error as e:
            self.logger.error(f"Ошибка SQL в semantic_search: {e}")
            return []
        except Exception as e:
            self.logger.error(f"Неожиданная ошибка в semantic_search: {e}")
            return []
    
    @staticmethod
    def _normalize_scores(results: List[SearchResult]) -> List[SearchResult]:
        """Нормализация скоров к диапазону [0, 1] через min-max нормализацию.

        BM25 скоры (0-100+) и косинусное сходство (0-1) имеют разные масштабы.
        Без нормализации BM25 полностью доминирует при комбинировании.
        """
        if not results:
            return results

        scores = [r.score for r in results]
        min_score = min(scores)
        max_score = max(scores)
        score_range = max_score - min_score

        if score_range == 0:
            # Все скоры одинаковые — нормализуем к 1.0
            for r in results:
                r.score = 1.0
        else:
            for r in results:
                r.score = (r.score - min_score) / score_range

        return results

    def _hybrid_search(self, query: str, limit: int) -> List[SearchResult]:
        """Гибридный поиск (комбинация fulltext + semantic)"""
        try:
            self.logger.debug(f"Гибридный поиск: '{query}', лимит: {limit}")

            # Получаем результаты от обоих методов
            fulltext_results = self._fulltext_search(query, limit * 2)
            semantic_results = self._semantic_search(query, limit * 2) if self.embedding_model else []

            # Нормализуем скоры к [0, 1] перед комбинированием
            fulltext_results = self._normalize_scores(fulltext_results)
            semantic_results = self._normalize_scores(semantic_results)

            # Создаем словарь результатов по document.id
            combined = {}

            # Добавляем полнотекстовые результаты
            for result in fulltext_results:
                doc_id = result.document.id
                combined[doc_id] = result
                combined[doc_id].score = result.score * 0.7  # Вес 70%

            # Добавляем/обновляем семантические результаты
            for result in semantic_results:
                doc_id = result.document.id
                if doc_id in combined:
                    # Комбинируем скоры
                    combined[doc_id].score += result.score * 0.3  # Вес 30%
                    combined[doc_id].match_type = "hybrid"
                else:
                    combined[doc_id] = result
                    combined[doc_id].score = result.score * 0.3

            # Сортируем и возвращаем топ результатов
            final_results = list(combined.values())
            final_results.sort(key=lambda x: x.score, reverse=True)

            # Фильтруем по минимальному порогу
            filtered_results = [r for r in final_results if r.score >= MIN_RELEVANCE_SCORE]

            if len(filtered_results) < len(final_results):
                self.logger.debug(f"Отфильтровано {len(final_results) - len(filtered_results)} результатов с низкой релевантностью")

            self.logger.info(f"Найдено {len(filtered_results[:limit])} результатов (hybrid)")
            return filtered_results[:limit]

        except Exception as e:
            self.logger.error(f"Ошибка в hybrid_search: {e}")
            # Fallback на fulltext поиск
            self.logger.info("Переход на fulltext поиск как fallback")
            return self._fulltext_search(query, limit)
    
    def _row_to_document(self, row) -> Document:
        """Преобразование строки БД в объект Document"""
        return Document(
            id=row[0],
            title=row[1],
            path=row[2],
            content=row[3],
            content_preview=row[4],
            size=row[5],
            modified=row[6],
            tags=json.loads(row[7]) if row[7] else [],
            doc_type=row[8]
        )
    
    def _generate_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """Генерация сниппета с контекстом запроса"""
        query_lower = query.lower()
        content_lower = content.lower()
        
        # Ищем первое вхождение запроса
        pos = content_lower.find(query_lower)
        
        if pos == -1:
            # Если точного совпадения нет, берем начало
            return content[:max_length] + "..." if len(content) > max_length else content
        
        # Определяем границы сниппета
        start = max(0, pos - max_length // 3)
        end = min(len(content), pos + len(query) + max_length // 3)
        
        snippet = content[start:end]
        
        # Добавляем многоточия
        if start > 0:
            snippet = "..." + snippet
        if end < len(content):
            snippet = snippet + "..."
            
        return snippet
    
    def get_statistics(self) -> Dict[str, Any]:
        """Получение статистики по индексу"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM documents")
        total_docs = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM embeddings")
        docs_with_embeddings = cursor.fetchone()[0]
        
        cursor.execute("SELECT SUM(size) FROM documents")
        total_size = cursor.fetchone()[0] or 0
        
        cursor.execute("SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type")
        types_stats = dict(cursor.fetchall())
        
        # Используем json_valid() для фильтрации невалидных JSON тегов
        cursor.execute("""
            SELECT COUNT(DISTINCT tags.value)
            FROM documents, json_each(documents.tags) AS tags
            WHERE documents.tags IS NOT NULL
              AND json_valid(documents.tags)
        """)
        unique_tags = cursor.fetchone()[0] or 0
        
        conn.close()
        
        return {
            "total_documents": total_docs,
            "documents_with_embeddings": docs_with_embeddings,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / 1024 / 1024, 2),
            "document_types": types_stats,
            "unique_tags": unique_tags,
            "embeddings_enabled": EMBEDDINGS_AVAILABLE and (self._embedding_model is not None or not self._embedding_model_loaded),
            "model_name": "paraphrase-multilingual-MiniLM-L12-v2" if EMBEDDINGS_AVAILABLE else None
        }

    # ============================================================================
    # ОПТИМИЗИРОВАННАЯ ИНДЕКСАЦИЯ (v2.0)
    # ============================================================================

    def generate_embeddings_batch(self, documents: List[Document], batch_size: int = 32,
                                   progress_callback: Optional[Callable[[int, int, str], None]] = None) -> int:
        """
        Батчевая генерация эмбеддингов для списка документов.

        Args:
            documents: Список документов для генерации эмбеддингов
            batch_size: Размер батча (по умолчанию 32)
            progress_callback: Callback для прогресса (current, total, message)

        Returns:
            Количество успешно обработанных документов
        """
        if not self.embedding_model or not documents:
            return 0

        total = len(documents)
        processed = 0

        # Разбиваем на батчи
        for i in range(0, total, batch_size):
            batch_docs = documents[i:i + batch_size]
            batch_texts = [f"{doc.title} {doc.content}" for doc in batch_docs]

            try:
                # Генерируем эмбеддинги для всего батча сразу
                embeddings = self.embedding_model.encode(batch_texts, show_progress_bar=False)

                # Сохраняем в базу
                conn = self._get_connection()
                cursor = conn.cursor()

                for doc, embedding in zip(batch_docs, embeddings):
                    cursor.execute("""
                        INSERT OR REPLACE INTO embeddings (document_id, embedding)
                        VALUES (?, ?)
                    """, (doc.id, embedding.tobytes()))

                conn.commit()
                conn.close()

                processed += len(batch_docs)

                if progress_callback:
                    progress_callback(processed, total, f"Эмбеддинги: {processed}/{total}")

            except Exception as e:
                log_stderr(f"[WARNING] Ошибка батчевой генерации эмбеддингов: {e}")
                # Fallback на поодиночную генерацию
                for doc in batch_docs:
                    try:
                        self._generate_embedding(doc)
                        processed += 1
                    except Exception:
                        pass

        return processed

    def index_bsl_file_data(self, file_path: str, chunk_mode: str = "smart") -> Tuple[List[Document], int]:
        """
        Индексация BSL файла БЕЗ генерации эмбеддингов (для параллельной обработки).
        Возвращает список документов для последующей батчевой генерации эмбеддингов.

        Args:
            file_path: Путь к .bsl файлу
            chunk_mode: Режим разбиения (full, procedures, smart)

        Returns:
            Tuple[List[Document], int]: (список документов, количество проиндексированных)
        """
        path = Path(file_path)
        documents = []

        if not path.exists() or path.suffix.lower() != '.bsl':
            return documents, 0

        try:
            # Читаем содержимое с попыткой разных кодировок
            content = None
            for encoding in ['utf-8-sig', 'utf-8', 'cp1251', 'cp866']:
                try:
                    with open(path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                return documents, 0

            # Извлекаем метаданные и анализируем содержимое
            metadata = self._extract_bsl_metadata(file_path)
            analysis = self._analyze_bsl_content(content)

            if chunk_mode == "full" or chunk_mode == "smart":
                # Создаём документ для всего файла
                summary = self._build_bsl_summary(content, metadata, analysis)
                enhanced_content = summary + "\n\n```bsl\n" + content + "\n```"

                doc_id = self._generate_doc_id(file_path)
                content_hash = self._get_content_hash(enhanced_content)

                title = f"{metadata['object_type']}: {metadata['object_name']}"
                if metadata['module_type']:
                    title += f" ({metadata['module_type']})"

                tags = self._extract_tags(content, "bsl")
                tags.extend([metadata['object_type'], metadata['module_type'] or 'module'])
                if analysis['event_handlers']:
                    tags.append('events')
                if analysis['queries']:
                    tags.append('queries')
                if analysis['api_calls']:
                    tags.append('bsp-api')
                tags.append(f"complexity:{analysis['complexity']}")

                document = Document(
                    id=doc_id,
                    title=title,
                    path=file_path,
                    content=enhanced_content,
                    content_preview=summary[:800],
                    size=len(content),
                    modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                    tags=list(set(tags)),
                    doc_type="bsl"
                )

                # Сохраняем документ (без эмбеддинга)
                self._save_document(document, content_hash)
                documents.append(document)

            if chunk_mode == "procedures" or chunk_mode == "smart":
                # Дополнительно разбиваем на процедуры (только для smart)
                if chunk_mode == "smart":
                    # В smart режиме добавляем только экспортные процедуры
                    chunks = [c for c in self._parse_bsl_content(content, file_path) if c.get('is_export')]
                else:
                    chunks = self._parse_bsl_content(content, file_path)

                for chunk in chunks:
                    chunk_id = f"{file_path}::{chunk['name']}"
                    doc_id = self._generate_doc_id(chunk_id)
                    content_hash = self._get_content_hash(chunk['content'])

                    proc_title = f"{metadata['object_type']}.{metadata['object_name']}.{chunk['name']}"
                    if chunk['is_export']:
                        proc_title += " (Экспорт)"

                    proc_tags = self._extract_tags(chunk['content'], "bsl")
                    proc_tags.extend([metadata['object_type'], chunk['type']])
                    if chunk['is_export']:
                        proc_tags.append('export')

                    proc_summary = f"# {chunk['type'].title()}: {chunk['name']}\n\n"
                    proc_summary += f"**Модуль:** {metadata['object_name']}\n"
                    enhanced_proc = proc_summary + "\n```bsl\n" + chunk['content'] + "\n```"

                    proc_document = Document(
                        id=doc_id,
                        title=proc_title,
                        path=chunk_id,
                        content=enhanced_proc,
                        content_preview=chunk['content'][:500],
                        size=len(chunk['content']),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=list(set(proc_tags)),
                        doc_type="bsl-procedure"
                    )

                    self._save_document(proc_document, content_hash)
                    documents.append(proc_document)

            return documents, len(documents)

        except Exception as e:
            log_stderr(f"[ERROR] Ошибка индексации {file_path}: {e}")
            return documents, 0

    # ============================================================================
    # ИНДЕКСАЦИЯ BSL ПРОЕКТОВ
    # ============================================================================

    def _parse_bsl_content(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """
        Парсинг BSL файла на чанки (процедуры/функции)

        Returns:
            Список чанков с метаданными:
            - name: имя процедуры/функции
            - type: 'procedure' или 'function'
            - content: полный текст
            - is_export: экспортная ли
            - start_line: начальная строка
        """
        import re
        chunks = []

        # Паттерн для процедур и функций (русский и английский)
        pattern = r'(?P<type>Процедура|Функция|Procedure|Function)\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)(?P<export>\s+Экспорт|\s+Export)?(?P<body>.*?)(?P<end>КонецПроцедуры|КонецФункции|EndProcedure|EndFunction)'

        matches = re.finditer(pattern, content, re.IGNORECASE | re.DOTALL)

        for match in matches:
            proc_type = match.group('type').lower()
            is_function = 'функц' in proc_type or 'function' in proc_type
            is_export = match.group('export') is not None

            chunk = {
                'name': match.group('name'),
                'type': 'function' if is_function else 'procedure',
                'params': match.group('params').strip(),
                'content': match.group(0),
                'is_export': is_export,
                'start_pos': match.start(),
                'file_path': file_path
            }
            chunks.append(chunk)

        # Если не нашли процедур - возвращаем весь файл как один чанк
        if not chunks:
            chunks.append({
                'name': Path(file_path).stem,
                'type': 'module',
                'params': '',
                'content': content,
                'is_export': False,
                'start_pos': 0,
                'file_path': file_path
            })

        return chunks

    def _extract_bsl_metadata(self, file_path: str) -> Dict[str, str]:
        """
        Извлечение метаданных из пути BSL файла

        Формат 1С EDT: src/CommonModules/МодульИмя/Module.bsl
        """
        path_parts = Path(file_path).parts

        metadata = {
            'object_type': 'unknown',
            'object_name': Path(file_path).stem,
            'module_type': 'unknown',
            'project': ''
        }

        # Определяем тип объекта по структуре пути
        type_mapping = {
            'CommonModules': 'ОбщийМодуль',
            'Documents': 'Документ',
            'Catalogs': 'Справочник',
            'DataProcessors': 'Обработка',
            'Reports': 'Отчёт',
            'InformationRegisters': 'РегистрСведений',
            'AccumulationRegisters': 'РегистрНакопления',
            'Constants': 'Константа',
            'Enums': 'Перечисление',
            'ChartsOfCharacteristicTypes': 'ПланВидовХарактеристик',
            'ChartsOfAccounts': 'ПланСчетов',
            'Tasks': 'Задача',
            'BusinessProcesses': 'БизнесПроцесс',
            'ExchangePlans': 'ПланОбмена',
            'SettingsStorages': 'ХранилищеНастроек',
            'HTTPServices': 'HTTPСервис',
            'WebServices': 'WebСервис'
        }

        for part in path_parts:
            if part in type_mapping:
                metadata['object_type'] = type_mapping[part]
                # Следующая часть - имя объекта
                idx = path_parts.index(part)
                if idx + 1 < len(path_parts):
                    metadata['object_name'] = path_parts[idx + 1]
                break

        # Определяем тип модуля по имени файла
        file_name = Path(file_path).name.lower()
        module_mapping = {
            'module.bsl': 'МодульОбъекта',
            'managermanagermodule.bsl': 'МодульМенеджера',
            'objectmodule.bsl': 'МодульОбъекта',
            'ext.bsl': 'МодульФормы',
            'commandmodule.bsl': 'МодульКоманды',
            'recordsetmodule.bsl': 'МодульНабораЗаписей'
        }

        for pattern, module_type in module_mapping.items():
            if pattern in file_name:
                metadata['module_type'] = module_type
                break

        # Извлекаем имя проекта из пути
        # Ищем папку проекта после 'configuration/'
        config_idx = -1
        for i, part in enumerate(path_parts):
            if part == 'configuration':
                config_idx = i
                break

        # Если нашли configuration, берём следующую часть как имя проекта
        if config_idx >= 0 and config_idx + 1 < len(path_parts):
            metadata['project'] = path_parts[config_idx + 1]
        else:
            # Fallback: ищем части начинающиеся с '25' или содержащие 'GKS'/'GKSTCPLK'
            for part in path_parts:
                if part.startswith('25') or 'GKSTCPLK' in part or 'GKS_' in part or '_GKS-' in part:
                    metadata['project'] = part
                    break

        return metadata

    def _analyze_bsl_content(self, content: str) -> Dict[str, Any]:
        """
        Глубокий анализ содержимого BSL файла

        Извлекает:
        - Области (#Область)
        - Директивы компиляции (&НаКлиенте, &НаСервере)
        - Зависимости (вызовы других модулей)
        - Используемые объекты метаданных
        - Запросы
        - Переменные модуля
        - Обработчики событий
        """
        import re
        analysis = {
            'regions': [],           # Области
            'directives': [],        # Директивы компиляции
            'dependencies': [],      # Зависимости от других модулей
            'metadata_objects': [],  # Используемые объекты метаданных
            'queries': [],           # SQL-подобные запросы
            'module_vars': [],       # Переменные модуля
            'event_handlers': [],    # Обработчики событий
            'api_calls': [],         # Вызовы БСП/API
            'complexity': 'low',     # Оценка сложности
            'lines_count': 0,
            'procedures_count': 0,
            'functions_count': 0
        }

        lines = content.split('\n')
        analysis['lines_count'] = len(lines)

        # 1. Области (#Область / #Region)
        region_pattern = r'#(?:Область|Region)\s+(\w+)'
        analysis['regions'] = re.findall(region_pattern, content, re.IGNORECASE)

        # 2. Директивы компиляции
        directive_pattern = r'&(НаКлиенте|НаСервере|НаСервереБезКонтекста|НаКлиентеНаСервереБезКонтекста|НаКлиентеНаСервере|AtClient|AtServer|AtServerNoContext)'
        analysis['directives'] = list(set(re.findall(directive_pattern, content, re.IGNORECASE)))

        # 3. Зависимости - вызовы других модулей (МодульИмя.Метод)
        dependency_pattern = r'([А-Яа-яA-Za-z_]\w+)\.([А-Яа-яA-Za-z_]\w+)\s*\('
        deps = re.findall(dependency_pattern, content)
        # Фильтруем системные объекты
        system_objects = {'Справочники', 'Документы', 'РегистрыСведений', 'РегистрыНакопления',
                        'Обработки', 'Отчёты', 'ПланыОбмена', 'Константы', 'Перечисления',
                        'Catalogs', 'Documents', 'InformationRegisters', 'AccumulationRegisters'}
        analysis['dependencies'] = list(set(
            f"{mod}.{method}" for mod, method in deps
            if mod not in system_objects and not mod.startswith('Этот')
        ))[:20]  # Ограничиваем топ-20

        # 4. Используемые объекты метаданных
        metadata_patterns = {
            'Справочники': r'Справочники\.(\w+)',
            'Документы': r'Документы\.(\w+)',
            'РегистрыСведений': r'РегистрыСведений\.(\w+)',
            'РегистрыНакопления': r'РегистрыНакопления\.(\w+)',
            'Обработки': r'Обработки\.(\w+)',
            'Отчёты': r'Отчёты\.(\w+)',
            'Перечисления': r'Перечисления\.(\w+)',
            'ПланыВидовХарактеристик': r'ПланыВидовХарактеристик\.(\w+)',
            'ПланыСчетов': r'ПланыСчетов\.(\w+)',
        }
        for obj_type, pattern in metadata_patterns.items():
            matches = re.findall(pattern, content)
            for match in set(matches):
                analysis['metadata_objects'].append(f"{obj_type}.{match}")

        # 5. Запросы (ВЫБРАТЬ / SELECT)
        query_pattern = r'(ВЫБРАТЬ|SELECT)\s+.{10,100}'
        queries = re.findall(query_pattern, content, re.IGNORECASE)
        analysis['queries'] = [q[:100] + '...' for q in queries[:5]]  # Топ-5 начал запросов

        # 6. Переменные модуля (Перем / Var в начале строки)
        var_pattern = r'^(?:Перем|Var)\s+(\w+)'
        analysis['module_vars'] = re.findall(var_pattern, content, re.MULTILINE | re.IGNORECASE)

        # 7. Обработчики событий (стандартные имена)
        event_handlers = [
            'ПриСозданииНаСервере', 'ПриОткрытии', 'ПередЗаписью', 'ПриЗаписи',
            'ОбработкаПроведения', 'ОбработкаУдаленияПроведения', 'ОбработкаЗаполнения',
            'ПередЗаписьюНаСервере', 'ПриЧтенииНаСервере', 'ПриКопировании',
            'ОбработчикОповещения', 'ПриИзменении', 'ПриАктивизацииСтроки',
            'OnCreateAtServer', 'OnOpen', 'BeforeWrite', 'OnWrite', 'Posting'
        ]
        for handler in event_handlers:
            if handler in content:
                analysis['event_handlers'].append(handler)

        # 8. Вызовы БСП/API (типичные модули БСП)
        bsp_modules = [
            'ОбщегоНазначения', 'ОбщегоНазначенияКлиент', 'ОбщегоНазначенияКлиентСервер',
            'СтроковыеФункцииКлиентСервер', 'ОбщегоНазначенияСервер',
            'РаботаСФайлами', 'ЭлектроннаяПодпись', 'Пользователи', 'УправлениеДоступом',
            'ОбменДанными', 'ВерсионированиеОбъектов', 'ПолнотекстовыйПоиск'
        ]
        for module in bsp_modules:
            if module in content:
                analysis['api_calls'].append(module)

        # 9. Подсчёт процедур и функций
        analysis['procedures_count'] = len(re.findall(r'\b(?:Процедура|Procedure)\s+\w+', content, re.IGNORECASE))
        analysis['functions_count'] = len(re.findall(r'\b(?:Функция|Function)\s+\w+', content, re.IGNORECASE))

        # 10. Оценка сложности
        total_methods = analysis['procedures_count'] + analysis['functions_count']
        if total_methods > 20 or analysis['lines_count'] > 1000:
            analysis['complexity'] = 'high'
        elif total_methods > 10 or analysis['lines_count'] > 500:
            analysis['complexity'] = 'medium'
        else:
            analysis['complexity'] = 'low'

        return analysis

    def _build_bsl_summary(self, content: str, metadata: Dict, analysis: Dict) -> str:
        """
        Построение структурированного summary для BSL файла
        Этот summary используется для семантического поиска
        """
        summary_parts = []

        # Заголовок
        summary_parts.append(f"# {metadata['object_type']}: {metadata['object_name']}")
        summary_parts.append(f"Тип модуля: {metadata['module_type']}")

        if metadata['project']:
            summary_parts.append(f"Проект: {metadata['project']}")

        # Статистика
        summary_parts.append(f"\n## Статистика")
        summary_parts.append(f"- Строк кода: {analysis['lines_count']}")
        summary_parts.append(f"- Процедур: {analysis['procedures_count']}")
        summary_parts.append(f"- Функций: {analysis['functions_count']}")
        summary_parts.append(f"- Сложность: {analysis['complexity']}")

        # Области
        if analysis['regions']:
            summary_parts.append(f"\n## Области")
            for region in analysis['regions']:
                summary_parts.append(f"- {region}")

        # Директивы компиляции
        if analysis['directives']:
            summary_parts.append(f"\n## Контекст выполнения")
            summary_parts.append(", ".join(analysis['directives']))

        # Зависимости
        if analysis['dependencies']:
            summary_parts.append(f"\n## Зависимости (вызываемые модули)")
            for dep in analysis['dependencies'][:10]:
                summary_parts.append(f"- {dep}")

        # Используемые объекты метаданных
        if analysis['metadata_objects']:
            summary_parts.append(f"\n## Используемые объекты конфигурации")
            for obj in analysis['metadata_objects'][:15]:
                summary_parts.append(f"- {obj}")

        # Обработчики событий
        if analysis['event_handlers']:
            summary_parts.append(f"\n## Обработчики событий")
            for handler in analysis['event_handlers']:
                summary_parts.append(f"- {handler}")

        # БСП API
        if analysis['api_calls']:
            summary_parts.append(f"\n## Используемые модули БСП")
            for api in analysis['api_calls']:
                summary_parts.append(f"- {api}")

        # Запросы
        if analysis['queries']:
            summary_parts.append(f"\n## Запросы к данным")
            summary_parts.append(f"Найдено запросов: {len(analysis['queries'])}")

        # Переменные модуля
        if analysis['module_vars']:
            summary_parts.append(f"\n## Переменные модуля")
            for var in analysis['module_vars']:
                summary_parts.append(f"- {var}")

        summary_parts.append(f"\n---\n## Исходный код\n")

        return "\n".join(summary_parts)

    def index_bsl_file(self, file_path: str, chunk_mode: str = "smart", force: bool = False) -> int:
        """
        Индексация BSL файла с глубоким анализом содержимого

        Args:
            file_path: Путь к .bsl файлу
            chunk_mode: Режим разбиения:
                - "full": весь файл как один документ с анализом
                - "procedures": каждая процедура/функция как отдельный документ
                - "smart": структурированный анализ + экспортные API (рекомендуется)
            force: Принудительная переиндексация (игнорирует проверку hash)

        Returns:
            Количество проиндексированных документов
        """
        path = Path(file_path)

        if not path.exists() or path.suffix.lower() != '.bsl':
            log_stderr(f"[ERROR] Файл не найден или не BSL: {file_path}")
            return 0

        try:
            # Читаем содержимое с попыткой разных кодировок
            content = None
            for encoding in ['utf-8-sig', 'utf-8', 'cp1251', 'cp866']:
                try:
                    with open(path, 'r', encoding=encoding) as f:
                        content = f.read()
                    break
                except UnicodeDecodeError:
                    continue

            if content is None:
                log_stderr(f"[ERROR] Не удалось прочитать {file_path}")
                return 0

            # Извлекаем метаданные из пути и анализируем содержимое
            metadata = self._extract_bsl_metadata(file_path)
            analysis = self._analyze_bsl_content(content)
            indexed_count = 0

            if chunk_mode == "full":
                # Индексируем весь файл с summary
                summary = self._build_bsl_summary(content, metadata, analysis)
                enhanced_content = summary + "\n\n```bsl\n" + content + "\n```"

                doc_id = self._generate_doc_id(file_path)
                content_hash = self._get_content_hash(enhanced_content)

                if force or not self._is_document_current(doc_id, content_hash):
                    title = f"{metadata['object_type']}: {metadata['object_name']}"
                    if metadata['module_type']:
                        title += f" ({metadata['module_type']})"

                    # Формируем теги на основе анализа
                    tags = self._extract_tags(content, "bsl")
                    tags.extend([metadata['object_type'], metadata['module_type'] or 'module'])
                    if analysis['event_handlers']:
                        tags.append('events')
                    if analysis['queries']:
                        tags.append('queries')
                    if analysis['api_calls']:
                        tags.append('bsp-api')
                    tags.append(f"complexity:{analysis['complexity']}")

                    document = Document(
                        id=doc_id,
                        title=title,
                        path=file_path,
                        content=enhanced_content,
                        content_preview=summary[:800],
                        size=len(content),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=list(set(tags)),
                        doc_type="bsl"
                    )

                    self._save_document(document, content_hash)
                    if self.embedding_model:
                        self._generate_embedding(document)
                    indexed_count = 1

            elif chunk_mode == "procedures":
                # Разбиваем на процедуры/функции
                chunks = self._parse_bsl_content(content, file_path)
                for chunk in chunks:
                    chunk_id = f"{file_path}::{chunk['name']}"
                    doc_id = self._generate_doc_id(chunk_id)
                    content_hash = self._get_content_hash(chunk['content'])

                    if not force and self._is_document_current(doc_id, content_hash):
                        continue

                    # Анализируем отдельную процедуру
                    chunk_analysis = self._analyze_bsl_content(chunk['content'])

                    # Формируем заголовок с метаданными
                    title = f"{metadata['object_type']}.{metadata['object_name']}.{chunk['name']}"
                    if chunk['is_export']:
                        title += " (Экспорт)"

                    # Формируем теги для процедуры
                    tags = self._extract_tags(chunk['content'], "bsl")
                    tags.extend([metadata['object_type'], chunk['type']])
                    if chunk['is_export']:
                        tags.append('export')
                    if chunk_analysis['directives']:
                        tags.extend([d.lower() for d in chunk_analysis['directives']])

                    # Формируем краткое описание процедуры
                    proc_summary = f"# {chunk['type'].title()}: {chunk['name']}\n\n"
                    proc_summary += f"**Модуль:** {metadata['object_name']}\n"
                    proc_summary += f"**Тип объекта:** {metadata['object_type']}\n"
                    if chunk['is_export']:
                        proc_summary += "**Экспортная:** Да\n"
                    if chunk_analysis['directives']:
                        proc_summary += f"**Директивы:** {', '.join(chunk_analysis['directives'])}\n"

                    enhanced_content = proc_summary + "\n```bsl\n" + chunk['content'] + "\n```"

                    document = Document(
                        id=doc_id,
                        title=title,
                        path=chunk_id,
                        content=enhanced_content,
                        content_preview=chunk['content'][:500] + "..." if len(chunk['content']) > 500 else chunk['content'],
                        size=len(chunk['content']),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=list(set(tags)),
                        doc_type="bsl-procedure"
                    )

                    self._save_document(document, content_hash)
                    if self.embedding_model:
                        self._generate_embedding(document)
                    indexed_count += 1

            elif chunk_mode == "smart":
                # Структурированный анализ всего модуля
                summary = self._build_bsl_summary(content, metadata, analysis)

                doc_id = self._generate_doc_id(file_path)
                content_hash = self._get_content_hash(content + summary)

                if force or not self._is_document_current(doc_id, content_hash):
                    title = f"{metadata['object_type']}: {metadata['object_name']}"
                    if metadata['module_type']:
                        title += f" ({metadata['module_type']})"

                    # Комплексные теги на основе анализа
                    tags = self._extract_tags(content, "bsl")
                    tags.extend([metadata['object_type']])
                    if metadata['module_type']:
                        tags.append(metadata['module_type'])
                    if metadata['project']:
                        tags.append(f"project:{metadata['project']}")

                    # Теги на основе анализа содержимого
                    for directive in analysis['directives']:
                        tags.append(directive.lower())
                    if analysis['event_handlers']:
                        tags.append('event-handlers')
                    if analysis['queries']:
                        tags.append('has-queries')
                    if analysis['api_calls']:
                        tags.append('uses-bsp')
                    if analysis['metadata_objects']:
                        tags.append('uses-metadata')
                    tags.append(f"complexity:{analysis['complexity']}")

                    # Содержимое = summary + код
                    enhanced_content = summary + "\n\n```bsl\n" + content + "\n```"

                    document = Document(
                        id=doc_id,
                        title=title,
                        path=file_path,
                        content=enhanced_content,
                        content_preview=summary[:1000],
                        size=len(content),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=list(set(tags)),
                        doc_type="bsl"
                    )

                    self._save_document(document, content_hash)
                    if self.embedding_model:
                        self._generate_embedding(document)
                    indexed_count = 1

                # Дополнительно индексируем экспортные процедуры как API
                chunks = self._parse_bsl_content(content, file_path)
                export_chunks = [c for c in chunks if c['is_export']]

                for chunk in export_chunks:
                    chunk_id = f"{file_path}::api::{chunk['name']}"
                    doc_id = self._generate_doc_id(chunk_id)
                    content_hash = self._get_content_hash(chunk['content'])

                    if not force and self._is_document_current(doc_id, content_hash):
                        continue

                    # Анализ экспортной процедуры
                    chunk_analysis = self._analyze_bsl_content(chunk['content'])

                    title = f"API: {metadata['object_name']}.{chunk['name']}"

                    # Описание API
                    api_desc = f"# API: {chunk['name']}\n\n"
                    api_desc += f"**Модуль:** {metadata['object_name']}\n"
                    api_desc += f"**Тип:** {metadata['object_type']}\n"
                    api_desc += f"**Вид:** {chunk['type']}\n"
                    if chunk_analysis['directives']:
                        api_desc += f"**Контекст выполнения:** {', '.join(chunk_analysis['directives'])}\n"
                    if chunk_analysis['dependencies']:
                        api_desc += f"**Зависимости:** {', '.join(chunk_analysis['dependencies'][:5])}\n"

                    enhanced_content = api_desc + "\n```bsl\n" + chunk['content'] + "\n```"

                    tags = ['api', 'export', metadata['object_type'], chunk['type']]
                    if metadata['project']:
                        tags.append(f"project:{metadata['project']}")
                    if chunk_analysis['directives']:
                        tags.extend([d.lower() for d in chunk_analysis['directives']])

                    document = Document(
                        id=doc_id,
                        title=title,
                        path=chunk_id,
                        content=enhanced_content,
                        content_preview=chunk['content'][:500],
                        size=len(chunk['content']),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=list(set(tags)),
                        doc_type="bsl-api"
                    )

                    self._save_document(document, content_hash)
                    if self.embedding_model:
                        self._generate_embedding(document)
                    indexed_count += 1

            log_stderr(f"[OK] BSL: {path.name} → {indexed_count} док. (режим: {chunk_mode})")
            return indexed_count

        except Exception as e:
            log_stderr(f"[ERROR] BSL индексация {file_path}: {e}")
            import traceback
            log_stderr(traceback.format_exc())
            return 0

    # ========================================================================
    # JAVASCRIPT / TYPESCRIPT INDEXING
    # ========================================================================

    def _extract_js_functions(self, content: str) -> List[Dict[str, Any]]:
        """Извлекает функции из JavaScript/TypeScript кода"""
        import re
        functions = []

        # Function declaration: function name() {}
        pattern1 = r'function\s+(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(pattern1, content):
            start = match.start()
            functions.append({
                'name': match.group(1),
                'type': 'function',
                'start': start,
                'line': content[:start].count('\n') + 1
            })

        # Method declaration: methodName() {}
        pattern2 = r'(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(pattern2, content):
            # Исключаем function keyword (уже обработаны) и new keyword
            prefix_start = max(0, match.start() - 20)
            prefix = content[prefix_start:match.start()]
            if not re.search(r'\b(function|new|if|while|for|switch|catch)\s*$', prefix):
                functions.append({
                    'name': match.group(1),
                    'type': 'method',
                    'start': match.start(),
                    'line': content[:match.start()].count('\n') + 1
                })

        # Arrow functions: const name = () => {}
        pattern3 = r'(?:const|let|var)\s+(\w+)\s*=\s*(?:\([^)]*\)|\w+)\s*=>'
        for match in re.finditer(pattern3, content):
            functions.append({
                'name': match.group(1),
                'type': 'arrow-function',
                'start': match.start(),
                'line': content[:match.start()].count('\n') + 1
            })

        # Async functions
        pattern4 = r'async\s+function\s+(\w+)\s*\([^)]*\)\s*\{'
        for match in re.finditer(pattern4, content):
            functions.append({
                'name': match.group(1),
                'type': 'async-function',
                'start': match.start(),
                'line': content[:match.start()].count('\n') + 1
            })

        return functions

    def _extract_js_classes(self, content: str) -> List[Dict[str, Any]]:
        """Извлекает классы из JavaScript/TypeScript кода"""
        import re
        classes = []

        # Class declaration: class Name {}
        pattern = r'class\s+(\w+)\s*(?:extends\s+(\w+)\s*)?\{'
        for match in re.finditer(pattern, content):
            classes.append({
                'name': match.group(1),
                'parent': match.group(2) if match.lastindex > 1 else None,
                'type': 'class'
            })

        return classes

    def _extract_js_exports(self, content: str) -> List[Dict[str, Any]]:
        """Извлекает экспорты из JavaScript/TypeScript модуля"""
        import re
        exports = []

        # Named exports: export function name() {}
        pattern1 = r'export\s+(?:function|const|let|var|class)\s+(\w+)'
        for match in re.finditer(pattern1, content):
            exports.append({
                'name': match.group(1),
                'type': 'named'
            })

        # Default exports: export default ...
        pattern2 = r'export\s+default\s+(?:function|class)?\s*(\w*)'
        match = re.search(pattern2, content)
        if match:
            exports.append({
                'name': match.group(1) or 'default',
                'type': 'default'
            })

        return exports

    def _analyze_js_content(self, content: str) -> Dict[str, Any]:
        """Анализирует JavaScript/TypeScript содержимое"""
        import re

        analysis = {
            'functions': [],
            'classes': [],
            'exports': [],
            'imports': [],
            'dependencies': [],
            'complexity': 0,
            'lines': content.count('\n') + 1
        }

        # Извлекаем структуры
        analysis['functions'] = self._extract_js_functions(content)
        analysis['classes'] = self._extract_js_classes(content)
        analysis['exports'] = self._extract_js_exports(content)

        # Извлекаем импорты
        import_patterns = [
            r'import\s+.*?\s+from\s+[\'"]([^\'"]+)[\'"]',
            r'import\(([\'"]([^\'"]+)[\'"])\)',
            r'require\([\'"]([^\'"]+)[\'"]\)'
        ]
        for pattern in import_patterns:
            for match in re.finditer(pattern, content):
                dep = match.group(1)
                if dep and dep not in analysis['imports']:
                    analysis['imports'].append(dep)

        # Вычисляем сложность (количество функций + классы)
        analysis['complexity'] = len(analysis['functions']) + len(analysis['classes']) * 2

        # Классифицируем сложность
        if analysis['complexity'] < 5:
            complexity_level = 'low'
        elif analysis['complexity'] < 15:
            complexity_level = 'medium'
        else:
            complexity_level = 'high'
        analysis['complexity_level'] = complexity_level

        return analysis

    def index_javascript_file(self, file_path: str, chunk_mode: str = "smart", force: bool = False) -> int:
        """
        Индексация JavaScript/TypeScript файла с анализом содержимого

        Args:
            file_path: Путь к .js/.ts файлу
            chunk_mode: Режим разбиения:
                - "full": весь файл как один документ с анализом
                - "functions": каждая функция как отдельный документ
                - "smart": структурированный анализ + экспортные API (рекомендуется)
            force: Принудительная переиндексация (игнорирует проверку hash)

        Returns:
            Количество проиндексированных документов
        """
        path = Path(file_path)

        if not path.exists():
            log_stderr(f"[ERROR] Файл не найден: {file_path}")
            return 0

        # Проверяем расширение
        ext = path.suffix.lower()
        if ext not in ['.js', '.ts', '.jsx', '.tsx', '.mjs']:
            log_stderr(f"[ERROR] Не JavaScript/TypeScript файл: {file_path}")
            return 0

        # Проверяем исключения
        if should_exclude_path(str(path)):
            return 0

        try:
            # Читаем содержимое с автоопределением кодировки
            content, used_encoding = read_file_with_fallback(str(path))
            if used_encoding not in ('utf-8', 'utf-8-sig'):
                log_stderr(f"[ENCODING] {path.name}: {used_encoding}")

            # Определяем тип
            doc_type = 'typescript' if ext in ['.ts', '.tsx'] else 'javascript'

            # Анализируем содержимое
            analysis = self._analyze_js_content(content)
            indexed_count = 0

            if chunk_mode == "full":
                # Индексируем весь файл с summary
                summary = self._build_js_summary(content, path, analysis)

                doc_id = self._generate_doc_id(file_path)
                content_hash = self._get_content_hash(content)

                if force or not self._is_document_current(doc_id, content_hash):
                    tags = self._extract_tags(content, doc_type)
                    tags.append(doc_type)
                    tags.append(f"complexity:{analysis['complexity_level']}")
                    if analysis['exports']:
                        tags.append('has-exports')
                    if analysis['classes']:
                        tags.append('has-classes')

                    document = Document(
                        id=doc_id,
                        title=path.stem,
                        path=file_path,
                        content=content,
                        content_preview=summary[:800],
                        size=len(content),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=list(set(tags)),
                        doc_type=doc_type
                    )

                    self._save_document(document, content_hash)
                    if self.embedding_model:
                        self._generate_embedding(document)
                    indexed_count = 1

            elif chunk_mode == "functions":
                # Индексируем каждую функцию отдельно
                for func in analysis['functions']:
                    func_id = f"{file_path}::{func['name']}"
                    doc_id = self._generate_doc_id(func_id)
                    # Для hash используем имя функции (упрощённо)
                    content_hash = self._get_content_hash(f"{func['name']}:{func.get('line', 0)}")

                    if not force and self._is_document_current(doc_id, content_hash):
                        continue

                    title = f"{func['type']}: {func['name']}"
                    desc = f"# {func['type']}: {func['name']}\n\n"
                    desc += f"**Файл:** {path.name}\n"
                    desc += f"**Строка:** {func.get('line', '?')}\n"
                    desc += f"**Тип:** {func['type']}\n"

                    # Находим тело функции (упрощённо - берём 50 строк после начала)
                    lines = content.split('\n')
                    start_line = func.get('line', 1) - 1
                    func_lines = lines[start_line:min(start_line + 50, len(lines))]
                    func_content = '\n'.join(func_lines)

                    enhanced_content = desc + f"\n```{doc_type}\n{func_content}\n```"

                    tags = [doc_type, func['type'], 'function']
                    if 'async' in func['type']:
                        tags.append('async')

                    document = Document(
                        id=doc_id,
                        title=title,
                        path=func_id,
                        content=enhanced_content,
                        content_preview=func_content[:500],
                        size=len(func_content),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=tags,
                        doc_type=f"{doc_type}-function"
                    )

                    self._save_document(document, content_hash)
                    if self.embedding_model:
                        self._generate_embedding(document)
                    indexed_count += 1

            elif chunk_mode == "smart":
                # Структурированный анализ + экспортные API
                summary = self._build_js_summary(content, path, analysis)
                enhanced_content = summary + "\n\n```" + doc_type + "\n" + content + "\n```"

                doc_id = self._generate_doc_id(file_path)
                content_hash = self._get_content_hash(enhanced_content)

                if force or not self._is_document_current(doc_id, content_hash):
                    tags = self._extract_tags(content, doc_type)
                    tags.append(doc_type)
                    tags.append(f"complexity:{analysis['complexity_level']}")
                    if analysis['exports']:
                        tags.append('has-exports')
                        for exp in analysis['exports']:
                            tags.append(f"export:{exp['name']}")
                    if analysis['classes']:
                        tags.append('has-classes')
                        for cls in analysis['classes']:
                            tags.append(f"class:{cls['name']}")
                    if analysis['imports']:
                        tags.append('has-imports')

                    document = Document(
                        id=doc_id,
                        title=path.stem,
                        path=file_path,
                        content=enhanced_content,
                        content_preview=summary[:1000],
                        size=len(content),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=list(set(tags)),
                        doc_type=doc_type
                    )

                    self._save_document(document, content_hash)
                    if self.embedding_model:
                        self._generate_embedding(document)
                    indexed_count = 1

                # Дополнительно индексируем экспорты как API
                for exp in analysis['exports']:
                    exp_id = f"{file_path}::export::{exp['name']}"
                    doc_id = self._generate_doc_id(exp_id)
                    content_hash = self._get_content_hash(f"export:{exp['name']}:{exp['type']}")

                    if not force and self._is_document_current(doc_id, content_hash):
                        continue

                    title = f"Export: {exp['name']} ({path.name})"

                    # Описание экспорта
                    api_desc = f"# Export: {exp['name']}\n\n"
                    api_desc += f"**Модуль:** {path.name}\n"
                    api_desc += f"**Тип экспорта:** {exp['type']}\n"
                    api_desc += f"**Тип файла:** {doc_type}\n"
                    if analysis['functions']:
                        api_desc += f"\n**Функции ({len(analysis['functions'])}):** "
                        api_desc += ", ".join([f['name'] for f in analysis['functions'][:5]])
                        if len(analysis['functions']) > 5:
                            api_desc += f" ... и ещё {len(analysis['functions']) - 5}"
                    if analysis['classes']:
                        api_desc += f"\n**Классы ({len(analysis['classes'])}):** "
                        api_desc += ", ".join([c['name'] for c in analysis['classes']])

                    enhanced_content = api_desc + "\n\n```" + doc_type + "\n" + content + "\n```"

                    tags = ['api', 'export', doc_type, exp['type']]
                    if exp['name'] != 'default':
                        tags.append(f"export:{exp['name']}")

                    document = Document(
                        id=doc_id,
                        title=title,
                        path=exp_id,
                        content=enhanced_content,
                        content_preview=api_desc[:500],
                        size=len(content),
                        modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                        tags=list(set(tags)),
                        doc_type=f"{doc_type}-export"
                    )

                    self._save_document(document, content_hash)
                    if self.embedding_model:
                        self._generate_embedding(document)
                    indexed_count += 1

            log_stderr(f"[OK] {doc_type.upper()}: {path.name} → {indexed_count} док. (режим: {chunk_mode})")
            return indexed_count

        except Exception as e:
            log_stderr(f"[ERROR] {doc_type.upper()} индексация {file_path}: {e}")
            import traceback
            log_stderr(traceback.format_exc())
            return 0

    def _build_js_summary(self, content: str, path: Path, analysis: Dict[str, Any]) -> str:
        """Строит summary для JavaScript/TypeScript файла"""
        summary_parts = [f"# {path.name}\n"]

        # Основная информация
        doc_type = 'TypeScript' if path.suffix.lower() in ['.ts', '.tsx'] else 'JavaScript'
        summary_parts.append(f"**Тип:** {doc_type}\n")
        summary_parts.append(f"**Строк:** {analysis['lines']}\n")
        summary_parts.append(f"**Сложность:** {analysis['complexity_level']} ({analysis['complexity']})\n")

        # Функции
        if analysis['functions']:
            summary_parts.append(f"\n## Функции ({len(analysis['functions'])})\n")
            func_by_type = {}
            for func in analysis['functions']:
                ftype = func['type']
                if ftype not in func_by_type:
                    func_by_type[ftype] = []
                func_by_type[ftype].append(func['name'])

            for ftype, funcs in func_by_type.items():
                summary_parts.append(f"- **{ftype}** ({len(funcs)}): {', '.join(funcs[:10])}")
                if len(funcs) > 10:
                    summary_parts.append(f"  ... и ещё {len(funcs) - 10}")

        # Классы
        if analysis['classes']:
            summary_parts.append(f"\n## Классы ({len(analysis['classes'])})\n")
            for cls in analysis['classes']:
                cls_info = f"- **{cls['name']}**"
                if cls.get('parent'):
                    cls_info += f" extends {cls['parent']}"
                summary_parts.append(cls_info)

        # Экспорты
        if analysis['exports']:
            summary_parts.append(f"\n## Экспорты ({len(analysis['exports'])})\n")
            for exp in analysis['exports']:
                summary_parts.append(f"- **{exp['type']}**: {exp['name']}")

        # Импорты
        if analysis['imports']:
            summary_parts.append(f"\n## Импорты ({len(analysis['imports'])})\n")
            for imp in analysis['imports'][:10]:
                summary_parts.append(f"- `{imp}`")
            if len(analysis['imports']) > 10:
                summary_parts.append(f"- ... и ещё {len(analysis['imports']) - 10}")

        summary_parts.append(f"\n---\n## Исходный код\n")

        return "\n".join(summary_parts)

    def index_bsl_project(self, project_path: str, chunk_mode: str = "smart") -> Dict[str, int]:
        """
        Индексация всего BSL проекта (конфигурации 1С)

        Args:
            project_path: Путь к проекту (папка с src/)
            chunk_mode: Режим разбиения ("full", "procedures", "smart")

        Returns:
            Статистика: {files, documents, errors}
        """
        project_root = Path(project_path)
        if not project_root.exists():
            log_stderr(f"[ERROR] Проект не найден: {project_path}")
            return {"files": 0, "documents": 0, "errors": 1}

        log_stderr(f"[BSL] Индексация проекта: {project_root}")
        stats = {"files": 0, "documents": 0, "errors": 0}

        # Ищем все .bsl файлы
        bsl_files = list(project_root.rglob("*.bsl"))
        log_stderr(f"[INFO] Найдено BSL файлов: {len(bsl_files)}")

        for bsl_file in bsl_files:
            try:
                docs_count = self.index_bsl_file(str(bsl_file), chunk_mode)
                if docs_count > 0:
                    stats["files"] += 1
                    stats["documents"] += docs_count
            except Exception as e:
                stats["errors"] += 1
                log_stderr(f"[ERROR] {bsl_file.name}: {e}")

        log_stderr(f"[OK] BSL проект проиндексирован: {stats['files']} файлов, {stats['documents']} документов")
        return stats

    # ============================================================================
    # ИНДЕКСАЦИЯ XML ФАЙЛОВ 1C EDT
    # ============================================================================

    def index_xml_file(self, file_path: str) -> int:
        """
        Индексация XML файла 1C EDT с извлечением структурированных данных

        Args:
            file_path: Путь к .xml файлу

        Returns:
            Количество проиндексированных документов (обычно 1)
        """
        try:
            from edt_xml_parser import EDTXMLParser
        except ImportError:
            log_stderr("[ERROR] edt_xml_parser не найден. Убедитесь что модуль в том же каталоге.")
            return 0

        try:
            path = Path(file_path)
            if not path.exists():
                log_stderr(f"[WARNING] Файл не существует: {file_path}")
                return 0

            parser = EDTXMLParser()
            rag_data = parser.extract_for_rag(str(path))

            if not rag_data or not rag_data.get('content'):
                log_stderr(f"[SKIP] Нет данных для RAG: {path.name}")
                return 0

            # Создаём документ для индексации
            doc_id = f"xml:{hashlib.md5(str(path).encode()).hexdigest()[:12]}"

            # Вычисляем размер контента и хеш
            content = rag_data.get('content', '')
            content_hash = self._get_content_hash(content)

            doc = Document(
                id=doc_id,
                title=rag_data.get('title', path.stem),
                content=content,
                content_preview=content[:500] + "..." if len(content) > 500 else content,
                path=str(path),
                size=len(content),
                modified=datetime.fromtimestamp(path.stat().st_mtime).isoformat(),
                doc_type=rag_data.get('doc_type', 'xml'),
                tags=rag_data.get('tags', [])
            )

            # Сохраняем в базу
            self._save_document(doc, content_hash)

            # Генерируем эмбеддинги если доступны
            if self.embedding_model:
                self._generate_embedding(doc)

            log_stderr(f"[OK] Проиндексирован XML: {path.name}")
            return 1

        except Exception as e:
            log_stderr(f"[ERROR] XML индексация {file_path}: {e}")
            import traceback
            log_stderr(traceback.format_exc())
            return 0

    def index_xml_project(self, project_path: str, xml_types: List[str] = None) -> Dict[str, int]:
        """
        Индексация всех XML файлов проекта 1C EDT

        Args:
            project_path: Путь к проекту (папка src/)
            xml_types: Список типов XML для индексации (по умолчанию все)
                       Варианты: ['subsystems', 'forms', 'rights', 'languages', 'metadata']

        Returns:
            Словарь со статистикой: {files, documents, errors, by_type}
        """
        project_root = Path(project_path)
        if not project_root.exists():
            log_stderr(f"[ERROR] Путь не существует: {project_path}")
            return {"files": 0, "documents": 0, "errors": 1}

        log_stderr(f"[START] Индексация XML проекта: {project_path}")

        stats = {
            "files": 0,
            "documents": 0,
            "errors": 0,
            "by_type": {
                "subsystem": 0,
                "form": 0,
                "rights": 0,
                "language": 0,
                "metadata": 0,
                "command_interface": 0,
            }
        }

        # Шаблоны для разных типов XML
        xml_patterns = {
            "subsystems": "Subsystems/**/*.xml",
            "forms": "**/Forms/*/Ext/Form.xml",
            "rights": "**/Ext/Rights.xml",
            "languages": "Languages/*.xml",
            "command_interface": "**/CommandInterface.xml",
            "metadata": "*.xml",  # Корневые файлы
        }

        # Если не указаны типы, индексируем приоритетные
        if xml_types is None:
            xml_types = ["subsystems", "forms", "languages"]

        try:
            from edt_xml_parser import EDTXMLParser
            parser = EDTXMLParser()
        except ImportError:
            log_stderr("[ERROR] edt_xml_parser не найден")
            return {"files": 0, "documents": 0, "errors": 1}

        # Собираем все XML файлы по паттернам
        xml_files = set()
        for xml_type in xml_types:
            pattern = xml_patterns.get(xml_type, "**/*.xml")
            for xml_file in project_root.glob(pattern):
                if xml_file.is_file() and xml_file.suffix.lower() == '.xml':
                    xml_files.add(xml_file)

        log_stderr(f"[INFO] Найдено XML файлов для индексации: {len(xml_files)}")

        for xml_file in xml_files:
            try:
                rag_data = parser.extract_for_rag(str(xml_file))
                if not rag_data or not rag_data.get('content'):
                    continue

                doc_type = rag_data.get('doc_type', 'xml')
                # Извлекаем тип из doc_type (например, 'xml-subsystem' -> 'subsystem')
                type_key = doc_type.replace('xml-', '').replace('xml', 'metadata')
                if type_key in stats["by_type"]:
                    stats["by_type"][type_key] += 1

                doc_id = f"xml:{hashlib.md5(str(xml_file).encode()).hexdigest()[:12]}"
                # Вычисляем размер контента и хеш
                content = rag_data.get('content', '')
                content_hash = self._get_content_hash(content)

                doc = Document(
                    id=doc_id,
                    title=rag_data.get('title', xml_file.stem),
                    content=content,
                    content_preview=content[:500] + "..." if len(content) > 500 else content,
                    path=str(xml_file),
                    size=len(content),
                    modified=datetime.fromtimestamp(xml_file.stat().st_mtime).isoformat(),
                    doc_type=doc_type,
                    tags=rag_data.get('tags', [])
                )

                # Сохраняем в базу
                self._save_document(doc, content_hash)

                # Генерируем эмбеддинги если доступны
                if self.embedding_model:
                    self._generate_embedding(doc)

                stats["files"] += 1
                stats["documents"] += 1

            except Exception as e:
                stats["errors"] += 1
                log_stderr(f"[ERROR] {xml_file.name}: {e}")

        log_stderr(f"[OK] XML проект проиндексирован: {stats['files']} файлов, {stats['documents']} документов")
        log_stderr(f"[STATS] По типам: {stats['by_type']}")
        return stats

    # ============================================================================
    # ИНКРЕМЕНТАЛЬНАЯ ИНДЕКСАЦИЯ
    # ============================================================================

    def _update_index_metadata(self, docs_path: str, files_indexed: int):
        """Обновление метаданных индексации"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # Получаем текущие метаданные
        cursor.execute("SELECT indexed_paths FROM index_metadata WHERE id = 1")
        result = cursor.fetchone()
        indexed_paths = json.loads(result[0]) if result and result[0] else []

        # Добавляем новый путь если нет
        if docs_path not in indexed_paths:
            indexed_paths.append(docs_path)

        # Обновляем
        now = datetime.now().isoformat()
        cursor.execute("""
            UPDATE index_metadata
            SET last_index_time = ?,
                last_full_scan_time = ?,
                total_files_indexed = total_files_indexed + ?,
                indexed_paths = ?
            WHERE id = 1
        """, (now, now, files_indexed, json.dumps(indexed_paths)))

        conn.commit()
        conn.close()

    def index_directory_incremental(self, docs_path: str, doc_type: str = "markdown") -> Dict[str, int]:
        """
        Инкрементальная индексация директории

        Индексирует только:
        - Новые файлы (ещё не в индексе)
        - Изменённые файлы (по content_hash)
        - Удаляет из индекса удалённые файлы

        Args:
            docs_path: Путь к директории с документацией
            doc_type: Тип документа (markdown, bsl, etc.)

        Returns:
            Словарь со статистикой: {new, modified, deleted, skipped}
        """
        docs_root = Path(docs_path)
        if not docs_root.exists():
            self.logger.error(f"Путь не существует: {docs_path}")
            return {"new": 0, "modified": 0, "deleted": 0, "skipped": 0, "error": "path_not_found"}

        self.logger.info(f"🔄 Инкрементальная индексация: {docs_path}")

        stats = {"new": 0, "modified": 0, "deleted": 0, "skipped": 0}

        # Получаем список всех файлов в файловой системе
        fs_files = set(str(p) for p in docs_root.rglob("*.md") if p.is_file())

        # Получаем список файлов в индексе для этого пути
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT path, content_hash FROM documents WHERE path LIKE ?", (f"{docs_path}%",))
        indexed_files = dict(cursor.fetchall())
        conn.close()

        indexed_paths = set(indexed_files.keys())

        # 1. Удалённые файлы (есть в индексе, но нет в файловой системе)
        deleted_files = indexed_paths - fs_files
        for file_path in deleted_files:
            if self.delete_document(file_path):
                stats["deleted"] += 1

        # 2. Новые и изменённые файлы
        for file_path in fs_files:
            try:
                content, _ = read_file_with_fallback(file_path)
                content_hash = self._get_content_hash(content)
                doc_id = self._generate_doc_id(file_path)

                # Проверяем статус файла
                if file_path not in indexed_files:
                    # Новый файл
                    if self.index_document(file_path, doc_type):
                        stats["new"] += 1
                elif indexed_files[file_path] != content_hash:
                    # Изменённый файл
                    if self.index_document(file_path, doc_type):
                        stats["modified"] += 1
                else:
                    # Актуальный файл
                    stats["skipped"] += 1

            except Exception as e:
                self.logger.error(f"Ошибка обработки {file_path}: {e}")

        # Обновляем метаданные
        self._update_index_metadata(docs_path, stats["new"] + stats["modified"])

        self.logger.info(f"✅ Инкрементальная индексация завершена: "
                       f"+{stats['new']}, ~{stats['modified']}, -{stats['deleted']}, ⏭{stats['skipped']}")

        return stats

    # ============================================================================
    # ФАСЕТНЫЙ ПОИСК
    # ============================================================================

    def search_with_facets(
        self,
        query: str,
        limit: int = 10,
        search_type: str = "hybrid",
        doc_type: Optional[str] = None,
        tags: Optional[List[str]] = None,
        date_after: Optional[str] = None,
        date_before: Optional[str] = None,
        source: Optional[str] = None
    ) -> List[SearchResult]:
        """
        Поиск с фасетной фильтрацией

        Args:
            query: Поисковый запрос
            limit: Максимальное количество результатов
            search_type: Тип поиска ('fulltext', 'semantic', 'hybrid')
            doc_type: Фильтр по типу документа (markdown, bsl, xml)
            tags: Фильтр по тегам (OR логика - хоть один тег совпал)
            date_after: Фильтр по дате (ISO format, например "2025-01-01")
            date_before: Фильтр по дате (ISO format)
            source: Фильтр по источнику (часть пути, например "claude", "framework")

        Returns:
            Список результатов поиска с применёнными фильтрами
        """
        # Сначала обычный поиск
        results = self.search(query, limit=limit * 3, search_type=search_type)

        # Применяем фасетные фильтры
        filtered_results = []
        for result in results:
            doc = result.document

            # Фильтр по doc_type
            if doc_type and doc.doc_type != doc_type:
                continue

            # Фильтр по тегам (OR - хотя бы один совпал)
            if tags:
                if not any(tag in doc.tags for tag in tags):
                    continue

            # Фильтр по дате (after)
            if date_after:
                try:
                    doc_date = datetime.fromisoformat(doc.modified)
                    filter_date = datetime.fromisoformat(date_after)
                    if doc_date < filter_date:
                        continue
                except ValueError:
                    pass

            # Фильтр по дате (before)
            if date_before:
                try:
                    doc_date = datetime.fromisoformat(doc.modified)
                    filter_date = datetime.fromisoformat(date_before)
                    if doc_date > filter_date:
                        continue
                except ValueError:
                    pass

            # Фильтр по источнику (части пути)
            if source:
                if source.lower() not in doc.path.lower():
                    continue

            filtered_results.append(result)

        self.logger.info(f"Найдено {len(filtered_results)} результатов после фасетной фильтрации")

        return filtered_results[:limit]

    def get_available_facets(self) -> Dict[str, Any]:
        """
        Получение доступных значений фасетов

        Returns:
            Словарь с доступными значениями для фильтрации:
            - doc_types: Список типов документов
            - tags: Список всех тегов с количеством
            - sources: Список источников (папок)
            - date_range: Минимальная и максимальная дата
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Типы документов
        cursor.execute("SELECT doc_type, COUNT(*) FROM documents GROUP BY doc_type")
        doc_types = dict(cursor.fetchall())

        # Теги с количеством
        cursor.execute("""
            SELECT tags.value, COUNT(*)
            FROM documents, json_each(documents.tags) AS tags
            GROUP BY tags.value
            ORDER BY COUNT(*) DESC
        """)
        tags = dict(cursor.fetchall())

        # Источники (верхние уровни пути)
        cursor.execute("SELECT DISTINCT path FROM documents")
        sources = set()
        for (path,) in cursor.fetchall():
            # Извлекаем компоненты пути
            parts = Path(path).parts
            if len(parts) >= 2:
                # Берём папку сразу после docs/
                for part in parts:
                    if part in ['claude', 'framework', '1C Developer Documentation', 'for-users', 'for-claude', 'anthropic-docs']:
                        sources.add(part)
                        break

        # Диапазон дат
        cursor.execute("SELECT MIN(modified), MAX(modified) FROM documents")
        min_date, max_date = cursor.fetchone()

        conn.close()

        return {
            "doc_types": doc_types,
            "tags": tags,
            "sources": sorted(list(sources)),
            "date_range": {
                "min": min_date,
                "max": max_date
            }
        }


class DocsFileWatcher:
    """
    Мониторинг файловой системы для автоматической индексации

    Отслеживает:
    - Добавление новых .md файлов
    - Изменение существующих .md файлов
    - Удаление .md файлов
    """

    def __init__(self, search_engine: HybridSearchEngine, docs_path: str,
                 debounce_seconds: float = 1.0):
        """
        Инициализация файлового наблюдателя

        Args:
            search_engine: Экземпляр HybridSearchEngine
            docs_path: Путь к папке с документацией
            debounce_seconds: Задержка для предотвращения множественных событий
        """
        if not WATCHDOG_AVAILABLE:
            raise RuntimeError("watchdog не установлен. Установите: pip install watchdog")

        self.search_engine = search_engine
        self.docs_path = Path(docs_path)
        self.debounce_seconds = debounce_seconds
        self.observer = None
        self._running = False
        self._lock = threading.Lock()
        self._pending_events = {}  # path -> (event_type, timestamp)
        self._debounce_thread = None

        self.logger = logging.getLogger(__name__ + ".FileWatcher")
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('[FileWatcher] %(asctime)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)

    def _is_markdown_file(self, path: str) -> bool:
        """Проверка что файл является markdown"""
        return path.lower().endswith(('.md', '.markdown'))

    def _handle_event(self, event_type: str, file_path: str):
        """Обработка события файловой системы с debounce"""
        if not self._is_markdown_file(file_path):
            return

        with self._lock:
            self._pending_events[file_path] = (event_type, time.time())

    def _debounce_processor(self):
        """Фоновый поток для обработки событий с задержкой"""
        while self._running:
            time.sleep(0.5)  # Проверяем каждые 500ms

            events_to_process = []
            current_time = time.time()

            with self._lock:
                for path, (event_type, timestamp) in list(self._pending_events.items()):
                    if current_time - timestamp >= self.debounce_seconds:
                        events_to_process.append((path, event_type))
                        del self._pending_events[path]

            for path, event_type in events_to_process:
                try:
                    if event_type == "deleted":
                        self.logger.info(f"🗑️ Файл удалён: {Path(path).name}")
                        self.search_engine.delete_document(path)
                    else:
                        # created или modified
                        self.logger.info(f"📝 Файл {'создан' if event_type == 'created' else 'изменён'}: {Path(path).name}")
                        self.search_engine.index_document(path)
                except Exception as e:
                    self.logger.error(f"Ошибка обработки события {event_type} для {path}: {e}")

    def start(self):
        """Запуск мониторинга"""
        if self._running:
            self.logger.warning("FileWatcher уже запущен")
            return

        if not self.docs_path.exists():
            raise ValueError(f"Путь к документации не существует: {self.docs_path}")

        # Создаём обработчик событий
        class DocsEventHandler(FileSystemEventHandler):
            def __init__(handler_self, watcher):
                handler_self.watcher = watcher

            def on_created(handler_self, event):
                if not event.is_directory:
                    handler_self.watcher._handle_event("created", event.src_path)

            def on_modified(handler_self, event):
                if not event.is_directory:
                    handler_self.watcher._handle_event("modified", event.src_path)

            def on_deleted(handler_self, event):
                if not event.is_directory:
                    handler_self.watcher._handle_event("deleted", event.src_path)

            def on_moved(handler_self, event):
                if not event.is_directory:
                    # При перемещении: удаляем старый, добавляем новый
                    handler_self.watcher._handle_event("deleted", event.src_path)
                    handler_self.watcher._handle_event("created", event.dest_path)

        self.observer = Observer()
        self.observer.schedule(
            DocsEventHandler(self),
            str(self.docs_path),
            recursive=True
        )

        self._running = True
        self.observer.start()

        # Запускаем debounce поток
        self._debounce_thread = threading.Thread(target=self._debounce_processor, daemon=True)
        self._debounce_thread.start()

        self.logger.info(f"👁️ FileWatcher запущен для: {self.docs_path}")

    def stop(self):
        """Остановка мониторинга"""
        if not self._running:
            return

        self._running = False

        if self.observer:
            self.observer.stop()
            self.observer.join(timeout=5)
            self.observer = None

        self.logger.info("👁️ FileWatcher остановлен")

    def get_status(self) -> Dict[str, Any]:
        """Получение статуса наблюдателя"""
        return {
            "running": self._running,
            "docs_path": str(self.docs_path),
            "debounce_seconds": self.debounce_seconds,
            "pending_events": len(self._pending_events),
            "watchdog_available": WATCHDOG_AVAILABLE
        }


def main():
    """Демонстрация работы поискового движка"""
    log_stderr("🚀 Демонстрация гибридного поискового движка")
    log_stderr("=" * 60)

    # Инициализация
    engine = HybridSearchEngine()

    # Индексация документации фреймворка
    docs_path = Path("Документация по фреймворку")

    if docs_path.exists():
        log_stderr(f"📚 Индексация документов из {docs_path}")

        for md_file in docs_path.rglob("*.md"):
            engine.index_document(str(md_file))

    # Статистика
    stats = engine.get_statistics()
    log_stderr(f"\n[STATS] Статистика индекса:")
    log_stderr(f"   Документов: {stats['total_documents']}")
    log_stderr(f"   С эмбеддингами: {stats['documents_with_embeddings']}")
    log_stderr(f"   Размер: {stats['total_size_mb']} MB")
    log_stderr(f"   Эмбеддинги: {'[OK]' if stats['embeddings_enabled'] else '[NO]'}")

    # Тестовые запросы
    test_queries = [
        "Task Master",
        "BSL анализ качества",
        "MCP сервер",
        "интеграция Claude"
    ]

    for query in test_queries:
        log_stderr(f"\n[SEARCH] Поиск: '{query}'")
        results = engine.search(query, limit=3)

        for i, result in enumerate(results, 1):
            log_stderr(f"  {i}. {result.document.title}")
            log_stderr(f"     Релевантность: {result.score:.3f} ({result.match_type})")
            log_stderr(f"     Файл: {Path(result.document.path).name}")


if __name__ == "__main__":
    main()