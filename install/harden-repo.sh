#!/usr/bin/env bash
# Harden a GitHub repo for the pipeline: protect the default branch, delete merged branches,
# turn on secret scanning and Dependabot alerts, and enable CodeQL code scanning.
# Needs the GitHub CLI (gh), logged in, with admin rights on the repo.
# UNTESTED against live GitHub: each step reports success or failure and the script continues.
# Some features need a paid plan for PRIVATE repos (branch protection, secret scanning, CodeQL).
# Usage: ./install/harden-repo.sh OWNER/REPO [--require-ci] [--branch main]
set -uo pipefail

repo="${1:?Usage: $0 OWNER/REPO [--require-ci] [--branch main]}"; shift
require_ci=0; branch=""
while [ $# -gt 0 ]; do
  case "$1" in
    --require-ci) require_ci=1; shift ;;
    --branch) branch="${2:?--branch needs a value}"; shift 2 ;;
    *) echo "unknown option: $1"; exit 1 ;;
  esac
done

command -v gh >/dev/null || { echo "Install the GitHub CLI (https://cli.github.com), then run: gh auth login"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Run: gh auth login"; exit 1; }
[ -n "$branch" ] || branch="$(gh api "repos/$repo" --jq .default_branch)"

step() { # step "label" command...
  local label="$1"; shift
  if "$@" >/dev/null 2>/tmp/harden.err; then echo "  ok      $label"
  else echo "  FAILED  $label  ($(head -c 160 /tmp/harden.err | tr '\n' ' '))"; fi
}

echo "Hardening $repo (branch: $branch)"

step "delete branches automatically after merge" \
  gh api -X PATCH "repos/$repo" -F delete_branch_on_merge=true

step "secret scanning and push protection" \
  gh api -X PATCH "repos/$repo" \
    -F 'security_and_analysis[secret_scanning][status]=enabled' \
    -F 'security_and_analysis[secret_scanning_push_protection][status]=enabled'

step "Dependabot alerts" gh api -X PUT "repos/$repo/vulnerability-alerts"
step "Dependabot security updates" gh api -X PUT "repos/$repo/automated-security-fixes"

step "CodeQL default setup (code scanning)" \
  gh api -X PATCH "repos/$repo/code-scanning/default-setup" -f state=configured -f query_suite=default

# Branch protection: changes must come through a pull request; no force pushes or deletion.
# Required approvals stay at 0 so you can merge your own pull requests (you are the owner and sole reviewer).
if [ "$require_ci" = 1 ]; then
  checks='{"strict":false,"contexts":["ci"]}'
else
  checks='null'
fi
body=$(cat <<JSON
{
  "required_status_checks": $checks,
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 0},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
JSON
)
step "protect $branch (pull request required, no force push)" \
  bash -c "printf '%s' '$body' | gh api -X PUT 'repos/$repo/branches/$branch/protection' --input -"

cat <<NEXT

Done. Check Settings -> Branches and Settings -> Code security on GitHub to confirm what applied.
- "FAILED" with a 403/404 on a private repo usually means that feature needs a paid GitHub plan.
- --require-ci makes the check named "ci" mandatory. The pipeline starts CI for its own pull requests;
  if a pipeline PR ever shows the check as "Expected" and stuck, run Actions -> CI -> Run workflow on that branch.
NEXT
