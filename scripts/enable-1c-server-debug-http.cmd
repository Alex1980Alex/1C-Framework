@echo off
rem GKSTCPLK-2468: switch 1C server debug to HTTP protocol (was TCP-only with -debug alone)

echo === Stopping 1C Server Agent ===
sc.exe stop "1C:Enterprise 8.3 Server Agent"
timeout /t 4 /nobreak >nul

echo.
echo === Updating binPath to -debug -http ===
sc.exe config "1C:Enterprise 8.3 Server Agent" binPath= "\"C:\Program Files (x86)\1cv8\8.3.27.1936\bin\ragent.exe\" -srvc -agent -regport 1541 -port 1540 -range 1560:1591 -debug -http -d \"C:\Program Files (x86)\1cv8\srvinfo\""

echo.
echo === Starting 1C Server Agent ===
sc.exe start "1C:Enterprise 8.3 Server Agent"

echo.
echo === Verify ===
sc.exe qc "1C:Enterprise 8.3 Server Agent"

echo === DONE ===
timeout /t 4 /nobreak >nul
