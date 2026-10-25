# 3. Setup guide (macOS, Windows, Linux)

The pipeline itself runs on GitHub's servers, so your operating system only matters for the one-time setup. Pick your column in the tables; everything else is identical.

## Step 0: Decide your repo

- New project: create an empty **private** GitHub repo (add a README so it has a default branch).
- Existing project: use its repo. The template adds files only; it never deletes or overwrites your code. Existing `CLAUDE.md`, `PIPELINE.md` and `.gitattributes` are kept (a `.pipeline-new` copy is written beside them).
- Note your **default branch name** (usually `main`). Everything below says `main`.

## Step 1: Create accounts and keys

1. **GitHub**: account and the repo above.
2. **Anthropic API**: create an account at console.anthropic.com, add billing, create an API key (name it for this pipeline), and set a monthly spend limit.
3. **Devin**: sign up (Pro plan is the cheapest path, see [costs](02-requirements-and-costs.md)). Then:
   1. Connect GitHub in Devin (Settings -> Integrations -> GitHub), install the Devin GitHub App, and **select your repo**. Private repos are invisible to Devin until you do. Verify in GitHub: Settings -> Applications -> Installed GitHub Apps -> Devin -> Configure lists the repo. If not, Devin finishes in minutes with no code and the run ends without a PR.
   2. Settings -> **Devin API** -> **Service users** -> **Provision service user**. Name it (for example `pipeline`) and choose the **Member** role.
   3. Copy the `cog_...` key **immediately** (shown once). Also copy the **organization ID** from the top of the same page (`org-...`).
   4. Store both in a password manager. GitHub secrets cannot be read back later.

## Step 2: Install local tools

You need **git**. Everything else is optional but handy.

### macOS
```bash
# Homebrew (https://brew.sh) if you do not have it, then:
brew install git gh node python@3.12
```

### Windows (PowerShell)
```powershell
winget install --id Git.Git -e
winget install --id GitHub.cli -e
winget install --id OpenJS.NodeJS.LTS -e
winget install --id Python.Python.3.12 -e
```
Close and reopen PowerShell afterwards. Alternative: install **WSL2** (`wsl --install`) and follow the Linux steps inside it; the `.sh` scripts then work unchanged. Git Bash (installed with Git for Windows) can also run the `.sh` scripts.

### Linux
```bash
# Debian / Ubuntu
sudo apt update && sudo apt install -y git nodejs npm python3 python3-pip
# GitHub CLI: follow https://cli.github.com for the current package source

# Fedora
sudo dnf install -y git gh nodejs python3
# Arch
sudo pacman -S git github-cli nodejs npm python
```

Then sign in once (optional, needed only for the `set-secrets` scripts): `gh auth login`.

## Step 3: Get the repo and install the template

Clone your repo and unzip this package somewhere outside it.

```bash
git clone https://github.com/OWNER/REPO.git
```

Run the installer, pointing it at your clone:

| OS | Command |
|---|---|
| macOS / Linux / WSL / Git Bash | `./install/install.sh /path/to/REPO` |
| Windows PowerShell | `.\install\install.ps1 -Target C:\path\to\REPO` |

If PowerShell refuses to run scripts: `powershell -ExecutionPolicy Bypass -File .\install\install.ps1 -Target C:\path\to\REPO`.

Options: `--env NAME` (bash) / `-EnvName NAME` (PowerShell) sets a different GitHub environment name (default `pipeline`).

**Manual alternative** (no scripts): copy everything inside `template/` into your repo root, **including the hidden folders `.github` and `.claude`**. Do not use GitHub's drag-and-drop web uploader; it skips dot-folders (see [troubleshooting](07-troubleshooting.md)).

## Step 4: Fill in the project rules

Open `CLAUDE.md` in the repo and replace every `TODO`. This single file is how agents learn your stack, commands and guardrails. It matters more than any other file. Keep it short and factual. See [customizing](05-customizing.md).

If you already had a `CLAUDE.md`, merge the useful sections of `CLAUDE.md.pipeline-new` into it, then delete the `.pipeline-new` file.

## Step 5: Commit and merge (workflows only run from the default branch)

```bash
cd /path/to/REPO
git checkout -b pipeline-setup
git add -A
git status          # confirm .github/ and .claude/ files are listed; no .env, no node_modules
git commit -m "Add AI build pipeline"
git push -u origin pipeline-setup
```
Open the pull request on GitHub and **merge it into `main`**. (Without the `gh` CLI, use the link git prints after pushing, or `https://github.com/OWNER/REPO/pull/new/pipeline-setup`.)

## Step 6: Environment and secrets

Secrets live in a GitHub **Environment** restricted to your default branch. This prevents a workflow edited on some other branch from reading your keys.

