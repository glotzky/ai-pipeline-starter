# Maintaining this repository

How to develop and keep up each top-level file. Each file also carries its own short note at the top
(an invisible comment in the Markdown files, `#` comments in `.gitignore`). `LICENSE` has none, because
license text must stay exactly as is.

## The files

| File | What it is | When to change it | How |
|---|---|---|---|
| `README.md` | Front page, doc map, verification table | A doc, workflow or status changes | Keep the doc numbering matching `docs/`; mark "Verified live" only after a real Actions run; run the link check; add a CHANGELOG line |
| `LICENSE` | MIT license, "Copyright (c) 2026 Gil Lotzky" | Almost never. Change the year or name only if they change | Leave the wording untouched. Another license means replacing the whole file and telling contributors |
| `.gitignore` | Files never to commit | A new tool creates junk files | One pattern per line; verify with `git status` |
| `SECURITY.md` | How to report vulnerabilities | Reporting route or scope changes | Keep Private vulnerability reporting switched on in Settings -> Code security |
| `CONTRIBUTING.md` | Ground rules for changes | A rule keeps being broken | Add a rule after the same mistake happens twice |
| `CHANGELOG.md` | What changed per release | Every release | New dated section on top; semantic version; then `git tag` |
| `MAINTAINING.md` | This file | You add or remove a top-level file | Add a row to the table |
| `docs/` | The guides | Behavior or advice changes | Edit the numbered file; update README map and CHANGELOG |
| `tests/` | Tests for the kit itself (not installed into projects) | You change `run.py`, `run_metrics.py`, the schema or `summarize.py` | Add or update a test in the same change; run the suite |
| `template/` | What gets copied into projects | You improve a workflow, agent or script | Follow "Changing the template" below |
| `install/` | Installers and setup scripts | The template gains files that need special handling | Test with a scratch repo (below) |

## Tests
```bash
python3 -m unittest discover -s tests        # 50 tests, about 20 seconds, standard library only
```
They cover the metrics recorder and schema, the summary script, and the real `pipeline/run.py` run end to end against a fake `claude`, `gh` and Devin in a scratch git repository. Run them after any change to `template/pipeline/`, `template/metrics/` or the schema.

## Changing the template (the part that matters most)

1. Edit the file under `template/`.
2. Run the checks:
```bash
python3 -m py_compile template/pipeline/run.py template/pipeline/project_plan.py
bash -n install/install.sh install/set-secrets.sh install/harden-repo.sh
python3 -c "import yaml,glob;[yaml.safe_load(open(f)) for f in glob.glob('template/.github/**/*.yml', recursive=True)]"
```
3. Test the installer on a scratch repository, never a real project:
```bash
D=$(mktemp -d) && git init -q -b main "$D" && git -C "$D" commit -q --allow-empty -m init
bash install/install.sh "$D" && ls -a "$D" "$D/.github/workflows"
```
4. If you changed a workflow or `run.py`, run it once in a scratch GitHub repo before telling anyone it works.
5. Update `README.md` (verification table) and `CHANGELOG.md`, then tag a release.

## Link check (run before every commit that touches Markdown)
```bash
python3 - <<'PY'
import re,os,glob
bad=0
for f in glob.glob('**/*.md',recursive=True):
    for m in re.finditer(r'\]\(([^)#]+?)(#[^)]*)?\)',open(f).read()):
        t=m.group(1)
        if t.startswith('http'): continue
        if not os.path.exists(os.path.join(os.path.dirname(f),t)): print("broken",f,t); bad+=1
print("broken links:",bad)
PY
```

## Personal-data check (run before every push)
```bash
grep -rniE "cog_[A-Za-z0-9]{10,}|sk-ant-[A-Za-z0-9_-]{10,}|ghp_[A-Za-z0-9]{20,}|github_pat_|/Users/|@gmail\.com" . -I --exclude-dir=.git --exclude=MAINTAINING.md
```
It should print nothing except the pattern names mentioned in `template/metrics/README.md` and `template/pipeline/run_metrics.py`. Never commit keys, IDs, or the names of your own private projects.

## Releasing
```bash
# 1. update CHANGELOG.md, 2. commit, 3. then:
git tag v1.0.1 && git push && git push --tags
```
