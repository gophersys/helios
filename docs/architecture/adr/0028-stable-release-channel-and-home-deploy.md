# ADR-0028: The stable release channel and home-cluster deploy

- **Status:** Accepted (the tag-driven stable channel + the home-cluster deploy shape are ratified
  and PROVEN end-to-end — `v0.1.0`→`v0.1.4` cut, built, pushed, and seeded the home cluster; see
  Implementation status)
- **Date:** 2026-07-08
- **Deciders:** Mateo (ratified the one-verb tag-driven channel, the `ghcr.io/gophersys/eden/*`
  prefix, the single `eden` namespace, the Vault-native app-secret plane, static+nginx same-origin
  frontend serving, and digest-pinned GitOps promotion)

## Context

Eden has a live local demo (ADR-0022 `deploy/ctl.sh demo` — the whole stack in the devcontainer)
and a typed render catalog that already emits both compose and Helm from one `ServiceSpec`
(`deploy/servicespec/`). What it did NOT have was a **stable release to a real cluster**: a durable,
versioned artifact set running at a public URL, driven the same GitOps way the rest of the fleet is.

The forces:

- **One artifact origin, one signal.** Eden ships four deployable images (agentgateway — also the
  orchestrator binary via a command override; agent-runtime — the PID-1 agent pod; platformgateway;
  frontend). They must version together off ONE human action, not four ad-hoc pushes.
- **The home cluster is GitOps-driven.** `gophersys/infrastructure` is reconciled by Argo CD; the
  standing secrets rule (CLAUDE.md) forbids hand-created k8s Secrets and `kubectl apply` outside
  break-glass. A release must therefore land as a **git change to `infrastructure/`**, not a push.
- **Eden's secrets are Vault-native, not k8s Secrets.** Milestone B (ADR-0022) already built the
  dual-mode Vault provider and the `vault://eden/production#…` reference grammar. Folding JWT signing
  keys / harness credentials into k8s Secrets would fork the secret plane and break the canary
  redaction property. The release must consume the SAME references the demo does.
- **The frontend is a static SvelteKit SPA.** It has no server runtime of its own; it needs a
  serving surface that also gives the browser a same-origin path to the platform API (no CORS, no
  second public hostname).
- **The channel is an AI-instrumentation seam.** A single verb the main loop can call — cut, watch,
  verify — is worth more than a wiki page of manual `docker build` steps. The whole cut must never
  print a secret value.

This is architecturally significant: it fixes the public artifact namespace, the cluster tenancy,
the secret plane on the deploy path, and the promotion mechanism — all costly to reverse and all
constraining every future Eden deploy. Hence a ruling, not an autonomous edit.

## Decision

### 1. The channel is TAG-DRIVEN — one verb, a `v<semver>` tag is the stable signal

A stable release is cut by ONE verb, `bash deploy/ctl.sh release v<semver>`, which validates the
version shape, a clean tree, an up-to-date branch, and a committed harness pin (the agent-runtime
build sources `CLAUDE_CODE_VERSION` from `harnesses/versions.env`, ADR-0021), then creates and
pushes an **annotated** `v<semver>` tag. The tag push — and only the tag push — triggers the release
pipeline. `v*` is the natural stable signal; `workflow_dispatch` is the escape hatch (it pins a
`<short-sha>-dispatch` ref). The verb NEVER prints a credential. This is the single instrumentation
seam: cut with `release`, watch with `release-status`.

### 2. Artifacts live under ONE prefix: `ghcr.io/gophersys/eden/*`

The four images publish to `ghcr.io/gophersys/eden/{agentgateway,agent-runtime,platformgateway,frontend}`,
each tagged `{v<semver>, latest, sha-<short>}`. One owner prefix, one registry, versioned together
off the one tag. agentgateway is built once and runs as BOTH agentgateway and the orchestrator (a
command override), so it is pinned into both Deployments from its single digest.

### 3. ONE namespace on the home cluster: `eden`

All Eden workloads and their backing stack run in a single kubernetes namespace, `eden`, on the home
cluster, served at `https://eden.mateosegura.com` (tailnet, `letsencrypt-homelab` TLS). The backing
stack (Postgres · NATS · file-storage Vault + the seed Job + the bootstrap `ExternalSecret` + RBAC +
ingress) lives in `infrastructure/apps/eden/`; the workload Deployments arrive by promotion (§6).
The Argo `Application eden` sits in the reserved `apps` AppProject (the own-codebase project);
the cluster-scoped `Namespace` is owned by the `platform` project.

### 4. The app-secret plane is VAULT-NATIVE with token-file mode — no injector

