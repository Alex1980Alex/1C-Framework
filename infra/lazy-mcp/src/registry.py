"""
Registry Module - Реестр MCP серверов и категорий

Загружает конфигурацию серверов и предоставляет навигацию по категориям.
"""

import yaml
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any


@dataclass
class ServerConfig:
    """Конфигурация MCP сервера"""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    description: str = ""
    timeout: int = 60000
    type: str = "native"  # native, docker-mcp, npx, docker-gateway, bridge
    docker_image: Optional[str] = None  # Для docker-mcp: mcp/brave-search
    docker_server: Optional[str] = None  # Для docker-mcp: имя сервера в gateway
    endpoints: dict[str, str] = field(default_factory=dict)  # Для bridge: {base_url, ...}


@dataclass
class ToolInfo:
    """Информация об инструменте"""
    name: str
    description: str
    server: str
    category: str
    input_schema: dict = field(default_factory=dict)


class Registry:
    """
    Реестр MCP серверов с иерархической навигацией.

    Структура:
    /
    ├── 1c-development/
    │   ├── ast-grep-mcp
    │   └── bsl-platform-context
    ├── web-search/
    │   └── brave
    └── ...
    """

    def __init__(self, config_path: Optional[Path | str] = None):
        # Конвертация str в Path если передана строка
        if config_path is not None:
            self.config_path = Path(config_path) if isinstance(config_path, str) else config_path
        else:
            self.config_path = Path(__file__).parent.parent / "config" / "registry.yaml"
        self.categories: dict[str, dict] = {}
        self.servers: dict[str, ServerConfig] = {}
        self.tool_cache: dict[str, list[ToolInfo]] = {}
        self._load_config()

    def _load_config(self) -> None:
        """Загрузка конфигурации из YAML"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Registry config not found: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        self.categories = config.get('categories', {})

        # Парсинг серверов из категорий
        for category_name, category_data in self.categories.items():
            servers = category_data.get('servers', {})
            for server_name, server_data in servers.items():
                server_type = server_data.get('type', 'native')

                # Для docker-mcp серверов command может быть не указан
                if server_type == "docker-mcp":
                    command = "docker"  # Заглушка, будет игнорироваться
                    args = []
                else:
                    command = server_data.get('command', '')
                    args = server_data.get('args', [])

                self.servers[server_name] = ServerConfig(
                    name=server_name,
                    command=command,
                    args=args,
                    env=server_data.get('env', {}),
                    cwd=server_data.get('cwd'),
                    description=server_data.get('description', ''),
                    timeout=server_data.get('timeout', 60000),
                    type=server_type,
                    docker_image=server_data.get('docker_image'),
                    docker_server=server_data.get('docker_server', server_name),
                    endpoints=server_data.get('endpoints', {})
                )

    def get_categories(self, path: str = "/") -> list[str]:
        """
        Получить список категорий или серверов по пути.

        Args:
            path: Путь в иерархии (/, /1c-development, /1c-development/ast-grep-mcp)

        Returns:
            Список имён категорий или серверов
        """
        path = path.strip('/')

        if not path:
            # Корневой уровень - возвращаем категории
            return list(self.categories.keys())

        parts = path.split('/')

        if len(parts) == 1:
            # Уровень категории - возвращаем серверы
            category = parts[0]
            if category in self.categories:
                return list(self.categories[category].get('servers', {}).keys())
            return []

        if len(parts) == 2:
            # Уровень сервера - возвращаем инструменты
            category, server = parts
            if category in self.categories:
                servers = self.categories[category].get('servers', {})
                if server in servers:
                    # Здесь нужно получить инструменты сервера
                    return self._get_server_tools_names(server)
            return []

        return []

    def _get_server_tools_names(self, server_name: str) -> list[str]:
        """Получить имена инструментов сервера (из кеша или заглушка)"""
        if server_name in self.tool_cache:
            return [t.name for t in self.tool_cache[server_name]]

        # Заглушка - реальные инструменты будут загружены при первом вызове
        return [f"[tools of {server_name} - call execute_tool to load]"]

    def get_server_config(self, server_name: str) -> Optional[ServerConfig]:
        """Получить конфигурацию сервера по имени"""
        return self.servers.get(server_name)

    def find_server_by_path(self, tool_path: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Найти сервер по полному пути к инструменту.

        Args:
            tool_path: Полный путь (/category/server/tool)

        Returns:
            (category, server_name, tool_name) или (None, None, None)
        """
        path = tool_path.strip('/')
        parts = path.split('/')

        if len(parts) >= 2:
            category = parts[0]
            server = parts[1]
            tool = parts[2] if len(parts) > 2 else None

            if category in self.categories:
                servers = self.categories[category].get('servers', {})
                if server in servers:
                    return (category, server, tool)

        return (None, None, None)

    def get_category_info(self, path: str = "/") -> dict[str, Any]:
        """
        Получить информацию о категории для отображения.

        Returns:
            {
                "path": "/1c-development",
                "description": "Инструменты разработки 1С",
                "items": ["ast-grep-mcp", "bsl-platform-context"],
                "type": "category" | "servers" | "tools"
            }
        """
        path = path.strip('/')

        if not path:
            return {
                "path": "/",
                "description": "Root - all tool categories",
                "items": list(self.categories.keys()),
                "type": "categories"
            }

        parts = path.split('/')

        if len(parts) == 1:
            category = parts[0]
            if category in self.categories:
                cat_data = self.categories[category]
                return {
                    "path": f"/{category}",
                    "description": cat_data.get('description', ''),
                    "items": list(cat_data.get('servers', {}).keys()),
                    "type": "servers"
                }

        if len(parts) == 2:
            category, server = parts
            if server in self.servers:
                server_config = self.servers[server]
                return {
                    "path": f"/{category}/{server}",
                    "description": server_config.description,
                    "items": self._get_server_tools_names(server),
                    "type": "tools",
                    "server_config": {
                        "command": server_config.command,
                        "type": server_config.type
                    }
                }

        return {"error": f"Path not found: {path}"}

    def cache_tools(self, server_name: str, tools: list[ToolInfo]) -> None:
        """Кешировать информацию об инструментах сервера"""
        self.tool_cache[server_name] = tools

    def get_servers_in_category(self, category: str) -> list[str]:
        """Получить список серверов в категории"""
        if category in self.categories:
            return list(self.categories[category].get('servers', {}).keys())
        return []

    def to_json(self) -> str:
        """Экспорт реестра в JSON для отладки"""
        return json.dumps({
            "categories": self.categories,
            "servers": {k: v.__dict__ for k, v in self.servers.items()}
        }, indent=2, ensure_ascii=False)
