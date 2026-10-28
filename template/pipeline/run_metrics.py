"""Per-run metrics recorder for the pipeline. Standard library only.

Writes one JSON file per run to metrics/runs/<run_id>.json, validated by metrics/schema.json.
The file is written when the run starts (status "incomplete") and rewritten after every change,
so a run that is killed, cancelled or times out still leaves an honest partial record.

Rules this module follows:
  * Never invent a number. Anything not measured or not reported by a tool is null.
  * Never record secrets, prompts, issue text, review text, or Devin session links.
  * Error messages are scrubbed of known secret values and token patterns, then truncated.
"""
import json
import os
import re
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

SCHEMA_VERSION = 1
SECRET_ENV_VARS = ("ANTHROPIC_API_KEY", "DEVIN_API_KEY", "DEVIN_ORG_ID", "GH_TOKEN", "GITHUB_TOKEN")
SECRET_PATTERNS = [
    r"cog_[A-Za-z0-9]+",
    r"sk-ant-[A-Za-z0-9_\-]+",
    r"gh[pousr]_[A-Za-z0-9]+",
    r"github_pat_[A-Za-z0-9_]+",
    r"(?i)bearer\s+[A-Za-z0-9._\-]+",
    r"org-[0-9a-fA-F]{16,}",
]
USAGE_FIELDS = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")


def scrub(text, limit=300):
    """Remove secret values and token-shaped strings, then truncate."""
    text = "" if text is None else str(text)
    for name in SECRET_ENV_VARS:
        value = os.environ.get(name, "")
        if len(value) >= 6:
            text = text.replace(value, "[redacted]")
    for pattern in SECRET_PATTERNS:
        text = re.sub(pattern, "[redacted]", text)
    return text[:limit]


