# .devcontainer — identity and conventions

This repo (`gophersys/.devcontainer`) is a shared submodule consumed by
every project monorepo in the brain ecosystem. Its role is to provide the
container images used both for local development (VS Code devcontainer)
and as the CI runtime that GitHub Actions invokes `nx affected` inside.

## Purpose

- Single source of truth for the three base images every brain-ecosystem
  project depends on.
- Keeps local dev and CI execution environments byte-for-byte identical.
- Provides a place to bump a toolchain version exactly once and have the
  change flow to every project via shared-change propagation.

## 3-image model

The repo exposes exactly three images. All three have the
`GOPHERSYS_DEVCONTAINER` env marker set so scripts can detect which image
they are running inside.

| Image | `GOPHERSYS_DEVCONTAINER` | Intent |
|---|---|---|
| `ghcr.io/gophersys/base`    | `base`    | Everything most projects need: shells (zsh+oh-my-zsh), git/gh, languages (Node LTS, Python 3.12, Go, Rust), infra CLIs (terraform/kubectl/helm/k9s/tailscale/docker-cli/docker-compose/bw/nats), desktop libs (Tauri/GTK/webkit), USB/BLE libs (libusb, libudev, libbluetooth, bluez), data clients (psql, sqlite3, redis-cli), parsing (jq, yq, httpie, rg, fd, bat), QA (shellcheck, hadolint). |
| `ghcr.io/gophersys/flutter` | `flutter` | Base + OpenJDK 17 + Android cmdline-tools/platform/build-tools + Flutter stable SDK. |
| `ghcr.io/gophersys/zephyr`  | `zephyr`  | Base + device-tree-compiler/ninja/ccache + west in an isolated venv + Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf by default) + udev rules for common dev boards. |

## Structure

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring
├── ctl.sh                       # repo-wide control
├── .claude/rules/00-identity.md # (this file)
├── images/
│   ├── base/     { Dockerfile, project.json, ctl.sh }
│   ├── flutter/  { Dockerfile, project.json, ctl.sh }
│   └── zephyr/   { Dockerfile, project.json, ctl.sh }
└── .github/workflows/build-and-push.yml
```

## Conventions

1. **No Nx workspace of its own.** Every operation must be runnable as plain
   `bash ./ctl.sh <cmd>` from within this repo.
2. **Two-file project rule.** Every image directory under `images/*`
   contains `Dockerfile` + `project.json` + `ctl.sh`. No per-image READMEs;
   `ctl.sh usage()` is the spec.
3. **No `CLAUDE.md` files.** Repo-specific conventions live here in
   `.claude/rules/`.
4. **Human-authored voice.** Commits, comments, and docs contain no AI/LLM
   attribution of any kind.

## ARGs-at-top + latest-LTS convention

Every Dockerfile MUST declare all tool versions as `ARG`s at the top of the
file. Each ARG line carries a `# latest LTS as of YYYY-MM-DD` comment.

- **Bumping a version** = edit one ARG line + its date comment, nothing else.
- **Hardcoding a version in a RUN line is forbidden.** `ctl.sh validate`
  greps for `=\d+\.\d+\.\d+` inside RUN lines and fails the build.
- Adding a new tool requires picking its **latest LTS/stable** release
  (research via apt-cache / upstream GitHub releases / pypi) — never
  invent a version.
- Approval required for bumps: changes to version ARGs go through the
  brain-level approval gate.

## Multi-arch-on-push policy

Every image is published multi-arch (linux/amd64 + linux/arm64). The rule
is non-negotiable:

| Verb | Scope | Arch |
|---|---|---|
| `build` | local dev loop | native single-arch (fast) |
| `build-multi-arch` | local verification | buildx multi-arch, `--load=false` |
| `push` | publish | **ENFORCED** buildx multi-arch, no flag to downgrade |

Both the repo-root and per-image `ctl.sh` expose
`require_buildx_and_multi_arch` as a guard that runs at the start of every
`push` verb. It fails closed if buildx is missing, if no buildx builder is
active, or if the active builder cannot emulate both required platforms.

The CI workflow enforces the same policy: it always sets up QEMU +
buildx and builds with `--platform linux/amd64,linux/arm64 --push`.

## Dev-in-container expectation

These images are intended for **development from inside the container**,
not just CI runtime. The default `CMD` is zsh; oh-my-zsh is preinstalled
for the `dev` user (uid 1000, sudo-nopasswd). Workdir is `/workspace`,
matching the bind-mount convention used by brain-ecosystem projects.

Every image exports `GOPHERSYS_DEVCONTAINER=<image-name>` so dev scripts
and project CI can detect which image they are running inside.

## Per-image verb catalog

| Verb | Action | Cache |
|---|---|---|
| `build` | native single-arch `docker build` | false |
| `build-multi-arch` | `docker buildx build --platform linux/amd64,linux/arm64 --load=false` | false |
| `push` | `docker buildx build --platform linux/amd64,linux/arm64 --push` (guarded) | false |
| `pull` | `docker pull ghcr.io/gophersys/<name>:latest` | false |
| `inspect` | `docker image inspect ghcr.io/gophersys/<name>:latest` | false |
| `help` | Print the usage block from `ctl.sh` | n/a |

## Repo-root verb catalog

| Verb | Action |
|---|---|
| `build <image>` | Delegate to per-image `ctl.sh build` |
| `build-multi-arch <image>` | Delegate to per-image `ctl.sh build-multi-arch` |
| `push <image>` | Delegate to per-image `ctl.sh push` (multi-arch enforced) |
| `pull <image>` | Delegate to per-image `ctl.sh pull` |
| `inspect <image>` | Delegate to per-image `ctl.sh inspect` |
| `list` | Print the managed image refs |
| `validate` | shellcheck, jq, hadolint, ARG-discipline checks |
| `propagate` | Fan out submodule pointer bumps (delegates to brain) |
| `release` | Cut a release (delegates to brain) |
| `help` | Usage |

## Dependency graph

```
     base
   ┌──┴──┐
flutter  zephyr
```

Declared in three places that MUST stay in sync:

- `BUILD_ORDER` in `./ctl.sh`.
- `dependsOn` in each image's `project.json`.
- `needs:` in `.github/workflows/build-and-push.yml`.

## Shared-change propagation

This repo is consumed as a submodule by every project monorepo under
`<project>/.devcontainer/`. Changes here are not visible to projects until
each project bumps its submodule pointer. Run `bash ./ctl.sh propagate`
from within brain to fan out the bump — approval-gated.

## Git hygiene

- Git identity is set per-repo:
  `user.name = Mateo Segura`, `user.email = mateo.segura413@gmail.com`.
- `commit.gpgsign = false` per-repo.
- Conventional Commits for every commit.
- No force-pushes to `main`.
- No AI/LLM attribution anywhere.
