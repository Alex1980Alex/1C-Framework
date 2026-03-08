@echo off
REM Docker MCP Pilot - Start Script
REM Phase 1: Proof of Concept
REM Date: 2026-01-04

setlocal enabledelayedexpansion

echo ========================================
echo Docker MCP Pilot - Starting...
echo ========================================
echo.

REM Check if Docker is running
docker ps >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

echo [INFO] Docker is running
echo.

REM Change to project directory
cd /d "%~dp0..\"

echo [INFO] Current directory: %CD%
echo.

REM Check if data directory exists
if not exist "D:\1C-Enterprise_Framework\data" (
    echo [INFO] Creating data directory...
    mkdir "D:\1C-Enterprise_Framework\data"
)

REM Start pilot services
echo [INFO] Starting pilot MCP services...
echo.

docker-compose up -d

if errorlevel 1 (
    echo.
    echo [ERROR] Failed to start services!
    echo Check docker-compose.yml for errors.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Docker MCP Pilot - Started!
echo ========================================
echo.
echo Services:
docker-compose ps
echo.

REM Wait for health checks
echo [INFO] Waiting for services to be healthy (30 seconds)...
timeout /t 30 /nobreak >nul

echo.
echo [INFO] Checking service health...
docker ps --filter "name=mcp-" --format "table {{.Names}}\t{{.Status}}"
echo.

echo ========================================
echo Next steps:
echo ========================================
echo 1. Check logs: docker-compose logs -f
echo 2. View logs UI: docker-compose --profile monitoring up -d
echo    Then open: http://localhost:8080
echo 3. Stop services: scripts\stop-pilot.bat
echo.

pause
