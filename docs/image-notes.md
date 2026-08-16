# The `hardware` image — build-ready specification

Status: specification for later development. No Dockerfile in this repo changes now.
Sources: the image census and the image-architecture design (task #94 program),
plus this repo's `ci/Dockerfile`, `.devcontainer/Dockerfile`, `.github/workflows/ci.yml`,
and `scripts/clone_pilots.sh`. All sizes come from the census. `EST` marks an estimate.
Language: ASD-STE100 Simplified Technical English.

This document is complete. Build the image from this document. Do not derive the
facts again.

---

## 1. What this image is

`ghcr.io/gophersys/hardware` is the one image for all research-hardware work:
CI, the devcontainer, and agent runners.

- **Parent:** `ghcr.io/gophersys/cloud` (the reduced base, 3.0–4.8 GB EST).
  The image is `FROM cloud` plus one script: `_delta/hardware.sh`.
- **Home:** the eden `.devcontainer/` estate, next to the other category images.
  Not this repo. This repo only consumes the image, by digest.
- **Child:** `hardware-runner` = `hardware` + the shared `runner/Dockerfile`
  (`ARG PARENT_IMAGE`). The runner delta is measured: ~1.04 GB
  (.NET runtime deps 3.65 MB, Actions runner 2.336.0 = 707 MB, cictl 66 MB,
  claude CLI 267 MB).
- **Sibling consumer:** `matrix` runs the same `_delta/hardware.sh` as its first
  delta layer. One edit to the script moves `hardware` AND `matrix` together.

### What it absorbs and retires

| Retired item | Why the census kills it |
|---|---|
| `ci/Dockerfile` → `ghcr.io/gophersys/research-hardware-ci` | Its full content moves into `_delta/hardware.sh`. Nothing is lost. |
| `.devcontainer/Dockerfile` | It is a sibling of the CI image, from `ubuntu:24.04`, with manual sync. The sync is asserted, never proven. The KiCad package sets differ (metapackage vs explicit). The pip pins differ (4 pinned vs 11 unpinned). It has no build-time proof block. |
| `.github/workflows/build-ci-image.yml` | The eden `build-and-push.yml` pipeline builds and publishes the image. |
| The "keep the two in sync" comments (`ci/Dockerfile`, `docs/ci.md:40`) | Drift becomes structurally impossible: dev and CI pin the same digest of the same image. |

The dev comfort layer (zsh, oh-my-zsh, gh, docker-ce-cli, Node, jq, ripgrep, fd,
vim) is not lost. `cloud` already carries all of it. The devcontainer becomes an
`"image"` reference to the `hardware` digest, with no local Dockerfile.

---

## 2. Exact delta contents — `_delta/hardware.sh`

The delta is the census delta list, verbatim. Pins live once, at the top of the
script, as guarded defaults (`: "${KIUTILS_VERSION:=1.4.8}"`).

1. **KiCad 10 from the PPA** `ppa:kicad/kicad-10.0-releases`. Install the
   explicit package names: `kicad kicad-symbols kicad-footprints
   kicad-packages3d`. Do NOT use the `kicad-libraries` metapackage:
   `--no-install-recommends` drops the libraries on that path, `/usr/share/kicad`
   stays empty, and the resolver fails with `assert 0 > 10000`, which reads as a
   code bug.
2. **`software-properties-common`** — only if `cloud` does not carry
   `add-apt-repository`. Verify at implementation (see open question Q2).
3. **Pinned, root-reachable Python stack** with system `pip3
   --break-system-packages --no-cache-dir`:
   `kiutils==1.4.8 sexpdata==1.0.2 pytest==9.1.1 ruff==0.16.0`.
   Root-reachable, because gates run as root.
4. **`ENV PYTHONUNBUFFERED=1`** — set in `hardware/Dockerfile`, not in the
   script. A script cannot set ENV.
5. **Build-time proof block** (FAIL-NOT-SKIP; the build is red without it):
   ```sh
   kicad-cli version; python3 --version; ruff --version
   fp=$(find /usr/share/kicad/footprints -name '*.kicad_mod' | wc -l)
   sym=$(find /usr/share/kicad/symbols -name '*.kicad_sym' | wc -l)
   step=$(find /usr/share/kicad/3dmodels -name '*.step' | wc -l)
   [ "$fp"  -gt 10000 ] || { echo "ERROR: only $fp footprints";   exit 1; }
   [ "$sym" -gt 100   ] || { echo "ERROR: only $sym symbol libs"; exit 1; }
   [ "$step" -gt 1000 ] || { echo "ERROR: only $step STEP models"; exit 1; }
   ```
   The counts matter as much as the binary. An image with `kicad-cli` but no
   footprints passes a naive smoke test and fails the whole resolver suite later.

Already in `cloud`, so NOT in the delta: `git`, `curl`, `gnupg`,
`ca-certificates` (the PPA and corpus-clone needs), Python 3.12 + pip + venv,
and the full comfort layer.

### Deliberately dropped, with proof

| Dropped | Proof |
|---|---|
| pip: `httpx, pandas, pytest-asyncio, pyyaml, rich, typer, claude-code-sdk` (the old dev image's 7 extra packages) | A grep of every Python import in `src/ scripts/ tools/ tests/` finds only stdlib + `kiutils` + `sexpdata`. No gate and no import uses them. |
| `build-essential`, `make` (the old dev image's own line) | No compiled dependency exists; all pip packages install as wheels or pure Python. Also: `cloud` already carries build-essential (~250 MB EST). The delta must not install it again. |
| The old dev image's unpinned pip copies of kiutils/sexpdata/pytest/ruff | Replaced by the 4 exact pins above. A different `ruff` gives a different lint verdict. |

### Sizes

| Layer | Size |
|---|---|
| `cloud` (parent) | 3.0–4.8 GB EST per arch (the ≤ 4 GB gate arbitrates) |
| `hardware` delta | cloud + 4–7 GB EST — `kicad-packages3d` dominates; never measured. The first build measures it. |
| `hardware-runner` delta | ~1.04 GB, measured |

---

## 3. Dual-arch notes

Policy: `linux/amd64,linux/arm64` for `hardware` and `hardware-runner`.
No QEMU in CI, ever. amd64 builds native on the cluster (arc-org pool). arm64
builds native on the mini's buildkitd (`tcp://10.168.0.92:1234`, mTLS, BUILD API
only, measured 3.44× faster than emulation). If the mini is down, the build
FAILS and names the node.

Per-arch execution smoke is mandatory: amd64 in-cluster before publish; arm64 on
the mini's own docker (native Apple-silicon execution) against `:<sha>-arm64`.
An emulated smoke is forbidden — the D42 incident proved an emulated pass hides
a mislabelled image. After both smokes: manifest merge
(`docker buildx imagetools create`), `verify-published` (both platforms in the
manifest), and `verify-image-arch` (ELF machine bytes per arch).

### Arch risk specific to this category

- **R2 (primary): the KiCad PPA on arm64 is unproven.** Launchpad arm64 builds
  for `ppa:kicad/kicad-10.0-releases` are not confirmed. The library packages
  (`kicad-symbols`, `kicad-footprints`, `kicad-packages3d`) are arch-independent
  data; the risk concentrates in the `kicad` binary package. Verify on Launchpad
  BEFORE the dual-arch step. If arm64 binaries do not exist, narrow `hardware`
  to `linux/amd64` with the documented per-image switch
  (`IMAGE_PLATFORMS="linux/amd64"` in the image's ctl) — stated, never silent.
- **Layer weight:** the 4–7 GB delta publishes twice (once per arch). Expect
  long push times and real registry cost. The fixed matrix layer order puts this
  cost in every matrix rebuild too.
- **Cross-arch determinism is unproven.** ERC/DRC and Gerber output can differ
  across architectures (floating-point paths). Section 4 handles this honestly:
  per-arch byte-stability is the day-1 assertion; cross-arch equality is
  measured first, then promoted or documented (open question Q5).

---

## 4. The real-world publish gate — ERC/DRC/netlist/Gerber on pilot #1, byte-stable

Correctness first: the gate proves the image computes the same real result on a
real board, not that binaries print versions. It runs per arch, on native
silicon, BEFORE the manifest merge and the `:latest` tag. A gate that cannot run
(mini unreachable, corpus fetch fails, pin refused) is a FAILURE that names the
missing thing. Nothing skips.

### The subject

Pilot #1: Antmicro Jetson Nano baseboard, pinned at commit
`d8d0b2d71ab4cc4bcdb204a09f78be40d4c8cda3`
(`scripts/clone_pilots.sh`, entry 1). The gate uses the same pinned sparse-fetch
mechanism. The default-branch fallback in `clone_pilots.sh` is FORBIDDEN inside
the gate: a pin the host refuses is a red gate, not a drifted corpus
(same rule as `check_pilot_pins.sh` in `ci.yml`).

### The procedure (exact commands)

Run inside the candidate image (`docker run --rm -v "$CORPUS":/corpus -w /out <candidate-ref> …`):

```sh
set -euo pipefail
# 1. Resolve the project. Exactly one match, or fail and name the path.
pro=$(find /corpus/antmicro__jetson-nano-baseboard -name '*.kicad_pro' | head -2)
[ "$(echo "$pro" | wc -l)" -eq 1 ] || { echo "ERROR: project file not unique: $pro"; exit 1; }
sch="${pro%.kicad_pro}.kicad_sch"
pcb="${pro%.kicad_pro}.kicad_pcb"
[ -f "$sch" ] || { echo "ERROR: missing $sch"; exit 1; }
[ -f "$pcb" ] || { echo "ERROR: missing $pcb"; exit 1; }

# 2. The battery. Each command must exit 0. Each output must exist and be non-empty.
kicad-cli sch erc            "$sch" --output erc.rpt      --severity-all
kicad-cli sch export netlist "$sch" --output netlist.net  --format kicadsexpr
kicad-cli pcb drc            "$pcb" --output drc.rpt      --severity-all
kicad-cli pcb export gerbers "$pcb" --output gerbers/
for f in erc.rpt netlist.net drc.rpt; do [ -s "$f" ] || { echo "ERROR: empty $f"; exit 1; }; done
[ "$(ls gerbers/ | wc -l)" -gt 0 ] || { echo "ERROR: no gerbers"; exit 1; }
```

Do not pass `--exit-code-violations`. The board is upstream work; its violations
are data, not our failure. The violation COUNTS are the assertion (below).

### The assertions

1. **Byte-stability (determinism), per arch.** Run the full battery TWICE in the
   same container. Normalize each output with the pinned volatile-line list
   (below). Assert `sha256sum` of run A equals run B for EVERY file. One
   different byte is red.
2. **Golden equality.** Compare the normalized digests to the committed golden
   manifest (`goldens/pilot1-<arch>.sha256`). Any diff is red: it means the
   toolchain changed behavior, which is exactly what a publish gate must catch.
   The first green run on the approved image RECORDS the goldens; a human
   reviews and commits them in a PR. After that, no regeneration without a
   reviewed PR.
3. **Violation counts.** Extract the ERC and DRC totals from the reports. Assert
   they equal the pinned counts recorded with the goldens. A changed count with
   an unchanged pilot means toolchain drift.
4. **The normalization list is pinned and CLOSED.** Candidate volatile lines,
   to verify against real KiCad 10 output at implementation (open question Q4):
   - report header dates: `/^\*\* Created on/d` (erc.rpt, drc.rpt)
   - Gerber attributes: `/TF\.CreationDate/d`
   - Gerber comment: `/^G04 Created by KiCad/d`
   A diff outside this list is red. Never widen the list to make a gate green.

### Wiring

- amd64: the in-cluster job runs the gate against the LOADED image, pre-push.
- arm64: the mini job pulls `:<sha>-arm64` and runs the same script through the
  mini's docker (the `mini-serial` concurrency group).
- The pilot corpus is cached by pin (`key: pilots-<hash of the pin>`), exactly
  as `ci.yml` caches it today.
- After publish, this repo's `ci.yml` keeps its own gate (ruff + full pytest
  suite on the pinned corpus) per PR, in the same image, at the same digest as
  the devcontainer (dev/CI digest-identity tripwire, acceptance metric 5).

---

## 5. Migration and rollback

Migration is design step (c). Each numbered item is one reviewable change.

**Preconditions:** step (a) (renames) and step (b) (cloud reduction +
`_delta/` mechanism) are merged, and `cloud` is published dual-arch.

1. In eden `.devcontainer/`: add `_delta/hardware.sh` (section 2, verbatim) and
   `hardware/Dockerfile` (`FROM cloud`, COPY + RUN the script, the ENV line).
2. Sync the dependency graph in all 4 places: BUILD_ORDER in the ctl, the
   byte-identical provider copy, eden `project.json` `dependsOn`, and
   `build-and-push.yml` `needs` (×2 with the provider copy). Add
   `_delta/hardware.sh` to the change-detection inputs of `hardware`,
   `hardware-runner`, AND `matrix`.
3. Build and publish through the section-4 gate. Record the measured delta size
   against the 4–7 GB estimate.
4. In THIS repo, one PR:
   - `ci.yml`: `IMAGE` → `ghcr.io/gophersys/hardware@<digest>`. REPLACE the
     "build locally when unusable" fallback: pull must succeed and `usable()`
     must pass, else FAIL and name the image. The local-rebuild path dies with
     `ci/Dockerfile`.
   - `.devcontainer/devcontainer.json`: `"build"` → `"image"` at the SAME
     digest.
5. One green CI run on the new image (ruff + full pytest, pinned corpus).
6. Then, in the same PR chain: DELETE `ci/Dockerfile`,
   `.devcontainer/Dockerfile`, `.github/workflows/build-ci-image.yml`. Update
   `docs/ci.md` (the sync paragraph and the rebuild instructions). This
   supersedes the census drift findings for this repo.
7. The ghcr package `research-hardware-ci` stays published through the soak.
   Its deletion needs Mateo's explicit authorization (design section 8).

**Rollback (one commit):**
- The deleted files live in git history; revert restores them.
- Re-point `ci.yml` `IMAGE` and the devcontainer at
  `ghcr.io/gophersys/research-hardware-ci:latest` — the package still exists
  until Mateo authorizes deletion.
- The `hardware` tags stay published; an unused tag is harmless.
- Nothing in eden must revert for this repo to work again.

---

## 6. Open questions — honest

- **Q1 — KiCad PPA on arm64 (risk R2).** Not confirmed on Launchpad. Verify
  before the dual-arch step. If absent: narrow `hardware` to amd64 with the
  documented switch; the arm64 half of the gate then does not exist, and the
  narrowing is stated in the manifest checks.
- **Q2 — `add-apt-repository` in `cloud`.** `software-properties-common` sits
  in a census group that is partly dropped. Verify in the built `cloud`; the
  delta installs it only if absent.
- **Q3 — the delta size is unmeasured.** 4–7 GB EST; `kicad-packages3d`
  dominates. Only `cloud` has a size gate (≤ 4 GB). Decide after the first
  build whether `hardware` gets its own budget, or the measurement is simply
  recorded.
- **Q4 — the exact volatile-line list.** The section-4 normalization patterns
  are candidates. Enumerate the real volatile lines from KiCad 10 output at
  implementation. Also verify whether `kicad-cli` honors `SOURCE_DATE_EPOCH`;
  if yes, the list may shrink to zero.
- **Q5 — cross-arch byte-identity.** Unproven. Day 1 asserts per-arch
  determinism and per-arch goldens. Measure amd64-vs-arm64 equality of the
  normalized outputs; if equal, collapse to one golden set and assert it; if
  not, keep per-arch goldens and record why.
- **Q6 — where the gate and goldens live.** The design gives image gates to
  eden's `build-and-push.yml`, but the pilot pin lives in this repo's
  `clone_pilots.sh`. Proposal: gate script + goldens live with the image in
  eden, plus a tripwire that its pinned SHA equals this repo's pin. Decide at
  implementation.
- **Q7 — pip stack vs `cloud` Python.** The delta uses system `pip3
  --break-system-packages`, as the CI image does today. Verify no collision
  with tooling `cloud` installs for Python 3.12, and that `pytest`/`ruff`
  resolve root-wide ahead of any user-homed copies.
