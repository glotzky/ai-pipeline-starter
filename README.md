<!--
HOW TO DEVELOP THIS FILE (invisible when rendered on GitHub)
Purpose: the front page. A stranger should learn in one minute what this is, what is proven, and how to start.
Edit it when: you add/remove a doc, workflow or script; a verification status changes; the quick start changes.
How:
  1. Keep the "Documentation map" numbering in step with the files in docs/ (check: ls docs).
  2. Keep the "Verification status" table honest. Mark something "Verified live" only after you ran it in
     GitHub Actions. Change "not yet run live" rows the moment you run them.
  3. Keep the disclaimer block. Do not add names, keys or repo names of your own projects.
  4. After editing: check every relative link still resolves (see MAINTAINING.md, "Link check").
  5. Record the change in CHANGELOG.md.
-->
# AI Software-Engineering Pipeline Starter

A reusable kit that turns a rough idea into a reviewed draft pull request, mostly without you.
You file an idea from your phone; AI agents interview you, research, plan, (optionally) design, build, test and review it, then leave a draft PR for **you** to approve.

```
Idea (GitHub issue) -> Interviewer -> /go -> Researcher -> Planner -> [Designer]
        -> Developer (Devin) -> Tester -> Reviewer -> draft PR -> YOU merge
```

Everything runs in the cloud (GitHub Actions + Anthropic API + Devin). **No always-on computer is needed.**
It works for any project and any stack; the project-specific parts live in one file, `CLAUDE.md`.

Created by Gil Lotzky. Licensed under the [MIT License](LICENSE).

