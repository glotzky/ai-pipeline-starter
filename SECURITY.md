<!--
HOW TO DEVELOP THIS FILE (invisible when rendered on GitHub)
Purpose: tells people how to report a vulnerability in the kit privately. GitHub shows it on the Security tab.
Edit it when: your reporting route changes, or the scope of what you support changes.
How:
  1. Turn on Settings -> Code security -> Private vulnerability reporting so the "Report a vulnerability" link works.
  2. Keep the instruction never to include real keys in a report.
  3. If you add a contact email, use a noreply or project address, never a personal one.
-->
# Security policy

This kit gives AI agents write access to a repository and runs AI-written code with your keys in the environment. Read [docs/09-security.md](docs/09-security.md) before using it.

## Reporting a problem with the kit

If you find a vulnerability in the template or scripts (for example a way for an outsider to trigger a run, read a secret, or inject a command through issue text), please report it privately through this repository's **Security -> Report a vulnerability** page rather than a public issue.

**Never include real keys, tokens or customer data in a report.** If you accidentally exposed a key, revoke it at the vendor first (Anthropic console, Devin service users, GitHub tokens), then replace the secret.

## Scope

In scope: the files under `template/` and `install/`. Out of scope: vulnerabilities in GitHub, Devin, Claude or other third-party services, and the code your own pipeline generates in your own projects.

This is a personal project maintained on a best-effort basis, without warranty.
