"""
Embedding Service для BSL Semantic Search

Генерация embeddings через Ollama (nomic-embed-text)

Phase 45: Миграция из 1C-Enterprise_Framework
"""

import logging
import os
import shutil
import subprocess
import time
from typing import List, Optional

import httpx

logger = logging.getLogger(__name__)

_OLLAMA_KNOWN_PATHS = [
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Ollama\ollama.exe"),
]


def _find_ollama() -> Optional[str]:
    path = shutil.which("ollama")
    if path:
        return path
    for p in _OLLAMA_KNOWN_PATHS:
        if os.path.isfile(p):
            return p
    return None


def _is_ollama_running(host: str) -> bool:
    try:
        resp = httpx.get(f"{host}/api/tags", timeout=3.0)
        return resp.status_code == 200
    except Exception:
        return False


def _ensure_ollama(host: str, max_wait: int = 30) -> bool:
    """Запустить Ollama если не запущена. Возвращает True если доступна."""
    if _is_ollama_running(host):
        return True

    exe = _find_ollama()
    if not exe:
        logger.error("Ollama не найдена. Установите: https://ollama.com/download")
        return False

    logger.info(f"Ollama не запущена, запускаю: {exe} serve")
    try:
        subprocess.Popen(
            [exe, "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "DETACHED_PROCESS", 0)
            | getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception as e:
        logger.error(f"Не удалось запустить Ollama: {e}")
        return False

    for i in range(max_wait):
        time.sleep(1)
        if _is_ollama_running(host):
            logger.info(f"Ollama запущена (ожидание {i + 1}с)")
            return True

    logger.error(f"Ollama не отвечает после {max_wait}с ожидания")
    return False


class EmbeddingService:
    """
    Сервис генерации embeddings через Ollama

    Использует nomic-embed-text модель (768d)
    """

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        model: str = "nomic-embed-text"
    ):
        """
        Инициализация Embedding Service

        Args:
            ollama_host: URL Ollama сервера
            model: Модель для генерации embeddings
        """
        self.ollama_host = ollama_host
        self.model = model
        self.client = httpx.Client(timeout=60.0)
        self._ollama_checked = False

        logger.info(f"EmbeddingService инициализирован: {ollama_host}, model={model}")

    def create_embedding(self, text: str) -> Optional[List[float]]:
        """
        Создание embedding для текста

        Args:
            text: Текст для векторизации

        Returns:
            Список float значений (768d) или None при ошибке
        """
        if not text or not text.strip():
            logger.warning("Пустой текст для embedding")
            return None

        try:
            url = f"{self.ollama_host}/api/embeddings"
            payload = {
                "model": self.model,
                "prompt": text[:8000]  # Ограничение длины
            }

            response = self.client.post(url, json=payload)
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding", [])

            if embedding:
                logger.debug(f"Embedding создан: {len(embedding)}d")
                return embedding

            logger.error("Ollama вернул пустой embedding")
            return None

        except httpx.HTTPError as e:
            logger.error(f"HTTP ошибка при создании embedding: {e}")
            return None
        except Exception as e:
            logger.error(f"Ошибка создания embedding: {e}")
            return None

    def create_embeddings_batch(
        self,
        texts: List[str],
        batch_size: int = 10
    ) -> List[Optional[List[float]]]:
        """
        Пакетное создание embeddings

        Args:
            texts: Список текстов
            batch_size: Размер пакета

        Returns:
            Список embeddings (или None для неудачных)
        """
        results = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            batch_results = []

            for text in batch:
                embedding = self.create_embedding(text)
                batch_results.append(embedding)

            results.extend(batch_results)
            logger.debug(f"Обработан batch {i//batch_size + 1}: {len(batch_results)} embeddings")

        return results

    def __del__(self):
        """Закрытие HTTP клиента"""
        if hasattr(self, 'client'):
            self.client.close()
