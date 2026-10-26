# Updating your projects when the pipeline improves

**Author:** Gil Lotzky · Applies to: every project that was installed with `install/install.sh` (macOS, Linux, WSL, Git Bash).

You improve the starter once; each project pulls the update when you choose. Nothing updates itself, so a change to the starter can never break a project you did not touch.

## How it works

- The installer writes `.pipeline-version` into each project (commit it). It records the starter version, your GitHub environment name, where the starter lives, and a fingerprint of every file it installed.
- `install.sh --upgrade` compares each file with that record:

| Situation | What the upgrade does |
|---|---|
| File is new in the starter | Adds it |
| You never edited the file | Replaces it with the new version (your environment name is kept) |
| You edited the file | Leaves yours, writes the new version beside it as `<file>.pipeline-new` |
| `CLAUDE.md`, `PIPELINE.md`, `CODEOWNERS`, `dependabot.yml`, PR template, `.gitattributes` | Always yours; the new version arrives as `.pipeline-new` only if it differs |
| File was removed from the starter | Reports it; never deletes anything |

## The one-command way (no clone of the starter needed)

Inside the project, on a new branch:

```
git checkout main && git pull && git checkout -b pipeline-upgrade
bash pipeline/update.sh            # newest tagged version; or: bash pipeline/update.sh v1.2.0
```

It reads the starter's GitHub address from `.pipeline-version`, downloads that tagged version to a temporary folder and runs its installer with `--upgrade`. Nothing is committed. Only point it at a starter repository you trust, because it runs that repository's installer.

## Do an update from a local clone (about 5 minutes)

1. **In the starter** (once): bump `VERSION`, add a `CHANGELOG.md` entry, run `python3 -m unittest discover -s tests`, commit, push, then tag: `git tag v1.2.0 && git push --tags`.
2. **In each project:**
   ```
   cd ~/code/ai-pipeline-starter && git pull
   cd /path/to/project && git checkout main && git pull && git checkout -b pipeline-upgrade
   ~/code/ai-pipeline-starter/install/install.sh /path/to/project --upgrade
   ```
3. For every `*.pipeline-new` file listed: compare, copy over what you want, delete the `.pipeline-new` file. (A file you edited stays flagged until your copy matches the new one.)
4. Commit, push, open a PR, merge, then run Actions -> Health check.

## Be told when an update exists

The **Update check** workflow runs every Monday, compares your `.pipeline-version` with the newest tag in the starter repository, and opens one issue ("Pipeline update available: x.y.z") when there is a newer one. It changes no files. It needs the starter repo to be public and to have version tags.

## First time for a project installed before this feature

Run the normal install once (no `--upgrade`): `install.sh /path/to/project --env YOUR_ENV_NAME`. Files you never changed are rewritten with identical content; your own `CLAUDE.md` etc. are kept. After that, use `--upgrade`.

## Limits

- `--upgrade` is bash only. On Windows use Git Bash or WSL (the normal PowerShell installer still works for first installs).
- A fork of the starter updates from the fork's tags.
- Projects that copy the starter by hand (no installer) have no record, so they need the one-time install above.
