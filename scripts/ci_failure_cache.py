#!/usr/bin/env python3
"""CI Failure Cache + Analysis."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = PROJECT_ROOT / ".claude" / "cache"
JSONL_FILE = CACHE_DIR / "ci-failures.jsonl"
ISSUE_TAG_FILE = CACHE_DIR / "ci-failure-issues.json"
TEI_URL = "http://localhost:8080"
QDRANT_URL = "http://localhost:6333"
COLLECTION = "ci_failures"
COLLECTION_DIM = 1024
OCCURRENCE_THRESHOLD = 3
NOISE_PATTERNS = re.compile(
    r"##\[group\]|Prepare workflow|Set up Python|Install uv|Cache dependencies|"
    r"Initialize CodeQL|Post Run|safe\.directory|Cleaning up orphan|Post job cleanup",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _gh(*args: str) -> tuple[int, str, str]:
    r = subprocess.run(
        ["gh", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(PROJECT_ROOT),
        check=False,
    )
    return r.returncode, r.stdout, r.stderr


_NORMALIZE_PATTERNS = [
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z?"), ""),
    (re.compile(r"\b\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\b"), ""),
    (re.compile(r"<job_\d+>"), "<job_ID>"),
    (re.compile(r"\brun_id=\d+\b"), "run_id=N"),
    (re.compile(r"\bid=\d+\b"), "id=N"),
    (re.compile(r"\s+"), " "),
]


def _normalize_for_hash(s: str) -> str:
    for pat, repl in _NORMALIZE_PATTERNS:
        s = pat.sub(repl, s)
    return s.strip()


def _hash(text: str) -> str:
    return hashlib.sha256(_normalize_for_hash(text).encode("utf-8", errors="replace")).hexdigest()[
        :16
    ]


def _append_jsonl(entry: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with JSONL_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_jsonl() -> list[dict]:
    if not JSONL_FILE.exists():
        return []
    out = []
    with JSONL_FILE.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                out.append(parsed)
    return out


def extract_first_error(log: str) -> str:
    markers = ("##[error]", "FAIL", "Error:", "error:", "Failed:", "failure")
    for raw in log.splitlines():
        line = raw.strip()
        if not line or NOISE_PATTERNS.search(line):
            continue
        line = re.sub(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s+", "", line)
        # Strip "<job>\t<step>\t" prefix — step can be mixed case + /@.-
        line = re.sub(r"^[\w\s().\-]+\t[\w\s().\-/@]+\t", "", line)
        # Strip any embedded ISO timestamp (after prefix removal)
        line = re.sub(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z\s*", "", line)
        for m in markers:
            if m in line:
                return line[:300]
    return "(no error line extracted)"


def fetch_failure_log(run_id: str, job_name: str | None = None) -> str:
    rc, out, _ = _gh("run", "view", str(run_id), "--log-failed")
    if rc != 0 or not out.strip():
        return ""
    if job_name:
        return "\n".join(ln for ln in out.splitlines() if job_name in ln)
    return out


def _mrl_truncate(vec: list[float], dim: int) -> list[float]:
    if len(vec) <= dim:
        return vec
    vec = vec[:dim]
    norm = sum(x * x for x in vec) ** 0.5
    return [x / norm for x in vec] if norm > 1e-9 else vec


def _embed_tei(text: str) -> list[float] | None:
    try:
        import httpx
    except ImportError:
        return None
    prefix = "Instruct: Given a web search query, retrieve relevant passages that answer the query\nQuery: "
    try:
        with httpx.Client(base_url=TEI_URL, timeout=3.0) as c:
            r = c.post(
                "/embed", json={"inputs": [prefix + text], "normalize": True, "truncate": True}
            )
            r.raise_for_status()
            data = r.json()
    except Exception:
        return None
    return _parse_embedding(data)


def _parse_embedding(data) -> list[float] | None:
    if not isinstance(data, list) or not data:
        return None
    first = data[0]
    if isinstance(first, list):
        vec = [float(x) for x in first]
    elif isinstance(first, dict) and "embedding" in first:
        vec = [float(x) for x in first["embedding"]]
    else:
        return None
    return _mrl_truncate(vec, COLLECTION_DIM)


def _ensure_qdrant_collection() -> bool:
    try:
        import httpx

        with httpx.Client(base_url=QDRANT_URL, timeout=3.0) as c:
            if c.get(f"/collections/{COLLECTION}").status_code == 200:
                return True
            r = c.put(
                f"/collections/{COLLECTION}",
                json={"vectors": {"size": COLLECTION_DIM, "distance": "Cosine"}},
            )
            return r.status_code in (200, 201)
    except Exception:
        return False


def _search_qdrant(vec: list[float], top_k: int = 3) -> list[dict]:
    try:
        import httpx

        with httpx.Client(base_url=QDRANT_URL, timeout=3.0) as c:
            r = c.post(
                f"/collections/{COLLECTION}/points/search",
                json={"vector": vec, "limit": top_k, "with_payload": True, "score_threshold": 0.7},
            )
            return r.json().get("result", []) if r.status_code == 200 else []
    except Exception:
        return []


def _upsert_qdrant(point_id: str, vec: list[float], payload: dict) -> bool:
    try:
        import httpx

        int_id = int(point_id[:15], 16)
        with httpx.Client(base_url=QDRANT_URL, timeout=3.0) as c:
            r = c.put(
                f"/collections/{COLLECTION}/points",
                json={"points": [{"id": int_id, "vector": vec, "payload": payload}]},
            )
            return r.status_code in (200, 201)
    except Exception:
        return False


def _load_issue_tags() -> dict:
    if not ISSUE_TAG_FILE.exists():
        return {}
    try:
        return json.loads(ISSUE_TAG_FILE.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_issue_tags(tags: dict) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    ISSUE_TAG_FILE.write_text(json.dumps(tags, indent=2, ensure_ascii=False), encoding="utf-8")


def _maybe_create_issue(error_hash: str, error_line: str, occ: list[dict]) -> str | None:
    if len(occ) < OCCURRENCE_THRESHOLD:
        return None
    tags = _load_issue_tags()
    if error_hash in tags:
        return tags[error_hash]
    prs = sorted({f"#{o['pr']}" for o in occ if o.get("pr")})
    urls = "\n".join(f"- {o.get('url', '')}" for o in occ[-5:])
    body = (
        f"## Recurring CI Failure\n\n**Error:** `{error_line}`\n\n"
        f"**Hash:** `{error_hash}` · **Occurrences:** {len(occ)}\n\n"
        f"**PRs:** {', '.join(prs) if prs else '(none)'}\n\n**Runs:**\n{urls}\n\n"
        f"_Auto-created by `scripts/ci_failure_cache.py`._"
    )
    rc, out, _ = _gh(
        "issue",
        "create",
        "--title",
        f"[CI] Recurring: {error_line[:60]}",
        "--body",
        body,
        "--label",
        "ci-failure,automated",
    )
    if rc != 0:
        return None
    url = out.strip().splitlines()[-1] if out.strip() else None
    if url:
        tags[error_hash] = url
        _save_issue_tags(tags)
    return url


def _resolve_pr_head(pr: int) -> tuple[str | None, str | None]:
    """Resolve PR number to (headRefName, headRefOid). Returns (None, None) on failure."""
    rc, out, _ = _gh("pr", "view", str(pr), "--json", "headRefName,headRefOid")
    if rc != 0:
        return None, None
    try:
        data = json.loads(out)
        return data.get("headRefName"), data.get("headRefOid")
    except json.JSONDecodeError:
        return None, None


def _resolve_run_id(pr, sha) -> str | None:
    """Find latest FAILURE run for PR/SHA. Prefers --commit (specific) over --branch."""
    branch, commit = None, sha
    if pr:
        branch, head_oid = _resolve_pr_head(int(pr))
        commit = commit or head_oid
    args = ["run", "list", "--limit", "10", "--json", "databaseId,conclusion,workflowName"]
    if commit:
        args += ["--commit", commit]
    elif branch:
        args += ["--branch", branch]
    else:
        return None
    rc, out, _ = _gh(*args)
    if rc != 0:
        return None
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return None
    for d in data:
        if d.get("conclusion") == "failure":
            return str(d.get("databaseId"))
    return str(data[0].get("databaseId")) if data else None


def analyze_failure(pr, sha, run_id, job) -> dict:
    if not run_id and (pr or sha):
        run_id = _resolve_run_id(pr, sha)
    if not run_id:
        return {"error": "no run_id resolved"}
    log = fetch_failure_log(run_id, job)
    if not log:
        return {"error": "no failure log"}
    return _process_failure(pr, sha, run_id, job, log)


def _process_failure(pr, sha, run_id: str, job, log: str) -> dict:
    error_line = extract_first_error(log)
    error_hash = _hash(error_line)
    entry = {
        "ts": _now_iso(),
        "pr": pr,
        "sha": sha,
        "job": job,
        "run_id": run_id,
        "url": f"https://github.com/Alex1980Alex/1C-Framework/actions/runs/{run_id}",
        "error_first_line": error_line,
        "error_hash": error_hash,
    }
    _append_jsonl(entry)
    same = [e for e in _read_jsonl() if e.get("error_hash") == error_hash]
    similar = []
    vec = _embed_tei(error_line)
    if vec and _ensure_qdrant_collection():
        _upsert_qdrant(error_hash + str(len(same)).zfill(4), vec, entry)
        similar = _search_qdrant(vec, top_k=3)
    issue_url = _maybe_create_issue(error_hash, error_line, same)
    return {
        "logged": True,
        "error_hash": error_hash,
        "error_line": error_line,
        "occurrences": len(same),
        "similar": _format_similar(similar),
        "issue_url": issue_url,
    }


def _format_similar(similar: list[dict]) -> list[dict]:
    return [
        {
            "score": round(s.get("score", 0), 3),
            "hash": s.get("payload", {}).get("error_hash"),
            "ts": s.get("payload", {}).get("ts"),
        }
        for s in similar
    ]


def _lookup_pr_for_branch(branch: str) -> int | None:
    if not branch:
        return None
    for state in ("open", "all"):
        rc, out, _ = _gh(
            "pr", "list", "--head", branch, "--state", state, "--limit", "1", "--json", "number"
        )
        if rc != 0:
            continue
        try:
            data = json.loads(out)
            if data:
                return data[0].get("number")
        except (json.JSONDecodeError, IndexError, KeyError):
            continue
    return None


def catchup(limit: int = 20) -> dict:
    """Fetch recent FAILURE runs, process those not yet in cache.

    Returns: {processed, skipped, errors[]}. Safe to call repeatedly.
    """
    existing = {e.get("run_id") for e in _read_jsonl() if e.get("run_id")}
    rc, out, _ = _gh(
        "run",
        "list",
        "--status",
        "failure",
        "--limit",
        str(limit),
        "--json",
        "databaseId,headSha,headBranch,workflowName,event",
    )
    if rc != 0:
        return {"error": "gh run list failed"}
    try:
        runs = json.loads(out)
    except json.JSONDecodeError:
        return {"error": "invalid JSON from gh"}
    processed, skipped, errors = 0, 0, []
    for r in runs:
        run_id = str(r.get("databaseId", ""))
        if not run_id or run_id in existing:
            skipped += 1
            continue
        pr = _lookup_pr_for_branch(r.get("headBranch", ""))
        log = fetch_failure_log(run_id)
        if not log:
            errors.append({"run_id": run_id, "reason": "no log"})
            continue
        try:
            _process_failure(pr, r.get("headSha"), run_id, None, log)
            processed += 1
        except Exception as e:  # noqa: BLE001 — graceful degradation, never break batch
            errors.append({"run_id": run_id, "error": str(e)[:120]})
            print(f"[catchup] error run_id={run_id}: {e}", file=sys.stderr)
    return {"processed": processed, "skipped": skipped, "errors": errors}


def stats() -> dict:
    entries = _read_jsonl()
    failures = [e for e in entries if not e.get("event_type")]
    events = [e for e in entries if e.get("event_type")]
    by_hash: dict = {}
    for e in failures:
        by_hash.setdefault(e.get("error_hash", "?"), []).append(e)
    top = sorted(by_hash.items(), key=lambda kv: -len(kv[1]))[:10]
    return {
        "total_failures": len(failures),
        "total_events": len(events),
        "unique_hashes": len(by_hash),
        "top_recurring": [
            {
                "hash": h,
                "count": len(v),
                "first": (v[0].get("error_first_line") or "")[:80],
                "last_ts": v[-1].get("ts"),
            }
            for h, v in top
        ],
    }


def search_text(query: str) -> list[dict]:
    q = query.lower()
    return [
        e
        for e in _read_jsonl()
        if q in (e.get("error_first_line") or "").lower()
        or q in (e.get("content_preview") or "").lower()
    ][-10:]


VALID_EVENT_TYPES = {"notification", "pr-review", "workflow-event", "other"}


def log_event(event_type: str, key: str, content: str) -> dict:
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"invalid event_type {event_type!r}; expected one of {sorted(VALID_EVENT_TYPES)}"
        )
    error_hash = _hash(content)
    entry = {
        "ts": _now_iso(),
        "event_type": event_type,
        "key": key,
        "content_preview": content[:300],
        "error_hash": error_hash,
    }
    _append_jsonl(entry)
    same = [e for e in _read_jsonl() if e.get("error_hash") == error_hash]
    return {
        "logged": True,
        "event_type": event_type,
        "error_hash": error_hash,
        "occurrences": len(same),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--pr", type=int)
    p.add_argument("--sha", type=str)
    p.add_argument("--run-id", type=str, dest="run_id")
    p.add_argument("--job", type=str)
    p.add_argument("--stats", action="store_true")
    p.add_argument("--search", type=str)
    p.add_argument(
        "--catchup",
        nargs="?",
        const=20,
        type=int,
        metavar="LIMIT",
        help="Backfill recent FAILURE runs not in cache (default LIMIT=20)",
    )
    p.add_argument(
        "--log-event",
        dest="log_event_type",
        help="Log generic event (pr-review|notification|workflow-event|other)",
    )
    p.add_argument("--key", help="Event key/identifier (used with --log-event)")
    p.add_argument("--content", help="Event content for hashing (used with --log-event)")
    args = p.parse_args()
    return _dispatch(args)


def _dispatch(args) -> int:
    if args.stats:
        print(json.dumps(stats(), indent=2, ensure_ascii=False))
        return 0
    if args.search:
        print(json.dumps(search_text(args.search), indent=2, ensure_ascii=False))
        return 0
    if args.catchup is not None:
        print(json.dumps(catchup(limit=args.catchup), indent=2, ensure_ascii=False))
        return 0
    if args.log_event_type:
        if not (args.key and args.content):
            print("error: --log-event requires --key and --content", file=sys.stderr)
            return 2
        try:
            result = log_event(args.log_event_type, args.key, args.content)
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if not (args.pr or args.sha or args.run_id):
        print(
            "error: provide --pr, --sha, --run-id, --stats, --search, or --catchup",
            file=sys.stderr,
        )
        return 2
    result = analyze_failure(args.pr, args.sha, args.run_id, args.job)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
