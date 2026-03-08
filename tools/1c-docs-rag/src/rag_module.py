"""
RAG Module для 1C Framework Docs
================================

Retrieval-Augmented Generation модуль для генерации ответов на основе документации.
Использует z.ai proxy (glm-4.6) по умолчанию для генерации.

Использование:
    from rag_module import RAGModule

    rag = RAGModule(search_engine)
    answer = await rag.ask("Как настроить MCP сервер?")

LangSmith Tracing:
    export LANGSMITH_TRACING=true
    export LANGSMITH_API_KEY=your-key
    export LANGSMITH_PROJECT=1c-enterprise-framework
"""

import asyncio
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, AsyncIterator
from dataclasses import dataclass
from datetime import datetime, timedelta

# LangSmith tracing (optional)
try:
    from langsmith_tracing import TraceContext, log_metric
    LANGSMITH_ENABLED = True
except ImportError:
    LANGSMITH_ENABLED = False
    TraceContext = None
    log_metric = None

import aiohttp

def log_stderr(*args, **kwargs):
    """Логирование в stderr (НЕ в stdout - там MCP протокол!)"""
    print(*args, file=sys.stderr, **kwargs)

logger = logging.getLogger(__name__)

# Путь к LLM HTTP серверу (z.ai proxy по умолчанию)
LLM_ROTATION_HTTP_SCRIPT = os.getenv(
    "LLM_ROTATION_HTTP_SCRIPT",
    ""  # LLM Rotation migrated as MCP service, no local proxy needed
)

# Конфигурация
LLM_ROTATION_URL = os.getenv("LLM_ROTATION_URL", "http://localhost:8000")
CACHE_TTL_HOURS = int(os.getenv("RAG_CACHE_TTL_HOURS", "24"))
MAX_CONTEXT_LENGTH = int(os.getenv("RAG_MAX_CONTEXT_LENGTH", "8000"))
TOP_K_DOCUMENTS = int(os.getenv("RAG_TOP_K_DOCUMENTS", "5"))


@dataclass
class RAGResponse:
    """Структура ответа RAG"""
    answer: str
    sources: List[Dict[str, Any]]
    query: str
    model_used: str
    cached: bool
    generation_time: float
    total_tokens: int


class RAGCache:
    """Простой файловый кеш для RAG ответов"""

    def __init__(self, cache_dir: Optional[str] = None):
        self.cache_dir = Path(cache_dir or "cache/rag")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=CACHE_TTL_HOURS)

    def _get_cache_key(self, query: str) -> str:
        """Генерация ключа кеша"""
        normalized = query.lower().strip()
        return hashlib.md5(normalized.encode()).hexdigest()

    def _get_cache_path(self, key: str) -> Path:
        """Путь к файлу кеша"""
        return self.cache_dir / f"{key}.json"

    def get(self, query: str) -> Optional[RAGResponse]:
        """Получить из кеша"""
        key = self._get_cache_key(query)
        cache_file = self._get_cache_path(key)

        if not cache_file.exists():
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Проверяем TTL
            cached_at = datetime.fromisoformat(data.get('cached_at', ''))
            if datetime.now() - cached_at > self.ttl:
                cache_file.unlink()  # Удаляем устаревший кеш
                return None

            return RAGResponse(
                answer=data['answer'],
                sources=data['sources'],
                query=data['query'],
                model_used=data['model_used'],
                cached=True,
                generation_time=0.0,
                total_tokens=data.get('total_tokens', 0)
            )
        except Exception as e:
            logger.warning(f"Ошибка чтения кеша: {e}")
            return None

    def set(self, response: RAGResponse) -> None:
        """Сохранить в кеш"""
        key = self._get_cache_key(response.query)
        cache_file = self._get_cache_path(key)

        try:
            data = {
                'answer': response.answer,
                'sources': response.sources,
                'query': response.query,
                'model_used': response.model_used,
                'total_tokens': response.total_tokens,
                'cached_at': datetime.now().isoformat()
            }
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.warning(f"Ошибка записи в кеш: {e}")

    def clear(self) -> int:
        """Очистить кеш"""
        count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_file.unlink()
            count += 1
        return count