### Option A: script (needs `gh`, logged in)
```bash
./install/set-secrets.sh OWNER/REPO pipeline main            # macOS / Linux / WSL
```
```powershell
.\install\set-secrets.ps1 -Repo OWNER/REPO -EnvName pipeline -Branch main   # Windows
```
It creates the environment, restricts it to the branch, prompts (hidden) for the three secrets, and turns on the Actions permissions below. These scripts are untested; if anything errors, do Option B.

### Option B: by hand
1. Repo **Settings -> Environments -> New environment**. Name it exactly as in the workflows (`pipeline` unless you changed it).
2. **Deployment branches and tags -> Selected branches** -> add `main`.
3. Do **not** add required reviewers (it would stop unattended runs from starting).
4. **Environment secrets -> Add secret**, three times:
   - `ANTHROPIC_API_KEY` = your Anthropic key
   - `DEVIN_API_KEY` = the `cog_...` key
   - `DEVIN_ORG_ID` = the `org-...` id
5. **Settings -> Actions -> General -> Workflow permissions**: choose **Read and write permissions** and tick **Allow GitHub Actions to create and approve pull requests**. Save.
6. Optional: **Settings -> Branches** -> require pull requests before merging into `main`, so nothing can push to it directly.

## Step 7: Health check

**Actions -> Health check -> Run workflow** (branch `main`), and tick **Also start a tiny real Devin session** the first time. All steps should be green:

| Step | Proves |
|---|---|
| Required files exist | The template installed completely (hidden folders included) |
| Secrets are set | The three secrets are in the environment the workflows use |
| orchestrator compiles | `run.py` has no syntax errors |
| Devin credentials | The key is valid and belongs to the org ID you stored |
| Devin can start a session | Billing/quota allow real API sessions |
| Anthropic key and Claude CLI work | The key is valid and the CLI runs in Actions |

Red step? See [troubleshooting](07-troubleshooting.md). Two harmless annotations about Node.js 20 and `ubuntu-latest` migrating can be ignored.

## Step 7b: Harden the repo (recommended before real work)

Turns on the safety net a strong team relies on: pull requests required for the default branch, no force pushes, merged branches auto-deleted, secret scanning with push protection, Dependabot alerts, and CodeQL code scanning.

```bash
./install/harden-repo.sh OWNER/REPO                 # macOS / Linux / WSL
./install/harden-repo.sh OWNER/REPO --require-ci    # also make the "ci" check mandatory
```
```powershell
.\install\harden-repo.ps1 -Repo OWNER/REPO [-RequireCi]
```
Each step prints `ok` or `FAILED`. On a **private repo, some features need a paid GitHub plan** (branch protection, secret scanning, CodeQL), so a 403 or 404 is normal on a free plan; do what the plan allows. These scripts were not run against live GitHub when the kit was written; the manual equivalents are in Settings -> Branches and Settings -> Code security. Also: open `.github/dependabot.yml` and delete ecosystems you do not use, and check `.github/CODEOWNERS` names you.

## Step 8: First runs, in stages

Do these in order. Stop at the first surprise.

1. **File an idea.** Repo -> **Issues -> New issue -> Idea**. Keep the `[idea]` title prefix. Pick something small and concrete. If the repo has no app yet, make the first idea "scaffold the app" and include a test framework and a smoke test in it (otherwise the Tester has nothing to run).
2. **Interview.** Within a minute or two the interviewer comments with up to 4 questions (each with a default) or a finished brief. Answer, or reply `defaults`.
3. **Plan only.** When a brief appears, reply `/go plan`. In 5-10 minutes the issue gets a comment naming the branch `pipeline/<timestamp>`. Open it and read `.pipeline/research.md` and `.pipeline/spec.md`. They should name real files and have checkable acceptance criteria. If not, tune `CLAUDE.md` or the planner prompt before continuing.
4. **Build.** On a fresh issue, reply `/go dev`. Open the Devin session link in the Actions log. Check the branch for Devin's commits and `.pipeline/changes.md`, and that Devin opened no PR of its own and did not touch `main`.
5. **Full run.** Reply `/go`. You should get a draft PR with the Reviewer's verdict and the Devin session links. Review it yourself; merge if you are happy.
6. Check Devin's and Anthropic's usage pages and write down the cost of one full run.

## Step 9: Phone setup

Install the **GitHub mobile app** and enable notifications for the repo. Everything in [Using the pipeline](04-using-the-pipeline.md) can be done from it.

## Optional: VS Code with Claude Code

Useful for editing agent prompts and `CLAUDE.md`, and for asking Claude to review the setup against your real codebase. Install VS Code, add the Claude Code extension, open the repo folder. Not needed to *run* the pipeline.
