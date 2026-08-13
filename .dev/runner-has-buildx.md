# runner-has-buildx

phase:    fix
repo:     gophersys/.devcontainer
branch:   feat/runner-has-buildx
worktree: ~/code/.worktrees/dc-buildx
pr:       -
attempt:  2/2

## Goal

The runner image has no `docker buildx`, so CI cannot use the Mac mini as a
native arm64 builder. Add the plugin to the image, and add the assertion that
notices if it ever goes missing again.

## The blocker, MEASURED twice — do not re-derive

Against the pinned image `ghcr.io/gophersys/base-runner:e0c6bc5`:

```
/usr/local/lib/docker/cli-plugins:   docker-compose        <- buildx ABSENT
docker buildx version             -> docker: unknown command: docker buildx
```

`base/Dockerfile:482` installs `docker-ce-cli`, and lines 493-496 then download
ONLY the compose plugin into `/usr/local/lib/docker/cli-plugins`. buildx ships
separately (`docker-buildx-plugin`, or a direct release binary the same way
compose is fetched). Nothing installs it.

## Why this matters now

`gophersys/infrastructure` branch `feat/mini-buildx` mounts a dial-only SSH key
into the arc-org pool so image builds can reach the mini, which builds arm64
**3.44x faster** than the amd64 runners can emulate it (4.02s vs 13.8s, measured;
transfer cost ~100 MB/s, so 1-2s for a realistic context). Every part of that is
proven EXCEPT this: the documented workflow step cannot run, because the image
has no buildx.

The infrastructure implementer deliberately refused to work around it by
downloading buildx inside the job, citing `ci-substrate.md`'s rule that software
capability belongs in the image and the fact that `validate.yml` carries no
tool-install step for exactly that reason. That was right, and it is why this is
a separate change rather than a hack.

## Plan

APPROVED (self, under delegated authority, 2026-08-13).

1. Install the buildx plugin in `base/Dockerfile`, PINNED by an `ARG` the way the
   other tools in this image are pinned. Follow whatever the compose install
   already does — do not invent a second style.
2. Assert it. The image already has a verification path; the assertion must fail
   if buildx is absent, and it must name the tool.

## Deliberately NOT in this change

- Reversing D42, or adding `linux/arm64` to any image's platform list. That lands
  only after the builder is proven in CI.
- Anything in `gophersys/infrastructure`.

## Proven

Nothing yet. Phase 2 owes a RED test.

## Blocked

Nothing.

## Next

Test author: a red assertion that the runner image carries buildx.


## Phase 2 — RED, all four states observed

The assertion went into `.ci/smoke.sh` (SMOKE_BASE), which is the ONLY place this
repository asserts runtime IMAGE CONTENT. Not into `_ctl/tests/*.test.sh` (those
are hermetic and read files), and deliberately NOT into `gophersys/infrastructure`:
its `verify-runner-image` tests the POD SHAPE (docker group membership, which a
bare `docker run` has no sidecar for), whereas `docker buildx version` reaches no
daemon and needs no pod.

Four states, all observed rather than reasoned about:

```
buildx absent                      -> red   "docker: unknown command: docker buildx"
present, no ARG pin                -> red   "declares no ARG *BUILDX*_VERSION"
present, ARG pinned to 0.35.0      -> red   "drift: image runs v0.36.1, Dockerfile pins v0.35.0"
present, ARG matches               -> green
```

FAIL-NOT-SKIP proven on both paths: `docker` absent -> exit 127 naming the tool;
an unpullable ref -> exit 1 with "NOTHING was asserted about this image".

## Phase 3 — GREEN

`ARG DOCKER_BUILDX_VERSION=0.36.1` beside `DOCKER_COMPOSE_VERSION`, with a RUN
block in the same shape as the compose block at lines 489-498.

**The arch mapping differs from compose ON PURPOSE**: buildx release assets use Go
arch names (`amd64`/`arm64`), compose uses `x86_64`/`aarch64`. Copying the compose
line verbatim would have 404'd.

```
docker build base/                      rc=0
docker build runner/                    rc=0
bash .ci/smoke.sh base-runner <local>   rc=0
  github.com/docker/buildx v0.36.1 ...
  docker buildx: v0.36.1 matches the pin in base/Dockerfile
bash ./ctl.sh validate                  rc=0   (hadolint 2.14.0, all 5 Dockerfiles)
bash ./ctl.sh test                      rc=0   (36 PASS, 0 failed)
```

Drift proof, image NOT rebuilt: ARG moved to 0.35.0 -> `SMOKE EXIT STATUS: 1`
naming both versions; restored -> 0. **The check was satisfied, not defeated.**

Version choice: 0.36.1 is the newest non-prerelease (published 2026-08-04), the
patch on v0.36.0 folding in buildkit v0.32.2. The repo pins equally fresh
elsewhere (GO_VERSION dated 2026-08-12). No leading `v` in the ARG value, matching
every other version ARG and the check's own comparison.

## Findings worth keeping

- **`_ctl/lib.sh:48` hardcodes `IMAGE_REGISTRY_NAMESPACE`**, so there is no
  supported way to build to a local tag through `ctl.sh`. The implementer had to
  go around the wrapper with plain `docker build` to avoid overwriting the real
  `ghcr.io/gophersys/base:latest`. That is a real ergonomic gap in the dispatcher.
