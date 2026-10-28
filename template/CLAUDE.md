# Project conventions (read by every pipeline agent)

<!-- Fill in the TODO items. Keep it short and factual: every agent reads this on every run. -->

## Project
- What this is: TODO one or two sentences, and who it is for.
- Stack: TODO languages, frameworks, database, hosting.
- Package manager: TODO (npm / pnpm / yarn / pip / ...).

## Commands
- Install: TODO (for example `npm ci`)
- Test: TODO (for example `npm test` or `pytest`)
- Type-check / lint / build: TODO

## Conventions
- Reuse existing components and helpers before creating new ones. Match existing code style.
- Keep changes minimal and within the spec. No drive-by refactors.
- Secrets: never commit keys or `.env` files. Use `.env.example` with variable names only.
- Tests: TODO framework, and what to mock. No network or real databases in unit tests.
- **Every new or changed behavior ships with unit tests in the same change** (happy path, edge cases, a failure case). The pipeline fails a run that changes source code without adding tests.
- Generated or vendor files that must not be hand-edited: TODO (or "none")

## Definition of done
A change is done only when: unit tests cover every new or changed behavior; lint, type-check, tests and build pass; docs are updated if behavior or setup changed; no secrets or real customer data are in the diff; database changes ship as reversible migration files that a human applies.

## Data, security and privacy
- TODO: what personal or sensitive data this project handles, and the rules for it (what may be stored, logged, or sent to third parties).
- Never put real customer data in the repo, tests, issues or logs. Use obvious fake data.
- Validate all external input; check authorization on every data access.

## Database and migrations
- TODO: database and migration tool (for example Supabase migrations).
- Every schema change is a new migration file with a rollback note. Agents never apply migrations or touch production data.

## Deployment and operations
- TODO: where this deploys, how a preview or release is made, and how to roll back. Agents do not deploy.

## Run and demo
- How to start the app for a demo screenshot: TODO (for example `npm run dev -- --host 127.0.0.1 --port 4173`). Vite projects are detected automatically; for anything else set the repository variable `PIPELINE_DEMO_CMD` (and `PIPELINE_DEMO_URL`).
- Pages worth a screenshot: TODO (for example `/` and `/leads`; set `PIPELINE_DEMO_PATHS` to a comma-separated list).
- The demo app runs without the pipeline's secrets, so use fake or empty data. Screenshots are saved on the run's branch and shown in the pull request.

## Pipeline rules
- Work happens on `pipeline/*` branches. Only the owner merges to the default branch.
- Do not edit `.github/`, `.claude/`, `pipeline/`, `.pipeline/spec.md` or `.pipeline/design.md`.
- Agents write database migration files but never run them against any database.
- Unattended agents cannot create accounts, provision services or add secrets. If a task needs that, record it as a BLOCKER in changes.md instead of guessing.

## Product guardrails
- TODO rules specific to your domain (wording that must never be used, data that is sensitive, features that must not be built). Delete this section if none.
