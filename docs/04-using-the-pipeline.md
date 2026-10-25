# 4. Using the pipeline: when you interact, when you do not, and how

## At a glance

| Phase | Needs you? | What you do |
|---|---|---|
| One-time setup (accounts, keys, secrets, health check) | **Yes, once** | [Setup guide](03-setup-guide.md) |
| Submit an idea | **Yes** | File an `[idea]` issue (phone or browser) |
| Interview (clarifying questions) | **Yes, briefly** | Answer, or reply `defaults` |
| Approve the brief | **Yes** | Reply `/go` (or `/go plan`, `/go dev`, ...) |
| Research, planning, design | **No** | Wait. Only a `BLOCKED` spec asks for you. |
| Building (Devin), testing, review, retries | **No** | Wait. Optional: watch progress. |
| Draft PR created, issue comment posted | **Yes** | Read the result, then merge or decline |
| Failure or `NEEDS WORK`/`BLOCK` after retries | **Yes** | See [When something goes wrong](#when-something-goes-wrong) |
| Anything outside the repo: accounts, secrets, migrations, deploys, DNS | **Yes, always** | Agents cannot do these |
| Periodic upkeep: cost check, key rotation, `CLAUDE.md` refresh | **Yes, occasionally** | See [Upkeep](#upkeep) |

Between `/go` and the draft PR, you do not need to do anything. You can close the app.

## Rules of the road

- **Only the repository owner** triggers anything. Comments from anyone else are ignored.
- The issue **title must start with `[idea]`** (the form pre-fills it). Remove the prefix and the pipeline ignores the issue.
- **One idea per issue.** Keep the issue open; it becomes the log of that run (questions, brief, branch, PR link, cost).
- **Runs always start from your default branch.** Work that is not merged is invisible to the next run. If slice 2 depends on slice 1, merge slice 1 first.
- The pipeline never merges. Never.
- **Merge only the draft PR from a full `/go` run.** Plan-only, research, design and dev-only runs leave a branch to *inspect*; delete those branches, do not merge them. Merging several branches from one idea duplicates work and puts unreviewed files on the default branch.
- "Pipeline finished: success" means the script ended cleanly, **not** that a PR exists. Read the rest of the issue comment for the stop reason.

## A. Submit an idea

**Phone (GitHub app) or browser:** repo -> **Issues** -> **New issue** (the `+`) -> choose **Idea**.

- **Title:** keep `[idea] ` and add a short name, e.g. `[idea] Add CSV export to reports`.
- **Your idea:** what you want and why, in plain words. Rough is fine.
- **Anything else (optional):** constraints, examples, things to avoid.

Good ideas are **one PR worth of work**, concrete about behavior, and name constraints ("no new dependencies", "reuse the existing table component"). Bad ideas are vague ("improve the app") or huge ("build the whole product"). If your project is big, break it into slices yourself and file them one at a time, merging each result before starting the next.

If the repo has no application yet, your first idea should be "scaffold the app" and must include a test framework plus one smoke test.

## B. Answer the interviewer

Within a minute or two a comment appears with either:

- **Up to 4 numbered questions**, each with a recommended default. Reply with answers, or just `defaults` to accept all of them. You may answer a few and say "defaults for the rest".
- **A finished brief** (title, goal, requirements, acceptance criteria, assumptions, out of scope, follow-ups).

If the brief is not what you meant, **reply with your changes** (any comment that is not a `/go` command). The interviewer revises and posts a new brief. Only the **latest** brief is used.

If nothing appears after about 3 minutes: Actions -> **Idea intake** run -> read the log; see [troubleshooting](07-troubleshooting.md).

## C. Start the run with `/go`

Reply on the issue with one of:

| Comment | Runs | Use it when |
|---|---|---|
| `/go` | Everything: research, plan, design if needed, Devin builds, tests, review, draft PR | You trust the brief |
| `/go plan` | Research and plan only (cheap, about a dollar or two) | First time, risky or unclear ideas |
| `/go research` | Research only | You just want facts about the repo |
| `/go design` | Through the design stage | You want a design brief before building |
| `/go dev` | Through Devin's build, no tests or review | Checking what Devin produces |
| `/go test` | Through the tester | Checking build plus tests, no review |

The pipeline replies "Pipeline started" with a link to the run. Commands are not case-sensitive, and `/go` must be the first thing on the **first line** of your comment.

If you comment `/go` before a brief exists, it replies that it has no brief yet. Answer the interviewer first.

### Other commands (owner only)

*Built but not yet verified in a live run; see the README status table.*

| Where | Comment | Does |
|---|---|---|
| Pipeline pull request | `/fix <what to change>` | Sends your feedback to Devin on the **same branch**, re-tests, re-reviews, comments the new verdict on the PR and updates its title |
| Any issue or PR | `/status` | Lists the latest pipeline runs |
| Any issue or PR | `/stop` | Cancels the running pipeline job. Stop the Devin session in Devin too |
| Any issue or PR | `/queue start` | Starts the next queued idea |
| New issue, **Bug** form | (title starts `[bug]`) | Interviewer asks for reproduction steps; the fix must start with a failing test |
| New issue, **Project plan** form | (title starts `[project]`) | AI splits the plan into ordered `[idea]` issues labeled `queued`. Nothing is built until you `/queue start` |

After you merge a pipeline PR, the next queued idea is **offered** in a comment. Set the repository variable `PIPELINE_AUTO_QUEUE` to `true` to start it automatically (this spends Devin and API usage without asking).

Only one pipeline run goes at a time per repository; a second one waits for the first.

## D. Wait (or watch)

Nothing to do. If you want to watch:

- **Actions tab -> AI pipeline -> latest run:** live log. The Devin stage prints lines like `Devin: running / working | ACUs: 0.4` every 30 seconds, plus a link to the Devin session.
- **Devin session link:** shows exactly what Devin is doing. You may message it there, but the pipeline does not expect you to.
- **Notifications:** enable GitHub notifications for the repo; the issue gets a comment when the run finishes, which pings you.

Typical durations: plan-only 5-10 minutes; full runs 30 minutes to a few hours, mostly Devin.

## E. Review the result

When a run finishes, the issue gets a comment like: "Pipeline finished: success. Branch: `pipeline/20261025-143012`. Draft PR: <link>. Run log: <link>".

Open the **draft PR**. Its description holds the test result, the Reviewer's verdict, and the Devin session links with their cost. Then:

1. Read the **verdict**:

| Verdict | Meaning | Your move |
|---|---|---|
| `SHIP` | Matches the spec, tests meaningful, no serious issues found | Still read the diff yourself, then merge |
| `NEEDS WORK` | Fixable issues (listed with file and line). Already retried up to 2 times | Fix by hand, or merge and file a follow-up idea |
| `BLOCK` | Serious problem: security, data loss, spec not met | Do not merge. Read why. Fix by hand or close the PR |
| `UNKNOWN` | The Reviewer's output was malformed | Read `.pipeline/review.md` on the branch and judge yourself |

2. Read the **Files changed** tab. Confirm nothing unexpected: no edits to `.github/`, `.claude/` or `pipeline/`, no secrets or `.env`, nothing outside the spec's scope.
3. Skim the handoff files on the branch (`.pipeline/spec.md`, `changes.md`, `test-results.md`, `review.md`). On the phone: repo -> **Code** -> branch selector -> `pipeline/<timestamp>` -> `.pipeline/`. They show how each agent understood the task, which teaches you how to write better ideas.
4. Check the PR's **BLOCKERS** note in `changes.md`. Devin lists anything it could not do (missing account, secret, migration).

## F. Merge, or ask for changes

**Ask for changes without a new idea:** comment `/fix <feedback>` on the draft PR (see Other commands above). Merge when the verdict and your own read are good. CI must be green if you enabled branch protection with `--require-ci`.

- **Merge** (squash is fine). The GitHub app can merge from your phone. Delete the `pipeline/*` branch afterwards if you like.
- **Changes needed, small:** check out the branch (`git fetch && git checkout pipeline/<timestamp>`), edit, push, then merge.
- **Changes needed, larger:** merge what is acceptable, then file a **new idea** describing the follow-up ("In the CSV export from #12, also include the date column"). Mention the issue or PR number so the Researcher can find context.
- **Reject:** close the PR. Optionally refine the idea and `/go` again on the same issue; a re-run creates a fresh branch.

## When something goes wrong

Every failed run still pushes its branch with `.pipeline/logs/` and comments on the issue (if it started from one). Start there.

| Symptom | What it means | What to do |
|---|---|---|
| Issue comment says the spec is **BLOCKED** | The Planner found a contradiction or needs something only you can give | Read `.pipeline/spec.md` on the branch (top says why). Answer it by editing the idea or the brief, then `/go` again |
| Run **failed** (red X in Actions) | A stage errored | Open the run -> "Run pipeline" step -> last 30 lines; also the branch's `.pipeline/logs/`. See [troubleshooting](07-troubleshooting.md) |
| "Devin finished but **pushed no commits**" | Devin did nothing on the branch (it asked a question, hit a blocker, or pushed elsewhere) | Open the Devin session link and read why. Fix the cause (access, unclear spec), then `/go` again |
| Tests **FAIL** in the PR after retries | The code does not meet the criteria or tests cannot run | Read `.pipeline/test-results.md`. If the cause is environment (missing deps or test framework), fix that in the repo first |
| Verdict `NEEDS WORK` / `BLOCK` | See the table in section E | |
| Nothing happens after `/go` | The dispatch failed or the run is queued | Actions tab -> look for "AI pipeline"; then the "Idea intake" run's log |
| Costs higher than expected | Large idea, retries, long Devin sessions | Stop runs (below), shrink ideas, check usage pages |

### Cancel a run
Actions -> the running "AI pipeline" -> **Cancel workflow**. Devin's session keeps running on its own: open its session link in the Devin app and stop or archive it, or it keeps consuming quota.

### Re-run
Comment `/go` (or `/go plan` etc.) again on the issue. The pipeline starts a fresh run on a fresh branch from the same latest brief.

## What the pipeline cannot do for you

You must do these yourself, and the agents will tell you in `changes.md` under BLOCKERS when a slice needs them:

- Create accounts or projects at third-party services (databases, auth, payments, hosting).
- Add or rotate secrets and environment variables in those services.
- Apply database migrations (agents write the files; you run them).
- Deploy, publish, or point DNS.
- Decide product questions and priorities.

## Upkeep

| When | Task |
|---|---|
| After your first 3 runs | Record cost per run (Devin usage page plus Anthropic usage page). Adjust ideas' size or limits |
| Weekly while active | Glance at both usage pages and at open `pipeline/*` branches; delete stale ones |
| After the codebase changes shape | Update `CLAUDE.md` (stack, commands, conventions, protected files). Stale rules produce bad specs |
| When models are retired | Update the `model:` line in each `.claude/agents/*.md` (see [customizing](05-customizing.md)) |
| Every few months, or after a leak | Rotate the Anthropic key, Devin service-user key, and update the environment secrets |
| Before big spend | Re-check Devin and Anthropic limits |

## A sample session

```
You (issue):   [idea] Add a /health endpoint returning {"status":"ok"}
Bot:           Questions: 1) Path: /health or /api/health? (default: /health) 2) Include version? (default: no)
You:           defaults
Bot:           <brief: goal, requirements, acceptance criteria, assumptions>  Reply /go to run...
You:           /go
Bot:           Pipeline started (stops after: review). Progress: <link>
   ... you do something else for an hour ...
Bot:           Pipeline finished: success. Branch: pipeline/20261025-143012. Draft PR: <link>
You (phone):   open PR -> verdict SHIP -> skim Files changed -> Merge
```
