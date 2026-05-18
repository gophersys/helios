# Onboarding — knowledge

How an admin brings a new developer from zero to "their first
deploy" against the Concord platform. The user-facing version of
this is published at [`docs/administration/onboarding.md`](../../../docs/administration/onboarding.md);
this file is the agent-facing distilled version of the same flow.

Refresh this file when: the kubeconfig generator's flags change, a
new RBAC role is added to `bindings-<env>.yaml`, the SSH-key /
clone flow changes, or the devcontainer bootstrap sequence changes.

## What an admin provisions for a new dev

Four items, in this order:

1. **Bitbucket SSH key** — they generate it on their own machine and add it to their Bitbucket account. The admin only needs to grant them write access to the `corekinect` workspace.
2. **AD/SSO account** — created by domain admin. Username `<first>@ad.corekinect.com`, group `role_engineer_manufacturing`.
3. **Kubeconfig (role-scoped)** — admin runs `bash infrastructure/clusters/office/kubeconfigs/generate.sh <email> <ROLE> <days>` and hands them the resulting `<username>.kubeconfig` from `./generated/`. See [RBAC](#rbac).
4. **Per-service credentials** — whichever values the dev needs from the team's secret store (Bitbucket API token, K8s secrets, etc.). What they need depends on what they'll be running — see [`credentials.md`](credentials.md).

## RBAC

Four roles in `infrastructure/clusters/office/rbac/clusterroles.yaml`. The generator script (`infrastructure/clusters/office/kubeconfigs/generate.sh`) maps each to its K8s Group.

| Platform Role | K8s ClusterRole | Group | Scope |
|---|---|---|---|
| `ADMIN` | `concord-super-admin` | `concord-admins` | Cluster — every namespace, every verb, every resource |
| `MAINTAINER` | `concord-namespace-admin` | `concord-maintainers` | RW on `development`, `staging`, `validation`, `devops`; read-only on `production` |
| `DEVELOPER` | `concord-namespace-readonly` | `concord-developers` | Read-only on `development`, `staging`; zero production access. **Default for new hires.** |
| `OPERATOR` | (operator role binding) | `concord-operators` | Read-only on `staging` only — manufacturing operators |

Auth chain: client cert (CN=email, O=group) signed by cluster CA → K8s identifies the group → `RoleBinding`/`ClusterRoleBinding` in `bindings-<env>.yaml` grants the cluster role's permissions → kubectl works inside scope, refused outside it.

The cert is valid for whatever `days` the admin passes. Default convention is 365. Rotate by re-running the same `generate.sh` invocation — it deletes the old CSR first.

## The generator command

```bash
cd infrastructure/clusters/office/kubeconfigs
bash generate.sh newdev@ad.corekinect.com DEVELOPER 365
# → ./generated/newdev.kubeconfig
# → ./generated/newdev.meta.json (audit record)
# → script auto-tests: ✓ staging list pods, ✗ production list pods (expected for DEVELOPER)
```

Hand the dev the kubeconfig file. They put it at `~/.kube/config` or export `KUBECONFIG=/path/to/newdev.kubeconfig`.

## What the dev needs installed on their host

Most CoreKinect workstations have the basics. Bootstrap:

- `git`, `docker` — already on the office Ubuntu image
- **Node 18+** — install via `nvm install --lts`. Needed for `npx -y @devcontainers/cli` which runs `nx` commands on the host.
- **VS Code** + Dev Containers extension
- **kubectl** — `sudo snap install kubectl --classic`
- **helm** — `sudo snap install helm --classic`

Everything else (Python deps, Zephyr SDK, nRF Connect SDK, west, nrfjprog, etc.) lives **inside** the right devcontainer. The repo ships five devcontainers (`base`, `mtib`, `ncs-v2.7.0`, `ncs-v3.2.1`, `zephyr-v4.0`) — see [`.devcontainer/README.md`](../../../.devcontainer/README.md).

## The 30-minute happy path

```bash
# Dev's first commands
mkdir -p ~/work/concord && cd ~/work/concord
chmod 600 ~/.ssh/keys/bitbucket    # SSH key from admin
git clone --recurse-submodules git@bitbucket.org:corekinect/concord.git
cd concord
cp .env.example .env
sed -i "s|/path/to/concord|$(pwd)|" .env

mkdir -p ~/.kube
cp ~/Downloads/newdev.kubeconfig ~/.kube/config
kubectl get pods -n staging        # smoke test

# Open in VS Code → "Dev Containers: Reopen in Container" → base
# First open runs .devcontainer/base/ctl.sh create — installs all the rest.
# Then:
nx start platform                  # full dev stack
```

## When the kubeconfig expires

Set a calendar reminder for ~30 days before the cert expires. To rotate:

```bash
cd infrastructure/clusters/office/kubeconfigs
bash generate.sh newdev@ad.corekinect.com DEVELOPER 365
# Hand them the new ./generated/newdev.kubeconfig — they replace ~/.kube/config
```

## When they leave

```bash
# 1. Find their CSR
kubectl get csr | grep newdev

# 2. Delete the CSR record (the cert won't be re-issued; old cert remains valid until expiry, K8s doesn't have a revocation list for client certs)
kubectl delete csr concord-newdev

# 3. Remove their generated kubeconfig
rm infrastructure/clusters/office/kubeconfigs/generated/newdev.{kubeconfig,meta.json}

# 4. Remove their Bitbucket access in the workspace settings
# 5. Remove their AD account from role_engineer_manufacturing
# 6. Revoke any per-service .env credentials shared with them
```

For real revocation before expiry: rotate the cluster CA (heavy) or wait it out.

## What to fix proactively

Three small gaps that trip up new devs and have been worth fixing
before each new onboarding:

1. The 3 firmware-signing-key env vars (`BENCH_SIGNING_KEY`, `ENGINEERING_SIGNING_KEY`, `PRODUCTION_SIGNING_KEY`) live in `deploy/development/.env.example` but aren't always called out in the "what does a new dev actually need" list — they only matter if the dev runs build-service locally. The default `prisma/seed.py` bench keys cover most local-dev cases.
2. `generate.sh` has no `list-active` subcommand — auditing who has what kubeconfig means manually reading `./generated/*.meta.json` + `kubectl get csr`. Documented limitation.
3. `~/.ssh-devcontainer/` parallel directory is unusual — surprising for devs used to one `~/.ssh`. It's bind-mounted readonly into the devcontainer at `/root/.ssh/` to avoid the VS Code container clobbering the host's permissions. Worth a heads-up.

## Related

- [`credentials.md`](credentials.md) — the per-credential index
- [`../../../docs/administration/onboarding.md`](../../../docs/administration/onboarding.md) — public-facing version of this same flow
- [`../../skills/onboard-dev/SKILL.md`](../../skills/onboard-dev/SKILL.md) — slash command that walks an admin through the steps
- `infrastructure/clusters/office/kubeconfigs/generate.sh` — the kubeconfig minter
- `infrastructure/clusters/office/rbac/*.yaml` — the RBAC definitions
