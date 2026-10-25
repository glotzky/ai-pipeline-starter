#!/usr/bin/env python3
"""Summarize pipeline run metrics. Standard library only.

Usage:
  python3 metrics/summarize.py                      # reads metrics/runs
  python3 metrics/summarize.py DIR_OR_FILE [...]    # any mix of folders and .json files
  python3 metrics/summarize.py --kind run --json    # only new-idea runs, machine-readable

Records are checked against metrics/schema.json; invalid files are skipped and counted, never
silently used. Missing data (null) is excluded from an average and reported as "n/a" with the
number of runs it is based on. Nothing is estimated.
"""
import argparse
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FINISHED = ("success", "failure", "stopped")


# ---------- tiny JSON Schema subset validator (type, enum, required, properties, items,
# additionalProperties, minimum), enough for metrics/schema.json without third-party packages ----------
def _type_ok(value, name):
    if name == "null":
        return value is None
    if name == "boolean":
        return isinstance(value, bool)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "string":
        return isinstance(value, str)
    if name == "array":
        return isinstance(value, list)
    if name == "object":
        return isinstance(value, dict)
    return True


def validate(value, schema, path="$"):
    """Return a list of human-readable problems (empty list means valid)."""
    problems = []
    types = schema.get("type")
    if types is not None:
        names = types if isinstance(types, list) else [types]
        if not any(_type_ok(value, n) for n in names):
            return [f"{path}: expected {'/'.join(names)}, got {type(value).__name__}"]
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: {value!r} is not one of {schema['enum']}")
    if "minimum" in schema and isinstance(value, (int, float)) and not isinstance(value, bool) and value < schema["minimum"]:
        problems.append(f"{path}: {value} is below the minimum {schema['minimum']}")
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for key in schema.get("required", []):
            if key not in value:
                problems.append(f"{path}: missing required field '{key}'")
        if schema.get("additionalProperties") is False:
            for key in value:
                if key not in props:
                    problems.append(f"{path}: unexpected field '{key}'")
        for key, sub in props.items():
            if key in value:
                problems += validate(value[key], sub, f"{path}.{key}")
    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            problems += validate(item, schema["items"], f"{path}[{i}]")
    return problems


def load_schema():
    return json.loads((HERE / "schema.json").read_text())


# ---------- loading ----------
def find_files(paths):
    files = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            files += sorted(p.rglob("*.json"))
        elif p.is_file():
            files.append(p)
    return files


def load_records(paths, schema=None):
    """Return (records, skipped). Duplicate run_ids keep the most complete copy."""
    schema = schema or load_schema()
    best, skipped = {}, []
    for f in find_files(paths):
        try:
            rec = json.loads(f.read_text())
        except (OSError, ValueError) as e:
            skipped.append((str(f), f"not readable JSON ({type(e).__name__})"))
            continue
        problems = validate(rec, schema)
        if problems:
            skipped.append((str(f), problems[0]))
            continue
        key = (rec["run_id"], rec["kind"])
        old = best.get(key)
        # prefer a finished record over an incomplete one, then the later end time
        rank = (rec["status"] in FINISHED, rec.get("ended_at") or "")
        if old is None or rank > (old["status"] in FINISHED, old.get("ended_at") or ""):
            best[key] = rec
    return list(best.values()), skipped


# ---------- statistics ----------
def _mean(values):
    return round(statistics.fmean(values), 4) if values else None


def _median(values):
    return round(statistics.median(values), 1) if values else None


