# Onboarding a new developer

Walk-through for the platform owner (you) to bring a new engineer
from zero to "their first deploy" in ~30 minutes. Aimed at the
*admin* doing the onboarding, not the new dev — read this first, then
hand them the "What the new dev runs" section at the bottom.

---

## What you (admin) provision before they sit down

| # | Item | Where you create it | Where they put it |
|---|---|---|---|
| 1 | **Bitbucket SSH key** (their personal one, write access to `corekinect` workspace) | Bitbucket → Workspace settings → User invite, then have them generate a key and add it to their account | `~/.ssh/keys/bitbucket` (chmod 600) |
| 2 | **AD/SSO account** | Domain admin — `<first>@ad.corekinect.com`, in group `role_engineer_manufacturing` | OS login |
| 3 | **K8s kubeconfig** (role-scoped) | `bash infrastructure/clusters/office/kubeconfigs/generate.sh <email> <ROLE> 365` — see [RBAC roles](#rbac-roles) | `~/.kube/config` or `KUBECONFIG=...` |
| 4 | **Access to the secrets you've decided to share** | Up to you and your team — see [Secrets handoff](#secrets-handoff) | their team-decided store |

That's the canonical set. Everything else (devcontainer images, build cache, Python deps, Node deps, Helm, kubectl) flows from the repo + devcontainer.

---

## RBAC roles

`generate.sh` mints one of four roles. Pick the right one — overshooting on permissions is the most common onboarding mistake.

| Role | K8s ClusterRole | What they get | Give to |
|---|---|---|---|
| `ADMIN` | `concord-super-admin` | Full cluster — every namespace, every verb, every resource | Platform owner only |
| `MAINTAINER` | `concord-namespace-admin` | RW on `development`, `staging`, `validation`, `devops`; read-only on `production` | Senior engineers shipping their own changes |
| `DEVELOPER` | `concord-namespace-readonly` | Read-only on `development`, `staging`; zero production access | **Default for new hires** |
| `OPERATOR` | (operator role binding) | Read-only on `staging` only — for ops people running manufacturing sessions without touching code | Manufacturing operators |

```bash
# You, as cluster admin, run this once per new hire:
cd infrastructure/clusters/office/kubeconfigs
bash generate.sh newdev@ad.corekinect.com DEVELOPER 365
# → ./generated/newdev.kubeconfig + .meta.json
# → auto-tests "✓ staging list pods" / "✗ production list pods (expected for DEVELOPER)"
```

The cert is valid for whatever you pass as the third arg (days). 365 is the conventional default. Re-run the same command to rotate — it deletes the old CSR first.

---

## Secrets handoff

The platform deliberately does **not** mandate a specific secret store. You decide — 1Password, Vault, an internal wiki, an encrypted file, whatever fits your team. The repo just expects the values to land in two places:

* **Developer's per-service `.env` files** — each app has its own `.env.example` showing exactly which env vars it needs. The developer copies `.env.example → .env` and fills in the values you give them.
* **Cluster K8s Secrets** — created by `bash infrastructure/clusters/office/secrets/create-all.sh <env>` which reads `infrastructure/clusters/office/secrets/{shared,staging,production}.env` and applies them as Secrets. These three `.env` files are gitignored and live only on the deployer's host.

For a new **DEVELOPER**-role dev, you typically only need to share:

* Their Bitbucket account + SSH key (so they can clone)
* Their kubeconfig (so `kubectl get pods -n staging` works)
* The Bitbucket API token in `apps/backend/http-api/.env` if they're going to run the http-api locally and want it to call Bitbucket

For a new **MAINTAINER**, add:
* The full `shared.env` + `staging.env` so they can run `nx run platform:sync-secrets -c staging` and deploy

For an **ADMIN**, hand over everything including `production.env`.

The full inventory of which env var lives where is in [`.claude/knowledge/deploy/secrets.md`](../../.claude/knowledge/deploy/secrets.md) and per-service `.env.example` files.

---

## What you set up before their first PR

Take 5 minutes to verify the user can do all of this — these are the failure modes that waste the most onboarding time:

1. **SSH to bitbucket works**: `ssh -T git@bitbucket.org` → "authenticated via ssh key"
2. **kubectl works**: `kubectl get pods -n staging` → returns a list (or empty list with no error)
3. **kubectl is correctly scoped**: `kubectl auth can-i list pods -n production` → `no` for DEVELOPER
4. **They can clone**: `git clone --recurse-submodules git@bitbucket.org:corekinect/concord.git`
5. **VS Code → "Reopen in Container"** opens the base devcontainer successfully

If 1–5 pass, they're productive.

---

## Bootstrapping a fresh machine — what they need installed

Most CoreKinect workstations have the basics. If not, they need:

* `git`, `docker` (already on the office image)
* **Node 18+** — install via `nvm install --lts`. Needed for `npx -y @devcontainers/cli` which runs `nx` commands on the host.
* **VS Code** + Dev Containers extension
* **kubectl** — `sudo snap install kubectl --classic`
* **helm** — `sudo snap install helm --classic`

Everything else (Python deps, Zephyr SDK, nRF Connect SDK, west, nrfjprog, etc.) lives **inside** the right devcontainer. The repo ships 5 devcontainers (`base`, `mtib`, `ncs-v2.7.0`, `ncs-v3.2.1`, `zephyr-v4.0`) — see [`.devcontainer/README.md`](../../.devcontainer/README.md).

---

## What the new dev runs (hand them this)

```bash
# Once: install host-side tools (assumes Ubuntu / Debian)
sudo apt-get install -y git docker.io
curl -fsSL https://deb.nodesource.com/setup_lts.x | sudo -E bash - && sudo apt-get install -y nodejs
sudo snap install kubectl --classic
sudo snap install helm --classic

# SSH key from the platform owner — put at ~/.ssh/keys/bitbucket
chmod 600 ~/.ssh/keys/bitbucket

# Kubeconfig from the platform owner
mkdir -p ~/.kube
cp ~/Downloads/newdev.kubeconfig ~/.kube/config
kubectl get pods -n staging   # smoke test — should succeed

# Clone
mkdir -p ~/work/concord && cd ~/work/concord
git clone --recurse-submodules git@bitbucket.org:corekinect/concord.git
cd concord
cp .env.example .env
sed -i "s|/path/to/concord|$(pwd)|" .env

# Open in VS Code → palette → "Dev Containers: Reopen in Container" → base
# First open auto-runs .devcontainer/base/ctl.sh create — installs the rest.
# Subsequent opens run ctl.sh start (verifies env, installs incremental deps).

# Once inside the container, run the platform locally:
nx start platform                  # full dev stack via docker-compose
# or just the API:
nx serve http-api
# or just the frontend:
nx serve app
```

The full repo conventions, agent system, and slash commands live in [`CLAUDE.md`](../../CLAUDE.md) at the repo root. New devs working with Claude Code as their AI pair should `/start-here` after opening the repo for an overview.

---

## When their kubeconfig expires

After 365 days (or whenever you passed to `generate.sh`), `kubectl` will start returning auth errors. To rotate:

```bash
cd infrastructure/clusters/office/kubeconfigs
bash generate.sh newdev@ad.corekinect.com DEVELOPER 365
# Hand them the new ./generated/newdev.kubeconfig — they replace ~/.kube/config
```

Set a calendar reminder for ~30 days before the expiry to do this proactively rather than reactively.

---

## When they leave

```bash
# Find their CSR
kubectl get csr | grep newdev

# Revoke the user from K8s (deletes the CSR record + their cert won't be re-issued)
kubectl delete csr concord-newdev

# Remove the kubeconfig file you handed them (they should already have it)
rm infrastructure/clusters/office/kubeconfigs/generated/newdev.kubeconfig

# Remove their Bitbucket access in the workspace settings
# Remove their AD account from role_engineer_manufacturing
# Revoke any per-service `.env` credentials you shared with them
```

The cert itself remains valid until expiry (K8s doesn't have a revocation list for client certs), but with the CSR deleted and their account removed elsewhere, they have no path back in.
