# ADR-0021: Harness version management — pinned, reproducible, gated upgrades

- **Status:** Accepted
- **Date:** 2026-06-13
- **Deciders:** Mateo

## Context

Eden orchestrates external agent harnesses — Claude Code (`claude`), Oh My Pi (`omp`), and
Codex (`codex`) — each a third-party CLI with its **own release cadence**. Each adapter
(`libs/go/agentsession/<harness>adapter`) parses that harness's streamed protocol (stream-json /
`--mode json` / `exec --json`). When a harness ships a new release it can change that protocol —
exactly the class of break that hid behind the fakes until a real `claude` run exposed the
missing `-p` (see ADR-0020 context, [[harness-platform-architecture]]). Two requirements follow:

1. **Reproducibility.** An agent run must use a *known, fixed* harness version — "run fixed
   versions so the harness requirements are met" (Mateo, 2026-06-13). Installing "latest"
   implicitly makes a run irreproducible and lets an upstream release silently change behaviour
   in production.
2. **Maintainability.** "Whenever a new version of the agents is released we have to update our
   harnesses" — so the upgrade must be a **routine, automated, gated** event, not a manual
   scramble, and it must scale as a long-term project across three (soon more) harnesses.

The devcontainer (`ghcr.io/gophersys/base`) is both the dev substrate and the CI runtime and is
the image spawned agent pods dogfood, so the same pin must reach the dev box, CI, and the pod.

## Decision

### One source of truth — `harnesses/versions.env`

The exact harness CLI versions Eden runs are pinned in a single shell-sourceable manifest,
`harnesses/versions.env` (`CLAUDE_CODE_VERSION`, `OMP_VERSION`, `CODEX_VERSION`). It is the one
home for those pins; every consumer reads it and nothing installs "latest" implicitly:

- **Devcontainer post-create** installs those exact versions (claude via `install.sh <version>`,
  omp/codex via `npm install -g <pkg>@<version>`). `HARNESS_CHANNEL=latest` overrides — the only
  sanctioned way to run unpinned, used by the upgrade-test path below.
- **The agent-pod image** (`apps/agent-runtime`, Milestone B) bakes the same pins, so a spawned
  pod runs a reproducible harness with no network install.
- **An `AgentTemplate`** may request a specific harness version; absent that, it defaults to the
  platform pin.
- **CI** installs the pinned versions and runs the adapter conformance + live gated tests against
  them (below).

`bun` is **not** in the manifest: it is baked into the base image, so its one home is the
`BUN_VERSION` ARG in `.devcontainer/base/Dockerfile` (the agent-pod image inherits it `FROM`
base). The manifest owns only the post-create-installed harness CLIs.

### A pin bump is a gated event, never silent

Changing a pin in `harnesses/versions.env` is the **only** way to upgrade a harness, and the
change is gated: the per-adapter **conformance** suite plus the **live gated tests** (real
harness + real provider, the `integration` lane) MUST pass against the new version before the
bump merges. A protocol change that breaks an adapter fails the gate on the bump PR, where it is
cheap to fix (adjust the normalizer + re-record fixtures) — never in production. The live tests
need the harness bootstrap credentials as CI secrets (`CLAUDEADAPTER_LIVE_TOKEN`,
`OPENROUTER_API_KEY`); absent them the conformance fixtures still run, but the live verification —
the part that actually catches a real protocol drift — is skipped, so the secrets are required
for a *merge-eligible* bump. (This is the CI "bootstrap credential" tier of
[[eden-secrets-and-deploy-architecture]]; it migrates to the secret manager with the rest.)

### Upstream is watched; the bump PR is opened automatically

A scheduled CI job (`harness-upgrade-check`) queries each upstream (npm for omp/codex, the claude
release channel) for the latest release, compares to the manifest, and when a newer version
exists opens a PR that bumps `harnesses/versions.env`. That PR runs the gate above and is
mergeable only when green. New harness, routine cadence, controlled blast radius.

## Consequences

- Reproducible agent runs; an upstream release cannot change Eden's behaviour until a green,
  reviewed bump PR lands.
- The cost of an upgrade is bounded and front-loaded into a PR with a real-substrate gate.
- Adding a harness = an adapter + one manifest line + one upstream-check entry — the process
  scales without new machinery.
- The conformance fixtures must be re-recordable per version; a bump that changes the protocol
  re-records them in the same PR (mirrors the ADR-0020 bench/api re-baseline pattern).

This ADR extends ADR-0020 (the test taxonomy supplies the conformance + live lanes the gate
runs) and is cited by the devcontainer foundation (`.devcontainer/base`) and the agent-runtime
build spec.
