# Concord DevContainers

Development containers for the Concord monorepo. All images are stored at `containers.ad.corekinect.com`.

## Container Hierarchy

```
ubuntu:22.04
└── concord-devcontainer-base:latest        Base — Node, Python, Docker, K8s, Helm, Protobuf, Playwright, Claude Code
    ├── concord-devcontainer-mtib:latest     MTIB — nrfjprog, J-Link, esptool, i2c-tools (ARM64)
    ├── concord-devcontainer-ncs:v2.7.0      NCS v2.7.0 — Zephyr SDK 0.17.4, west, nRF Connect SDK
    ├── concord-devcontainer-ncs:v3.2.1      NCS v3.2.1 — Zephyr SDK 0.17.4, west, nRF Connect SDK
    └── concord-devcontainer-zephyr:v4.0     Zephyr v4.0 LTS — Zephyr SDK 0.17.0, vanilla Zephyr
```

All child images inherit everything from base. The NCS variants share a single Dockerfile (`ncs/Dockerfile`) parameterized by `NCS_VERSION`.

## Quick Start

### Build from scratch (no registry access)

From the **repo root**:

```bash
chmod +x .devcontainer/base/ctl.sh && ./.devcontainer/base/ctl.sh build
```

Then reopen in the base container via VS Code.

### Build all images (from inside a devcontainer)

```bash
nx run devcontainer:create-platform-builder   # One-time: create multi-arch builder + inject CA certs
nx run devcontainer:build-all                 # Build base → all variants (local)
nx run devcontainer:push-all                  # Build + push to registry
```

Individual images:

```bash
nx run devcontainer-base:build                # Build base (local, native platform)
nx run devcontainer-base:push                 # Build + push base (amd64 + arm64)
nx run devcontainer-mtib:build
nx run devcontainer-ncs-v2.7.0:build
nx run devcontainer-ncs-v3.2.1:build
nx run devcontainer-zephyr-v4.0:build
```

### Preflight Checks

After the container starts, `ctl.sh` runs preflight checks automatically. Run manually:

```bash
.devcontainer/ctl.sh preflight
```

Checks: Docker socket, registry reachability + CA trust, Kubernetes cluster access.

## Lifecycle

| Event | Script | What it does |
|-------|--------|-------------|
| First open | `ctl.sh create` | Preflight, `yarn`, populate `.env` files, create buildx builder, inject CA certs |
| Subsequent opens | `ctl.sh start` | Preflight, `yarn`, install Python deps, fix USB permissions |

Both are triggered automatically by `devcontainer.json` (`postCreateCommand` / `postStartCommand`).

## File Layout

```
.devcontainer/
├── ctl.sh                      Shared lifecycle script (create, start, preflight)
├── README.md
├── project.json                Nx orchestrator (build-all, push-all, create-platform-builder)
├── assets/
│   └── buildkitd.toml          Buildkit config (registry TLS, multi-arch)
├── base/
│   ├── Dockerfile              Base image (ubuntu:22.04 + all tooling)
│   ├── devcontainer.json       VS Code devcontainer config
│   ├── ctl.sh                  Build/push script for base image
│   └── project.json            Nx project (build, push)
├── mtib/
│   ├── Dockerfile              Extends base — J-Link, nrfjprog, esptool
│   ├── devcontainer.json
│   └── project.json            Builds ARM64 only
├── ncs/
│   └── Dockerfile              Shared NCS template (parameterized by NCS_VERSION)
├── ncs-v2.7.0/
│   ├── devcontainer.json
│   └── project.json            Passes NCS_VERSION=v2.7.0 to ncs/Dockerfile
├── ncs-v3.2.1/
│   ├── devcontainer.json
│   └── project.json            Passes NCS_VERSION=v3.2.1 to ncs/Dockerfile
└── zephyr-v4.0/
    ├── Dockerfile              Vanilla Zephyr v4.0 LTS (not NCS)
    ├── devcontainer.json
    └── project.json
```

## Mounts

All variants mount these from the host:

| Mount | Target | Mode | Purpose |
|-------|--------|------|---------|
| `~/.kube` | `/root/.kube` | readonly | Kubernetes access |
| `~/.ssh-devcontainer` | `/root/.ssh` | readonly | SSH keys (Bitbucket, Git) |
| `~/.claude` | `/root/.claude` | read-write | Claude Code config |
| `~/.claude` | `$HOME/.claude` | read-write | Claude Code (WSL home path) |
| `/var/run/docker.sock` | `/var/run/docker.sock` | bind | Docker-in-Docker |
| `/dev` | `/dev` | bind | USB device access |
| `/mnt` | `/mnt` | bind | Host filesystem |

The MTIB variant additionally mounts `/sys` for USB device enumeration.

## Certificates

The internal registry (`containers.ad.corekinect.com`) uses HTTPS with a private CA. Certificate handling is fully automated:

1. **On container create/start** — `ctl.sh` extracts the CA chain via TLS handshake and installs it into the system trust store
2. **On builder creation** — `nx run devcontainer:create-platform-builder` creates the buildx builder and injects CA certs into the buildkit container's trust bundle
3. **buildkitd.toml** — configures the registry as HTTPS/secure so buildkit validates the CA

No manual certificate setup is needed. If the registry is unreachable, preflight warns but doesn't block.

## Environment

The repo-root `.env` file (from `.env.example`) provides:

- `CONCORD_MONOREPO_ROOT` — host path to repo (required for Docker-in-Docker volume mounts)

Service-level `.env` files are managed by the env tool (`tools/env/ctl.sh`). Run `nx setup env -c development` to populate all `.env` files from their `.env.example` templates.
