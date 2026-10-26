#!/usr/bin/env bash
# Update this project's AI pipeline from the ai-pipeline-starter GitHub repository, as a pull request.
#
#   bash pipeline/update.sh            create a branch, apply the newest tagged version, push, open a pull request
#   bash pipeline/update.sh v1.2.0     the same, for a specific tag
#   bash pipeline/update.sh --check    change nothing; report whether this project matches the starter (exit 1 if not)
#   bash pipeline/update.sh --local    apply to your working folder only: no branch, no commit, no push, no PR
#
# It downloads that version into a temporary folder and runs its installer with --upgrade, so files you edited are
# kept (the new version is saved as <file>.pipeline-new for you to merge by hand; those copies are NOT in the PR).
# It never merges anything: you review and merge the pull request yourself.
# Needs: git, curl, tar, and the GitHub CLI (gh) to open the PR (without gh it pushes the branch and tells you).
# Only run this against a starter repository you trust: it runs that repository's install script.
# How to develop this file: see docs/15-updating.md in the starter. Test overrides: PIPELINE_TARBALL, PIPELINE_LATEST.
set -euo pipefail

mode=pr; want=""
for a in "$@"; do
  case "$a" in
    --local) mode=local ;;
    --check) mode=check ;;
    -h|--help) sed -n '2,13p' "$0"; exit 0 ;;
    v[0-9]*|[0-9]*) want="$a" ;;
    *) echo "error: unknown option '$a' (see: bash pipeline/update.sh --help)"; exit 2 ;;
  esac
done

root="$(git rev-parse --show-toplevel)"
manifest="$root/.pipeline-version"
[ -f "$manifest" ] || { echo "error: $manifest not found. Run the starter's install.sh once first (see docs/15-updating.md)."; exit 1; }
src="$(sed -n 's/^source=//p' "$manifest" | head -n1)"
cur="$(sed -n 's/^version=//p' "$manifest" | head -n1)"
case "$src" in */*) ;; *) echo "error: no source repository recorded in $manifest"; exit 1 ;; esac

auto=0
if [ -z "$want" ]; then
  auto=1
  want="${PIPELINE_LATEST:-}"
  if [ -z "$want" ]; then
    want="$(curl -fsSL "https://api.github.com/repos/$src/tags?per_page=100" | grep -o '"name": *"[^"]*"' | sed 's/.*: *"//; s/"$//' \
      | sed 's/^v//' | grep -E '^[0-9]+(\.[0-9]+)*$' | sort -V | tail -n1 || true)"
  fi
  [ -n "$want" ] || { echo "error: could not find a version tag in https://github.com/$src (is it public and tagged?)."; exit 1; }
fi
tag="v${want#v}"
newest="$(printf '%s\n%s\n' "$cur" "${want#v}" | sort -V | tail -n1)"

if [ "$auto" = 1 ] && [ "$mode" != check ] && [ "$newest" = "$cur" ]; then
  echo "Already up to date (version $cur)."; exit 0
fi

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
if [ -n "${PIPELINE_TARBALL:-}" ]; then cp "$PIPELINE_TARBALL" "$work/s.tgz"
else curl -fsSL "https://codeload.github.com/$src/tar.gz/refs/tags/$tag" -o "$work/s.tgz"; fi
mkdir "$work/x" && tar -xzf "$work/s.tgz" -C "$work/x"
inst="$(find "$work/x" -maxdepth 3 -path '*/install/install.sh' | head -n1)"
[ -n "$inst" ] || { echo "error: the download does not contain install/install.sh"; exit 1; }

