# User manual: setup -> new idea -> publish

The short version. Everything else in `docs/` is reference. Time: about 45 minutes once, then a couple of minutes per idea.

## Part 1. One-time setup

Do these in order. Each has a "you are done when" check.

1. **Accounts.** GitHub, Anthropic API (billing + spend limit), Devin (Pro).
   *Done when:* you have an Anthropic key, and a Devin `cog_...` key plus `org-...` ID saved in a password manager.
2. **Connect Devin to GitHub, and to your repo.** In Devin: Settings -> Integrations -> GitHub, install the Devin GitHub App on your account, and select your repo (private repos are not visible until you do). Check in GitHub: Settings -> Applications -> Installed GitHub Apps -> Devin -> Configure -> the repo is listed.
   *Done when:* the repo appears in that list. Skipping this makes Devin finish in minutes with no code.
3. **Install tools.** Git, GitHub CLI (`gh`), then `gh auth login`. Commands per system are in [Setup guide, Step 2](03-setup-guide.md).
   *Done when:* `gh auth status` says you are logged in.
4. **Install the template.** `./install/install.sh /path/to/repo` (macOS/Linux) or `.\install\install.ps1 -Target C:\path\to\repo` (Windows).
   *Done when:* the repo has `.github/workflows/`, `.claude/agents/`, `pipeline/run.py`, `CLAUDE.md`.
5. **Fill in `CLAUDE.md`** (what the project is, stack, test and build commands, rules). Commit on a branch, open a PR, **merge it** (workflows only run from the default branch).
6. **Secrets and permissions.** Run `install/set-secrets.sh` (or `.ps1`), or by hand: environment named as in the workflows, restricted to the default branch, three secrets, and Settings -> Actions -> General -> Workflow permissions = **Read and write** + **Allow GitHub Actions to create and approve pull requests**.
   *Done when:* Settings shows both Actions boxes set.
7. **Health check.** Actions -> Health check -> Run workflow (tick the real Devin session the first time).
   *Done when:* every step is green.
8. **Harden the repo** (recommended): `./install/harden-repo.sh OWNER/REPO` (Windows: `harden-repo.ps1`). Branch protection, secret scanning, Dependabot, CodeQL. Some need a paid plan for private repos.
   *Done when:* the script prints `ok` for what your plan allows.
9. **Phone.** Install the GitHub app. Repo -> Watch -> Custom -> Issues, Pull requests.

## Part 2. Submit a new idea (about 2 minutes of your time)

1. GitHub (phone or web) -> repo -> **Issues -> New issue -> Idea**. Keep `[idea]` at the start of the title.
2. Write what you want and why. One PR worth of work. Name constraints.
3. Wait a minute or two. The bot comments with questions or a brief.
   - Questions: answer them, or reply `defaults`.
   - Brief: if it is right, go on. If not, reply with changes.
4. Start it. Reply on the issue:

| Reply | Does |
|---|---|
| `/go plan` | Plan only (cheap). Use for your first runs and for risky ideas. |
| `/go dev` | Through the Devin build, no review. |
| `/go` | Everything, ending in a draft PR. |

You can now close the app. Nothing needs your computer.

**Other ways in:**
- **Bug:** New issue -> **Bug** form. It asks for steps to reproduce and requires a failing test first.
- **A whole project:** New issue -> **Project plan**, paste the plan. AI creates ordered `[idea]` issues labeled `queued`. Start the first with `/queue start`. After each merge the next is offered (or starts itself if `PIPELINE_AUTO_QUEUE` is `true`).

## Part 3. Publish (review and merge)

1. A comment on the issue says the run finished, with the branch, the draft PR link and, if it stopped early, why.
2. Open the **draft PR**. Read the title verdict:
   - `[pipeline SHIP]`: tests passed and the reviewer approved.
   - `[pipeline NEEDS WORK]`: read the reviewer notes in the PR body, then decide.
   - `[pipeline BLOCK]`: do not merge; read why.
3. Skim **Files changed** and the tester output in `.pipeline/test-results.md`. Nobody but you has read this as a human.
4. **Want changes?** Comment `/fix <what to change>` on the PR. Devin updates the same branch and the verdict is re-posted.
   **Happy?** Check CI is green, then **Ready for review -> Merge.** Merge only this PR. Branches from `/go plan` or `/go dev` runs are for inspection; delete them, never merge them.
5. Next idea: start again at Part 2. Each run builds on what is merged.

## If something looks wrong

| You see | Do |
|---|---|
| "Pipeline finished: success" but no PR | Read the rest of that comment. It names the stop reason. Usual causes: planner `BLOCKED` (answer it), Devin pushed nothing (Devin cannot see the repo, step 2), or you used `/go plan`/`/go dev`. |
| "Pipeline finished: failure" | Actions -> that run -> the "Run pipeline" step. See [troubleshooting](07-troubleshooting.md). |
| PR step fails: "not permitted to create or approve pull requests" | Setup step 6, the Actions permission. The branch still has the work; open the PR by hand from `https://github.com/OWNER/REPO/pull/new/pipeline/<timestamp>`. |
| Unsure what is on `main` after a messy run | [Recovery](07-troubleshooting.md#recovering-a-messy-main) |

How the whole system flows and where you are in the loop: [map](10-phone-and-decision-map.md). When you must act and when you must not: [Using the pipeline](04-using-the-pipeline.md).
