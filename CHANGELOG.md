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

## 1.3.0 (unreleased)

- **Specification verification (optional)** (`pipeline/sve_lib.py`, `docs/18-spec-verification.md`): with `PIPELINE_SVE_URL` set, an external Specification Verification Engine turns the idea into numbered acceptance criteria before the developer starts (`.pipeline/acceptance.md`), and after the tester the pipeline runs the project's tests, uploads the JUnit result, and has the engine judge each criterion from test evidence only. Default gate `enforce`: not fully verified means a developer retry and a final `SHIP` is lowered to `NEEDS WORK`; `report` only informs. An unreachable engine never crashes a run and is never reported as verified. Off by default; unchanged when unset. Verified against a stand-in server and the real `run.py`; **not yet run live in GitHub Actions**.
- **Triage stage** (`.claude/agents/triage.md`, `pipeline/triage_lib.py`): labels the ask (`kind:`, `size:`, `route:`), skips research for small asks, stops no-code asks before any spend (and says so instead of reporting success), sets an ACU budget. `FORCE: yes` overrides a stop. `/go triage` stops after it. Off with `PIPELINE_TRIAGE=0`.
- **ACU budget:** the budget goes into the developer prompt and to Devin as `max_acu_limit`; `PIPELINE_MAX_ACU` (default 10) caps the whole run; every summary and metrics record states whether the run stayed inside its budget (unknown stays unknown).
- **Demo screenshots** (`pipeline/demo.py`): the app is started without the pipeline's secrets, pages are captured with headless Chromium, and the tester reads the images and writes `DEMO: PASS|FAIL|SKIPPED`. Screenshots go on the branch, in the PR description and in an Actions artifact.
- **Prompt engineer** (`pipeline/prompt_engineer.py`, optional): backends `claude`, `ollama`, `openai`-compatible; output validated; always falls back to the default prompt. Workflow step can install Ollama on the runner.
- Metrics schema: optional `triage`, `prompt_engineer`, `demo` objects and `devin.acu_budget/acu_limit/over_budget`; `summarize.py` reports the within-budget rate, triage routes and demo pass rate.
- The workflow now passes `PIPELINE_REQUIRE_TESTS` through. Tests check that every variable the pipeline reads is wired in `pipeline.yml`, and that the health check knows every module and agent.
- See `docs/16-triage-acu-prompting-demo.md`.

## 1.2.1 (2026-10-26)

- **Fixed:** `update-check.yml` was invalid YAML (issue text at column 0 inside a `run: |` block), so GitHub rejected the workflow. Its issue body is now written with `echo`. New `tests/test_yaml.py` parses every template YAML file (with PyYAML when installed, and with a dependency-free check that catches this exact mistake), so an invalid workflow can no longer ship unnoticed.

## 1.2.0 (2026-10-26)

- **`bash pipeline/update.sh` now opens a pull request** (new branch `pipeline-update/vX.Y.Z`, commit, push, `gh pr create`); it never merges. `--check` reports whether a project matches the starter without changing anything; `--local` keeps the old apply-to-working-folder behaviour. See `docs/15-updating.md`.
- **Fixed:** the installer printed "updated .gitignore" on every run even when it added nothing.

## 1.1.0 (2026-10-26)
- Per-run metrics: `metrics/` (schema, README, `summarize.py`) and `pipeline/run_metrics.py`, wired into `run.py`. Records stage timings, retries, tests, verdict, PR, Devin ACUs, Claude tokens and CLI-reported cost; saved on the run branch and as an Actions artifact; incomplete runs are recorded honestly; no secrets or free text.
- Claude stages now call `claude -p --output-format json` to get usage; output that is not that JSON is used as before.
- A fix run writes `<run_id>-fix.json`. The `.pipeline/metrics.json` file added earlier is replaced by `metrics/runs/`.
- Added `tests/` (52 tests at the time, passing on Linux and macOS). Not yet run in GitHub Actions.
- **Upgrades:** the installer writes `.pipeline-version`; `install.sh --upgrade` updates files you have not edited, writes `.pipeline-new` beside ones you have, and never touches `CLAUDE.md` etc. New weekly **Update check** workflow opens an issue when a newer tagged version exists. See `docs/15-updating.md`.
- `pipeline/update.sh` in every project: `bash pipeline/update.sh` downloads the newest tagged starter from GitHub and runs the upgrade. Anyone who installed from your repository receives your updates this way, with their own edits kept.
- **Fixed:** the installer stopped silently on a first install over an older install (no `.pipeline-version` yet); now covered by a test.
- **Fixed:** install and upgrade keep the GitHub Action versions a project already uses (Dependabot bumps), instead of downgrading them to the template's pins.
- **Failure watch:** new workflow that opens a `[bug]` issue (run link plus failing log lines) when CI, Queue, Intake, Commands or Project plan fails; you reply `/go` and the pipeline opens a draft PR. Optional `PIPELINE_AUTO_FIX=true` starts CI fixes automatically (max 3 per 24 h).
- **Fixed:** `queue.yml` used `environment:` on a `pull_request` job, so an environment limited to `main` refused it (`Branch "refs/pull/N/merge" is not allowed to deploy`). A test now blocks `environment:` on any pull_request workflow.
- The installer no longer copies `__pycache__`, `.pyc` or `.DS_Store` files; the tests no longer create them inside `template/`; added installer tests.
- The PR and issue summary now says "ACUs not reported" instead of showing "None" or a made-up 0.0 when Devin reports no ACUs.

## 1.0.0 (2026-10-25)
First release.

- Pipeline: interviewer, researcher, planner, optional designer, Devin developer, tester, read-only reviewer, orchestrator `run.py`, draft PR, report-back comment.
- Intake from GitHub issues with `/go` stages (`plan`, `dev`, `test`, `review`).
- Unit-test enforcement at planner, developer, tester, orchestrator gate and reviewer.
- CI workflow, `/fix`, `/status`, `/stop`, `/queue`, `[project]` planner and queue, `[bug]` form, one run at a time, per-run `metrics.json`.
- Installers for macOS, Linux and Windows; secrets and repo-hardening scripts.
- Documentation: user manual, setup, usage, customizing, multiple projects, troubleshooting, lessons learned, security, gap analysis, engineering practices, optional Vercel, local models.
- Known limits: the newest workflows (`/fix`, queue, project plan, CI) and the hardening and PowerShell scripts have not been run against live GitHub. See the verification table in the README.
