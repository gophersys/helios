package main

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"

	"github.com/gophersys/eden/apps/agentgateway/internal/connectorcredential"
)

// vaultTokenFilePath is the default sidecar token-file path when EDEN_VAULT_TOKEN_FILE is unset on
// the production path (matches the agent-runtime / orchestrator deployment's EDEN_VAULT_TOKEN_FILE).
const vaultTokenFilePath = "/vault/secrets/token" // #nosec G101 -- a sidecar output PATH, not a credential value.

// defaultHarness is the propose turn's harness when EDEN_HARNESS is unset (the account default is
// claude-code — the standing Opus directive routes it to the Opus model).
const defaultHarness = "claude-code"

// defaultWorkspace is the propose harness CWD when EDEN_WORKSPACE is unset. In a pod this is a
// writable ephemeral path (the container's own filesystem); the propose turn reads/reasons only.
const defaultWorkspace = "/tmp/eden-gateway-workspace" // #nosec G101 -- a directory path, not a credential.

// defaultConnectorsKEKRef is the platform-Vault reference the envelope KEK resolves from when
// EDEN_GATEWAY_CONNECTORS_KEK_REF is unset — the SAME only-if-absent-minted reference the
// platformgateway connectors domain seals under (ADR-0029 §2). Meaningful only when the connectors DSN
// reference is set (else no "eden" scheme is bound).
const defaultConnectorsKEKRef = "vault://eden/production#connectors-kek" // #nosec G101 -- an opaque vault REFERENCE (path), not a credential value.

// configuration is the fully-resolved composition input read ONCE from the environment (the
// configuration pattern). It holds NO secret VALUE — the JWT signing key is an opaque, loggable
// vault:// Reference (JWTSecretReference) resolved through the secrets provider at build. run()
// builds the live ports from it; parseConfiguration is the pure env→configuration seam the unit
// test drives.
type configuration struct {
	// Address is the HTTP bind address (EDEN_GATEWAY_ADDRESS or :8080).
	Address string
	// EventsStream is the JetStream events stream the SSE bridge replays (EDEN_GATEWAY_EVENTS_STREAM).
	EventsStream string
	// NATSURL is the bus the gateway dials (EDEN_NATS_URL); empty folds to the SDK default at dial.
	NATSURL string

	// JWTSecretReference is the opaque vault:// reference the dev-JWT HMAC signing key resolves from
	// (EDEN_GATEWAY_JWT_SECRET_REF). Required — the gateway is behind auth even locally (ADR-0022 #3).
	// An opaque path, safe to log; the VALUE it resolves to is used point-of-use and zeroized.
	JWTSecretReference string

	// ── The FULL production surface (prodserve): the REST/record plane the SvelteKit UI consumes
	// (propose · projects · insight · agent-configs · sessions list/get). Each field is OPTIONAL —
	// when the whole set is absent the gateway serves the NATS→SSE bridge ALONE (the pre-v0.1.7
	// behavior), so a partial rollout never breaks. FullSurfaceConfigured() gates the wiring on the
	// two load-bearing seams (the DSN reference + the workspace); the rest carry sane defaults. ──

	// DatabaseDSNReference is the opaque vault:// reference the record + dashboard Postgres DSN
	// resolves from (EDEN_GATEWAY_DATABASE_DSN_REF, e.g. vault://eden/production#database-dsn). The
	// VALUE is resolved point-of-use at boot and never logged. Empty == the full surface is OFF (the
	// gateway serves only the stateless bridge).
	DatabaseDSNReference string
	// CredentialReference is the opaque vault:// reference the propose harness turn's credential
	// resolves from (EDEN_CREDENTIAL_REF). Empty == the propose route degrades to a classified 503.
	CredentialReference string
	// Harness / Model are the propose turn's adapter key + model (EDEN_HARNESS / EDEN_MODEL). Harness
	// defaults to claude-code; Model empty folds to the account default.
	Harness string
	Model   string
	// Workspace is the propose harness turn's CWD (EDEN_WORKSPACE, default defaultWorkspace). Required
	// when the full surface is wired (the harness subprocess needs a real, writable directory).
	Workspace string

	// VaultMode / VaultAddress / VaultTokenFilePath / VaultUsername / VaultPassword are the dual-mode
	// Vault bootstrap the secrets provider is built over (EDEN_VAULT_MODE selects the production
	// token-file path — the K8s-SA sidecar output — vs the local userpass path). The password is read
	// but NEVER logged; it lives only in this struct and the adapter login body.
	VaultMode          vaultadapter.Mode
	VaultAddress       string
	VaultTokenFilePath string
	VaultUsername      string
	VaultPassword      string

	// ── The connector-credential seam (OPTIONAL, ADR-0029 §4 / A3): when the connectors DSN reference
	// is set, the gateway binds the "eden" scheme so a session can CONSUME a user-uploaded connector
	// (eden://connector/<id>). When empty the "eden" scheme is not bound and every session gets the
	// platform EDEN_CREDENTIAL_REF exactly as today — the fallback is never regressed. ──

	// ConnectorsDatabaseDSNReference is the opaque vault:// reference the platformgateway connectors
	// database DSN resolves from (EDEN_GATEWAY_CONNECTORS_DSN_REF). Empty ⇒ no connector resolution.
	ConnectorsDatabaseDSNReference string
	// ConnectorsKEKReference is the opaque vault:// reference the envelope KEK resolves from
	// (EDEN_GATEWAY_CONNECTORS_KEK_REF, default vault://eden/production#connectors-kek — the SAME
	// reference the platformgateway connectors domain seals under). Meaningful only when the connectors
	// DSN reference is set.
	ConnectorsKEKReference string
}

