# .ci — CI orchestration layer

This directory owns **everything that spans more than one image** in the
gophersys/.devcontainer repo. Individual images live under `<name>/`
and each carries its own `ctl.sh` + `project.json` + `Dockerfile`. The
repo-level `ctl.sh` delegates to those per-image scripts. This layer sits one
level above that and is the only entrypoint that should ever appear in a CI
pipeline YAML.

## Layout

```
.ci/
├── ctl.sh              bash orchestration (validate/build/push/smoke across all images)
├── smoke.sh            post-build native-arch smoke test — one script, image arg
├── project.json        Nx wrappers around each ctl.sh verb (ci-.devcontainer-*)
├── README.md           this file
└── providers/          CI-system shim YAMLs — source of truth for each provider
    ├── README.md
    └── github/
        └── build-and-push.yml   ← symlinked into .github/workflows/
```

## Invocation contract

Every verb is shape-stable — no env vars, no flags. The verb IS the interface.

```
bash .ci/ctl.sh <verb>
```

| Verb                    | What it does                                                |
|-------------------------|-------------------------------------------------------------|
| `validate`              | shellcheck + hadolint + jq across the whole tree            |
| `build-all`             | Native single-arch build of every image (base → flutter → zephyr) |
| `build-all-multi-arch`  | Explicit multi-arch build of every image (no push)          |
| `push-all`              | ENFORCED multi-arch push of every image to ghcr.io          |
| `smoke-test-all`        | Run `smoke.sh` against each image after a local build       |
| `help`                  | Show the inline verb index                                  |

## Nx integration

All verbs are also exposed as Nx targets in `.ci/project.json`:

```
nx run ci-devcontainer:ci-.devcontainer-validate
nx run ci-devcontainer:ci-.devcontainer-build-all
nx run ci-devcontainer:ci-.devcontainer-build-all-multi-arch
nx run ci-devcontainer:ci-.devcontainer-push-all
nx run ci-devcontainer:ci-.devcontainer-smoke-test-all
```

## Why a separate layer?

Historically each image had its own `ctl.sh` and the repo-level `ctl.sh`
delegated to those. That works for per-image operations (`build base`,
`push flutter`) but provides no place for operations that act on **all**
images as a set — which is exactly what CI needs to do on every push to `main`.

`.ci/ctl.sh` fills that gap: it knows the dependency order, it knows that
`push-all` means "buildx --push all three, fail on any", and it knows the
post-build smoke test is not the same as the per-image build. It is the
contract CI pipelines consume. It is also the contract local devs consume
when they want to mirror the CI behavior on their own laptop.
