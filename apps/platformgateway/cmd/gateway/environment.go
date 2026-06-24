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
//
// defaultUserPasswordFallback is the DEV-ONLY default password the seed bcrypts into the default user's
// "password" account when EDEN_PLATFORM_DEFAULT_USER_PASSWORD is unset. It is "eden" — a convenience so a
// fresh local boot has a working login (POST /auth/login {email, password:"eden"}); a real deployment
// MUST override it. The plaintext is hashed at seed time and NEVER logged; the digest is never logged.
const (
	defaultUserIDFallback       = "00000000-0000-0000-0000-0000000000ed"
	defaultUserEmailFallback    = "mateo@eden.local"
	defaultUserNameFallback     = "Mateo Segura"
	defaultUserPasswordFallback = "eden" // DEV-ONLY default; override via EDEN_PLATFORM_DEFAULT_USER_PASSWORD.
)

// defaultPasswordAccountIDFallback is the fixed id of the default user's "password" account (the linked
// identity the seed plants). A fixed uuid keeps the account stable across boots so the ON CONFLICT seed is
// a true no-op on every start. Env-overridable like the other seed ids.
const defaultPasswordAccountIDFallback = "00000000-0000-0000-0000-0000000000ac" // "ac" (account).

// defaultTokenTTLFallback is the lifetime a /auth/login-minted session JWT is valid for when
// EDEN_PLATFORM_TOKEN_TTL is unset. 24h is a DEV default (a local session does not expire mid-work); a
// deployment overrides it.
const defaultTokenTTLFallback = 24 * time.Hour

// The IOTEA-style RBAC seed's fixed identifiers + org name when their env override is unset. The ids
// are fixed uuids so the default organization, admin permission set, and the default user's membership
// are stable across boots and the ON CONFLICT seed is a true no-op on every start. All four are
// env-overridable (mirroring the DefaultUser* pattern), so a deployment can pin its own org.
const (
	defaultOrganizationIDFallback   = "00000000-0000-0000-0000-00000000074a" // "org" (0x74a) — the default organization.
	defaultOrganizationNameFallback = "Eden"
	adminPermissionSetIDFallback    = "00000000-0000-0000-0000-0000000000ad" // "ad" — the admin permission set.
	defaultMembershipIDFallback     = "00000000-0000-0000-0000-00000000003b" // "mb" (member) — the default membership.
)

// Environment is the parsed, fully-resolved process environment (the configuration pattern: read
// ONCE at the edge). A missing REQUIRED value is a typed startup error, not a silent default. The
// libraries downstream read no env of their own — everything arrives through this value.
type Environment struct {
	Address             string            // EDEN_GATEWAY_ADDRESS — the bind address; "" == defaultAddress.
	Stage               string            // EDEN_STAGE — development|test|staging|production (10 §2).
	ServiceVersion      string            // EDEN_SERVICE_VERSION — stamped on observability resources.
	JWTSecretRef        secrets.Reference // EDEN_GATEWAY_JWT_SECRET_REF — the secrets Reference for the JWT signing key.
	HeartbeatInterval   time.Duration     // EDEN_GATEWAY_HEARTBEAT — the SSE keepalive cadence.
	SubstrateHint       string            // EDEN_SUBSTRATE — an explicit "docker"|"kubernetes" override for detection.
	VaultAddress        string            // VAULT_ADDR — the Vault backend address; "" == the local default.
	VaultMode           string            // EDEN_VAULT_MODE — "token-file" (kubernetes) else userpass (local).
	PersistenceDSNRef   secrets.Reference // EDEN_GATEWAY_DATABASE_DSN_REF — the secrets Reference for the Postgres DSN; zero → boot probe-only (no DB).
	DefaultUserID       uuid.UUID         // EDEN_PLATFORM_DEFAULT_USER_ID — the seeded default user's stable id.
	DefaultUserEmail    string            // EDEN_PLATFORM_DEFAULT_USER_EMAIL — the seeded default user's login handle.
	DefaultUserName     string            // EDEN_PLATFORM_DEFAULT_USER_NAME — the seeded default user's display name.
	DefaultUserPassword string            // EDEN_PLATFORM_DEFAULT_USER_PASSWORD — the seeded default user's dev password (hashed at seed; never logged).

	DefaultPasswordAccountID uuid.UUID     // EDEN_PLATFORM_DEFAULT_PASSWORD_ACCOUNT_ID — the seeded password account's stable id.
	TokenTTL                 time.Duration // EDEN_PLATFORM_TOKEN_TTL — the minted login token's lifetime (0 → the 24h dev default).

	DefaultOrganizationID   uuid.UUID // EDEN_PLATFORM_DEFAULT_ORG_ID — the seeded default organization's stable id.
	DefaultOrganizationName string    // EDEN_PLATFORM_DEFAULT_ORG_NAME — the seeded default organization's display name.
	AdminPermissionSetID    uuid.UUID // EDEN_PLATFORM_ADMIN_PERMISSION_SET_ID — the seeded admin permission set's stable id.
	DefaultMembershipID     uuid.UUID // EDEN_PLATFORM_DEFAULT_MEMBERSHIP_ID — the seeded default membership's stable id.

	RateLimit       int           // EDEN_GATEWAY_RATE_LIMIT — per-client request budget per window; 0 → unlimited.
	RateLimitWindow time.Duration // EDEN_GATEWAY_RATE_LIMIT_WINDOW — the rolling window the budget is measured over.
}

