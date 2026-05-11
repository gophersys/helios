---
name: add-env-var
description: Add a new env var to a service in all three environments (dev compose, staging helm, production helm) — enforces the all-three-envs rule.
argument-hint: "<VAR_NAME> — <which service> — <one-line purpose>"
---

# /add-env-var

> **If the value is a credential** (API token, password, key, secret), stop and use `/add-secret` instead. That flow handles the Bitwarden + K8s Secret + sync-secrets steps that this skill doesn't. Plain config (URLs, feature flags, timeouts) belongs here.

Spawn `deployer` (`.claude/agents/deployer.md`) with the env var details.

## What the agent does

The flow follows `.claude/rules/all-three-envs.md` exactly:

1. **Read in code**: add the consumer in the service's Python (or TS) code with a sensible default or explicit failure. Backend reads via `corekinect.utils.EnvConfig` subclasses; frontend reads via `import.meta.env`.

2. **Dev**: add to `deploy/development/docker-compose.yaml` under the service's `environment:` block with a dev-friendly value.

3. **Staging**: add to `deploy/production/helm/values-staging.yaml` in the right section.

4. **Production**: add to `deploy/production/helm/values-production.yaml` in the right section.

5. **Helm template**: if the deployment template needs a new `env:` entry that pulls from values, add it to `deploy/production/helm/concord/templates/<service>-deployment.yaml`. Use `{{ .Values.<service>.<key> }}` to wire it.

6. **CI guard**: add the key to `apps/backend/http-api/tests/test_env_config.py` (or the equivalent test for the service) so the helm-values-completeness check catches future drift. This test caught the `BITBUCKET_WORKSPACE` gap that broke v0.9.18.

7. **Update knowledge**: `.claude/knowledge/deploy/helm.md` for plain config (note the new key in the staging vs production table).

## Verify

- Compose stack picks it up: `nx stop platform && nx start platform`, then `docker compose exec <service> printenv | grep <VAR_NAME>`.
- Helm template renders cleanly: `nx diff platform -c staging` and `nx diff platform -c production`.
- The CI completeness test passes: `nx test http-api -- tests/test_env_config.py`.

## Don't

- Don't add to one env "for now, I'll do the others later". The CI gate catches some but not all of these; the all-three-envs discipline exists because the alternative is silent staging/production differences.
- Don't commit a real value in a `.env.example` file. Placeholders only (`replace-me`, `changeme`, `<your-token-here>`).
