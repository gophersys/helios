# codex-review-auth-property

phase: pr
repo: gophersys/infrastructure
branch: fix/codex-review-auth-property
worktree: ~/code/.worktrees/infrastructure-codex-review-auth-property
pr: -
attempt: 0/2

## Goal

Make the private review runner receive the complete Codex `auth.json` stored in
the Vaultwarden item's password property, then prove a real Eden review can
authenticate. Remove the process state file accidentally merged by the bootstrap
change.

## Plan

plan: HUMAN-APPROVED — Mateo explicitly authorized the secret-selector repair on
2026-08-27 after the first live runner proved the mounted default field was not
JSON.

1. Strengthen the focused test so it requires `remoteRef.property: password`.
2. Prove that assertion fails against the current manifest.
3. Add the selector and prove focused and repository-owned validation gates.
4. Submit and merge the narrow infrastructure PR, observe GitOps reconciliation,
   then rerun Eden pull request 25's Codex review.
5. Remove this state file before merge.

Affected targets: the `codex-review-auth` ExternalSecret and its focused test.
Fastest proof: `bash scripts/test-codex-review-auth.sh`.

Explicit exclusions: no credential value changes, no runner image rebuild, no
other runner pools, no Claude removal.

## Proven

- Live runner job 98444408756 reached the Codex action but failed login parsing
  with `expected value at line 1 column 1`.
- Read-only metadata showed the generated Kubernetes value is 89 bytes with
  first byte code 67, while the Vaultwarden password is a valid JSON object.
- RED — `bash scripts/test-codex-review-auth.sh`: exit 1 with
  `Vaultwarden password property is not selected` after adding the regression
  assertion against the current manifest.
- GREEN — `bash scripts/test-codex-review-auth.sh`: exit 0 with
  `codex-review-auth: OK` after selecting `remoteRef.property: password`.
- `shellcheck -S style scripts/test-codex-review-auth.sh` and
  `git diff --check`: exit 0, silent.
- `bash ctl.sh validate`: exit 0 after parsing six projects and linting all 35
  shell scripts.
- `bash ctl.sh verify-vault-refs`: exit 0 with `pass=15 fail=0`; the Codex item
  resolves exactly once.
- Removed `.dev/codex-review-auth.md`, which the authorized bootstrap merge
  accidentally carried onto main.

## Blocked

-

## Next

Commit, push, and open the pull request.
