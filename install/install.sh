#!/usr/bin/env bash
# Copy the pipeline template into a git repository (macOS, Linux, WSL, Git Bash).
# Usage: ./install/install.sh /path/to/your/repo [--env ENVIRONMENT_NAME]
set -euo pipefail

usage() { echo "Usage: $0 /path/to/your/repo [--env ENVIRONMENT_NAME] [--upgrade]"; }

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tpl="$here/template"
version="$(tr -d '[:space:]' < "$here/VERSION" 2>/dev/null || echo unknown)"
target=""
envname=""
upgrade=0

while [ $# -gt 0 ]; do
  case "$1" in
    --env) envname="${2:?--env needs a value}"; shift 2 ;;
    --upgrade) upgrade=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) target="$1"; shift ;;
  esac
done
[ -n "$target" ] || { usage; exit 1; }
target="$(cd "$target" && pwd)"

[ -d "$target/.git" ] || { echo "error: $target is not the root of a git repository (no .git folder)."; exit 1; }
command -v git >/dev/null || { echo "error: git is not installed."; exit 1; }

# sha256 of a file, on macOS (shasum) or Linux (sha256sum).
sha() { if command -v sha256sum >/dev/null; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }

manifest="$target/.pipeline-version"
old_version=""
if [ -f "$manifest" ]; then
  old_version="$(sed -n 's/^version=//p' "$manifest" | head -n1)"
  [ -n "$envname" ] || envname="$(sed -n 's/^env=//p' "$manifest" | head -n1)"
fi
if [ "$upgrade" = 1 ] && [ ! -f "$manifest" ]; then
  echo "error: $manifest not found. This repository was installed before upgrades existed."
  echo "       Run the normal install once (without --upgrade) to create it; your edited files are kept as .pipeline-new copies."
  exit 1
fi
[ -n "$envname" ] || envname="pipeline"

if [ -n "$(git -C "$target" status --porcelain)" ]; then
  echo "warning: $target has uncommitted changes. Consider committing or stashing first."
fi

if [ "$upgrade" = 1 ]; then echo "Upgrading pipeline in: $target   (${old_version:-unknown} -> $version)"; else echo "Installing pipeline template into: $target"; fi
echo "GitHub environment name used in workflows: $envname"
echo

# Files that are yours once they exist (never overwritten; we write <name>.pipeline-new instead).
keep_existing() { case "$1" in ./CLAUDE.md|./PIPELINE.md|./.gitattributes|./.github/CODEOWNERS|./.github/dependabot.yml|./.github/PULL_REQUEST_TEMPLATE.md) return 0 ;; *) return 1 ;; esac; }

# GitHub username from the origin remote (used to fill in CODEOWNERS).
owner="$(git -C "$target" remote get-url origin 2>/dev/null | sed -E 's#.*github\.com[:/]([^/]+)/.*#\1#' || true)"
case "$owner" in */*|*:*|'') owner="" ;; esac

# Where upgrades are checked against (this starter's own GitHub repo, so forks follow the fork).
source_repo="$(git -C "$here" remote get-url origin 2>/dev/null | sed -E 's#.*github\.com[:/]([^/]+/[^/.]+)(\.git)?$#\1#' || true)"
case "$source_repo" in */*) ;; *) source_repo="glotzky/ai-pipeline-starter" ;; esac
case "$source_repo" in *:*|*' '*) source_repo="glotzky/ai-pipeline-starter" ;; esac

new_manifest="$(mktemp)"; trap 'rm -f "$new_manifest"' EXIT
tmp="$(mktemp)"; trap 'rm -f "$new_manifest" "$tmp"' EXIT
n_new=0; n_upd=0; n_same=0; n_conf=0

render() { # render <rel> -> $tmp (the file exactly as it would be installed)
  case "$1" in
    *.yml) sed "s/environment: pipeline/environment: $envname/" "$tpl/$1" > "$tmp" ;;
    ./.github/CODEOWNERS) if [ -n "$owner" ]; then sed "s/@OWNER/@$owner/g" "$tpl/$1" > "$tmp"; else cp "$tpl/$1" "$tmp"; fi ;;
    *) cp "$tpl/$1" "$tmp" ;;
  esac
}
recorded_hash() { awk -v p="$1" '$2==p {print $1}' "$manifest" 2>/dev/null | head -n1; }

