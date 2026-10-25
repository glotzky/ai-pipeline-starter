# Tools used

| Tool | Role | Where | Required? |
|---|---|---|---|
| **GitHub** (repo, Issues, Actions, Environments, PRs) | Hosts the code, your inbox (issues), the runners, the approval gate (PRs) | github.com | Yes |
| **GitHub Actions** | Runs the interviewer and orchestrator on `ubuntu-latest` | Built into GitHub | Yes |
| **GitHub mobile app** | Phone interface: issues, comments, PR review and merge | iOS / Android | Recommended |
| **GitHub CLI (`gh`)** | PR creation inside Actions; optional local convenience (`set-secrets` scripts) | cli.github.com | Local: optional |
| **git** | Version control; installing the template | git-scm.com | Yes (local) |
| **Anthropic API** | Claude models for six of the seven stages | console.anthropic.com | Yes |
| **Claude Code CLI** (`@anthropic-ai/claude-code`) | Runs each agent non-interactively (`claude -p`) in Actions | npm | Installed by the workflow |
| **Claude Code in VS Code** | Local assistant for editing the kit and project rules | VS Code extension | Optional |
| **Devin** (API v3, service users) | The Developer stage in its own cloud VM | devin.ai | Yes (or replace with a Claude coder, see [customizing](05-customizing.md)) |
| **Node.js 22** | Runtime for the Claude CLI in Actions | Installed by the workflow | Local: optional |
| **Python 3.12** with `requests` | Runs `pipeline/run.py` | Installed by the workflow | Local: optional |
| **Homebrew / winget / apt / dnf / pacman** | Installing local tools | Per OS | Optional |
| **Self-hosted runner** | Alternative to GitHub's runners | Your machine or VM | Optional |
| **Lovable** | UI generator, evaluated, **not integrated** | lovable.dev | No |

## Claude models used (October 2026 IDs; verify current)

| Stage | Model ID |
|---|---|
| Planner, Reviewer | `claude-opus-5-5` |
| Interviewer, Researcher, Designer, Tester | `claude-sonnet-5-5` |
| Health-check ping | `claude-haiku-5-5` |

## Files in the template

| Path | Purpose |
|---|---|
| `.github/workflows/pipeline.yml` | The run: installs tools, runs `run.py`, reports back to the issue |
| `.github/workflows/intake.yml` | Issue interviewer and `/go` dispatch |
| `.github/workflows/health-check.yml` | Verifies files, secrets, Devin key, Anthropic key |
| `.github/ISSUE_TEMPLATE/idea.yml` | The "Idea" issue form |
| `.claude/agents/*.md` | The six agent prompts |
| `pipeline/run.py` | The orchestrator: stage order, retries, Devin API, PR creation |
| `CLAUDE.md` | Project rules every agent reads |
| `PIPELINE.md` | Short in-repo usage note |
| `.gitattributes`, `.gitignore` additions | LF line endings; ignore build and secret files |
