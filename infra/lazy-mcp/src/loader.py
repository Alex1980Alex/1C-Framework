"""
Loader Module - Динамический загрузчик MCP серверов

Управляет жизненным циклом серверов: запуск, остановка, пул активных.

Windows-specific fixes based on:
- https://github.com/modelcontextprotocol/python-sdk/issues/552 (stdio hanging)
- https://github.com/modelcontextprotocol/python-sdk/issues/671 (tool execution hanging)
"""

import asyncio
import subprocess
import sys
import os
import json
import threading
import urllib.request
import urllib.error
from typing import Optional, Any
from dataclasses import dataclass, field
from collections import OrderedDict
import logging

# Windows-specific flags for subprocess
# IMPORTANT: DO NOT use CREATE_NO_WINDOW - it breaks stdio pipes!
# See: Testing 2026-01-06 - CREATE_NO_WINDOW causes all MCP servers to hang
# Only use CREATE_NEW_PROCESS_GROUP for proper signal handling
if sys.platform == 'win32':
    WINDOWS_CREATION_FLAGS = subprocess.CREATE_NEW_PROCESS_GROUP
else:
    WINDOWS_CREATION_FLAGS = 0

try:
    from .registry import ServerConfig, Registry
except ImportError:
    from registry import ServerConfig, Registry

logger = logging.getLogger(__name__)


@dataclass
class ActiveServer:
    """Активный MCP сервер"""
    name: str
    process: subprocess.Popen
    config: ServerConfig
    tools: list[dict] = None
    is_proxy: bool = False  # Если True - это прокси для docker-mcp
    proxied_servers: dict[str, list[dict]] = None  # {"brave": [tools], "fetch": [tools]}
    stderr_thread: threading.Thread = None  # Daemon thread для чтения stderr

    def __post_init__(self):
        if self.tools is None:
            self.tools = []
        if self.proxied_servers is None:
            self.proxied_servers = {}


@dataclass
class BridgeServer:
    """HTTP Bridge сервер (например MCPO)"""
    name: str
    config: ServerConfig
    base_url: str
    tools: list[dict] = None
    is_running: bool = False

    def __post_init__(self):
        if self.tools is None:
            self.tools = []