class RAGModule:
    """RAG модуль для генерации ответов на основе документации"""

    _llm_http_process: Optional[subprocess.Popen] = None  # Класс-переменная для процесса

    def __init__(self, search_engine, cache_dir: Optional[str] = None):
        """
        Инициализация RAG модуля

        Args:
            search_engine: HybridSearchEngine для поиска документов
            cache_dir: Директория для кеша (опционально)
        """
        self.search_engine = search_engine
        self.cache = RAGCache(cache_dir)
        self.llm_url = LLM_ROTATION_URL
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать HTTP сессию"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=120)
            )
        return self._session

    async def _ensure_llm_http_running(self) -> bool:
        """
        Проверить и при необходимости запустить LLM Rotation HTTP сервер.

        Returns:
            True если сервер доступен, False если не удалось запустить
        """
        logger.info("RAG: Проверка доступности LLM HTTP сервера...")

        # Проверяем доступность сервера
        try:
            session = await self._get_session()
            async with session.get(f"{self.llm_url}/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass  # Сервер недоступен, попробуем запустить

        # Проверяем существование скрипта
        script_path = Path(LLM_ROTATION_HTTP_SCRIPT)
        if not script_path.exists():
            logger.error(f"LLM Rotation HTTP скрипт не найден: {script_path}")
            return False

        # Запускаем сервер в фоновом режиме
        logger.info(f"Запуск LLM Rotation HTTP сервера: {script_path}")
        try:
            # Определяем Python интерпретатор
            python_exe = sys.executable

            # Лог-файл для отладки
            log_file = Path(script_path).parent.parent / "cache" / "llm_http_autostart.log"
            log_file.parent.mkdir(parents=True, exist_ok=True)
            log_handle = open(log_file, "w", encoding="utf-8")

            # Запускаем процесс
            if sys.platform == "win32":
                # Windows: CREATE_NEW_PROCESS_GROUP без DETACHED для надёжности
                RAGModule._llm_http_process = subprocess.Popen(
                    [python_exe, str(script_path), "--port", "8000"],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
                )
            else:
                # Linux/Mac
                RAGModule._llm_http_process = subprocess.Popen(
                    [python_exe, str(script_path), "--port", "8000"],
                    stdout=log_handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True
                )

            logger.info(f"LLM Rotation HTTP запущен с PID: {RAGModule._llm_http_process.pid}")

            # Ждём пока сервер станет доступен (до 10 секунд)
            for attempt in range(20):
                await asyncio.sleep(0.5)
                try:
                    async with session.get(f"{self.llm_url}/health", timeout=aiohttp.ClientTimeout(total=2)) as resp:
                        if resp.status == 200:
                            logger.info("LLM Rotation HTTP сервер готов к работе")
                            return True
                except Exception:
                    continue

            logger.warning("LLM Rotation HTTP сервер запущен, но не отвечает")
            return False

        except Exception as e:
            logger.error(f"Ошибка запуска LLM Rotation HTTP: {e}")
            return False

    async def close(self):
        """Закрыть HTTP сессию"""
        if self._session and not self._session.closed:
            await self._session.close()

    def _build_context(self, results: List[Any]) -> str:
        """
        Построить контекст из результатов поиска

        Args:
            results: Результаты поиска документов

        Returns:
            Форматированный контекст для LLM
        """
        context_parts = []
        total_length = 0

        for i, result in enumerate(results, 1):
            doc = result.document
            # Используем сниппет или обрезаем контент
            content = result.snippet if len(result.snippet) > 200 else doc.content[:2000]

            section = f"""
### Документ {i}: {doc.title}
**Источник:** {doc.path}
**Релевантность:** {result.score:.2f}

{content}
"""
            section_length = len(section)

            if total_length + section_length > MAX_CONTEXT_LENGTH:
                break

            context_parts.append(section)
            total_length += section_length

        return "\n---\n".join(context_parts)

    def _build_prompt(self, query: str, context: str) -> str:
        """
        Построить промпт для LLM

        Args:
            query: Вопрос пользователя
            context: Контекст из документов

        Returns:
            Полный промпт для LLM
        """
        return f"""Ты эксперт по 1C:Enterprise Framework. Ответь на вопрос пользователя, используя ТОЛЬКО информацию из предоставленного контекста документации.

## Контекст из документации:
{context}

## Вопрос пользователя:
{query}

## Инструкции:
1. Отвечай ТОЛЬКО на основе информации из контекста
2. Если информации недостаточно, честно скажи об этом
3. Используй конкретные примеры из документации
4. Форматируй ответ с markdown (заголовки, списки, код)
5. В конце укажи источники информации

## Ответ:"""

    async def _call_llm(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """
        Вызов LLM через Rotation API

        Args:
            prompt: Промпт для LLM
            system_prompt: Системный промпт (опционально)

        Returns:
            Ответ от LLM API
        """
        session = await self._get_session()

        payload = {
            "model": "auto",  # LLM Rotation выберет лучший провайдер
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.3  # Более детерминированные ответы для RAG
        }

        if system_prompt:
            payload["messages"].insert(0, {
                "role": "system",
                "content": system_prompt
            })

        try:
            async with session.post(
                f"{self.llm_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LLM API error {response.status}: {error_text}")

                return await response.json()
        except aiohttp.ClientError as e:
            raise Exception(f"Ошибка подключения к LLM Rotation: {e}")

    async def _call_llm_stream(self, prompt: str, system_prompt: Optional[str] = None) -> AsyncIterator[str]:
        """
        Вызов LLM через Rotation API со streaming

        Args:
            prompt: Промпт для LLM
            system_prompt: Системный промпт (опционально)

        Yields:
            Текстовые токены по мере генерации
        """
        session = await self._get_session()

        payload = {
            "model": "auto",  # LLM Rotation выберет лучший провайдер
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 2000,
            "temperature": 0.3,  # Более детерминированные ответы для RAG
            "stream": True  # ENABLE STREAMING
        }

        if system_prompt:
            payload["messages"].insert(0, {
                "role": "system",
                "content": system_prompt
            })

        try:
            async with session.post(
                f"{self.llm_url}/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"}
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"LLM API error {response.status}: {error_text}")

                # Читаем SSE поток
                async for line in response.content:
                    line_str = line.decode('utf-8').strip()

                    # SSE format: "data: {...}\n\n"
                    if not line_str or not line_str.startswith('data:'):
                        continue

                    data_str = line_str[5:].strip()
                    if data_str == '[DONE]':
                        break

                    try:
                        chunk = json.loads(data_str)
                        # OpenAI streaming format: choices[0].delta.content
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            yield content
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue

        except aiohttp.ClientError as e:
            raise Exception(f"Ошибка подключения к LLM Rotation (stream): {e}")

    async def ask(
        self,
        query: str,
        use_cache: bool = True,
        search_type: str = "hybrid",
        top_k: int = TOP_K_DOCUMENTS,
        source_filter: Optional[str] = None
    ) -> RAGResponse:
        """
        Ответить на вопрос используя RAG

        Args:
            query: Вопрос пользователя
            use_cache: Использовать кеш
            search_type: Тип поиска (fulltext, semantic, hybrid)
            top_k: Количество документов для контекста
            source_filter: Фильтр по источнику (путь к документации)

        Returns:
            RAGResponse с ответом и метаданными
        """
        start_time = time.time()

        # Проверяем кеш
        if use_cache and not source_filter:  # Не используем кеш при фильтрации
            cached = self.cache.get(query)
            if cached:
                logger.info(f"RAG: кеш-попадание для '{query[:50]}...'")
                # Логируем метрику кеш-попадания
                if log_metric:
                    log_metric("rag_cache_hit", 1)
                return cached

        # Поиск релевантных документов
        logger.info(f"RAG: поиск документов для '{query[:50]}...'")
        search_start = time.time()
        results = self.search_engine.search(query, limit=top_k * 2, search_type=search_type)  # Ищем больше для фильтрации
        search_time = time.time() - search_start

        # Логируем метрики поиска
        if log_metric:
            log_metric("rag_search_time_ms", int(search_time * 1000), {"query_length": len(query)})
            log_metric("rag_results_count", len(results))

        # Фильтрация по источнику если указан
        if source_filter:
            results = [r for r in results if source_filter.lower() in r.document.path.lower()]
            logger.info(f"RAG: отфильтровано {len(results)} документов по '{source_filter}'")

        # Enforce top_k limit after filtering
        results = results[:top_k]

        if not results:
            filter_msg = f" (фильтр: {source_filter})" if source_filter else ""
            if log_metric:
                log_metric("rag_no_results", 1)
            return RAGResponse(
                answer=f"К сожалению, по вашему запросу не найдено релевантной документации.{filter_msg}",
                sources=[],
                query=query,
                model_used="none",
                cached=False,
                generation_time=time.time() - start_time,
                total_tokens=0
            )

        # Построить контекст и промпт
        context = self._build_context(results)
        prompt = self._build_prompt(query, context)

        # Убеждаемся что LLM HTTP сервер запущен
        llm_available = await self._ensure_llm_http_running()
        if not llm_available:
            logger.warning("RAG: LLM HTTP сервер недоступен, используем fallback")
            # Fallback: вернуть только результаты поиска
            fallback_answer = "**Не удалось запустить LLM сервер.**\n\n"
            fallback_answer += "Найденные документы:\n\n"
            for r in results:
                fallback_answer += f"- **{r.document.title}** ({r.score:.2f}): {r.snippet[:200]}...\n"

            return RAGResponse(
                answer=fallback_answer,
                sources=[{"title": r.document.title, "path": r.document.path, "score": r.score} for r in results],
                query=query,
                model_used="fallback",
                cached=False,
                generation_time=time.time() - start_time,
                total_tokens=0
            )

        # Вызов LLM
        logger.info(f"RAG: вызов LLM для генерации ответа")
        try:
            llm_response = await self._call_llm(prompt)
        except Exception as e:
            logger.error(f"RAG: ошибка LLM - {e}")
            # Fallback: вернуть только результаты поиска
            fallback_answer = "**Не удалось сгенерировать ответ (LLM недоступен).**\n\n"
            fallback_answer += "Найденные документы:\n\n"
            for r in results:
                fallback_answer += f"- **{r.document.title}** ({r.score:.2f}): {r.snippet[:200]}...\n"

            return RAGResponse(
                answer=fallback_answer,
                sources=[{"title": r.document.title, "path": r.document.path, "score": r.score} for r in results],
                query=query,
                model_used="fallback",
                cached=False,
                generation_time=time.time() - start_time,
                total_tokens=0
            )

        # Извлечь ответ
        answer = llm_response.get("choices", [{}])[0].get("message", {}).get("content", "")
        model_used = llm_response.get("model", "unknown")
        usage = llm_response.get("usage", {})
        total_tokens = usage.get("total_tokens", 0)

        # Формируем источники
        sources = [
            {
                "title": r.document.title,
                "path": r.document.path,
                "score": r.score,
                "id": r.document.id
            }
            for r in results
        ]

        # Добавляем источники к ответу если их нет
        if "источник" not in answer.lower() and "source" not in answer.lower():
            answer += "\n\n---\n**Источники:**\n"
            for s in sources[:3]:
                answer += f"- [{s['title']}]({s['path']}) (релевантность: {s['score']:.2f})\n"

        response = RAGResponse(
            answer=answer,
            sources=sources,
            query=query,
            model_used=model_used,
            cached=False,
            generation_time=time.time() - start_time,
            total_tokens=total_tokens
        )

        # Сохраняем в кеш
        if use_cache:
            self.cache.set(response)

        logger.info(f"RAG: ответ сгенерирован за {response.generation_time:.2f}с, {total_tokens} токенов")

        # Логируем финальные метрики
        if log_metric:
            log_metric("rag_generation_time_ms", int(response.generation_time * 1000), {"model": model_used})
            log_metric("rag_total_tokens", total_tokens)
            log_metric("rag_success", 1)

        return response

    async def ask_with_followup(
        self,
        query: str,
        conversation_history: Optional[List[Dict[str, str]]] = None
    ) -> RAGResponse:
        """
        Ответить на вопрос с учетом истории разговора

        Args:
            query: Текущий вопрос
            conversation_history: История диалога [{role: "user/assistant", content: "..."}]

        Returns:
            RAGResponse с ответом
        """
        # Для follow-up вопросов расширяем контекст
        extended_query = query
        if conversation_history:
            # Добавляем контекст из последних сообщений
            recent = conversation_history[-4:]  # Последние 2 пары
            context_parts = []
            for msg in recent:
                if msg["role"] == "user":
                    context_parts.append(f"Предыдущий вопрос: {msg['content']}")
            if context_parts:
                extended_query = f"{' | '.join(context_parts)} | Текущий вопрос: {query}"

        return await self.ask(extended_query, use_cache=False)

    async def stream(
        self,
        query: str,
        search_type: str = "hybrid",
        top_k: int = TOP_K_DOCUMENTS,
        source_filter: Optional[str] = None
    ) -> AsyncIterator[str]:
        """
        Потоковая генерация ответа на вопрос используя RAG

        Args:
            query: Вопрос пользователя
            search_type: Тип поиска (fulltext, semantic, hybrid)
            top_k: Количество документов для контекста
            source_filter: Фильтр по источнику (путь к документации)

        Yields:
            Текстовые фрагменты ответа по мере генерации
        """
        start_time = time.time()

        # Поиск релевантных документов
        logger.info(f"RAG stream: поиск документов для '{query[:50]}...'")
        results = self.search_engine.search(query, limit=top_k * 2, search_type=search_type)

        # Фильтрация по источнику если указан
        if source_filter:
            results = [r for r in results if source_filter.lower() in r.document.path.lower()]
            logger.info(f"RAG stream: отфильтровано {len(results)} документов")

        results = results[:top_k]

        if not results:
            filter_msg = f" (фильтр: {source_filter})" if source_filter else ""
            yield f"К сожалению, по вашему запросу не найдено релевантной документации.{filter_msg}"
            return

        # Построить контекст и промпт
        context = self._build_context(results)
        prompt = self._build_prompt(query, context)

        # Убеждаемся что LLM HTTP сервер запущен
        llm_available = await self._ensure_llm_http_running()
        if not llm_available:
            yield "**Не удалось запустить LLM сервер.**\n\n"
            yield "Найденные документы:\n\n"
            for r in results:
                yield f"- **{r.document.title}** ({r.score:.2f}): {r.snippet[:200]}...\n"
            return

        # Вызов LLM со streaming
        logger.info(f"RAG stream: вызов LLM для генерации ответа")
        try:
            full_answer = ""
            async for token in self._call_llm_stream(prompt):
                full_answer += token
                yield token

            # Добавляем источники если их нет
            if "источник" not in full_answer.lower() and "source" not in full_answer.lower():
                sources = "\n\n---\n**Источники:**\n"
                for r in results[:3]:
                    sources += f"- [{r.document.title}]({r.document.path}) (релевантность: {r.score:.2f})\n"
                yield sources

            logger.info(f"RAG stream: завершено за {time.time() - start_time:.2f}с")

        except Exception as e:
            logger.error(f"RAG stream: ошибка LLM - {e}")
            yield f"**Ошибка генерации:** {e}\n\n"
            yield "Найденные документы:\n\n"
            for r in results:
                yield f"- **{r.document.title}** ({r.score:.2f}): {r.snippet[:200]}...\n"

    def get_cache_stats(self) -> Dict[str, Any]:
        """Получить статистику кеша"""
        cache_files = list(self.cache.cache_dir.glob("*.json"))
        total_size = sum(f.stat().st_size for f in cache_files)

        return {
            "cached_queries": len(cache_files),
            "cache_size_kb": total_size / 1024,
            "cache_dir": str(self.cache.cache_dir),
            "ttl_hours": CACHE_TTL_HOURS
        }

    def clear_cache(self) -> int:
        """Очистить кеш"""
        return self.cache.clear()


# Для тестирования модуля
async def _test_rag():
    """Тестирование RAG модуля"""
    from hybrid_search_engine import HybridSearchEngine

    engine = HybridSearchEngine()
    rag = RAGModule(engine)

    try:
        # Тестовый запрос
        response = await rag.ask("Как настроить MCP сервер для Claude Code?")

        log_stderr(f"Вопрос: {response.query}")
        log_stderr(f"Модель: {response.model_used}")
        log_stderr(f"Время: {response.generation_time:.2f}с")
        log_stderr(f"Токены: {response.total_tokens}")
        log_stderr(f"Кеш: {response.cached}")
        log_stderr(f"\nОтвет:\n{response.answer}")
        log_stderr(f"\nИсточники: {len(response.sources)}")
        for s in response.sources:
            log_stderr(f"  - {s['title']} ({s['score']:.2f})")
    finally:
        await rag.close()


if __name__ == "__main__":
    asyncio.run(_test_rag())
