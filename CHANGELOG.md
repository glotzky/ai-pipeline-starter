<!--
HOW TO DEVELOP THIS FILE (invisible when rendered on GitHub)
Purpose: a dated list of what changed in each release, newest first.
Edit it when: you tag a release (git tag vX.Y.Z).
How:
  1. Add a new "## X.Y.Z (YYYY-MM-DD)" section at the top. Never edit old sections.
  2. Version rule: patch (1.0.1) = doc or bug fixes; minor (1.1.0) = new workflow, command or doc;
     major (2.0.0) = a change that needs users to redo setup or breaks installed copies.
  3. List what changed in plain words, and what is still unverified.
  4. Then: git tag vX.Y.Z && git push --tags
-->
# Changelog

## 1.1.0 (unreleased)
- Per-run metrics: `metrics/` (schema, README, `summarize.py`) and `pipeline/run_metrics.py`, wired into `run.py`. Records stage timings, retries, tests, verdict, PR, Devin ACUs, Claude tokens and CLI-reported cost; saved on the run branch and as an Actions artifact; incomplete runs are recorded honestly; no secrets or free text.
- Claude stages now call `claude -p --output-format json` to get usage; output that is not that JSON is used as before.
- A fix run writes `<run_id>-fix.json`. The `.pipeline/metrics.json` file added earlier is replaced by `metrics/runs/`.
- Added `tests/` (50 tests). Not yet run in GitHub Actions.

## 1.0.0 (2026-10-25)
First release.

- Pipeline: interviewer, researcher, planner, optional designer, Devin developer, tester, read-only reviewer, orchestrator `run.py`, draft PR, report-back comment.
- Intake from GitHub issues with `/go` stages (`plan`, `dev`, `test`, `review`).
- Unit-test enforcement at planner, developer, tester, orchestrator gate and reviewer.
- CI workflow, `/fix`, `/status`, `/stop`, `/queue`, `[project]` planner and queue, `[bug]` form, one run at a time, per-run `metrics.json`.
- Installers for macOS, Linux and Windows; secrets and repo-hardening scripts.
- Documentation: user manual, setup, usage, customizing, multiple projects, troubleshooting, lessons learned, security, gap analysis, engineering practices, optional Vercel, local models.
- Known limits: the newest workflows (`/fix`, queue, project plan, CI) and the hardening and PowerShell scripts have not been run against live GitHub. See the verification table in the README.
