-- 0004_create_connectors — the user/org connector store (goose-style up/down). It APPLIES the
-- connectors tables to a real database; the embedded startup migrate runner (persistence/migrate.go)
-- runs the +goose Up section on every boot (idempotent, CREATE ... IF NOT EXISTS), and the
-- integration lane runs the SAME section against a real postgres. schema/schema.sql is the SAME
-- shape sqlc type-checks against — keep them in lockstep.
--
-- A connector is a user's third-party credential (a Claude API token, a GitHub token, an OpenRouter
-- key) that an agent session resolves and uses (ADR-0029, doc 19). The value is NEVER stored here in
-- plaintext: the `connectors` row holds only the loggable metadata (kind, name, scope, account_hint,
-- fingerprint), and the sealed material lives in a SEPARATE `connector_secrets` table so a list query
-- never even SELECTs ciphertext. The sealed columns are the libs/go/envelope Sealed record
-- (ciphertext, wrapped_dek, two nonces, kek_version) — see docs/architecture/contracts/envelope.md.
-- A connector is ORG-scoped by default (user_id NULL); a per-user connector sets user_id (ADR-0029 §5).

-- +goose Up
CREATE TABLE IF NOT EXISTS connectors (
    -- id is the server-minted primary key (uuid). The create route generates it (the database does
    -- not default it), so an insert is explicit and reproducible.
    id              uuid        PRIMARY KEY,
    -- organization_id scopes the connector to its owning organization — the tenancy key every query
    -- filters on (WHERE organization_id = $callerOrg), the cross-tenant isolation invariant (ADR-0029 §2.3).
    organization_id uuid        NOT NULL REFERENCES organizations (id),
    -- user_id is the owning user for a USER-scoped connector; NULL means ORG-scoped (shared across the
    -- org). ORG scope is the default (ADR-0029 §5).
    user_id         uuid        REFERENCES users (id),
    -- kind is the closed v1 connector kind: 'claude-api' | 'github' | 'openrouter' (honest chrome —
    -- only a kind whose connect path works ships). The route's validate stage rejects anything off-list.
    kind            text        NOT NULL,
    -- name is the connector's human label (shown in the Connectors settings row).
    name            text        NOT NULL,
    -- account_hint is a NON-secret display crumb (e.g. an account handle or masked email) the write-only
    -- UI shows alongside the fingerprint. It is never the credential value. Defaults to the empty string.
    account_hint    text        NOT NULL DEFAULT '',
    -- fingerprint is a one-way truncated SHA-256 of the credential (envelope.Fingerprint) — safe to
    -- store and show, used only for the UI's write-only display and change-detection. Never the value.
    fingerprint     text        NOT NULL,
    -- created_by is the user who created the connector (the audit actor). Distinct from user_id (a
    -- user-scoped connector's owner) so an admin can create an org connector on behalf of the org.
    created_by      uuid        NOT NULL REFERENCES users (id),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    -- A connector is single-valued per (org, kind, name): the natural key a re-create conflicts on,
    -- rendered as KindConflict → 409 at the boundary.
    UNIQUE (organization_id, kind, name)
);

CREATE TABLE IF NOT EXISTS connector_secrets (
    -- connector_id is the 1:1 owning connector (PRIMARY KEY = one sealed record per connector). ON
    -- DELETE CASCADE so revoking a connector purges its sealed material atomically.
    connector_id     uuid    PRIMARY KEY REFERENCES connectors (id) ON DELETE CASCADE,
    -- ciphertext is AES-256-GCM(DEK, credential) — the sealed credential (envelope.Sealed.Ciphertext).
    ciphertext       bytea   NOT NULL,
    -- wrapped_dek is AES-256-GCM(KEK, DEK) — the data key sealed under the platform-Vault KEK.
    wrapped_dek      bytea   NOT NULL,
    -- nonce_ciphertext / nonce_dek are the two 12-byte GCM nonces (one per AEAD layer).
    nonce_ciphertext bytea   NOT NULL,
    nonce_dek        bytea   NOT NULL,
    -- kek_version is the KEK generation that wrapped the DEK — makes two KEK generations coexist during
    -- a caller-driven re-wrap rotation pass (ADR-0029 §rotation).
    kek_version      integer NOT NULL
);

-- +goose Down
DROP TABLE connector_secrets;
DROP TABLE connectors;