def summarize(records, kind=None):
    if kind:
        records = [r for r in records if r["kind"] == kind]
    by_status = {s: sum(1 for r in records if r["status"] == s) for s in ("success", "failure", "stopped", "incomplete")}
    finished = by_status["success"] + by_status["failure"]

    durations = [r["duration_seconds"] for r in records if r["status"] in FINISHED and r["duration_seconds"] is not None]
    ran_dev = [r for r in records if r["retries"]["developer_attempts"] > 0]
    retries = [r["retries"]["retries"] for r in ran_dev]
    tested = [r for r in records if r["tests"]["result"] in ("PASS", "FAIL")]
    passed = sum(1 for r in tested if r["tests"]["result"] == "PASS")
    costs = [r["ai_usage"]["totals"]["cost_usd"] for r in records if r["ai_usage"]["totals"]["cost_usd"] is not None]
    partial_cost = sum(1 for r in records if r["ai_usage"]["totals"]["cost_complete"] is False)
    acus = [r["devin"]["acus_consumed"] for r in records if r["devin"]["acus_consumed"] is not None]
    tokens = {f: [r["ai_usage"]["totals"][f] for r in records if r["ai_usage"]["totals"][f] is not None]
              for f in ("input_tokens", "output_tokens")}

    stage_times = {}
    for r in records:
        for s in r["stages"]:
            if s["duration_seconds"] is not None and s["status"] in ("ok", "error"):
                stage_times.setdefault(s["name"], []).append(s["duration_seconds"])

    return {
        "runs": len(records),
        "by_status": by_status,
        "success_rate": {"value": round(by_status["success"] / finished, 4) if finished else None,
                         "based_on": finished,
                         "note": "success / (success + failure); stopped and incomplete runs are excluded"},
        "median_duration_seconds": {"value": _median(durations), "based_on": len(durations)},
        "median_stage_seconds": {k: {"value": _median(v), "based_on": len(v)} for k, v in sorted(stage_times.items())},
        "average_developer_retries": {"value": _mean(retries), "based_on": len(retries)},
        "test_pass_rate": {"value": round(passed / len(tested), 4) if tested else None, "based_on": len(tested)},
        "average_cost_usd": {"value": _mean(costs), "based_on": len(costs),
                             "runs_with_partial_cost": partial_cost,
                             "note": "Claude cost as reported by the Claude CLI; excludes Devin (billed in ACUs)"},
        "average_devin_acus": {"value": _mean(acus), "based_on": len(acus)},
        "average_tokens": {f: {"value": _mean(v), "based_on": len(v)} for f, v in tokens.items()},
    }


# ---------- output ----------
def _fmt(entry, kind="num"):
    v = entry["value"]
    if v is None:
        return "n/a (no data)"
    if kind == "pct":
        text = f"{v * 100:.1f}%"
    elif kind == "usd":
        text = f"${v:.4f}"
    elif kind == "sec":
        text = f"{v:.0f}s ({v / 60:.1f} min)"
    else:
        text = f"{v:g}"
    return f"{text}  [n={entry['based_on']}]"


def render(s, skipped):
    st = s["by_status"]
    lines = [
        f"Runs: {s['runs']}  (success {st['success']}, failure {st['failure']}, "
        f"stopped early {st['stopped']}, incomplete {st['incomplete']})",
        f"Success rate:              {_fmt(s['success_rate'], 'pct')}",
        f"Median run time:           {_fmt(s['median_duration_seconds'], 'sec')}",
        f"Average developer retries: {_fmt(s['average_developer_retries'])}",
        f"Test pass rate:            {_fmt(s['test_pass_rate'], 'pct')}",
        f"Average Claude cost:       {_fmt(s['average_cost_usd'], 'usd')}"
        + (f"  ({s['average_cost_usd']['runs_with_partial_cost']} run(s) had calls with no cost reported)"
           if s["average_cost_usd"]["runs_with_partial_cost"] else ""),
        f"Average Devin ACUs:        {_fmt(s['average_devin_acus'])}",
    ]
    if s["median_stage_seconds"]:
        lines.append("Median time per stage:")
        for name, e in s["median_stage_seconds"].items():
            lines.append(f"  {name:<14} {_fmt(e, 'sec')}")
    if skipped:
        lines.append(f"Skipped {len(skipped)} invalid file(s):")
        lines += [f"  {path}: {why}" for path, why in skipped[:10]]
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="*", help="folders or .json files (default: metrics/runs)")
    ap.add_argument("--kind", choices=["run", "fix"], help="only this kind of run")
    ap.add_argument("--json", action="store_true", help="print machine-readable JSON")
    a = ap.parse_args(argv)
    paths = a.paths or [HERE / "runs"]
    records, skipped = load_records(paths)
    summary = summarize(records, a.kind)
    if a.json:
        print(json.dumps({"summary": summary, "skipped": [{"file": f, "reason": w} for f, w in skipped]}, indent=2))
    else:
        print(render(summary, skipped) if records or skipped else "No run records found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
