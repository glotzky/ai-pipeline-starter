# AI build pipeline (in this repo)

Idea -> interview -> research -> plan -> [design] -> Devin builds -> tests -> review -> draft PR.

## Use it
1. Issues -> New issue -> **Idea**. Describe a rough idea (keep the `[idea]` title prefix).
2. Answer the interviewer's questions, or reply `defaults`.
3. When it posts a brief, reply `/go` (everything), or `/go plan`, `/go design`, `/go dev`, `/go test` to stop early.
4. The pipeline comments on the issue with the branch and a draft PR. Review and merge it yourself.

Other owner-only commands: `/fix <feedback>` on a pipeline PR, `/status`, `/stop`, `/queue start`.
Other forms: **Bug** (`[bug]`, starts with a failing test) and **Project plan** (`[project]`, splits a plan into queued ideas).

Every run records metrics in `metrics/runs/`; summarize them with `python3 metrics/summarize.py` (see `metrics/README.md`).

Only the repository owner's activity on issues titled `[idea] ...` is acted on.
Run Actions -> **Health check** after any setup change.

Agents live in `.claude/agents/*.md`, the orchestrator is `pipeline/run.py`, and every agent reads `CLAUDE.md`.
Full guide: see the documentation package this was installed from.
