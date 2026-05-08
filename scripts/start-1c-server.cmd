@echo off
echo === Killing zombie ragent if any ===
taskkill /F /IM ragent.exe /T 2>nul

timeout /t 3 /nobreak >nul

echo.
echo === Starting 1C Server Agent service ===
sc.exe start "1C:Enterprise 8.3 Server Agent"

timeout /t 8 /nobreak >nul

echo.
echo === Status ===
sc.exe query "1C:Enterprise 8.3 Server Agent"

timeout /t 3 /nobreak >nul
