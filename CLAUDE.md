# Infrastructure Repo — Claude Code Instructions

## Git Workflow

- Never commit to `main` directly — use branches: `<type>/<description>`
- Types: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`
- Commit format: `<type>(<scope>): <description>` (max 72 chars)

## Terraform

- Always run `terraform plan` before `terraform apply`
- Never apply without reviewing the plan output
- State files are remote (OCI Object Storage) — never commit `.tfstate`
- Use `terraform.tfvars` for variable overrides (gitignored)
- Lock file (`.terraform.lock.hcl`) is gitignored; regenerate with `terraform init`

## ARM Instance Protection — NON-NEGOTIABLE

The A1.Flex ARM instances (server-00, agent-00) are **irreplaceable**. OCI free
tier A1.Flex capacity is nearly impossible to re-acquire once released. These
instances were obtained through weeks of retry scripting.

**Rules:**
- NEVER run `terraform destroy` on A1.Flex resources
- NEVER allow a `terraform plan` that shows `destroy` or `replace` on server-00 or agent-00
- If Terraform wants to recreate an ARM instance (e.g., due to a config change that
  forces replacement), use `terraform state mv` or `moved` blocks instead
- When importing existing ARM instances into new state, use `terraform import` — never create fresh
- The E2.1.Micro and E4.Flex instances can be destroyed and recreated freely
- If in doubt, abort and ask — losing an ARM instance is unrecoverable

## Security

- Never commit `.env`, credentials, API keys, or kubeconfig files
- SSH keys and OCI PEM files are gitignored
- Secrets in Kubernetes use sealed-secrets or are injected from env vars

## Repo Structure

```
cloud/oracle/       Terraform, Ansible, scripts for OCI cluster (5 nodes)
cloud/aws/          Terraform for AWS resources (builder + agent-02)
kubernetes/         Shared K8s manifests (observability, databases, messaging)
apps/               Per-product deployment configs (Helm values, overlays)
docker/             Dockerfiles for all services
docs/               Infrastructure documentation
```

## Multi-Cloud Cluster Layout

```
OCI Phoenix (Always Free):
  server-00   A1.Flex ARM   2 CPU / 12 GB   K3s server
  agent-00    A1.Flex ARM   2 CPU / 12 GB   K3s agent
  agent-01    E4.Flex x86   1 CPU / 16 GB   K3s agent (~$14/mo)
  sentinel-00 E2.Micro x86  1 CPU /  1 GB   bastion
  sentinel-01 E2.Micro x86  1 CPU /  1 GB   bastion

AWS Oregon (Free Tier):
  agent-02    t4g.small ARM  2 CPU /  2 GB   K3s agent (always-on)
  arm-builder t4g.small ARM  2 CPU /  2 GB   Docker builder (on-demand)
```

All nodes connected via Tailscale mesh. K3s networking is transparent across clouds.

## Shell Scripts

- Use `set -euo pipefail` at the top of every script
- Quote all variables
- Use `$(...)` not backticks

## ARM Builder (On-Demand Remote Docker Builds)

The cluster runs on ARM. Dev machines are x86. To build ARM container images
natively, we use an AWS t4g.small (Graviton ARM) instance that is **stopped
when idle** and **started on demand** (~20s resume). Per-second billing.

**Scripts:**
- `cloud/oracle/scripts/arm-builder.sh` — Main CLI (up/down/ensure/status/ssh/build)
- `cloud/oracle/scripts/arm-builder-setup.sh` — One-time dev machine setup

**Usage:**
```bash
docker-arm build -t myapp:latest .     # auto-starts builder if needed
arm-builder up                          # manual start (~20s)
arm-builder down                        # stop ($0 compute, EBS persists)
arm-builder status                      # check state + cost
arm-builder ensure                      # idempotent start (for CI)
```

**Cost:** $0 compute (free tier through Dec 2026). ~$4/mo EBS (Docker cache).
Auto-stops after 10 min idle.

**Required credentials on a new machine:**
1. AWS credentials (`~/.aws/credentials` or `AWS_ACCESS_KEY_ID` + `AWS_SECRET_ACCESS_KEY`)
2. SSH key (`~/.ssh/arm-builder` + `.pub`)
3. `GITHUB_TOKEN` for ghcr.io push (optional, auto-discovered from .env)

**Rules:**
- ALWAYS use the remote ARM builder for staging/production container builds
- NEVER use QEMU emulation for production images (5x slower, can mask bugs)
- Local `docker build` (x86) is fine for dev/testing only
- The builder is NOT a cluster node — safe to stop/start freely

## Nx Targets

```bash
nx run oracle:plan       # Terraform plan
nx run oracle:apply      # Terraform apply
nx run oracle:configure  # Ansible playbook
nx run oracle:bootstrap  # Full provision cycle
```
