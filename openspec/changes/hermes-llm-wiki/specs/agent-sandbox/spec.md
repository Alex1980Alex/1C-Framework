# Spec: agent-sandbox

**Change:** hermes-llm-wiki
**Phase:** 5
**Profile:** python-framework

## Контекст

Research-скиллы (`architecture-research`, `tech-research`, `autoresearch`) и Ralph Wiggum loops требуют безопасного исполнения Python-кода: eval scripts, benchmark запуски, prototype тестирование. Сейчас этот код исполняется **на хост-машине**, что создаёт риски: недоверенный код, случайные deletions, network exfil.

После аудита v1.3.2 обнаружено: **LangSmith sandbox уже в `.venv`** (`.venv/Lib/site-packages/langsmith/sandbox/`) как транзитивная зависимость — zero-cost fallback без E2B API key. Для полноценной изоляции (Firecracker microVMs, 24h sessions) используется [e2b-dev/code-interpreter](https://github.com/e2b-dev/code-interpreter) (2.3k⭐, Apache-2.0, ~150ms startup).

**Отвергнуто:** Daytona (72k⭐, AGPL-3.0) — AGPL блокер для enterprise.

Фаза 5 вводит abstract `SandboxBackend` с тремя implementations (pluggable), feature flag для включения per-скиллу, graceful degradation при отсутствии API ключей.

---

## ## ADDED REQ-1: SandboxBackend абстрактный интерфейс

**Файл:** `src/pdf_framework/sandbox/base.py` (новый)

Abstract base class с четырьмя методами для исполнения кода в изолированном окружении.

### API

```python
# src/pdf_framework/sandbox/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SandboxExecutionResult:
    success: bool
    stdout: str
    stderr: str
    return_value: Any  # serialized (json-able) or repr()
    execution_time_s: float
    error: str | None = None


class SandboxBackend(ABC):
    """Abstract backend for sandboxed Python code execution."""

    @property
    @abstractmethod
    def backend_name(self) -> str:
        """e.g. 'e2b', 'langsmith', 'dry-run'."""

    @abstractmethod
    async def execute(
        self,
        code: str,
        timeout_s: int = 30,
        env: dict[str, str] | None = None,
    ) -> SandboxExecutionResult:
        """Execute Python code in sandbox. Return result."""

    @abstractmethod
    async def install(self, package: str) -> bool:
        """Install Python package in sandbox (pip install). True on success."""

    @abstractmethod
    async def upload(self, local_path: Path, remote_path: str) -> None:
        """Upload file to sandbox filesystem."""

    @abstractmethod
    async def download(self, remote_path: str, local_path: Path) -> None:
        """Download file from sandbox to local."""

    @abstractmethod
    async def cleanup(self) -> None:
        """Release sandbox resources (kill container, close session)."""
```

### Сценарий 1: Abstract compliance

**Given** концептуальный `SandboxBackend` subclass реализует все 4 method + 2 property
**When** `SandboxBackend.__subclasshook__` проверяется
**Then** `isinstance(instance, SandboxBackend) == True`
**And** `instance.backend_name` возвращает valid string

### Сценарий 2: Неполная реализация отклоняется

**Given** subclass реализует только `execute()` и `backend_name`, но не `install/upload/download/cleanup`
**When** `BadBackend()` создаётся
**Then** `TypeError: Can't instantiate abstract class BadBackend with abstract methods ...`

### Граничные условия

- `execute(code="")` → SandboxExecutionResult(success=True, stdout="", return_value=None)
- `execute(code=None)` → TypeError
- `timeout_s <= 0` → ValueError "timeout must be positive"
- `env` содержит reserved vars (PATH, HOME) → merge, не replace

---

## ## ADDED REQ-2: E2BBackend (production)

**Файл:** `src/pdf_framework/sandbox/e2b_backend.py` (новый)

Production implementation используя `e2b-code-interpreter` SDK.

### API

```python
# src/pdf_framework/sandbox/e2b_backend.py
import os
from pathlib import Path
from typing import Any

from e2b_code_interpreter import CodeInterpreter

from src.pdf_framework.sandbox.base import SandboxBackend, SandboxExecutionResult


class E2BBackend(SandboxBackend):
    def __init__(self, api_key: str | None = None, timeout_s: int = 300):
        self._api_key = api_key or os.environ["E2B_API_KEY"]
        self._session_timeout_s = timeout_s
        self._interpreter: CodeInterpreter | None = None

    @property
    def backend_name(self) -> str:
        return "e2b"

    async def _ensure_session(self) -> CodeInterpreter:
        if self._interpreter is None:
            self._interpreter = CodeInterpreter.create(
                api_key=self._api_key,
                timeout=self._session_timeout_s,
            )
        return self._interpreter

    async def execute(
        self,
        code: str,
        timeout_s: int = 30,
        env: dict[str, str] | None = None,
    ) -> SandboxExecutionResult:
        interp = await self._ensure_session()
        start = time.monotonic()
        try:
            exec_result = interp.notebook.exec_cell(code, timeout_s=timeout_s)
            elapsed = time.monotonic() - start
            return SandboxExecutionResult(
                success=not exec_result.error,
                stdout="\n".join(exec_result.logs.stdout),
                stderr="\n".join(exec_result.logs.stderr),
                return_value=exec_result.results[0].text if exec_result.results else None,
                execution_time_s=elapsed,
                error=str(exec_result.error) if exec_result.error else None,
            )
        except TimeoutError as e:
            return SandboxExecutionResult(
                success=False, stdout="", stderr="",
                return_value=None, execution_time_s=timeout_s,
                error=f"Timeout after {timeout_s}s",
            )

    async def install(self, package: str) -> bool:
        result = await self.execute(f"!pip install {package}", timeout_s=120)
        return result.success

    async def cleanup(self) -> None:
        if self._interpreter:
            self._interpreter.close()
            self._interpreter = None
```

### Сценарий 1: Successful code execution

**Given** `E2B_API_KEY` установлен, E2B сервис доступен
**And** `backend = E2BBackend()`
**When** `result = await backend.execute("x = 1 + 1; print(x)")`
**Then** `result.success == True`
**And** `result.stdout == "2\n"`
**And** `result.execution_time_s < 1.0`
**And** `result.error is None`

### Сценарий 2: Timeout enforcement

**Given** `backend.execute("import time; time.sleep(60)", timeout_s=5)`
**When** 5 секунд проходит
**Then** `SandboxExecutionResult(success=False, error="Timeout after 5s")`
**And** sandbox session **не убита** (reused for next call)

### Сценарий 3: Destructive code isolated

**Given** `code = "import os; os.system('rm -rf /')"` (имитация атаки)
**When** `backend.execute(code)` выполняется
**Then** код удаляет файлы **только в sandbox VM**
**And** host filesystem **нетронут**
**And** next session starts clean

### Граничные условия

- `E2B_API_KEY` не установлен → `RuntimeError("E2B_API_KEY env var required")` при инициализации
- E2B service down → retry 1 раз через existing `retry.py`, затем `SandboxExecutionResult(error="E2B unreachable")`
- Session expired (>24h) → автоматический recreate через `_ensure_session()`
- Package install fail → `install()` возвращает `False`, не exception
- Concurrent `execute()` calls → один session shared, FIFO queue (не параллель)
- Cost limit (daily budget) → enforced через `budget_guard` env var `E2B_DAILY_LIMIT_USD`

### Ссылки

- `e2b-code-interpreter` PyPI package
- `src/memory/infrastructure/retry.py` — existing retry logic
- `src/memory/infrastructure/circuit_breaker.py` — for E2B failure isolation
- [e2b-dev/code-interpreter](https://github.com/e2b-dev/code-interpreter)

---

## ## ADDED REQ-3: LangSmithBackend (zero-cost fallback)

**Файл:** `src/pdf_framework/sandbox/langsmith_backend.py` (новый)

Alternative implementation используя `langsmith.sandbox` (уже установлен как транзитивная зависимость).

**Important:** LangSmith sandbox не даёт Firecracker isolation — это subprocess-based sandbox с resource limits, подходящий для trusted code (research scripts, eval). Для untrusted code → E2BBackend.

### API

```python
# src/pdf_framework/sandbox/langsmith_backend.py
from langsmith.sandbox import LangSmithSandbox  # already installed

from src.pdf_framework.sandbox.base import SandboxBackend, SandboxExecutionResult


class LangSmithBackend(SandboxBackend):
    @property
    def backend_name(self) -> str:
        return "langsmith"

    async def execute(
        self, code: str, timeout_s: int = 30, env: dict[str, str] | None = None
    ) -> SandboxExecutionResult:
        # Subprocess-based execution with resource limits
        ...
```

### Сценарий 1: Zero-config usage

**Given** `E2B_API_KEY` не установлен
**And** `LangSmithBackend` выбран как fallback
**When** `await backend.execute("print('hello')")`
**Then** работает без внешних API
**And** `result.stdout == "hello\n"`

### Граничные условия

- LangSmith sandbox не доступен (старая версия langsmith) → fallback на `DryRunBackend`
- Resource limit exceeded (memory > 512MB) → subprocess killed, `error="Memory limit"`
- Trust level warning: log warning `[SANDBOX] LangSmith backend is subprocess-based, not VM-isolated. For untrusted code use E2B.`

### Ссылки

- `.venv/Lib/site-packages/langsmith/sandbox/` — уже установлено

---

## ## ADDED REQ-4: DryRunBackend (development / CI)

**Файл:** `src/pdf_framework/sandbox/dry_run_backend.py` (новый)

Локальный subprocess-based "sandbox" для разработки и CI — **без реальной изоляции**, но с API-compatible интерфейсом. Используется когда ни E2B, ни LangSmith недоступны.

### API

```python
# src/pdf_framework/sandbox/dry_run_backend.py
import asyncio
import subprocess
from src.pdf_framework.sandbox.base import SandboxBackend, SandboxExecutionResult


class DryRunBackend(SandboxBackend):
    @property
    def backend_name(self) -> str:
        return "dry-run"

    async def execute(
        self, code: str, timeout_s: int = 30, env: dict[str, str] | None = None
    ) -> SandboxExecutionResult:
        proc = await asyncio.create_subprocess_exec(
            "python", "-c", code,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout_s)
            return SandboxExecutionResult(
                success=(proc.returncode == 0),
                stdout=stdout.decode(),
                stderr=stderr.decode(),
                return_value=None,
                execution_time_s=0.0,  # not measured
            )
        except asyncio.TimeoutError:
            proc.kill()
            return SandboxExecutionResult(
                success=False, stdout="", stderr="",
                return_value=None, execution_time_s=timeout_s,
                error="Timeout",
            )
```

### Сценарий 1: Dev workflow без E2B ключа

**Given** developer локально без E2B API key
**And** `settings.sandbox.backend == "dry-run"` в `.env`
**When** research-skill вызывает `sandbox.execute(code)`
**Then** код исполняется на хост-машине (trusted dev env)
**And** result корректен
**And** warning log: `[SANDBOX] Using DryRunBackend — NO ISOLATION, dev mode only`

### Граничные условия

- Код пытается `os.system('rm -rf ...')` → **выполнится на хосте!** (warning в docs)
- Exception в коде → `success=False`, stderr содержит traceback
- CI environment → `DryRunBackend` допустим только если код trusted (наши own scripts)

### Ссылки

- `.env.example` — добавить `SANDBOX__BACKEND=dry-run` как default
- `src/pdf_framework/config/infrastructure.py` — `SandboxSettings` новый subsection

---

## ## ADDED REQ-5: Sandbox factory + configuration

**Файл:** `src/pdf_framework/sandbox/__init__.py` (новый)

Factory function для выбора backend на основе settings, с fallback цепочкой: `e2b → langsmith → dry-run`.

### API

```python
# src/pdf_framework/sandbox/__init__.py
from src.pdf_framework.config import Settings
from src.pdf_framework.sandbox.base import SandboxBackend, SandboxExecutionResult

__all__ = ["SandboxBackend", "SandboxExecutionResult", "get_sandbox"]


def get_sandbox(settings: Settings) -> SandboxBackend:
    """Factory: select backend by settings + fallback chain.

    Priority:
        1. settings.sandbox.backend == "e2b" AND E2B_API_KEY set → E2BBackend
        2. settings.sandbox.backend == "langsmith" → LangSmithBackend
        3. settings.sandbox.backend == "dry-run" OR fallback → DryRunBackend
    """
    backend_pref = settings.sandbox.backend
    if backend_pref == "e2b" and settings.sandbox.e2b_api_key:
        from src.pdf_framework.sandbox.e2b_backend import E2BBackend
        return E2BBackend(api_key=settings.sandbox.e2b_api_key)
    if backend_pref == "langsmith":
        try:
            from src.pdf_framework.sandbox.langsmith_backend import LangSmithBackend
            return LangSmithBackend()
        except ImportError:
            logger.warning("LangSmith sandbox unavailable, falling back to dry-run")
    from src.pdf_framework.sandbox.dry_run_backend import DryRunBackend
    return DryRunBackend()
```

### Sandbox settings

```python
# src/pdf_framework/config/infrastructure.py (extension)
from typing import Literal
from pydantic import BaseModel, Field


class SandboxSettings(BaseModel):
    backend: Literal["e2b", "langsmith", "dry-run"] = "dry-run"
    e2b_api_key: str | None = Field(default=None, alias="E2B_API_KEY")
    timeout_default_s: int = 30
    daily_budget_usd: float = 5.0  # E2B only
    max_concurrent_sessions: int = 3
```

### Сценарий 1: Production → E2B

**Given** `.env: SANDBOX__BACKEND=e2b`, `E2B_API_KEY=...`
**When** `get_sandbox(settings)` вызывается
**Then** возвращается `E2BBackend` instance
**And** `backend.backend_name == "e2b"`

### Сценарий 2: CI → DryRun fallback

**Given** `.env: SANDBOX__BACKEND=e2b` но `E2B_API_KEY` не установлен
**When** `get_sandbox(settings)` вызывается
**Then** возвращается `DryRunBackend` (fallback)
**And** warning log: `[SANDBOX] E2B requested but key missing, falling back to dry-run`

### Граничные условия

- `backend_pref` — invalid value → default to `dry-run`
- Все 3 backend недоступны → `RuntimeError("No sandbox backend available")` (не должно случиться, dry-run всегда работает)
- Concurrent sessions limit exceeded → queue FIFO

### Ссылки

- `src/pdf_framework/config/infrastructure.py` — extension с `SandboxSettings`
- `src/pdf_framework/config/__init__.py` — re-export
- `.env.example` — добавить sandbox section

---

## ## ADDED REQ-6: Research skills integration

**Файл:** `.claude/skills/sandbox-execution/SKILL.md` (новый)

Новый skill `sandbox-execution` описывает паттерн использования `SandboxBackend` из research workflows.

### Usage pattern

```python
# Example: architecture-research skill использует sandbox для eval
from src.pdf_framework.sandbox import get_sandbox
from src.pdf_framework.config import get_settings

async def run_benchmark_in_sandbox(script: str) -> dict:
    sandbox = get_sandbox(get_settings())
    try:
        result = await sandbox.execute(script, timeout_s=60)
        return {
            "success": result.success,
            "stdout": result.stdout,
            "elapsed": result.execution_time_s,
        }
    finally:
        await sandbox.cleanup()
```

### Граничные условия для research контекста

- Research-skill генерирует code (via LLM) → **всегда через sandbox**, не eval locally
- Long-running benchmarks → session reused через `_ensure_session()`
- Cost accounting → logs в `docs/wiki/log.md` через `WikiPromoter` (Фаза 3)

---

## Регрессия

Фаза 5 **НЕ ДОЛЖНА** ломать:

- [ ] Existing tests (`tests/unit/`, `tests/integration/`) — они не используют sandbox
- [ ] Existing research scripts (`scripts/eval_*.py`) — они продолжают работать на хосте, постепенно мигрируются
- [ ] `src/shared/llm_rotation/` — не затрагивается
- [ ] Ralph Wiggum state files в `shared/ralph_state.py` — не затрагиваются (sandbox orthogonal)

## Новые тесты

```
tests/unit/pdf_framework/sandbox/
  test_base.py                    — SandboxBackend abstract compliance
  test_dry_run_backend.py         — subprocess execution, timeout, env vars
  test_langsmith_backend.py       — LangSmith integration (если установлен)
  test_factory.py                 — get_sandbox() fallback chain

tests/integration/
  test_e2b_backend.py             — real E2B integration (skipped без API key)
  test_sandbox_research_flow.py   — research skill using sandbox E2E
```

**Coverage target:** `base.py` ≥95%, `dry_run_backend.py` ≥90%. E2B tests optional (require API key + cost).
