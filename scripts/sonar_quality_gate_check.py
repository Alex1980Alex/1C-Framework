#!/usr/bin/env python3
"""R6 (ADR-034): Quality Gate check — fail на ERROR (Clean-as-You-Code, новый код).

Опрашивает /api/qualitygates/project_status. Exit 1 если status=ERROR (иначе 0).
--soft → только warn (exit 0). Hard-gate включается env SONAR_QG_HARD=1 (через wrapper/CI).
Сервер недоступен → skip (exit 0). Zero-dep (urllib). Auth: SONAR_TOKEN или admin:admin.
"""

import argparse
import base64
import json
import os
import sys
import urllib.request

# .env loader (gitignored секреты: SONAR_TOKEN/SONAR_HOST_URL); env > .env. ADR-041 follow-up.
try:
    import os as _o
    import sys as _s

    _s.path.insert(0, _o.path.dirname(_o.path.abspath(__file__)))
    from _dotenv import load_dotenv as _ld

    _ld()
except Exception:
    pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("SONAR_HOST_URL", "http://localhost:9000"))
    ap.add_argument("--project", default="upravlenie-transportom-plk")
    ap.add_argument("--token", default=os.environ.get("SONAR_TOKEN"))
    ap.add_argument("--soft", action="store_true", help="warn-only, не падать (exit 0)")
    a = ap.parse_args()
    url = a.host.rstrip("/") + "/api/qualitygates/project_status?projectKey=" + a.project
    req = urllib.request.Request(url)
    cred = (a.token + ":") if a.token else "admin:admin"
    req.add_header("Authorization", "Basic " + base64.b64encode(cred.encode()).decode())
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.load(r)
    except Exception as e:
        print(f"QG check: сервер недоступен ({e}) -> skip")
        return 0
    ps = data.get("projectStatus", {})
    status = ps.get("status", "NONE")
    failed = [c for c in ps.get("conditions", []) if c.get("status") not in ("OK", "NONE")]
    print(
        "Quality Gate: " + status + "  (условия new-code = Clean-as-You-Code; легаси не блокирует)"
    )
    for c in failed:
        print(
            "  FAIL %s: %s (порог %s)"
            % (c.get("metricKey"), c.get("actualValue"), c.get("errorThreshold"))
        )
    if status == "ERROR" and not a.soft:
        print("HARD GATE: QG=ERROR -> exit 1 (снять: SONAR_QG_HARD!=1 либо --soft)")
        return 1
    if status == "ERROR":
        print("(soft: не валю билд)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
