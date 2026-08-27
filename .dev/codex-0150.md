# codex-0150

phase:    verify
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
- RED — compared the edited `versions.env` pin with `codex --version` inside pod `arc-org-wgxks-runner-r65bv`, running immutable cloud digest `sha256:ffdcf5046c4dc30be32f6388bbe09c055abff03bab78db703432793b8c5da7bd`: `expected=0.150.1 actual=0.146.0`; `test` exited 1.
- GREEN — `devcontainer exec ... bash ./ctl.sh validate`: `validate: OK` with pinned ShellCheck 0.9.0 and Hadolint 2.15.1.
- GREEN — `docker run --rm --user dev --mount type=bind,source=/Users/mateo/code,target=/Users/mateo/code ... bash ./ctl.sh test`: `test: OK (26 files)`.
- Invalid environment run retained for diagnosis: mounting the worktree at `/workspace` made Git worktree pointers unresolvable and `guard.test.sh` failed `cannot determine short SHA`; rerunning at the real absolute path passed all 26 files.

## Blocked


## Next
Commit the pin, push the branch, open the pull request, and read every remote check.
