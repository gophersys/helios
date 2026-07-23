# 19 — Connectors and user secret material (the per-user credential manager)

> Status: Accepted · 2026-07-20 · Canonical home for: the `connectors` domain in `platformgateway`
> (how a user's third-party credential is uploaded, stored envelope-encrypted, scoped to an org/user,
> and consumed by an agent) and the `envelope`-encryption crypto model. The RULING (why
> envelope-in-Postgres over Vaultwarden-per-tenant, why the KEK lives in the platform Vault, why
> `envelope` is a new leaf lib, why `eden://connector/<id>` and not a `vault://` overload, the closed
> v1 kind enum, org-default scope, and the ADR-0022 §1 supersession) is
> [ADR-0029](adr/0029-user-connectors-and-secret-material.md) — this doc cites it, never re-decides
> it. The crypto surface is the frozen contract [`contracts/envelope.md`](contracts/envelope.md); the
> redaction/injection seam it plugs into is [`contracts/secrets.md`](contracts/secrets.md) and the
> 5-files-per-route discipline is [ADR-0023](adr/0023-application-template-system.md). One concept,
> one home (10 §9): every type below is defined in its cited home and referenced here.

## 1. The picture ✅

A user uploads a credential (a Claude API token, a GitHub token, an OpenRouter key). It crosses the
`POST /v1/connectors` seam **exactly once**, is sealed with envelope encryption, and is stored in
Postgres — never in plaintext, never in git. From then on the value is unreadable to any human: the
`Response` and every read return only `{id, kind, name, scope, state, accountHint, fingerprint}`. The
only reader of the plaintext is an agent session, which resolves it through the existing
redaction/injection seam and places it on the child process inside a `Secret.Use` window that
zeroizes on close.

```
user ──POST /v1/connectors {kind,name,value,scope}──▶ platformgateway
        (value crosses ONCE)                            │
                                                        ▼  envelope.Seal
                              connectors(row: id,org,user?,kind,name,account_hint,fingerprint)
                              connector_secrets(row: ciphertext,wrapped_dek,nonce*,kek_version)
                                                        │
  agent session ──Spec.Credential = eden://connector/<id>──▶ secrets.Mediator
        │                                                        │  (route by "eden" scheme)
        ▼  Secret.Use → zeroize                        platformconnectoradapter
   child process                                        └─ authorize org → load row → envelope.Unseal → *secrets.Secret
```

## 2. The crypto model — envelope encryption ✅

Defined once in [`contracts/envelope.md`](contracts/envelope.md); summarized here for the reader.

- **KEK** (key-encryption-key): one AES-256 key in the **platform Vault** (Plane 2), resolved through
  the frozen `secrets.Provider.Resolve` seam via `vault://eden/production#connectors-kek`. `envelope`
  never holds it — it reads it inside a `Secret.Use` window per operation and zeroizes.
- **DEK** (data-encryption-key): a fresh random 256-bit key minted **per stored secret** at write time.
- **Seal:** `ciphertext = AES-256-GCM(DEK, plaintext)`; `wrapped_dek = AES-256-GCM(KEK, DEK)` — random
  nonce each. The row stores `{ciphertext, wrapped_dek, nonce_ct, nonce_dek, fingerprint, kek_version}`.
- **Unseal:** `DEK = AES-256-GCM_open(KEK, wrapped_dek)`; `plaintext = AES-256-GCM_open(DEK, ciphertext)`
  — revealed only inside a `Use` callback, then gone.
- **Fingerprint:** a truncated one-way SHA-256 of the plaintext, stored plainly, used only for the
  write-only UI's change-detection (the same class as a password hash — reveals nothing but equality).

**Rotation** (ADR-0029 §rotation): a KEK rotation is a caller-driven re-wrap pass — `Unseal` the DEK
under KEK-v1, `Seal` it under KEK-v2; the `kek_version` column makes the two generations coexist
during the roll. A credential replace (`PUT`) re-seals a fresh plaintext under a new DEK. A `DELETE`
revokes immediately.

## 3. The `connectors` domain — routes & storage ✅

Home: `apps/platformgateway/internal/api/v1/connectors/`. The first authenticated write in the
gateway; each route is the 5-files-per-route rule ([ADR-0023](adr/0023-application-template-system.md),
`internal/api/v1/ping/` is the reference).

### 3.1 Route table

| Method / Path | operationId | Required grant | Success | Notes |
|---|---|---|---|---|
| `POST /v1/connectors` | `createConnector` | `connectors:write` | 201 | The credential crosses here ONCE. |
| `GET /v1/connectors` | `listConnectors` | `connectors:read` | 200 | Caller's org only; never the value. |
| `GET /v1/connectors/{id}` | `getConnector` | `connectors:read` | 200 | Single; never the value. |
| `PUT /v1/connectors/{id}` | `replaceConnectorCredential` | `connectors:write` | 200 | Re-seal a new plaintext (rotation/replace). |
| `DELETE /v1/connectors/{id}` | `deleteConnector` | `connectors:write` | 200 | Revoke; `{id}` acknowledgement in the uniform Envelope. |

