# .ci — CI orchestration layer

This directory owns **every operation that acts on more than 1 image** in the
gophersys/.devcontainer repository. Each image has its own directory `<name>/`
with its own `ctl.sh` + `project.json` + `Dockerfile`. The repository-level
`ctl.sh` delegates to those per-image scripts. This layer is 1 level above
them. Use only this layer in a CI pipeline YAML.

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

Every verb has the same shape. There is no environment variable and no flag.
The verb is the interface.

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

`.ci/project.json` also exposes every verb as an Nx target:

```
nx run ci-devcontainer:ci-.devcontainer-validate
nx run ci-devcontainer:ci-.devcontainer-build-all
nx run ci-devcontainer:ci-.devcontainer-build-all-multi-arch
nx run ci-devcontainer:ci-.devcontainer-push-all
nx run ci-devcontainer:ci-.devcontainer-smoke-test-all
```

## Why this layer is separate

In the past each image had its own `ctl.sh`, and the repository-level `ctl.sh`
delegated to them. That structure works for an operation on 1 image
(`build base`, `push flutter`). It gives no place for an operation that acts on
**all** the images as a set. CI must do such an operation on every push to
`main`.

`.ci/ctl.sh` supplies that place. It knows the dependency order. It knows that
`push-all` does `buildx --push` on all 3 images and fails if 1 image fails. It
knows that the smoke test after the build is not the same as the build of 1
image. It is the contract that a CI pipeline uses. It is also the contract that
a local developer uses to get the same behavior as CI on a personal computer.
