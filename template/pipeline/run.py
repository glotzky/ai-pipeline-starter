#!/usr/bin/env python3
"""Pipeline orchestrator: researcher -> planner -> [designer] -> Devin -> tester -> reviewer.

Handoffs are files in .pipeline/ committed to a per-run branch. Claude stages run via the
Claude Code CLI (`claude -p`); the developer stage is Devin, driven through its v3 API.
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile, time
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path

import requests

import demo as demo_mod
import prompt_engineer
import sve_lib
import triage_lib
from run_metrics import Recorder, parse_claude_output, scrub

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / ".pipeline"
AGENTS = ROOT / ".claude" / "agents"
BASE_BRANCH = os.environ.get("BASE_BRANCH", "main")
REPO = os.environ.get("GITHUB_REPOSITORY", "")
REC = None  # metrics Recorder, created in main(); None-safe everywhere it is used
STAGES = ["triage", "research", "plan", "design", "dev", "test", "review"]
DEVIN_WARNINGS = []  # notes from devin_run (for example: the ACU limit was rejected), added to the run summary


def sh(*cmd, check=True):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed:\n{r.stdout}\n{r.stderr}")
    return r.stdout.strip()


SRC_EXT = (".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rb", ".java", ".kt", ".rs", ".cs", ".php", ".swift")


def is_test_file(path):
    low = path.lower()
    name = os.path.basename(low)
    return bool(re.search(r"(^|/)(tests?|__tests__|spec)/", low)
                or re.search(r"[._](test|spec)\.[a-z]+$", name) or name.startswith("test_"))


def missing_tests():
    """Return a failure note if the branch changes source code but adds or changes no test file."""
    if os.environ.get("PIPELINE_REQUIRE_TESTS", "1") == "0":
        return ""
    names = sh("git", "diff", "--name-only", f"origin/{BASE_BRANCH}...HEAD").splitlines()
    names = [n for n in names if not n.startswith(".pipeline/")]
    src = [n for n in names if n.endswith(SRC_EXT) and not is_test_file(n)
           and not n.endswith(".d.ts") and ".config." not in os.path.basename(n)]
    if src and not any(is_test_file(n) for n in names):
        return ("No unit tests were added or changed for these source files: "
                + ", ".join(src[:10]) + ". Every new or changed behavior needs unit tests.")
    return ""


def read(name):
    p = PIPE / name
    return p.read_text() if p.exists() else ""


def commit_and_push(branch, message):
    sh("git", "add", "-A")
    if sh("git", "status", "--porcelain"):
        sh("git", "commit", "-m", message)
    sh("git", "push", "-u", "origin", branch)


def load_agent(name):
    text = (AGENTS / f"{name}.md").read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    meta = dict(line.split(":", 1) for line in m.group(1).splitlines() if ":" in line)
    return {k.strip(): v.strip() for k, v in meta.items()}, m.group(2).strip()


def claude_stage(name, task, max_turns=40, attempt=1):
    meta, body = load_agent(name)
    print(f"\n=== {name} ({meta['model']}) ===", flush=True)
    with REC.stage(name.replace("-", "_"), attempt) if REC else nullcontext():
        r = subprocess.run(
            ["claude", "-p", task, "--model", meta["model"], "--append-system-prompt", body,
             "--permission-mode", "acceptEdits", "--max-turns", str(max_turns),
             "--output-format", "json",
             "--allowedTools", ",".join(t.strip() for t in meta["tools"].split(","))],
            cwd=ROOT, capture_output=True, text=True)
        # JSON output carries token counts and cost. If it is not the expected JSON, the raw text is
        # used exactly as before and no usage is recorded.
        text, usage = parse_claude_output(r.stdout)
        if REC:
            REC.usage(name.replace("-", "_"), meta["model"], usage)
        (PIPE / "logs").mkdir(parents=True, exist_ok=True)
        (PIPE / "logs" / f"{name}.txt").write_text(text + "\n---STDERR---\n" + r.stderr)
        if r.returncode != 0:
            raise RuntimeError(f"{name} failed (exit {r.returncode}):\n{r.stderr[-2000:]}")
        return text.strip()


def install_deps():
    """Install project dependencies on the branch AFTER the developer stage.

    The app (or new dependencies) may not have existed when the job started, so this
    must run before the tester. Override with the PIPELINE_INSTALL_CMD repository variable.
    """
    (PIPE / "logs").mkdir(parents=True, exist_ok=True)
    custom = os.environ.get("PIPELINE_INSTALL_CMD", "").strip()
    cmds = []
    if custom:
        cmds = [custom]
    else:
        if (ROOT / "package.json").exists():
            if (ROOT / "pnpm-lock.yaml").exists():
                cmds.append("corepack enable && (pnpm install --frozen-lockfile || pnpm install)")
            elif (ROOT / "yarn.lock").exists():
                cmds.append("corepack enable && (yarn install --frozen-lockfile || yarn install)")
            elif (ROOT / "package-lock.json").exists():
                cmds.append("npm ci || npm install")
            else:
                cmds.append("npm install")
        if (ROOT / "requirements.txt").exists():
            cmds.append("pip install -r requirements.txt")
        elif (ROOT / "pyproject.toml").exists():
            cmds.append("pip install -e . || pip install .")
    if not cmds:
        print("No dependency manifest found; skipping install.", flush=True)
        return
    log = []
    for c in cmds:
        print(f"Installing dependencies: {c}", flush=True)
        r = subprocess.run(c, shell=True, cwd=ROOT, capture_output=True, text=True)
        log.append(f"$ {c}\n{r.stdout}\n{r.stderr}")
        if r.returncode != 0:
            print(f"  install command failed (exit {r.returncode}); see .pipeline/logs/install.txt", flush=True)
    (PIPE / "logs" / "install.txt").write_text("\n".join(log))


# ---------- Devin ----------
DEVIN = "https://api.devin.ai/v3"
ORG = os.environ.get("DEVIN_ORG_ID", "")
DH = {"Authorization": f"Bearer {os.environ.get('DEVIN_API_KEY', '')}"}


def devin_prompt(branch, feedback, brief=None, budget=None):
    p = f"""You are the Developer stage of an automated pipeline. Work unattended and do not ask questions.

