#!/usr/bin/env bash
# Copy the pipeline template into a git repository (macOS, Linux, WSL, Git Bash).
# Usage: ./install/install.sh /path/to/your/repo [--env ENVIRONMENT_NAME]
set -euo pipefail

usage() { echo "Usage: $0 /path/to/your/repo [--env ENVIRONMENT_NAME]"; }

here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tpl="$here/template"
target=""
envname="pipeline"

while [ $# -gt 0 ]; do
  case "$1" in
    --env) envname="${2:?--env needs a value}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) target="$1"; shift ;;
  esac
done
[ -n "$target" ] || { usage; exit 1; }
target="$(cd "$target" && pwd)"

[ -d "$target/.git" ] || { echo "error: $target is not the root of a git repository (no .git folder)."; exit 1; }
command -v git >/dev/null || { echo "error: git is not installed."; exit 1; }

if [ -n "$(git -C "$target" status --porcelain)" ]; then
  echo "warning: $target has uncommitted changes. Consider committing or stashing first."
fi

echo "Installing pipeline template into: $target"
echo "GitHub environment name used in workflows: $envname"
echo

# Files that must never be overwritten if they already exist (we write <name>.pipeline-new instead).
keep_existing() { case "$1" in ./CLAUDE.md|./PIPELINE.md|./.gitattributes|./.github/CODEOWNERS|./.github/dependabot.yml|./.github/PULL_REQUEST_TEMPLATE.md) return 0 ;; *) return 1 ;; esac; }

# GitHub username from the origin remote (used to fill in CODEOWNERS).
owner="$(git -C "$target" remote get-url origin 2>/dev/null | sed -E 's#.*github\.com[:/]([^/]+)/.*#\1#' || true)"
case "$owner" in */*|*:*|'') owner="" ;; esac

(cd "$tpl" && find . -type f ! -name '.gitignore.pipeline' | sort) | while IFS= read -r rel; do
  src="$tpl/$rel"; dst="$target/$rel"
  mkdir -p "$(dirname "$dst")"
  if keep_existing "$rel" && [ -e "$dst" ]; then
    cp "$src" "$dst.pipeline-new"
    echo "  kept existing  $rel   (wrote $rel.pipeline-new for you to merge by hand)"
    continue
  fi
  case "$rel" in
    *.yml) sed "s/environment: pipeline/environment: $envname/" "$src" > "$dst" ;;
    ./.github/CODEOWNERS) if [ -n "$owner" ]; then sed "s/@OWNER/@$owner/g" "$src" > "$dst"; else cp "$src" "$dst"; fi ;;
    *)     cp "$src" "$dst" ;;
  esac
  echo "  wrote          $rel"
done

# Append missing lines to .gitignore (never removes anything).
touch "$target/.gitignore"
while IFS= read -r line; do
  case "$line" in ''|'#'*) continue ;; esac
  grep -qxF "$line" "$target/.gitignore" || echo "$line" >> "$target/.gitignore"
done < "$tpl/.gitignore.pipeline"
echo "  updated        .gitignore (appended missing lines)"

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