// parseConfiguration resolves the composition configuration from env ONCE (the configuration
// pattern), validating the fields the composition genuinely requires and returning a wrapped
// KindInvalid error naming the missing field (never echoing a value). It is the PURE env→config
// seam the unit test drives via a table over the environment map; run() calls it at the edge and
// builds the live ports from the result. It mirrors cmd/agentgateway-orchestrator's
// parseConfiguration shape (env names + per-mode validation).
//
// getenv is injected so the test drives it deterministically without mutating the process
// environment; run() passes os.Getenv.
func parseConfiguration(getenv func(string) string) (configuration, error) {
	configured := configuration{
		Address:            envOr(getenv, "EDEN_GATEWAY_ADDRESS", defaultAddress),
		EventsStream:       getenv("EDEN_GATEWAY_EVENTS_STREAM"),
		NATSURL:            getenv("EDEN_NATS_URL"),
		JWTSecretReference: getenv("EDEN_GATEWAY_JWT_SECRET_REF"),
		VaultMode:          vaultadapter.ParseMode(getenv("EDEN_VAULT_MODE")),
		VaultAddress:       getenv("VAULT_ADDR"),
		VaultTokenFilePath: envOr(getenv, "EDEN_VAULT_TOKEN_FILE", vaultTokenFilePath),
		VaultUsername:      getenv("VAULT_USERNAME"),
		VaultPassword:      getenv("VAULT_PASSWORD"),

		DatabaseDSNReference: getenv("EDEN_GATEWAY_DATABASE_DSN_REF"),
		CredentialReference:  getenv("EDEN_CREDENTIAL_REF"),
		Harness:              envOr(getenv, "EDEN_HARNESS", defaultHarness),
		Model:                getenv("EDEN_MODEL"),
		Workspace:            envOr(getenv, "EDEN_WORKSPACE", defaultWorkspace),

		ConnectorsDatabaseDSNReference: getenv("EDEN_GATEWAY_CONNECTORS_DSN_REF"),
		ConnectorsKEKReference:         envOr(getenv, "EDEN_GATEWAY_CONNECTORS_KEK_REF", defaultConnectorsKEKRef),
	}

	if err := configured.validate(); err != nil {
		return configuration{}, err
	}
	return configured, nil
}

