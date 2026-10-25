# Create the GitHub environment, restrict it to one branch, store the three secrets,
# and enable the Actions permissions the pipeline needs. Requires the GitHub CLI (gh), logged in.
# UNTESTED CONVENIENCE SCRIPT: docs\03-setup-guide.md describes the same steps by hand.
# Usage: .\install\set-secrets.ps1 -Repo OWNER/REPO [-EnvName pipeline] [-Branch main]
param(
  [Parameter(Mandatory = $true)][string]$Repo,
  [string]$EnvName = "pipeline",
  [string]$Branch = "main"
)
$ErrorActionPreference = "Stop"

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) { throw "Install the GitHub CLI (https://cli.github.com), then run: gh auth login" }
gh auth status *> $null
if ($LASTEXITCODE -ne 0) { throw "Run: gh auth login" }

Write-Host "Creating environment '$EnvName' on $Repo, limited to branch '$Branch'..."
$envBody = '{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}'
$envBody | gh api -X PUT "repos/$Repo/environments/$EnvName" --input - | Out-Null
$ruleBody = (@{ name = $Branch; type = "branch" } | ConvertTo-Json -Compress)
try { $ruleBody | gh api -X POST "repos/$Repo/environments/$EnvName/deployment-branch-policies" --input - | Out-Null }
catch { Write-Host "  (branch rule may already exist; check Settings > Environments)" }

function Set-PipelineSecret([string]$Name) {
  $sec = Read-Host "$Name (input hidden)" -AsSecureString
  $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
  try { $plain = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr) }
  finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) }
  if ([string]::IsNullOrEmpty($plain)) { throw "Empty value for $Name; aborting." }
  gh secret set $Name --env $EnvName --repo $Repo --body $plain | Out-Null
  Write-Host "  stored $Name"
}
Set-PipelineSecret "ANTHROPIC_API_KEY"
Set-PipelineSecret "DEVIN_API_KEY"
Set-PipelineSecret "DEVIN_ORG_ID"

Write-Host "Enabling Actions read/write permissions and PR creation by Actions..."
try {
  '{"default_workflow_permissions":"write","can_approve_pull_request_reviews":true}' |
    gh api -X PUT "repos/$Repo/actions/permissions/workflow" --input - | Out-Null
} catch { Write-Host "  Could not set this automatically. Do it by hand: Settings > Actions > General > Workflow permissions." }

Write-Host "Done. Verify at: https://github.com/$Repo/settings/environments"
