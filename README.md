# infrastructure

Shared infrastructure monorepo managed with Nx. Provisions and configures the
multi-cloud K3s cluster and deploys all product workloads.

## Repo Structure

```
cloud/oracle/          Terraform, Ansible, and scripts for the OCI cluster
cloud/aws/             Terraform for AWS resources (ARM builder, agent-02)
kubernetes/            Shared K8s manifests (observability, databases, messaging)
apps/codectl/          codectl app deployment (Helm values, overlays)
apps/fintel/           fintel app deployment
docker/codectl/        Dockerfiles for codectl services
docker/fintel/         Dockerfiles for fintel services
docs/                  Infrastructure documentation
```

## The Cluster

Multi-cloud K3s cluster (v1.34.5+k3s1) across OCI and AWS:

| Node | Cloud | Shape | Arch | CPU | RAM | Role |
|------|-------|-------|------|-----|-----|------|
| server-00 | OCI | A1.Flex | arm64 | 2 | 12 Gi | K3s control plane |
| agent-00 | OCI | A1.Flex | arm64 | 2 | 12 Gi | K3s worker (main) |
| agent-01 | OCI | E4.Flex | amd64 | 1 | 16 Gi | K3s worker (IB Gateway) |
| agent-02 | AWS | t4g.small | arm64 | 2 | 2 Gi | K3s worker |
| sentinel-00 | OCI | E2.Micro | amd64 | 1 | 1 Gi | Bastion |
| sentinel-01 | OCI | E2.Micro | amd64 | 1 | 1 Gi | Backup bastion |

Connected via Tailscale mesh VPN. Cloudflare DNS + cert-manager for TLS.

## Getting Started

### Prerequisites

- [Bitwarden CLI](https://bitwarden.com/help/cli/) (`npm install -g @bitwarden/cli`)
- [devcontainer CLI](https://github.com/devcontainers/cli) (`npm install -g @devcontainers/cli`)

### First-time setup

```bash
# 1. Configure bw CLI to point at the self-hosted vault
bw config server https://secrets.mateosegura.com
bw login mateo.segura413@gmail.com

# 2. Unlock and export session (do this once per terminal session)
bw unlock
export BW_SESSION="<paste session key>"

# 3. Start the devcontainer
.devcontainer/ctl.sh create
.devcontainer/ctl.sh start
```

That's it. No `.env` files to copy or fill in. The devcontainer pulls all
secrets from your Bitwarden vault automatically.

### Daily workflow

```bash
bw unlock                     # type master password once
export BW_SESSION="..."       # paste session key
.devcontainer/ctl.sh start    # secrets loaded, tools configured
```

## Secrets Management

All secrets are stored in Bitwarden (self-hosted Vaultwarden at
`secrets.mateosegura.com`) and pulled at devcontainer startup. Zero
plaintext secrets on disk.

### How it works

```
bw unlock (host) → BW_SESSION env var → devcontainer mount
  → ctl.sh post-create → bw get notes "env:<project>"
  → ~/.secrets.env (600 perms) → sourced in shell profiles
  → OCI/SSH/AWS configured from env vars
```

### Bitwarden items

Each project stores its full environment as a Bitwarden secure note:

| Item Name | Folder | Used By |
|-----------|--------|---------|
| `env:infrastructure` | Infrastructure | infrastructure devcontainer |
| `env:fintel` | Fintel | fintel devcontainer |
| `env:codectl` | Codectl | codectl devcontainer |

To update a project's secrets:
```bash
# Edit the note in the web vault at https://secrets.mateosegura.com
# Or via CLI:
bw get item "env:infrastructure" | jq '.notes = "NEW_CONTENT"' | bw encode | bw edit item <id>
```

### Fallback modes

The `ctl.sh` script auto-detects the environment:

| Mode | Detection | Secrets Source |
|------|-----------|---------------|
| **Bitwarden** (preferred) | `BW_SESSION` is set | `bw get notes "env:<project>"` |
| **CI** | `CI` or `GITHUB_ACTIONS` is set | Env vars from CI system |
| **Legacy .env** (fallback) | `.devcontainer/.env` exists | Plaintext file |

### Vault (secrets.mateosegura.com)

- **URL**: `https://secrets.mateosegura.com`
- **Auth**: Google OAuth (web) + Master Password + TOTP MFA
- **Helm chart**: `fintel/deploy/helm/secrets-manager/`
- **Namespace**: `shared-services`
- **Credentials file**: `~/.mateo/secrets` (root-owned, `sudo cat` to read)

### Security layers

1. **Google OIDC** — must authenticate with Google to access web vault
2. **Master password** — encrypts all vault data client-side (E2E)
3. **TOTP MFA** — phone authenticator required for login
4. **TLS** — Let's Encrypt wildcard via cert-manager
5. **Rate limiting** — 10 req/s on ingress
6. **Network policies** — only ingress-nginx can reach vault pods
7. **Signups disabled** — single-user vault

## Nx Targets

```bash
nx run oracle:plan       # Terraform plan
nx run oracle:apply      # Terraform apply
nx run oracle:configure  # Ansible configure
nx run oracle:bootstrap  # Full bootstrap (plan + apply + configure)
```

## Shared Services

All shared data services in `shared-services` namespace:

| Service | Address | Port |
|---------|---------|------|
| PostgreSQL | `postgres.shared-services.svc.cluster.local` | 5432 |
| ClickHouse | `clickhouse.shared-services.svc.cluster.local` | 8123, 9000 |
| Redis | `redis.shared-services.svc.cluster.local` | 6379 |
| NATS | `nats.shared-services.svc.cluster.local` | 4222 |
| MinIO | `minio.shared-services.svc.cluster.local` | 9000 |
| OTEL Collector | `otel-collector.shared-services.svc.cluster.local` | 4317 |
| Vaultwarden | `vaultwarden.shared-services.svc.cluster.local` | 80 |

## ARM Builder

The cluster runs on ARM. Dev machines are x86. Container images are built
natively on an AWS Graviton instance (on-demand, ~20s resume, auto-stops
after 10 min idle):

```bash
docker-arm build -t myapp:latest .   # auto-starts builder
arm-builder status                    # check state + cost
```
