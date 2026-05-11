# Nx is the only entry point

Build, test, lint, run, deploy, release — everything goes through Nx. Never invoke the underlying tooling directly.

## Forbidden

- `docker build`, `docker run`, `docker compose up`, `docker compose down`
- `helm install`, `helm upgrade`, `helm rollback`
- `kubectl apply -f deploy/...` (kubectl for read-only inspection is fine)
- `pnpm run`, `yarn <script>`, `npm run` for project commands
- `pytest`, `vitest`, `playwright test` directly
- `bash deploy/ctl.sh ...`
- `prisma migrate`, `prisma generate` directly

## Correct

- `nx start platform` / `nx stop platform` — local dev stack via docker-compose
- `nx serve app` / `nx serve docs` / `nx serve ci-admin` — frontend dev servers
- `nx update platform -c <env>` — build images, push, helm upgrade, verify rollout, smoke test
- `nx diff platform -c <env>` — preview helm changes
- `nx rollback platform -c <env>` — undo last deploy
- `nx test <project>` — run tests
- `nx typecheck <project>`, `nx run <project>:lint`
- `nx run <project>:build` for build outputs

## Why

Nx caches, parallelizes, and tracks the dependency graph. Bypassing it leads to:

- Cache misses (slow builds)
- Forgotten preflight checks (broken env files, missing secrets, unreachable cluster)
- Skipped smoke tests after deploys
- Tag drift between built images and helm release
- Migration init-container not running because the local image was tagged inconsistently

The wrappers exist *because* the bare commands have sharp edges in this repo.

## Inspecting what an Nx target actually runs

`nx run <project>:<target> --dry-run` shows the underlying command without executing it. Use this when you suspect Nx is doing something unexpected — but still run through Nx in the end.

`cat <project>/project.json` shows the target definitions directly.

## Adding a new Nx target

When a new operation needs to exist (e.g., "regenerate fixtures from a CSV"), add it to the relevant `project.json` `targets` block — do not write a top-level bash script that bypasses Nx. The contract is: every action a developer takes against this repo is an Nx target.
