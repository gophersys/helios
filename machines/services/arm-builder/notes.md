# arm-builder — operational notes

## What this is

An AWS `t4g.small` EC2 instance (Graviton2 ARM). It exists to build native ARM
container images and push them to `ghcr.io`. It is **not** a Kubernetes node, and
it never will be. A stop or a start of this instance has no effect on any
cluster.

- **Region:** us-west-2 (Oregon)
- **Instance tag:** `Name=arm-builder`
- **Root volume:** about 30 GB of EBS, gp3. It keeps the Docker layer cache
  across a stop and a start, so a rebuild is fast.
- **Billing:** per second. The compute is free until December 2026, under the AWS
  t4g free tier. The storage costs about $4 per month. After the free tier, the
  compute costs about $0.017 per hour.
- **Idle behaviour:** the instance stops automatically after 10 minutes with no
  use. See `scripts/arm-builder.sh --idle`.

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

A consumer project, for example codectl or fintel, wraps this pattern in its own
`ctl.sh` verbs.

## The local setup that you must do

Run this the first time that a dev machine uses the builder:

```bash
bash scripts/arm-builder-setup.sh
```

The script does 3 things:

1. It adds an entry for the builder to `~/.ssh/config`, with the Tailscale
   hostname.
2. It verifies that the AWS CLI credentials resolve.
3. It verifies that the SSH key at `~/.ssh/arm-builder` exists and is loaded.

The Bitwarden items that these scripts consume:

- `ssh-key-arm-builder` — the private key for SSH. The script writes it to
  `~/.ssh/arm-builder`.
- `cloud-aws-brain-admin` — the AWS credentials that control EC2.
- A GitHub token, which is optional. The builder uses it for
  `docker login ghcr.io`. The setup step takes it from `gh auth token` on the
  local machine.

## Migration note

Until 2026-04 these scripts lived at
`infrastructure/cloud/oracle/scripts/arm-builder{,-setup}.sh`. The rebuild moved
them to `machines/services/arm-builder/scripts/`, so that the operational logic
sits with the host that it operates, and not under the cloud provider of an
unrelated cluster.
