# Secrets handling

Secrets never go in git. Period.

## What counts as a secret

- API tokens (Bitbucket, Google OAuth, CoreOps, anything third-party).
- Passwords (Postgres, MinIO, anything with a password field).
- Private keys (SSH, JWT signing keys, TLS cert keys).
- Webhook signing secrets (HMAC).
- Anything in a K8s `Secret` resource.

## Where they live

| Layer | Storage | Used by |
|---|---|---|
| Production / staging | K8s `Secret` resources in their namespace | running pods |
| Source of truth | Your team's secret store (1Password, Vault, encrypted file — admin's call) | humans, before they sync to K8s |
| Sync mechanism | `infrastructure/clusters/office/secrets/create-all.sh` reads `shared.env` + per-env `.env` files | applies as K8s Secrets |
| Local dev | `deploy/development/.env` (gitignored) and per-service `.env` files (gitignored) | docker-compose |
| Templates | `.env.example` files (committed) | onboarding new devs |

See `.claude/knowledge/deploy/secrets.md` for the master inventory and the per-secret rotation flow.

## What goes in git

- `.env.example` files with **placeholder** values (e.g., `BITBUCKET_API_TOKEN=replace-me`).
- `shared.env` if and only if it contains paths and non-sensitive defaults — never raw secrets.
- K8s manifests and helm templates that *reference* Secrets (`valueFrom.secretKeyRef`), not the secret values.
- Documentation that describes *where* a secret lives, not what it is.

## What never goes in git

- Real token values.
- Decoded JWT tokens.
- `.env` files without `.example` suffix.
- Test fixtures with embedded real credentials.
- Screenshots or logs that show secrets in plaintext.

## If a secret leaks

1. Rotate it immediately. The leaked value is dead the moment it's in git, even if you force-push it out.
2. Update your team's secret store with the new value.
3. Re-sync K8s Secrets: `nx run platform:sync-secrets -c staging` and `-c production`.
4. Restart the affected deployments (rolling restart picks up the new env).
5. File an incident note under `/home/mateo/work/docs/incidents/`.

`git filter-repo` to scrub history is a secondary action — the rotation must happen first because anyone watching the public repo state has the leaked value.

## CI

CI pipelines read secrets from the CI Helm chart's Secret resources (or the Bitbucket pipeline variables panel for some). The same rule applies: only references in YAML, never raw values.

## Logging

Never log a secret. The audit log explicitly forbids JWTs and credentials in `details` (see `audit-logging.md`). The Python `logging` config strips known secret env vars from tracebacks where possible — but the safer pattern is to never let a secret reach a log statement in the first place.

## Reviewing PRs

When reviewing a diff that adds a config file: `git diff | grep -iE 'token|password|secret|key' | grep -v '\.example\|placeholder\|valueFrom'`. If anything matches with a real-looking value, block the PR.
