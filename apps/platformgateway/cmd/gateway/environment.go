package main

import (
	"os"
	"strconv"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/configuration"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// defaultHeartbeat is the SSE keepalive cadence when EDEN_GATEWAY_HEARTBEAT is unset (the edenhttp
// spine defaults it too; the env override lives at the edge).
const defaultHeartbeat = 20 * time.Second

// The default user the IOTEA-style startup seed plants when its env override is unset. The id is a
// fixed uuid so the default user's id is stable across boots; email/name are sensible single-user
// dev defaults the login bootstrap renders. All three are env-overridable.
const (
	defaultUserIDFallback    = "00000000-0000-0000-0000-0000000000ed"
	defaultUserEmailFallback = "mateo@eden.local"
	defaultUserNameFallback  = "Mateo Segura"
)

// Environment is the parsed, fully-resolved process environment (the configuration pattern: read
// ONCE at the edge). A missing REQUIRED value is a typed startup error, not a silent default. The
// libraries downstream read no env of their own — everything arrives through this value.
type Environment struct {
	Address           string            // EDEN_GATEWAY_ADDRESS — the bind address; "" == defaultAddress.
	Stage             string            // EDEN_STAGE — development|test|staging|production (10 §2).
	ServiceVersion    string            // EDEN_SERVICE_VERSION — stamped on observability resources.
	JWTSecretRef      secrets.Reference // EDEN_GATEWAY_JWT_SECRET_REF — the secrets Reference for the JWT signing key.
	HeartbeatInterval time.Duration     // EDEN_GATEWAY_HEARTBEAT — the SSE keepalive cadence.
	SubstrateHint     string            // EDEN_SUBSTRATE — an explicit "docker"|"kubernetes" override for detection.
	VaultAddress      string            // VAULT_ADDR — the Vault backend address; "" == the local default.
	VaultMode         string            // EDEN_VAULT_MODE — "token-file" (kubernetes) else userpass (local).
	PersistenceDSNRef secrets.Reference // EDEN_GATEWAY_DATABASE_DSN_REF — the secrets Reference for the Postgres DSN; zero → boot probe-only (no DB).
	DefaultUserID     uuid.UUID         // EDEN_PLATFORM_DEFAULT_USER_ID — the seeded default user's stable id.
	DefaultUserEmail  string            // EDEN_PLATFORM_DEFAULT_USER_EMAIL — the seeded default user's login handle.
	DefaultUserName   string            // EDEN_PLATFORM_DEFAULT_USER_NAME — the seeded default user's display name.
	RateLimit         int               // EDEN_GATEWAY_RATE_LIMIT — per-client request budget per window; 0 → unlimited.
	RateLimitWindow   time.Duration     // EDEN_GATEWAY_RATE_LIMIT_WINDOW — the rolling window the budget is measured over.
}

// loadEnvironment parses the environment with the configuration library's env edge, then resolves
// the required values into the frozen Environment. SKELETON: it reads from os.Environ via the
// configuration FormatEnv decoder so a generated app extends the parsed Document rather than
// reaching for os.Getenv ad hoc; the required JWT secret reference is validated here.
func loadEnvironment() (Environment, error) {
	// The configuration parser is the typed env edge (FormatEnv: KEY=VALUE lines, dotted keys nest).
	// The composition root reads the resolved process env directly for the required startup values
	// below; a generated app extends this Parser over its layered sources (.env / config.yaml) and
	// calls parser.Parse instead of reaching for os.Getenv ad hoc. Constructing it here proves the
	// configuration library is assembled correctly at the edge, the one place env is read.
	if _, err := configuration.New(
		configuration.Config{Format: configuration.FormatEnv},
		configuration.Deps{},
	); err != nil {
		return Environment{}, errors.Wrap(errors.KindInvalid, "gateway: build configuration parser", err)
	}

	rawRef := os.Getenv("EDEN_GATEWAY_JWT_SECRET_REF")
	if rawRef == "" {
		return Environment{}, errors.New(errors.KindInvalid,
			"gateway: EDEN_GATEWAY_JWT_SECRET_REF is required (the gateway is behind auth even locally)")
	}
	jwtRef, err := secrets.ParseReference(rawRef)
	if err != nil {
		return Environment{}, errors.Wrap(errors.KindInvalid, "gateway: parse EDEN_GATEWAY_JWT_SECRET_REF", err)
	}

	heartbeat := defaultHeartbeat
	if raw := os.Getenv("EDEN_GATEWAY_HEARTBEAT"); raw != "" {
		parsed, parseErr := time.ParseDuration(raw)
		if parseErr != nil {
			return Environment{}, errors.Wrap(errors.KindInvalid, "gateway: parse EDEN_GATEWAY_HEARTBEAT", parseErr)
		}
		heartbeat = parsed
	}

	stage := os.Getenv("EDEN_STAGE")
	if stage == "" {
		stage = "development"
	}

	// The Postgres DSN reference is OPTIONAL: when unset the gateway boots probe-only (no DB) so
	// liveness/readiness serve before persistence is provisioned. When set it is a secrets Reference
	// (loggable; the value resolves through Vault at startup), never a raw DSN in the environment.
	var dsnRef secrets.Reference
	if raw := os.Getenv("EDEN_GATEWAY_DATABASE_DSN_REF"); raw != "" {
		dsnRef, err = secrets.ParseReference(raw)
		if err != nil {
			return Environment{}, errors.Wrap(errors.KindInvalid, "gateway: parse EDEN_GATEWAY_DATABASE_DSN_REF", err)
		}
	}

	rateLimit, err := parseNonNegativeInt("EDEN_GATEWAY_RATE_LIMIT")
	if err != nil {
		return Environment{}, err
	}
	rateWindow, err := parseOptionalDuration("EDEN_GATEWAY_RATE_LIMIT_WINDOW")
	if err != nil {
		return Environment{}, err
	}

	defaultUserID, err := parseUUIDOrDefault("EDEN_PLATFORM_DEFAULT_USER_ID", defaultUserIDFallback)
	if err != nil {
		return Environment{}, err
	}

	return Environment{
		Address:           os.Getenv("EDEN_GATEWAY_ADDRESS"),
		Stage:             stage,
		ServiceVersion:    os.Getenv("EDEN_SERVICE_VERSION"),
		JWTSecretRef:      jwtRef,
		HeartbeatInterval: heartbeat,
		SubstrateHint:     os.Getenv("EDEN_SUBSTRATE"),
		VaultAddress:      os.Getenv("VAULT_ADDR"),
		VaultMode:         os.Getenv("EDEN_VAULT_MODE"),
		PersistenceDSNRef: dsnRef,
		DefaultUserID:     defaultUserID,
		DefaultUserEmail:  getenvOr("EDEN_PLATFORM_DEFAULT_USER_EMAIL", defaultUserEmailFallback),
		DefaultUserName:   getenvOr("EDEN_PLATFORM_DEFAULT_USER_NAME", defaultUserNameFallback),
		RateLimit:         rateLimit,
		RateLimitWindow:   rateWindow,
	}, nil
}

// getenvOr reads name from the environment, falling back to the given default when it is unset. It is
// the edge default the seed values use (a present-but-empty override would intentionally clear it).
func getenvOr(name, fallback string) string {
	if value, ok := os.LookupEnv(name); ok {
		return value
	}
	return fallback
}

// parseUUIDOrDefault reads name as a uuid, falling back to the given default string when unset. A
// present-but-malformed value (or a malformed fallback) is a typed startup error, never a silent zero.
func parseUUIDOrDefault(name, fallback string) (uuid.UUID, error) {
	raw := os.Getenv(name)
	if raw == "" {
		raw = fallback
	}
	parsed, err := uuid.Parse(raw)
	if err != nil {
		return uuid.UUID{}, errors.Wrap(errors.KindInvalid, "gateway: parse "+name, err)
	}
	return parsed, nil
}

// parseNonNegativeInt reads name as a non-negative integer, defaulting to 0 (unset → the feature's
// off value) and rejecting a malformed or negative value as a typed startup error.
func parseNonNegativeInt(name string) (int, error) {
	raw := os.Getenv(name)
	if raw == "" {
		return 0, nil
	}
	value, err := strconv.Atoi(raw)
	if err != nil {
		return 0, errors.Wrap(errors.KindInvalid, "gateway: parse "+name, err)
	}
	if value < 0 {
		return 0, errors.New(errors.KindInvalid, "gateway: "+name+" must be non-negative")
	}
	return value, nil
}

// parseOptionalDuration reads name as a Go duration, defaulting to 0 (unset → the consumer's own
// default) and rejecting a malformed value as a typed startup error.
func parseOptionalDuration(name string) (time.Duration, error) {
	raw := os.Getenv(name)
	if raw == "" {
		return 0, nil
	}
	value, err := time.ParseDuration(raw)
	if err != nil {
		return 0, errors.Wrap(errors.KindInvalid, "gateway: parse "+name, err)
	}
	return value, nil
}
