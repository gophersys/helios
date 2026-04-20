# arm-builder — operational notes

## What this is

An AWS `t4g.small` (Graviton2 ARM) EC2 instance that exists to build and
push native-ARM container images to `ghcr.io`. It is **not** a Kubernetes
node and never will be — stopping/starting it has zero cluster impact.

- **Region:** us-west-2 (Oregon)
- **Instance tag:** `Name=arm-builder`
- **Root volume:** ~30 GB EBS, gp3. Persists Docker layer cache across
  stop/start cycles so rebuilds are fast.
- **Billing:** per-second. Compute is free through Dec 2026 (AWS t4g free
  tier); storage is ~$4/mo. Post-free-tier compute is ~$0.017/hr.
- **Idle behavior:** auto-stops after 10 idle minutes (see
  `scripts/arm-builder.sh --idle`).

## Daily workflow

```bash
# From any dev machine with AWS creds + SSH key:
./scripts/arm-builder.sh up       # ~20s
./scripts/arm-builder.sh status   # check state + uptime + cost-so-far
./scripts/arm-builder.sh ssh      # interactive SSH
./scripts/arm-builder.sh down     # stop (keeps EBS)
```

Build via remote Docker:

```bash
BUILDER_IP=$(./scripts/arm-builder.sh ensure)
export DOCKER_HOST="ssh://ubuntu@${BUILDER_IP}"
docker buildx build --platform linux/arm64 -t ghcr.io/mateosegura/foo:latest --push .
unset DOCKER_HOST
```

Consumer projects (codectl, fintel) wrap this pattern in their own
`ctl.sh` verbs.

## Required local setup

The first time a dev machine uses the builder, run:

```bash
bash scripts/arm-builder-setup.sh
```

That:

1. Adds `~/.ssh/config` entry for the builder (via Tailscale hostname).
2. Verifies AWS CLI credentials resolve.
3. Verifies the SSH key at `~/.ssh/arm-builder` exists and is loaded.

Bitwarden items consumed by these scripts:

- `ssh-key-arm-builder` — private key for SSH (placed at `~/.ssh/arm-builder`).
- `cloud-aws-brain-admin` — AWS credentials for EC2 control.
- (optional) GitHub token — used for `docker login ghcr.io` on the builder
  itself. Pulled from `gh auth token` on the local machine at setup time.

## Migration note

Until 2026-04, these scripts lived at
`infrastructure/cloud/oracle/scripts/arm-builder{,-setup}.sh`. The
rebuild moved them to `machines/services/arm-builder/scripts/` so
operational logic sits with the host it operates on, instead of being
filed under the cloud provider of an unrelated cluster.
