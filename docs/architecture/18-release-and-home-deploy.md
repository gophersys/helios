# 18 — Release and home deploy (the stable-release runbook)

> Status: Accepted · 2026-07-08 · Canonical home for: the operational flow of Eden's stable-release
> channel — the one-verb cut, the `release.yml` job-by-job build, the digest-pin GitOps promotion,
> the Argo reconcile path, the backing-stack prerequisites, and the demo-vs-release distinction.
> The RULING (why tag-driven, why the `ghcr.io/gophersys/eden/*` prefix, why one `eden` namespace,
> why Vault-native token-file secrets, why static+nginx, why digest-pinned promotion) is
> [ADR-0028](adr/0028-stable-release-channel-and-home-deploy.md) — this doc cites it, never
> re-decides it. The home-cluster backing stack + the out-of-band ceremony live in
> `infrastructure/apps/eden/README.md`; this doc cites that runbook, never restates its `kubectl`.

## 1. The one-verb flow ✅

A stable release is one human action:

```sh
bash deploy/ctl.sh release v<semver>     # e.g. v0.1.4
```

`release_cut` (`deploy/ctl.sh`) validates, in order: a `v`-prefixed semver; the tag is unused
locally AND on origin (a released version is immutable); a clean working tree; the current branch is
up-to-date with its `origin/<branch>` counterpart; and `harnesses/versions.env` is tracked with a
non-empty `CLAUDE_CODE_VERSION` (the agent-runtime build needs the committed pin — ADR-0021). It
then creates an **annotated** tag (signed-tag git configs reject a messageless tag) and pushes it.
The **tag push is the only trigger** for the pipeline. The verb NEVER prints a credential.

Then watch the cut without leaving the verb:

```sh
bash deploy/ctl.sh release-status v<semver>
```

`release_status` reports three things, each degrading HONESTLY when its tool/credential is absent
(never fabricating a status, never printing a secret): the `release.yml` runs for the tag (`gh run
list`), the open infrastructure promotion PR (`chore(deploy): eden -> <version>`), and — read-only —
the Argo `Application/eden` on the home cluster when a kubeconfig is present.

## 2. What `release.yml` does, job-by-job 🧩

The pipeline is authored **byte-identically** in `.github/workflows/release.yml` AND
`.ci/providers/github/release.yml` (the provider-pair convention — edit both together). It runs on
the org ARC fleet (`runs-on: arc-org`). Version/sha/pin derivation is the ONE home
`.ci/release-meta.sh` (`version` = the tag on a tag push, `<short-sha>-dispatch` on a dispatch;
`claude_code_version` from `harnesses/versions.env`). All four build jobs run **serially** (the ARC
fleet seats one runner at a time — see lesson L2):

| Job | Builds | Arch | Notes |
|---|---|---|---|
| `agentgateway` | `agentgateway.Dockerfile` | multi-arch (amd64+arm64) | The stateless NATS→SSE bridge; also the orchestrator binary via a command override. |
| `agent-runtime` | `agent-runtime.Dockerfile` | **amd64 only** | The PID-1 agent pod. `FROM` the PRIVATE `ghcr.io/gophersys/base` → pre-pulled with the pull PAT into the local store, built on the `docker` driver (see L4). Bakes the pinned Claude Code harness via the REQUIRED `CLAUDE_CODE_VERSION` build-arg. |
| `platformgateway` | `apps/platformgateway/deploy/Dockerfile` | multi-arch | Eden's platform HTTP API (users + login + RBAC). |
| `frontend` | `apps/frontend/deploy/Dockerfile` | multi-arch | Static SvelteKit SPA + nginx. Builds the `@eden/*` libs in the base devcontainer image FIRST (the toolchain-carrying substrate) so the image consumes the prebuilt `dist/` (see L5); heaviest, runs last. |

Each build job pushes three tags — `{v<semver>, latest, sha-<short>}` — to
`ghcr.io/gophersys/eden/<service>`, logging in as `GITHUB_TOKEN` for the push, and exports the image
**digest** as a job output. The checkout uses the org PAT (`HARNESS_BOT_TOKEN`), not `GITHUB_TOKEN`,
because the Dockerfiles COPY the PRIVATE sibling submodules (`libs` / `infrastructure` /
`.devcontainer`) that `GITHUB_TOKEN` cannot clone.

## 3. Promotion → Argo (the deploy path) ✅

The `promote` job needs all four builds. It checks out **eden first** (`release-meta.sh` lives here —
see L6), resolves the version, checks out `gophersys/infrastructure`, then runs
`.ci/pin-eden-digests.sh` to rewrite every `apps/eden/*` Deployment `image:` line to the freshly-built
**digest** (`ghcr.io/gophersys/eden/<service>@sha256:…`, keyed on the ref stem so it is robust to file
layout; agentgateway AND orchestrator both pin to the one agentgateway digest). It opens a PR against
`gophersys/infrastructure` (title `chore(deploy): eden -> <version>`) using the org PAT so the PR
triggers infrastructure's own CI. On merge, Argo CD (`Application eden`, project `apps`;
`selfHeal + prune + ServerSideApply`) reconciles `apps/eden/` onto the home cluster, ns `eden`,
served at `https://eden.mateosegura.com`. The release path touches the cluster ONLY through git —
never `kubectl apply` (ADR-0028 §6; the standing GitOps/no-hand-created-Secrets rule).

## 4. Backing-stack prerequisites + the four imperative secrets ✅