// validate checks the fields the composition genuinely requires, returning a wrapped KindInvalid
// error naming the missing seam (never echoing a value). The Vault credential is validated per the
// resolved Mode — the local userpass path needs the username/password (the production token-file
// path needs only the token-file path, which parseConfiguration always defaults) — mirroring
// vaultadapter.New's own per-Mode contract, failing at the edge instead of at first Resolve.
func (c *configuration) validate() error {
	if c.JWTSecretReference == "" {
		return errors.New(errors.KindInvalid,
			"agentgateway: EDEN_GATEWAY_JWT_SECRET_REF is required (the opaque vault:// dev-JWT signing-key reference — the gateway is behind auth even locally)")
	}
	if c.VaultAddress == "" {
		return errors.New(errors.KindInvalid, "agentgateway: VAULT_ADDR is required (the secrets provider backend)")
	}
	if c.VaultMode == vaultadapter.ModeUserpass {
		switch {
		case c.VaultUsername == "":
			return errors.New(errors.KindInvalid, "agentgateway: VAULT_USERNAME is required in the local userpass Vault mode")
		case c.VaultPassword == "":
			return errors.New(errors.KindInvalid, "agentgateway: VAULT_PASSWORD is required in the local userpass Vault mode (the bootstrap credential)")
		}
	}
	return nil
}

// FullSurfaceConfigured reports whether the command wires the FULL production surface (prodserve: the
// REST/record plane) IN ADDITION to the stateless NATS→SSE bridge. The load-bearing seam is the
// Postgres DSN reference — the record plane + every dashboard/Settings store is durable, so no DSN
// means no full surface. When false the command serves the bridge ALONE (the pre-v0.1.7 behavior), so
// a partial rollout (the manifest without the new env) degrades honestly rather than failing to boot.
func (c *configuration) FullSurfaceConfigured() bool {
	return c.DatabaseDSNReference != ""
}

// buildSecretsProvider builds the secrets Mediator over the dual-mode Vault backend: the PRODUCTION
// token-file path (ModeTokenFile — the K8s-SA sidecar output at VaultTokenFilePath, re-read per
// Resolve) on the cluster, or the LOCAL userpass bootstrap for a local run. It mirrors
// liveserve.buildSecretsProvider / agentgateway-orchestrator.buildSecretsProvider's mediator wiring
// (one scheme, "vault"); the ONLY difference is the per-Mode backend Config/Deps, resolved at the
// edge from EDEN_VAULT_MODE. The bootstrap is lazy (first Resolve), so New stays cheap and a Vault
// briefly unreachable at startup does not fail construction.
//
//nolint:ireturn // returns the secrets.Provider port the verifier resolution holds (the frozen surface).
func buildSecretsProvider(ctx context.Context, configured *configuration) (secrets.Provider, error) {
	vault, err := vaultadapter.New(
		vaultadapter.Config{
			Address:       configured.VaultAddress,
			Mode:          configured.VaultMode,
			TokenFilePath: configured.VaultTokenFilePath, // read only on ModeTokenFile
		},
		vaultadapter.Deps{
			Username: configured.VaultUsername, // read only on ModeUserpass
			Password: configured.VaultPassword, // read only on ModeUserpass; never logged
		},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway: build vault backend", err)
	}

	resolvers := map[string]secrets.Provider{"vault": vault}

	// The connector-credential seam (ADR-0029 §4 / A3): when the connectors DSN reference is configured,
	// resolve it point-of-use (a secret — it carries the Postgres password) through the Vault backend and
	// bind the "eden" scheme (platformconnectoradapter) so eden://connector/<id> resolves. The KEK is the
	// SAME vault:// reference the platformgateway connectors domain seals under. Absent the DSN reference,
	// the "eden" scheme is not bound and every session gets the platform EDEN_CREDENTIAL_REF exactly as
	// today — the fallback is never regressed.
	if configured.ConnectorsDatabaseDSNReference != "" {
		connectorsDSN, dsnErr := resolveDSN(ctx, vault, secrets.Ref(configured.ConnectorsDatabaseDSNReference))
		if dsnErr != nil {
			return nil, errors.Wrap(errors.KindOf(dsnErr), "agentgateway: resolve connectors database dsn", dsnErr)
		}
		seam, seamErr := connectorcredential.Build(
			ctx,
			connectorcredential.Config{
				ConnectorsDSN: connectorsDSN,
				KEK:           secrets.Ref(configured.ConnectorsKEKReference),
				Fallback:      secrets.Ref(configured.CredentialReference),
			},
			connectorcredential.Deps{Secrets: vault},
		)
		if seamErr != nil {
			return nil, errors.Wrap(errors.KindOf(seamErr), "agentgateway: build connector-credential seam", seamErr)
		}
		if seam.Adapter != nil {
			resolvers["eden"] = seam.Adapter // eden://connector/<id> routes to the connector adapter
		}
		// The connectors pool is process-lifetime (resolution runs for the process's life); the seam's
		// Close rides the process, mirroring the record-plane pool's lifetime.
		_ = seam.Close
	}

	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: resolvers},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "agentgateway: build secrets mediator", err)
	}
	return mediator, nil
}

