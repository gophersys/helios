# Rule — Harness versions are pinned, and upgrades are gated (ADR-0021)

> The agent harnesses (`claude`, `omp`, `codex`) are third-party CLIs whose streamed protocol can
> change between releases. The adapters in `libs/go/agentsession/<harness>adapter` parse that
> protocol, so the version is part of the contract. Enforced by the `harness-conformance` CI gate
> and the `harness-upgrade-check` scheduled job.

## The one home

The exact versions Eden runs are pinned in **`harnesses/versions.env`** (in the eden monorepo):
`CLAUDE_CODE_VERSION`, `OMP_VERSION`, `CODEX_VERSION`. That manifest is the single source of
truth. Never install a harness "latest" implicitly anywhere — the devcontainer post-create, the
agent-pod image, CI, and an `AgentTemplate`'s default all read this file. `bun` is the lone
exception: it is baked into the base image, so its home is the `BUN_VERSION` ARG in
`.devcontainer/base/Dockerfile`, not this manifest.

## Bumping a pin

- **You may NOT bump a pin without re-proving the adapter against the new version.** Editing
  `harnesses/versions.env` (or any adapter) triggers `harness-conformance`: it installs the
  pinned harnesses and runs the per-adapter conformance + the **live gated tests** (real harness +
  real provider, `-tags integration`) against them. A protocol change that breaks the adapter
  fails there — fix the normalizer and re-record the conformance fixtures **in the same PR**
  (the same re-baseline discipline as bench/apidiff in rule 20).
- **The upgrade is normally opened for you.** `harness-upgrade-check` watches upstream (npm for
  omp/codex, the claude stable channel) and opens the bump PR when a newer release appears. Your
  job on that PR is to make the gate green, not to hand-roll the bump.
- A pin bump is the **only** sanctioned way to change a harness version. `HARNESS_CHANNEL=latest`
  exists only for local upgrade-testing, never for a committed/default path.

## Why

A harness release that silently changes its stdout is exactly the break the fakes hid until a
real run exposed it (ADR-0020 context). Pinning makes every agent run reproducible; gating the
bump on the real-substrate conformance makes a protocol change fail cheaply in a PR instead of in
a production pod.
