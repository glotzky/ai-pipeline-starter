# 8. Lessons learned

What building this taught us, so you do not repeat it. Vendor facts are dated (October 2026) and may change.

## Design lessons

1. **Narrow agents beat one big agent.** Each agent keeps a clean context and does one job. Hand off through files, not conversation.
2. **Separate the builder from the checker.** The Tester never fixes code; the Reviewer cannot edit. If the checker can patch, it will hide problems.
3. **Make handoffs machine-readable.** First-line markers (`STATUS`, `NEEDS_DESIGN`, `RESULT`, `VERDICT`) let a script branch without guessing.
4. **Unattended means assume, do not ask.** Waiting for answers stalls an overnight run. Record assumptions; block only when truly stuck.
5. **The human gate belongs at "what to build" and "what to merge".** Everything between can be automatic. Do not auto-merge.
6. **Git is the shared medium** when one participant (Devin) lives in its own VM.
7. **Make failures leave evidence.** A failed run that leaves nothing behind cannot be debugged. Push logs to the run's branch on failure.
8. **Stage your first runs** (`plan` -> `dev` -> full). Cheap stages reveal bad prompts before expensive ones burn money.
9. **Project rules are a product.** `CLAUDE.md` quality largely determines spec and code quality.
10. **Small slices.** Large, vague ideas produce vague specs and expensive Devin sessions.

## Vendor facts we had to discover

**Devin**
- The cheap entry plan changed during 2026 (Core and Team retired; Pro at $20/month). Older articles still describe the old plans.
- API access uses **service users**; keys start `cog_`, show once, and are scoped to an organization. API v3 base: `https://api.devin.ai/v3`.
- `/v3/self` can succeed while session creation fails with `out_of_quota`; that is a billing state, not a key problem.
- A finished or idle session reports `status: running` with `status_detail: waiting_for_user`, not `exit`. Poll for that.
- Sessions expose `acus_consumed`; log it for cost visibility. Quotas are opaque; measure real runs.

**Lovable (UI generator)**
- No classic REST API with developer keys. It offers "Build with URL" (a prompt link) and an MCP server (research preview, OAuth). It syncs with GitHub two-way on the default branch only. Sources disagreed on importing an existing repo. We decided not to integrate it. If you want it, use it manually for UI slices.

**GitHub**
- The web uploader skips dot-folders. Use git or the installer.
- Environment names must match exactly; environment branch restrictions mean workflows must run from the default branch.
- Events created with the built-in `GITHUB_TOKEN` do not trigger other workflows, **except** `workflow_dispatch`; that exception is what lets `/go` start the pipeline.
- `issue_comment` and `issues` events run the workflow from the default branch.
- "Allow GitHub Actions to create and approve pull requests" is off by default and blocks the final PR step.

**Claude Code CLI**
- `--allowedTools` takes a comma- or space-separated list; strings with parentheses such as `Bash(git diff:*)` are valid. It is variadic, so keep it the last flag or follow it with another `--flag`.
- It reads `CLAUDE.md` from the working directory automatically.

**Costs**
- Opus 5.5 $4/$20 and Sonnet 5.5 $2/$10 per million input/output tokens (Oct 2026). Opus is for the two quality gates only.

## Bugs we hit (and fixed in the template)

| Bug | Why it happened | Fix in template |
|---|---|---|
| Developer stage waited 3 hours after Devin finished | Polling only stopped on `exit`/`error`/`suspended` | Treat two consecutive `waiting_for_user` polls as done |
| Tester ran without dependencies | Install step ran at job start, before the app existed or changed | `install_deps()` runs on the branch after the Developer stage |
| Reviewer could not write its verdict | It had no `Write` tool (correctly) but was told to write a file | It prints the verdict; the orchestrator saves `review.md` |
| Failed runs left no branch | Pushes happened only after stages succeeded | Catch exceptions, push logs, include the error in the summary |
| `.gitignore` hid real source folders | The stock Python template ignores `lib/` and `ENV/` | Template appends needed lines; docs warn to check |
| Script injection risk in the workflow | Idea text interpolated straight into a shell command | Pass user text through environment variables, never inline |
| Wrong environment name caused silent failure | Docs said one name, user created another | One configurable name, set by the installer |
| Tools string with spaces after commas | Unverified CLI parsing | Normalize to commas in `claude_stage` |
| Run reported "success" with no PR and no reason | Devin pushed no commits (could not see the private repo) and the script exited 0 with the reason only in the job summary | That case now exits non-zero; the stop reason is posted in the issue comment |
| Stale `.pipeline/` files from merged runs leaked into new runs | Handoff folder persisted on the default branch | `run.py` clears `.pipeline/` (keeping `.gitkeep`) at the start of each run |
| Shell brace expansion failed in `/bin/sh` | `mkdir -p a/{b,c}` is bash-only | Avoid brace expansion in portable scripts |

## Process lessons

- Verify each hop before adding the next: secrets -> Devin session -> Claude call -> plan-only run -> build -> full run.
- When an AI summary says a vendor feature exists (for example an API on a plan tier), test it with one real call before designing around it.
- Never paste secrets into chats or tickets. Use hidden prompts (`read -s` / `Read-Host -AsSecureString`).
- Write down what is verified versus assumed. This kit's README does.
- Merge only the final draft PR of a full run. Merging partial-run branches by hand creates a mess that takes a revert to undo.
- Connect the builder to your repo and check it before the first run. The most expensive wrong turn was a green run with no code.
