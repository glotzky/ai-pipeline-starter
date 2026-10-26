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

## 1.2.0 (unreleased)

- **`bash pipeline/update.sh` now opens a pull request** (new branch `pipeline-update/vX.Y.Z`, commit, push, `gh pr create`); it never merges. `--check` reports whether a project matches the starter without changing anything; `--local` keeps the old apply-to-working-folder behaviour. See `docs/15-updating.md`.
- **Fixed:** the installer printed "updated .gitignore" on every run even when it added nothing.

## 1.1.0 (2026-10-26)
- Per-run metrics: `metrics/` (schema, README, `summarize.py`) and `pipeline/run_metrics.py`, wired into `run.py`. Records stage timings, retries, tests, verdict, PR, Devin ACUs, Claude tokens and CLI-reported cost; saved on the run branch and as an Actions artifact; incomplete runs are recorded honestly; no secrets or free text.
- Claude stages now call `claude -p --output-format json` to get usage; output that is not that JSON is used as before.
- A fix run writes `<run_id>-fix.json`. The `.pipeline/metrics.json` file added earlier is replaced by `metrics/runs/`.
- Added `tests/` (94 tests, passing on Linux and macOS). Not yet run in GitHub Actions.
- **Upgrades:** the installer writes `.pipeline-version`; `install.sh --upgrade` updates files you have not edited, writes `.pipeline-new` beside ones you have, and never touches `CLAUDE.md` etc. New weekly **Update check** workflow opens an issue when a newer tagged version exists. See `docs/15-updating.md`.
- `pipeline/update.sh` in every project: `bash pipeline/update.sh` downloads the newest tagged starter from GitHub and runs the upgrade. Anyone who installed from your repository receives your updates this way, with their own edits kept.
- **Fixed:** the installer stopped silently on a first install over an older install (no `.pipeline-version` yet); now covered by a test.
- **Fixed:** install and upgrade keep the GitHub Action versions a project already uses (Dependabot bumps), instead of downgrading them to the template's pins.
- **Failure watch:** new workflow that opens a `[bug]` issue (run link plus failing log lines) when CI, Queue, Intake, Commands or Project plan fails; you reply `/go` and the pipeline opens a draft PR. Optional `PIPELINE_AUTO_FIX=true` starts CI fixes automatically (max 3 per 24 h).
- **Fixed:** `queue.yml` used `environment:` on a `pull_request` job, so an environment limited to `main` refused it (`Branch "refs/pull/N/merge" is not allowed to deploy`). A test now blocks `environment:` on any pull_request workflow.
- The installer no longer copies `__pycache__`, `.pyc` or `.DS_Store` files; the tests no longer create them inside `template/`; added installer tests (94 tests in total).
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