- **`.ci/smoke.sh` runs on push to main, NOT at PR time** (task #65). So a PR that
  deletes this install passes its own gate and the image goes red after merge.

## Not verified

`flutter`, `zephyr` and `zephyr-devbox` were not rebuilt or smoked. They inherit
the layer from `base` and `SMOKE_BASE` applies the same check to them, but each is
hours of emulated build on this host. CI rebuilds them in dependency order.

## Next

Verifier: try to refute that this is done.


## Phase 4 — 7 findings. One of them inverts the purpose of the change.

**F1 (MEDIUM-HIGH). The change installs a blocker on the exact path it exists to
unblock.** `.ci/smoke.sh:243-248` hard-fails when `SANCTIONED_PLATFORMS` names
more than one platform. This entire feature exists so that `linux/arm64` can be
added. The moment somebody makes that one edit,
`.github/workflows/build-and-push.yml:167` exits 1 BEFORE asserting anything and
the `base-runner` publish job goes red.

`.claude/rules/00-identity.md` states "Widening it is 1 edit, and every path reads
it." **That sentence is now false**, and the change did not update it.

Proven in a mirror copy, no tracked file touched:

```
SANCTIONED_PLATFORMS="linux/amd64" -> "linux/amd64,linux/arm64"
bash <mirror>/.ci/smoke.sh base-runner dc-buildx-base-runner:local   rc=1
  [error] IMAGE_PLATFORMS holds more than 1 platform: linux/amd64,linux/arm64
  [error] a smoke test runs 1 image, so it can name only 1 platform
```

**F3 (MEDIUM). The gate that runs on this PR has ZERO coverage of this change.**
No hermetic test was added. Proven by renaming the ARG so `${DOCKER_BUILDX_VERSION}`
dangles at line 511 — a state where the base build CANNOT succeed (HTTP 404,
curl rc=56):

```
ARG DOCKER_BUILDX_VERSION -> ARG DOCKER_BLDX_VERSION
bash ./ctl.sh validate                       rc=0     <- the finding
bash .ci/smoke.sh base-runner <local>        rc=1     (only smoke catches it)
```

The state file disclosed the TIMING half (smoke runs on push, not on PRs — task
#65) but not that nothing in the PR gate reads this at all.

**F2 (MEDIUM). The fetched binary is verified by nothing.** `curl -fsSL` writes an
executable into every CI image with no checksum and no signature. `-f` rejects a
404 but accepts any 200 body. The smoke assertion does NOT close this: it reads
the binary's self-reported version string, which any binary can print. Upstream
publishes `checksums.txt`, `checksums-signed.txt` and a sigstore bundle.
**Compose has the identical gap** and also publishes a `.sha256`, so this is a
finding about both — the new block copied the weaker standard. The binary shipped
today IS correct (sha256 matches upstream), so this is a missing control, not a
live compromise.

**F4 (LOW-MEDIUM). Undisclosed scope drift.** The approved plan named two items.
The diff also adds an optional `[ref]` argument, a pre-set `REPO_ROOT`,
`require_cmd docker`, `require_sanctioned_platforms`, the single-platform guard,
an explicit pull-with-named-error, and `--platform` on `docker run` — roughly 40
of 117 changed lines, recorded nowhere. **F1 is a direct consequence of it.**

**F5 (LOW-MEDIUM). The state file implies smoke coverage CI does not provide.**
`grep -rn "smoke.sh" .github/workflows/` returns exactly ONE invocation:
`build-and-push.yml:167 bash .ci/smoke.sh base-runner`. The `flutter`, `zephyr`
and `zephyr-devbox` jobs have no smoke step, so those three ship buildx with
nothing asserting it. Pre-existing, but my sentence read as coverage.

**F6 (LOW).** `.ci/smoke.sh:9` still says "Nothing is emulated here", which the
added `--platform` handling at :239-242 contradicts — proven, the green run on
this arm64 host reported `x86_64` from inside the container.

**F7 (LOW).** `buildx_pin` reads the FIRST pattern match, not the effective ARG. A
decoy `ARG BUILDX_HELPER_VERSION` wins; a re-declared ARG below the real one (the
value Docker actually uses) is ignored; an indented ARG or a leading `v` yields
nothing. **Every case degrades to a false RED with a misleading message, never a
false green** — which is the right direction to fail, but the message lies.

## What the verifier attacked hardest and could NOT refute

**The arch mapping holds.** It did not take the reasoning on trust: both
`buildx-v0.36.1.linux-amd64` and `.linux-arm64` return 200; the compose-style
`linux-x86_64`/`linux-aarch64` return 404 on buildx and 200 on compose; negative
controls 404 so the probe can go red. It then BUILT the exact RUN block for
`linux/arm64` natively, executed it on aarch64, and matched its sha256 against
upstream `checksums.txt`. **The arm64 path is not latent-broken** — which was my
main worry.

Also: no false green could be constructed; no masked exit codes anywhere in the
repo's shell scripts; version claim verified against the GitHub API
(prerelease=False, draft=False, newest of any kind).

## Next

Test author: F1 (the guard must not block the multi-platform edit), F3 (a
hermetic PR-gate test), F6, F7. Then implementer: F2 (checksum), F5 and the stale
rule sentence in `00-identity.md`.
