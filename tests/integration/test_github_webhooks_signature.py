"""Integration tests for GitHub webhook HMAC signature verification.

Roadmap 40_PR_AUTOMATION/40.4 P3.1 — security-critical path. Verifies that
`src.api.routes.github_webhooks` only accepts deliveries with a valid
HMAC-SHA256 signature against `GITHUB_WEBHOOK_SECRET`, and rejects every
other shape (missing header, wrong digest, missing secret, malformed
prefix, bad JSON body).
"""

from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes import github_webhooks


SECRET = "test-shared-secret-do-not-use-in-prod"


def _sign(body: bytes, secret: str = SECRET) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Mount the webhook router on an isolated FastAPI app.

    Redirects the state-file to a per-test tmp dir so concurrent test runs
    don't clobber each other or the live `.claude/cache/...` file.
    """
    monkeypatch.setenv("GITHUB_WEBHOOK_SECRET", SECRET)
    monkeypatch.setattr(github_webhooks, "_STATE_FILE", tmp_path / "state.json")
    app = FastAPI()
    app.include_router(github_webhooks.router)
    return TestClient(app)


@pytest.mark.integration
class TestWebhookSignature:
    """HMAC SHA-256 verification must accept only correctly-signed deliveries."""

    def test_valid_signature_ping_accepted(self, client):
        body = json.dumps({"zen": "Practicality beats purity."}).encode()
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["received"] is True
        assert data["event"] == "ping"
        assert data["zen"] == "Practicality beats purity."

    def test_missing_signature_rejected(self, client):
        body = json.dumps({"any": "thing"}).encode()
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={"X-GitHub-Event": "ping", "Content-Type": "application/json"},
        )
        assert resp.status_code == 401
        assert "signature" in resp.json()["detail"].lower()

    def test_wrong_signature_rejected(self, client):
        body = json.dumps({"any": "thing"}).encode()
        wrong = _sign(body, secret="some-other-secret")
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": wrong,
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401

    def test_malformed_prefix_rejected(self, client):
        """Signature must start with `sha256=`. Legacy `sha1=` is refused."""
        body = json.dumps({"any": "thing"}).encode()
        legacy_digest = hmac.new(SECRET.encode(), body, hashlib.sha1).hexdigest()
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": f"sha1={legacy_digest}",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401

    def test_empty_secret_refuses_everything(self, monkeypatch, tmp_path):
        """Empty/unset GITHUB_WEBHOOK_SECRET -> always reject (no silent accept)."""
        monkeypatch.delenv("GITHUB_WEBHOOK_SECRET", raising=False)
        monkeypatch.setattr(github_webhooks, "_STATE_FILE", tmp_path / "state.json")
        app = FastAPI()
        app.include_router(github_webhooks.router)
        local = TestClient(app)
        body = json.dumps({"any": "thing"}).encode()
        resp = local.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": _sign(body, secret=""),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 401

    def test_bad_json_body_returns_400(self, client):
        """Valid sig over invalid JSON -> 400 (not 401, not 500)."""
        body = b"this is { not json"
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "ping",
                "X-Hub-Signature-256": _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 400
        assert "json" in resp.json()["detail"].lower()


@pytest.mark.integration
class TestWebhookDispatch:
    """Signed deliveries should be dispatched by `X-GitHub-Event` header."""

    def test_pull_request_event_updates_state(self, client, tmp_path):
        payload = {
            "action": "closed",
            "pull_request": {
                "html_url": "https://github.com/o/r/pull/42",
                "merged": True,
                "merged_at": "2026-05-22T20:00:00Z",
                "merge_commit_sha": "deadbeefcafe1234567890abcdef1234567890ab",
                "head": {"ref": "task/123-do-the-thing"},
            },
        }
        body = json.dumps(payload).encode()
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "pull_request",
                "X-Hub-Signature-256": _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["task_id"] == "123"
        assert data["data"]["merged"] is True
        state_file = tmp_path / "state.json"
        assert state_file.exists()
        state = json.loads(state_file.read_text(encoding="utf-8"))
        entry = state["processed"]["123"]
        assert entry["pr_url"] == "https://github.com/o/r/pull/42"
        assert entry["merge_sha"].startswith("deadbeef")

    def test_unknown_event_acked_not_processed(self, client):
        """GitHub stops retrying on 200 — unknown event types must still ack."""
        body = json.dumps({"foo": "bar"}).encode()
        resp = client.post(
            "/webhooks/github",
            content=body,
            headers={
                "X-GitHub-Event": "issue_comment",
                "X-Hub-Signature-256": _sign(body),
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert "not processed" in resp.json()["data"]["note"]
