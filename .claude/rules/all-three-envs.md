# Any env-var or config change touches all three environments

The platform runs in three environments. Any change to configuration that exists in one **must** be reflected in all three, in the same commit.

## The three layers

| Environment | Config source | File |
|---|---|---|
| development | docker-compose | `deploy/development/docker-compose.yaml` |
| staging | Helm values | `deploy/production/helm/values-staging.yaml` |
| production | Helm values | `deploy/production/helm/values-production.yaml` |

(Secrets — values that differ per env or must not be in git — live elsewhere. See [`secrets-handling.md`](secrets-handling.md).)

## What this means in practice

Adding an env var consumed by, say, `concord-http-api`:

1. Read the var in Python code with a sensible default or explicit failure.
2. Add it to `deploy/development/docker-compose.yaml` under the service's `environment:` block — with a dev-friendly value.
3. Add it to `deploy/production/helm/values-staging.yaml` under the relevant section.
4. Add it to `deploy/production/helm/values-production.yaml` under the relevant section.
5. If the helm template (`deploy/production/helm/concord/templates/http-api-deployment.yaml` or similar) needs a new `env:` entry that reads from values, add that too.
6. Update `.claude/knowledge/deploy/secrets.md` (if a credential) or `.claude/knowledge/deploy/helm.md` (otherwise).

If you only add it to staging values, production breaks at next deploy. If you only add it to docker-compose, the dev passes but staging fails. The CI helm-values-completeness check (added in v0.9.18) will catch some of these, but you should fix it at the source.

## Existing examples

- `BITBUCKET_API_TOKEN` lives in all three (dev: from `.env`, staging/production: from K8s Secret synced via `tools/env/`).
- `BITBUCKET_WORKSPACE` was the missed one that caused v0.9.18 — present in code, absent from values files. Fixed by adding to both helm values and as a required key in the CI check.
- `MOTION_ENABLED` is derived per fixture at MTIB deploy time, not from helm — but the http-api code that derives it lives in three matching places (dev, staging, prod) and was the basis of the architectural fix to `_mtib_env_for_fixture(fixture)`.

## What doesn't apply

- One-off feature flags that intentionally only exist in one env (rare). Document the exception in the values file with a comment explaining why production doesn't have it.
- Local dev convenience values (e.g., `AUTH_ENABLED=false`) — production never sets these; that's expected.

## Hook coverage

The knowledge-freshness hook will flag the deploy knowledge file when you touch `deploy/`, but it cannot tell whether you updated all three env files. That's a discipline.
