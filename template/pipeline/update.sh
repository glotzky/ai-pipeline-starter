#!/usr/bin/env bash
# Update this project's AI pipeline from the ai-pipeline-starter GitHub repository.
# Run from anywhere inside the project:   bash pipeline/update.sh            (latest tagged version)
#                                         bash pipeline/update.sh v1.2.0     (a specific tag)
# It downloads that version into a temporary folder and runs its installer with --upgrade, so files you edited are
# kept and the new versions arrive as <file>.pipeline-new. Nothing is committed or pushed; you review with git status.
# Only run this against a starter repository you trust: it runs that repository's install script.
# How to develop this file: see docs/15-updating.md in the starter. Test overrides: PIPELINE_TARBALL, PIPELINE_LATEST.
set -euo pipefail

root="$(git rev-parse --show-toplevel)"
manifest="$root/.pipeline-version"
[ -f "$manifest" ] || { echo "error: $manifest not found. Run the starter's install.sh once first (see docs/15-updating.md)."; exit 1; }
src="$(sed -n 's/^source=//p' "$manifest" | head -n1)"
cur="$(sed -n 's/^version=//p' "$manifest" | head -n1)"
case "$src" in */*) ;; *) echo "error: no source repository recorded in $manifest"; exit 1 ;; esac

want="${1:-}"
if [ -z "$want" ]; then
  want="${PIPELINE_LATEST:-}"
  if [ -z "$want" ]; then
    want="$(curl -fsSL "https://api.github.com/repos/$src/tags?per_page=100" | grep -o '"name": *"[^"]*"' | sed 's/.*: *"//; s/"$//' \
      | sed 's/^v//' | grep -E '^[0-9]+(\.[0-9]+)*$' | sort -V | tail -n1 || true)"
  fi
  [ -n "$want" ] || { echo "error: could not find a version tag in https://github.com/$src (is it public and tagged?)."; exit 1; }
  if [ "$(printf '%s\n%s\n' "$cur" "$want" | sort -V | tail -n1)" = "$cur" ]; then
    echo "Already up to date (version $cur)."; exit 0
  fi
fi
tag="v${want#v}"

work="$(mktemp -d)"; trap 'rm -rf "$work"' EXIT
if [ -n "${PIPELINE_TARBALL:-}" ]; then cp "$PIPELINE_TARBALL" "$work/s.tgz"
else curl -fsSL "https://codeload.github.com/$src/tar.gz/refs/tags/$tag" -o "$work/s.tgz"; fi
mkdir "$work/x" && tar -xzf "$work/s.tgz" -C "$work/x"
inst="$(find "$work/x" -maxdepth 3 -path '*/install/install.sh' | head -n1)"
[ -n "$inst" ] || { echo "error: the download does not contain install/install.sh"; exit 1; }

echo "Updating from $src $tag (you have $cur)"
bash "$inst" "$root" --upgrade
