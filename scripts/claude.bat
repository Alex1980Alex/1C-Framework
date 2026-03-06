@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

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
echo |  0. Exit                                             |
echo +======================================================+
echo.

set /p choice="Select profile [1-4, c, r, 0]: "

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

if not defined profile (
    echo Invalid choice.
    timeout /t 2 >nul
    goto menu
)

:run
echo.
echo Starting Claude Code with profile: %profile%
claude --strict-mcp-config --mcp-config "D:\1С-Framework\.mcp\%profile%.json" %extra% %*
