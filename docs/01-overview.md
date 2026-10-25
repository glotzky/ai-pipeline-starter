# 1. Overview and architecture

## The idea

Using one AI agent for everything means one context window holds planning notes, code, test output and review comments at once, and quality drops. This pipeline splits the work across **specialist agents with narrow jobs** that hand off through **files committed to a branch**. A human stays in the loop at two points that matter: approving what to build, and merging what was built.

## The stages

| # | Stage | Runs on | Job | Output file (`.pipeline/`) |
|---|---|---|---|---|
| 0 | Interviewer | Claude Sonnet (GitHub Action) | Turns a rough idea into a buildable brief by asking up to 4 questions with defaults | brief, posted as an issue comment |
| 1 | Researcher | Claude Sonnet | Reads the repo and the web; reports facts, risks, a recommended approach | `research.md` |
| 2 | Planner | Claude Opus | Writes the spec: files, signatures, edge cases, acceptance criteria. Decides if design is needed | `spec.md` |
| 3 | Designer (conditional) | Claude Sonnet | UI flow, states, data model or API contract. Runs only when the spec says `NEEDS_DESIGN: yes` | `design.md` |
| 4 | Developer | **Devin** (its own cloud VM, via API) | Implements exactly the spec on the run's branch | commits + `changes.md` |
| 5 | Tester | Claude Sonnet | Writes and runs tests. Never fixes code | `test-results.md` |
| 6 | Reviewer | Claude Opus, read-only | Compares diff to spec; gives a verdict | `review.md` |
| 7 | Orchestrator | `pipeline/run.py` in GitHub Actions | Runs the stages, retries, opens a draft PR, reports back to the issue | draft PR |

Failed tests or a `NEEDS WORK` verdict send the feedback back to the Developer, up to 2 retries.

## Key design rules (and why)

- **Handoff by files in git.** Each agent reads what the previous one wrote. Devin runs in its own VM, so git is the only thing both sides can share.
- **Machine-readable first lines.** `STATUS:`, `NEEDS_DESIGN:`, `RESULT:` and `VERDICT:` let the orchestrator branch without parsing prose.
- **The Reviewer is read-only.** It prints its verdict; the orchestrator saves it. A reviewer that can edit will paper over problems instead of reporting them.
- **The Tester never fixes code.** Separation of builder and checker is the point.
- **The Planner assumes instead of stalling.** Unattended runs cannot wait for answers. It records assumptions, and blocks only on real contradictions or things only a human can supply.
- **Nothing merges automatically.** The pipeline stops at a *draft* PR. You are the final gate.
- **One branch per run** (`pipeline/<timestamp>`). Runs never collide, and a failed run still pushes its logs to its branch.

## Where each thing runs

```
Your phone/browser --(issue, comments)--> GitHub
GitHub Actions (ubuntu runner): intake.yml (interviewer), pipeline.yml (run.py orchestrator)
        |-- Claude Code CLI --> Anthropic API (research, plan, design, test, review)
        |-- Devin REST API  --> Devin cloud VM (implements, pushes to the run's branch)
        `-- git push / gh pr create --> your repo
```

No server of yours is involved. See [hosting](06-multiple-projects-and-hosting.md).

## What it does not do (yet)

- It breaks a whole plan into a queue only when you ask (a `[project]` issue), and it starts the next slice only when you say so (`/queue start`) or you turn on `PIPELINE_AUTO_QUEUE`. Both are built but not yet verified live.
- It does not provision accounts, databases, hosting or secrets for the app you are building.
- It does not apply database migrations. Agents write migration files only.
- It does not drive a UI-generation tool. (Lovable was evaluated and rejected; see [lessons learned](08-lessons-learned.md).)

For a ranked list of what a strong engineering team does that this pipeline does not yet (CI on every PR, branch protection, security scanning, a fix loop, a backlog queue, and more), see the [gap analysis](12-gap-analysis.md).
