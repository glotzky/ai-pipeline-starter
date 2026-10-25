#!/usr/bin/env bash
# Create the GitHub environment, restrict it to one branch, store the three secrets,
# and enable the Actions permissions the pipeline needs. Requires the GitHub CLI (gh), logged in.
# UNTESTED CONVENIENCE SCRIPT: docs/03-setup-guide.md describes the same steps by hand.
# Usage: ./install/set-secrets.sh OWNER/REPO [ENVIRONMENT_NAME] [BRANCH]
set -euo pipefail

repo="${1:?Usage: $0 OWNER/REPO [ENVIRONMENT_NAME] [BRANCH]}"
envname="${2:-pipeline}"
branch="${3:-main}"

command -v gh >/dev/null || { echo "Install the GitHub CLI (https://cli.github.com), then run: gh auth login"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "Run: gh auth login"; exit 1; }

echo "Creating environment '$envname' on $repo, limited to branch '$branch'..."
gh api -X PUT "repos/$repo/environments/$envname" \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true' >/dev/null
gh api -X POST "repos/$repo/environments/$envname/deployment-branch-policies" \
  -f name="$branch" -f type=branch >/dev/null 2>&1 || echo "  (branch rule may already exist; check Settings > Environments)"

put_secret() {
  local name="$1" value
  read -r -s -p "$name (input hidden): " value; echo
  [ -n "$value" ] || { echo "Empty value; aborting."; exit 1; }
  printf '%s' "$value" | gh secret set "$name" --env "$envname" --repo "$repo" >/dev/null
  echo "  stored $name"
}
put_secret ANTHROPIC_API_KEY
put_secret DEVIN_API_KEY
put_secret DEVIN_ORG_ID

echo "Enabling Actions read/write permissions and PR creation by Actions..."
gh api -X PUT "repos/$repo/actions/permissions/workflow" \
  -f default_workflow_permissions=write -F can_approve_pull_request_reviews=true >/dev/null \
  || echo "  Could not set this automatically. Do it by hand: Settings > Actions > General > Workflow permissions."

echo "Done. Verify at: https://github.com/$repo/settings/environments"
