@echo off
REM Docker MCP Pilot - Status Check Script
REM Phase 1: Proof of Concept
REM Date: 2026-01-04

setlocal enabledelayedexpansion

echo ========================================
echo Docker MCP Pilot - Status
echo ========================================
echo.

REM Check if Docker is running
docker ps >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Docker is not running!
    pause
    exit /b 1
)

echo [INFO] Container Status:
echo.
docker ps --filter "name=mcp-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo.

echo [INFO] Container Health:
echo.
docker ps --filter "name=mcp-" --format "{{.Names}}: {{.Health}}" 2>nul
echo.

echo [INFO] Resource Usage:
echo.
docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" --filter "name=mcp-"
echo.

echo [INFO] Recent Logs (last 5 lines per container):
echo.
for /f %%i in ('docker ps --filter "name=mcp-" --format "{{.Names}}"') do (
    echo ======== %%i ========
    docker logs --tail 5 %%i 2>&1
    echo.
)

echo ========================================
echo Quick Actions:
echo ========================================
echo - View logs: docker-compose logs -f
echo - Restart: docker-compose restart
echo - Stop: scripts\stop-pilot.bat
echo.

pause