`connectors:read`/`connectors:write` enter `permission_sets.permissions[]`; the Admin `{*}` set
already covers them (the authorize spine makes a new grant effective on the caller's next request, no
JWT re-issue).

### 3.2 Wire shapes (the Go route types are the source of truth — go-first-emit)

`ConnectorView { id, kind, name, scope, state, accountHint, fingerprint }` — **no `value` field,
ever**. `POST` request `{ kind, name, value, scope }` (value = the plaintext, crosses once); `PUT`
request `{ value }`. `kind` is the closed v1 enum `claude-api | github | openrouter` (anything
off-list → `KindInvalid` → 400). `scope` is `{ level: "org"|"user", targetId? }` — `user_id` NULL ⇒
org-scoped (ADR-0029 §5).

### 3.3 Tenant scoping (enforced in `execute`, never free)

`execute.go` loads the caller's `organization_id` via the existing `persistence.RBAC.MembershipFor`
port (keyed on the JWT subject) and filters **every** query `WHERE organization_id = $callerOrg`.
Cross-org isolation is this invariant, proven by the RBAC-scoping integration test on real Postgres: a
caller in org A cannot read/list/update/delete a connector owned by org B (404, never a leak). A
`UNIQUE (organization_id, kind, name)` collision is `KindConflict` → 409.

### 3.4 Storage (DDL) ✅

```sql
CREATE TABLE IF NOT EXISTS connectors (
    id uuid PRIMARY KEY,
    organization_id uuid NOT NULL REFERENCES organizations(id),
    user_id uuid REFERENCES users(id),                    -- NULL => org-scoped
    kind text NOT NULL, name text NOT NULL,
    account_hint text NOT NULL DEFAULT '', fingerprint text NOT NULL,
    created_by uuid NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (organization_id, kind, name));
CREATE TABLE IF NOT EXISTS connector_secrets (
    connector_id uuid PRIMARY KEY REFERENCES connectors(id) ON DELETE CASCADE,
    ciphertext bytea NOT NULL, wrapped_dek bytea NOT NULL,
    nonce_ciphertext bytea NOT NULL, nonce_dek bytea NOT NULL, kek_version int NOT NULL);
```

The sealed material lives in its own table so a list query never even SELECTs ciphertext.

### 3.5 Audit is value-free ✅

Every connector mutation emits an `observability.Event` (the route's `effect.go` after-respond stage)
carrying **only** `{connector id, kind, org, actor user id, verb}` — never the value, never the
fingerprint's preimage. The `secrets.Secret` redaction contract + the `envelope` SeededCanary test
guarantee the value cannot ride an Event/log/error by construction.

## 4. The resolution seam — `eden://connector/<id>` ✅

Agents consume a connector through a new `eden://connector/<id>` scheme resolved by a new adapter
(`platformconnectoradapter`) behind the **existing** `secrets.Mediator` — the frozen `secrets` API is
untouched (ADR-0029 §4). The adapter implements the frozen `secrets.Provider` (`Resolve` only), is
bound under the `"eden"` scheme in the orchestrator's composition root next to `"vault"`, and on
`eden://connector/<id>` authorizes the caller's org, loads the row, unseals via `envelope`, and mints
a genuine un-printable `*secrets.Secret`. The orchestrator derives the per-session reference from the
project's owning org/user (project → owner → `eden://connector/<id>`), with the
`EDEN_CREDENTIAL_REF` manifest constant as the graceful fallback when an org has no uploaded
connector. *This adapter + derivation is the ADR-0029 §4 follow-on (Brief A3); the first backend cut
lands the domain + the KEK seed + the `envelope` lib.*

## 5. Template bake-in ✅

Because slices are instance-owned / copy-once ([ADR-0026](adr/0026-templates-in-libs-and-monorepo-maintenance.md)),
every future app gets the connectors backend by adding the slice to the template
(`libs/templates/go/http-gateway/`) so it is present at generation time, shaped like the existing
`resource` reference slice; the secret-material discipline (sealed reference resolved through the
injected sealer inside a `Use` window — never inlined in the row/Response/log/error) is baked into the
template's `.claude/rules`. `platformgateway` — the first adopter and the dogfood proof — gets the
slice by the explicit build (this doc's domain), not by silent sync. The KEK is an app concern: the
template ships the *pattern* (envelope-seal via `envelope`, KEK from a `vault://` reference); each app
names its own KEK reference and provisions it via its own seed.

## 6. What is NOT ruled here

The Connectors settings UI (the write-only field, the provider rows, the honest state pills) is the
frontend brief; it consumes this doc's `ConnectorView` wire shape and the `connectProvider` seam
(credential crosses once). It is governed by [doc 17](17-design-language.md) (the design language) and
built app-local under `apps/frontend/src/lib/settings/connectors/` — not part of this backend spec.
