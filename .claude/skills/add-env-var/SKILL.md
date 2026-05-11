---
name: add-env-var
description: Add a new env var to a service in all three environments (dev compose, staging helm, production helm) — enforces the all-three-envs rule.
argument-hint: "<VAR_NAME> — <which service> — <one-line purpose>"
---

# /add-env-var

Spawn `deployer` (`.claude/agents/deployer.md`) with the env var details.

## What the agent does

The flow follows `.claude/rules/all-three-envs.md` exactly:

1. **Read in code**: add the consumer in the service's Python (or TS) code with a sensible default or explicit failure.

2. **Dev**: add to `deploy/development/docker-compose.yaml` under the service's `environment:` block with a dev-friendly value.

3. **Staging**: add to `deploy/production/helm/values-staging.yaml` in the right section.

4. **Production**: add to `deploy/production/helm/values-production.yaml` in the right section.

5. **Helm template**: if the deployment template needs a new `env:` entry that pulls from values, add it to `deploy/production/helm/concord/templates/<service>-deployment.yaml`.

6. **CI guard**: add the key to `apps/backend/http-api/tests/test_env_config.py` (or the equivalent test for the service) so the helm-values-completeness check catches future drift.

7. **Update knowledge**: `.claude/knowledge/deploy/helm.md` for plain config, `.claude/knowledge/deploy/secrets.md` if it's a credential.

## If it's a secret

Use `/add-secret` instead — the secret flow has additional Bitwarden + K8s Secret + sync-secrets steps.

## Verify

- Compose stack picks it up: `nx stop platform && nx start platform`, `kubectl-equivalent exec → printenv`.
- Helm template renders cleanly: `nx diff platform -c staging`.
- The CI completeness test passes.
