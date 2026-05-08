@echo off
rem Full restart of 1C Server Agent — drops rphost cache,
rem forces recompilation of modules without disabled extensions.

echo === Stopping 1C Server Agent ===
sc.exe stop "1C:Enterprise 8.3 Server Agent"
timeout /t 5 /nobreak >nul

echo.
echo === Starting 1C Server Agent ===
sc.exe start "1C:Enterprise 8.3 Server Agent"

echo.
echo === Waiting 10s for cluster ===
timeout /t 10 /nobreak >nul

echo.
echo === Status ===
sc.exe query "1C:Enterprise 8.3 Server Agent"

echo === DONE ===
timeout /t 3 /nobreak >nul