# --------------------------------------------------------------------------- check: change nothing
if [ "$mode" = check ]; then
  git clone -q --local --no-hardlinks "$root" "$work/proj"
  url="$(git -C "$root" remote get-url origin 2>/dev/null || true)"
  [ -z "$url" ] || git -C "$work/proj" remote set-url origin "$url"
  echo "Checking $root (committed files, version $cur) against $src $tag"
  PIPELINE_QUIET_NEXT=1 bash "$inst" "$work/proj" --upgrade > "$work/out.txt" 2>&1 || { cat "$work/out.txt"; exit 1; }
  diffs="$(grep -E '^  (new|updated|you edited|no longer shipped) ' "$work/out.txt" || true)"
  if [ "${cur}" != "${want#v}" ]; then echo "  version: this project has $cur, the starter has ${want#v}"; fi
  if [ -n "$diffs" ]; then echo "$diffs"; fi
  if [ "${cur}" = "${want#v}" ] && [ -z "$diffs" ]; then echo "In sync with the starter ($tag)."; exit 0; fi
  echo "Not in sync. Run: bash pipeline/update.sh"
  exit 1
fi

# --------------------------------------------------------------------------- local: working folder only
if [ "$mode" = local ]; then
  echo "Updating from $src $tag (you have $cur), working folder only"
  bash "$inst" "$root" --upgrade
  exit 0
fi

# --------------------------------------------------------------------------- pr: branch, commit, push, pull request
if [ -n "$(git -C "$root" status --porcelain --untracked-files=no)" ]; then
  echo "error: you have uncommitted changes. Commit or stash them first, so the update PR holds only the update."
  exit 1
fi
start="$(git -C "$root" rev-parse --abbrev-ref HEAD)"
base="$(git -C "$root" symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's#^origin/##' || true)"
[ -n "$base" ] || base="$start"
branch="pipeline-update/$tag"
if git -C "$root" rev-parse --verify -q "$branch" >/dev/null || git -C "$root" ls-remote --exit-code --heads origin "$branch" >/dev/null 2>&1; then
  echo "error: branch $branch already exists. Merge or delete it first (git branch -D $branch; git push origin --delete $branch)."
  exit 1
fi

echo "Updating from $src $tag (you have $cur) on a new branch: $branch"
git -C "$root" checkout -q -b "$branch"
back() { git -C "$root" checkout -q -f "$start" 2>/dev/null || true; git -C "$root" branch -D "$branch" >/dev/null 2>&1 || true; }
if ! PIPELINE_QUIET_NEXT=1 bash "$inst" "$root" --upgrade | tee "$work/out.txt"; then back; echo "error: the upgrade failed; nothing was committed."; exit 1; fi

git -C "$root" add -A -- . ':(exclude)*.pipeline-new'
if git -C "$root" diff --cached --quiet; then
  back; echo "Nothing to change: this project already matches $tag."; exit 0
fi
git -C "$root" commit -q -m "Update AI pipeline to $tag" -m "From $src, previously $cur."

mine="$(cd "$root" && git ls-files --others --exclude-standard | grep '\.pipeline-new$' || true)"
{
  echo "Updates the AI pipeline from **$cur** to **${tag#v}** (source: https://github.com/$src, see its CHANGELOG.md)."
  echo
  echo '```'
  grep -E '^  (new|updated|kept yours|you edited|no longer shipped) ' "$work/out.txt" || echo "(no file changes listed)"
  echo '```'
  echo
  echo "Files you never edited were replaced. Files you edited were left as they are."
  if [ -n "$mine" ]; then
    echo
    echo "New versions of files you own were saved on the machine that ran the update, not in this PR. Compare and merge by hand, then delete them:"
    echo
    printf '%s\n' "$mine" | sed 's/^/- `/; s/$/`/'
  fi
  echo
  echo "Before merging: read the diff. Workflows only run from the default branch, so nothing takes effect until you merge. After merging: Actions -> Health check -> Run workflow."
} > "$work/body.md"

git -C "$root" push -q -u origin "$branch"
if command -v gh >/dev/null 2>&1; then
  (cd "$root" && gh pr create --base "$base" --head "$branch" --title "Update AI pipeline to $tag" --body-file "$work/body.md")
else
  echo "The GitHub CLI (gh) is not installed, so no pull request was opened. The branch is pushed: open a pull request from $branch into $base on GitHub."
fi
git -C "$root" checkout -q "$start"
echo "Done. Review and merge the pull request yourself; nothing was merged. You are back on $start."
