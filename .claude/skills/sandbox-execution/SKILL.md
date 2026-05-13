---
name: sandbox-execution
description: "Sandbox для исполнения сгенерированного агентом кода (Python). Изоляция через LangSmith/E2B/dry-run backends. Триггеры: 'sandbox', 'песочница', 'execute code agent', 'sandboxed execution', 'LangSmith sandbox', 'E2B', 'DryRunBackend', 'SandboxBackend'. НЕ для запуска тестов фреймворка (используй pytest), НЕ для отладки BSL кода (используй 1c-debug-hmr)."
---

# sandbox-execution — изолированное исполнение agent-generated кода

## Зачем нужен

Когда research/analytical агент генерирует код и хочет выполнить его (например, `architecture-research` строит прототип, `tech-research` валидирует API через пример) — НЕ запускать его в основном процессе. Sandbox изолирует:

- Файловую систему (write только в `/tmp` песочницы)
- Зависимости (отдельный pip env)
- Сеть (по умолчанию запрещена; explicit allowlist для paid backends)
- CPU/memory (timeout 30s, soft RAM limit)

Без sandbox-а агентный exec эквивалентен `eval()` в production — компрометация = compromise всего фреймворка.

## Архитектура

```
SandboxBackend (ABC, src/pdf_framework/sandbox/base.py)
  │
  ├─ DryRunBackend          — zero-dep, no-execute, records calls
  ├─ LangSmithBackend        — TODO Ф5 (default once API key configured)
  └─ E2BBackend              — TODO Ф5 (paid alternative, full sandbox)
```

### Контракт ABC

```python
from src.pdf_framework.sandbox import SandboxBackend, SandboxResult, SandboxQuotaExceeded
from pathlib import Path

# 5 abstract async methods
class SandboxBackend(ABC):
    async def execute(self, code: str, language: str = "python", timeout: float = 30.0) -> SandboxResult: ...
    async def install(self, packages: list[str]) -> None: ...
    async def upload(self, local_path: Path, remote_path: str) -> None: ...
    async def download(self, remote_path: str, local_path: Path) -> None: ...
    async def close(self) -> None: ...

# Result dataclass
@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_seconds: float
    truncated: bool          # True if output > ~100 KB and was cut

# Exception
class SandboxQuotaExceeded(Exception): ...  # raised on 51st execute() call
```

## DryRunBackend — fallback и contract tester

```python
from src.pdf_framework.sandbox import DryRunBackend

backend = DryRunBackend()
result = await backend.execute("print('hello')")
# SandboxResult(stdout="[dry-run] code not executed", stderr="", exit_code=0, ...)

# All calls recorded for introspection
backend.calls  # → [{"method": "execute", "args": {"code": "print('hello')", ...}}]

# Quota: 50 execute() ok, 51st raises
for _ in range(50):
    await backend.execute("...")
try:
    await backend.execute("...")  # 51st
except SandboxQuotaExceeded:
    print("hit quota")
```

**Когда использовать:**
- Zero-cost CI: smoke-test код, который вызывает sandbox, не платя за E2B
- Local development без API ключей
- Unit-тесты высокоуровневого кода (mocking sandbox через DryRun)
- Валидация call-shape перед платным запуском

## Будущие backends (Ф5 pending)

### LangSmithBackend (default once API key configured)

Бесплатный (LangSmith free tier), интегрирован в LangChain ecosystem. Требует `LANGSMITH_API_KEY` в env. Запускает код в LangSmith trace-context — побочный профит: trace доступен для debug.

### E2BBackend (paid alternative)

[E2B](https://e2b.dev) — полноценная Firecracker VM. Дороже, но изолирует **полностью** (включая kernel-level). Требует `E2B_API_KEY` + платный план. Используй когда:
- Код может писать в произвольные пути
- Код устанавливает arbitrary pip packages
- Нужна сетевая изоляция (E2B по умолчанию режет outbound)

## Интеграция в агенты (TODO Ф5)

```python
# В будущем (architecture-research / tech-research):
from src.pdf_framework.sandbox import DryRunBackend, LangSmithBackend

async def execute_prototype(code: str) -> SandboxResult:
    # Select backend by env presence
    if os.getenv("LANGSMITH_API_KEY"):
        backend = LangSmithBackend()
    else:
        backend = DryRunBackend()  # fallback for CI/local
    try:
        return await backend.execute(code, timeout=30.0)
    finally:
        await backend.close()
```

## Тестирование своего кода с моком sandbox-а

```python
import pytest
from src.pdf_framework.sandbox import DryRunBackend

async def my_agent_function(sandbox: SandboxBackend, code: str):
    result = await sandbox.execute(code)
    return result.stdout

@pytest.mark.asyncio
async def test_agent_invokes_sandbox():
    sandbox = DryRunBackend()
    output = await my_agent_function(sandbox, "print('test')")
    assert output == "[dry-run] code not executed"
    assert sandbox.calls[0]["method"] == "execute"
```

## Файлы

| Файл | Назначение |
|---|---|
| `src/pdf_framework/sandbox/base.py` | ABC + SandboxResult + SandboxQuotaExceeded |
| `src/pdf_framework/sandbox/dry_run_backend.py` | Zero-dep fallback impl |
| `src/pdf_framework/sandbox/__init__.py` | Public API re-exports |
| `tests/unit/pdf_framework/sandbox/test_dry_run_backend.py` | 13 contract tests |
| (TODO) `src/pdf_framework/sandbox/langsmith_backend.py` | Ф5 task 1-2 |
| (TODO) `src/pdf_framework/sandbox/e2b_backend.py` | Ф5 task 3-4 |

## Связано

- `openspec/changes/hermes-llm-wiki/tasks.md` §Фаза 5 — полный roadmap
- Commit `9b392c465` — skeleton landing
- `agent-orchestration` — где integration с research-agents произойдёт
