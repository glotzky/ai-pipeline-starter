#!/usr/bin/env python3
"""Demo step: start the app, take screenshots of key pages, write a report the tester reads.

Used by run.py after the developer stage when triage says the change is visible in a browser. Also runnable by hand:
    python3 pipeline/demo.py --out .pipeline/demo [--cmd "npm run dev"] [--url http://127.0.0.1:4173] [--paths /,/leads]

Configuration (repository variables, all optional):
    PIPELINE_DEMO=0           turn the demo step off
    PIPELINE_DEMO_CMD         command that starts the app (default: detected for Vite projects only)
    PIPELINE_DEMO_URL         where the app listens (default http://127.0.0.1:4173 for the Vite default)
    PIPELINE_DEMO_PATHS       comma-separated pages to capture (default "/")

It never fails the pipeline: problems come back as status "skipped" or "failed" with a reason. The app is started WITHOUT the
pipeline's secrets in its environment. Needs Playwright (installed on demand: pip install playwright, then Chromium).
How to develop this file: docs/16-triage-demo-acu-prompting.md in the starter.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

SECRET_ENV = ("ANTHROPIC_API_KEY", "DEVIN_API_KEY", "DEVIN_ORG_ID", "GH_TOKEN", "GITHUB_TOKEN", "OPENAI_API_KEY",
              "PIPELINE_PE_API_KEY", "ACTIONS_RUNTIME_TOKEN", "ACTIONS_ID_TOKEN_REQUEST_TOKEN")
DEFAULT_URL = "http://127.0.0.1:4173"
VITE_CMD = "npm run dev -- --host 127.0.0.1 --port 4173 --strictPort"
MAX_SHOTS = 6


def detect(root, env):
    """Return (command, url, why_not). The command comes from PIPELINE_DEMO_CMD, or is detected for Vite projects."""
    cmd, url = env.get("PIPELINE_DEMO_CMD", "").strip(), env.get("PIPELINE_DEMO_URL", "").strip()
    if cmd:
        return cmd, url or DEFAULT_URL, None
    pkg = Path(root) / "package.json"
    try:
        data = json.loads(pkg.read_text())
    except (OSError, ValueError):
        return None, None, "no package.json, and PIPELINE_DEMO_CMD is not set"
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    if "vite" in deps and "dev" in data.get("scripts", {}):
        return VITE_CMD, url or DEFAULT_URL, None
    return None, None, "could not detect how to start the app; set the repository variable PIPELINE_DEMO_CMD (and PIPELINE_DEMO_URL)"


def _short(e):
    """First line of an error, so reports do not carry Playwright's multi-line banners."""
    lines = [l for l in str(e).splitlines() if l.strip()]
    return f"{type(e).__name__}: {(lines[0] if lines else '')[:200]}"


def slug(path):
    s = re.sub(r"[^a-z0-9]+", "-", path.strip("/").lower()).strip("-")
    return s or "home"


def parse_paths(raw):
    paths = [p.strip() for p in (raw or "/").split(",") if p.strip()]
    paths = [p if p.startswith("/") else "/" + p for p in paths]
    return (paths or ["/"])[:MAX_SHOTS]


def wait_for(url, timeout, proc=None):
    """True once the URL answers (any HTTP status counts as up); False on timeout or if the server process died."""
    end = time.time() + timeout
    while time.time() < end:
        if proc is not None and proc.poll() is not None:
            return False
        try:
            urllib.request.urlopen(url, timeout=3).close()
            return True
        except urllib.error.HTTPError:
            return True
        except Exception:  # noqa: BLE001 (not up yet)
            time.sleep(1)
    return False


def ensure_playwright(env):
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        pass
    if env.get("PIPELINE_DEMO_NO_INSTALL") == "1":
        return False
    for cmd in ([sys.executable, "-m", "pip", "install", "-q", "playwright"],
                [sys.executable, "-m", "playwright", "install", "--with-deps", "chromium"]):
        if subprocess.run(cmd, capture_output=True, text=True).returncode != 0:
            return False
    return True