def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _number(value):
    """Accept real numbers only (not bool, not strings). Anything else is missing data."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def parse_claude_output(raw):
    """Split `claude -p --output-format json` stdout into (text, usage_info or None).

    If the output is not the expected JSON object (older CLI, plain text), return the raw text
    unchanged and no usage, so pipeline behaviour never depends on this parsing.
    """
    try:
        data = json.loads(raw)
    except (ValueError, TypeError):
        return raw, None
    if not isinstance(data, dict) or data.get("type") != "result":
        return raw, None
    usage_in = data.get("usage") if isinstance(data.get("usage"), dict) else {}
    info = {f: _number(usage_in.get(f)) for f in USAGE_FIELDS}
    info["cost_usd"] = _number(data.get("total_cost_usd"))
    info["num_turns"] = _number(data.get("num_turns"))
    result = data.get("result")
    return (result if isinstance(result, str) else raw), info


class Recorder:
    def __init__(self, root, run_id, kind, until, branch, enabled=True):
        self.enabled = enabled
        suffix = "-fix" if kind == "fix" else ""
        self.path = Path(root) / "metrics" / "runs" / f"{run_id}{suffix}.json"
        self._t0 = time.monotonic()
        self._started = time.time()
        self._finished = False
        self.data = {
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "kind": kind,
            "status": "incomplete",
            "stop_reason": None,
            "until": until,
            "branch": branch,
            "started_at": _iso(self._started),
            "ended_at": None,
            "duration_seconds": None,
            "github": {
                "workflow_run_id": os.environ.get("GITHUB_RUN_ID") or None,
                "run_attempt": int(os.environ["GITHUB_RUN_ATTEMPT"]) if os.environ.get("GITHUB_RUN_ATTEMPT", "").isdigit() else None,
            },
            "stages": [],
            "retries": {"developer_attempts": 0, "retries": 0, "reasons": []},
            "tests": {"result": "not_run", "attempts": 0, "gate_failed": False},
            "review": {"verdict": "not_run"},
            "pull_request": {"created": False, "updated": False, "number": None, "url": None},
            "devin": {"sessions": 0, "sessions_with_acus": 0, "acus_consumed": None,
                      "acu_budget": None, "acu_limit": None, "over_budget": None},
            "triage": None,
            "prompt_engineer": None,
            "demo": None,
            "ai_usage": {"calls": [], "totals": {
                "calls": 0, "calls_with_cost": 0, "cost_complete": None, "cost_usd": None,
                "input_tokens": None, "output_tokens": None,
                "cache_creation_input_tokens": None, "cache_read_input_tokens": None},
                "cost_source": None},
            "error": None,
        }
        self.save()

    # ---- persistence ----
    def save(self):
        if not self.enabled:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2) + "\n")
            tmp.replace(self.path)
        except OSError as e:  # metrics must never break the pipeline
            print(f"[metrics] could not write {self.path}: {scrub(e)}", flush=True)

    # ---- stages ----
    @contextmanager
    def stage(self, name, attempt=1):
        entry = {"name": name, "attempt": attempt, "started_at": _iso(time.time()),
                 "ended_at": None, "duration_seconds": None, "status": "incomplete", "detail": None}
        self.data["stages"].append(entry)
        t0 = time.monotonic()
        self.save()
        try:
            yield entry
        except SystemExit:
            entry["status"] = "stopped"
            raise
        except BaseException as e:
            entry["status"] = "error"
            entry["detail"] = scrub(f"{type(e).__name__}: {e}")
            raise
        else:
            if entry["status"] == "incomplete":
                entry["status"] = "ok"
        finally:
            entry["ended_at"] = _iso(time.time())
            entry["duration_seconds"] = round(time.monotonic() - t0, 1)
            self.save()

    # ---- facts ----
    def usage(self, stage, model, info):
        """Record one Claude call. `info` is None when the CLI reported no usage (nothing is guessed)."""
        call = {"stage": stage, "model": model}
        for f in USAGE_FIELDS + ("cost_usd", "num_turns"):
            call[f] = (info or {}).get(f)
        self.data["ai_usage"]["calls"].append(call)
        self._totals()
        self.save()

    def _totals(self):
        ai = self.data["ai_usage"]
        calls = ai["calls"]
        t = ai["totals"]
        t["calls"] = len(calls)
        for f in USAGE_FIELDS + ("cost_usd",):
            values = [c[f] for c in calls if c[f] is not None]
            t[f] = round(sum(values), 6) if values else None
        t["calls_with_cost"] = sum(1 for c in calls if c["cost_usd"] is not None)
        t["cost_complete"] = (t["calls_with_cost"] == t["calls"]) if calls else None
        ai["cost_source"] = "claude_cli_reported" if t["calls_with_cost"] else None

    def developer_attempt(self, acus):
        d = self.data["devin"]
        d["sessions"] += 1
        self.data["retries"]["developer_attempts"] += 1
        self.data["retries"]["retries"] = max(0, self.data["retries"]["developer_attempts"] - 1)
        value = _number(acus)
        if value is not None:
            d["sessions_with_acus"] += 1
            d["acus_consumed"] = round((d["acus_consumed"] or 0) + value, 3)
        self._budget_check()
        self.save()

    def _budget_check(self):
        d = self.data["devin"]
        used, budget = d["acus_consumed"], d["acu_budget"]
        d["over_budget"] = None if (used is None or not budget) else used > budget  # unknown stays unknown

    def devin_budget(self, budget, limit):
        """The ACU budget triage set and the per-session limit sent to Devin (None when not set)."""
        d = self.data["devin"]
        d["acu_budget"], d["acu_limit"] = _number(budget), _number(limit)
        self._budget_check()
        self.save()

    def triage(self, t):
        self.data["triage"] = {"parsed": bool(t.get("parsed")), "kind": t.get("kind"), "size": t.get("size"),
                               "route": t.get("route"), "needs_demo": bool(t.get("needs_demo")),
                               "acu_budget": _number(t.get("acu_budget"))}
        self.save()

    def prompt_engineer(self, backend, status):
        self.data["prompt_engineer"] = {"backend": backend, "status": status}
        self.save()

    def demo(self, status, screenshots, reason=None):
        self.data["demo"] = {"status": status, "screenshots": int(screenshots),
                             "reason": scrub(reason, 200) if reason else None, "confirmed": None}
        self.save()

    def demo_confirmed(self, value):
        """What the tester wrote on its DEMO line (PASS, FAIL, SKIPPED), or 'missing' if screenshots existed but it wrote none."""
        if self.data["demo"] is not None:
            self.data["demo"]["confirmed"] = value
            self.save()

    def retry(self, reason):
        self.data["retries"]["reasons"].append(reason)
        self.save()

    def tests(self, result, gate_failed=False):
        t = self.data["tests"]
        t["result"] = result if result in ("PASS", "FAIL") else "FAIL"
        t["attempts"] += 1
        t["gate_failed"] = bool(t["gate_failed"] or gate_failed)
        self.save()

    def review(self, verdict):
        self.data["review"]["verdict"] = verdict
        self.save()

    def pull_request(self, created=False, updated=False, url=None):
        pr = self.data["pull_request"]
        pr["created"], pr["updated"] = bool(created), bool(updated)
        if url:
            url = scrub(url, 200).strip()
            pr["url"] = url
            m = re.search(r"/pull/(\d+)", url)
            pr["number"] = int(m.group(1)) if m else None
        self.save()

    # ---- end of run ----
    def finish(self, status, reason=None, error=None, force=False):
        """Record how the run ended. The first call wins unless force=True (used when something fails
        after the run was already marked finished, for example a failed push)."""
        if self._finished and not force:
            return
        self._finished = True
        d = self.data
        d["status"], d["stop_reason"] = status, reason
        d["ended_at"] = _iso(time.time())
        d["duration_seconds"] = round(time.monotonic() - self._t0, 1)
        if error is not None:
            d["error"] = {"type": type(error).__name__, "message": scrub(error)}
        self.save()