Every Eden secret on the cluster is a `vault://eden/production#<field>` reference resolved by the
app's own dual-mode Vault provider (ADR-0022), NOT a k8s Secret and NOT a Vault-injector sidecar.
Pods run `EDEN_VAULT_MODE=token-file` against `VAULT_ADDR=http://vault:8200`, reading a token file
mounted from the k8s Secret `eden-vault-token` (key `token`) at `/vault/secrets/token`. That token
Secret is minted out-of-band by the seed Job (the Vault ceremony); the render names it, never a
value (`deploy/servicespec/catalog.go` `edenVaultTokenSecret()` is the ONE home). JWT signing keys,
harness credentials, and the platformgateway DSN are Vault fields — they are **never** folded into
k8s Secrets. The lone plain k8s Secret in the plane is the Postgres password (`DATABASE_URL`); the
frontend, a static SPA, carries no Vault plane at all.

### 5. The frontend is served STATIC by nginx, same-origin with the platform API

The frontend image is a static SvelteKit build (adapter-static) served by nginx, which also
reverse-proxies the platform API path so the browser talks to ONE origin (no CORS, one public
hostname). The build consumes the PREBUILT `@eden/*` library `dist/` — the Svelte toolchain resolves
only through the yarn-4/bun workspace install, so the libraries are built in the base devcontainer
image (the ADR-0022 substrate that carries the toolchain) BEFORE the image build, not inside the
lean serving stage. The `eden` ingress routes all paths to `frontend:8080`.

### 6. Promotion is a DIGEST-PINNED GitOps PR — Argo reconciles, nothing is `kubectl apply`ed

After the four images push, the pipeline opens a PR against `gophersys/infrastructure` that rewrites
the `apps/eden/*` Deployment `image:` lines to the freshly-built **digests** (`@sha256:…`, never
`:latest` — the deploy contract is that Argo reconciles the exact image the release built). On merge,
Argo CD (`selfHeal + prune + ServerSideApply`) reconciles `apps/eden/` onto the home cluster. The
release path touches the cluster only through git.

## Consequences

- Cutting a stable Eden release is ONE verb; the four images version together off one tag; the whole
  cut is a machine-drivable, secret-safe seam (the AI-instrumentation goal).
- The public artifact namespace `ghcr.io/gophersys/eden/*` and the `eden` namespace are now fixed
  contracts: the render drift test expects the prefix, the infra half names the namespace, and the
  promotion script keys on the prefix stem — all three would have to change together to move either.
- The deploy path inherits the SAME Vault-native secret plane as the demo — no k8s-Secret fork, the
  canary redaction property holds, and a re-run of the seed Job never rotates the JWT keys (sessions
  survive). The cost is a real one-time operator Vault ceremony (init/unseal + the imperative
  Secrets), which GitOps cannot do and which the `infrastructure/apps/eden/` runbook owns.
- The frontend gains a same-origin API path (no CORS) at the cost of a two-stage build (libs
  prebuilt in the devcontainer substrate, then the static+nginx image) — the same substrate the CI
  gates already depend on.
- Promotion is auditable and revertible (a git PR of digest pins); a bad release is rolled back by
  reverting the pin PR, not by racing `kubectl`.
- **Alternatives rejected:** (a) a Vault-injector sidecar — rejected for the token-file mode, which
  needs no admission webhook and reuses the app's own dual-mode provider; (b) folding secrets to k8s
  Secrets on the deploy path — rejected: it forks the secret plane and breaks redaction; (c) serving
  the frontend from a Node adapter — rejected: the SPA has no server needs and a static+nginx image
  is smaller, cacheable, and gives same-origin proxying for free; (d) a `:latest`-tag deploy —
  rejected: digest pinning is the only way Argo reconciles the exact built image; (e) pushing images
  and `kubectl apply`-ing manifests — rejected: it violates the GitOps + no-hand-created-Secrets rule.

This ADR builds on ADR-0022 (the Milestone-B render catalog + the dual-mode Vault provider it
consumes) and follows the `.devcontainer` multi-arch buildx + GHCR precedent; the operational flow
(job-by-job, the promotion path, the backing-stack prerequisites, the six pipeline lessons, and the
demo-vs-release distinction) is specified in the canonical spec
[18 — release and home deploy](../18-release-and-home-deploy.md), and the home-cluster backing stack
+ the out-of-band ceremony live in `infrastructure/apps/eden/README.md`.

## Implementation status

- **BUILT + PROVEN.** `deploy/ctl.sh` carries the `release` + `release-status` verbs; the pipeline is
  authored byte-identically in `.github/workflows/release.yml` and `.ci/providers/github/release.yml`
  (the provider-pair convention); `.ci/release-meta.sh` and `.ci/pin-eden-digests.sh` are the ONE
  homes for version/digest derivation and the infra rewrite; `infrastructure/apps/eden/` carries the
  backing stack + the runbook. `v0.1.0`→`v0.1.4` were cut: the four images are pushed to
  `ghcr.io/gophersys/eden/*` and the workloads are seeded into `apps/eden/` digest-pinned.
- **Pending:** the home-cluster pods await the operator's out-of-band checklist (the four imperative
  secrets + the Vault init/unseal ceremony — `infrastructure/apps/eden/README.md`), after which the
  ingress serves `https://eden.mateosegura.com`. Multi-arch on agent-runtime returns when the private
  base package goes public or grants this repo read access (today it builds amd64-only, which the
  amd64 home cluster loses nothing by).
