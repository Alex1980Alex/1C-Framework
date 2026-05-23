@echo off
echo === Killing rphost ===
taskkill /F /IM rphost.exe /T
timeout /t 8 /nobreak >nul
echo === New rphost (auto-spawned) ===
tasklist /FI "IMAGENAME eq rphost.exe"
timeout /t 3 /nobreak >nul
