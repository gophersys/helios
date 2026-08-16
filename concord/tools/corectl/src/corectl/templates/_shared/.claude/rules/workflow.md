<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# Workflow

How to develop, validate, and ship test changes for this repo.

## Local-dev TDD against real MTIBs

For a hands-on dev loop against live hardware, lease a fixture (or specific nodes) with `corectl test claim`:

```bash
corectl test claim --fixture <name|id>      # whole-fixture lease, single- or multi-slot
corectl test claim --node <hostname>         # ad-hoc node-mode lease (one --node per slot)
corectl test status                          # live claim summary + sliding-TTL remaining
corectl test unclaim                         # release the lease and stop the heartbeat
```

`claim` writes `.concord-claim.json` at the project root and spawns a detached heartbeat daemon. The sliding TTL is 5 min from the last heartbeat; once the daemon stops (or you run `unclaim`), the lease expires server-side and the fixture is free again. An 8 h hard ceiling caps every claim regardless of heartbeats.

While the claim is active:

- `corectl test run <stage>` automatically resolves `MTIB_HOST` / `MTIB_HOSTS` and `CONCORD_CLAIM_ID` from the state file. Bare `pytest` does the same via this repo's `conftest.py` claim hook. Ambient env vars still win — set `MTIB_HOST` by hand to override.
- `corectl test status` reconciles the local state file against the backend and warns if the lease was expired or released out-of-band.
- The backend's reservation gate refuses to schedule concurrent TestRuns or ManufacturingSessions against the held fixture / nodes for the lifetime of the claim.

Full design (schema, lifecycle, reconciliation rules) lives in concord's `.claude/specs/dev-hold-claim.md`.

## Daily loop

```bash
corectl test validate              # pre-flight; no hardware needed
corectl test run <stage>           # local run against a fixture (needs MTIB)
corectl test upload                # publish a development version
```

Each `upload` writes an immutable `dev-<sha>-<epoch>` version. The platform serves this version to any DEV-purpose fixture immediately.

## Releasing

```bash
# 1. Bump version in concord.yaml package.version (semver)
# 2. Validate
corectl test validate --strict

# 3. Upload + promote in one step
corectl test upload --release

# Or upload first, promote later
corectl test upload
corectl test release --version dev-<sha>-<epoch>
```

Released versions are immutable. They get bound to ProductStageConfig per-stage by the platform admin (or via `corectl release` if you have permission).

## Reconciling with the backend

The backend owns: product slug, board revision, device IDs, testbed controller class path. The local manifest reflects them.

If an admin renames a board, bumps device IDs, or swaps fixtures:

```bash
corectl test sync                  # diff remote vs local, prompt to apply
corectl test sync --apply          # auto-apply
```

`validate`, `run`, and `upload` all surface drift as a non-fatal warning so you never run against a stale manifest silently.

## Updating the framework

Framework artifacts (`.claude/`, `.devcontainer/`) are versioned in lockstep with `corectl` and `corekinect`. When you upgrade tools, refresh the artifacts:

```bash
corectl update                     # upgrade corectl + corekinect together
corectl test update                # refresh .claude/ and .devcontainer/
```

`corectl test update` prints a diff of what would change. Pass `--apply` to write.

## What you may NOT edit

Hand-editing files in `.claude/` or `.devcontainer/` causes `corectl test validate` to fail (cohesion gate). The platform refuses uploads with drifted artifacts. If you need different behavior:

- For a new skill or rule, file an issue in the framework repo so it ships to all test apps.
- For an emergency override, do not bypass — fix the framework instead.

## What you DO own

- `concord.yaml` (manifest)
- `conftest.py`
- `pyproject.toml`
- `testbeds/<board>/testbed.py`
- everything under `tests/`
- `assets/`, `README.md`

These are dev-owned. Edit freely.
