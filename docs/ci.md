# CI

## What runs

One workflow, `.github/workflows/ci.yml`, on every PR and every push to `main`:

1. **ruff** over `src/` and `tests/`
2. **pytest** over the whole suite, **with KiCad 10 available**

Plus `.github/workflows/build-ci-image.yml`, which still builds and publishes the
**retired** repo-local image (see "The CI image" below). It is kept only as the rollback
anchor; nothing in `ci.yml` pulls it any more.

## Where it runs

On **`runs-on: arc-org`** — the gophersys org-wide [actions-runner-controller][arc]
scale set, defined in the infrastructure repo at
`platform/services/gitops/registry/app-arc-runners-org.yaml` and reconciled by ArgoCD
onto the homelab k3s cluster.

Three properties of those runners shape everything here:

| Property | Consequence |
|---|---|
| Stock `ghcr.io/actions/actions-runner` image | No KiCad, no project tooling |
| **No sudo** | Cannot `apt-get install` anything in a job |
| Privileged **dind** sidecar | Docker *is* available — so tooling comes from a container |
| `minRunners: 0`, `maxRunners: 4` | Scales from zero (expect ~30–60s queue on a cold start), shared with every other gophersys repo |

Because the scale set is registered at the **org** level, this repo needed no runner-group
change and no new credentials to use it.

## The CI image

`ghcr.io/gophersys/hardware` — the org **category** image, built and published from the
eden `.devcontainer/` estate, not from this repository. It is `ghcr.io/gophersys/cloud`
plus `_delta/hardware.sh`: KiCad 10 from the `ppa:kicad/kicad-10.0-releases` PPA with the
explicit `kicad kicad-symbols kicad-footprints kicad-packages3d` package set, plus
`kiutils`, `sexpdata`, `pytest`, `ruff`. See [image-notes.md](image-notes.md) for the
full specification. This repo only **consumes** the image.

`ci.yml` pins it **by digest**, not by tag: the devcontainer and CI must run identical
bytes, and a moving `:latest` cannot promise that.

Two consequences of consuming an org image:

| Consequence | Why |
|---|---|
| The pull needs `GHCR_PULL_TOKEN`, not `GITHUB_TOKEN` | `GITHUB_TOKEN`'s `packages:read` only covers packages linked to *this* repository; `gophersys/hardware` is a private cross-repo package. The repo secret holds the org-scope pull PAT. |
| Every `docker run` passes `--user root` | The org image defaults to uid 1000 (`dev`). The runner-owned checkout is not writable by it, so `pytest --junitxml` would EACCES. The retired image had no `USER` and ran as root, so this only preserves the old behaviour. |

A failed pull, or an image without `kicad-cli` and its footprint libraries, is a hard
failure that names the image. There is **no local-rebuild fallback** any more: this repo
no longer owns the image, so falling back to a stale local Dockerfile would silently test
the wrong toolchain.

### The retired repo-local image

`ghcr.io/gophersys/research-hardware-ci` — built from `ci/Dockerfile` by
`build-ci-image.yml`. Nothing pulls it now. It stays published as the **rollback anchor**:
re-pointing `IMAGE` in `ci.yml` back at `ghcr.io/gophersys/research-hardware-ci:latest`
restores the previous CI in one commit. Deleting that ghcr package needs Mateo's explicit
authorization. `ci/Dockerfile`, `.devcontainer/Dockerfile` and `build-ci-image.yml` are
removed in a follow-up change, after this image has a green history here
([image-notes.md](image-notes.md) §5 step 6).

## Why KiCad in CI is the point

The pipeline's whole purpose is generating KiCad files and validating them with
`kicad-cli` — ERC, DRC, netlist export, Gerber generation. Before this workflow existed
that half of the suite had **never run in automation**, and on a developer machine
without KiCad it did not even skip cleanly: `kicad-cli` resolution fell back to a
hardcoded `/usr/bin/kicad-cli`, so a missing toolchain surfaced as 58 unrelated-looking
`FileNotFoundError` failures.

Resolution now lives in one place, `src/pipeline/kicad_cli.py`, and is **PATH-only** —
matching the project decision in `CLAUDE.md` that the toolchain is whatever `kicad-cli`
PATH points at, never a hardcoded location.

## The pilot corpus

