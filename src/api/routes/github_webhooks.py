"""GitHub webhook receiver. Roadmap: 40_PR_AUTOMATION/40.4 P3.1.

Endpoints
  POST /webhooks/github   — receive PR + check_suite events from GitHub.
                            Verifies HMAC SHA-256 signature against the
                            shared secret in env `GITHUB_WEBHOOK_SECRET`.
                            Updates the same state-file used by
                            `post-task-push-pr.py` so the hook + webhook
                            converge on a single source of truth.

Wiring (operator task)
  1. `pip install fastapi uvicorn`  (already done).
  2. In `src/api/app.py` add to imports:
       from src.api.routes import github_webhooks
     and register:
       app.include_router(github_webhooks.router)
  3. Expose your API via reverse-proxy / tunnel (ngrok / Cloudflare Tunnel).
  4. GitHub repo → Settings → Webhooks → Add:
       - Payload URL:  https://your-host/webhooks/github
       - Content type: application/json
       - Secret:       <same value as GITHUB_WEBHOOK_SECRET>
       - Events:       Pull requests, Check suites
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request, status

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks/github", tags=["webhooks"])

# Project root — three levels up from this file (src/api/routes → repo).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_STATE_FILE = _PROJECT_ROOT / ".claude" / "cache" / "post-task-push-pr-state.json"


def _verify_signature(body: bytes, sig_header: str | None) -> bool:
    """HMAC SHA-256 signature check against GITHUB_WEBHOOK_SECRET.

    GitHub sends header `X-Hub-Signature-256: sha256=<hex>`.
    """
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "").encode()
    if not secret:
        # No secret configured — refuse rather than silently accept.
        return False
    if not sig_header or not sig_header.startswith("sha256="):
        return False
    expected = sig_header.split("=", 1)[1].strip()
    mac = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, expected)


def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save_state(state: dict) -> None:
    try:
        _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        tmp = _STATE_FILE.with_suffix(_STATE_FILE.suffix + ".tmp")
        tmp.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(tmp, _STATE_FILE)
    except OSError as exc:
        logger.warning("[gh-webhook] failed to persist state: %s", exc)


def _task_id_from_branch(branch: str) -> str | None:
    """`task/<id>-...` → `<id>` (or None)."""
    if not branch.startswith("task/"):
        return None
    tail = branch[len("task/"):]
    head = tail.split("-", 1)[0]
    return head or None


def _apply_pr_event(payload: dict[str, Any]) -> dict[str, Any]:
    action = payload.get("action")
    pr_obj = payload.get("pull_request") or {}
    head_ref = (pr_obj.get("head") or {}).get("ref", "")
    pr_url = pr_obj.get("html_url", "")
    merged = bool(pr_obj.get("merged"))
    merge_sha = (pr_obj.get("merge_commit_sha") or "") if merged else ""

    task_id = _task_id_from_branch(head_ref)
    out = {
        "action": action,
        "branch": head_ref,
        "pr_url": pr_url,
        "task_id": task_id,
        "merged": merged,
    }
    if not task_id:
        return out

    state = _load_state()
    processed = state.setdefault("processed", {})
    entry = processed.setdefault(task_id, {})
    entry["pr_url"] = pr_url or entry.get("pr_url")
    entry["branch"] = head_ref or entry.get("branch")
    entry["webhook_last_event"] = action
    entry["webhook_last_ts"] = datetime.now().isoformat(timespec="seconds")
    if merged:
        entry["merged_ts"] = pr_obj.get("merged_at") or entry.get("merged_ts")
        entry["merge_sha"] = merge_sha or entry.get("merge_sha")
    _save_state(state)
    return out


def _apply_check_suite_event(payload: dict[str, Any]) -> dict[str, Any]:
    cs = payload.get("check_suite") or {}
    branch = cs.get("head_branch", "")
    sha = cs.get("head_sha", "")
    conclusion = (cs.get("conclusion") or "").lower()
    status_str = (cs.get("status") or "").lower()
    out = {
        "branch": branch,
        "sha": sha,
        "status": status_str,
        "conclusion": conclusion,
    }
    task_id = _task_id_from_branch(branch)
    if not task_id:
        return out
    state = _load_state()
    processed = state.setdefault("processed", {})
    entry = processed.setdefault(task_id, {})
    entry.setdefault("check_suites", []).append(
        {
            "sha": sha,
            "status": status_str,
            "conclusion": conclusion,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
    )
    # cap history length to last 20
    entry["check_suites"] = entry["check_suites"][-20:]
    _save_state(state)
    return out


@router.post("", status_code=status.HTTP_200_OK)
async def receive(
    request: Request,
    x_github_event: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
) -> dict[str, Any]:
    """Receive a GitHub webhook delivery.

    Verifies HMAC SHA-256 signature, dispatches by `X-GitHub-Event` header,
    and persists relevant data into the shared state-file.

    Returns a small JSON envelope so deliveries can be audited from the
    GitHub UI.
    """
    body = await request.body()
    if not _verify_signature(body, x_hub_signature_256):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing signature",
        )
    try:
        payload = json.loads(body.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"invalid JSON: {exc}",
        ) from exc

    event = (x_github_event or "").lower()
    result: dict[str, Any] = {"event": event, "received": True}
    if event == "ping":
        result["zen"] = payload.get("zen", "")
    elif event == "pull_request":
        result["data"] = _apply_pr_event(payload)
    elif event == "check_suite":
        result["data"] = _apply_check_suite_event(payload)
    else:
        # Unhandled event types still ack so GitHub doesn't retry.
        result["data"] = {"note": "event accepted, not processed"}
    return result
