# drop-arm64

phase:    green
repo:     gophersys/.devcontainer
branch:   feat/drop-arm64
worktree: ~/code/.worktrees/dc-drop-arm64
pr:       -
attempt:  0/2

## Goal

Stop publishing an arm64 variant of every devcontainer image. The published
linux/arm64 base image is an amd64 Ubuntu userland carrying aarch64 Go binaries,
so it is mislabelled rather than native, and it emulates its userland anyway on
the only host that would consume it. It therefore delivers none of the benefit of
a native image while costing the larger half of a 41.7-minute build.

When this is done, every image builds and publishes amd64 only, no document
claims otherwise, and a future edit that re-adds arm64 fails loudly at the guard
instead of quietly restoring an emulated build.

## Plan

APPROVED. Mateo approved the scope change on 2026-08-12.

**Scope grew by 1 line, for a measured reason.** The Go toolchain bump belongs
here, not in the libs feature where it was first filed. `GO-2026-5856` is
CVE-2026-42505, an ECH privacy leak in `crypto/tls`. It is a Go TOOLCHAIN bug,
not a dependency, it is reachable and genuinely called in 5 libraries, and the
whole fix is `ARG GO_VERSION` 1.26.4 -> 1.26.5 in `base/Dockerfile:59`.

That file is this feature's. Two features editing one file is what the ownership
model exists to prevent. Both changes also require republishing the base image,
which is the 41.7-minute cost, and this feature is what halves it. Splitting them
pays that twice and leaves a window where the image is architecture-correct and
still ships a vulnerable toolchain.

### Verified by the planner before planning on it

Every audit claim was re-checked. 2 were wrong in my favour and 3 facts were new:
- `build-multi-arch` is referenced from **24** sites, not the ~13 I passed it.
- `.ci/providers/github/build-and-push.yml` has ALREADY drifted from the
  workflow: 5 missing `timeout-minutes: 90` blocks, from commit d9089b2. The
  identity rule calls the 2 files byte-for-byte identical and nothing checks it.
  Surfaced, not caused.
- A single-platform push still publishes an OCI index, so a manifest-reading
  check will not break after the drop.
- `.ci/ctl.sh` and `.ci/smoke.sh` are linted by nothing today.

### The change

One declaration, one membership rule, every path through it.

- `_ctl/lib.sh`: `SANCTIONED_PLATFORMS="linux/amd64"` as the single source of
  truth; `MULTI_ARCH_PLATFORMS` renamed to `IMAGE_PLATFORMS`; a tripwire that
  fails if the old name is still set, because both values are now the same string
  and a missed rename would otherwise be invisible.
- The guard is SPLIT, not deleted. 3 of its 4 conditions have nothing to do with
  arm64 and are the only protection `push` has. `require_sanctioned_platforms`
  adds a NEW condition: any platform outside the sanctioned set fails and names
  itself, so a future edit that re-adds arm64 fails loudly instead of quietly
  restoring an emulated build.
- `image_build` gains an explicit `--platform`, closing the most likely silent
  breakage: a bare `docker build` on an Apple Silicon host currently targets
  arm64.
- `base/Dockerfile:27` -> plain `FROM ubuntu:24.04`. This is the MECHANICAL CAUSE
  of the mislabelled image; removing arm64 without it reproduces the same defect
  in the opposite direction on a Mac.
- `base/Dockerfile:59` -> `ARG GO_VERSION=1.26.5`.
- The 18 TARGETPLATFORM case blocks STAY. The planner argued for keeping them.
- `build-multi-arch` deleted from all 24 sites; new `verify-published` verb
  asserts the published manifest carries exactly the sanctioned set.
- Every document that would become untrue is rewritten.

## Proven — phase 2, red

3 hermetic test files under `_ctl/tests/`, run directly with `bash <file>` because
no runner exists yet; exit status read on its own line, never through a pipe.

  platform-policy.test.sh   10 checks, 6 failed
  guard.test.sh             11 checks,  2 failed (+5 conservation guards, green)
  verify-published.test.sh   6 checks,  5 failed

The 2 guard reds are the new rule: with `IMAGE_PLATFORMS=linux/amd64,linux/arm64`
the push is ACCEPTED today and exits 0. The log line also revealed that
`IMAGE_PLATFORMS` is ignored entirely right now — the baseline run pushed
`linux/amd64,linux/arm64` even with the variable set to amd64.

The 5 conservation guards are GREEN from the first run and say so. Their power is
proven by counter-stimulus: 2 baselines exit 0, and each guard flips exactly 1
variable and exits non-zero.

`verify-published` fails with "the verb does not exist yet" in those words, rather
than a shell error a reader would misdiagnose. Satisfiability proved outside the
repository with 3 throwaway implementations: a correct one passes 6 of 6; one that
COUNTS manifest entries fails only the attestation check; one that says "no
variants found" on a read failure fails only that check.

**The test author caught and removed 2 FALSE PASSES of its own before committing** —
a check that passed on an accepted push because the info log prints the platform
string, and 2 that passed because an unknown verb exits non-zero while printing a
usage block containing `linux/arm64`. A status and its message are now 1 check.

**Pre-existing, surfaced not caused:** `.ci/providers/github/build-and-push.yml`
differs from the workflow by 5 `timeout-minutes: 90` blocks, from commit d9089b2,
while `.claude/rules/00-identity.md` calls the 2 byte-for-byte identical. Nothing
checked it before this file.

`shellcheck -x -S style` clean on all 6 shell files.

## Proven — phase 0

- Measured on ghcr.io/gophersys/base:e0c6bc5 by running each manifest variant:
  amd64 -> uname x86_64, dpkg amd64, gofumpt ELF x86-64, consistent.
  arm64 -> uname x86_64, dpkg amd64, gofumpt ELF aarch64, MIXED.
- The Go tools in the arm64 variant execute on an Apple Silicon host, because the
  host runs the aarch64 binaries natively while Docker Desktop emulates the amd64
  userland. That is why nobody saw this.
- base-runner and zephyr-devbox are already amd64 only by earlier measured
  decisions, and are NOT defects.

## Blocked

Nothing.

## Seams the implementer must honour

The test author named 4 contracts. Breaking any makes a test undrivable:
1. the platform list stays OVERRIDABLE from the environment
   (`: "${IMAGE_PLATFORMS:=$SANCTIONED_PLATFORMS}"`), the shape
   `MULTI_ARCH_PLATFORMS` has today. A hard assignment makes the 2 new guard
   checks impossible to drive.
2. `verify-published` is a PER-IMAGE verb, reached as
   `bash base/ctl.sh verify-published`, and it appears in the usage block.
3. the manifest is read with `docker manifest inspect` OR
   `docker buildx imagetools inspect --raw` — the stub models both.
4. the old-name tripwire fires at SOURCE time on the variable being SET, not
   inside the guard on its value.

## Next

Phase 3: dev-implementer makes the 13 red checks green, then COMMIT before
phase 4.
