# 12. Gap analysis: what a strong software team does that this pipeline does not (yet)

A review of the pipeline against the practices of an efficient, high-quality engineering team. Status:
**Covered** = built and in the template. **Partial** = some of it exists. **Missing** = not built.

## Where it matches a good team

| Practice | How the pipeline does it | Status |
|---|---|---|
| Clarify requirements before building | Interviewer asks up to 4 questions and writes a brief | Covered |
| Research / spike | Researcher reads the repo and web, reports risks | Covered |
| Written spec with acceptance criteria | Planner writes `spec.md` with files, signatures, edge cases | Covered |
| Design before building when needed | Designer runs when the spec says so | Covered |
| Implementation by a specialist | Devin works on a branch | Covered |
| Unit tests with the change | Planner lists tests; Devin writes them; Tester verifies; orchestrator gate blocks a run with none | Covered |
| Independent review | Read-only Reviewer with a SHIP / NEEDS WORK / BLOCK verdict | Covered |
| Human approval before merge | Draft PRs only, owner merges | Covered |
| Branch per change, audit trail | `pipeline/<timestamp>` branches, handoff files, issue comments | Covered |
| Cost control | Spend limit, retry and time caps, staged runs | Covered |

## What is missing or thin

*Updated: most items below are now built into the template (see [engineering practices](13-engineering-practices.md) for where each lives). "Built" means written and, where noted, tested in a scratch repo; none of the new workflows have run live yet. Items still open: 7 (end-to-end tests), 11 (visual previews: set up on your host), 12, 13, 14 (deployment and monitoring: outside the pipeline), 19, 20.*

Ordered by value for a small team shipping a customer-facing app. "Effort" is a rough build estimate.

| # | Practice | Why teams do it | Status today | What to add | Effort |
|---|---|---|---|---|---|
| 1 | **CI on every pull request** | Checks run on every change, including your own edits, not only inside the pipeline | **Built, not yet run live** | A `ci.yml` workflow: install, lint, type-check, test, build on every PR | Small |
| 2 | **Branch protection** | Nothing merges unless CI is green; nobody pushes to `main` | **Built (script), not yet run live** | Require PRs and the CI check on `main`; add `CODEOWNERS` for `.github/`, `.claude/`, `pipeline/` | Small |
| 3 | **Security scanning** | Catches vulnerable dependencies, leaked secrets and common code flaws automatically | **Built (script and config), not yet run live** | Dependabot, GitHub secret scanning and push protection, CodeQL. All free for private repos on supported plans (verify your plan) | Small |
| 4 | **Lint, format, type-check as enforced gates** | Style and type errors never reach review | **Built (CI runs them)**, not yet run live | Make the tester and CI fail on them | Small |
| 5 | **Fix loop after review** | Reviewer comments get addressed on the same PR | **Built (`/fix`), not yet run live** | `/fix <text>` on a PR that sends feedback to Devin on the same branch | Medium |
| 6 | **Backlog and sequencing** | Work is broken into ordered slices; the next starts when the last ships | **Built (project planner and queue), not yet run live** | A project planner that creates ordered issues and a queue that starts the next after a merge | Medium |
| 7 | **Integration and end-to-end tests** | Unit tests miss broken wiring between parts | **Missing.** Unit tests only | Add integration tests for data access and one end-to-end smoke test (Playwright) for key flows | Medium |
| 8 | **Definition of done / PR template** | Everyone checks the same list | **Built** (PR template) | A PR template with a checklist: tests, docs, screenshots, migration notes, risk | Small |
| 9 | **Documentation upkeep** | README, API notes and decisions stay true | **Partial.** Planner, reviewer and PR checklist cover it; no automated changelog | Planner lists doc changes; reviewer flags missing ones; keep a short changelog and a decisions log (ADRs) | Small |
| 10 | **Database change safety** | Migrations are reviewed, reversible and tested | **Built as policy** (`CLAUDE.md` rules, reviewer check); a human applies migrations | A rule: every migration has a rollback and is tested on a scratch database; a human applies it | Medium |
| 11 | **Visual review for UI work** | Reviewers see what changed, not just code | **Missing.** UI is judged from a diff | Screenshot or preview deployment per PR (Vercel, Netlify or Cloudflare previews; see [optional Vercel](14-optional-vercel.md)) | Medium |
| 12 | **Accessibility and performance checks** | Catches issues before users do | **Missing** | Lighthouse or axe checks in CI with budgets | Medium |
| 13 | **Deployment and rollback** | Shipping is a routine, reversible step | **Missing.** Out of scope by design | Preview per PR, staging, deploy on merge, and a written rollback | Medium |
| 14 | **Monitoring and error tracking** | You hear about failures before customers do | **Missing** | Error tracking (for example Sentry) and uptime checks; a runbook | Small to medium |
| 15 | **Bug triage and hotfix path** | Defects are reported, reproduced and fixed fast | **Built** (`[bug]` form, failing test first), not yet run live | A `[bug]` issue template that starts with a failing test, plus a fast `/go` path | Small |
| 16 | **Metrics and retrospectives** | Teams improve by measuring cycle time, rework and escaped defects | **Built** (`metrics.json` per run); the monthly review is yours | Log cost, ACUs, retries and verdict per run to a file or sheet; a monthly review that feeds lessons back into `CLAUDE.md` | Small |
| 17 | **Concurrency control** | Two changes to the same files do not collide | **Built** (one run at a time) | Queue runs one at a time per project; rebase before the PR | Small to medium |
| 18 | **Dependency and branch hygiene** | Old branches and stale packages do not pile up | **Built** (auto-delete merged branches, Dependabot) | Auto-delete merged branches (a repo setting), weekly Dependabot | Small |
| 19 | **Compliance and data privacy** | Customer data is handled lawfully and safely | **Partial.** Security doc covers the pipeline, not your app | For a project with customer data: a data-handling policy, no real customer data in repo or tests, review of what you collect and retain | Your call |
| 20 | **Second human reviewer** | Humans catch what the AI misses | **Missing.** You are the only reviewer | For high-risk changes, require a second person or a deliberate pause | Process |

## Practices that help most for a one-person team

If you only add five things, add these, in order:

1. **CI on every PR** (#1) and **branch protection** (#2). Together they make "green" mean something even when the AI reviewer is wrong.
2. **Security scanning** (#3). Cheap, automatic, and the AI reviewer is not a substitute.
3. **PR template with a done checklist** (#8), so your own review is consistent.
4. **`/fix` on a PR** (#5). It is the biggest day-to-day friction remover, because feedback stays on the same branch.
5. **Project planner and queue** (#6), when you have a backlog and want to work from your phone.

## Honest limits

- The AI reviewer comes from the same model family as the planner and tester. It will share blind spots. CI, scanners and your own read are the independent checks.
- Passing tests prove the code does what the tests say, not that the tests are right. Skim test files in every PR.
- Nothing here proves the product is worth building. The interviewer sharpens an idea; it does not validate demand.
- Cost and quality numbers in these docs are estimates until you measure real runs.
