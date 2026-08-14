# runner-has-buildx

phase:    pr
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


## Phase 5 — F1, F3, F6, F7 closed (`8963e06`)

**F1 — a RESOLVER, not a refusal.** A smoke test does run one image, so it names
one platform; the defect was the conclusion drawn from that. It now SELECTS, in
order, and never runs on an unnamed platform:

```
SMOKE_PLATFORM when named   (and it must still be in the sanctioned list —
                             a choice WITHIN the guard, not around it)
else the DOCKER DAEMON's platform, when the list holds it
else the only entry
else FAIL, naming both the list and the daemon
```

It reads the **daemon**, not `uname -m`, because on Docker Desktop the host is
darwin while the daemon is linux. Consequence: the moment a second architecture is
sanctioned, the amd64 runner smokes amd64 and the arm64 builder smokes arm64, each
natively, with no further edit here.

Proven the same way it was proven broken — mirror copy, list widened to two:

```
SMOKE_PLATFORM=linux/amd64 ...   SMOKE EXIT STATUS: 0    <- was rc=1, asserting nothing
no override                      picks the daemon (linux/arm64), natively
SMOKE_PLATFORM=linux/riscv64     rc=1  not in IMAGE_PLATFORMS
list without the daemon's arch   rc=1  cannot choose a platform to smoke
```

The guard is not deleted: an unsanctioned platform is still refused and an
unresolvable one still fails closed.

**A bonus defect found during that proof.** The presence check called
`docker image inspect` without asking WHICH architecture the store held, so a
local amd64 image satisfied it and `docker run --platform` then failed with
`pull access denied ... may require 'docker login'` — a CREDENTIALS message for an
ARCHITECTURE defect. It now compares `{{.Os}}/{{.Architecture}}` and says so.

**F3 — a hermetic PR-gate test.** `_ctl/tests/dockerfile-args.test.sh`, 16 checks:
every version-shaped `${NAME}` reference must be declared by an `ARG` in the same
file. Red against the exact dangling-ARG construction, while `ctl.sh validate`
stayed rc=0 — the finding reproduced.

Its scope is narrow ON PURPOSE, and the reasoning is worth keeping: the WIDER rule
(all `${...}`) needs an allowlist — `VERSION_CODENAME` from `/etc/os-release`,
`WEST_VENV` from the parent image's ENV, `USERNAME` from zsh, and `${VAR}` written
in prose. Version-shaped names need **zero exceptions across all five Dockerfiles,
48 references**. *"An allowlist is a place for a real defect to hide"*, so none was
opened.

The fixture is a PERMANENT counter-stimulus: the test asserts the detector finds
the dangling name, does NOT report the correctly-declared one, and does NOT read
the one inside a comment. *"A detector that has only seen correct input has never
been watched to fire."*

**F6** — the header no longer claims nothing is emulated.

**F7** — every message is now true, and it takes the LAST declaration of a name
because that is the one Docker threads into the build. Two matching ARGs now fail
saying it will not choose between them; an indented ARG and a leading-`v` value
now both resolve correctly; `=latest` fails naming the shape it cannot read.

```
bash ./ctl.sh test       rc=0    6 files, dockerfile-args 16 checks 0 failed
bash ./ctl.sh validate   rc=0
bash .ci/smoke.sh base-runner <local>   rc=0, v0.36.1 matches the pin
```

### The self-catch worth recording

`ctl.sh test` went red on the author's OWN explanatory comments —
`platform-policy.test.sh` caught the forbidden architecture token on the named
build path. That test file was within its ownership, so editing it was available.
It rewrote its prose instead and wrote down why the token is absent, naming the
alternative as "the paper-over move".

### Its own account of the F1 miss, kept because it generalises

> I reasoned correctly about the constraint (one image, one platform) and then
> implemented the CHEAPEST response to it rather than the CORRECT one, in a file
> whose whole purpose was to unblock the widening I was blocking. Unrecorded
> drift is what let that sit unexamined — it was not in the plan, so nothing
> asked what it did when the sanctioned set grows.

## Next

Implementer: F2 (the fetched binary is verified by nothing — upstream publishes
checksums), F5 (the state-file sentence that implies smoke coverage CI does not
give), the stale "1 edit" sentence in `.claude/rules/00-identity.md`, and
`.ci/README.md:14`, now wrong on both halves.


## Phase 6 — the supply-chain gap closed (F2), and two truths corrected

**The red, proven before the fix.** The pre-change block had exactly one gate,
`curl -f`:

```
curl -fsSL <a README URL> -o decoy-buildx    rc=0
chmod +x decoy-buildx                         12886 bytes, "ASCII text"
sha256 ddba5a636b7c...   expected 48af8a397ebd...
```

The fetch-then-`chmod +x` sequence completes rc=0 on a body that is not the
binary. Nothing compared anything.