> **Read before you use it.** This kit gives AI agents write access to a repository and runs AI-written code with your keys in the environment. It is provided as is, without warranty. Several parts are written but not yet verified end to end (see the [verification status](#verification-status-read-this)). You are responsible for your keys, your spend limits and everything you merge. Devin, Claude, GitHub, Vercel and other product names belong to their owners; this project is independent and not affiliated with or endorsed by them.

## What is in this package

| Path | What it is |
|---|---|
| `template/` | The files that get copied into your repo: 8 workflows (intake, pipeline, CI, commands, project plan, queue, health check), 3 issue forms (idea, bug, project), a PR template, Dependabot and CODEOWNERS config, 7 agent prompts, the orchestrator `run.py`, `project_plan.py`, a `CLAUDE.md` template |
| `tests/` | The kit's own tests (`python3 -m unittest discover -s tests`). Not installed into projects |
| `install/` | One-command installers for macOS/Linux (`install.sh`) and Windows (`install.ps1`), secrets/environment setup scripts, and repo-hardening scripts (`harden-repo.sh` / `.ps1`) |
| `docs/` | The guides (below) |

## Documentation map

0. **[User manual: setup -> new idea -> publish](docs/00-user-manual.md)**: start here
1. [Overview and architecture](docs/01-overview.md): how it works and why it is built this way
2. [Requirements and costs](docs/02-requirements-and-costs.md): accounts, plans, realistic monthly cost
3. [Setup guide](docs/03-setup-guide.md): step by step for macOS, Windows and Linux
4. [Using the pipeline](docs/04-using-the-pipeline.md): **when you must interact, when you do not, and exactly how**
5. [Customizing](docs/05-customizing.md): stacks, models, agents, stages
6. [Multiple projects and hosting](docs/06-multiple-projects-and-hosting.md): one pipeline or many; do you need a computer
7. [Troubleshooting](docs/07-troubleshooting.md): every error we hit, with fixes
8. [Lessons learned](docs/08-lessons-learned.md): what we discovered building it
9. [Security](docs/09-security.md): what is protected, what is not
10. [Phone use and the decision map](docs/10-phone-and-decision-map.md): diagram of the whole flow, what you can do from a phone, roadmap
11. [Local models (Ollama)](docs/11-local-models-ollama.md): optional, probably not worth it
12. [Gap analysis](docs/12-gap-analysis.md): what a strong engineering team does that this does not yet, ranked
13. [Engineering practices](docs/13-engineering-practices.md): how each team practice is covered, where it lives and its verification status
14. [Optional: Vercel](docs/14-optional-vercel.md): previews and hosting, adopt later, not part of the pipeline
15. [Updating your projects](docs/15-updating.md): pull starter improvements into every project without losing your edits
16. [Triage, ACU budget, prompt engineer, demo screenshots](docs/16-triage-acu-prompting-demo.md): cheaper runs and a visible demo (v1.3)
15. [Tools used](docs/tools.md) and [Cheat sheet](docs/cheatsheet.md)

## Quick start (about 45 minutes, most of it account setup)

1. Create accounts and keys: GitHub, Anthropic API, Devin ([requirements](docs/02-requirements-and-costs.md)).
2. Install the template into your repo:
   - macOS / Linux: `./install/install.sh /path/to/your/repo`
   - Windows (PowerShell): `.\install\install.ps1 -Target C:\path\to\your\repo`
3. Fill in `CLAUDE.md`, commit on a branch, open a PR, merge it into your default branch.
4. Create the GitHub environment and secrets (`install/set-secrets.sh` / `.ps1`, or by hand).
5. Run **Actions -> Health check**.
6. Harden the repo: `./install/harden-repo.sh OWNER/REPO` (optional but recommended).
7. File your first idea: **Issues -> New issue -> Idea**, then reply `/go plan`.

Full details: [Setup guide](docs/03-setup-guide.md).

## Verification status (read this)

This kit was built interactively and tested in stages. Be clear about what is proven:

| Area | Status |
|---|---|
| GitHub environment + secrets wiring, Health check workflow | Verified live |
| Devin API: service-user key creates a session from a workflow | Verified live |
| Anthropic key + Claude CLI call inside Actions | Verified live |
| `install.sh` on a scratch repo (keeps existing files, idempotent) | Verified locally |
| YAML parses, `run.py` compiles, bash scripts pass syntax check | Verified locally |
| Issue interviewer, `/go` dispatch, research and plan stages in Actions | Verified live (design stage not yet triggered) |
| Report-back comment on the issue | Verified live |
| Devin building on a branch, tester, reviewer, draft PR | Verified in a live full run (reported by the author: the draft PR was raised and merged). Later changes to these stages are tracked in the rows below |
| CI workflow, `/fix`, `/status`, `/stop`, `/queue`, `[project]` planner and queue, `[bug]` form, one-run-at-a-time, `metrics.json` | Written. `run.py` fix mode, metrics and CI dispatch tested with stubs in a scratch repo; `project_plan.py` parsing tested; **workflows not yet run in Actions** |
| `harden-repo.sh` / `.ps1`, `CODEOWNERS`, `dependabot.yml`, PR template | Written, `install.sh` tested (owner fill-in, keep-existing); **hardening scripts never run against live GitHub**; PowerShell scripts untested |
| Unit-test enforcement (planner, Devin, tester, reviewer prompts plus an orchestrator gate) | Live runs produced unit-test files alongside the code; the gate itself was tested in a scratch repo and **has not yet been seen blocking a run in Actions** |
| Run metrics (`metrics/`, `pipeline/run_metrics.py`): per-run JSON record, schema, summary script, artifact upload | Tests pass locally. **Live:** two real pipeline runs committed `metrics/runs/*.json` records to the project. Still to review: the record contents and the Actions artifact upload |
| Install, `install.sh --upgrade` and `pipeline/update.sh` (download from GitHub by tag) | **Verified live** on a real project (v1.1.0): first install over an older install, upgrade keeping Dependabot action versions, and a download of the tagged release. The v1.2.0 pull-request and `--check` modes are tested locally against stubs and a local bare repo, **not yet run against real GitHub**. PowerShell installer is first-install only and untested |
| Triage, ACU budget, prompt engineer, demo screenshots (v1.3) | Tested locally: parsing, routing, labels, ACU limit/budget/cap against a fake Devin, prompt-engineer backends against local stub servers, and the demo step against real headless Chromium. **Not yet run in Actions or against the real Devin API** (the `max_acu_limit` field, Playwright and Ollama on a runner, how screenshots show in the GitHub mobile app) |
| Failure watch and Update check workflows; `queue.yml` environment fix | Written and merged into a real project, **not yet triggered** (they run only when a workflow fails, on Mondays, or when a pipeline PR is merged) |
| Clean `.pipeline/` at run start, stop reason in the issue comment, loud failure when Devin pushes nothing | Written, tested in a scratch repo, **not yet run in Actions** |
| `install_deps()` step, `install.ps1`, `set-secrets.sh/.ps1` | Written, **not tested** |

Use the staged first run in the setup guide (`/go plan`, then `/go dev`, then `/go`) so problems surface cheaply.
Vendor details (Devin plans, API behavior, model names and prices) change; they were current in October 2026. Re-check before relying on them.
