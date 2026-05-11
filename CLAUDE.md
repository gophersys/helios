# Concord — Claude Code orientation

You are working inside the **Concord monorepo**: the CoreKinect platform that owns firmware builds, validation, manufacturing, fixture management, and device orchestration.

This file is loaded automatically at the start of every Claude Code session in this repo. Read it first; everything else flows from here.

## What `.claude/` is

A self-contained guidance system. A developer can clone a virgin repo, open it in Claude Code, and ask either:

- "How do I get started?" → `/start-here`
- "I want to add feature X" → `/plan-feature`

…and the right specialist agents load with the right knowledge to drive the work.

The folder has five top-level pieces:

| Folder | Purpose | When loaded |
|---|---|---|
| `.claude/agents/` | Specialist personas (system prompts). One per service, plus three high-level roles (architect, planner, deployer). | Spawned by skills as needed. |
| `.claude/skills/` | User-invocable workflows (slash commands). Short entry points that reference the rest. | When the user types `/skill-name`. |
| `.claude/knowledge/` | The substrate. Mirrors repo paths (`apps/backend/http-api.md` describes the code at `apps/backend/http-api/`). | Read on demand by agents. |
| `.claude/rules/` | Unconditional behaviors. Auto-loaded into every session. | Always. |
| `.claude/hooks/` | Git/Claude lifecycle scripts. | Triggered by events. |

## The non-negotiable rule

**If you change code, you update the matching `.claude/knowledge/` file in the same commit.**

The git `commit-msg` hook at `.claude/hooks/commit-msg` enforces this — install once with `.claude/hooks/install.sh` (sets `core.hooksPath`). The only escape hatch is `[no-arch-change]` in the commit message — use it for typos, formatting, log message tweaks, version bumps. Anything that changes behavior or shape requires the knowledge update.

See [`.claude/rules/update-knowledge-on-change.md`](.claude/rules/update-knowledge-on-change.md) for the full policy and the path map.

## Path-mirroring naming

Every code path in this repo has a corresponding knowledge file:

| Code path | Knowledge file |
|---|---|
| `apps/backend/http-api/` | `.claude/knowledge/apps/backend/http-api.md` |
| `apps/frontend/app/` | `.claude/knowledge/apps/frontend/app.md` |
| `apps/edge/mtib-server/` | `.claude/knowledge/apps/edge/mtib-server.md` |
| `libs/python/` | `.claude/knowledge/libs/python-corekinect.md` |
| `tools/corectl/` | `.claude/knowledge/tools/corectl.md` |
| `infrastructure/` | `.claude/knowledge/infrastructure.md` |
| `prisma/schema.prisma` | `.claude/knowledge/prisma/schema-overview.md` |
| `deploy/` | `.claude/knowledge/deploy/{helm,ctl-sh,nx-targets,secrets,...}.md` |

When you see a path, you know where its knowledge lives. When you write new knowledge, you put it at the path that mirrors the code. The full map is at [`.claude/hooks/knowledge-map.txt`](.claude/hooks/knowledge-map.txt).

## Starting points by intent

| You want to… | Run |
|---|---|
| Set up a fresh clone | `/start-here` |
| Add a new feature | `/plan-feature` |
| Add a v2 API endpoint | `/add-endpoint` |
| Add a SvelteKit page (main app) | `/add-page` |
| Add a Prisma model or enum value | `/add-prisma-model` |
| Add an env var (non-secret) | `/add-env-var` |
| Add a secret (credential) | `/add-secret` |
| Add a new app | `/add-app` |
| Stand up a new fixture | `/add-fixture` |
| Onboard a new MTIB Verdin node | `/onboard-mtib` |
| Deploy staging | `/deploy-staging` |
| Deploy production | `/deploy-production` |
| Cut a versioned release (bump + tag + wheel + record) | `/concord-release` |
| Debug a production issue | `/debug-prod` |
| Audit `.claude/` for drift | `/refresh-claude` |
| Just refresh your knowledge | Read [`.claude/knowledge/architecture.md`](.claude/knowledge/architecture.md) |

