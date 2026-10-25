# 7. Troubleshooting

## Where to look first

1. **The issue thread.** The pipeline comments there when it starts and finishes.
2. **Actions tab -> the run -> the failed step.** The last 30 lines usually name the problem. Scan for secrets before pasting logs anywhere (GitHub masks them, but check).
3. **The run's branch `pipeline/<timestamp>` -> `.pipeline/logs/`.** Failed runs push their logs here. `install.txt` is the dependency install output.
4. **The Devin session link** (printed in the log and the PR description) for anything about the build.

## Symptom -> cause -> fix

### Setup and files

| Symptom | Cause | Fix |
|---|---|---|
| `.github/workflows/pipeline.yml` or `.claude/` missing on GitHub | GitHub's drag-and-drop web uploader skips dot-folders, and macOS/Windows hide them | Install with git from the command line, or use the installer scripts. Turn on "show hidden files" in your file explorer |
| Workflow does not appear in the Actions tab | The workflow files are not on the default branch | Merge the setup PR into the default branch, refresh |
| Run sits "Waiting", or secrets are empty | The workflow's `environment:` name does not match the environment you created, or the run was started from a non-default branch | Make the names identical (case and underscores included); leave "Use workflow from" on the default branch; confirm the environment's branch rule includes it |
| Health check: "Secrets are set" fails | Secrets were added at repository level in a different spot, or to a differently named environment | Add the three secrets under Settings -> Environments -> *your environment* -> Environment secrets |
| `.gitignore` problems: files missing from commits, or `node_modules` committed | The default GitHub Python `.gitignore` ignores `lib/` and `ENV/` anywhere (hiding `src/lib/`), and does not ignore `node_modules` | Scope those rules to the repo root and add `node_modules/`. The installer appends missing lines. Check with `git status` before `git add -A` |
| Shell scripts fail on Windows with odd `^M` errors | CRLF line endings | The template ships `.gitattributes` forcing LF; re-clone or `git add --renormalize .` |

### Devin

| Symptom | Cause | Fix |
|---|---|---|
| `404 ... /v3/organizations//sessions` | `DEVIN_ORG_ID` is empty in your terminal (the path has `//`) | `export DEVIN_ORG_ID=...` in the same terminal window (PowerShell: `$env:DEVIN_ORG_ID=...`) |
| `403 Forbidden "Unauthorized"` on `/v3/self` | Key mistyped, truncated while pasting, or revoked | Re-provision a service user, copy the full `cog_...` key, update the secret. Check `echo ${#DEVIN_API_KEY}` and that it starts with `cog_` |
| `403 ... billing error ... out_of_quota` on session creation | Plan quota or extra usage is not enabled for API sessions | Devin billing settings: enable extra usage / add credit; retry. `/v3/self` works even when this is broken |
| Key lost | GitHub secrets cannot be read back | Provision a new service user, update the secret, revoke the old one |
| Session shows `running` / `waiting_for_user` and never ends | That is how an idle Devin session (finished or asking a question) looks; it does not report `exit` | The orchestrator treats two consecutive such polls as "done". If the Devin stage then says "pushed no commits", read the session: Devin probably asked a question |
| "Devin finished but pushed no commits" | Devin could not push to the branch, opened its own PR, worked elsewhere, or got blocked | Confirm the repo is connected in Devin with write access. Read the session. Make the spec clearer |
| Devin opened its own PR or touched the default branch | It ignored the prompt | Close that PR. Tighten the Developer prompt in `run.py`; enable branch protection on the default branch |

### Intake (issues)

| Symptom | Cause | Fix |
|---|---|---|
| Interviewer never comments | Title lost the `[idea]` prefix; you are not the repo owner account; the run failed | Check the title; check the **Idea intake** run log (Actions) |
| `/go` replies "no brief yet" | No bot comment containing a brief exists | Answer the interviewer, wait for the brief, then `/go` |
| `/go` does nothing | Dispatch failed (permissions) or `/go` is not the first characters of the comment | Check the Idea intake run log; ensure workflow permissions allow `actions: write` (the workflow requests it) |
| New issue template not shown | Template is not on the default branch yet | Merge the setup PR |

### Pipeline run

