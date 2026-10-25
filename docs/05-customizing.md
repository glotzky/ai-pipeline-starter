# 5. Customizing

## Project rules: `CLAUDE.md`

Every Claude stage reads it automatically (Claude Code loads `CLAUDE.md` from the repo root), and the Developer prompt tells Devin to read it first. It is the one file that adapts the pipeline to a project. Good contents:

- What the project is and who it is for (two sentences).
- Stack and package manager.
- Exact commands: install, test, type-check/lint/build.
- Conventions: reuse before creating, minimal diffs, where tests live and what to mock.
- **Protected files** (generated code, vendor folders, lockfiles you must not hand-edit).
- Pipeline rules: do not edit `.github/`, `.claude/`, `pipeline/`; write migrations but never run them; report anything needing accounts or secrets as a BLOCKER.
- **Product guardrails**: wording that must never be used, sensitive data rules, things that must not be built. This is where domain-specific safety lives.

Keep it under a page. Long rule files get ignored. Update it when the project changes shape.

## Agent prompts: `.claude/agents/*.md`

Each file is YAML front matter plus a prompt:

```markdown
---
name: planner
description: one line
tools: Read, Grep, Glob, Write
model: claude-opus-5-5
---
You are a planning specialist...
```

- **`tools`** limits what the agent can do. The reviewer deliberately has no `Write`/`Edit`. Do not widen it.
- **`model`**: the Claude model ID. Defaults: Opus for the planner and reviewer (quality gates), Sonnet for the rest. Model IDs change; look up current ones in Anthropic's docs and update here. A cheaper `claude-haiku-5-5` can serve simple stages.
- **Keep the machine-readable first lines.** `run.py` and the intake workflow parse `STATUS:`, `NEEDS_DESIGN:`, `RESULT:` and `VERDICT:`. If you reword those instructions, keep those exact formats.

## Orchestrator settings: `pipeline/run.py` and `pipeline.yml`

| Setting | Where | Default |
|---|---|---|
| Retries after failed tests or `NEEDS WORK` | `--max-retries` | 2 |
| Devin wait limit | `--devin-timeout` (minutes) | 180 |
| Whole-job limit | `timeout-minutes` in `pipeline.yml` | 330 |
| Base branch | `BASE_BRANCH` (set from the repo's default branch) | `main` |
| Dependency install command | repo **variable** `PIPELINE_INSTALL_CMD` | auto-detect |

To pass flags such as `--max-retries 1`, edit the last line of `pipeline.yml`: `run: python pipeline/run.py "$IDEA" --until "$UNTIL" --max-retries 1`.

### Other stacks and the dependency install

After Devin finishes, `install_deps()` runs on the branch before the Tester. It detects `package.json` (npm, pnpm or yarn by lockfile), `requirements.txt`, and `pyproject.toml`. For anything else (Go, Rust, Java, .NET, monorepos, system packages), set a repository variable: Settings -> Secrets and variables -> Actions -> **Variables** -> `PIPELINE_INSTALL_CMD`, for example `go mod download` or `cd backend && pip install -r requirements.txt && cd ../web && npm ci`. Runtimes other than Node and Python also need a setup step added to `pipeline.yml` (for example `actions/setup-go`).

Also tell the Tester how to run tests in `CLAUDE.md`.

## Stages

- **Skip the designer** for backend-only projects: it already runs only when the spec says `NEEDS_DESIGN: yes`; tell the Planner in `CLAUDE.md` or its prompt to use `no` unless a real UI is involved.
- **Add a stage** (for example a security reviewer or a docs writer): copy an agent file, then add a `claude_stage("name", "task")` call in `run.py` at the right point. Keep it read-only unless it must write.
- **Replace Devin** with a Claude coding agent: add `.claude/agents/coder.md` (tools: Read, Write, Edit, Grep, Glob, Bash; model Sonnet; prompt: implement exactly the spec, write `changes.md`) and call `claude_stage("coder", ...)` where `devin_run(...)` is called, skipping the polling. Untested here, but it removes the Devin dependency and its overage risk at the cost of more API tokens. The coder then runs on the Actions runner instead of Devin's VM, so it has the runner's limits.

## Extensions worth building next

- **Project planner and queue.** A `[project]` issue where you paste a whole plan; an agent breaks it into ordered slices and, on `/approve`, creates one `[idea]` issue per slice. A workflow on `pull_request: closed (merged)` then starts the next slice. Keeps you as the merge gate while removing the manual feeding.
- **Notifications elsewhere** (Slack, email) from the report-back step.
- **Scheduled runs**, for example a weekly dependency-update idea.
- **Auto-merge on `SHIP`.** Possible, but I do not recommend it: unreviewed AI code lands while you sleep, and one bad slice compounds through every later slice.
- **Stricter protection:** `CODEOWNERS` requiring your review for `.github/`, `.claude/`, `pipeline/`.

## Unit tests are required, not optional

Tests are enforced at four points, so a change cannot reach a draft PR without them:

1. **Planner**: the spec must include a "Tests to add" section (exact file paths and cases).
2. **Developer (Devin)**: told to write unit tests for every new or changed behavior and run them.
3. **Tester**: checks each acceptance criterion has a test, adds what is missing, and reports `RESULT: FAIL` for an empty, skipped or trivial suite.
4. **Orchestrator gate** (`missing_tests()` in `run.py`): if the branch changes source files (`.py .js .jsx .ts .tsx .go .rb .java .kt .rs .cs .php .swift`, excluding `*.config.*` and `.d.ts`) but adds or changes no test file, the run records `RESULT: FAIL` and sends Devin back (up to 2 retries). Test files are recognized by `test/`, `tests/`, `__tests__/` or `spec/` folders, `*.test.*`, `*.spec.*`, `*_test.*` and `test_*` names.
5. **Reviewer**: missing or superficial tests mean `NEEDS WORK` at minimum.

Set the repository variable `PIPELINE_REQUIRE_TESTS=0` to turn off only the orchestrator gate (also add `PIPELINE_REQUIRE_TESTS: ${{ vars.PIPELINE_REQUIRE_TESTS }}` to the "Run pipeline" env in `pipeline.yml`). Put your test command and framework in `CLAUDE.md`; the agents read it.