**The mechanism: hardcoded per-arch digest ARGs**, checked with `sha256sum -c -`
BEFORE `chmod +x`. Fetching upstream `checksums.txt` was REJECTED, and the reason
is the good one: *that file arrives over the same transport from the same origin
as the binary, so whoever can serve a substituted binary can serve a checksum that
agrees with it.*

**What it does NOT protect against — stated, not glossed:** trust on first use (it
proves the bytes are what upstream published the day the pin was set, not that
upstream was honest; only sigstore verification gives provenance, and that needs
`cosign` — a new tool and a new pin); a `--build-arg` override by a caller who
controls the build command; anything about what the binary DOES; and the fact that
a version bump must move its digest with it (this fails loudly, proven).

**Compose was fixed in the same commit** — same defect, same file, three lines
away, and the buildx block had copied it. Outside the approved plan, and the commit
body says so.

**The refusal was WATCHED, on the real file.** Corrupting the ARG value invalidates
the whole image (~40 min, ~9 GB, and the host had 6.5 GB), so the amd64 branch was
pointed at the arm64 digest instead — real plumbing, real asset, wrong expected
value, one invalidated step:

```
docker build --platform linux/amd64    rc=1   27 steps CACHED
  #33 docker-buildx: FAILED   sha256sum: WARNING: 1 computed checksum did NOT match
restored                                rc=0   32/32 CACHED
```

The all-CACHED restore also proves the committed file has the same instruction
stream as the file that produced the green image. arm64 was verified separately by
building the two RUN blocks standalone, natively, with the same pass/fail pair.

### The "1 edit" rule sentence is STILL FALSE — verified rather than trusted

Phase 5 fixed the SMOKE path to select a platform. The implementer did not take
that as sufficient. Mirror copy, one edit widening `SANCTIONED_PLATFORMS`:

```
bash <mirror>/ctl.sh test    rc=1    8 checks red across 4 files
  build.test.sh   IMAGE_PLATFORMS holds more than 1 platform ... use push
  guard.test.sh, platform-policy.test.sh, verify-published.test.sh
```

`image_build` still refuses a multi-entry list, and the policy is stated in three
more places. A qualifier was not enough; the sentence is replaced by the
measurement.

## BLOCKER — the workflow publishes BEFORE it smokes (task #68)

`.github/workflows/build-and-push.yml`:

```
line 148   push: true                      <- the image ships to ghcr.io
line 157   verify the published manifest
line 162   smoke test (native amd64)       <- the assertion runs HERE
```

**The gate runs after the irreversible action.** The buildx assertion this feature
adds cannot PREVENT a broken image shipping; it can only report afterwards, once
consumers can already pull it. With task #65 (smoke does not run at PR time at
all), the real coverage is: a PR that breaks the image passes its own gate, the
image publishes, and the failure lands on whoever pushes next.

This must be fixed before the branch lands, or the feature's safety story is
false.

## Left alone, and it is a real finding

**21 of 24 `curl` fetches in `base/Dockerfile` remain unverified**, including three
`curl | sh` installers — oh-my-zsh:226, nvm:256, uv:267 — and rustup:308, plus go,
bun, aws-cli, gh, terraform, kubectl, helm, k9s, k3d, kind, yq, nats, bw, hadolint,
kubeconform, gitleaks, tailscale. This change closed 2 of 24. Extending it needs a
per-tool digest source and its own plan.

## Environment note

The rebuild first died with `No space left on device` — the Docker VM had 262 MB
free of 63 GB. The implementer pruned build cache and its own scratch tags,
disclosed exactly what it removed, and confirmed every `ghcr.io/*` image, all 71
volumes and all running containers were untouched. 6.5 GB free now; a full base
build needs ~10 GB.

Also flagged: three containers (`amazing_noyce`, `impl-validate-final2`,
`bold_faraday`) are running from `ghcr.io/gophersys/base:latest`, left by another
agent.


## Phase 7 — the publish-order blocker is closed (`faa86d4`)

The `base-runner` job now builds twice: `push: false` + `load: true` to a
registry-less `SMOKE_REF`, then the smoke against that loaded ref, then a second
`push: true` build, then `verify-published` (still after the push, as the test
pins it).

`SMOKE_REF` carries NO registry on purpose: nothing can pull it, so a load that
did not happen fails the smoke instead of silently asserting against the last
PUBLISHED image. That is the difference between a gate and a gate-shaped hole.

### The reordering was EXECUTED, not read

The workflow has no `continue-on-error` and no `if:` (grep rc=1), so a failed step
ends the job. The three steps were run locally, twice, changing only the parent
image:

```
A  BASE_IMAGE=dc-buildx-base:local            (base WITH the buildx install layer)
   build --push=false --load   rc=0   nothing published
   smoke                       rc=0   v0.36.1 matches the pin
   publish                     REACHED
   verify-published            after the push, as pinned

B  BASE_IMAGE=ghcr.io/gophersys/base:latest   (published base, NO buildx layer)
   build --push=false --load   rc=0   nothing published
   smoke                       rc=1   docker: unknown command: docker buildx
   JOB STOPS — the publish step is NEVER REACHED
```

