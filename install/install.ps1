# Copy the pipeline template into a git repository (Windows PowerShell 5.1+ or PowerShell 7).
# Usage: .\install\install.ps1 -Target C:\path\to\your\repo [-EnvName pipeline]
param(
  [Parameter(Mandatory = $true)][string]$Target,
  [string]$EnvName = "pipeline"
)
$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $PSScriptRoot
$tpl  = Join-Path $here "template"
$Target = (Resolve-Path $Target).Path

if (-not (Test-Path (Join-Path $Target ".git"))) { throw "$Target is not the root of a git repository (no .git folder)." }
if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw "git is not installed." }

$dirty = git -C $Target status --porcelain
if ($dirty) { Write-Warning "$Target has uncommitted changes. Consider committing or stashing first." }

Write-Host "Installing pipeline template into: $Target"
Write-Host "GitHub environment name used in workflows: $EnvName"
Write-Host ""

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$keep = @("CLAUDE.md", "PIPELINE.md", ".gitattributes", ".github\CODEOWNERS", ".github\dependabot.yml", ".github\PULL_REQUEST_TEMPLATE.md")
$owner = ""
try {
  $remote = git -C $Target remote get-url origin 2>$null
  if ($remote -match "github\.com[:/]([^/]+)/") { $owner = $Matches[1] }
} catch { }

Get-ChildItem -Path $tpl -Recurse -File -Force | Where-Object { $_.Name -ne ".gitignore.pipeline" -and $_.Name -ne ".DS_Store" -and $_.Extension -ne ".pyc" -and $_.FullName -notmatch "__pycache__" } | ForEach-Object {
  $rel = $_.FullName.Substring($tpl.Length + 1)
  $dst = Join-Path $Target $rel
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dst) | Out-Null

  if (($keep -contains $rel) -and (Test-Path $dst)) {
    Copy-Item $_.FullName "$dst.pipeline-new" -Force
    Write-Host "  kept existing  $rel   (wrote $rel.pipeline-new for you to merge by hand)"
    return
  }
  if ($rel -eq ".github\CODEOWNERS" -and $owner) {
    $text = [System.IO.File]::ReadAllText($_.FullName) -replace "@OWNER", "@$owner"
    [System.IO.File]::WriteAllText($dst, $text, $utf8NoBom)
  } elseif ($_.Extension -eq ".yml") {
    $text = [System.IO.File]::ReadAllText($_.FullName) -replace "environment: pipeline", "environment: $EnvName"
    [System.IO.File]::WriteAllText($dst, $text, $utf8NoBom)
  } else {
    Copy-Item $_.FullName $dst -Force
  }
  Write-Host "  wrote          $rel"
}

# Append missing lines to .gitignore (never removes anything).
$gi = Join-Path $Target ".gitignore"
if (-not (Test-Path $gi)) { New-Item -ItemType File -Path $gi | Out-Null }
$existing = Get-Content $gi
foreach ($line in Get-Content (Join-Path $tpl ".gitignore.pipeline")) {
  if ($line -eq "" -or $line.StartsWith("#")) { continue }
  if ($existing -notcontains $line) { Add-Content -Path $gi -Value $line }
}
Write-Host "  updated        .gitignore (appended missing lines)"

Write-Host @"

Done. Next steps:
  1. Edit CLAUDE.md (or merge CLAUDE.md.pipeline-new into yours): fill in every TODO.
  2. cd "$Target"
     git checkout -b pipeline-setup
     git add -A; git status        # confirm .github\ and .claude\ are listed
     git commit -m "Add AI build pipeline"
     git push -u origin pipeline-setup
  3. Open a pull request and merge it into your default branch (workflows only run from there).
  4. Set up the GitHub environment and secrets: .\install\set-secrets.ps1 -Repo OWNER/REPO -EnvName $EnvName
     (or follow docs\03-setup-guide.md, section "Environment and secrets").
  5. Actions -> Health check -> Run workflow (tick the Devin session box once).
"@
