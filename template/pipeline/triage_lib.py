"""Triage: read the triage agent's answer, apply safe defaults, and turn it into a route, labels and an ACU budget.

Standard library only. Nothing here calls a model, so it is fully unit-tested. An answer that is missing or invalid
never lowers safety: the pipeline falls back to the full route and the run-wide ACU cap.
"""
import os
import re

KINDS = ("bug", "feature", "chore", "docs", "no-code")
SIZES = ("xs", "s", "m", "l")
ROUTES = ("full", "light", "stop")
SIZE_BUDGET = {"xs": 1, "s": 2, "m": 4, "l": 8}
DEFAULT_MAX_ACU = 10
LABEL_COLORS = {"kind": "5319e7", "size": "fbca04", "route": "0e8a16"}


def max_acu(env=None):
    """The run-wide ACU cap (repository variable PIPELINE_MAX_ACU). Invalid or missing values give the default."""
    raw = (env if env is not None else os.environ).get("PIPELINE_MAX_ACU", "")
    return int(raw) if raw.strip().isdigit() and int(raw) > 0 else DEFAULT_MAX_ACU


def parse(text):
    """Read KEY: value lines from the top of triage.md. Unknown or invalid values become None."""
    found = {}
    for line in (text or "").splitlines()[:14]:
        m = re.match(r"^\s*([A-Z_]+):\s*(.*?)\s*$", line)
        if m and m.group(1) not in found:
            found[m.group(1)] = m.group(2)

    def pick(key, allowed):
        v = found.get(key, "").lower().strip("`* ")
        return v if v in allowed else None

    demo = found.get("NEEDS_DEMO", "").lower().strip("`* ")
    budget = re.match(r"^\d+", found.get("ACU_BUDGET", "").strip("`* "))
    out = {
        "kind": pick("KIND", KINDS), "size": pick("SIZE", SIZES), "route": pick("ROUTE", ROUTES),
        "needs_demo": True if demo == "yes" else (False if demo == "no" else None),
        "acu_budget": int(budget.group()) if budget and int(budget.group()) > 0 else None,
        "reason": found.get("REASON") or None,
    }
    out["parsed"] = any(out[k] is not None for k in ("kind", "size", "route", "acu_budget"))
    return out


def forced(idea):
    """The owner can say `FORCE: yes` on its own line of the brief to build even when triage says no-code."""
    return bool(re.search(r"^\s*FORCE:\s*yes\s*$", idea or "", re.I | re.M))


def decide(t, cap, force=False):
    """Turn a parsed answer into what the orchestrator does. `cap` is the run-wide ACU cap.

    route:       full | light | stop. stop is honoured only for KIND no-code, and never when forced.
    acu_budget:  what triage asked for (or the size default), capped; None when nothing usable was given.
    acu_limit:   the per-session limit sent to Devin: the budget, or the cap when there is no budget.
    """
    route = t.get("route") or "full"
    if route == "stop" and (t.get("kind") != "no-code" or force):
        route = "full"
    budget = t.get("acu_budget") or SIZE_BUDGET.get(t.get("size") or "")
    budget = min(budget, cap) if budget else None
    return {**t, "route": route, "acu_budget": budget, "acu_limit": budget or cap, "cap": cap,
            "needs_demo": bool(t.get("needs_demo"))}


def labels(t):
    """Issue labels for the values that were really parsed (never a guess)."""
    out = []
    for key in ("kind", "size", "route"):
        if t.get(key):
            out.append(f"{key}:{t[key]}")
    return out


def over_budget(total, budget):
    """True/False when both numbers are known, otherwise None (never guessed)."""
    if total is None or not budget:
        return None
    return total > budget


def acu_line(total, budget, cap):
    """One honest sentence about ACU use for the run summary."""
    if total is None:
        return "Devin did not report ACU usage for this run, so usage cannot be confirmed."
    if not budget:
        return f"{total:g} ACUs used (triage set no budget; run-wide cap {cap})."
    verdict = "within budget" if total <= budget else "**OVER budget**"
    return f"{total:g} ACUs used of a {budget} ACU budget: {verdict} (run-wide cap {cap})."