Path B is a real build of the real `runner/Dockerfile` on a base that genuinely
lacks the install. It substitutes for deleting the install block from a throwaway
`base/Dockerfile`, which was attempted and ABANDONED at ~30s: the earlier cache
prune meant that path needed a full ~10 GB / ~40 min rebuild against 6.1 GB free,
and the implementer killed it to protect a Docker daemon shared with other agents
rather than let it hit `No space left on device`. Correct call, and disclosed.

```
ctl.sh test      rc=0   publish-order 28 checks, 0 failed
ctl.sh validate  rc=0
diff .github/workflows/build-and-push.yml .ci/providers/github/build-and-push.yml   rc=0
```

### One file generates the other? NO — and a README lies about it

There is no generator and no symlink. Both are regular files kept equal only by a
`cmp` in `_ctl/tests/platform-policy.test.sh`. **`.ci/providers/README.md` claims
`.github/workflows/*.yml` ARE symlinks into the provider directory.** That is
false, and `.ci/README.md:23` states the truth ("a copy, not a symlink"). Two
documents in one repository disagree about the mechanism, and the false one is the
more authoritative-sounding. Untouched by this change — filed separately.

### A scope expansion, flagged rather than hidden — and I am CONFIRMING it

The implementer also edited `.claude/rules/00-identity.md`, outside the two files
I scoped, because its sentence ("builds with `--push`, then verify-published") had
become FALSE for `base-runner`. **Keep it.** Leaving a rule file describing a
sequence the repository no longer performs is precisely the doc-truth defect this
estate has spent the night finding. A change that falsifies a document and does
not fix it is incomplete, not in-scope.

### Fidelity gap, stated

The local builds used the `docker` driver, not the `docker-container` driver
`setup-buildx-action` creates in CI. Materialising `base` in a fresh
docker-container builder needs ~10 GB, which this disk does not have. `--load`
differs in mechanism only, but the SECOND (publish) build's cache hit is therefore
NOT measured. No push to ghcr.io was performed.

## Next

Final verification, then the pull request. All findings from two verifier rounds
plus the publish-order blocker are now closed.


## Phase 8 — VERIFIED, and the last false number is gone

A third verifier round passed the branch on one condition: correct the
measurement the branch itself introduced. Done, and the implementer re-measured
rather than taking my word:

```
one edit: SANCTIONED_PLATFORMS="linux/amd64" -> "linux/amd64,linux/arm64"
bash ./ctl.sh test    rc=1    8 '--- FAIL:' lines
  build.test.sh            6 checks, 3 failed
  guard.test.sh           11 checks, 1 failed     <- the source of the wrong "11"
  platform-policy.test.sh  8 checks, 2 failed
  verify-published.test.sh 6 checks, 2 failed
```

"4 test files" was TRUE; only the count was wrong. The rule file now carries the
per-file breakdown, so a reader can CHECK THE SUM — a bare total is what allowed
`11 checks, 1 failed` to be misread in the first place.

**The README lie was 5 places, not 1** — lines 8, 19, 23, 25-27 and 33 of
`.ci/providers/README.md`, including an ACTIVE INSTRUCTION to run
`ln -s` to link the file into `.github/workflows/`, which would have broken the
`cmp` that keeps the two copies equal. Verified rather than assumed: `git ls-files
-s` gives mode `100644` on all three workflow files and `test -L` says REGULAR.

**And it caught its own over-claim mid-write.** It first wrote that
`platform-policy.test.sh` keeps the pair equal; the `cmp` is hardcoded to
`build-and-push.yml` alone, so a SECOND file in that directory would get nothing.
It rewrote the sentence to state that limit rather than ship a new
believed-but-empty claim inside a commit whose purpose is deleting one.

### The verifier's judgement on the known debt — none of it blocks

- smoke not at PR time (#65): repo-wide design; blocking on it would block the fix for #68
- 21 of 24 unverified curl fetches: this branch closes 2 and writes down the rest;
  blocking means closing 0
- `_ctl/lib.sh:48` hardcoded namespace: ergonomic, no correctness effect
- the 4 unsmoked publishers: now named and ratcheted, strictly better than before

### One watch item for the PR body, not a blocker

`load: true` materialises the image on the runner: `base-runner` is **10.6 GB
uncompressed** (2.39 GB compressed). Before this branch the job streamed the build
straight to ghcr.io and never materialised it locally; now it does, on top of the
copy buildkit holds. Nobody has measured whether `ubuntu-latest` has room after
`free-disk-space`, and it cannot be measured anywhere but CI.

**It fails CLOSED** — the load step dies before the publish, so nothing broken
ships — but `base-runner` would go red on main and publish nothing. Watch the
first run.