16 of 33 test modules read from `data/raw/` — 188 MB of upstream KiCad projects, cloned
by `scripts/clone_pilots.sh` and gitignored.

All 12 repos are **pinned to commits**. An unpinned `--depth 1` clone tracks upstream
HEAD, which means an unrelated commit in someone else's repository can turn this repo's
CI red overnight — with no change on our side to explain it.

CI caches `data/raw` keyed on the hash of `clone_pilots.sh`. Because the clones are
pinned, a cache hit and a cold clone produce byte-identical corpora, so the key only has
to change when the script does.

`scripts/check_pilot_pins.sh` runs after the clone and **fails the build** if any repo is
not on its pinned commit. `clone_pilots.sh` falls back to the default branch when a host
refuses to serve an arbitrary SHA (needs `uploadpack.allowReachableSHA1InWant`); that
fallback keeps a developer unblocked but must never pass silently in CI.

### Updating a pin

```bash
cd data/raw/<project> && git fetch --depth 1 origin <new-sha> && git checkout <new-sha>
# then edit the matching clone_sparse call in scripts/clone_pilots.sh
bash scripts/check_pilot_pins.sh data/raw    # must pass before pushing
```

Changing the script invalidates the CI cache automatically.

## Reproducing a CI failure locally

Same image, same command. Pull it rather than build it — `docker login ghcr.io` first,
since the package is private:

```bash
IMAGE=ghcr.io/gophersys/hardware:latest@sha256:ad5851092f6acc7f9a32bd3557499f82d592f15f15201311106852f517734d58
docker pull "$IMAGE"
docker run --rm --user root -v "$PWD":/workspace -w /workspace "$IMAGE" \
  python3 -m pytest tests/ -q
```

Use the digest `ci.yml` pins, not `:latest` — otherwise you are not reproducing CI.

Or use the devcontainer, which has the same KiCad 10.

Without either, KiCad-dependent tests skip with a reason naming the missing tool.

## Extending

- **Another check** — add a step to the `ci` job. It is one job on purpose: the org has
  4 runner slots shared across all repos and this project runs a tall PR stack, so extra
  jobs cost queue time without adding signal.
- **Another Python dependency, or a newer KiCad** — edit `_delta/hardware.sh` in the eden
  `.devcontainer/` estate, let that pipeline publish, then bump the pinned digest in
  `ci.yml` here. Nothing in this repository builds the image any more, so a change made
  here alone has no effect.
- **Another repo needing KiCad CI** — consume `ghcr.io/gophersys/hardware` the same way;
  `arc-org` is org-wide and needs no per-repo wiring, but the consuming repo does need
  its own `GHCR_PULL_TOKEN` secret (it is a repo secret, not an org secret).

## Known gaps

- **Derived pattern data is not generated in CI.** Nine tests consume
  `data/patterns/subcircuit_clusters.json` and `decoupling_rules.json` — extraction
  output that is gitignored and absent from a fresh checkout. They are marked
  `requires_patterns` and skip with a reason. `scripts/bulk_subcircuits.py` produces
  the clusters file, but **nothing in the repo generates `decoupling_rules.json`** —
  it is only ever read. Closing this means writing that generator and adding an
  extraction step (cacheable, since the corpus is pinned). Until then those nine tests
  run nowhere, which the named skip makes visible instead of silent.
- **Live Claude CLI tests never run in CI.** `tests/test_e2e_novel_mcu.py` (ESP32-C6
  datasheet extraction, which deliberately has no hardcoded fallback) and
  `tests/test_cluster_label.py` shell out to `claude --print`. The org image *ships* the
  CLI at `/home/dev/.local/bin/claude` but carries no credentials, so it answers
  "Not logged in" and exits 1. They are marked `requires_claude`; `conftest.py` probes
  whether the CLI can actually answer and skips with that probe's own words. Under the
  retired image the CLI was absent entirely, so these tests had always skipped — CI
  signal is unchanged, the reason is now truthful. Closing this gap means giving the job
  an Anthropic credential and accepting a live, paid, non-hermetic call per run: Mateo's
  call, not a default.
- No branch protection is enforced yet; `ci` should be made a required check on `main`
  once it has a green history.
- `maxRunners: 4` is shared org-wide. A busy org queues this repo's jobs; the workflow
  uses `concurrency` with `cancel-in-progress` so superseded pushes release their slot.

[arc]: https://github.com/actions/actions-runner-controller
