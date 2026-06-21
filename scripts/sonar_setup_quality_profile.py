#!/usr/bin/env python3
"""Идемпотентно создаёт кастомный BSL-профиль «1C BSL Way profile» (наследник
встроенного «BSL Language Server rules») и активирует ВСЕ default-off
1С-диагностики — режим МАКСИМАЛЬНОЙ проверки (жёсткие правила, 180/180).
Встроенный профиль read-only → нужен child. Zero-dep (urllib).
Auth: SONAR_TOKEN или admin:admin. ADR-033 (remediation).

Запуск: python scripts/sonar_setup_quality_profile.py
"""

import base64
import json
import os
import urllib.error
import urllib.parse
import urllib.request

HOST = os.environ.get("SONAR_HOST_URL", "http://localhost:9000")
TOKEN = os.environ.get("SONAR_TOKEN")
PARENT = "BSL Language Server rules"
CHILD = "1C BSL Way profile"
# ВСЕ 13 default-off правил BSL LS → максимальная проверка (180/180)
RULES = [
    # содержательные (баги/безопасность/перф/качество запросов)
    "bsl-language-server:FieldsFromJoinsWithoutIsNull",
    "bsl-language-server:MissingTempStorageDeletion",
    "bsl-language-server:UseSystemInformation",
    "bsl-language-server:DenyIncompleteValues",
    "bsl-language-server:UsingLikeInQuery",
    "bsl-language-server:CodeAfterAsyncCall",
    "bsl-language-server:FunctionOutParameter",
    "bsl-language-server:FileSystemAccess",
    "bsl-language-server:InternetAccess",
    # стилевые/конвенции (включаем для максимальной строгости)
    "bsl-language-server:BadWords",
    "bsl-language-server:FunctionNameStartsWithGet",
    "bsl-language-server:TernaryOperatorUsage",
    "bsl-language-server:TooManyReturns",
]


def call(path, post=None):
    req = urllib.request.Request(HOST.rstrip("/") + path)
    cred = f"{TOKEN}:" if TOKEN else "admin:admin"
    req.add_header("Authorization", "Basic " + base64.b64encode(cred.encode()).decode())
    data = None
    if post is not None:
        data = urllib.parse.urlencode(post).encode()
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, data=data, timeout=30) as r:
            body = r.read().decode()
            return r.status, (json.loads(body) if body.strip() else {})
    except urllib.error.HTTPError as e:
        return e.code, {"error": e.read().decode()[:200]}


def find_profile(name):
    _, d = call("/api/qualityprofiles/search?language=bsl")
    for p in d.get("profiles", []):
        if p.get("name") == name:
            return p
    return None


def main():
    parent = find_profile(PARENT)
    print(f"parent '{PARENT}': active={parent.get('activeRuleCount') if parent else 'NOT FOUND'}")
    child = find_profile(CHILD)
    if not child:
        st, d = call("/api/qualityprofiles/create", {"language": "bsl", "name": CHILD})
        print(f"create child: HTTP {st} {d.get('error', 'ok')}")
        child = find_profile(CHILD)
    else:
        print(f"child '{CHILD}': exists active={child.get('activeRuleCount')}")
    if not child:
        print("FATAL: child не создан")
        return
    key = child["key"]
    st, d = call(
        "/api/qualityprofiles/change_parent",
        {"qualityProfile": CHILD, "language": "bsl", "parentQualityProfile": PARENT},
    )
    print(f"change_parent: HTTP {st} {d.get('error', 'ok')}")
    ok = 0
    for rule in RULES:
        st, d = call("/api/qualityprofiles/activate_rule", {"key": key, "rule": rule})
        if st in (200, 204):
            ok += 1
        else:
            print(f"  ! {rule.split(':')[1]}: HTTP{st} {d.get('error', '')[:60]}")
    st, d = call("/api/qualityprofiles/set_default", {"qualityProfile": CHILD, "language": "bsl"})
    print(f"set_default: HTTP {st} {d.get('error', 'ok')}")
    res = find_profile(CHILD)
    print(
        f"RESULT: '{CHILD}' active={res.get('activeRuleCount')} default={res.get('isDefault')} (activated {ok}/{len(RULES)})"
    )


if __name__ == "__main__":
    main()
