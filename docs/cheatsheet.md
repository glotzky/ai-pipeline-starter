# Cheat sheet

## Talking to the pipeline (on the issue)

| You write | Result |
|---|---|
| New issue from the **Idea** form, title starts `[idea]` | Interviewer asks questions or posts a brief |
| `defaults` | Accept the interviewer's recommended answers |
| Any other comment | Interviewer revises the brief |
| `/go` | Full run, ends in a draft PR |
| `/go plan` | Research and plan only |
| `/fix <text>` (on a pipeline PR) | Devin applies your feedback on the same branch; re-test and re-review |
| `/status` / `/stop` / `/queue start` | Latest runs / cancel the job / start the next queued idea |
| New **Bug** issue (`[bug]`) | Reproduction questions, failing test first |
| New **Project plan** issue (`[project]`) | Ordered, queued `[idea]` issues; nothing built until `/queue start` |
| `/go research` / `/go design` / `/go dev` / `/go test` | Stop after that stage |

## Where things are

| Need | Go to |
|---|---|
| Run history and logs | Repo -> Actions |
| A run's handoff files | Branch `pipeline/<timestamp>` -> `.pipeline/` |
| Failure logs | Same branch -> `.pipeline/logs/` |
| Devin's work | The session link in the Actions log or PR description |
| Secrets and environment | Settings -> Environments |
| Cancel a run | Actions -> run -> Cancel workflow (and stop the Devin session) |

## Git

```bash
git fetch origin && git checkout pipeline/<timestamp>      # inspect or fix a run's branch
git push origin --delete pipeline/<timestamp>               # delete a stale pipeline branch
git status                                                  # check before git add -A
```

## Test Devin from your terminal

**macOS / Linux / WSL**
```bash
export DEVIN_ORG_ID="org-xxxxxxxx"
read -s DEVIN_API_KEY && export DEVIN_API_KEY        # paste key; nothing shows; press Enter
curl https://api.devin.ai/v3/self -H "Authorization: Bearer $DEVIN_API_KEY"
curl -X POST "https://api.devin.ai/v3/organizations/$DEVIN_ORG_ID/sessions" \
  -H "Authorization: Bearer $DEVIN_API_KEY" -H "Content-Type: application/json" \
  -d '{"prompt":"Say hello and stop."}'
```

**Windows PowerShell**
```powershell
$env:DEVIN_ORG_ID = "org-xxxxxxxx"
$s = Read-Host "Devin key" -AsSecureString
$env:DEVIN_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($s))
$h = @{ Authorization = "Bearer $env:DEVIN_API_KEY"; "Content-Type" = "application/json" }
Invoke-RestMethod https://api.devin.ai/v3/self -Headers $h
Invoke-RestMethod -Method Post -Uri "https://api.devin.ai/v3/organizations/$env:DEVIN_ORG_ID/sessions" -Headers $h -Body '{"prompt":"Say hello and stop."}'
```

Check a session: `GET https://api.devin.ai/v3/organizations/$DEVIN_ORG_ID/sessions/<session_id>` and read `status`, `status_detail`, `acus_consumed`.

## Install quick reference

| | macOS / Linux / WSL | Windows PowerShell |
|---|---|---|
| Install template | `./install/install.sh /path/to/repo` | `.\install\install.ps1 -Target C:\path\to\repo` |
| Set up environment and secrets | `./install/set-secrets.sh OWNER/REPO` | `.\install\set-secrets.ps1 -Repo OWNER/REPO` |
| Local tools | `brew install git gh node python@3.12` | `winget install Git.Git GitHub.cli OpenJS.NodeJS.LTS Python.Python.3.12` |

## Defaults worth remembering

Retries 2 · Devin wait 180 min · job limit 330 min · environment name `pipeline` · branch names `pipeline/<UTC timestamp>` · nothing merges automatically.

## Metrics

```bash
python3 metrics/summarize.py          # success rate, median time, retries, test pass rate, average cost
```
Records: `metrics/runs/` on merged runs, and the `pipeline-metrics-*` artifact of every run. Details: `metrics/README.md`.

## Terminal shortcuts (GitHub CLI)

```bash
gh run list --workflow=pipeline.yml --limit 3        # recent runs
gh run watch                                         # follow the latest
gh run view --log-failed | tail -40                  # why it failed
gh issue view <n> --comments | tail -30              # the bot's report on an issue
gh pr list --draft                                   # draft PRs waiting for you
gh pr ready <n> && gh pr merge <n> --merge --delete-branch
```

## Update the pipeline in a project

`bash pipeline/update.sh` opens a pull request with the newest tagged version (never merges). `--check` shows whether the project matches the starter. Details: [docs/15-updating.md](15-updating.md).
