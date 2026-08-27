# codex-0150

phase:    plan
repo:     gophersys/.devcontainer
branch:   chore/codex-0150
worktree: ~/code/.worktrees/devcontainer-codex-0150
pr:       -
attempt:  0/2

## Goal
Publish the trusted devcontainer image set with Codex 0.150.1 so agent review runs use a baked, verified CLI instead of mutating runner pods at runtime.

## Plan
Change the single canonical Codex pin, prove the old published cloud image fails that new version contract, run the repository gates, and merge only after CI builds, smokes, and publishes the affected graph. Verify the immutable cloud artifact before any consumer is repointed.

plan: SELF-APPROVED — weighed the full six-image rebuild caused by the one-pin-home invariant against introducing a divergent cloud-only pin; preserving the invariant is safer.

Acceptance evidence: the old cloud image reports 0.146.0 against the new 0.150.1 contract (red); local validation and tests pass; publish CI smokes each affected image; the published cloud image reports 0.150.1 by immutable digest.

Affected: `versions.env` and the generated image build graph. Agent instrumentation changes: none; both Claude and Codex remain baked from the same canonical pin file. Excludes runtime npm installation, cictl behavior changes, and deployment changes.

## Proven
- `git rev-parse HEAD` at intake: `b5684eb5e1695a36bf9d01692efd11c3186abd45`.
- `images.yaml` inspection: `versions.env` is an input of both `base` and `cloud`; their descendants therefore rebuild through the declared parent graph.

## Blocked


## Next
Commit intake, change `CODEX_VERSION`, and prove the current published cloud image violates the new pin.
