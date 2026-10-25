# 14. Optional: Vercel (previews and hosting)

**Not part of the pipeline and not required.** The pipeline never deploys. This page describes an optional add-on to adopt later, when you have a real web app and want to see changes before merging. Nothing in the template depends on it, and nothing here has been tested with this kit.

## What it would give you

| Need | How Vercel helps |
|---|---|
| **See a change before merging** (the gap analysis's visual-review item) | Every pull request, including each pipeline PR, gets its own preview URL, posted as a comment. You can open it from your phone |
| **Deploy on merge** | Merging to the default branch deploys production automatically |
| **Easy rollback** | Promote or redeploy a previous deployment from the dashboard |
| **Environment variables per environment** | Different values for preview and production |

Alternatives that do the same job: Netlify, Cloudflare Pages. The advice below applies to any of them.

## When to adopt it

Not yet if the repo has no running web app (only scaffolding or a static page nobody needs previewed). Adopt it when:
1. The app builds and runs locally with `npm run build`.
2. You are reviewing UI changes and the diff alone is not enough.
3. You are ready to show the site to anyone outside the project.

## Cost (checked October 2026; confirm on vercel.com/pricing)

- **Hobby: free, but limited to non-commercial, personal use** per Vercel's fair-use rules. A business site (for example a service you charge for) does not qualify.
- **Pro: $20 per user per month** for developer seats (viewer seats are free), with included usage and overage billing. Set a spend limit in the dashboard.
- Preview deployments count against deployment limits (Hobby 100 per day, Pro 6,000 per day). Each pipeline push can create one, so busy retries add up on Hobby.

## How it fits the pipeline (when you add it)

1. Connect the repo with Vercel's **Git integration** (Vercel dashboard -> Add New -> Project -> import the GitHub repo). Set the production branch to your default branch.
2. The pipeline's draft PR gets a preview URL comment. Open it, click through, then merge or `/fix`.
3. Use **Deployment Protection** (Vercel Authentication on previews) so unfinished work is not public.
4. Put any real values in Vercel's **Environment Variables**, scoped to Preview and Production separately.

## Security rules

- **Deploy only through the Git integration.** Do not give the pipeline, Devin or any agent a Vercel token. Agents that cannot deploy cannot break production.
- **Never expose server secrets to the browser.** Variables with a client prefix (`VITE_`, `NEXT_PUBLIC_`) are shipped to every visitor. A public Supabase anon key is fine there; the Supabase service-role key must never be in any client variable or in the repo.
- Use a separate backend project (database) for preview and production, so a preview can never touch real customer data.
- Add Vercel's build environment to your list of places that need the same secret hygiene as GitHub.

## Checklist to adopt later

- [ ] Hobby vs Pro decided (commercial use means Pro)
- [ ] Git integration connected, production branch set to the default branch
- [ ] Preview protection on
- [ ] Preview and production environment variables set separately
- [ ] Spend limit set
- [ ] Rollback steps written under "Deployment and operations" in `CLAUDE.md`
- [ ] Required CI check still green before merge (`harden-repo.sh --require-ci`)
