"""SMTP email notifier for PR automation events.

Opt-in via env vars. Silent no-op if SMTP_HOST not set.
Never raises — failures swallow into bool return + audit log.

Env config (all optional, but HOST is gate):
  AUTO_PR_SMTP_HOST      — SMTP server hostname (gate; empty = disabled)
  AUTO_PR_SMTP_PORT      — int, default 587
  AUTO_PR_SMTP_USER      — login (optional, no-auth if empty)
  AUTO_PR_SMTP_PASS      — password (optional)
  AUTO_PR_SMTP_TLS       — "1" STARTTLS (default), "0" plain, "ssl" SSL
  AUTO_PR_NOTIFY_FROM    — From address (defaults to SMTP_USER)
  AUTO_PR_NOTIFY_TO      — comma-separated recipients (required)
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _config() -> dict[str, Any] | None:
    host = _env("AUTO_PR_SMTP_HOST")
    to = _env("AUTO_PR_NOTIFY_TO")
    if not host or not to:
        return None
    try:
        port = int(_env("AUTO_PR_SMTP_PORT", "587") or 587)
    except ValueError:
        port = 587
    return {
        "host": host,
        "port": port,
        "user": _env("AUTO_PR_SMTP_USER") or None,
        "password": _env("AUTO_PR_SMTP_PASS") or None,
        "tls": _env("AUTO_PR_SMTP_TLS", "1"),
        "from": _env("AUTO_PR_NOTIFY_FROM") or _env("AUTO_PR_SMTP_USER") or "auto-pr@localhost",
        "to": [t.strip() for t in to.split(",") if t.strip()],
    }


def send_email(subject: str, body: str, *, timeout: int = 10) -> tuple[bool, str]:
    """Send a single plaintext email. Returns (ok, message)."""
    cfg = _config()
    if cfg is None:
        return False, "smtp disabled (AUTO_PR_SMTP_HOST/AUTO_PR_NOTIFY_TO not set)"

    msg = EmailMessage()
    msg["From"] = cfg["from"]
    msg["To"] = ", ".join(cfg["to"])
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        if cfg["tls"] == "ssl":
            ctx = ssl.create_default_context()
            with smtplib.SMTP_SSL(
                cfg["host"], cfg["port"], context=ctx, timeout=timeout
            ) as srv:
                if cfg["user"] and cfg["password"]:
                    srv.login(cfg["user"], cfg["password"])
                srv.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=timeout) as srv:
                if cfg["tls"] == "1":
                    srv.starttls(context=ssl.create_default_context())
                if cfg["user"] and cfg["password"]:
                    srv.login(cfg["user"], cfg["password"])
                srv.send_message(msg)
        return True, f"sent to {len(cfg['to'])} recipient(s)"
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        return False, f"{type(exc).__name__}: {exc}"


# --- structured event helpers ------------------------------------------

def notify_pr_created(task_id: str, subject: str, branch: str, pr_url: str) -> tuple[bool, str]:
    body = (
        f"PR created automatically.\n\n"
        f"Task: #{task_id}\n"
        f"Subject: {subject or '(none)'}\n"
        f"Branch: {branch}\n"
        f"PR: {pr_url}\n"
    )
    return send_email(f"[PR Created] Task #{task_id} — {subject or branch}"[:120], body)


def notify_pr_merged(task_id: str, pr_url: str, mode: str = "squash") -> tuple[bool, str]:
    body = f"PR auto-merged ({mode}).\n\nTask: #{task_id}\nPR: {pr_url}\n"
    return send_email(f"[PR Merged] Task #{task_id}"[:120], body)


def notify_pr_failed(task_id: str, stage: str, reason: str, pr_url: str = "") -> tuple[bool, str]:
    body = (
        f"PR automation failed.\n\n"
        f"Task: #{task_id}\n"
        f"Stage: {stage}\n"
        f"Reason: {reason}\n"
        f"PR: {pr_url or '(not created)'}\n"
    )
    return send_email(f"[PR Failed] Task #{task_id} — {stage}"[:120], body)


def notify_checks_failed(task_id: str, pr_url: str, tail: str) -> tuple[bool, str]:
    body = (
        f"Pre-push or PR checks FAILED.\n\n"
        f"Task: #{task_id}\n"
        f"PR: {pr_url or '(local-only)'}\n\n"
        f"Tail:\n{tail[-1000:]}\n"
    )
    return send_email(f"[PR Checks FAIL] Task #{task_id}"[:120], body)