class ServerLoader:
    """
    Динамический загрузчик MCP серверов.

    - Запускает серверы по требованию
    - Поддерживает пул активных серверов (LRU)
    - Graceful shutdown
    - Singleton Docker MCP Gateway с retry логикой
    """

    # Singleton для Docker MCP Gateway (класс-уровень)
    _gateway_instance: Optional[ActiveServer] = None
    _gateway_tools_cache: list[dict] = []
    _gateway_lock = asyncio.Lock()

    def __init__(self, registry: Registry, max_active: int = 5):
        self.registry = registry
        self.max_active = max_active
        self.active_servers: OrderedDict[str, ActiveServer] = OrderedDict()
        self.bridge_servers: dict[str, BridgeServer] = {}  # HTTP bridge серверы
        self._lock = asyncio.Lock()

    async def get_server(self, server_name: str) -> Optional[ActiveServer]:
        """
        Получить активный сервер (запустить если нужно).

        Args:
            server_name: Имя сервера из registry

        Returns:
            ActiveServer или None если не удалось запустить
        """
        async with self._lock:
            # Если уже активен - проверить жив ли процесс
            if server_name in self.active_servers:
                server = self.active_servers[server_name]
                # Проверка: процесс всё ещё работает?
                if server.process and server.process.poll() is None:
                    self.active_servers.move_to_end(server_name)
                    return server
                else:
                    # Процесс мёртв - удалить из кеша и перезапустить
                    logger.warning(f"Server {server_name} process died, restarting...")
                    del self.active_servers[server_name]

            # Проверить лимит и освободить место
            while len(self.active_servers) >= self.max_active:
                oldest_name = next(iter(self.active_servers))
                await self._shutdown_server(oldest_name)

            # Запустить новый сервер
            server = await self._start_server(server_name)
            if server:
                self.active_servers[server_name] = server

            return server

    async def _start_server(self, server_name: str) -> Optional[ActiveServer]:
        """Запустить MCP сервер"""
        config = self.registry.get_server_config(server_name)
        if not config:
            logger.error(f"Server config not found: {server_name}")
            return None

        # Для docker-mcp серверов запускаем через gateway
        if config.type == "docker-mcp":
            return await self._start_docker_server(server_name, config)

        # Для bridge серверов (MCPO) - не запускаем процесс, только регистрируем
        if config.type == "bridge":
            return await self._register_bridge_server(server_name, config)

        try:
            # Подготовка окружения
            env = os.environ.copy()
            env.update(config.env)
            env['PYTHONIOENCODING'] = 'utf-8'
            # CRITICAL: Disable Python stdout buffering for stdio MCP protocol
            # Without this, responses are buffered (~8KB) and never reach the client
            env['PYTHONUNBUFFERED'] = '1'

            # Формирование команды
            cmd = [config.command] + config.args

            # For Python servers: add -u flag for unbuffered stdout
            # This is more reliable than PYTHONUNBUFFERED for stdio MCP protocol
            if 'python' in config.command.lower():
                # Insert -u after python executable and before script
                cmd = [config.command, '-u'] + config.args

            logger.info(f"Starting server: {server_name} (type: {config.type})")
            logger.debug(f"Command: {cmd}")

            # Windows-specific: Use cmd /c wrapper instead of shell=True
            # shell=True creates intermediate cmd.exe which can break stdio pipes
            # Issue: https://github.com/modelcontextprotocol/python-sdk/issues/552
            if sys.platform == 'win32' and config.command in ('npx', 'node', 'npm', 'python', 'java'):
                # Wrap command with cmd /c for PATH resolution
                cmd_str = ' '.join(cmd)
                cmd = ['cmd', '/c', cmd_str]
                use_shell = False
            else:
                use_shell = False

            # Запуск процесса с Windows-specific flags
            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                cwd=config.cwd,
                bufsize=0,
                shell=use_shell,
                creationflags=WINDOWS_CREATION_FLAGS if sys.platform == 'win32' else 0
            )

            # CRITICAL FIX: Start daemon thread to drain stderr
            # Without this, stderr buffer fills up (~64KB) and blocks the process
            # from writing to stdout, causing tools/call to timeout
            # See: test_unified_deep.py which works because it drains stderr
            def drain_stderr(proc, name):
                """Drain stderr in background to prevent buffer blocking stdout"""
                try:
                    while proc.poll() is None:
                        line = proc.stderr.readline()
                        if line:
                            text = line.decode('utf-8', errors='ignore').strip()
                            if text:
                                logger.debug(f"[{name}] {text}")
                except Exception:
                    pass  # Process terminated

            stderr_thread = threading.Thread(
                target=drain_stderr,
                args=(process, server_name),
                daemon=True,
                name=f"stderr-drain-{server_name}"
            )
            stderr_thread.start()

            # Задержка для инициализации (больше для тяжёлых серверов)
            init_delay = 0.5
            if server_name in ('unified-memory', 'bsl-platform-context', 'memory-ai', 'deep-code-reasoning'):
                init_delay = 3.0  # Эти серверы загружают модели/базы или внешние API
            await asyncio.sleep(init_delay)

            if process.poll() is not None:
                stderr_out = process.stderr.read().decode('utf-8', errors='ignore')
                stdout = process.stdout.read().decode('utf-8', errors='ignore')
                logger.error(f"Server {server_name} failed to start")
                logger.error(f"  Exit code: {process.returncode}")
                logger.error(f"  Command: {' '.join(cmd)}")
                logger.error(f"  CWD: {config.cwd}")
                if stderr_out:
                    logger.error(f"  STDERR: {stderr_out[:500]}")
                if stdout:
                    logger.error(f"  STDOUT: {stdout[:500]}")
                return None

            server = ActiveServer(
                name=server_name,
                process=process,
                config=config,
                stderr_thread=stderr_thread
            )

            # Получить список инструментов
            tools = await self._get_server_tools(server)
            server.tools = tools

            logger.info(f"Server {server_name} started with {len(tools)} tools")
            return server

        except Exception as e:
            logger.error(f"Failed to start server {server_name}: {e}")
            return None

    async def _start_docker_server(self, server_name: str, config: ServerConfig) -> Optional[ActiveServer]:
        """
        Запустить docker-mcp сервер через Docker MCP Gateway (Singleton).

        Docker MCP Gateway - это единый прокси для всех docker-mcp серверов.
        Он запускается ОДИН РАЗ (singleton) и предоставляет инструменты для работы с docker-mcp серверами.

        Architecture:
        1. Используем singleton _gateway_instance (если не запущен - запускаем с retry)
        2. Добавляем нужный сервер через mcp-add
        3. Вызываем инструменты через mcp-exec

        Fix: https://github.com/docker/mcp-gateway/issues/89 - увеличен timeout до 15 сек
        """
        try:
            # Получаем или создаём singleton gateway
            gateway = await self._ensure_gateway_running()
            if not gateway:
                logger.error("Failed to start Docker MCP Gateway after retries")
                return None

            # Добавляем docker-mcp сервер в gateway
            await self._add_docker_server_to_gateway(gateway, config)

            # Создаём виртуальный ActiveServer для docker-mcp
            # Он использует gateway.process для выполнения
            server = ActiveServer(
                name=server_name,
                process=gateway.process,
                config=config,
                is_proxy=True
            )

            # Добавляем инструменты сервера в proxied_servers
            # Используем заранее известный список инструментов для каждого docker-mcp сервера
            server_tools = self._get_known_docker_tools(config.docker_server or server_name)
            server.tools = server_tools
            gateway.proxied_servers[server_name] = server_tools

            # Также добавляем в active_servers для LRU tracking
            gateway_name = "docker-mcp-gateway"
            if gateway_name not in self.active_servers:
                self.active_servers[gateway_name] = gateway

            logger.info(f"Docker-MCP server {server_name} proxied with {len(server_tools)} tools")
            return server

        except Exception as e:
            logger.error(f"Failed to start docker-mcp server {server_name}: {e}")
            return None

    # =========================================================================
    # HTTP Bridge Server Support (MCPO и аналоги)
    # =========================================================================

    async def _register_bridge_server(self, server_name: str, config: ServerConfig) -> Optional[ActiveServer]:
        """
        Зарегистрировать HTTP bridge сервер (MCPO).

        Bridge серверы НЕ запускаются как subprocess - они уже запущены отдельно.
        Мы только проверяем доступность и регистрируем для использования.
        """
        try:
            base_url = config.endpoints.get("base_url", "http://localhost:8765")

            # Проверяем доступность bridge сервера
            is_available = await self._check_bridge_health(base_url)
            if not is_available:
                logger.warning(f"Bridge server {server_name} not available at {base_url}")
                # Возвращаем None - bridge недоступен, но это не критическая ошибка
                return None

            # Создаём BridgeServer и добавляем в registry
            bridge = BridgeServer(
                name=server_name,
                config=config,
                base_url=base_url,
                is_running=True
            )

            # Получаем список инструментов от bridge (MCPO предоставляет OpenAPI)
            tools = await self._get_bridge_tools(bridge)
            bridge.tools = tools

            self.bridge_servers[server_name] = bridge
            logger.info(f"Bridge server {server_name} registered at {base_url} with {len(tools)} tools")

            # Возвращаем "виртуальный" ActiveServer для совместимости с LRU cache
            # process=None означает что это не subprocess
            virtual_server = ActiveServer(
                name=server_name,
                process=None,  # Нет subprocess для bridge
                config=config,
                tools=tools,
                is_proxy=True  # Помечаем как proxy
            )

            return virtual_server

        except Exception as e:
            logger.error(f"Failed to register bridge server {server_name}: {e}")
            return None

    async def _check_bridge_health(self, base_url: str, timeout: float = 5.0) -> bool:
        """Проверить доступность HTTP bridge сервера"""
        try:
            # Простой GET запрос на корень для проверки доступности
            req = urllib.request.Request(
                base_url,
                method="GET",
                headers={"Accept": "application/json"}
            )

            loop = asyncio.get_event_loop()

            def do_request():
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        return response.status == 200
                except urllib.error.HTTPError as e:
                    # 404, 405 и т.д. - сервер доступен, просто endpoint не найден
                    return e.code < 500
                except Exception:
                    return False

            return await loop.run_in_executor(None, do_request)

        except Exception as e:
            logger.debug(f"Bridge health check failed: {e}")
            return False

    async def _get_bridge_tools(self, bridge: BridgeServer) -> list[dict]:
        """
        Получить список инструментов от bridge сервера.

        MCPO предоставляет OpenAPI spec, из которого можно извлечь tools.
        Для простоты используем предопределённый список из registry endpoints.
        """
        tools = []

        # Для MCPO: endpoints содержит маршруты к sub-серверам
        # Например: {base_url, filesystem: "/filesystem", ripgrep: "/ripgrep"}
        for endpoint_name, endpoint_path in bridge.config.endpoints.items():
            if endpoint_name == "base_url":
                continue

            # Добавляем известные инструменты для каждого endpoint
            endpoint_tools = self._get_known_bridge_tools(endpoint_name)
            for tool in endpoint_tools:
                tool["_bridge_endpoint"] = endpoint_name
                tools.append(tool)

        return tools

    def _get_known_bridge_tools(self, endpoint_name: str) -> list[dict]:
        """
        Получить известные инструменты для bridge endpoint.

        В реальной системе можно парсить OpenAPI spec от MCPO.
        """
        known_tools = {
            "filesystem": [
                {
                    "name": "read_file",
                    "description": "Read file content (alias for read_text_file)",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                },
                {
                    "name": "read_text_file",
                    "description": "Read text file content",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                },
                {
                    "name": "write_file",
                    "description": "Write content to file",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "content": {"type": "string"}
                        },
                        "required": ["path", "content"]
                    }
                },
                {
                    "name": "list_directory",
                    "description": "List directory contents",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                },
                {
                    "name": "search_files",
                    "description": "Search for files by pattern",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string"},
                            "pattern": {"type": "string"}
                        },
                        "required": ["path", "pattern"]
                    }
                }
            ],
            "ripgrep": [
                {
                    "name": "search",
                    "description": "Search for pattern in files",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": "string"}
                        },
                        "required": ["pattern", "path"]
                    }
                },
                {
                    "name": "list-files",
                    "description": "List files that would be searched",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"path": {"type": "string"}},
                        "required": ["path"]
                    }
                }
            ],
            "fetch": [
                {
                    "name": "fetch",
                    "description": "Fetch URL content",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"url": {"type": "string"}},
                        "required": ["url"]
                    }
                }
            ],
            "brave": [
                {
                    "name": "brave_web_search",
                    "description": "Search the web with Brave",
                    "inputSchema": {
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"]
                    }
                }
            ],
            "serena": [
                {
                    "name": "list_dir",
                    "description": "List directory",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "relative_path": {"type": "string"},
                            "recursive": {"type": "boolean"}
                        },
                        "required": ["relative_path", "recursive"]
                    }
                },
                {
                    "name": "find_file",
                    "description": "Find files by mask",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "file_mask": {"type": "string"},
                            "relative_path": {"type": "string"}
                        },
                        "required": ["file_mask", "relative_path"]
                    }
                }
            ]
        }

        return known_tools.get(endpoint_name, [])

    async def execute_bridge_tool(
        self,
        server_name: str,
        tool_name: str,
        arguments: dict
    ) -> Any:
        """
        Выполнить инструмент через HTTP bridge (MCPO).

        Args:
            server_name: Имя bridge сервера (mcpo)
            tool_name: Имя инструмента (read_text_file)
            arguments: Аргументы вызова

        Returns:
            Результат выполнения
        """
        # Проверяем наличие bridge сервера
        if server_name not in self.bridge_servers:
            # Пробуем зарегистрировать
            config = self.registry.get_server_config(server_name)
            if config and config.type == "bridge":
                await self._register_bridge_server(server_name, config)

        bridge = self.bridge_servers.get(server_name)
        if not bridge:
            return {"error": f"Bridge server not available: {server_name}"}

        # Определяем endpoint для инструмента
        endpoint = self._find_tool_endpoint(bridge, tool_name)
        if not endpoint:
            return {"error": f"Tool endpoint not found: {tool_name}"}

        # Формируем URL для вызова
        url = f"{bridge.base_url}/{endpoint}/{tool_name}"

        try:
            # HTTP POST запрос к MCPO
            data = json.dumps(arguments).encode("utf-8")
            req = urllib.request.Request(
                url,
                data=data,
                method="POST",
                headers={"Content-Type": "application/json"}
            )

            loop = asyncio.get_event_loop()
            timeout = (bridge.config.timeout / 1000.0) if bridge.config.timeout else 30.0

            def do_request():
                try:
                    with urllib.request.urlopen(req, timeout=timeout) as response:
                        result = response.read().decode("utf-8")
                        # Пробуем парсить как JSON
                        try:
                            return json.loads(result)
                        except json.JSONDecodeError:
                            # Возвращаем как текст
                            return {"content": [{"type": "text", "text": result}]}
                except urllib.error.HTTPError as e:
                    error_body = e.read().decode("utf-8") if e.fp else str(e)
                    return {"error": f"HTTP {e.code}: {error_body}"}
                except Exception as e:
                    return {"error": str(e)}

            result = await loop.run_in_executor(None, do_request)
            logger.debug(f"Bridge tool {tool_name} result: {str(result)[:200]}...")
            return result

        except Exception as e:
            logger.error(f"Error executing bridge tool {tool_name}: {e}")
            return {"error": str(e)}

    def _find_tool_endpoint(self, bridge: BridgeServer, tool_name: str) -> Optional[str]:
        """Найти endpoint для инструмента по имени"""
        for tool in bridge.tools:
            if tool.get("name") == tool_name:
                return tool.get("_bridge_endpoint")

        # Fallback: пробуем найти по известным паттернам
        tool_to_endpoint = {
            # filesystem tools
            "read_file": "filesystem",
            "read_text_file": "filesystem",
            "read_media_file": "filesystem",
            "read_multiple_files": "filesystem",
            "write_file": "filesystem",
            "edit_file": "filesystem",
            "create_directory": "filesystem",
            "list_directory": "filesystem",
            "list_directory_with_sizes": "filesystem",
            "directory_tree": "filesystem",
            "move_file": "filesystem",
            "search_files": "filesystem",
            "get_file_info": "filesystem",
            "list_allowed_directories": "filesystem",
            # ripgrep tools
            "search": "ripgrep",
            "list-files": "ripgrep",
            "advanced-search": "ripgrep",
            "count-matches": "ripgrep",
            "list-file-types": "ripgrep",
            # web tools
            "fetch": "fetch",
            "brave_web_search": "brave",
            # serena tools
            "list_dir": "serena",
            "find_file": "serena"
        }

        return tool_to_endpoint.get(tool_name)

    async def _ensure_gateway_running(self) -> Optional[ActiveServer]:
        """
        Singleton pattern: получить или создать Docker MCP Gateway.

        - Если gateway уже запущен и жив - возвращаем его
        - Если нет - запускаем с retry логикой (3 попытки)
        - Timeout: 15 секунд (для загрузки каталога 311+ серверов)
        """
        async with ServerLoader._gateway_lock:
            # Проверяем существующий gateway
            if ServerLoader._gateway_instance:
                if ServerLoader._gateway_instance.process.poll() is None:
                    logger.debug("Using existing Docker MCP Gateway (singleton)")
                    return ServerLoader._gateway_instance
                else:
                    logger.warning("Docker MCP Gateway process died, restarting...")
                    ServerLoader._gateway_instance = None
                    ServerLoader._gateway_tools_cache = []

            # Запускаем новый gateway с retry логикой
            max_retries = 3
            for attempt in range(1, max_retries + 1):
                logger.info(f"Starting Docker MCP Gateway (attempt {attempt}/{max_retries})...")

                gateway = await self._start_gateway_process()
                if gateway:
                    # Ждём готовности gateway
                    if await self._wait_for_gateway_ready(gateway):
                        ServerLoader._gateway_instance = gateway
                        logger.info(f"Docker MCP Gateway started successfully (attempt {attempt})")
                        return gateway
                    else:
                        # Gateway запустился но не отвечает - убиваем и пробуем снова
                        logger.warning(f"Gateway started but not responding (attempt {attempt})")
                        try:
                            gateway.process.kill()
                        except:
                            pass

                # Пауза между попытками (увеличивается с каждой попыткой)
                if attempt < max_retries:
                    wait_time = 2.0 * attempt
                    logger.info(f"Waiting {wait_time}s before retry...")
                    await asyncio.sleep(wait_time)

            logger.error(f"Failed to start Docker MCP Gateway after {max_retries} attempts")
            return None

    async def _start_gateway_process(self) -> Optional[ActiveServer]:
        """Запустить процесс Docker MCP Gateway"""
        try:
            gateway_name = "docker-mcp-gateway"
            gateway_config = self.registry.get_server_config(gateway_name)

            if not gateway_config:
                logger.error("Docker MCP Gateway config not found in registry")
                return None

            # Подготовка окружения
            env = os.environ.copy()
            env.update(gateway_config.env)

            cmd = [gateway_config.command] + gateway_config.args
            logger.info(f"Starting Docker MCP Gateway: {' '.join(cmd)}")

            # Windows-specific: Use cmd /c wrapper instead of shell=True
            # shell=True creates intermediate cmd.exe which can break stdio pipes
            if sys.platform == 'win32':
                cmd_str = ' '.join(cmd)
                cmd = ['cmd', '/c', cmd_str]
                use_shell = False
            else:
                use_shell = False

            process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                bufsize=0,
                shell=use_shell,
                creationflags=WINDOWS_CREATION_FLAGS if sys.platform == 'win32' else 0
            )

            # Задержка для запуска процесса (gateway грузит каталог ~2.5 сек)
            await asyncio.sleep(5.0)

            if process.poll() is not None:
                stderr = process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"Docker MCP Gateway process exited immediately: {stderr}")
                return None

            return ActiveServer(
                name=gateway_name,
                process=process,
                config=gateway_config,
                is_proxy=True
            )

        except Exception as e:
            logger.error(f"Error starting gateway process: {e}")
            return None

    async def _wait_for_gateway_ready(self, gateway: ActiveServer, timeout: float = 15.0) -> bool:
        """
        Ждать пока gateway ответит на initialize запрос.

        Docker MCP Gateway загружает каталог 311+ серверов при старте,
        что занимает 5-10 секунд. Используем timeout 15 сек с polling.

        Returns:
            True если gateway готов, False если timeout
        """
        import time
        start_time = time.time()
        poll_interval = 1.0
        attempt = 0

        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "lazy-mcp",
                    "version": "1.0.0"
                }
            }
        }

        while time.time() - start_time < timeout:
            attempt += 1
            logger.debug(f"Checking gateway readiness (attempt {attempt}, elapsed: {time.time() - start_time:.1f}s)")

            # Проверяем что процесс жив
            if gateway.process.poll() is not None:
                stderr = gateway.process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"Gateway process died during wait: {stderr}")
                return False

            try:
                response = await self._send_request_with_timeout(gateway, init_request, timeout=3.0)
                if response and 'result' in response:
                    logger.info(f"Gateway ready after {time.time() - start_time:.1f}s")

                    # Получаем и кешируем список инструментов
                    tools = await self._get_gateway_tools(gateway)
                    gateway.tools = tools
                    ServerLoader._gateway_tools_cache = tools

                    logger.info(f"Docker MCP Gateway has {len(tools)} tools")
                    return True

            except Exception as e:
                logger.debug(f"Gateway not ready yet: {e}")

            await asyncio.sleep(poll_interval)

        logger.error(f"Gateway did not become ready within {timeout}s")
        return False

    async def _send_request_with_timeout(self, server: ActiveServer, request: dict, timeout: float = 5.0) -> Optional[dict]:
        """Отправить JSON-RPC запрос с явным timeout"""
        try:
            # Check if process is still alive
            if server.process.poll() is not None:
                logger.debug(f"Server {server.name} process died before request")
                return None

            message = json.dumps(request) + "\n"
            logger.debug(f"Sending (timeout={timeout}s) to {server.name}: {request.get('method', 'unknown')}")

            server.process.stdin.write(message.encode('utf-8'))
            server.process.stdin.flush()

            loop = asyncio.get_event_loop()

            def read_response():
                try:
                    line = server.process.stdout.readline()
                    if not line:
                        return None
                    return line.decode('utf-8', errors='ignore').strip()
                except Exception as e:
                    logger.debug(f"Read error from {server.name}: {e}")
                    return None

            response_line = await asyncio.wait_for(
                loop.run_in_executor(None, read_response),
                timeout=timeout
            )

            if response_line:
                logger.debug(f"Response from {server.name}: {response_line[:100]}...")
                return json.loads(response_line)

            logger.debug(f"Empty response from {server.name}")
            return None

        except asyncio.TimeoutError:
            logger.debug(f"Timeout ({timeout}s) from {server.name}")
            return None
        except json.JSONDecodeError as e:
            logger.debug(f"Invalid JSON from {server.name}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Request error to {server.name}: {e}")
            return None

    async def _get_gateway_tools(self, gateway: ActiveServer) -> list[dict]:
        """Получить список инструментов от gateway (с кешированием)"""
        # Если есть кеш - используем его
        if ServerLoader._gateway_tools_cache:
            return ServerLoader._gateway_tools_cache

        tools_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }

        try:
            response = await self._send_request_with_timeout(gateway, tools_request, timeout=10.0)
            if response and 'result' in response:
                tools = response['result'].get('tools', [])
                ServerLoader._gateway_tools_cache = tools
                return tools
        except Exception as e:
            logger.error(f"Failed to get gateway tools: {e}")

        return []

    async def _add_docker_server_to_gateway(self, gateway: ActiveServer, server_config: ServerConfig) -> bool:
        """
        Добавить docker-mcp сервер в gateway через mcp-add.

        ВАЖНО: mcp-add доступен только в динамическом режиме (--enable-all-servers).
        В статическом режиме (--servers=) серверы уже предзагружены и mcp-add не нужен.
        """
        try:
            # Ищем инструмент mcp-add в gateway
            mcp_add_tool = None
            for tool in gateway.tools:
                if 'mcp-add' in tool.get('name', ''):
                    mcp_add_tool = tool
                    break

            if not mcp_add_tool:
                # В статическом режиме (--servers=) mcp-add отсутствует - это нормально
                # Серверы уже предзагружены при старте gateway
                logger.debug(f"Static mode: mcp-add not available, server {server_config.name} should be pre-loaded")
                return True  # Возвращаем True т.к. серверы уже загружены

            # Динамический режим: используем mcp-add
            if not server_config.docker_image:
                logger.warning(f"No docker_image specified for {server_config.name}")
                return False

            request = {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": mcp_add_tool['name'],
                    "arguments": {
                        "server": server_config.docker_image
                    }
                }
            }

            response = await self._send_request(gateway, request)
            if response and 'result' in response:
                logger.info(f"Added docker-mcp server {server_config.name} ({server_config.docker_image}) to gateway")
                return True

            logger.warning(f"Failed to add {server_config.name} to gateway")
            return False

        except Exception as e:
            logger.error(f"Error adding server to gateway: {e}")
            return False

    def _get_known_docker_tools(self, docker_server: str) -> list[dict]:
        """
        Получить заранее известные инструменты для docker-mcp сервера.

        В реальной системе эти инструменты можно discover через:
        1. mcp-add + mcp-find
        2. Или через tools/list после добавления сервера

        Возвращает короткие имена инструментов (без префикса mcp-{server}/)
        """
        known_tools = {
            "brave": [
                {"name": "brave_web_search", "description": "Search the web with Brave Search API"}
            ],
            "fetch": [
                {"name": "fetch", "description": "Fetch a URL and return the content"}
            ],
            "puppeteer": [
                {"name": "navigate", "description": "Navigate to a URL"},
                {"name": "screenshot", "description": "Take a screenshot"},
                {"name": "pdf", "description": "Save page as PDF"}
            ],
            "zip": [
                {"name": "read_zip", "description": "Read contents of a ZIP archive"},
                {"name": "create_zip", "description": "Create a ZIP archive"}
            ],
            "markitdown": [
                {"name": "convert", "description": "Convert document to Markdown"}
            ]
        }

        return known_tools.get(docker_server, [])

    async def _get_server_tools(self, server: ActiveServer) -> list[dict]:
        """Получить список инструментов от сервера через MCP протокол"""
        try:
            # Отправляем initialize request
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {
                        "name": "lazy-mcp",
                        "version": "1.0.0"
                    }
                }
            }

            response = await self._send_request(server, init_request)
            if not response:
                return []

            # ВАЖНО: Отправляем notifications/initialized (MCP протокол требует это!)
            # После initialize response клиент ОБЯЗАН отправить эту нотификацию
            # Иначе серверы могут не принимать tools/call запросы
            # Fix: https://modelcontextprotocol.io/specification/basic/lifecycle
            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized"
            }
            message = json.dumps(initialized_notification) + "\n"
            server.process.stdin.write(message.encode('utf-8'))
            server.process.stdin.flush()
            logger.debug(f"Sent notifications/initialized to {server.name}")

            # Отправляем tools/list request
            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {}
            }

            response = await self._send_request(server, tools_request)
            if response and 'result' in response:
                return response['result'].get('tools', [])

            return []

        except Exception as e:
            logger.error(f"Failed to get tools from {server.name}: {e}")
            return []

    async def _send_request(self, server: ActiveServer, request: dict, timeout: float = None) -> Optional[dict]:
        """Отправить JSON-RPC запрос серверу"""
        try:
            # Check if process is still alive
            if server.process.poll() is not None:
                logger.error(f"Server {server.name} process died (exit code: {server.process.returncode})")
                return None

            message = json.dumps(request) + "\n"
            logger.debug(f"Sending to {server.name}: {request.get('method', 'unknown')}")

            server.process.stdin.write(message.encode('utf-8'))
            server.process.stdin.flush()

            # Читаем ответ с таймаутом (используем timeout из конфига или 30 сек по умолчанию)
            if timeout is None:
                timeout = (server.config.timeout / 1000.0) if server.config.timeout else 30.0
                # Лимит 180 сек для серверов с внешними API (z.ai, Gemini), 60 сек для остальных
                timeout = min(timeout, 180.0)

            loop = asyncio.get_event_loop()

            def read_response():
                try:
                    # Windows fix: byte-by-byte reading instead of readline()
                    # readline() blocks on Windows due to stdout buffering issues
                    data = b''
                    while True:
                        chunk = server.process.stdout.read(1)
                        if not chunk:
                            # EOF - process might have died
                            if not data:
                                return None
                            break
                        data += chunk
                        # FastMCP uses \r\n as line terminator
                        if data.endswith(b'\r\n') or data.endswith(b'\n'):
                            break
                    return data.decode('utf-8', errors='ignore').strip()
                except Exception as e:
                    logger.error(f"Error reading from {server.name}: {e}")
                    return None

            response_line = await asyncio.wait_for(
                loop.run_in_executor(None, read_response),
                timeout=timeout
            )

            if response_line:
                logger.debug(f"Response from {server.name}: {response_line[:200]}...")
                return json.loads(response_line)

            logger.warning(f"Empty response from {server.name}")
            return None

        except asyncio.TimeoutError:
            logger.warning(f"Timeout ({timeout}s) reading from {server.name}")
            # Check if process died during timeout
            if server.process.poll() is not None:
                stderr = server.process.stderr.read().decode('utf-8', errors='ignore')
                logger.error(f"Server {server.name} died during request: {stderr[:500]}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON from {server.name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error communicating with {server.name}: {e}")
            return None

    async def execute_tool(self, server_name: str, tool_name: str, arguments: dict) -> Any:
        """
        Выполнить инструмент на сервере.

        Args:
            server_name: Имя сервера
            tool_name: Имя инструмента
            arguments: Аргументы вызова

        Returns:
            Результат выполнения
        """
        # Проверяем тип сервера ДО запуска
        config = self.registry.get_server_config(server_name)

        # Для bridge серверов (MCPO) используем HTTP вместо subprocess
        if config and config.type == "bridge":
            return await self.execute_bridge_tool(server_name, tool_name, arguments)

        server = await self.get_server(server_name)
        if not server:
            return {"error": f"Failed to start server: {server_name}"}

        # Для docker-mcp серверов используем mcp-exec через gateway
        if server.is_proxy:
            return await self._execute_docker_tool(server, tool_name, arguments)

        try:
            request = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            response = await self._send_request(server, request)

            if response:
                if 'result' in response:
                    return response['result']
                elif 'error' in response:
                    return {"error": response['error']}

            return {"error": "No response from server"}

        except Exception as e:
            logger.error(f"Error executing {tool_name} on {server_name}: {e}")
            return {"error": str(e)}

    async def _execute_docker_tool(self, server: ActiveServer, tool_name: str, arguments: dict) -> Any:
        """
        Выполнить инструмент docker-mcp сервера через Docker MCP Gateway.

        В статическом режиме (--servers=) инструменты вызываются НАПРЯМУЮ по имени.
        В динамическом режиме (--enable-all-servers) используется mcp-exec.
        """
        try:
            # Получаем gateway
            gateway_name = "docker-mcp-gateway"
            gateway = self.active_servers.get(gateway_name)
            if not gateway:
                return {"error": "Docker MCP Gateway not found"}

            # В статическом режиме (--servers=) инструменты доступны напрямую
            # Например: brave_web_search, fetch, puppeteer_navigate и т.д.
            # В динамическом режиме (--enable-all-servers) используется mcp-exec

            # Проверяем наличие mcp-exec для определения режима
            has_mcp_exec = any('mcp-exec' in tool.get('name', '') for tool in gateway.tools)

            if has_mcp_exec:
                # Динамический режим: используем mcp-exec
                mcp_exec_tool = next(t for t in gateway.tools if 'mcp-exec' in t.get('name', ''))
                docker_server = server.config.docker_server or server.name
                full_tool_name = f"mcp-{docker_server}/{tool_name}"

                request = {
                    "jsonrpc": "2.0",
                    "id": 20,
                    "method": "tools/call",
                    "params": {
                        "name": mcp_exec_tool['name'],
                        "arguments": {
                            "name": full_tool_name,
                            "arguments": arguments
                        }
                    }
                }
            else:
                # Статический режим: вызываем инструмент напрямую по имени
                # Инструменты уже зарегистрированы в gateway (например brave_web_search)
                request = {
                    "jsonrpc": "2.0",
                    "id": 20,
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    }
                }

            logger.debug(f"Executing docker tool: {tool_name} (dynamic={has_mcp_exec})")
            response = await self._send_request(gateway, request)

            if response:
                if 'result' in response:
                    return response['result']
                elif 'error' in response:
                    return {"error": response['error']}

            return {"error": "No response from Docker MCP Gateway"}

        except Exception as e:
            logger.error(f"Error executing docker tool {tool_name}: {e}")
            return {"error": str(e)}

    async def _shutdown_server(self, server_name: str) -> None:
        """Остановить сервер"""
        if server_name not in self.active_servers:
            return

        server = self.active_servers.pop(server_name)
        logger.info(f"Shutting down server: {server_name}")

        try:
            server.process.terminate()
            try:
                server.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                server.process.kill()
        except Exception as e:
            logger.error(f"Error shutting down {server_name}: {e}")

    async def shutdown_all(self) -> None:
        """Остановить все серверы"""
        for server_name in list(self.active_servers.keys()):
            await self._shutdown_server(server_name)

    def list_active(self) -> list[str]:
        """Список активных серверов"""
        return list(self.active_servers.keys())

    def get_server_tools(self, server_name: str) -> list[dict]:
        """Получить кешированные инструменты сервера"""
        if server_name in self.active_servers:
            return self.active_servers[server_name].tools
        return []
