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

## Production backends (Hermes Ф5 COMPLETE 2026-05-15)

### LangSmithBackend (GA May 2026)

Firecracker microVM через `langsmith[sandbox]` SDK. Требует `LANGSMITH_API_KEY`.

```python
from src.pdf_framework.sandbox import select_backend

backend = select_backend("langsmith")  # или "auto" если LANGSMITH_API_KEY set
result = await backend.execute("print('hello')", timeout=30.0)
await backend.close()
```

Преимущества: hardware-virtualized microVM (kernel isolation), Auth Proxy (секреты НЕ попадают в runtime), snapshots/copy-on-write forks (10 parallel branches ≈ стоимость одного), blueprints (cold-start reduction).

### E2BBackend (stateful Jupyter)

```python
from src.pdf_framework.sandbox import E2BBackend

backend = E2BBackend()  # E2B_API_KEY required
await backend.execute("x = 42")
result = await backend.execute("print(x * 2)")  # → "84" — variables persist!
await backend.close()
```

Уникальная фича — **stateful** Jupyter Kernel: переменные/импорты сохраняются между `execute` вызовами в рамках одного sandbox. Pricing: ~$0.10/час vCPU, pause-resume preserves state до 30 дней.

### Auto-selector

```python
from src.pdf_framework.sandbox import select_backend

# Order: prefer arg → LANGSMITH_API_KEY → E2B_API_KEY → DryRun fallback
backend = select_backend("auto")
```

## Интеграция в research-агенты

```python
from src.pdf_framework.sandbox import select_backend

async def execute_prototype(code: str) -> SandboxResult:
    backend = select_backend("auto")  # env-driven
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
| `src/pdf_framework/sandbox/langsmith_backend.py` | LangSmith microVM (F1, 2026-05-15) |
| `src/pdf_framework/sandbox/e2b_backend.py` | E2B Code Interpreter (F2, 2026-05-15) |
| `src/pdf_framework/sandbox/__init__.py` | Public API + `select_backend()` helper |
| `tests/unit/pdf_framework/sandbox/test_dry_run_backend.py` | 13 contract tests |
| `tests/unit/pdf_framework/sandbox/test_langsmith_backend.py` | 13 unit tests (mock-based) |
| `tests/unit/pdf_framework/sandbox/test_e2b_backend.py` | 12 unit tests + stateful Jupyter |

## Связано

- `openspec/changes/hermes-llm-wiki/tasks.md` §Фаза 5 — полный roadmap
- Commit `9b392c465` — skeleton landing
- `agent-orchestration` — где integration с research-agents произойдёт
