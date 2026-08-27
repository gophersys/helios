# codex-password-store

phase: wait
repo: gophersys/infrastructure
branch: fix/codex-password-store
worktree: ~/code/.worktrees/infrastructure-codex-password-store
pr: 207
attempt: 0/2

## Goal

Give the private review runner the complete Codex `auth.json` stored in a
Vaultwarden login password without changing the notes-backed contract used by
existing secrets.

## Plan

plan: HUMAN-APPROVED — Mateo explicitly authorized a dedicated
`vaultwarden-password` ClusterSecretStore on 2026-08-27 after live proof showed
the existing webhook store always returns item notes.

1. Strengthen the focused test to require the dedicated store, its login-password
   JSONPath, and the Codex ExternalSecret's reference to it.
2. Prove the new assertions fail against current main.
3. Add the isolated store and repoint only the Codex ExternalSecret.
4. Run focused, shell, manifest, and vault-reference validation.
5. Submit and perform the authorized bootstrap merge; observe GitOps and prove
   the generated value is a JSON object without exposing it.
6. Rerun Eden pull request 25's Codex review.

Affected targets: the secrets bridge's store definitions, the Codex review
ExternalSecret, and their focused test. Fastest proof:
`bash scripts/test-codex-review-auth.sh`.

Explicit exclusions: no Vaultwarden item mutation, no changes to the existing
`vaultwarden` store, no other ExternalSecret migrations, no runner image rebuild.

## Proven

- The live `vaultwarden` ClusterSecretStore uses the fixed result JSONPath
  `$.data.data[0].notes`; its generated Codex secret remained an 89-byte non-JSON
  note after `remoteRef.property: password` reconciled.
- RED — `bash scripts/test-codex-review-auth.sh`: exit 1 with
  `missing password-backed ClusterSecretStore` after adding the regression
  assertions against current main.
- GREEN — `bash scripts/test-codex-review-auth.sh`: exit 0 with
  `codex-review-auth: OK` after adding the isolated store and repointing only the
  Codex ExternalSecret.
- `shellcheck -S style scripts/test-codex-review-auth.sh` and
  `git diff --check`: exit 0, silent.
- `bash ctl.sh validate`: exit 0 after parsing six projects and linting all 35
  shell scripts.
- `bash ctl.sh verify-vault-refs`: exit 0 with `pass=15 fail=0`.

## Blocked

-

## Next

Poll pull request 207 and inspect every completed check log.
