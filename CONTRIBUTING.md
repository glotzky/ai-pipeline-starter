<!--
HOW TO DEVELOP THIS FILE (invisible when rendered on GitHub)
Purpose: ground rules for anyone proposing a change. GitHub links it when someone opens an issue or pull request.
Edit it when: you add a new check, a new supported platform, or a new rule you keep having to repeat.
How:
  1. Keep the "Checks before opening a pull request" commands identical to the ones in MAINTAINING.md.
  2. Keep the rules: generic (no personal data), honest verification claims, scratch-repo testing first, no secrets.
  3. Add a rule only when a mistake has happened twice.
-->
# Contributing

Issues and pull requests are welcome. This kit is maintained on a best-effort basis.

## Ground rules
- **Keep it generic.** No personal names, project names, repo names, keys, IDs or customer data anywhere in the kit. Use placeholders such as `OWNER/REPO`.
- **Say what you verified.** If you change behavior, say whether you ran it live in GitHub Actions, in a scratch repo, or not at all, and update the verification table in the README to match. Do not mark something verified that you did not run.
- **Test in a scratch repo first.** For installer or `run.py` changes: run `install/install.sh` into a throwaway repository, and run the orchestrator with stubs before pointing it at a real Devin or Anthropic key.
- **Never paste secrets** into issues, pull requests, logs or screenshots.
- Keep documentation plain and step by step, with commands for macOS, Windows and Linux where they differ.

## Checks before opening a pull request
```bash
python3 -m py_compile template/pipeline/run.py template/pipeline/project_plan.py
bash -n install/install.sh install/set-secrets.sh install/harden-repo.sh
python3 -c "import yaml,glob;[yaml.safe_load(open(f)) for f in glob.glob('template/.github/**/*.yml', recursive=True)]"
```