**`/concord-release` vs `/deploy-production`**: `/concord-release` is the full release flow — bumps the `VERSION` file, builds + tags images, publishes the corekinect/corectl wheels, creates the release record, then deploys. `/deploy-production` is the deploy step alone, used for patch redeploys that don't need a new version cut.

## Agents and when to spawn which

Three high-level roles + nine per-service specialists. The skill files spawn the right one(s) for you, but if you're choosing directly:

| Agent | Owns | When |
|---|---|---|
| `architect` | System-wide design + cross-cutting | "Where does this belong?" / consistency checks / trade-off calls. |
| `planner` | Feature decomposition | "I want to add X" — produces a file-level plan with handoffs. |
| `deployer` | Helm, K8s, ctl.sh, secrets, release flow | Anything between a green build and a running pod. |
| `http-api-eng` | `apps/backend/http-api/` | v2 endpoints, Prisma access, auth, audit, SocketIO, K8s job scheduling. |
| `frontend-eng` | `apps/frontend/app/` (main user UI) | SvelteKit routes, components, `api.ts`, `models.ts` mirror. |
| `frontend-docs-eng` | `apps/frontend/docs/` (MkDocs site) | User-facing documentation site, role-based visibility. Distinct from `frontend-eng` — different app, different audience. |
| `ci-admin-eng` | `apps/frontend/ci-admin/` + `deploy/ci/` | The standalone CI dashboard + cronjobs. Independent of main platform. |
| `mtib-edge-eng` | `apps/edge/mtib-server/` + Python MTIB client | gRPC hardware control on Verdin fixture nodes. ARM64. |
| `firmware-eng` | `apps/firmware/` + `libs/embedded/` + `libs/zephyr/` | Zephyr/ESP-IDF/nRF Connect SDK end-user firmware (icle today). **Not** the MTIB server — that's `mtib-edge-eng`. |
| `build-service-eng` | `apps/backend/build-service/` | Firmware compilation worker, Bitbucket SSH, MinIO uploads. |
| `git-poller-eng` | `apps/backend/git-poller/` | Bitbucket repo polling and build dispatch. |
| `corekinect-sdk-eng` | `libs/python/` (the SDK) | Shared Python SDK consumed by every Python service + corectl. |
| `db-schema-eng` | `prisma/` | Schema, migrations, enum values, frontend type mirror discipline. |

## The five things to know before doing anything

1. **Nx is the only entry point** for build, test, deploy, run. Never invoke `docker`, `helm`, `pnpm`, `pytest`, or `ctl.sh` directly. See [`.claude/rules/nx-only.md`](.claude/rules/nx-only.md).
2. **Three environments**: development (Docker Compose), staging (K8s), production (K8s). Any config touching one **must** touch all three. See [`.claude/rules/all-three-envs.md`](.claude/rules/all-three-envs.md).
3. **Every mutating endpoint** uses `@require_permissions(...)` and calls `log_audit(...)`. No exceptions. See [`.claude/rules/auth-defaults.md`](.claude/rules/auth-defaults.md) and [`.claude/rules/audit-logging.md`](.claude/rules/audit-logging.md).
4. **The HTTP API is the hub.** Frontend, build-service, git-poller, MTIB observability, corectl — they all talk to it. State changes go through it. See [`.claude/knowledge/architecture.md`](.claude/knowledge/architecture.md).
5. **Schema changes go through Prisma**, and the frontend `models.ts` must be kept in sync by hand. See [`.claude/rules/prisma-flow.md`](.claude/rules/prisma-flow.md).

## Identity & commit style

- Commits authored as `Mateo Segura <mateo@corekinect.com>`.
- Conventional Commits: `<type>(<scope>): <imperative subject>`.
- **Never** mention Claude, AI, LLM, or any automated tool in commit messages, code comments, or docs.

See [`.claude/rules/git-commits.md`](.claude/rules/git-commits.md).

## How to navigate the knowledge

Start with [`.claude/knowledge/architecture.md`](.claude/knowledge/architecture.md). It gives the system diagram, request lifecycle, and pointers into every other knowledge file. From there, drill into whatever the task touches.

If you can't find what you're looking for, the most likely problem is that the knowledge file is stale or missing — fix it in the same commit as your change. That's the whole point.
