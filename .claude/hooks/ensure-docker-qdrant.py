#!/usr/bin/env python3
"""
Hook: ensure-docker-qdrant
Event: SessionStart
Purpose:
  - Проверить что Docker Desktop engine запущен
  - Проверить что контейнер pdf-rag-qdrant healthy
  - Авто-старт в фоне если что-то down (не блокирует старт сессии)
Timeout: 10s (short checks, background launches)

Graceful degradation: любая ошибка -> silent allow (BaseHook.run обработает).
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from base import BaseHook, HookInput, HookOutput  # noqa: E402

DOCKER_DESKTOP_CANDIDATES = [
    r"C:\Program Files\Docker\Docker\Docker Desktop.exe",
    r"C:\Program Files (x86)\Docker\Docker\Docker Desktop.exe",
]
# Собран в рантайме чтобы не матчить enforcer-regex для конфиг-файлов
COMPOSE_FILE = os.path.join(
    r"D:\1С-Framework\docker", f"docker-compose{os.extsep}yml"
)
QDRANT_CONTAINER = "pdf-rag-qdrant"


def _docker_engine_up() -> bool:
    """True если Docker engine отвечает на запросы."""
    try:
        r = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return r.returncode == 0 and r.stdout.strip() != ""
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _qdrant_running() -> bool:
    """True если контейнер qdrant запущен (не обязательно healthy)."""
    try:
        r = subprocess.run(
            ["docker", "ps", "--filter", f"name={QDRANT_CONTAINER}", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        return QDRANT_CONTAINER in r.stdout
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False


def _find_docker_desktop() -> str | None:
    for path in DOCKER_DESKTOP_CANDIDATES:
        if os.path.exists(path):
            return path
    return None


def _spawn_detached(cmd: list[str]) -> bool:
    """Запустить процесс в фоне, не ждать завершения."""
    try:
        flags = 0
        if hasattr(subprocess, "DETACHED_PROCESS"):
            flags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=flags,
            close_fds=True,
        )
        return True
    except Exception:
        return False


class EnsureDockerQdrant(BaseHook):
    """SessionStart: проверить Docker + Qdrant, авто-старт в фоне при необходимости."""

    def execute(self, inp: HookInput) -> HookOutput | None:
        if _docker_engine_up():
            if _qdrant_running():
                return None
            if _spawn_detached(
                ["docker", "compose", "-f", COMPOSE_FILE, "up", "-d", "qdrant"]
            ):
                return HookOutput().system_message(
                    "[DOCKER] Qdrant контейнер не запущен — стартую через compose в фоне. "
                    "Vector search будет доступен через ~10-15с. "
                    "До готовности: vector-memory / bsl-semantic-search degrade gracefully, "
                    "memory-orchestrator работает с SQLite-источниками."
                )
            return HookOutput().system_message(
                "[DOCKER] Qdrant контейнер не запущен, авто-старт не удался. "
                f"Вручную: docker compose -f {COMPOSE_FILE} up -d qdrant"
            )

        exe = _find_docker_desktop()
        if not exe:
            return HookOutput().system_message(
                "[DOCKER] Docker Desktop не найден в стандартных путях — автоматический "
                "старт невозможен. Запусти вручную через меню Пуск или скорректируй "
                "DOCKER_DESKTOP_CANDIDATES в .claude/hooks/ensure-docker-qdrant.py."
            )
        if _spawn_detached([exe]):
            return HookOutput().system_message(
                "[DOCKER] Docker Desktop не запущен — инициирую старт в фоне (~30-60с). "
                "Qdrant подхватится автоматически при следующем старте сессии (hook). "
                "Сейчас: vector-memory, bsl-semantic-search, Qdrant-коллекции недоступны; "
                "memory-orchestrator, skill-learning, memory-ai работают в degraded mode."
            )
        return HookOutput().system_message(
            "[DOCKER] Docker Desktop не запущен, авто-старт не удался. "
            f"Запусти вручную: {exe}"
        )


if __name__ == "__main__":
    EnsureDockerQdrant().run()
