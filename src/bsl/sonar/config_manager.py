"""
SonarQube Configuration Manager

Phase 45: Миграция из 1C-Enterprise_Framework
"""

import json
import logging
import os
import tempfile
from pathlib import Path

from pydantic import BaseModel

logger = logging.getLogger(__name__)

_DEFAULT_CONFIG_PATH = Path("data/sonar_config.json")


class SonarQubeConfig(BaseModel):
    """Конфигурация SonarQube"""

    host: str = "http://localhost:9000"
    token: str = ""
    project_key: str = ""
    sources: str = "src"

    # BSL-specific settings
    bsl_plugin_version: str = "1.0.0"
    quality_profile: str = "bsl-way"

    # Scanner path (relative to project root, Windows default)
    sonar_scanner_path: str = "tools/sonar-scanner-6.2.1.4610-windows-x64/bin/sonar-scanner.bat"

    @property
    def api_url(self) -> str:
        return f"{self.host}/api"


class ConfigManager:
    """Менеджер конфигурации SonarQube"""

    def __init__(self, config_path: str | None = None):
        self.config_path = config_path
        self._config: SonarQubeConfig | None = None

    def load(self) -> SonarQubeConfig:
        """Загрузка конфигурации из JSON-файла. Возвращает defaults если файл отсутствует."""
        if self._config:
            return self._config

        config_path = Path(self.config_path) if self.config_path else _DEFAULT_CONFIG_PATH
        if config_path.exists():
            try:
                data = json.loads(config_path.read_text(encoding="utf-8"))
                self._config = SonarQubeConfig(**data)
                logger.debug("Loaded sonar config from %s", config_path)
            except Exception as e:
                logger.warning(
                    "Failed to load sonar config from %s: %s. Using defaults.", config_path, e
                )
                self._config = SonarQubeConfig()
        else:
            self._config = SonarQubeConfig()
        return self._config

    def save(self, config: SonarQubeConfig) -> None:
        """Атомарная запись конфигурации в JSON-файл через tempfile + os.replace."""
        self._config = config
        config_path = Path(self.config_path) if self.config_path else _DEFAULT_CONFIG_PATH
        config_path.parent.mkdir(parents=True, exist_ok=True)

        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=config_path.parent,
            suffix=".tmp",
            prefix=".sonar_config_",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                f.write(config.model_dump_json(indent=2))
            os.replace(tmp_path, config_path)
            logger.debug("Saved sonar config to %s", config_path)
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
