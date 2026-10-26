# Updating your projects when the pipeline improves

**Author:** Gil Lotzky · Applies to every project installed with `install/install.sh` (macOS, Linux, WSL, Git Bash).

You improve the starter once and tag a version. Each project then pulls that version **as a pull request**, which you read and merge yourself. Nothing updates on its own, so a change to the starter can never break a project you did not touch.

## The one command

Run inside the project, from a clean checkout (no uncommitted changes):

```
bash pipeline/update.sh
```

It does this, in order:

1. Finds the newest version tag of the starter (from `.pipeline-version`, which records where the project came from). If you are already on it, it says so and stops.
2. Downloads that version into a temporary folder.
3. Creates the branch `pipeline-update/vX.Y.Z`, applies the update, commits it, pushes it, and opens a pull request into your default branch.
4. Returns you to the branch you started on. **It never merges.**

Then you open the PR, read the diff, merge it, and run **Actions → Health check**. Workflows only run from the default branch, so nothing takes effect until you merge.

Variants:

| Command | What it does |
|---|---|
| `bash pipeline/update.sh v1.2.0` | The same, for a specific version |
| `bash pipeline/update.sh --check` | Changes nothing; says whether the project matches the starter; exit code 1 if not |
| `bash pipeline/update.sh --local` | Applies to your working folder only: no branch, no commit, no PR |

Needs `git`, `curl`, `tar` and the GitHub CLI `gh` (logged in with `gh auth login`). Without `gh` it still pushes the branch and tells you to open the PR on GitHub.

## What the update changes

| Situation | What happens |
|---|---|
| File is new in the starter | Added |
| You never edited the file | Replaced with the new version. Your GitHub environment name and the GitHub Action versions you already use (for example Dependabot bumps) are kept |
| You edited the file | Yours is kept. The new version is saved next to it as `<file>.pipeline-new` on the machine that ran the update; these copies are **not** in the PR, and the PR lists them so you can merge by hand and delete them |
| `CLAUDE.md`, `PIPELINE.md`, `CODEOWNERS`, `dependabot.yml`, PR template, `.gitattributes` | Always yours; a `.pipeline-new` copy appears only if the starter's version differs |
| File was removed from the starter | Listed in the PR; never deleted |

## Confirm a project is in sync with the starter

```
bash pipeline/update.sh --check
```

It compares what is **committed** on your current branch with the newest tagged starter and prints either `In sync with the starter (vX.Y.Z)` or the differences: a different version, files that would be updated or added, and files you edited. Use it after merging an update PR. Customised files (for example `CLAUDE.md`) are yours and are not counted.

## Be told when an update exists

The **Update check** workflow runs every Monday, compares `.pipeline-version` with the newest tag in the starter, and opens one issue ("Pipeline update available: x.y.z") if there is a newer one. It changes no files. It needs the starter repository to be public and to have version tags.

## Publish an update (maintainer steps)

1. In the starter: change what you need, bump `VERSION`, add a `CHANGELOG.md` entry, run `python3 -m unittest discover -s tests` (must end `OK`), commit and push.
2. Tag it: `git tag v1.3.0 && git push --tags`. Projects only see tagged versions, not `main`.
3. In each project: `bash pipeline/update.sh`, merge the PR, run Health check, then `bash pipeline/update.sh --check`.

## Projects that do not have `pipeline/update.sh` yet

- **Installed before v1.1.0** (no `.pipeline-version`): clone the starter and run `./install/install.sh /path/to/project --env YOUR_ENV_NAME` once, on a new branch, then commit and open a PR by hand.
- **Has the v1.1.x script** (applies locally only): run `bash pipeline/update.sh` on a new branch named `pipeline-update/vX.Y.Z`, then commit, push and open the PR by hand. After that merge the project has the PR-opening version.

## Limits

- Bash only (Git Bash or WSL on Windows). The PowerShell installer does first installs only.
- A fork of the starter updates from the fork's tags. Only point a project at a starter repository you trust: the update runs that repository's installer.
- `--check` looks at committed files, so commit or merge before running it.
- Tested with stubs and a local bare repository for the branch, push and PR steps; run against real GitHub once so far: the download from a tag. See the verification table in the README.
