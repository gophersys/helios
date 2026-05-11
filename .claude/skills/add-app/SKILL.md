---
name: add-app
description: Scaffold a new app under apps/<tier>/ with project.json, Dockerfile, tests, helm template, and the knowledge file. Run this for major new services only.
argument-hint: "<tier>/<name> — <one-line purpose>"
---

# /add-app

This is a heavy operation — a new app touches helm, CI, dev compose, and the knowledge tree. Spawn `architect` first to confirm the tier and name, then `deployer` for the helm/CI side, then the relevant `*-eng` for the service code.

## Pre-flight (architect)

Before scaffolding:
- Confirm the tier (`backend`, `frontend`, `edge`, `firmware`). The tier dictates Dockerfile base, ports, helm template skeleton.
- Confirm the name. It should match the folder, the Nx project name, the helm release name, and the K8s Deployment name. Lowercase, hyphenated.
- Verify the responsibility doesn't overlap with an existing app. Often the better answer is to extend an existing app.

## Scaffold

The agent walks roughly this list (exact files depend on tier — confirm against an existing analogue):

- `apps/<tier>/<name>/` folder.
- `apps/<tier>/<name>/project.json` with the standard targets (`build`, `test`, `serve` or `update`, `lint`, `typecheck`).
- `apps/<tier>/<name>/Dockerfile` — copy from a sibling app of the same tier and adjust.
- `apps/<tier>/<name>/src/` skeleton.
- `apps/<tier>/<name>/tests/` skeleton with one passing smoke test.
- Compose entry in `deploy/development/docker-compose.yaml`.
- Helm template `deploy/production/helm/concord/templates/<name>-deployment.yaml` + service.
- Helm values entries in `values-staging.yaml` and `values-production.yaml`.
- New knowledge file at `.claude/knowledge/apps/<tier>/<name>.md` — use the standard skeleton from sibling files.
- Add the path → knowledge mapping row in `.claude/hooks/knowledge-map.txt`.
- Update `.claude/knowledge/architecture.md` to include the new app in the diagram and tables.

## Verify

- `nx build <name>` succeeds.
- `nx start platform` brings the new service up alongside the rest.
- `nx diff platform -c staging` shows the new deployment template cleanly.
- The knowledge-freshness hook recognizes the new path.

## Don't

- Don't skip the knowledge-map update. The whole point of the maintenance system is that new code paths are accounted for.
- Don't add to the main app when it would be a separate service. Coupling is expensive in this codebase.
