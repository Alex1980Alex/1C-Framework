#!/usr/bin/env python3
"""Launcher для SonarQube MCP Server (docker) с кредами из НАШЕГО .env (ADR-042).

Единый источник секрета: читает SONAR_TOKEN/SONAR_HOST_URL (наши имена) из gitignored .env и
маппит в SONARQUBE_TOKEN/SONARQUBE_URL (имена, которые ждёт образ sonarsource/sonarqube-mcp).
localhost/127.0.0.1 → host.docker.internal (из контейнера host-loopback недостижим). stdio passthrough.
Запускается lazy-mcp (категория code-quality). Не печатает токен.
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

url = os.environ.get("SONAR_HOST_URL", "http://localhost:9000")
url = url.replace("localhost", "host.docker.internal").replace("127.0.0.1", "host.docker.internal")
tok = os.environ.get("SONAR_TOKEN", "")
image = "sonarsource" + "/" + "sonarqube-mcp"
cmd = ["docker", "run", "-i", "--rm",
       "-e", "SONARQUBE_URL=" + url,
       "-e", "SONARQUBE_TOKEN=" + tok,
       image]
sys.exit(subprocess.run(cmd).returncode)