# Triage, ACU budget, prompt engineer and demo screenshots (v1.3)

**Author:** Gil Lotzky

Four additions that make a run cheaper and easier to trust from a phone. All are on by default except the prompt engineer, and each can be turned off with a repository variable (Settings → Secrets and variables → Actions → Variables).

| Addition | In one line | Default | Turn off or change |
|---|---|---|---|
| Triage | A cheap first stage labels the ask and chooses the lightest safe route | On | `PIPELINE_TRIAGE=0` |
| ACU budget | Devin gets a hard per-session ACU limit, and every run says whether it stayed inside its budget | On (cap 10) | `PIPELINE_MAX_ACU=<number>` |
| Demo screenshots | The tester looks at real screenshots of the running app and confirms them | On when triage says the change is visible in a browser | `PIPELINE_DEMO=0` |
| Prompt engineer | A small model, which can be free (Ollama), rewrites the spec into a short developer brief | Off | `PIPELINE_PROMPT_ENGINEER=claude\|ollama\|openai` |

## 1. Triage (the evaluation lead)

Runs first, on a small model (`claude-haiku-5-5`), before research. It reads the idea and writes `.pipeline/triage.md`. The first six lines are a fixed format the orchestrator reads:

```
KIND: bug | feature | chore | docs | no-code
SIZE: xs | s | m | l
ROUTE: full | light | stop
NEEDS_DEMO: yes | no
ACU_BUDGET: 1-10
REASON: one sentence
```

Below that is a **Delegation** section: what the planner, developer and tester should do and what they should not spend effort on. The planner and tester read it. It can narrow the work; it can never remove the unit tests required for new or changed behavior.

What the orchestrator does with the answer:

- **Labels** the issue `kind:...`, `size:...`, `route:...` (only for values that were really parsed). Needs the `issue` number, which `/go` already passes.
- **`light` route** skips the research stage for small asks whose files are obvious.
- **`stop` route** ends the run before any spend, and says so plainly ("Pipeline stopped by triage: no code change needed"). It is honoured only for `KIND: no-code`: a setting, an account, a question, something already done. This is the fix for the earlier case where a settings question produced a "success" run with no PR. To build anyway, add a line `FORCE: yes` to the brief and run `/go` again.
- **Missing or invalid answer** means the full route and the run-wide ACU cap. Triage can only make a run cheaper or stop it for a no-code ask; a broken triage never blocks a build.
- `/go triage` stops after this stage (a cheap way to see how an idea would be routed).
- Fix runs (`/fix`) do not triage again: a human asked for that change.

How to develop it: edit the rules in `.claude/agents/triage.md` (the six-line format is parsed by `pipeline/triage_lib.py`, which has unit tests). To add a label or a route, change `triage_lib.py`, then its tests, then the agent text.

## 2. ACU budget and the "low usage" confirmation

Devin is billed in ACUs. This release adds three layers, cheapest first:

1. **A budget in the prompt.** Triage sets `ACU_BUDGET` (default by size: xs 1, s 2, m 4, l 8). The developer prompt says to stay inside it and not explore.
2. **A hard limit on the session.** The budget is sent to Devin as `max_acu_limit` when the session is created. The Devin API documents this field but not exactly what happens at the limit, so the orchestrator handles both outcomes: if Devin stops at the limit without pushing any commits, the run fails with a clear message (`acu_limit_reached`) and does not pretend to succeed. If Devin rejects the field, the session runs without a cap and the summary says so.
3. **A run-wide cap.** `PIPELINE_MAX_ACU` (default 10) bounds the whole run: before any rework attempt, if the ACUs already used reach the cap, the run stops (`acu_cap_reached`) instead of starting another session.

Every run's summary then states the result in one sentence, for example `1.5 ACUs used of a 2 ACU budget: within budget`, or `OVER budget`, or `Devin did not report ACU usage for this run, so usage cannot be confirmed`. The same facts are in the metrics record (`devin.acu_budget`, `acu_limit`, `over_budget`), and `python3 metrics/summarize.py` shows the share of runs that stayed within budget. Unknown stays unknown; it is never counted as zero.

Other ways to lower ACU use, outside this pipeline: smaller issues, `/go plan` before building, and checking your plan's ACU price. Devin also offers other session modes; check whether one is cheaper for you before relying on it.

## 3. Demo screenshots confirmed by the tester

When triage says `NEEDS_DEMO: yes`, after Devin pushes and dependencies are installed, `pipeline/demo.py`:

