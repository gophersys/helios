# libs .ci

Orchestration-layer CI for `gophersys/libs`. Verbs are invoked locally
inside a gophersys devcontainer, via Nx (`nx run ci-libs:<verb>`), or by
a remote CI runner (see `.ci/providers/`).

## Verbs

Tier verbs — referenced by `ci.contract.yaml`, identical locally and
remotely:

- `affected-gate-fast` — phase-gate implementation over the affected
  projects (pr tier).
- `affected-gate-substrate` — integration / lifecycle / load on real
  docker + k3d + kind (merge tier).
- `gate-all` — phase-gate all (1→4) over the affected projects (nightly
  tier).
- `updatability` — pinned-version matrix from the contract's
  `toolMatrix` (nightly tier).
- `ci-drift` — the generated workflows still match the contract (pr
  tier).

Meta verbs:

- `validate` — shellcheck every `ctl.sh`, every `<lang>/_ctl/*.sh` and
  every `*_test.sh`; jq-validate every `project.json`; report drift
  between targets and the verbs each dispatcher's own `help` prints; run
  every `*_test.sh` suite. Delegates to repo-level `ctl.sh validate`,
  and runs in the pr tier.
- `status` — inventory: total libs per language subtree.
- `release-check` — preflight for release.sh: clean working tree, on
  main, up to date with origin.
- `help`.

`__verbs` is hidden: `cictl conformance` invokes it to learn which verbs
this dispatcher defines, and fails if a tier references one that is
absent.

Follows the brain-wide CI convention documented in
`brain/.claude/rules/operations/ci-patterns.md`.

## Providers

`ci.contract.yaml` is the source of truth. `cictl generate -C .` renders
it into `providers/<system>/` and into the native paths
(`.github/workflows/`). Both are REGULAR FILES carrying a DO NOT EDIT
banner — not symlinks — so `ci-drift` re-renders from the contract and
fails the pull request that hand-edited one.

`github` is the one provider wired, with three workflows: `on-pr.yml`,
`on-push.yml` and `nightly.yml`.
