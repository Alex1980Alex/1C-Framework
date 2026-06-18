#!/usr/bin/env python3
"""Warm-serve для SetFit-гейта детектора 1С (ADR-025) — снимает 6с холодную перезагрузку.

Гейт живёт в UPS-хуке (свежий процесс на каждый промпт) → загрузка ST-модели = ~6с КАЖДЫЙ раз
(превышает 5с-таймаут хука → совет теряется). Этот сервис держит модель (rubert-tiny2 ST + LR-голова)
в памяти ОДНОГО долгоживущего процесса; хук делает быстрый HTTP-вызов (~6мс).

CPU-only (0 видеопамяти — модель крошечная, нагрузка = 1 предикт на неоднозначный промпт). stdlib
``http.server`` — без внешних зависимостей. **Idle-shutdown**: если нет запросов
``ONEC_SETFIT_IDLE_SHUTDOWN_S`` (деф. 1800с=30мин) — процесс сам выходит (0 ресурсов в простое).
Гейт авто-стартует сервис (detached) при первом промахе; прогрев ~6с (тот промпт — на TF-IDF).

Endpoints:
    GET  /health           -> {"ok": bool}                 (модель загружена?)
    POST /predict {"text"} -> {"prob": float}              (вероятность is_1c ∈ [0,1])

Запуск:
    python scripts/onec_setfit_serve.py [--port 8077]      (порт = env ONEC_SETFIT_PORT)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
HOOKS = PROJECT_ROOT / ".claude" / "hooks"
if str(HOOKS) not in sys.path:
    sys.path.insert(0, str(HOOKS))

_IDLE_S = float(os.environ.get("ONEC_SETFIT_IDLE_SHUTDOWN_S", "1800"))

_state = {"model": None, "last": time.monotonic(), "gate": None}


def _load():
    """Загрузить ST+LR один раз (через гейт — единый источник загрузки/контракта)."""
    os.environ.setdefault("ONEC_SETFIT_ENABLE", "1")  # _load_model не зависит от флага, но для ясности
    from shared import onec_setfit_gate as gate

    _state["gate"] = gate
    _state["model"] = gate._load_model()  # _STHead (ST + LR) | None
    return _state["model"]


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_a):  # тихо (не засорять stderr)
        pass

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if self.path == "/health":
            self._json(200, {"ok": _state["model"] is not None})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if self.path != "/predict":
            self._json(404, {"error": "not found"})
            return
        try:
            n = int(self.headers.get("Content-Length", 0) or 0)
            text = json.loads(self.rfile.read(n) or b"{}").get("text", "")
            _state["last"] = time.monotonic()
            model = _state["model"]
            if model is None:
                self._json(503, {"error": "model not loaded"})
                return
            prob = _state["gate"]._positive_prob(model.predict_proba([text]))
            self._json(200, {"prob": prob})
        except Exception as e:  # fail-soft: гейт деградирует на TF-IDF при любой ошибке
            self._json(500, {"error": type(e).__name__})


def _idle_watch(srv: ThreadingHTTPServer) -> None:
    """Самовыключение по простою (0 ресурсов, когда 1С-задач нет)."""
    while True:
        time.sleep(min(60.0, max(5.0, _IDLE_S / 4)))
        if time.monotonic() - _state["last"] > _IDLE_S:
            srv.shutdown()
            return


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Warm-serve SetFit gate (ADR-025)")
    ap.add_argument("--port", type=int, default=int(os.environ.get("ONEC_SETFIT_PORT", "8077")))
    args = ap.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    if _load() is None:
        print("модель не найдена (models/onec-setfit) — обучите scripts/train_onec_setfit.py", file=sys.stderr)
        return 2
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), _Handler)
    threading.Thread(target=_idle_watch, args=(srv,), daemon=True).start()
    print(f"warm-serve на http://127.0.0.1:{args.port}  (idle-shutdown {int(_IDLE_S)}с)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