1. starts the app (Vite projects are detected; otherwise set `PIPELINE_DEMO_CMD` and `PIPELINE_DEMO_URL`),
2. waits for it to answer, then takes a screenshot of each page in `PIPELINE_DEMO_PATHS` (default `/`, at most 6) with headless Chromium through Playwright,
3. records, per page, the HTTP status, console errors and failed requests in `.pipeline/demo/report.json`,
4. stops the app. The app runs **without the pipeline's secrets** in its environment.

Playwright and Chromium are installed on demand, only on runs that need a demo (about a minute). The tester then opens each image, compares it with the acceptance criteria, and writes a `## Demo` section plus a line `DEMO: PASS`, `DEMO: FAIL` or `DEMO: SKIPPED`. A screenshot showing an error page or contradicting a criterion makes the test result FAIL, which sends the run through its normal rework loop.

Where you see it: the screenshots are committed to the run's branch under `.pipeline/demo/`, embedded in the draft pull request description, and uploaded as the Actions artifact `pipeline-demo-<run>`. The embedded links point at the private repository, so they render for you when you are signed in to GitHub; I have not confirmed how the GitHub mobile app displays them, and the artifact and branch files are the fallback.

If the demo cannot run (no start command, app never starts, Playwright cannot install), the run continues: the PR says "No screenshots" with the reason, and the tester writes `DEMO: SKIPPED`. A demo problem never fails a run by itself, and the tester is told never to invent one. Use fake data only: screenshots are stored in the repository.

How to develop it: `pipeline/demo.py` is also a command (`python3 pipeline/demo.py --cmd "npm run dev" --url http://127.0.0.1:5173 --paths /,/leads`). Add framework detection in `detect()`. The tester's rules live in `.claude/agents/tester.md` and the task text in `tester_task()` in `pipeline/run.py`.

## 4. Prompt engineer (optional, can be free)

An optional stage after the plan (and design) that turns the spec into a short brief for Devin: goal, files, tests, done-when, do-not. The brief is added to the developer prompt **after** the fixed rules and labeled as non-authoritative: the spec and the rules always win, so a bad brief cannot switch off a guardrail. If the stage fails, the default prompt is used and the run continues.

Choose a backend with `PIPELINE_PROMPT_ENGINEER`:

| Value | Where it runs | Cost | Notes |
|---|---|---|---|
| `off` | nowhere | none | Default: the built-in developer prompt |
| `claude` | Claude CLI, small model (`.claude/agents/prompt-engineer.md`) | A few cents per run (see `ai_usage` in the metrics) | Most reliable |
| `ollama` | An Ollama server: set `OLLAMA_HOST` (for example your own machine through a tunnel or a self-hosted runner) and optionally `OLLAMA_MODEL` (default `llama3.2:3b`) | No API cost | If `OLLAMA_HOST` is empty the workflow installs Ollama on the runner and pulls the model every run: free, but slow on a CPU runner, a large download, and it uses Actions minutes |
| `openai` | Any OpenAI-compatible endpoint: `PIPELINE_PE_URL`, `PIPELINE_PE_MODEL`, and the secret `PIPELINE_PE_API_KEY` if needed | Depends on the provider (some have free tiers; check their current terms) | LM Studio, vLLM or a hosted service |

Small local models write weaker briefs, so the output is checked (length, required sections, mentions tests) and rejected if it does not look right. Whether the stage actually saves ACUs for your project is something to measure: compare `devin.acus_consumed` with the stage on and off using `metrics/summarize.py`.

How to develop it: backends and validation are in `pipeline/prompt_engineer.py` (tested against a local stub server); the instructions the model gets are in `.claude/agents/prompt-engineer.md`.

## Repository variables added in v1.3

`PIPELINE_TRIAGE`, `PIPELINE_MAX_ACU`, `PIPELINE_DEMO`, `PIPELINE_DEMO_CMD`, `PIPELINE_DEMO_URL`, `PIPELINE_DEMO_PATHS`, `PIPELINE_PROMPT_ENGINEER`, `OLLAMA_HOST`, `OLLAMA_MODEL`, `PIPELINE_PE_URL`, `PIPELINE_PE_MODEL`, and `PIPELINE_REQUIRE_TESTS` (the unit-test gate switch, now passed through). Secret: `PIPELINE_PE_API_KEY` (only for the `openai` backend).

## What is verified

Tested locally (see the README verification table): triage parsing and routing, labels, the ACU limit, budget and cap logic against a fake Devin, the prompt-engineer backends against local stub servers, and the demo step against real headless Chromium. **Not yet run in GitHub Actions or against the real Devin API:** the `max_acu_limit` field, installing Playwright on a runner, Ollama on a runner, and how the embedded screenshots look in the GitHub mobile app.
