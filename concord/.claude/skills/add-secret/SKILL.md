---
name: add-secret
description: Introduce a new secret (token, password, key) — stores in your team's secret store, wires to K8s Secret, syncs to cluster, and references from helm.
argument-hint: "<SECRET_NAME> — <which service> — <one-line purpose>"
---

# /add-secret

Spawn `deployer` with the secret details. The flow follows `.claude/rules/secrets-handling.md`.

## What the agent does

1. **Generate or obtain the value**: the actual credential. Never type it in chat or commit it — keep it in the terminal session only.

2. **Team secret store**: store as a new entry under whatever organization scheme your team uses (1Password vault, Vault path, encrypted file row). Note the reference key so other admins can find it during rotation.

3. **Local dev**: add `<SECRET_NAME>=<value>` to `deploy/development/.env` (gitignored). Add a placeholder line to `deploy/development/.env.example` (committed).

4. **Per-env**: add `<SECRET_NAME>=<value>` to `infrastructure/clusters/office/secrets/staging.env` and `production.env` (both gitignored). Placeholder to the corresponding `.example` files.

5. **K8s Secret template**: ensure the secret key is referenced in `deploy/production/helm/concord/templates/*-deployment.yaml` via `valueFrom.secretKeyRef`. The Secret resource itself is created by `nx run platform:sync-secrets -c <env>`, which reads the per-env `.env` files.

6. **Sync to cluster**:
   ```bash
   nx run platform:sync-secrets -c staging
   nx run platform:sync-secrets -c production
   ```

7. **Rolling restart** the affected deployments to pick up the new env:
   ```bash
   kubectl -n staging rollout restart deploy/<name>
   kubectl -n production rollout restart deploy/<name>
   ```

8. **Update knowledge**: `.claude/knowledge/deploy/secrets.md` — add the new row to the inventory.

## Don't

- Don't commit the real value. Only `.example` files (with `replace-me` or similar) go into git.
- Don't put the secret in helm values files. Always reference via `secretKeyRef`.
- Don't log the secret. Sanitize before any debug output.

## If the secret needs rotation later

The same flow in reverse: new value to your team's secret store, update per-env `.env`, `sync-secrets`, rolling restart. See `.claude/rules/secrets-handling.md`.
