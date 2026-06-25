#!/usr/bin/env python3
"""Launcher mcp-yaxunit-runner с кредами из .env (безопасность: НЕ хранить пароль в трекаемом конфиге).

Читает ONEC_DB_USER / ONEC_DB_PWD (+ опц. ONEC_V8_PATH / ONEC_TEST_CONN) из gitignored .env и
запускает java -jar runner. stdio passthrough. Запускается из .mcp профилей вместо хардкода creds.
"""
import os
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
try:
    from _dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

repo = pathlib.Path(__file__).resolve().parent.parent
java = r"C:\Program Files\1C\1CE\components\axiom-jdk-full-17.0.16+12-x86_64\bin\java.exe"
jar = str(repo / "tools" / "mcp-jars" / "mcp-yaxunit-runner-0.5.1.jar")
v8 = os.environ.get("ONEC_V8_PATH", r"C:\Program Files (x86)\1cv8\8.3.27.1936")
conn = os.environ.get("ONEC_TEST_CONN", 'Srvr="KOMPUTER";Ref="TestDB"')
user = os.environ.get("ONEC_DB_USER", "")
pwd = os.environ.get("ONEC_DB_PWD", "")
cmd = [java, "-Dfile.encoding=UTF-8", "-jar", jar, "--v8-path", v8,
       "--connection-string", conn, "--db-user", user, "--db-pwd", pwd]
sys.exit(subprocess.run(cmd).returncode)