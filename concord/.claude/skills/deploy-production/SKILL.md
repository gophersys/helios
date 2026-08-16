---
name: deploy-production
description: Deploy the current commit to production. Requires staging at the same commit, all checks green, and explicit user confirmation.
---

# /deploy-production

Spawn `deployer` (`.claude/agents/deployer.md`). Production is gated — the agent will refuse to deploy without confirmation.

## Pre-flight (the agent MUST verify all of these)

1. **Staging is at the target commit and healthy**:
   ```bash
   kubectl -n staging exec deploy/concord-http-api -- printenv | grep -E "APP_VERSION|GIT_COMMIT"
   ```
   Should match the commit you're about to deploy to production. If not, deploy staging first via `/deploy-staging` and run a smoke before continuing.

2. **Tests are green**: `nx run platform:check` passes locally.

3. **Submodule is clean**:
   ```bash
   git -C /home/bottinger/work/concord/concord status --porcelain
   ```
   Empty output is required.

4. **`.git-build-info` is fresh** (see `/deploy-staging` step 1).

5. **User confirmation**: the agent asks "deploying v<X.Y.Z> (commit <SHA>) to PRODUCTION — confirm?" and waits for an explicit yes.

## Deploy

From inside the devcontainer:

```bash
export KUBECONFIG=/root/.kube/config-concord-remote
nx update platform -c production
```

Same flow as staging: preflight → build → push → helm upgrade → rollout verify → smoke test. ~4-5 minutes.

## Post-deploy

1. **Verify**:
   ```bash
   kubectl -n production exec deploy/concord-http-api -- printenv | grep -E "APP_VERSION|GIT_COMMIT"
   ```

2. **Smoke the UI**: open `https://concord.ad.corekinect.com/` in a browser (or `concord-remote` tunnel). Log in, verify the dashboard renders.

3. **Watch logs for 5 minutes**: anything unusual in `kubectl -n production logs deploy/concord-http-api --tail=100 -f`?

## If production goes red

1. **Roll back immediately**:
   ```bash
   nx rollback platform -c production
   ```
2. **Then debug**. Don't try to fix forward on production while users are seeing errors.
3. **Capture the incident**: `/home/bottinger/work/docs/incidents/<YYYY-MM-DD>-<short-name>/incident.md` with a human-voice description of what happened.

## Don't

- Don't deploy production with a different commit than staging.
- Don't deploy production with a known failing test.
- Don't deploy on a Friday without a clear rollback plan.
- Don't skip the explicit confirmation — the gate exists because production deploys are not symmetric to staging deploys.
