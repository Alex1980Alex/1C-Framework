@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

rem === Node.js memory limit (OOM prevention) ===
if not defined NODE_OPTIONS (
    set "NODE_OPTIONS=--max-old-space-size=8192"
    echo [MEM] NODE_OPTIONS set to --max-old-space-size=8192
)

:menu
cls
echo +======================================================+
echo |        1C-Framework - Claude Code MCP Profiles        |
echo +======================================================+
echo |  1. pdf      - PDF RAG (~15k tokens)                 |
echo |  2. bsl      - 1C Development (~25k tokens)          |
echo |  3. full     - PDF + BSL + Memory (~45k tokens)      |
echo |  4. lazy-mcp - Auto-select (~5k tokens)              |
echo +------------------------------------------------------+
echo |  c. Continue last session (--continue)               |
echo |  r. Resume session (--resume)                        |
echo |  d. Diagnostics (Node.js heap stats)                 |
echo |  0. Exit                                             |
echo +======================================================+
echo   [MEM] NODE_OPTIONS=%NODE_OPTIONS%
echo.

set /p choice="Select profile [1-4, c, r, d, 0]: "

if "%choice%"=="1" set "profile=pdf"
if "%choice%"=="2" set "profile=bsl"
if "%choice%"=="3" set "profile=full"
if "%choice%"=="4" set "profile=lazy-mcp"
if "%choice%"=="0" exit /b 0

if "%choice%"=="c" (
    set /p cprofile="Profile to continue [1-4]: "
    if "!cprofile!"=="1" set "profile=pdf"
    if "!cprofile!"=="2" set "profile=bsl"
    if "!cprofile!"=="3" set "profile=full"
    if "!cprofile!"=="4" set "profile=lazy-mcp"
    set "extra=--continue"
    goto run
)

if "%choice%"=="r" (
    set /p rprofile="Profile to resume [1-4]: "
    if "!rprofile!"=="1" set "profile=pdf"
    if "!rprofile!"=="2" set "profile=bsl"
    if "!rprofile!"=="3" set "profile=full"
    if "!rprofile!"=="4" set "profile=lazy-mcp"
    set "extra=--resume"
    goto run
)

if "%choice%"=="d" (
    echo.
    echo === Node.js Heap Diagnostics ===
    echo NODE_OPTIONS=%NODE_OPTIONS%
    echo.
    node -e "const h=require('v8').getHeapStatistics();console.log('Heap limit:  '+(h.heap_size_limit/1024/1024).toFixed(0)+' MB');console.log('Heap used:   '+(h.used_heap_size/1024/1024).toFixed(0)+' MB');console.log('Heap total:  '+(h.total_heap_size/1024/1024).toFixed(0)+' MB');console.log('External:    '+(h.external_memory/1024/1024).toFixed(0)+' MB')"
    echo.
    echo --- OOM Recovery Tips ---
    echo   1. Start new session (don't --continue/--resume)
    echo   2. Use lazy-mcp profile (27 on-demand servers)
    echo   3. Increase limit: set NODE_OPTIONS=--max-old-space-size=16384
    echo.
    pause
    goto menu
)

if not defined profile (
    echo Invalid choice.
    timeout /t 2 >nul
    goto menu
)

:run
echo.
echo Starting Claude Code with profile: %profile%  [MEM: %NODE_OPTIONS%]
claude --strict-mcp-config --mcp-config "D:\1С-Framework\.mcp\%profile%.json" %extra% %*
