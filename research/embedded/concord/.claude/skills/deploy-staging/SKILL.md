---
name: deploy-staging
description: Deploy the current branch to the staging K8s cluster. Builds images, pushes, helm-upgrades, verifies rollout, smoke-tests.
---

# /deploy-staging

Spawn `deployer` (`.claude/agents/deployer.md`).

## What the agent does

1. **Pre-flight**:
   - Confirm the current concord branch and commit. Should be clean.
   - **If concord is a git submodule of an umbrella workspace**: refresh `.git-build-info` on the host before invoking the devcontainer (the container can't resolve git when the parent `.git/modules/` isn't mounted). See [`.claude/knowledge/deploy/ctl-sh.md`](../../knowledge/deploy/ctl-sh.md) — "Submodule context".
     ```bash
     { git rev-parse --short HEAD; git rev-parse --abbrev-ref HEAD; \
       [ -n "$(git status --porcelain 2>/dev/null)" ] && echo true || echo false; \
     } > .git-build-info
     ```
   - If concord is a standalone clone, skip this step — `git` works natively in the container.

2. **Run the deploy from inside the devcontainer**, with KUBECONFIG pointing at the right cluster:
   ```bash
   export KUBECONFIG=/root/.kube/config-concord-remote   # remote/offsite
   # or                /root/.kube/config                 # in-office
   nx update platform -c staging
   ```

3. **Watch the output**. The target:
   - Runs env preflight (helm values check, K8s reachability).
   - Builds 6 images in parallel (~2 min).
   - Pushes to `containers.ad.corekinect.com`.
   - `helm upgrade` (~30s).
   - Rollout verification (~50s — all 8 deployments at `1/1`).
   - Smoke test (curl `/api/health`, check build-service pod).

   Total ~4 minutes.

4. **Verify version**:
   ```bash
   kubectl -n staging exec deploy/concord-http-api -- printenv | grep -E "APP_VERSION|GIT_COMMIT"
   ```
   Should match what was just deployed.

## If it fails

| Symptom | Likely cause | Fix |
|---|---|---|
| K8s unreachable | wrong KUBECONFIG in container | export `config-concord-remote` |
| migrate-and-seed CrashLoopBackOff | failed migration | inspect logs, write forward fix migration |
| OOMKilled | memory limit exceeded | bump in helm values, redeploy |
| helm `context deadline exceeded` | slow pod termination | retry; if persistent, `kubectl delete --grace-period=0` on stuck pods |
| Rollout verify timeout | one deployment lagging | inspect that deployment's pod logs |

## Don't

- Don't run two `nx update` against the same cluster in parallel. They will fight over the helm release lock.
- Don't deploy a dirty submodule. The build-info will mark it dirty and the resulting image will fail downstream version checks.
- Don't skip the post-deploy version verify. Floating tags can mask a partial push.