files="$(cd "$tpl" && find . -type f ! -name '.gitignore.pipeline' ! -name '*.pyc' ! -path '*/__pycache__/*' ! -name '.DS_Store' | sort)"
while IFS= read -r rel; do
  dst="$target/$rel"
  mkdir -p "$(dirname "$dst")"
  render "$rel"
  if [ ! -e "$dst" ]; then
    cp "$tmp" "$dst"; echo "  new            $rel"; n_new=$((n_new+1))
    keep_existing "$rel" || echo "$(sha "$dst") $rel" >> "$new_manifest"
    continue
  fi
  if cmp -s "$tmp" "$dst"; then
    n_same=$((n_same+1))
    keep_existing "$rel" || echo "$(sha "$dst") $rel" >> "$new_manifest"
    continue
  fi
  if keep_existing "$rel"; then
    cp "$tmp" "$dst.pipeline-new"
    echo "  kept yours     $rel   (wrote $rel.pipeline-new to compare and merge by hand)"; n_conf=$((n_conf+1))
    continue
  fi
  recorded="$(recorded_hash "$rel")"
  if [ "$upgrade" = 1 ] && [ -n "$recorded" ] && [ "$recorded" != "$(sha "$dst")" ]; then
    cp "$tmp" "$dst.pipeline-new"
    echo "  you edited     $rel   (kept yours; wrote $rel.pipeline-new to compare and merge by hand)"; n_conf=$((n_conf+1))
    echo "$recorded $rel" >> "$new_manifest"   # keep the old baseline so it stays flagged until you merge
    continue
  fi
  cp "$tmp" "$dst"; echo "  updated        $rel"; n_upd=$((n_upd+1))
  echo "$(sha "$dst") $rel" >> "$new_manifest"
done <<< "$files"

# Files the old version installed that this version no longer ships (reported, never deleted).
if [ -f "$manifest" ]; then
  awk 'NF==2 && $1 ~ /^[0-9a-f]{64}$/ {print $2}' "$manifest" | while IFS= read -r rel; do
    grep -qxF "$rel" <<< "$files" || echo "  no longer shipped  $rel   (delete it yourself if you do not use it)"
  done
fi

{
  echo "# Written by ai-pipeline-starter. Do not edit. Used by: install/install.sh --upgrade"
  echo "version=$version"
  echo "env=$envname"
  echo "source=$source_repo"
  sort -k2 "$new_manifest"
} > "$manifest"
echo "  recorded       .pipeline-version ($version)"
echo
echo "Summary: $n_new new, $n_upd updated, $n_same already current, $n_conf for you to merge by hand."

# Append missing lines to .gitignore (never removes anything).
touch "$target/.gitignore"
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  grep -qxF "$line" "$target/.gitignore" || echo "$line" >> "$target/.gitignore"
done < "$tpl/.gitignore.pipeline"
echo "  updated        .gitignore (appended missing lines)"

if [ "$upgrade" = 1 ]; then
  cat <<UP

Upgrade done. Next steps:
  1. For each *.pipeline-new file above: compare with your version, copy over what you want, then delete the .pipeline-new file.
  2. cd "$target" && git checkout -b pipeline-upgrade && git add -A && git status
  3. git commit -m "Upgrade AI pipeline to $version", push, open a PR and merge it (workflows only run from the default branch).
  4. Actions -> Health check -> Run workflow.
UP
  exit 0
fi

cat <<NEXT

Done. Next steps:
  1. Edit CLAUDE.md (or merge CLAUDE.md.pipeline-new into yours): fill in every TODO.
  2. cd "$target"
     git checkout -b pipeline-setup
     git add -A && git status        # confirm .github/ and .claude/ are listed
     git commit -m "Add AI build pipeline"
     git push -u origin pipeline-setup
  3. Open a pull request and merge it into your default branch (workflows only run from there).
  4. Set up the GitHub environment and secrets: ./install/set-secrets.sh OWNER/REPO $envname
     (or follow docs/03-setup-guide.md, section "Environment and secrets").
  5. Actions -> Health check -> Run workflow (tick the Devin session box once).
  6. Harden the repo (branch protection, security scanning): ./install/harden-repo.sh OWNER/REPO
     If .github/dependabot.yml lists ecosystems you do not use, delete those blocks.
  7. Optional: .github/CODEOWNERS uses @$owner. Edit it if that is not you.
NEXT
