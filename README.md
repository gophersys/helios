# .devcontainer

Shared base container images for every project in the brain ecosystem.

Each image here serves two roles:

- **Local dev environment.** Projects reference these via the standard
  `.devcontainer/` convention (VS Code / JetBrains Gateway / devpod / etc.).
- **CI runtime.** The GitHub Actions workflows in each project monorepo
  run `nx affected` inside these same images, so local and CI execute in
  an identical environment.

This repo has **no Nx workspace of its own**. It is consumed as a submodule
by every project monorepo; the parent provides the Nx runtime. Each image
follows the `project.json` + `ctl.sh` pattern enforced across the
ecosystem.

## Image inventory

| Image | Contents | Base |
|---|---|---|
| `ghcr.io/gophersys/base` | `ubuntu:24.04`, bash, git, curl, jq, shellcheck, openssh-client, Bitwarden CLI, non-root `dev` user (uid 1000) | `ubuntu:24.04` |
| `ghcr.io/gophersys/node` | Node.js LTS via `nvm`, corepack-managed `yarn` + `pnpm` | `base` |
| `ghcr.io/gophersys/python` | Python 3.12 via `uv` | `base` |
| `ghcr.io/gophersys/go` | Go toolchain from the official `go.dev` tarball | `base` |
| `ghcr.io/gophersys/rust` | Rust `stable` via `rustup`, `rustfmt`, `clippy`, build-essential | `base` |
| `ghcr.io/gophersys/flutter` | Flutter stable SDK, JDK 17, Android build deps | `node` |
| `ghcr.io/gophersys/zephyr` | west, Zephyr SDK (arm-zephyr-eabi + riscv64-zephyr-elf), Zephyr host deps | `python` |

## Dependency graph

```
            base
      ┌──────┼──────┬──────┐
      │      │      │      │
    node  python   go    rust
      │      │
      │      │
   flutter zephyr
```

This is also the order the top-level `build-all` walks.

## Using an image

Pull directly:

```sh
docker pull ghcr.io/gophersys/python:latest
```

As a VS Code devcontainer (inside a consuming project):

```jsonc
// .devcontainer/devcontainer.json
{
  "image": "ghcr.io/gophersys/python:latest",
  "remoteUser": "dev"
}
```

As a GitHub Actions job container:

```yaml
jobs:
  build:
    runs-on: ubuntu-latest
    container:
      image: ghcr.io/gophersys/node:latest
    steps:
      - uses: actions/checkout@v4
      - run: npx nx affected -t build
```

## Repo layout

```
.devcontainer/
├── README.md
├── project.json                 # repo-level Nx wiring (build-all, push-all, list, validate, propagate)
├── ctl.sh                       # repo-wide control script
├── .claude/rules/               # identity + conventions for this repo
├── images/
│   ├── base/    { Dockerfile, project.json, ctl.sh }
│   ├── node/    { Dockerfile, project.json, ctl.sh }
│   ├── python/  { Dockerfile, project.json, ctl.sh }
│   ├── go/      { Dockerfile, project.json, ctl.sh }
│   ├── rust/    { Dockerfile, project.json, ctl.sh }
│   ├── flutter/ { Dockerfile, project.json, ctl.sh }
│   └── zephyr/  { Dockerfile, project.json, ctl.sh }
└── .github/workflows/build-and-push.yml
```

Every image is a self-contained Nx project: `project.json` wires the Nx
targets (`build`, `push`, `pull`, `inspect`); `ctl.sh` is the bash source
of truth. Nx is a wrapper; `bash ./ctl.sh <cmd>` works directly with or
without the Nx runtime.

## Day-to-day operations

From the repo root:

```sh
# Build every image in dependency order.
bash ./ctl.sh build-all

# Push every image to ghcr.io/gophersys/<name>.
bash ./ctl.sh push-all

# List canonical image refs.
bash ./ctl.sh list

# Lint shell scripts, validate JSON, lint Dockerfiles (if hadolint present).
bash ./ctl.sh validate
```

From a parent monorepo with Nx available:

```sh
nx run images-base:build
nx run images-node:build     # builds base first via dependsOn
nx run devcontainer:build-all
```

Per-image:

```sh
cd images/python
bash ./ctl.sh build
bash ./ctl.sh push
bash ./ctl.sh inspect
```

## Adding a new image

1. Create the directory: `images/<name>/`.
2. Write three files:
   - `Dockerfile` — `FROM` an existing image in this repo (or `ubuntu:24.04`
     for a new root); add the tool; clean apt lists; set `LABEL
     org.opencontainers.image.source`.
   - `project.json` — copy an existing image's project.json, rename, and
     add a `dependsOn` entry pointing at the image's parent.
   - `ctl.sh` — copy an existing image's ctl.sh and change the
     `IMAGE_NAME` constant. `chmod +x` it.
3. Add the name to `BUILD_ORDER` in the repo-root `ctl.sh`, placed so
     parents come first.
4. Add the image to the matrix in `.github/workflows/build-and-push.yml`
     and ensure its `depends_on` in the `needs:` field matches.
5. Run `bash ./ctl.sh validate` until clean, then `bash ./ctl.sh build-all`
     to prove the chain still builds end to end.
6. Commit. Open a PR. After merge, the workflow publishes `:latest` and
     `:<short-sha>` tags.

## Shared-change propagation

This repo is consumed by every project monorepo via submodule. After a
change lands on `main`, consuming projects still pin the previous commit
until someone explicitly bumps their submodule pointer.

The propagation flow is owned by the parent brain repo:

```sh
# From within brain:
bash brain/.claude/scripts/propagate.sh .devcontainer
```

or, equivalently from this repo when invoked through brain's submodule:

```sh
bash ./ctl.sh propagate
```

Propagation is an approval-gated operation — it fans out the pointer bump
to every consuming project, runs each project's smoke test, and rolls
back on failure. See `brain/.claude/rules/operations/shared-change-propagation.md`.

## CI

`.github/workflows/build-and-push.yml` builds and publishes every image
on every push to `main`, tagged with both `latest` and the short commit
SHA. Requires the `packages: write` permission (configured in the workflow).
