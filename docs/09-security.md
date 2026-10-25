# 9. Security

The pipeline gives AI agents write access to a repo and runs AI-written code with your keys in the environment. Treat it accordingly.

## What the template does

- **Owner-only triggers.** Intake acts only when the actor is the repository owner and the issue title starts with `[idea]`. Issue text from strangers is never processed.
- **No shell injection from issue text.** User-controlled text reaches scripts only via environment variables or files, never interpolated into commands.
- **Secrets in an Environment restricted to the default branch.** A workflow modified on another branch cannot read them.
- **Least privilege for the Reviewer.** Read-only tools plus `git diff/log/status`.
- **Nothing merges automatically.** Draft PRs only.
- **Agents are told not to touch** `.github/`, `.claude/`, `pipeline/` (via `CLAUDE.md`).

## What it does not do (your job)

| Risk | Mitigation |
|---|---|
| Agents *can* technically edit workflow files on their branch | Review every PR's file list; add branch protection plus `CODEOWNERS` for `.github/`, `.claude/`, `pipeline/`. The workflows run from the default branch, so a branch edit cannot take effect until you merge it |
| The Tester executes AI-written code on the runner, with `ANTHROPIC_API_KEY` (and the other secrets) in the job environment | Use a **dedicated Anthropic key with a low monthly cap**; keep the repo private; consider removing `DEVIN_API_KEY` and `GH_TOKEN` from the environment passed to Claude stages |
| Leaked or over-privileged keys | Devin service user with the **Member** role; rotate every few months; revoke old service users; never commit `.env` |
| Runaway cost | Anthropic spend limit; retry and timeout caps; check Devin usage |
| Sensitive data in prompts and logs | Keep real customer data out of the repo, tests and issues. Logs in `.pipeline/logs/` are committed to run branches |
| Public repos | Do not run this on a public repo with self-hosted runners; keep the pipeline private by default |
| AI code quality and licensing | You review and merge; the Reviewer is an aid, not a guarantee |
| Third-party prompt injection (web pages read by the Researcher, repo content) | Keep the Researcher's tools limited (no Bash); read PRs before merging |

## If a key leaks

Revoke it at the vendor first (Anthropic console, Devin service users, GitHub tokens), then replace the environment secret, then check usage pages for activity you do not recognize.