def capture(base_url, paths, out_dir):
    """Screenshot each path. Returns a list of per-page results (never raises for a page that fails to load)."""
    from playwright.sync_api import sync_playwright  # imported late: only needed when a demo really runs

    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            context = browser.new_context(viewport={"width": 1280, "height": 800})
            for i, path in enumerate(paths, 1):
                page = context.new_page()
                errors, failed = [], []
                page.on("console", lambda m, e=errors: e.append(m.text[:200]) if m.type == "error" else None)
                page.on("pageerror", lambda x, e=errors: e.append(str(x)[:200]))
                page.on("response", lambda r, f=failed: f.append(f"{r.status} {r.url[:120]}") if r.status >= 400 else None)
                item = {"path": path, "ok": False, "http_status": None, "title": None, "file": None,
                        "console_errors": errors, "failed_requests": failed}
                try:
                    resp = page.goto(base_url.rstrip("/") + path, wait_until="load", timeout=30000)
                    item["http_status"] = resp.status if resp else None
                    try:
                        page.wait_for_load_state("networkidle", timeout=5000)
                    except Exception:  # noqa: BLE001 (some apps never go idle; the screenshot is still useful)
                        pass
                    name = f"{i:02d}-{slug(path)}.jpg"
                    page.screenshot(path=str(out_dir / name), full_page=True, type="jpeg", quality=70)
                    item.update(ok=True, title=page.title()[:120], file=name)
                except Exception as e:  # noqa: BLE001
                    item["error"] = _short(e)
                finally:
                    page.close()
                results.append(item)
        finally:
            browser.close()
    return results


def run_demo(root, out_dir, env=None, log_dir=None):
    """Run the whole demo. Returns {"status": ok|skipped|failed, "reason", "screenshots": [...], "pages": [...]}."""
    env = dict(os.environ if env is None else env)
    out_dir = Path(out_dir)
    result = {"status": "skipped", "reason": None, "screenshots": [], "pages": []}

    def done(status, reason=None):
        result.update(status=status, reason=reason)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "report.json").write_text(json.dumps(result, indent=2) + "\n")
        return result

    if env.get("PIPELINE_DEMO") == "0":
        return done("skipped", "turned off (PIPELINE_DEMO=0)")
    cmd, url, why = detect(root, env)
    if not cmd:
        return done("skipped", why)
    if not ensure_playwright(env):
        return done("skipped", "Playwright is not available and could not be installed")

    server_env = {k: v for k, v in env.items() if k not in SECRET_ENV}
    log = None
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        log = open(Path(log_dir) / "demo-server.txt", "w")
    proc = subprocess.Popen(cmd, shell=True, cwd=root, env=server_env, stdout=log or subprocess.DEVNULL,
                            stderr=subprocess.STDOUT, start_new_session=True)
    try:
        if not wait_for(url, int(env.get("PIPELINE_DEMO_WAIT", "90")), proc):
            return done("failed", f"the app did not answer at {url} (see .pipeline/logs/demo-server.txt)")
        pages = capture(url, parse_paths(env.get("PIPELINE_DEMO_PATHS")), out_dir)
        result["pages"] = pages
        result["screenshots"] = [p["file"] for p in pages if p.get("file")]
        if not result["screenshots"]:
            return done("failed", "no page could be captured")
        return done("ok")
    except Exception as e:  # noqa: BLE001 (a demo problem must never fail the pipeline)
        return done("failed", _short(e))
    finally:
        try:
            os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            pass
        if log:
            log.close()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=".pipeline/demo")
    ap.add_argument("--cmd")
    ap.add_argument("--url")
    ap.add_argument("--paths")
    a = ap.parse_args(argv)
    env = dict(os.environ)
    for key, val in (("PIPELINE_DEMO_CMD", a.cmd), ("PIPELINE_DEMO_URL", a.url), ("PIPELINE_DEMO_PATHS", a.paths)):
        if val:
            env[key] = val
    root = Path(__file__).resolve().parent.parent
    res = run_demo(root, root / a.out, env, root / ".pipeline" / "logs")
    print(json.dumps({k: res[k] for k in ("status", "reason", "screenshots")}, indent=2))
    return 0 if res["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
