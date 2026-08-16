# CI

## What runs

One workflow, `.github/workflows/ci.yml`, on every PR and every push to `main`:

1. **ruff** over `src/` and `tests/`
2. **pytest** over the whole suite, **with KiCad 10 available**

Plus `.github/workflows/build-ci-image.yml`, which publishes the image the above runs in.

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

`ghcr.io/gophersys/research-hardware-ci` — built from `ci/Dockerfile`: Ubuntu 24.04, KiCad 10 from
the `ppa:kicad/kicad-10.0-releases` PPA, plus `kiutils`, `sexpdata`, `pytest`, `ruff`
pinned to the versions the project develops against.

It is deliberately **not** `.devcontainer/Dockerfile`. That image is for interactive work
and carries editors, zsh, Node, `gh` and Claude Code; CI pulls its image on every cold
runner, so every unnecessary layer is latency. The two share the KiCad install block —
**keep them in sync when bumping KiCad**, since the devcontainer is where developers
reproduce CI failures.

The image is rebuilt when `ci/Dockerfile` changes and weekly (Mondays 04:00 UTC) so base
security patches land without anyone remembering. PRs build it but never push, so an
in-flight change cannot overwrite the tag `ci.yml` pulls.

`ci.yml` pulls the image but **falls back to building it locally** when the pull fails.
That keeps three otherwise-confusing situations green: the bootstrap run before the image
was ever published, a PR that edits `ci/Dockerfile` (where `:latest` is deliberately
stale), and a GHCR outage.

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

Same image, same command:

```bash
docker build -f ci/Dockerfile -t hardware-ci ci/
docker run --rm -v "$PWD":/workspace -w /workspace hardware-ci \
  python3 -m pytest tests/ -q
```

Or use the devcontainer, which has the same KiCad 10.

Without either, KiCad-dependent tests skip with a reason naming the missing tool.

## Extending

- **Another check** — add a step to the `ci` job. It is one job on purpose: the org has
  4 runner slots shared across all repos and this project runs a tall PR stack, so extra
  jobs cost queue time without adding signal.
- **Another Python dependency** — add it to `ci/Dockerfile` (pinned) *and* the
  devcontainer, then let `build-ci-image` republish.
- **A newer KiCad** — bump `KICAD_PPA_VERSION` in both Dockerfiles. The build asserts the
  reported version matches, so a PPA that silently serves something else fails the build
  rather than the tests.
- **Another repo needing KiCad CI** — reuse `ci/Dockerfile`; `arc-org` is org-wide and
  needs no per-repo wiring.

## Known gaps

- **Derived pattern data is not generated in CI.** Nine tests consume
  `data/patterns/subcircuit_clusters.json` and `decoupling_rules.json` — extraction
  output that is gitignored and absent from a fresh checkout. They are marked
  `requires_patterns` and skip with a reason. `scripts/bulk_subcircuits.py` produces
  the clusters file, but **nothing in the repo generates `decoupling_rules.json`** —
  it is only ever read. Closing this means writing that generator and adding an
  extraction step (cacheable, since the corpus is pinned). Until then those nine tests
  run nowhere, which the named skip makes visible instead of silent.
- No branch protection is enforced yet; `ci` should be made a required check on `main`
  once it has a green history.
- `maxRunners: 4` is shared org-wide. A busy org queues this repo's jobs; the workflow
  uses `concurrency` with `cancel-in-progress` so superseded pushes release their slot.

[arc]: https://github.com/actions/actions-runner-controller
