#!/usr/bin/env python3
"""Минимальный stdlib .env-загрузчик (zero-dep) для gitignored секретов (напр. SONAR_TOKEN).

Заполняет os.environ из <repo>/.env. **env > .env**: уже заданные переменные НЕ перезаписываются
(User/process env приоритетнее). Используется sonar_*.py. .env защищён .gitignore (секреты не в git).
"""

import os
from pathlib import Path


def load_dotenv(path: str | None = None) -> int:
    """KEY=VALUE из .env → os.environ (без перезаписи существующих). Возврат — число установленных
    ключей. best-effort: нет файла / ошибка → 0 (не кидает). Кавычки вокруг значения снимаются."""
    p = Path(path) if path else (Path(__file__).resolve().parent.parent / ".env")
    n = 0
    try:
        if not p.is_file():
            return 0
        for raw in p.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip()
            # снимаем кавычки ТОЛЬКО парой по краям (KEY="value" → value); иначе значения
            # с внутренними кавычками (connection-строки Srvr="x";Ref="y") теряли закрывающую "
            if len(val) >= 2 and val[0] == val[-1] and val[0] in ('"', "'"):
                val = val[1:-1]
            if key and key not in os.environ:
                os.environ[key] = val
                n += 1
    except Exception:
        return n
    return n
