# Pipeline metrics

Every pipeline run writes one structured JSON record to `metrics/runs/<run_id>.json` (a `/fix` run writes `<run_id>-fix.json`). The records follow [`schema.json`](schema.json). [`summarize.py`](summarize.py) turns many records into success rate, median run time, average retries, test pass rate and average cost.

Nothing here is estimated. A value is either measured, reported by a tool, or `null` ("not available"). Averages skip `null` and say how many runs they are based on.

## Where the data lives

| Place | What | Lasts |
|---|---|---|
| The run's branch (`pipeline/<run_id>`), file `metrics/runs/` | The final record, committed by the pipeline | Forever once the PR is **merged**. Plan-only, failed and abandoned runs stay on their unmerged branches |
| GitHub Actions artifact `pipeline-metrics-<workflow run id>-<attempt>` | The same record, uploaded even if the run failed or was cancelled | 90 days |

The record is written when the run starts (status `incomplete`) and rewritten after every stage, so a run that crashes, is cancelled or times out still leaves an honest partial record. The pipeline only ever writes inside `metrics/runs/`; it never changes existing records.

## What a record contains

| Field | Meaning | Source |
|---|---|---|
| `run_id`, `kind`, `branch`, `until` | Unique id (UTC timestamp), `run` or `fix`, the run branch, the `--until` stage | Automatic |
| `status` | `success`, `failure`, `stopped` (ended early on purpose: `/go plan`, planner `BLOCKED`) or `incomplete` (no end was recorded) | Automatic |
| `stop_reason` | `completed`, `until_<stage>`, `planner_blocked`, `devin_no_commits`, `exception`, ... | Automatic |
| `started_at`, `ended_at`, `duration_seconds` | Wall-clock start and end; `null` while incomplete | Automatic (monotonic clock for durations) |
| `stages[]` | Per stage and attempt: name, start, end, `duration_seconds`, status `ok`/`error`/`stopped`/`incomplete`, a short scrubbed `detail` on error | Automatic |
| `retries` | `developer_attempts`, `retries` (attempts minus 1), `reasons` (`tests_failed`, `needs_work`) | Automatic |
| `tests` | Final `result` (`PASS`/`FAIL`/`not_run`), number of attempts, whether the missing-unit-tests gate ever fired | Automatic. **Test counts are not recorded**: the tester reports them in prose, which is not reliable to parse |
| `review.verdict` | `SHIP`, `NEEDS WORK`, `BLOCK`, `UNKNOWN` or `not_run` | Automatic |
| `pull_request` | Created or updated, number and URL | Automatic |
| `devin` | Sessions, how many reported ACUs, total `acus_consumed`, `acu_budget` (from triage), `acu_limit` (sent to Devin), `over_budget` | Automatic. Devin exposes ACUs only; **no dollar cost is computed** because the ACU rate depends on your plan. `over_budget` is `null` when either number is unknown |
| `triage` | Kind, size, route, whether a demo was needed, ACU budget, and whether triage gave a usable answer (`parsed`) | Automatic (v1.3). `null` on fix runs and when triage is off |
| `prompt_engineer` | Backend (`claude`, `ollama`, `openai`) and status (`ok`, `invalid`, `unavailable`) | Automatic (v1.3). `null` when the stage is off |
| `demo` | Status (`ok`, `skipped`, `failed`, `not_needed`), number of screenshots, reason, and what the tester confirmed (`PASS`, `FAIL`, `SKIPPED`, `missing`) | Automatic (v1.3). `missing` means screenshots existed but the tester wrote no `DEMO:` line |
| `ai_usage.calls[]` | Per Claude call: stage, model, input, output, cache-creation and cache-read tokens, `cost_usd`, `num_turns` | Automatic, from the Claude CLI's own JSON result |
| `ai_usage.totals` | Sums over the calls that reported a value. `cost_complete` is `false` if any call reported no cost | Automatic |
| `github` | Workflow run id and attempt | Automatic |
| `error` | Exception type and a scrubbed, truncated message, only on failure | Automatic |

## Automatic versus manual versus not collected

- **Automatic:** everything above.
- **Manual (you):** the monthly review of the numbers, and anything about whether a merged change was actually good (bugs found later, rework outside the pipeline).
- **Not collected:** Claude usage from the issue **interview** stage (`intake.yml`, a separate workflow and job); Devin dollar cost; test counts; time you spent reviewing. Add them as you need them; do not backfill guesses.

## Privacy and secrets

Records contain no idea text, prompts, review text, file contents, Devin session links, keys or tokens. Error messages are scrubbed of the pipeline's secret values and token-shaped strings (`cog_`, `sk-ant-`, `ghp_`, `github_pat_`, `Bearer ...`, org ids) and cut to 300 characters. The schema rejects unknown fields so free text cannot sneak in unnoticed. The PR URL and branch name are recorded; if the repository is public, so are those. Set the repository variable `PIPELINE_METRICS` to `0` to turn recording off.

## Summarize

```bash
python3 metrics/summarize.py                  # all records in metrics/runs
python3 metrics/summarize.py --kind run       # only new-idea runs (or --kind fix)
python3 metrics/summarize.py --json           # machine-readable
```
Example output:
```
Runs: 5  (success 2, failure 1, stopped early 1, incomplete 1)
Success rate:              66.7%  [n=3]
Median run time:           450s (7.5 min)  [n=4]
Average developer retries: 0.5  [n=4]
Test pass rate:            66.7%  [n=3]
Average Claude cost:       $0.1400  [n=3]
Average Devin ACUs:        4  [n=2]
```
`[n=...]` is the number of runs the figure is based on.

| Figure | Definition |
|---|---|
| Success rate | `success / (success + failure)`. Early stops and incomplete runs are excluded and counted separately |
| Median run time | Median `duration_seconds` of runs that ended (success, failure, stopped) |
| Average developer retries | Mean `retries.retries` over runs that reached the developer stage |
| Test pass rate | Runs whose final `tests.result` is `PASS`, over runs that ran tests |
| Average Claude cost | Mean of `ai_usage.totals.cost_usd` over runs where the CLI reported a cost, as reported by the CLI (list prices at the time) |

Invalid or unreadable files are skipped and listed, never silently counted. If the same run appears twice (the merged copy and an artifact), the finished copy wins.

### Including runs that were never merged
Merged runs are already in `metrics/runs/`. For failed, plan-only and abandoned runs, download the artifacts and summarize both folders together:
```bash
mkdir -p /tmp/runs
for id in $(gh run list --workflow pipeline.yml --limit 50 --json databaseId --jq '.[].databaseId'); do
  gh run download "$id" --pattern 'pipeline-metrics-*' --dir "/tmp/runs/$id" 2>/dev/null
done
python3 metrics/summarize.py metrics/runs /tmp/runs
```

## Verify after your next run
1. Actions -> the finished run -> **Artifacts**: `pipeline-metrics-...` is there.
2. On the run's branch (or the merged PR): `metrics/runs/<run_id>.json` exists. Open it: `status`, `stages`, `ai_usage.totals` should look right, and `cost_usd` should be a number.
3. `python3 metrics/summarize.py` prints the figures above.
4. Check the PR body: its "Metrics" line should agree with the record.
5. Search the file for anything sensitive: `grep -iE "sk-ant|cog_|ghp_|bearer|devin.ai" metrics/runs/*.json` should print nothing.

## Changing the schema
Edit `schema.json` and `pipeline/run_metrics.py` together, bump `schema_version`, keep old records readable, and run the tests from the starter repository (`python3 -m unittest discover -s tests`).
