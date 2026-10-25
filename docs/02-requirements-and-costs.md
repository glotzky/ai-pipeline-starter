# 2. Requirements and costs

## Accounts you need

| Account | Used for | Notes |
|---|---|---|
| **GitHub** | Repo, Actions runners, Issues (your inbox), PRs | A **private** repo is recommended. GitHub's mobile app is the phone interface. |
| **Anthropic API** (console.anthropic.com) | Claude for the interviewer, researcher, planner, designer, tester, reviewer | Pay per token. This is billed separately from a Claude chat subscription. Set a monthly spend limit. |
| **Devin** (devin.ai) | The Developer stage, via API | Needs a plan that allows API access through **service users** (see below). |

Optional: VS Code with the Claude Code extension, for editing the kit and project rules locally.

## Devin: what to know before you pay

*(Current as of October 2026; plans change, verify on devin.ai/pricing.)*

- Cognition retired the old Core and Team plans in 2026. The self-serve individual plan is **Pro, $20/month**, with quotas; usage beyond quota is billed at API pricing.
- API access uses a **service user** (Settings -> Devin API -> Service users). Its key starts with `cog_`, is shown **once**, and is scoped to your organization. Base URL: `https://api.devin.ai/v3`.
- A new account can fail with `403 ... "Your organization has a billing error. Error: out_of_quota"` when creating a session until billing / extra usage is enabled. Fix it in Devin's billing settings, then retry. The `/v3/self` call can succeed while session creation fails, so test with a real session.
- Sessions report `acus_consumed`; the orchestrator logs it so you can see cost per run.

## Local requirements (only for setup and maintenance)

Required: **git** and a web browser. Everything else is optional.

| Tool | Needed for | Required? |
|---|---|---|
| git | Getting the template into your repo | Yes |
| GitHub CLI (`gh`) | The `set-secrets` scripts; creating PRs from a terminal | Optional (web UI works) |
| Node.js 20+ and Python 3.10+ | Running things locally, testing `run.py` | Optional (Actions installs its own) |
| Claude Code (CLI or VS Code extension) | Editing prompts and rules with AI help | Optional |

Install commands per operating system are in the [setup guide](03-setup-guide.md).

## What it costs: fixed, variable and everything around it

*Prices checked in October 2026 where marked "verified"; everything else is a planning estimate. Vendors change prices; confirm on each pricing page before committing.*

### Fixed monthly costs

| Item | Cost | Status |
|---|---|---|
| GitHub (private repo, free plan) | $0, includes a monthly quota of Actions minutes | Plan quotas unchanged per a January 2026 announcement; check your plan's current minutes |
| Devin Pro | **$20/month**, with a usage quota (about 1 ACU is roughly 15 minutes of active work) | Verified. Higher tiers exist: Max $200, Teams $80 base plus $40 per seat |
| Anthropic API | $0 fixed, pay per token | Verified model prices: Opus 5.5 $4 / $20, Sonnet 5.5 $2 / $10 per million input / output tokens |
| **Fixed total** | **about $20** | |

### Variable cost per feature run (estimates, replace with your measured numbers)

| Stage | Model or tool | Rough cost per run |
|---|---|---|
| Interviewer (1 to 3 comments) | Sonnet | $0.05 to $0.30 |
| Researcher | Sonnet | $0.20 to $1.00 |
| Planner | Opus | $0.30 to $1.50 |
| Designer (only some runs) | Sonnet | $0.10 to $0.60 |
| Tester (per attempt) | Sonnet | $0.30 to $1.50 |
| Reviewer (per attempt) | Opus | $0.30 to $1.50 |
| **Claude subtotal** | | **about $1 to $8** (retries add to it) |
| Developer | Devin | Draws on the Pro quota, then overage at Devin's on-demand rate (not verified here). A small slice is often about 1 to 5 ACUs; measure it |
| GitHub Actions minutes | Runner time while the job waits for Devin | About 30 to 90 minutes per run |

### Worked monthly examples

| Usage | Claude | Devin | Actions | Likely total |
|---|---|---|---|---|
| Light: 8 small features | $10 to $40 | $20 plus maybe overage | Free quota covers it (about 4 to 12 hours) | **$40 to $100** |
| Medium: 20 features | $25 to $100 | $20 plus overage (this is the line to watch) | Near or over a free quota; overage a few dollars | **$100 to $250** |
| Heavy: 40 features, many retries | $60 to $200 | Often needs the Max tier ($200) | A few dollars to $20 | **$300 to $450** |

### Costs outside the pipeline (what you are building)

| Item | Typical cost |
|---|---|
| Supabase | Free: 2 active projects, 500 MB database, pauses after a week of inactivity. Pro: **$25/month** per organization (verified). Use Pro before real customers |
| App hosting | $0 to $20+/month. Vercel Hobby is free but **non-commercial only**; Pro is $20 per developer seat per month. Netlify and Cloudflare Pages are alternatives. See [optional Vercel](14-optional-vercel.md) |
| Domain | about $10 to $20/year |
| Email, analytics, error monitoring | $0 to $30/month on starter tiers |
| Optional always-on computer / local models | $0 if you skip it. See [local models](11-local-models-ollama.md) |

**Do not trust these numbers until you have measured.** After your first three full runs, note the Anthropic console cost, the Devin ACUs for each run (the orchestrator logs `acus_consumed`) and the Actions minutes, then replace the estimates above with them.

## Cost controls (set these on day one)

1. **Anthropic console:** set a monthly spend limit. Use a dedicated API key for the pipeline so you can cap or revoke it alone.
2. **Retries are capped** at 2 by default (`--max-retries` in `run.py`).
3. **Devin wait is capped** at 180 minutes (`--devin-timeout`).
4. **Start with `/go plan`.** The cheap stages cost a dollar or two and show whether the idea and spec are sane before Devin is involved.
5. **Keep slices small.** A vague, large idea is the fastest way to burn Devin usage.
6. Check Devin's usage page and the Anthropic usage page after your first few runs.