Repository: {REPO}
Branch: {branch}  (already exists; check it out and commit directly to it)

1. Read CLAUDE.md first (project rules, stack, guardrails). Then read .pipeline/spec.md (and .pipeline/design.md if present). Implement exactly what the spec says.
   Follow the patterns it names. Do not add features it did not ask for. Do not refactor unrelated code.
2. Do NOT open a pull request and do NOT touch the main branch. Push your commits to {branch}.
3. Do not edit .pipeline/spec.md or .pipeline/design.md. Do not weaken or delete existing tests.
   WRITE UNIT TESTS for every new or changed behavior, in the project's existing test framework and location (the spec's "Tests to add" section names them). Cover the happy path, the edge cases the spec names, and at least one failure case. A change with no tests will be rejected.
4. Before finishing, install dependencies and run the project's build/type-check/lint and tests (see CLAUDE.md and the project's manifest), and fix any failures you caused.
5. When done, write .pipeline/changes.md (files changed, what each change does, what the Tester should
   focus on, and a BLOCKERS section if anything prevented you from finishing), commit and push it.
   If you are blocked, record the blocker in changes.md and finish rather than waiting for a reply."""
    if budget:
        p += (f"\n\nACU budget: about {budget} ACUs for this whole task. Stay inside it: do not explore beyond what the spec "
              "names, do not rewrite working code, and stop as soon as the acceptance criteria are met and the tests pass.")
    if brief:
        p += ("\n\nTask brief (written to save you time; .pipeline/spec.md is authoritative and the rules above always win):\n"
              + brief)
    if read("acceptance.md").strip():
        p += ("\n\nACCEPTANCE CRITERIA: .pipeline/acceptance.md lists numbered criteria (AC-001, ...) that an external engine checks. "
              "Name at least one automated test per automatable criterion with its id, for example test_AC_003_rejects_empty_name or "
              "it('AC-003 rejects an empty name'). A criterion counts as met only when a passing test names it.")
    if feedback:
        p += f"\n\nThis is a REWORK pass. Fix the problems below, then update changes.md:\n\n{feedback}"
    return p


def devin_run(prompt, timeout_min, acu_limit=None):
    payload = {"prompt": prompt}
    if acu_limit:
        payload["max_acu_limit"] = int(acu_limit)  # Devin's per-session ACU cap
    r = requests.post(f"{DEVIN}/organizations/{ORG}/sessions", headers={**DH, "Content-Type": "application/json"}, json=payload)
    if r.status_code in (400, 422) and "max_acu_limit" in payload:
        DEVIN_WARNINGS.append(f"Devin rejected max_acu_limit={payload['max_acu_limit']} (HTTP {r.status_code}); this session ran without a hard ACU cap.")
        payload.pop("max_acu_limit")
        r = requests.post(f"{DEVIN}/organizations/{ORG}/sessions", headers={**DH, "Content-Type": "application/json"}, json=payload)
    r.raise_for_status()
    s = r.json()
    url = s.get("url")
    print(f"Devin session: {url}", flush=True)
    deadline = time.time() + timeout_min * 60
    idle_polls = 0
    while time.time() < deadline:
        time.sleep(30)
        g = requests.get(f"{DEVIN}/organizations/{ORG}/sessions/{s['session_id']}", headers=DH)
        g.raise_for_status()
        data = g.json()
        status, detail, acus = data.get("status"), data.get("status_detail"), data.get("acus_consumed")
        print(f"  Devin: {status} / {detail} | ACUs: {acus}", flush=True)
        if status in ("exit", "error", "suspended"):
            return url, status, acus
        if detail == "total_session_limit_exceeded":  # documented status detail for the ACU cap
            return url, "acu_limit", acus
        # Devin reports "running / waiting_for_user" when it is idle (finished, or asking a question).
        # Require two consecutive polls so a brief transient state is not mistaken for completion.
        idle_polls = idle_polls + 1 if detail == "waiting_for_user" else 0
        if idle_polls >= 2:
            return url, "waiting_for_user", acus
    raise TimeoutError(f"Devin session {url} exceeded {timeout_min} minutes")


def apply_labels(issue, names):
    """Label the issue with what triage decided. Best effort: labels never fail a run."""
    if not issue or not names:
        return
    for n in names:
        sh("gh", "label", "create", n, "--color", triage_lib.LABEL_COLORS[n.split(":")[0]], "--force", check=False)
    sh("gh", "issue", "edit", issue, "--add-label", ",".join(names), check=False)


def tester_task(demo):
    task = "Do your job for the changes on this branch."
    if demo["status"] == "ok":
        shots = ", ".join(demo["screenshots"])
        task += (f"\n\nDEMO: screenshots of the running app are in .pipeline/demo/ ({shots}) with a report in .pipeline/demo/report.json "
                 "(HTTP status, console errors and failed requests per page). Open each image with the Read tool and compare it with the "
                 "acceptance criteria in .pipeline/spec.md. Add a '## Demo' section to test-results.md saying, per screenshot, what is "
                 "visible and which acceptance criterion it confirms. Then add a line `DEMO: PASS` (everything the criteria describe is "
                 "visible, no error page) or `DEMO: FAIL` (something is missing, wrong or shows an error). If DEMO is FAIL, RESULT must be FAIL.")
    else:
        task += (f"\n\nDEMO: no screenshots were captured ({demo.get('reason') or 'not needed'}). Add the line `DEMO: SKIPPED` "
                 "and one sentence saying why to test-results.md. Do not invent a demo.")
    return task


def demo_markdown(demo, branch):
    if demo["status"] != "ok":
        return f"## Demo\nNo screenshots: {demo.get('status')} ({demo.get('reason') or 'not needed for this change'}).\n"
    out = ["## Demo", "Screenshots of the running app, captured by the pipeline on this branch:", ""]
    for p in demo["pages"]:
        if not p.get("file"):
            out.append(f"- `{p['path']}`: could not be captured ({p.get('error', 'unknown error')})")
            continue
        url = f"https://github.com/{REPO}/blob/{branch}/.pipeline/demo/{p['file']}?raw=true"
        notes = []
        if p.get("http_status") and p["http_status"] >= 400:
            notes.append(f"HTTP {p['http_status']}")
        if p.get("console_errors"):
            notes.append(f"{len(p['console_errors'])} console error(s)")
        out += [f"**`{p['path']}`** {p.get('title') or ''}" + (f" ({', '.join(notes)})" if notes else ""), f"![{p['path']}]({url})", ""]
    return "\n".join(out) + "\n"


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("idea")
    ap.add_argument("--until", choices=STAGES, default="review", help="stop after this stage")
    ap.add_argument("--max-retries", type=int, default=2)
    ap.add_argument("--devin-timeout", type=int, default=180, help="minutes")
    ap.add_argument("--fix-branch", default="", help="existing pipeline branch: apply the feedback in IDEA to it (no research/plan)")
    a = ap.parse_args()
    fix = bool(a.fix_branch)
    started = time.time()

    title = next((l.strip().lstrip("#").strip() for l in a.idea.splitlines() if l.strip()), a.idea)[:60]
    run_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    branch = a.fix_branch or f"pipeline/{run_id}"
    if fix:
        sh("git", "fetch", "origin", branch)
        sh("git", "checkout", branch)
        sh("git", "pull", "--ff-only", "origin", branch)
    else:
        sh("git", "checkout", "-b", branch)
    if os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"branch={branch}\n")
    # Start every run with a clean handoff folder: files from an earlier run that was merged into
    # the default branch (spec.md, test-results.md, ...) must not leak into this one.
    if PIPE.exists() and not fix:
        for child in PIPE.iterdir():
            if child.name != ".gitkeep":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    PIPE.mkdir(exist_ok=True)
    (PIPE / ".gitkeep").touch()
    if fix:  # keep the original idea and spec; record the feedback
        with open(PIPE / "fixes.md", "a") as f:
            f.write(f"\n## Fix request {run_id}\n{a.idea}\n")
    else:
        (PIPE / "idea.md").write_text(a.idea + "\n")
    global REC
    REC = Recorder(ROOT, run_id, "fix" if fix else "run", a.until, branch,
                   enabled=os.environ.get("PIPELINE_METRICS", "1") != "0")
    summary = [f"# Pipeline {'fix' if fix else 'run'} {run_id}", f"{'Feedback' if fix else 'Idea'}: {a.idea}", f"Branch: `{branch}`", ""]

    def write_summary():
        out = "\n".join(summary)
        print("\n" + out)
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            Path(os.environ["GITHUB_STEP_SUMMARY"]).write_text(out)
        # The workflow posts this file to the issue so you can see why a run stopped.
        (Path(os.environ.get("RUNNER_TEMP", tempfile.gettempdir())) / "pipeline-summary.md").write_text(out)

    def stop(stage, note=None, code=0, reason=None, post=None):
        """End the run. Finishes the metrics record first so the final record is in the pushed commit."""
        if note:
            summary.append(note)
        if stage == "done":
            REC.finish("success", "completed")
        elif code:
            REC.finish("failure", reason or f"stopped_at_{stage}")
        else:
            REC.finish("stopped", reason or f"until_{stage}")
        commit_and_push(branch, f"pipeline: {stage}")
        write_summary()
        if post:
            post()
        sys.exit(code)

    def reached(stage):
        return a.until == stage

    cap = triage_lib.max_acu()
    issue = os.environ.get("ISSUE", "").strip()
    issue = issue if issue.isdigit() else ""
    brief = None
    sve_on = sve_lib.enabled()
    sve_state, sve_result = None, None

    try:
        if fix:  # the original triage answer (if any) is on the branch; a human asked for this fix, so never stop on it
            tri = triage_lib.decide(triage_lib.parse(read("triage.md")), cap, force=True)
            brief = read("devin-brief.md").strip() or None
            if sve_on and read("sve.json").strip():
                sve_state = json.loads(read("sve.json"))
        else:
            if os.environ.get("PIPELINE_TRIAGE", "1") != "0":
                claude_stage("triage", "Do your job for the idea in .pipeline/idea.md.", max_turns=15)
            tri = triage_lib.decide(triage_lib.parse(read("triage.md")), cap, force=triage_lib.forced(a.idea))
            REC.triage(tri)
            apply_labels(issue, triage_lib.labels(tri))
            if tri["parsed"]:
                summary.append(f"Triage: **{tri['kind'] or '?'}**, size **{tri['size'] or '?'}**, route **{tri['route']}**, "
                               f"ACU budget **{tri['acu_budget'] if tri['acu_budget'] else 'not set'}**"
                               + (f" ({tri['reason']})" if tri.get("reason") else ""))
            else:
                summary.append("Triage: no usable answer, so the full route and the run-wide ACU cap are used.")
            if tri["route"] == "stop":
                stop("triage", "**Stopped by triage: this ask needs no code change.** "
                     + (tri.get("reason") or "") + "\n\nWhat to do instead is in `.pipeline/triage.md` on the branch. "
                     "To build anyway, add a line `FORCE: yes` to the brief and run `/go` again, or set the repository variable PIPELINE_TRIAGE=0.",
                     reason="triage_no_code")
            if reached("triage"): stop("triage", "Stopped after triage.")

        if not fix:
            if tri["route"] == "light":
                (PIPE / "research.md").write_text("Research skipped by triage: this is a small change whose files are obvious. See .pipeline/idea.md and .pipeline/triage.md.\n")
                summary.append("Research stage skipped (light route).")
            else:
                claude_stage("researcher", "Do your job for the idea in .pipeline/idea.md.")
            if reached("research"): stop("research")

            claude_stage("planner", "Do your job for the idea in .pipeline/idea.md.")
            spec = read("spec.md")
            if not re.search(r"^STATUS:\s*READY", spec, re.M):
                stop("plan", "**Planner marked the spec BLOCKED.** Read .pipeline/spec.md on the branch.", reason="planner_blocked")
            if reached("plan"): stop("plan", "Stopped after plan.")

            if re.search(r"NEEDS_DESIGN:\s*yes", spec, re.I):
                claude_stage("designer", "Do your job for the spec in .pipeline/spec.md.")
                summary.append("Design brief produced (.pipeline/design.md).")
            if reached("design"): stop("design", "Stopped after design.")

            pe = prompt_engineer.backend()
            if pe != "off":
                with (nullcontext() if pe == "claude" else REC.stage("prompt_engineer")):
                    brief, pe_status = prompt_engineer.generate(
                        pe, load_agent("prompt-engineer")[1], read("spec.md"), read("design.md"),
                        claude_stage=claude_stage, brief_path=PIPE / "devin-brief.md")
                REC.prompt_engineer(pe, pe_status)
                if brief:
                    (PIPE / "devin-brief.md").write_text(brief + "\n")
                    summary.append(f"Prompt engineer ({pe}): brief written (.pipeline/devin-brief.md).")
                else:
                    (PIPE / "devin-brief.md").unlink(missing_ok=True)
                    summary.append(f"Prompt engineer ({pe}): {pe_status}; the default developer prompt was used.")
            if sve_on:
                try:
                    sve_state = sve_lib.prepare(a.idea, title, os.environ)
                    (PIPE / "acceptance.md").write_text(sve_state.pop("markdown"))
                    (PIPE / "sve.json").write_text(json.dumps(sve_state, indent=2) + "\n")
                    summary.append(f"Specification: {sve_state['criteria']} acceptance criteria from SVE "
                                   f"(`{sve_state['specification_id']}`), written to .pipeline/acceptance.md.")
                except sve_lib.SveError as e:
                    sve_state = None
                    summary.append(f"Specification verification unavailable: {scrub(e, 300)}. The branch cannot be marked verified.")
            commit_and_push(branch, "pipeline: spec and design")

        feedback = ("Human feedback on the pull request. Apply it, keep every existing test passing, "
                    "and add tests for any behavior you change:\n" + a.idea) if fix else None
        verdict, result, devin_urls = "UNKNOWN", "UNKNOWN", []
        demo = {"status": "skipped", "reason": "not needed for this change", "screenshots": [], "pages": []}
        REC.devin_budget(tri["acu_budget"], tri["acu_limit"])
        for attempt in range(a.max_retries + 1):
            sve_result = None  # each attempt is judged on its own
            used = REC.data["devin"]["acus_consumed"]
            if attempt > 0 and used is not None and used >= tri["cap"]:
                stop("dev", f"**Stopped before another Devin attempt: {used:g} ACUs are already used, and the run-wide cap is {tri['cap']}.** "
                     "Raise the repository variable PIPELINE_MAX_ACU, or split the task into smaller ones.", code=1, reason="acu_cap_reached")
            print(f"\n##### Developer attempt {attempt + 1} #####", flush=True)
            with REC.stage("developer", attempt + 1):
                url, status, acus = devin_run(devin_prompt(branch, feedback, brief, tri["acu_budget"]), a.devin_timeout,
                                              acu_limit=tri["acu_limit"])
            REC.developer_attempt(acus)
            acu_text = f"{acus} ACUs" if isinstance(acus, (int, float)) and not isinstance(acus, bool) else "ACUs not reported"
            devin_urls.append(f"{url} ({acu_text})")
            before = sh("git", "rev-parse", "HEAD")
            sh("git", "pull", "--ff-only", "origin", branch)
            if sh("git", "rev-parse", "HEAD") == before:
                hit_limit = status == "acu_limit" or (isinstance(acus, (int, float)) and not isinstance(acus, bool) and acus >= tri["acu_limit"])
                if hit_limit:
                    stop("dev", f"**Devin reached its ACU limit ({acu_text} of {tri['acu_limit']}) before pushing any commits.** "
                         f"Raise PIPELINE_MAX_ACU or split the task. Session: {url}", code=1, reason="acu_limit_reached")
                stop("dev", f"**Devin finished ({status}) but pushed no commits.** Open the session to see why (often: Devin cannot access the repo). Session: {url}", code=1, reason="devin_no_commits")
            if reached("dev"): stop("dev", f"Stopped after dev. Devin session: {url} ({acu_text})")
            with REC.stage("install", attempt + 1):
                install_deps()

            shutil.rmtree(PIPE / "demo", ignore_errors=True)
            demo_enabled = os.environ.get("PIPELINE_DEMO", "1") != "0"
            if tri["needs_demo"] and demo_enabled:
                with REC.stage("demo", attempt + 1):
                    demo = demo_mod.run_demo(ROOT, PIPE / "demo", os.environ, PIPE / "logs")
                REC.demo(demo["status"], len(demo["screenshots"]), demo.get("reason"))
            else:
                demo = {"status": "skipped", "screenshots": [], "pages": [],
                        "reason": "not needed for this change" if not tri["needs_demo"] else "turned off (PIPELINE_DEMO=0)"}
                REC.demo("not_needed" if not tri["needs_demo"] else "skipped", 0, demo["reason"])

            claude_stage("tester", tester_task(demo), max_turns=60, attempt=attempt + 1)
            results = read("test-results.md")
            m_demo = re.search(r"^DEMO:\s*(PASS|FAIL|SKIPPED)", results, re.M)
            REC.demo_confirmed(m_demo.group(1) if m_demo else ("missing" if demo["status"] == "ok" else None))
            result = "PASS" if re.match(r"\s*RESULT:\s*PASS", results) else "FAIL"
            gap = missing_tests() if result == "PASS" else ""
            if gap:
                result = "FAIL"
                results = f"RESULT: FAIL\n{gap}\n\n(Tester report below)\n{results}"
                (PIPE / "test-results.md").write_text(results)
            sve_block = False
            if result == "PASS" and sve_on:
                if sve_state is None:
                    sve_result = sve_lib.unverified("SVE was unavailable when the specification was prepared.")
                else:
                    sve_result = sve_lib.verify(sve_state, os.environ, commit_sha=sh("git", "rev-parse", "HEAD"), root=ROOT)
                (PIPE / "verification.md").write_text(sve_result["report"])
                if sve_state is not None and sve_lib.blocks(sve_result):
                    sve_block = True
                    result = "FAIL"
                    results = f"RESULT: FAIL\n{sve_lib.summary_line(sve_result)}\n\n{sve_lib.feedback(sve_result)}\n\n(Tester report below)\n{results}"
                    (PIPE / "test-results.md").write_text(results)
            REC.tests(result, gate_failed=bool(gap) or sve_block)
            commit_and_push(branch, f"pipeline: tests (attempt {attempt + 1}) {result}")
            if result == "FAIL" and attempt < a.max_retries:
                feedback = "Tests failed:\n" + results
                REC.retry("tests_failed")
                continue
            if reached("test"): stop("test", f"Stopped after test. Result: {result}")

            review = claude_stage(
                "reviewer", f"Review this branch against origin/{BASE_BRANCH}. Base branch: {BASE_BRANCH}.",
                attempt=attempt + 1)
            (PIPE / "review.md").write_text(review + "\n")
            m = re.search(r"VERDICT:\s*(SHIP|NEEDS WORK|BLOCK)", review)
            verdict = m.group(1) if m else "UNKNOWN"
            REC.review(verdict)
            commit_and_push(branch, f"pipeline: review (attempt {attempt + 1}) {verdict}")
            if verdict == "NEEDS WORK" and attempt < a.max_retries:
                feedback = "Reviewer said NEEDS WORK:\n" + review
                REC.retry("needs_work")
                continue
            break

        if sve_on and sve_result is None:
            sve_result = sve_lib.unverified("The tests did not pass, so specification verification did not run.")
        if sve_result is not None and sve_lib.blocks(sve_result) and verdict == "SHIP":
            summary.append("Verdict lowered from SHIP to NEEDS WORK: the specification is not verified.")
            verdict = "NEEDS WORK"
        minutes = (time.time() - started) / 60
        total_acus = REC.data["devin"]["acus_consumed"]  # None when Devin reported no ACUs: never shown as 0
        total_acu_text = f"{total_acus:g} ACUs" if total_acus is not None else "ACUs not reported"
        summary += DEVIN_WARNINGS
        summary.append("ACU check: " + triage_lib.acu_line(total_acus, tri["acu_budget"], tri["cap"]))
        if demo["status"] == "ok":
            summary.append(f"Demo: {len(demo['screenshots'])} screenshot(s) captured; tester confirmation: **{REC.data['demo']['confirmed'] or 'none'}**.")
        elif tri["needs_demo"]:
            summary.append(f"Demo: {demo['status']} ({demo.get('reason')}).")
        if sve_result is not None:
            summary.append(sve_lib.summary_line(sve_result))
        summary += [f"Tests: **{result}**", f"Verdict: **{verdict}**",
                    "Devin sessions: " + ", ".join(devin_urls),
                    f"Metrics: {minutes:.0f} min, {len(devin_urls)} Devin attempt(s), {total_acu_text} "
                    f"(full record: metrics/runs/{run_id}{"-fix" if fix else ""}.json)"]
        sve_md = ("## Specification verification\n" + sve_result["report"][:20000] + "\n") if sve_result is not None else ""
        body = ("\n".join(summary) + "\n\n" + (demo_markdown(demo, branch) + "\n" if tri["needs_demo"] else "")
                + sve_md + "---\n\n" + read("review.md"))
        (PIPE / "pr-body.md").write_text(body)
        with REC.stage("pull_request"):
            if fix:
                old_title = sh("gh", "pr", "view", branch, "--json", "title", "--jq", ".title")
                clean = re.sub(r"^\[pipeline [A-Z ]+\]\s*", "", old_title)
                sh("gh", "pr", "comment", branch, "--body-file", str(PIPE / "pr-body.md"))
                sh("gh", "pr", "edit", branch, "--title", f"[pipeline {verdict}] {clean}")
                REC.pull_request(updated=True, url=sh("gh", "pr", "view", branch, "--json", "url", "--jq", ".url", check=False))
            else:
                out = sh("gh", "pr", "create", "--draft", "--base", BASE_BRANCH, "--head", branch,
                         "--title", f"[pipeline {verdict}] {title}", "--body-file", str(PIPE / "pr-body.md"))
                REC.pull_request(created=True, url=out.splitlines()[-1] if out else None)
        # Pull requests opened with the Actions token do not trigger CI by themselves; start it on the
        # final commit (after the metrics record is pushed).
        stop("done", post=lambda: sh("gh", "workflow", "run", "ci.yml", "--ref", branch, check=False))
    except SystemExit:
        raise
    except Exception as e:
        # Push whatever exists (including logs) so failures can be diagnosed from the branch.
        summary.append(f"**FAILED:** {scrub(e, 1500)}")
        REC.finish("failure", "exception", error=e, force=True)
        try:
            commit_and_push(branch, "pipeline: failed (logs attached)")
        except Exception as e2:
            print(f"Could not push failure branch: {e2}")
        write_summary()
        raise


if __name__ == "__main__":
    main()
