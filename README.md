# infrastructure

Shared infrastructure monorepo managed with Nx. Provisions and configures the
6-node OCI ARM cluster and deploys all product workloads.

## Repo Structure

```
cloud/oracle/          Terraform, Ansible, and scripts for the OCI cluster
kubernetes/            Shared K8s manifests (observability, databases, messaging)
apps/codectl/          codectl app deployment (Helm values, overlays)
apps/fintel/           fintel app deployment
docker/codectl/        Dockerfiles for codectl services
docker/fintel/         Dockerfiles for fintel services
docs/                  Infrastructure documentation
```

## The Cluster

6-node K3s cluster on Oracle Cloud ARM (Ampere A1) instances:

- 3 server nodes (control plane + etcd)
- 3 agent nodes (workloads)
- Tailscale mesh VPN for inter-node connectivity
- Cloudflare DNS for public endpoints
- cert-manager for TLS

## Getting Started

1. Install prerequisites: `npm install -g @devcontainers/cli`
2. Copy env file: `cp .devcontainer/.env.example .devcontainer/.env`
3. Fill in credentials in `.devcontainer/.env`
4. Start the devcontainer: `.devcontainer/ctl.sh create`
5. Open a shell: `.devcontainer/ctl.sh start`

## Nx Targets

```bash
nx run oracle:plan       # Terraform plan
nx run oracle:apply      # Terraform apply
nx run oracle:configure  # Ansible configure
nx run oracle:bootstrap  # Full bootstrap (plan + apply + configure)
```
