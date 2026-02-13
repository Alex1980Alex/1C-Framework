@echo off
chcp 65001 >nul
REM ========================================
REM  Запуск UI сервера (Gradio)
REM  Просто дважды кликните этот файл!
REM  Автоперезапуск при нажатии кнопки в UI
REM ========================================

set "SCRIPT_DIR=%~dp0"
call "%SCRIPT_DIR%.venv\Scripts\activate.bat"

:loop
echo.
echo  PDF Vector ^& Graph Framework - UI
echo  ====================================
echo  Для остановки: Ctrl+C
echo  Перезапуск: кнопка в Настройки -^> Сервер
echo.

pdf-framework ui

if %errorlevel% equ 42 (
    echo.
    echo  [Перезапуск сервера...]
    echo.
    timeout /t 2 /nobreak >nul
    goto loop
)

echo.
echo  Сервер остановлен.
pause
