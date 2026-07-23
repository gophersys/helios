# ADR-0029: User connectors and secret material — envelope-in-Postgres, `eden://connector/<id>` resolution

- **Status:** Accepted
- **Date:** 2026-07-20
- **Deciders:** Mateo (ratified the five default-calls 2026-07-19, grounded in the synthesis design
  `docs/architecture/19-connectors-and-user-secrets.md`)

## Context

Eden agents run on third-party credentials: a Claude API token, a GitHub token, an OpenRouter key.
Today those arrive from ONE process-wide bootstrap reference (`EDEN_CREDENTIAL_REF=vault://eden/production#setup-token`,
folded unchanged into every agent Spec by the orchestrator). There is no per-user, per-org place a
person can upload *their own* credential and have their projects' agents use it. Adding one is
architecturally significant: it decides where retrievable user secrets live at rest, how they are
encrypted, and how an agent session resolves one — each of which shapes a frozen library seam and is
costly to reverse.

The ground truth (verified against source, 19 §0): the redaction/injection plane
(`agentsession.Spec.Credential` → `Pool.injectCredential` → `secrets.Provider.Resolve` → `Secret.Use`
→ zeroize) is production-ready and already per-Spec parameterizable — it needs **zero change**. The
`secrets.Provider` port is **`Resolve`-only** (no `Write`/`Put` anywhere); `vaultadapter` renders only
the KV-v2 *read* endpoint. **No AEAD/crypto helper exists** in `libs/go` (the only at-rest precedent
is bcrypt, one-way — unusable for a retrievable token). The per-org Vault namespacing + per-session
ephemeral role of 07 §6 / ADR-0022 §1 were *designed, never built*: one path, one read-only policy,
one shared token exist today.

## Decision

### 1. User secrets live in a `platformgateway` `connectors` domain, envelope-encrypted in Postgres

A new `connectors` domain in `apps/platformgateway` (Eden's multi-tenant platform API — it already
carries the org/permission-set/member RBAC spine, the DB-driven per-request authorize, sqlc/pgx, and
the OpenAPI go-first-emit discipline) owns a `connectors` table + a `connector_secrets` table. The
credential **value is never stored in Postgres in plaintext and never in git**. Storage is
**envelope encryption**: a fresh per-secret data key (DEK) seals the plaintext, an external
key-encryption key (KEK) wraps the DEK, both AES-256-GCM; the row stores
`{ciphertext, wrapped_dek, nonce_ct, nonce_dek, fingerprint, kek_version}` — never the DEK, never the
plaintext, never the KEK.

**Chosen over Vaultwarden-per-tenant** because: (1) the frozen `secrets.Provider` is `Resolve`-only —
a per-tenant *write* into Vault/Vaultwarden breaks a foundation lib's `.apibaseline` (the cardinal
sin, ADR-0020) and needs the per-tenant Vault policy/token minting nobody has built; (2) cloud
Vaultwarden is CLAUDE.md's operator/GitOps bootstrap plane (Plane 1) — human-written, org-wide, no
tenancy, the wrong plane for thousands of per-user rows; (3) envelope-in-Postgres reuses the existing
tenancy-keyed data layer (every row carries `organization_id`), so cross-tenant isolation is a
`WHERE organization_id = $caller` invariant we already test on real Postgres; (4) it ships NOW without
touching a frozen API; (5) it keeps one home for secret *material* — the platform Vault holds the KEK,
the DEKs are ephemeral.

### 2. The KEK lives in the platform Vault (Plane 2), resolved via the frozen `vault://` seam — locked default

The KEK is a single AES-256 key in the **in-cluster platform Vault** (Plane 2), resolved through the
existing frozen `secrets.Provider.Resolve` seam at gateway boot via `vault://eden/production#connectors-kek`
— **no library change, no write path into the frozen port**. The seed Job (`infrastructure/apps/eden/08-vault-seed-job.yaml`)
mints it **only-if-absent** (`sys/tools/random`, exactly like the JWT signing keys it already mints).
(Mateo's fork, 2026-07-19: Plane 2, not a Vaultwarden-origin KEK — Plane 2 is the runtime plane and
needs no new ESO wiring.)

### 3. Envelope encryption is a NEW leaf library `libs/go/envelope` — locked default

