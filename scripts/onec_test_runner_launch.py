#!/usr/bin/env python3
"""Launcher mcp-yaxunit-runner (jar v0.5.1) — генерит Spring app-config из .env и запускает jar.

⚠ jar v0.5.1 (alkoleft) конфигурируется ТОЛЬКО Spring-профилем `app.*`
(base-path / source-set / connection / platform-version / tools.builder), а НЕ CLI-флагами
`--v8-path`/`--connection-string` (их в jar нет — Spring их игнорирует → basePath=null → краш).

Поэтому launcher: читает креды/строку подключения из gitignored .env, генерит application.yml
в gitignored .runtime/ (секреты НЕ в git), запускает jar с --spring.config.additional-location
(профиль mcp остаётся дефолтным).

ENV (.env): ONEC_TEST_CONN, ONEC_DB_USER, ONEC_DB_PWD, ONEC_V8_PATH,
            ONEC_PLATFORM_VERSION (опц.), ONEC_RUNNER_BASE_PATH (опц.)
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

conn = os.environ.get("ONEC_TEST_CONN", r"File='C:\onec-test-bases\TM_UnitTest';")
user = os.environ.get("ONEC_DB_USER", "")
pwd = os.environ.get("ONEC_DB_PWD", "")
v8 = os.environ.get("ONEC_V8_PATH", r"C:\Program Files (x86)\1cv8\8.3.27.1936")
platform_version = os.environ.get("ONEC_PLATFORM_VERSION") or pathlib.Path(v8).name
base_path = os.environ.get("ONEC_RUNNER_BASE_PATH", str(repo))


def yq(value: str) -> str:
    """Экранирование для YAML double-quoted скаляра (backslash, двойная кавычка)."""
    return value.replace("\\", "\\\\").replace('"', '\\"')


# source-set: CONFIGURATION (Designer-дамп конфигурации в .runtime/config-src — раннер ТРЕБУЕТ
# запись типа CONFIGURATION) + 2 Designer-расширения. base-path=репо покрывает оба корня.
# .runtime/config-src — Designer-выгрузка рабочей ИБ (gitignored; основная конфиг в репо хранится
# в EDT-формате, его в Designer-source-set класть нельзя). builder=DESIGNER собирает всё в ИБ.
cfg_dir = repo / "tools" / "mcp-jars" / ".runtime"
cfg_dir.mkdir(parents=True, exist_ok=True)
yml = cfg_dir / "application.yml"
yml.write_text(
    f"""# СГЕНЕРИРОВАНО onec_test_runner_launch.py из .env — НЕ редактировать (gitignored).
app:
  id: tm
  format: DESIGNER
  base-path: "{yq(base_path)}"
  source-set:
    - path: "tools/mcp-jars/.runtime/config-src"
      name: tm-config
      type: "CONFIGURATION"
      purpose: ["MAIN"]
    - path: "src/bsl/exts/YAXUNIT"
      name: yaxunit
      type: "EXTENSION"
      purpose: ["MAIN", "YAXUNIT"]
    - path: "src/bsl/exts/UnitTests"
      name: tests
      type: "EXTENSION"
      purpose: ["TESTS", "YAXUNIT"]
  connection:
    connection-string: "{yq(conn)}"
    user: "{yq(user)}"
    password: "{yq(pwd)}"
  platform-version: "{yq(platform_version)}"
  tools:
    builder: DESIGNER
    enterprise:
      # Headless-исполнение тонкого клиента (доказано live 2026-06-26):
      #  - БЕЗ /TESTMANAGER — это режим менеджера UI-тестов, клиент висит в ожидании
      #    подключения тест-клиента и не исполняет RunUnitTests (прежний "сел в простой").
      #  - /DisableStartupDialogs + /DisableStartupMessages — иначе стартовый диалог
      #    БСП (первый запуск / обновление ИБ) блокирует прогон до &После-обработчика.
      # Доп.требование (вне launcher): расширение YAXUNIT должно быть подключено с
      # выключенным безопасным режимом — иначе чтение config.json запрещено
      # (ЮТПараметрыЗапускаСлужебный: "Расширение подключено в безопасном режиме").
      additional-launch-keys: ["/DisableStartupDialogs", "/DisableStartupMessages"]
""",
    encoding="utf-8",
)

cmd = [
    java,
    "-Dfile.encoding=UTF-8",
    "-jar",
    jar,
    f"--spring.config.additional-location=file:{cfg_dir.as_posix()}/",
]
sys.exit(subprocess.run(cmd, cwd=str(repo)).returncode)
