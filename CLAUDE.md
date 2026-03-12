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
cloud/oracle/       Terraform, Ansible, scripts for OCI cluster
kubernetes/         Shared K8s manifests (observability, databases, messaging)
apps/               Per-product deployment configs (Helm values, overlays)
docker/             Dockerfiles for all services
docs/               Infrastructure documentation
```

## Shell Scripts

- Use `set -euo pipefail` at the top of every script
- Quote all variables
- Use `$(...)` not backticks

## Nx Targets

```bash
nx run oracle:plan       # Terraform plan
nx run oracle:apply      # Terraform apply
nx run oracle:configure  # Ansible playbook
nx run oracle:bootstrap  # Full provision cycle
```
