@echo off
echo [%date% %time%] lazy-mcp wrapper started >> D:\lazy-mcp-diag.log
echo [%date% %time%] ARGS: %* >> D:\lazy-mcp-diag.log
echo [%date% %time%] CWD: %CD% >> D:\lazy-mcp-diag.log
echo [%date% %time%] PYTHONIOENCODING: %PYTHONIOENCODING% >> D:\lazy-mcp-diag.log
"D:\1С-Framework\.venv\Scripts\python.exe" -u src/server.py %*
echo [%date% %time%] EXIT CODE: %ERRORLEVEL% >> D:\lazy-mcp-diag.log
