# 17. Development handoff: read this first when continuing work on the kit

**Author:** Gil Lotzky · **Purpose:** let a new AI chat (or a new contributor) pick up development of this kit without the old conversation. Keep it current: update the "State" and "Open items" sections whenever a release is tagged.

## How to start a new chat

Open a new chat in a place where the assistant can read this repository (a clone, or the attached files), then paste:

> Read `docs/17-development-handoff.md`, `MAINTAINING.md` and `CHANGELOG.md` in ai-pipeline-starter first. Then help me with: *(one task)*. Follow the working agreements in the handoff file. Run the test suite before saying anything works.

Use one new chat per task or release. Update this file at the end of each.

## What the kit is

A GitHub-issue-driven software pipeline you operate from a phone: issue (`[idea]`, `[bug]`, `[project]`) -> interview -> triage -> research -> plan -> optional design -> Devin builds -> tester -> reviewer -> **draft** pull request that the owner merges. The orchestrator is `template/pipeline/run.py`, run inside one GitHub Actions job (`pipeline.yml`). Claude stages run through the Claude Code CLI (`claude -p`); the developer stage is Devin through its v3 API. `install/install.sh` copies `template/` into any project; `pipeline/update.sh` (installed in every project) later pulls tagged releases from this repository as a pull request.

## Map of the repository

| Path | What lives there |
|---|---|
| `template/pipeline/` | `run.py` (orchestrator), `run_metrics.py`, `triage_lib.py`, `prompt_engineer.py`, `demo.py`, `project_plan.py`, `update.sh` |
| `template/.claude/agents/` | One file per agent: interviewer, triage, researcher, planner, designer, prompt-engineer, tester, reviewer, project-planner |
| `template/.github/workflows/` | `pipeline`, `intake`, `commands`, `ci`, `queue`, `project-plan`, `failure-watch`, `update-check`, `health-check` |
| `template/metrics/` | `schema.json`, `summarize.py`, README; per-run records land in `metrics/runs/` of the project |
| `install/` | `install.sh` (also `--upgrade`), PowerShell twin (first installs only), `set-secrets`, `harden-repo` |
| `tests/` | Tests for the kit itself; `helpers.py` has the sandbox with fake `claude`, `gh` and Devin |
| `docs/` | Numbered guides; `docs/15-updating.md` and `docs/16-...` describe the newest features |

Design rules that hold everywhere: handoff files in `.pipeline/` on a `pipeline/<UTC timestamp>` branch; machine-readable first lines (`STATUS`, `RESULT`, `VERDICT`, `KIND`...); draft PRs only; the owner is the only one who can trigger runs and merge; secrets live in a GitHub environment restricted to the default branch; workflows triggered by `pull_request` must not use `environment:`.

## State (update at each release)

- Version: see `VERSION` and `CHANGELOG.md`. Releases are git tags `vX.Y.Z`; projects see only tagged versions.
- Verified live in a real project: first install and upgrade, the download from a tag, `update.sh --check`, a full run to a merged PR, two runs that wrote metrics records.
- Written and tested locally only (see the README verification table for the exact list): the PR mode of `update.sh`, Failure watch, Update check, `/fix`, hardening scripts, Playwright and Ollama on a runner, `max_acu_limit` against the real Devin API, how embedded screenshots look in the GitHub mobile app, the PowerShell scripts.

## Open items (pick from here)

1. Run a real issue end to end on v1.3 and check: triage labels and route, the ACU line, the demo section in the PR, the metrics record, the Actions artifacts. Then change the README rows from "tested locally" to "verified live", only for what actually ran.
2. First real pull request from `bash pipeline/update.sh` on a project; record the result.
3. Measure: triage cost (`ai_usage` per stage), ACUs with and without the prompt engineer, demo time.
4. Backlog from `docs/12-gap-analysis.md` (ranked): the largest remaining gaps are preview deployments, security review depth, and observability after release.
5. PowerShell `--upgrade` and `update.sh` equivalent for Windows without WSL.

## Working agreements (how the owner likes to work)

- The owner works from a Mac terminal and a phone. Give **exact commands to paste**, one block per step, with the expected output named so a mismatch is obvious. Pasted `#` comments in zsh print harmless errors: avoid trailing comments on command lines.
- Deliver changes as a full zip **and** as a paste-in Python patch that is idempotent (matches lines by prefix, asserts before writing) and stops before any commit if it fails. Downloads sometimes arrive under a different file name: always include a check (`cat VERSION`, a `grep -c`) that proves the right files are in place.
- Never say something works that was not run. Run `python3 -m unittest discover -s tests` before every hand-off, and for each new check prove it can fail (re-introduce the bug, see the test fail, restore).
- The README verification table must stay honest: "Verified live" only after a real GitHub Actions run. Unknown values stay unknown (null), never zero or an estimate.
- Preserve the human gates (draft PRs, owner-only commands, nothing merges itself). Keep the package free of personal data, keys and local paths; the repository is public and every file is authored "Gil Lotzky".
- Prefer small, reversible changes and say plainly what was not tested. Version rule: patch = fixes or docs, minor = new workflow, command or stage.

## Lessons that cost time (do not repeat)

- A workflow YAML with text at column 0 inside a `run: |` block is invalid and GitHub just shows the file name as the run name. `tests/test_yaml.py` guards this.
- `environment:` on a `pull_request` job is refused when the environment is limited to the default branch.
- A first install over an older install has no `.pipeline-version`; any lookup of it must tolerate its absence.
- Installers must ignore `__pycache__`, `.pyc` and `.DS_Store`; Dependabot bumps of `actions/...@vN` must survive an upgrade.
- PRs opened with the Actions token do not trigger `pull_request` workflows; `run.py` dispatches `ci.yml` itself.
- Test fakes must copy what they record (a dict later mutated by the code under test hides the first request).
- A repository variable that is not set reaches a job as an empty string, not as a missing variable.
- Branch protection, secret scanning and code scanning need a paid plan on private repositories.
