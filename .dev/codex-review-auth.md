# codex-review-auth

phase: pr
repo: gophersys/infrastructure
branch: ci/codex-review-auth
worktree: ~/code/.worktrees/infrastructure-codex-review-auth
pr: -
attempt: 0/2

## Goal

Make the private `arc-review` runner able to execute Codex with the ChatGPT-managed
credential stored at `shared/eden/codex-review-auth`, without exposing that
credential to general build runners or placing it in GitHub Actions secrets.

## Plan

plan: SELF-APPROVED — the principal risk is credential exposure or placing a
refreshable auth file on a read-only volume. The user explicitly authorized wiring
this secret on 2026-08-26. Keep it exclusive to `arc-review`, seed a writable
ephemeral `CODEX_HOME` from a read-only Secret, and validate the exact manifest
contract before applying it through GitOps.

- Add one ExternalSecret mapping the Vaultwarden password field to `auth.json`.
- Copy that secret into a runner-private writable `emptyDir` during pod init.
- Set `CODEX_HOME` only on the credentialed review runner.
- Prove the wiring test red and green, then run repository manifest gates.
- Exclude changing Eden/cictl behavior and persisting refreshed credentials.

## Proven

- Vaultwarden item `shared/eden/codex-review-auth` exists and has a non-empty
  password property; its content was not printed.
- RED — `bash scripts/test-codex-review-auth.sh` exited 1 with
  `missing Codex ExternalSecret` against the original runner manifests.
- GREEN — `bash scripts/test-codex-review-auth.sh`: `codex-review-auth: OK`.
- `bash ./ctl.sh validate`: parsed 6 project files, linted 35 shell scripts,
  and exited 0 with `validate: OK`.
- `bash ./ctl.sh verify-vault-refs`: all 15 named items resolved exactly once,
  including `shared/eden/codex-review-auth`; no credential value was printed.
- `bash scripts/lint-manifests.sh`: 94 manifests valid, 0 invalid, 0 errors.

## Blocked

-

## Next

Submit the infrastructure pull request and inspect its checks before merge.
