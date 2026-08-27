---
name: onboard-dev
description: Walk an admin through onboarding a new developer to the Concord platform — Bitbucket access, AD account, scoped kubeconfig, per-service credentials, and the 30-minute first-PR path.
argument-hint: "<email> <ROLE>  e.g.  newdev@ad.corekinect.com DEVELOPER"
---

# /onboard-dev

Provision a new developer's access to Concord. Aimed at the **platform owner** running it on behalf of a new hire.

Full public-facing version: [`docs/administration/onboarding.md`](../../../docs/administration/onboarding.md). Distilled agent-facing version: [`../../knowledge/workflows/onboarding.md`](../../knowledge/workflows/onboarding.md).

## Arguments

- `<email>` — the new dev's AD email, format `<first>@ad.corekinect.com`
- `<ROLE>` — one of `ADMIN | MAINTAINER | DEVELOPER | OPERATOR` (default `DEVELOPER` for new hires; see RBAC table in the knowledge file)

## What the skill does

1. **Pre-flight checks the admin's environment**:
   - `kubectl config current-context` — confirm pointing at the office cluster
   - `kubectl auth can-i create csr --as=system:serviceaccount:kube-system:default` style check — confirm admin actually has CSR-approve permission
   - Confirm `infrastructure/clusters/office/kubeconfigs/generate.sh` is executable

2. **Run the kubeconfig generator**:
   ```bash
   cd infrastructure/clusters/office/kubeconfigs
   bash generate.sh "<email>" "<ROLE>" 365
   ```
   The script creates a CSR, has the admin approve it, retrieves the signed cert, builds the kubeconfig, and runs auto-tests. Output lands at `./generated/<username>.kubeconfig` plus `.meta.json`.

3. **Print the handoff checklist** — what the admin needs to give the new dev next:
   - The generated `.kubeconfig` file (out-of-band: Signal, encrypted email, in-person USB)
   - Confirmation that their Bitbucket account has write access to the `corekinect` workspace
   - Confirmation that their AD account is in `role_engineer_manufacturing`
   - Whichever per-service credentials they need from your team's secret store (depends on role — see below)

4. **List the per-service credentials by role**:
   - `DEVELOPER`: SSH key + kubeconfig only. They run things locally with `AUTH_ENABLED=false` and don't need any production secrets.
   - `MAINTAINER`: above + `shared.env` + `staging.env` so they can run `nx run platform:sync-secrets -c staging` and deploy.
   - `ADMIN`: above + `production.env` (full unlock).

5. **Tell the admin to share the dev-facing onboarding doc**: `docs/administration/onboarding.md` (the "What the new dev runs" section is the one to send them).

6. **Set a 335-day calendar reminder** for kubeconfig rotation. (335 = 365 - 30 days lead time.)

## What the skill does NOT do

- It does NOT generate or fetch the new dev's Bitbucket SSH key — they generate that themselves and add it to their Bitbucket account.
- It does NOT touch the team's secret store — secret handoff is the admin's call (which values, via what channel).
- It does NOT add the dev to AD — that's the domain admin's job, separate ticket.

## When they leave

```bash
kubectl delete csr concord-<username>
rm infrastructure/clusters/office/kubeconfigs/generated/<username>.{kubeconfig,meta.json}
# + revoke Bitbucket workspace access
# + remove from AD group role_engineer_manufacturing
# + revoke any per-service .env credentials shared with them
```

The cert remains valid until its expiry (K8s has no client-cert revocation list). For true revocation before expiry: rotate the cluster CA (heavy operation), or wait.

## Common pitfalls

- **Wrong role**: the most common onboarding mistake is overshooting on permissions. Default to `DEVELOPER` for new hires unless they explicitly need to deploy. You can always rotate up later by re-running this skill with a higher role.
- **Sharing the wrong env file**: handing a new `DEVELOPER` the `production.env` is a credential leak. Match the env-file scope to the role per step 4 above.
- **Cert in unencrypted email**: the kubeconfig contains a client-cert private key. Treat it like any other secret — out-of-band channel.
- **Forgetting `~/.ssh-devcontainer/`**: the dev's devcontainer expects this dir, not `~/.ssh`. Without it, in-container `git pull` fails. See [`../../knowledge/workflows/credentials.md`](../../knowledge/workflows/credentials.md#bitbucket-firmware-repo-access) for why.
