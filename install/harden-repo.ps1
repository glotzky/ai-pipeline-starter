# Harden a GitHub repo for the pipeline (Windows PowerShell). Same steps as harden-repo.sh.
# UNTESTED against live GitHub. Needs the GitHub CLI (gh), logged in, with admin rights.
# Usage: .\install\harden-repo.ps1 -Repo OWNER/REPO [-RequireCi] [-Branch main]
param(
  [Parameter(Mandatory = $true)][string]$Repo,
  [switch]$RequireCi,
  [string]$Branch = ""
)
$ErrorActionPreference = "Continue"
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { Write-Host "Install the GitHub CLI (https://cli.github.com), then run: gh auth login"; exit 1 }
gh auth status *> $null
if ($LASTEXITCODE -ne 0) { Write-Host "Run: gh auth login"; exit 1 }
if (-not $Branch) { $Branch = gh api "repos/$Repo" --jq .default_branch }

function Step($label, [scriptblock]$cmd) {
  $out = & $cmd 2>&1
  if ($LASTEXITCODE -eq 0) { Write-Host "  ok      $label" }
  else { Write-Host "  FAILED  $label  ($(($out | Out-String).Trim().Substring(0, [Math]::Min(160, ($out | Out-String).Trim().Length))))" }
}

Write-Host "Hardening $Repo (branch: $Branch)"
Step "delete branches automatically after merge" { gh api -X PATCH "repos/$Repo" -F delete_branch_on_merge=true }
Step "secret scanning and push protection" { gh api -X PATCH "repos/$Repo" -F "security_and_analysis[secret_scanning][status]=enabled" -F "security_and_analysis[secret_scanning_push_protection][status]=enabled" }
Step "Dependabot alerts" { gh api -X PUT "repos/$Repo/vulnerability-alerts" }
Step "Dependabot security updates" { gh api -X PUT "repos/$Repo/automated-security-fixes" }
Step "CodeQL default setup (code scanning)" { gh api -X PATCH "repos/$Repo/code-scanning/default-setup" -f state=configured -f query_suite=default }

$checks = if ($RequireCi) { '{"strict":false,"contexts":["ci"]}' } else { 'null' }
$body = @"
{
  "required_status_checks": $checks,
  "enforce_admins": false,
  "required_pull_request_reviews": {"required_approving_review_count": 0},
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false
}
"@
Step "protect $Branch (pull request required, no force push)" { $body | gh api -X PUT "repos/$Repo/branches/$Branch/protection" --input - }
Write-Host ""
Write-Host "Done. Check Settings -> Branches and Settings -> Code security on GitHub to confirm what applied."
Write-Host "FAILED with 403/404 on a private repo usually means the feature needs a paid GitHub plan."
