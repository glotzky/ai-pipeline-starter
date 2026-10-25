# 13. Engineering practices built into (or around) the pipeline

How the pipeline covers what a strong software team does, practice by practice, and what stays your job. Each item says **where it lives** and its **verification status**:
**Verified** (ran live), **Tested locally** (ran in a scratch repo, not in Actions), **Written** (not run), **Your job** (cannot be automated here).

## 1. Requirements and planning
| Practice | Where | Status |
|---|---|---|
| Clarify before building | Interviewer asks up to 4 questions, writes a brief | Verified |
| Break a big plan into slices | `[project]` issue -> `project-planner` agent -> ordered `[idea]` issues labeled `queued` (`pipeline/project_plan.py`) | Parsing tested locally; workflow written |
| Backlog and sequencing | Queue: after you merge a PR, the next queued idea is offered (or auto-started with `PIPELINE_AUTO_QUEUE=true`) | Written |
| Bug intake | `[bug]` form; the interviewer requires reproduction steps and a failing test first | Written |

## 2. Design and specification
Researcher, planner (files, signatures, edge cases, acceptance criteria, tests to add, docs to update, migration and privacy notes) and a conditional designer. Verified for research and plan; the extra spec sections are written.

## 3. Implementation
Devin builds on the run branch from the spec. Unit tests are written with the change (told in the prompt, checked by the tester and a hard gate in `run.py`). Tested locally.

## 4. Testing
| Level | Coverage |
|---|---|
| Unit | Required; gate fails a run that changes source with no test file |
| Integration | Planner adds them to "Tests to add" when parts are wired together; tester confirms they run |
| End-to-end / browser | Not automated by default. For a web app, add Playwright and one smoke test of the key flow as an early idea, then CI runs it |
| Accessibility and performance | Reviewer checks UI basics; add Lighthouse or axe to CI when you have pages worth measuring |
| Manual / exploratory | **Your job**: open the preview, click through it |

## 5. Review and quality gates
- **AI reviewer** (read-only): spec match, test quality, security and privacy, migrations, docs, UI basics. Written prompts; verdict flow verified in a live run.
- **CI on every PR** (`ci.yml`): installs, then runs `lint`, `typecheck`, `test`, `build` scripts if your `package.json` defines them (or `pytest` and `ruff` for Python). The pipeline starts it for its own PRs. Written.
- **Definition of done**: `.github/PULL_REQUEST_TEMPLATE.md` checklist plus the "Definition of done" section in `CLAUDE.md`. Written.
- **Human review**: you read the diff and the test files. Always.

## 6. Security
| Practice | Where | Status |
|---|---|---|
| Branch protection | `install/harden-repo.sh` (`--require-ci` to make CI mandatory) | Written; may need a paid plan for private repos |
| Secret scanning and push protection | `harden-repo.sh` | Written; may need a paid plan for private repos |
| Dependency updates and alerts | `.github/dependabot.yml`, Dependabot alerts | Written |
| Code scanning | CodeQL default setup via `harden-repo.sh` | Written; may need a paid plan for private repos |
| Pipeline self-protection | `.github/CODEOWNERS` (installer fills your username). It only *forces* review if you also tick "Require review from Code Owners" on the protected branch | Written |
| Keys and data | Dedicated low-cap API key, Member-role Devin service user, no real customer data in the repo | Your job |

## 7. Data and migrations
Rule in `CLAUDE.md`: every schema change is a migration file with a rollback note; agents never apply migrations or touch production data. Review a migration PR with extra care, apply it yourself, and take a backup first. **Your job.**

## 8. Release, deployment and operations
Deliberately **not automated**: the pipeline never deploys. Recommended setup, outside the pipeline:
- **Preview per PR** (Vercel, Netlify or Cloudflare Pages connect to GitHub and comment a preview link; see [optional Vercel](14-optional-vercel.md)). This gives you visual review from your phone.
- **Deploy on merge** to the default branch, with a staging environment before production.
- **Rollback**: revert the merge commit (`git revert -m 1 <hash>`) or redeploy the previous build; write the steps in `CLAUDE.md` under "Deployment and operations".
- **Monitoring**: error tracking (for example Sentry) and an uptime check, plus a one-page runbook for who gets told and what to try first.

## 9. Documentation
Planner lists the docs to update; reviewer flags missing updates; the PR checklist asks for it. Keep `CLAUDE.md` current: it is the memory every agent reads.

## 10. Measurement and improvement
- Each run writes `.pipeline/metrics.json` (minutes, Devin attempts, ACUs, test result, verdict) and a metrics line in the PR body and issue comment. Tested locally.
- Once a month: read the metrics, note rework rate (how often retries or `/fix` were needed), cost per merged PR, and any bug that escaped to production. Turn recurring mistakes into rules in `CLAUDE.md`. **Your job.**

## 11. Process hygiene
- One run at a time (`concurrency` in `pipeline.yml`), so runs do not edit the same files at once.
- Merged branches auto-delete (`harden-repo.sh`); delete stale `pipeline/*` branches from plan-only or failed runs.
- Merge only the draft PR of a full run.

## What is still not covered
A second human reviewer, compliance review (what customer data you collect and how long you keep it), usability testing with real users, and validating that the product is worth building. These are judgment calls the pipeline cannot make for you.