| Symptom | Cause | Fix |
|---|---|---|
| Failed before any branch appeared | Older versions did not push on failure | The shipped `run.py` pushes logs on failure. If you still see none, the failure was before `git checkout`: check the Actions log |
| Claude stage error about flags or authentication | CLI version difference or bad `ANTHROPIC_API_KEY` | Run the Health check; read `.pipeline/logs/<stage>.txt` |
| Planner says `STATUS: BLOCKED` | Contradiction or something only a human can provide | Read the top of `.pipeline/spec.md`; fix the idea; `/go` again |
| Tester `RESULT: FAIL` because tests cannot run | No test framework yet, dependencies not installed, wrong test command | Put commands in `CLAUDE.md`; set `PIPELINE_INSTALL_CMD` for unusual stacks; make the first slice add a test framework and a smoke test |
| Install failed (see `install.txt`) | Lockfile mismatch or private packages | Fix the lockfile; override with `PIPELINE_INSTALL_CMD` |
| PR creation fails: "GitHub Actions is not permitted to create pull requests" | Actions permission is off | Settings -> Actions -> General -> allow read/write and "Allow GitHub Actions to create and approve pull requests" |
| Run says success but there is no PR; the branch has only `research.md`/`spec.md` | Either you ran `/go plan`, the planner returned `BLOCKED`, or (older versions) Devin pushed nothing and the run still reported success | Read the stop reason in the issue comment. Current versions fail loudly when Devin pushes no commits |
| Devin session ends in minutes, no commits | Devin cannot see the repo (private repo not added to the Devin GitHub App) or hit a blocker | Open the session link. Fix access: [setup guide, Step 1](03-setup-guide.md). Re-run |
| PR step: "GitHub Actions is not permitted to create or approve pull requests" | Repo Actions setting is off. The orchestrator, not Devin or Claude, opens the PR | Settings -> Actions -> General -> Read and write + tick Allow GitHub Actions to create and approve pull requests. If greyed out, an organization policy blocks it. The branch holds all the work: open the PR by hand from `.../pull/new/pipeline/<timestamp>` |
| A pipeline PR's CI check never starts (shows "Expected") | PRs opened with the Actions token do not trigger `pull_request` workflows | The pipeline dispatches CI for its branch. If it did not, Actions -> CI -> Run workflow on that branch. `ci.yml` must exist on the default branch |
| `/fix`, `/status`, `/stop` or `/queue` does nothing | Commands workflow not on the default branch yet, or comment not from the owner, or the command is not at the start of the comment | Merge the workflows; use the exact command first; check Actions -> Commands |
| `[project]` issue made no slices | The planner returned something that was not a JSON list | Read the comment on the issue and the "Project plan" run log; add detail to the plan and file a new `[project]` issue |
| Queue did not start the next idea after a merge | Auto-start is off by default | Reply `/queue start`, or set the repository variable `PIPELINE_AUTO_QUEUE` to `true` |
| Second run stays "Queued" | One run at a time per repository (concurrency group) | Wait, or cancel the first with `/stop` |
| Run failed on tests with "No unit tests were added" | The test gate | Intended. Devin is sent back automatically; `PIPELINE_REQUIRE_TESTS=0` disables only this gate |
| Reviewer verdict `UNKNOWN` | The first line was not an exact `VERDICT:` line | Read `.pipeline/review.md`; check the reviewer prompt still demands that format |
| Review diff empty or wrong | Default branch is not `main` | `BASE_BRANCH` is set from the repo's default branch; confirm it in the workflow env |
| Run is slow or uses many Actions minutes | Long Devin session while the job polls | Smaller ideas; lower `--devin-timeout`; consider a self-hosted runner |

### Local environment

| Symptom | Cause | Fix |
|---|---|---|
| `gh: command not found` | GitHub CLI not installed | Not required. Use the web UI, or install `gh` ([setup guide](03-setup-guide.md)) |
| PowerShell blocks `install.ps1` | Execution policy | `powershell -ExecutionPolicy Bypass -File .\install\install.ps1 -Target ...` |
| `install.sh`: "not the root of a git repository" | Pointed at a subfolder or a non-repo | Pass the folder that contains `.git` |
| Node 20 deprecation / `ubuntu-latest` migration annotations | Runner announcements | Harmless; update action versions when convenient |

## Recovering a messy main

If you merged several `pipeline/*` branches (for example plan-only and dev-only branches) and `main` now has stale `.pipeline/` files or unreviewed code:

```bash
git checkout main && git pull
git log --oneline --first-parent -10              # find the merge commits to undo (newest first)
git checkout -b revert-pipeline-merges
git revert -m 1 <newest-merge-hash>
git revert -m 1 <older-merge-hash>                 # squash-merged? drop "-m 1"
git push -u origin revert-pipeline-merges
```
Open the PR from the printed link (or `gh pr create --fill --base main`) and merge it. Then delete stale branches (`git push origin --delete pipeline/<timestamp>`) and re-run the idea. Runs now clear `.pipeline/` at the start, so leftover handoff files no longer leak into new runs.
