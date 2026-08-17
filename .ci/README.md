# .ci — CI orchestration layer

This directory owns **every operation that acts on more than 1 image** in the
gophersys/.devcontainer repository. Each image has its own directory `<name>/`
with its own `ctl.sh` + `project.json` + `Dockerfile`. The repository-level
`ctl.sh` delegates to those per-image scripts. This layer is 1 level above them.

**`.ci/ctl.sh` is the LOCAL aggregate, and no workflow calls it.** This sentence
used to read "it is the only entrypoint that should appear in a CI pipeline
YAML", and the grep says otherwise: `.github/workflows/` executes
`.ci/affected.sh`, `.ci/mirror-buildkit.sh`, `.ci/buildx-node.sh`,
`.ci/smoke.sh` and `.ci/notify-failure.sh` directly, plus the repository-root
`./ctl.sh verify-published`. The only mention of `.ci/ctl.sh` in a workflow is
`validate.yml`, which `grep`s the file for `BUILD_ORDER` and never runs it. Each
job calls the purpose-built script it needs, because a job gates each step on
`.ci/affected.sh` and an aggregate verb cannot be gated per image.

## Layout

```
.ci/
├── ctl.sh              bash orchestration (validate/build/push/smoke across all images)
├── smoke.sh            the HOST driver — classifies every pin, resolves it, drives 1 docker run
├── image-checks.sh     the GUEST checks — the comparator + the functional groups
├── affected.sh         which images a commit changes — the input table, 1 home
├── buildx-node.sh      the builder every image build uses; owns the arm64 switch
├── mirror-buildkit.sh  keeps ghcr.io holding the pinned BuildKit index the builder boots from
├── notify-failure.sh   the 1 labelled issue a scheduled run opens, comments on and closes
├── fixtures/           what the functional checks read: a Go module, a Dockerfile,
│                       a compose file, a proto and its buf module
├── trivyignore.yaml    the CVE waivers, each with a statement and an expiry
├── project.json        Nx wrappers around each ctl.sh verb (ci-.devcontainer-*)
├── README.md           this file
└── providers/          CI-system shim YAMLs — source of truth for each provider
    ├── README.md
    └── github/         ← each file is copied to .github/workflows/, byte for byte
        ├── build-and-push.yml
        ├── security-nightly.yml
        └── weekly-bumps.yml
```

`smoke.sh` and `image-checks.sh` are 2 files because a pin lives on the HOST and
a tool lives in the IMAGE. The driver reads `versions.env` (the cloud family) or
the ARGs at the top of `base/Dockerfile` (the base family), classifies every pin
`asserted` / `not-a-version` / `not-in-this-image`, and sends the guest file, the
fixtures and the assertion table into the container in 1 stdin stream. The guest
compares what each tool REPORTS against the pin, then exercises the gate-critical
tools on the fixtures. `image-checks.sh` also runs on a host against a stub PATH,
which is how `_ctl/tests/guest-checks.test.sh` tests the comparator at pull
request time.

The provider file is a **copy**, not a symlink, and the 2 must stay byte-for-byte
identical. They have drifted twice. `_ctl/tests/platform-policy.test.sh` compares
them with `cmp` now, and `bash ./ctl.sh test` runs it in the pull request gate.

## Invocation contract

Every verb has the same shape. There is no environment variable and no flag.
The verb is the interface.

```
bash .ci/ctl.sh <verb>
```

| Verb                    | What it does                                                |
|-------------------------|-------------------------------------------------------------|
| `validate`              | shellcheck + hadolint + jq across the whole tree            |
| `build-all`             | Build every image, parent first, in `BUILD_ORDER`           |
| `push-all`              | GUARDED push of every image to ghcr.io. **Local only** — see below |
| `smoke-test-all`        | Run `smoke.sh` against each image after a local build       |
| `help`                  | Show the inline verb index                                  |

`build-all` and `push-all` walk `BUILD_ORDER` in `.ci/ctl.sh`, which holds all 5
images. Do not restate that chain here: this table used to say
"(base → flutter → zephyr)" while the same file said "All 5 that it builds" 30
lines lower, so the file disagreed with itself.

**`push-all` is a local verb and no workflow runs it.** It loops `BUILD_ORDER`
unconditionally, so it would push all 5 images whatever `.ci/affected.sh` says,
which is the opposite of the affected-only rule the publishing workflow obeys.
Each job of `build-and-push.yml` pushes the 1 image it just built and smoked.

## Which images CI smokes

**All 5 that it builds.** Every job of `.github/workflows/build-and-push.yml`
has the same shape, and the order is the property:

```
build with push: false + load: true   →   bash .ci/smoke.sh <image> <image>:smoke   →   push from the cache
```

The ref the smoke runs is the LOADED local image, so the check happens **before**
anything reaches ghcr.io. A push cannot be undone and no job here rolls one back,
which is why a check that runs after it reports a broken image but cannot stop
one from reaching a consumer. `_ctl/tests/publish-order.test.sh` holds that order
in the pull request gate, for both copies of the workflow.

A job builds only when `bash .ci/affected.sh <image>` says the commit changes
that image's inputs, and the smoke is inside that gate with the build and the
push. Nothing publishes unsmoked: the 3 move together, and an image that did not
build did not ship.

`base-runner` was the 6th, and it is retired — the ARC pools run `cloud`, so
nothing builds it. Its `content-runner` check group stayed: `cloud` carries the
runner layer, so those checks run against the image that ships it today.

`smoke-test-all` runs `smoke.sh` against every image in 1 command, for a local
loop. No workflow calls it: each job smokes the image it just built.

## Nx integration

`.ci/project.json` also exposes every verb as an Nx target:

```
nx run ci-devcontainer:ci-.devcontainer-validate
nx run ci-devcontainer:ci-.devcontainer-build-all
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
`push-all` does `buildx --push` on every image and fails if 1 image fails. It
knows that the smoke test after the build is not the same as the build of 1
image. It is the contract a local developer uses to get CI's behaviour on a
personal computer, in 1 command.

**A CI pipeline does not use it, and the reason is the affected-only rule.** A
workflow job gates its build, its smoke and its push on
`bash .ci/affected.sh <image>`, so the unit CI works in is 1 image and not the
set. The aggregate verbs stay for the local loop; the workflow calls the
individual scripts of this directory.
