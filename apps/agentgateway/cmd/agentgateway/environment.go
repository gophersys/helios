package main

import (
	"context"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"
)

// vaultTokenFilePath is the default sidecar token-file path when EDEN_VAULT_TOKEN_FILE is unset on
// the production path (matches the agent-runtime / orchestrator deployment's EDEN_VAULT_TOKEN_FILE).
const vaultTokenFilePath = "/vault/secrets/token" // #nosec G101 -- a sidecar output PATH, not a credential value.

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

	// VaultMode / VaultAddress / VaultTokenFilePath / VaultUsername / VaultPassword are the dual-mode
	// Vault bootstrap the secrets provider is built over (EDEN_VAULT_MODE selects the production
	// token-file path — the K8s-SA sidecar output — vs the local userpass path). The password is read
	// but NEVER logged; it lives only in this struct and the adapter login body.
	VaultMode          vaultadapter.Mode
	VaultAddress       string
	VaultTokenFilePath string
	VaultUsername      string
	VaultPassword      string
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

// buildSecretsProvider builds the secrets Mediator over the dual-mode Vault backend: the PRODUCTION
// token-file path (ModeTokenFile — the K8s-SA sidecar output at VaultTokenFilePath, re-read per
// Resolve) on the cluster, or the LOCAL userpass bootstrap for a local run. It mirrors
// liveserve.buildSecretsProvider / agentgateway-orchestrator.buildSecretsProvider's mediator wiring
// (one scheme, "vault"); the ONLY difference is the per-Mode backend Config/Deps, resolved at the
// edge from EDEN_VAULT_MODE. The bootstrap is lazy (first Resolve), so New stays cheap and a Vault
// briefly unreachable at startup does not fail construction.
//
//nolint:ireturn // returns the secrets.Provider port the verifier resolution holds (the frozen surface).
func buildSecretsProvider(configured *configuration) (secrets.Provider, error) {
	adapter, err := vaultadapter.New(
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
	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
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

// envOr returns the environment value for key, or fallback when it is unset/empty.
func envOr(getenv func(string) string, key, fallback string) string {
	if v := getenv(key); v != "" {
		return v
	}
	return fallback
}
