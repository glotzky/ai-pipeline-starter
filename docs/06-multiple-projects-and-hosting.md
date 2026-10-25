# 6. Multiple projects, and where it runs

## One pipeline for many projects, or a new pipeline each time?

**Short answer: reuse the kit, install a copy per project.** The kit is reusable; each project gets its own installed instance in its own repo.

### Why a per-repo instance is the default

- The agents work *inside* the repo they build: the Researcher reads its code, Devin pushes branches to it, the Tester runs its tests, PRs and issues live there. Keeping the pipeline in the same repo means no cross-repo checkouts or tokens.
- Each project needs its own `CLAUDE.md` (stack, commands, guardrails). That file is the project-specific part.
- Secrets, the environment's branch restriction, Actions permissions, and Devin's repo access are all per repo anyway.
- Installing is one command (`install.sh` / `install.ps1`) plus about ten minutes of setup, because that is what the kit is for.

### How to add a second project

1. Run the installer against the new repo.
2. Fill in its `CLAUDE.md`.
3. In Devin, grant access to the new repo (the same service user and key can serve several repos).
4. Create the environment and secrets in the new repo. Reuse the same keys, or **create separate Anthropic keys per project** so you can see and cap each project's cost separately.
5. Merge, run the Health check, then do the staged first run.

Tip: make your configured project a **GitHub template repository** (Settings -> "Template repository") so new projects start with the pipeline already in them.

### Options compared

| Approach | How | Good | Bad | Verdict |
|---|---|---|---|---|
| **A. Per-repo copy** (this kit) | Install into each repo | Simple, isolated, no cross-repo access, per-project cost and rules | Updating the kit means re-running the installer in each repo | **Recommended** |
| **B. Central pipeline repo with reusable workflows** | Project repos call a shared workflow (`workflow_call`) | One place to upgrade | Cross-repo checkouts and tokens, Devin needs access to many repos, harder debugging, shared blast radius | Consider at 5+ projects |
| **C. One monorepo for several apps** | One pipeline, `CLAUDE.md` per app folder | Single setup | Agents see everything; ideas must name the app; one branch policy | Only if the apps are truly one codebase |

### Things to know when running several projects

- **Concurrency.** Two runs in the *same* repo are independent (separate branches and Devin sessions) but can conflict at merge time. Run dependent slices one at a time: merge before starting the next.
- **Cost adds up across projects.** Devin quota and Anthropic spend are account-wide unless you separate keys.
- **Upgrading the kit.** Re-run the installer over an existing project. It overwrites workflows, agents and `run.py` (so keep local customizations of those in a branch or re-apply them), and never overwrites `CLAUDE.md`, `PIPELINE.md` or `.gitattributes`.
- **GitHub organization secrets** can share one set of keys across repos. The trade-off: they bypass the per-environment branch restriction, so prefer per-repo environment secrets unless you have a reason.

## Do I need a computer that is always on?

**No.** Nothing in the pipeline runs on your machine.

| Piece | Runs on |
|---|---|
| Interviewer, orchestrator, Claude stages | GitHub-hosted runners (Actions) |
| Claude models | Anthropic's API |
| Developer | Devin's cloud VM |
| Your inbox and approvals | GitHub (browser or phone app) |

You need a computer for: the one-time setup, and editing prompt files or `CLAUDE.md` (which you can even do in GitHub's web editor). The phone is enough for daily use. A laptop being closed, asleep or off does not affect running jobs.

### Limits to be aware of

- **Runner minutes.** The orchestrator job sits and polls while Devin works, and that time counts against your Actions allowance (check your plan's included minutes). A long Devin task can consume up to 3 hours of runner time. Keep ideas small.
- **Job time limit.** One job is capped at 6 hours (the workflow uses 330 minutes). The Devin wait limit is 180 minutes by default.
- **Queueing.** GitHub-hosted runners start in seconds to minutes, not instantly.

### If you want your own runner (optional)

Only worthwhile if Actions minutes become a real cost or you want custom tooling installed. Options: a spare computer, a small VM or VPS you maintain, or a mini PC (roughly $150-300, low power, always on). Setup: Repo -> Settings -> Actions -> Runners -> New self-hosted runner, then change `runs-on: ubuntu-latest` to `runs-on: self-hosted` in the workflows.

Cautions for self-hosted runners: they execute AI-written code on your hardware, so use a dedicated machine or VM with nothing sensitive on it, never use one for a public repo, and keep it patched. Hosted runners are isolated and discarded after every run, which is a real security advantage. Start hosted; move only with a reason.

You do not need to buy hardware for this pipeline.