// resolveVerifier resolves the dev-JWT HMAC signing key from ref through the secrets port and
// returns the CONCRETE edenhttp verifier built over it (return-concrete). It mirrors
// platformgateway's identity.NewVerifier: the secret is used ONLY to construct the verifier and is
// zeroized immediately after (the secrets.Use point-of-use scope) — it never reaches a log or a
// field. A missing/denied secret is a wrapped, inspectable error; the value never appears in it.
func resolveVerifier(ctx context.Context, provider secrets.Provider, ref secrets.Reference) (*edenhttp.HMACVerifier, error) {
	secret, err := provider.Resolve(ctx, ref)
	if err != nil {
		return nil, errors.Wrap(errors.KindOf(err), "agentgateway: resolve jwt signing secret", err)
	}
	defer secret.Zeroize()

	var verifier *edenhttp.HMACVerifier
	useErr := secret.Use(func(plaintext []byte) error {
		built, buildErr := edenhttp.NewHMACVerifier(string(plaintext))
		if buildErr != nil {
			return errors.Wrap(errors.KindInvalid, "agentgateway: new hmac verifier", buildErr)
		}
		verifier = built
		return nil
	})
	if useErr != nil {
		return nil, errors.Wrap(errors.KindInvalid, "agentgateway: build jwt verifier", useErr)
	}
	return verifier, nil
}

// resolveDSN resolves the Postgres DSN VALUE from its opaque vault:// reference through the secrets
// port, point-of-use — the same seam resolveVerifier uses for the JWT signing key. The DSN carries an
// embedded password, so it is treated as a secret: it is copied out of the Secret.Use scope into the
// returned string ONLY so the pgx pool can dial (pgxpool.New takes a plain DSN), and the Secret is
// zeroized immediately after. The reference is loggable; the resolved DSN is NOT logged. A
// missing/denied secret is a wrapped, inspectable error; the value never appears in it.
func resolveDSN(ctx context.Context, provider secrets.Provider, ref secrets.Reference) (string, error) {
	secret, err := provider.Resolve(ctx, ref)
	if err != nil {
		return "", errors.Wrap(errors.KindOf(err), "agentgateway: resolve database dsn", err)
	}
	defer secret.Zeroize()

	var dsn string
	useErr := secret.Use(func(plaintext []byte) error {
		dsn = string(plaintext)
		return nil
	})
	if useErr != nil {
		return "", errors.Wrap(errors.KindInvalid, "agentgateway: use database dsn", useErr)
	}
	return dsn, nil
}

// envOr returns the environment value for key, or fallback when it is unset/empty.
func envOr(getenv func(string) string, key, fallback string) string {
	if v := getenv(key); v != "" {
		return v
	}
	return fallback
}