There is no AEAD helper anywhere in `libs/go`, so the crypto is built as a new full-pipeline leaf
library `libs/go/envelope` (contract `docs/architecture/contracts/envelope.md`; ADR-0020 four-phase
gate green; conformance + SeededCanary + mutation >=75; HNS-1 naming — NOT `crypto`/`util`/`seal`,
name the concept). `platformgateway` consumes it; the gateway owns only the 5-file routes.
(Mateo's fork, 2026-07-19: a shared leaf lib, not an app-internal package — the crypto deserves the
single audited home + the mutation/canary gates.)

### 4. Agents CONSUME connectors through a NEW `eden://connector/<id>` scheme — the frozen `secrets` API is untouched

Resolution is a new adapter (`platformconnectoradapter`) that implements the *frozen* `secrets.Provider`
interface (one method, `Resolve`) and is bound under the `"eden"` scheme in the orchestrator's
composition root alongside the existing `"vault"` binding (`secrets.Deps.Resolvers` is a
`map[string]Provider` — adding a key is the sanctioned extension). On `eden://connector/<id>` it
authorizes the caller's org owns the connector, loads the row, unseals via `envelope`, and mints a
genuine un-printable `*secrets.Secret`. **Neither the `secrets` port nor `vaultadapter`'s
`.apibaseline` changes** — this is the load-bearing win. `vault://` is not overloaded (it maps 1:1 to
a KV-v2 read; a user connector is an envelope-sealed Postgres row with an org authorization check — a
distinct concept, a distinct scheme). *This adapter + the project→owner→`eden://connector/<id>`
derivation is specified here and built as a follow-on (Brief A3); it is not part of the first backend
cut, which lands the domain + the KEK + the `envelope` lib.*

### 5. v1 connector kinds, default scope — locked defaults

- **v1 kinds are a closed enum: `claude-api`, `github`, `openrouter` ONLY** (honest chrome — only a
  kind whose connect path works ships; mirrors the three ESO bootstrap items). Anything off-list is a
  `KindInvalid` → 400. (Mateo's fork, 2026-07-19: defer cloud-provider kinds until an agent consumes them.)
- **A connector is ORG-scoped by default; user-scope is supported** (`user_id` nullable — NULL ⇒
  org-scoped). (Mateo's fork, 2026-07-19.)

### 6. The ADR-0022 §1 ephemeral-per-session Vault role is SUPERSEDED for user connectors

ADR-0022 §1 designed a per-agent-session ephemeral Vault role + least-privilege policy. For the
**user-connector** use-case this ruling supersedes it: envelope-in-Postgres with a `WHERE
organization_id = $caller` tenancy invariant provides the isolation without minting per-session Vault
roles nobody built. The ephemeral-role design is **retained as future work for platform-plane
secrets** (a different class — the agent's own infrastructure credentials, not a user's uploaded
token); it is not a live requirement for user connectors. (Mateo's fork, 2026-07-19.)

## Consequences

**Easier:** a user uploads their own Claude/GitHub/OpenRouter credential and their org's projects use
it; the write-once/fingerprint-only discipline is mechanically provable (a no-plaintext-at-rest scan
test); cross-tenant isolation is the same `WHERE organization_id` invariant the rest of the platform
already tests on real Postgres; the crypto has a single audited home with mutation + canary gates.

**Harder / newly invalid:** a plaintext credential can never be read back (there is NO read route for
the value — the only reader is the agent-side resolution seam); the row's `Response` and every read
carry only `{id, kind, name, scope, state, accountHint, fingerprint}`; a KEK rotation is a
caller-driven re-wrap pass (the `kek_version` column makes two generations coexist), gated behind the
infra `secrets-rotate` approval flow.

**Must propagate:** the `connectors:read`/`connectors:write` grants enter `permission_sets.permissions[]`
(the Admin `{*}` set already covers them; a new grant is effective on the caller's next request, no JWT
re-issue). The template bakes the `connectors` slice + the secret-material `.claude` discipline so
every future generated app ships the pattern (19 §4).

**Alternatives rejected:** *Vaultwarden-per-tenant* — breaks the frozen `secrets` `.apibaseline` and
needs unbuilt per-tenant Vault minting (§1). *Extending `vault://` to sometimes mean a Postgres row* —
breaks one-concept-one-home and forces `vaultadapter` to grow a Postgres dependency (§4). *An
app-internal `sealed` package instead of a lib* — the crypto deserves the mutation/canary gates a
full-pipeline leaf gets (§3). *Cipher-by-configuration* — one AEAD, one home; AES-256-GCM is
hard-wired (contract §1).
