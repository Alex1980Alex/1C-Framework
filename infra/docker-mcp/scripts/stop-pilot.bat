@echo off
REM Docker MCP Pilot - Stop Script
REM Phase 1: Proof of Concept
REM Date: 2026-01-04

setlocal enabledelayedexpansion

echo ========================================
echo Docker MCP Pilot - Stopping...
echo ========================================
echo.

REM Change to project directory
cd /d "%~dp0..\"

echo [INFO] Current directory: %CD%
echo.

REM Stop pilot services
echo [INFO] Stopping pilot MCP services...
echo.

docker-compose down

if errorlevel 1 (
    echo.
    echo [WARNING] Some services may not have stopped properly.
    echo You can force stop with: docker-compose down -v
)

echo.
echo ========================================
echo Docker MCP Pilot - Stopped!
echo ========================================
echo.
echo All containers stopped.
echo.

REM Optional: Remove volumes
echo [OPTIONAL] Remove volumes? (This will delete data!)
set /p confirm="Remove volumes? (y/N): "
if /i "!confirm!"=="y" (
    echo.
    echo [INFO] Removing volumes...
    docker-compose down -v
    echo.
    echo Volumes removed.
)

echo.
pause
