# .ci — CI orchestration layer

This directory owns **every operation that acts on more than 1 image** in the
gophersys/.devcontainer repository. Each image has its own directory `<name>/`
with its own `ctl.sh` + `project.json` + `Dockerfile`. The repository-level
`ctl.sh` delegates to those per-image scripts. This layer is 1 level above them.

**`.ci/ctl.sh` holds 1 verb, and no workflow calls it.** This sentence
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
├── ctl.sh              1 verb: validate, delegated to the repository-root ctl.sh
├── smoke.sh            the HOST driver — classifies every pin, resolves it, drives 1 docker run
├── image-checks.sh     the GUEST checks — the comparator + the functional groups
├── affected.sh         which images a commit changes — the input table, 1 home
├── buildx-node.sh      the builder every image build uses; owns the arm64 switch
├── mirror-buildkit.sh  keeps ghcr.io holding the pinned BuildKit index the builder boots from
├── notify-failure.sh   the 1 labelled issue a scheduled run opens, comments on and closes
├── ghcr-retention.sh   what may be deleted from ghcr.io, and what may never be
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
a tool lives in the IMAGE. The driver reads `versions.env` for every image, and
for a CHILD image it reads that image's own Dockerfile as a second pin home. It
classifies every pin of every home it reads
`asserted` / `not-a-version` / `not-in-this-image` against the table that home
carries, and sends the guest file, the
fixtures and the assertion table into the container in 1 stdin stream. The guest
compares what each tool REPORTS against the pin, then exercises the gate-critical
tools on the fixtures. `image-checks.sh` also runs on a host against a stub PATH,
which is how `_ctl/tests/guest-checks.test.sh` tests the comparator at pull
request time.

**`not-in-this-image` carries its own probe.** The class field takes an optional
`:<binary>[,<binary>...]` suffix, and the guest asserts `! command -v <binary>`
for each one. Without it the class was an assertion nobody checked: on
2026-08-17 `ghcr.io/gophersys/base:latest` held `/usr/local/bin/terraform` and
`/usr/local/bin/aws` while `base/Dockerfile` installs neither, and no check here
could report it. The driver refuses to run an image whose whole table names no
probe.

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
| `help`                  | Show the inline verb index                                  |

**`build-all`, `push-all` and `smoke-test-all` stood in that table and are
DELETED.** No workflow and no script called any of the 3 — the grep that says so
covers `.github/workflows/`, `.ci/providers/` and every `*.sh` in the repository,
and it found each name only in `.ci/ctl.sh`, in `.ci/project.json` and in this
file. Each verb looped `BUILD_ORDER` unconditionally, which is the opposite of
the affected-only rule below: `push-all` would have pushed all 5 images whatever
`.ci/affected.sh` said. A verb nothing invokes is a capability the usage block
advertises and nobody maintains, and this one advertised a way past the gate.

`validate` stays. It is the 1 verb here with a caller who is not a workflow — a
developer running the pull request gate locally — and its body is the
repository-root one, delegated.

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

To smoke 1 image on a personal computer, call the driver the workflow calls:
`bash .ci/smoke.sh <image> [ref]`.

## Nx integration

`.ci/project.json` exposes the verb as an Nx target:

```
nx run ci-devcontainer:ci-.devcontainer-validate
```

It does not cache, and neither does any target of this repository. The reason is
in `.claude/rules/00-identity.md`, "Nx caching": these verbs discover their file
set at runtime, so no static `inputs` list can be complete. The list that stood
on the root `validate` target missed 32 tracked files the verb reads, and the
list that stood on this target repeated the fault.

## Why this layer is separate

This section used to argue that the repository needed 1 place for an operation
on **all** the images as a set, and that `.ci/ctl.sh` was that place. The
argument was refuted by the affected-only rule, and the 3 aggregate verbs it
justified are deleted.

**The unit of a CI run is 1 image.** Each job of `build-and-push.yml` gates its
build, its smoke and its push on `bash .ci/affected.sh <image>`, so an operation
that walks the whole set unconditionally is not a shortcut for what CI does — it
is the opposite of it. A local developer who wants CI's behaviour calls the same
purpose-built script CI calls, for the 1 image they changed.

What this directory owns is therefore the SCRIPTS, not an aggregate verb: which
images a commit affects, the builder, the BuildKit mirror, the smoke driver and
its guest half, the failure notifier, the retention policy, and the provider
YAMLs that are the source of truth for each CI system. `ctl.sh` keeps `validate`
alone, because that 1 gate really does act on the whole tree at once.

## Retention is the one aggregate script, and it says why

`ghcr-retention.sh` walks every image of `images.yaml` in a single run, which
reads like the opposite of the affected-only rule above. It is not: the unit of
a BUILD is 1 image because a commit changes 1 image, and the unit of a PRUNE is
the whole registry because the protected set is computed from things that live
OUTSIDE any one image — a consumer's submodule pointer, a digest pinned in
`gophersys/infrastructure`. There is no per-image gate that could answer "is
this version pinned", so there is nothing to gate per image.

It is also the 1 script here whose failure mode is destructive, so its whole
design is about refusing to act on a read it could not make. An untagged version
in this registry is almost always the live child of a tag — 225 of 225 on `base`,
measured 2026-08-26 — so the prune every retention example performs would delete
the content of the tags it is keeping. The file's header carries the
measurements, the 6 protection classes and the reason each one is not optional.

`bash .ci/ghcr-retention.sh [image...]` dry runs and deletes nothing.
`RETENTION_MODE=enforce` is what makes it act.
