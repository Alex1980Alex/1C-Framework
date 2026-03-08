@echo off
REM Lazy-MCP Startup Script
REM Запуск MCP сервера с динамической загрузкой

cd /d "%~dp0"

REM Проверка виртуального окружения
if exist ".venv\Scripts\python.exe" (
    echo [lazy-mcp] Using local venv
    .venv\Scripts\python.exe src\server.py %*
) else (
    echo [lazy-mcp] Using system Python
    python src\server.py %*
)
