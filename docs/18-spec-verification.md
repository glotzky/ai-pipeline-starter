<!--
HOW TO DEVELOP THIS FILE (invisible when rendered on GitHub)
Purpose: explain the optional Specification Verification Engine (SVE) step: what it adds, how to turn it on, how to read it.
Edit it when: sve_lib.py or its hooks in run.py change, or a PIPELINE_SVE_* variable is added or removed.
How: keep the variable table in step with template/.github/workflows/pipeline.yml (tests/test_workflows.py checks the wiring).
-->
# 18. Specification verification (optional)

The pipeline can ask a **Specification Verification Engine** (SVE) what "done" means *before* the developer starts, and check it *with evidence* afterwards. It is off unless you set `PIPELINE_SVE_URL`. With it off, nothing in the pipeline changes.

## What it adds

```
... Planner -> [Designer] -> SVE: spec + numbered criteria -> Developer (Devin) -> Tester
                                                                    -> SVE: run tests, judge each criterion -> Reviewer -> draft PR
```

1. **After planning**, SVE turns your idea into a specification with numbered acceptance criteria (`AC-001`, ...). They are written to `.pipeline/acceptance.md` on the branch, and the developer prompt tells Devin to name at least one automated test per criterion with its id (for example `test_AC_003_rejects_empty_name` or `it('AC-003 rejects an empty name')`).
2. **After the tester passes**, the pipeline runs your project's tests with a JUnit reporter and uploads the result to SVE. SVE judges every criterion from the test results alone:
   - **Verified**: a passing test names it, and nothing linked failed or errored.
   - **Failed**: a linked test failed.
   - **Blocked**: a linked test errored before reaching a verdict.
   - **Unverified**: no linked passing test, or it cannot be tested as written. *No evidence, no Verified.*
3. With the default gate (`enforce`), anything short of fully Verified sends the work back to the developer (a retry, like failing tests), and a final `SHIP` verdict is lowered to `NEEDS WORK`. The report goes in the pull request under **Specification verification**.

SVE never reads your code and never trusts a claim in prose. A passing test that does not name a criterion counts for nothing; the report lists such tests so you can fix the names.

## Turn it on

You need an SVE reachable **from GitHub Actions** (not `localhost`), over HTTPS, with `SVE_API_TOKEN` set on it.

| Name | Kind | Meaning |
|---|---|---|
| `PIPELINE_SVE_URL` | variable | Base URL of SVE. Unset = feature off. |
| `PIPELINE_SVE_TOKEN` | **secret** | The same value as SVE's `SVE_API_TOKEN`. |
| `PIPELINE_SVE_TEST_CMD` | variable | Command that runs your tests and writes JUnit XML to `{junit}`. Python projects default to `python -m pytest -q --junitxml={junit}`. Others must set it (for example `npx vitest run --reporter=junit --outputFile={junit}`). |
| `PIPELINE_SVE_JUNIT` | variable | Where the JUnit file is written (default: a temp file). |
| `PIPELINE_SVE_GATE` | variable | `enforce` (default), `report` (inform only, never blocks), or `off`. |

## If SVE is unreachable

The run does not crash. The summary says "Specification verification unavailable", no criterion is called verified, and under `enforce` the verdict is lowered to `NEEDS WORK`. Retrying cannot fix an unreachable service, so the developer is not re-run for it.

## Fixing an existing pull request

`/fix` reuses the specification stored in `.pipeline/sve.json` on the branch and verifies again.

## Not yet verified live

Everything above is covered by tests against a stand-in SVE server and the real `run.py`. It has not yet run in GitHub Actions against a hosted SVE. Try it with `PIPELINE_SVE_GATE=report` first.