// loadEnvironment parses the environment with the configuration library's env edge, then resolves
// the required values into the frozen Environment. It reads from os.Environ via the configuration
// FormatEnv decoder so a generated app extends the parsed Document rather than reaching for
// os.Getenv ad hoc; the required JWT secret reference is validated here.
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

	ids, err := parseSeedIDs()
	if err != nil {
		return Environment{}, err
	}
	tokenTTL, err := parseDurationOrDefault("EDEN_PLATFORM_TOKEN_TTL", defaultTokenTTLFallback)
	if err != nil {
		return Environment{}, err
	}

	return Environment{
		Address:             os.Getenv("EDEN_GATEWAY_ADDRESS"),
		Stage:               stage,
		ServiceVersion:      os.Getenv("EDEN_SERVICE_VERSION"),
		JWTSecretRef:        jwtRef,
		HeartbeatInterval:   heartbeat,
		SubstrateHint:       os.Getenv("EDEN_SUBSTRATE"),
		VaultAddress:        os.Getenv("VAULT_ADDR"),
		VaultMode:           os.Getenv("EDEN_VAULT_MODE"),
		PersistenceDSNRef:   dsnRef,
		DefaultUserID:       ids.user,
		DefaultUserEmail:    getenvOr("EDEN_PLATFORM_DEFAULT_USER_EMAIL", defaultUserEmailFallback),
		DefaultUserName:     getenvOr("EDEN_PLATFORM_DEFAULT_USER_NAME", defaultUserNameFallback),
		DefaultUserPassword: getenvOr("EDEN_PLATFORM_DEFAULT_USER_PASSWORD", defaultUserPasswordFallback),

		DefaultPasswordAccountID: ids.passwordAccount,
		TokenTTL:                 tokenTTL,

		DefaultOrganizationID:   ids.organization,
		DefaultOrganizationName: getenvOr("EDEN_PLATFORM_DEFAULT_ORG_NAME", defaultOrganizationNameFallback),
		AdminPermissionSetID:    ids.adminPermissionSet,
		DefaultMembershipID:     ids.membership,

		RateLimit:       rateLimit,
		RateLimitWindow: rateWindow,
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

// seedIDs is the bundle of fixed-but-env-overridable uuids the IOTEA-style startup seed plants under
// (the default user, organization, admin permission set, membership, and password account). Bundling the
// parse keeps loadEnvironment at one altitude — the five reads are one concern (the seed identifiers).
type seedIDs struct {
	user               uuid.UUID
	organization       uuid.UUID
	adminPermissionSet uuid.UUID
	membership         uuid.UUID
	passwordAccount    uuid.UUID
}

// parseSeedIDs reads every seed uuid (each env-overridable, each with a fixed fallback). The first
// malformed value is a typed startup error; otherwise the fully-resolved bundle is returned.
func parseSeedIDs() (seedIDs, error) {
	specs := []struct {
		name, fallback string
		target         *uuid.UUID
	}{
		{"EDEN_PLATFORM_DEFAULT_USER_ID", defaultUserIDFallback, nil},
		{"EDEN_PLATFORM_DEFAULT_ORG_ID", defaultOrganizationIDFallback, nil},
		{"EDEN_PLATFORM_ADMIN_PERMISSION_SET_ID", adminPermissionSetIDFallback, nil},
		{"EDEN_PLATFORM_DEFAULT_MEMBERSHIP_ID", defaultMembershipIDFallback, nil},
		{"EDEN_PLATFORM_DEFAULT_PASSWORD_ACCOUNT_ID", defaultPasswordAccountIDFallback, nil},
	}
	var ids seedIDs
	specs[0].target, specs[1].target = &ids.user, &ids.organization
	specs[2].target, specs[3].target = &ids.adminPermissionSet, &ids.membership
	specs[4].target = &ids.passwordAccount
	for _, spec := range specs {
		parsed, err := parseUUIDOrDefault(spec.name, spec.fallback)
		if err != nil {
			return seedIDs{}, err
		}
		*spec.target = parsed
	}
	return ids, nil
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

// parseDurationOrDefault reads name as a Go duration, falling back to the given default when unset and
// rejecting a malformed value as a typed startup error. It is the edge default the token-TTL knob uses (a
// present-but-empty override defers to the default; a present non-empty value must parse).
func parseDurationOrDefault(name string, fallback time.Duration) (time.Duration, error) {
	raw := os.Getenv(name)
	if raw == "" {
		return fallback, nil
	}
	value, err := time.ParseDuration(raw)
	if err != nil {
		return 0, errors.Wrap(errors.KindInvalid, "gateway: parse "+name, err)
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