The workload Deployments assume a home-cluster backing stack that is NOT part of a release: Postgres,
NATS, and a file-storage Vault (+ the seed Job, the bootstrap `ExternalSecret`, RBAC, and the
ingress) — all owned by `infrastructure/apps/eden/` and synced by Argo, EXCEPT the out-of-band secret
material + the Vault ceremony, which GitOps cannot do. Four **imperative** secrets are created by hand
once, per the `infrastructure/apps/eden/README.md` runbook (NAMES only here — values live only in the
operator's terminal / password manager; never in git, never printed):

| Secret (name only) | What it gates |
|---|---|
| `ghcr-pull` (docker-registry) | Pulling the PRIVATE `ghcr.io/gophersys/eden/*` images (every workload SA references it). |
| `eden-orchestrator-postgres` | The Postgres password (`DATABASE_URL`) — the ONE plain k8s Secret in the plane. |
| `eden-vault-init` | The Vault init ceremony (unseal key + root token); the seed Job reads the root token. |
| Vaultwarden `shared/eden/*` items | The bootstrap `ExternalSecret` (optional harness creds → Secret `eden-bootstrap`, copied into Vault by the seed Job). |

The seed Job then mints `eden-vault-token` (the token-file the pods mount) and seeds `eden/production`;
app secrets are Vault-native `vault://eden/production#…` refs resolved in `token-file` mode (ADR-0028
§4). See `infrastructure/apps/eden/README.md` for the exact ceremony — do not restate its `kubectl`
here.

## 5. Verification ✅

Three read-only checks, none of which prints a secret:

1. **The verb.** `bash deploy/ctl.sh release-status v<semver>` — the `release.yml` runs, the open
   promotion PR, and the Argo `Application/eden` (read-only, when a kubeconfig is present).
2. **`kubectl` GET-only** (home context): confirm the workloads are Ready and pinned to the release
   digests, e.g. `kubectl -n eden get pods,deploy` and
   `kubectl -n eden get deploy -o jsonpath='{..image}'`. GET only — never `apply` (§3).
3. **The browser.** Open `https://eden.mateosegura.com` (on the tailnet): the frontend serves, login
   works, the same-origin platform API responds.

## 6. Troubleshooting — the six pipeline lessons (v0.1.0→v0.1.4) 🧩

Each lesson is a defect that a real cut surfaced and the fix that is now baked into `release.yml`.

| # | Symptom | Root cause | Fix (in `release.yml`) |
|---|---|---|---|
| L1 | The libs build failed on a fresh runner | root's profile has no nvm — the toolchain is profile-homed, not on PATH | Build the `@eden/*` libs inside the base **devcontainer image** (the toolchain-carrying ADR-0022 substrate), not on the bare runner. |
| L2 | Three concurrent build jobs never got runners | the ARC fleet seats **one** runner at a time | **Serialize** the four builds into a `needs:` chain (`agentgateway → agent-runtime → platformgateway → frontend`). |
| L3 | BuildKit got a 403 resolving the base image | `GITHUB_TOKEN`'s `packages:read` covers only packages linked to THIS repo; the base is a PRIVATE cross-repo package, and one docker config holds one identity per registry | **Pre-pull the private base** with the pull PAT (`GHCR_PULL_TOKEN`) into the local store, re-login as `GITHUB_TOKEN`, and build **amd64-only on the `docker` driver** (which resolves `FROM` from the local store). Multi-arch returns when the base goes public. |
| L4 | The libs build missed `yarn` even under a login shell | the `@eden/*` libs are a self-contained **bun** workspace; `yarn`/nvm are profile-gated and not needed | Install with **`bun install --frozen-lockfile`** (bun is on the image ENV PATH, uid-independent), NOT nvm's yarn. |
| L5 | The frontend image could not resolve the Svelte build | the toolchain resolves only through the workspace install, and the lean bun-alpine build stage does not carry it | Prebuild the libs' `dist/` in the base devcontainer image and have the Dockerfile's scoped `.dockerignore` un-ignore it for the image build (adapter-static → nginx). |
| L6 | The `promote` job exited 127 | it had checked out only the infrastructure repo (into a subdir), so `.ci/release-meta.sh` did not exist | **Check out eden first** in `promote` (release-meta lives here), THEN the infrastructure repo into `./infrastructure`. |

## 7. Demo vs. release — a hard distinction ⚠️

Two different things share the `deploy/ctl.sh` entrypoint; do not conflate them:

- **`deploy/ctl.sh demo`** is the LOCAL demo: the whole stack (Vault + NATS + Postgres) + both
  gateways + the frontend run INSIDE the base devcontainer (`go run` gateways, vite dev server,
  a `socat` sidecar publishing the UI to the Mac host). It is ephemeral, single-machine, and for
  hands-on iteration. It does NOT touch the home cluster or ghcr.
- **`deploy/ctl.sh release v<semver>`** is the STABLE channel: it builds+pushes versioned images to
  `ghcr.io/gophersys/eden/*` and promotes them onto the home cluster via GitOps (this doc). It is
  durable, versioned, multi-machine, and Argo-reconciled.

"phase" = an SDLC step; "stage" = the environment axis — the home deploy is the `production` stage,
never a "phase" of the pipeline. (Frontend dev gates now run IN the devcontainer: a host-side
`yarn/npm install` overwrites the bind-mounted `node_modules` with darwin bindings and the
in-container vite then 500s on the missing linux `rolldown` binding — see the demo-infra note in the
UI frontier.)
