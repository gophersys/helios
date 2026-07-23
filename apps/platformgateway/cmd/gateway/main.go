// Command gateway is the composition ROOT for an http-gateway application generated from this
// template (ADR-0023). It owns ONLY the wiring — the libraries own all behavior. The wiring is the
// IOTEA assembly, in order:
//
//	configuration  → parse the process environment ONCE at the edge (the configuration pattern).
//	secrets        → build the redaction Mediator over Vault; resolve credentials by Reference.
//	observability  → build the Provider (slog exporter) the server logs structured Events on.
//	substrate      → detect kubernetes/docker/bare-process (orchestrator.Substrate) so the server
//	                 knows where it runs, mirroring the orchestrator's F1 adapter selection.
//	persistence    → open the typed pgx data layer when a DSN reference is configured (OPTIONAL: no
//	                 DSN → boot probe-only, so the health probes serve before a database exists). Its
//	                 reachability backs the readiness probe.
//	server.New     → assemble the edenhttp spine + the v1 routes behind it (the pure constructor),
//	                 with the readiness probes and the rate-limit budget resolved here.
//	signal drain   → serve until SIGINT/SIGTERM, then a graceful shutdown.
//
// This is the composition root in full: every value is resolved from the environment at the edge and
// threaded through the pure New constructors. The libraries downstream read no env and resolve no
// credential of their own — the wiring is chosen here, once.
package main

import (
	"context"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/google/uuid"

	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/slogadapter"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/vaultadapter"

	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/connectors"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/me"
	"github.com/gophersys/eden/apps/platformgateway/internal/api/v1/users"
	"github.com/gophersys/eden/apps/platformgateway/internal/server"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/credential"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/healthcheck"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/login"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/loginbootstrap"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/middleware"
	"github.com/gophersys/eden/apps/platformgateway/internal/server/runtime"
	"github.com/gophersys/eden/apps/platformgateway/persistence"
)

// defaultAddress is the bind address when EDEN_GATEWAY_ADDRESS is unset.
const defaultAddress = ":8080"

// readHeaderTimeout bounds the request-header read (a long-lived SSE route, if added, is exempt).
const readHeaderTimeout = 10 * time.Second

// shutdownGrace bounds the graceful drain after a signal.
const shutdownGrace = 10 * time.Second

// The IOTEA-style RBAC seed's fixed labels. The default user is seeded as an ADMIN member whose
// permission set carries the wildcard permission "*" (admin-like, "can do everything"). The role +
// permission strings are the seed's constants (the ids are env-overridable in environment.go); the
// role string mirrors the IOTEA OrganizationRole vocabulary (member|admin).
const (
	adminRole              = "admin"
	adminPermissionSetName = "Admin"
)

// adminPermissions is the wildcard permission set the seeded admin member holds: "*" matches every
// "namespace:action" (the IOTEA admin-like grant). It is a package-level value (a slice cannot be a
// const) the seed passes to EnsurePermissionSet.
var adminPermissions = []string{"*"}

func main() {
	os.Exit(realMain())
}

// realMain is the deferred-safe entrypoint body: it owns the signal context and returns an exit
// code, so main's only statement is os.Exit (no defer skipped by a direct os.Exit).
func realMain() int {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: slog.LevelInfo}))
	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	if err := run(ctx, logger); err != nil {
		logger.Error("gateway: exited with error", slog.String("error", err.Error()))
		return 1
	}
	return 0
}

// run is the testable composition body. Every required value is read from the environment ONCE
// here (the configuration pattern); a missing one is a typed startup error, never a silent default.
func run(ctx context.Context, logger *slog.Logger) error {
	// 1. configuration — parse the environment at the edge into the frozen, fully-resolved input.
	environment, err := loadEnvironment()
	if err != nil {
		return err
	}

	// 2. secrets — the redaction Mediator. The composition root is the ONLY place a credential
	// value is resolved; it never reaches a log line (the secrets no-leak contract).
	mediator, err := buildSecrets(&environment)
	if err != nil {
		return err
	}

	// 3. observability — the Provider the server emits structured Events on. The stage value
	// (development|…|production) arrives only here, from configuration (10 §2).
	provider, err := observability.New(
		observability.Config{
			ServiceName:    "platformgateway",
			ServiceVersion: environment.ServiceVersion,
			Environment:    environment.Stage,
			MinSeverity:    observability.SeverityInfo,
		},
		observability.Deps{Exporter: slogadapter.NewWithLogger(logger), Clock: systemClock{}},
	)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "gateway: build observability provider", err)
	}
	defer func() {
		flushCtx, cancel := context.WithTimeout(context.Background(), shutdownGrace)
		defer cancel()
		_ = provider.Flush(flushCtx) //nolint:errcheck // best-effort drain at shutdown.
	}()

	// 4. substrate — detect where we run (docker vs kubernetes), mirroring the orchestrator's F1
	// adapter selection, so the server records its substrate and a future deploy path can branch.
	substrate := runtime.DetectSubstrate(environment.SubstrateHint)
	provider.Log(ctx, observability.SeverityInfo, "gateway: detected substrate",
		observability.String("substrate", substrate.String()))

	// 5. persistence — open the typed pgx data layer when a DSN reference is configured. It is
	// OPTIONAL: with no DSN the gateway boots probe-only (liveness/readiness serve before a database
	// exists), so the binary comes up for the health probes even when Postgres is not yet provisioned.
	// When wired, its reachability backs the readiness probe (503 until the pool round-trips).
	var readinessProbes []healthcheck.Probe
	var userStore users.Store
	var rbacStore me.MembershipReader
	var accountStore login.AccountReader
	var defaultUserProvider loginbootstrap.DefaultProvider
	var defaultMembershipProvider loginbootstrap.MembershipProvider
	var connectorStore connectors.Store
	var tenantResolver connectors.TenantResolver
	var connectorSealer envelope.Sealer
	if !environment.PersistenceDSNRef.IsZero() {
		dataStore, dataErr := persistence.New(
			ctx,
			persistence.Configuration{DSN: environment.PersistenceDSNRef},
			persistence.Dependencies{Secrets: mediator, Observability: provider},
		)
		if dataErr != nil {
			return errors.Wrap(errors.KindUnavailable, "gateway: open persistence", dataErr)
		}
		defer dataStore.Close()

		// IOTEA-style startup: apply the embedded migrations (idempotent, every boot), then seed the
		// default user + the RBAC + the default user's password account. The whole migrate+seed sequence
		// lives in migrateAndSeed so this composition body stays at one altitude.
		if seedErr := migrateAndSeed(ctx, dataStore, &environment); seedErr != nil {
			return seedErr
		}

		readinessProbes = append(readinessProbes, postgresProbe(dataStore))
		// The persisted `users`/`me` routes + the public login bootstrap draw on the typed facades;
		// with no DSN they stay nil and only the no-persistence `ping` reference is mounted (the
		// probe-only boot). *persistence.Users + *persistence.RBAC satisfy the respective ports.
		usersFacade := dataStore.Users()
		rbacFacade := dataStore.RBAC()
		userStore = usersFacade
		rbacStore = rbacFacade
		accountStore = dataStore.Accounts()
		defaultUserProvider = usersFacade
		defaultMembershipProvider = rbacFacade

		// The connectors domain (ADR-0029): the envelope Sealer (KEK from the platform Vault via the
		// same mediator the DSN/JWT resolve through) + the connector store + the tenant resolver over
		// RBAC. All three are wired together or not at all — a credential cannot be stored without the
		// Sealer, so the resource mounts only when the whole set is present.
		sealer, sealerErr := envelope.New(
			envelope.Config{KEK: environment.ConnectorsKEKRef, KEKVersion: environment.ConnectorsKEKVersion},
			envelope.Deps{Secrets: mediator},
		)
		if sealerErr != nil {
			return errors.Wrap(errors.KindInvalid, "gateway: build connectors envelope sealer", sealerErr)
		}
		connectorSealer = sealer
		connectorStore = dataStore.Connectors()
		tenantResolver = rbacTenantResolver{rbac: rbacFacade}
	}

	// 6. server.New — the pure constructor that assembles the edenhttp spine + the v1 routes, with
	// the readiness probes and the rate-limit budget the composition root resolved.
	srv, err := server.New(
		server.Config{
			JWTSecretRef:      environment.JWTSecretRef,
			HeartbeatInterval: environment.HeartbeatInterval,
			Substrate:         substrate,
			RateLimit: middleware.RateLimitConfig{
				Limit:  environment.RateLimit,
				Window: environment.RateLimitWindow,
			},
			TokenTTL: environment.TokenTTL,
		},
		server.Deps{
			Secrets:           mediator,
			Observability:     provider,
			ReadinessProbes:   readinessProbes,
			Users:             userStore,
			RBAC:              rbacStore,
			Accounts:          accountStore,
			DefaultUser:       defaultUserProvider,
			DefaultMembership: defaultMembershipProvider,
			Connectors:        connectorStore,
			Tenants:           tenantResolver,
			Sealer:            connectorSealer,
		},
	)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "gateway: build server", err)
	}

	// 7. serve — bind the listener and run until the signal context is canceled, then drain.
	listener, err := net.Listen("tcp", address(&environment))
	if err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: bind listener", err)
	}
	logger.Info("gateway: serving", slog.String("address", listener.Addr().String()))
	return serve(ctx, srv.Handler(), listener)
}

// migrateAndSeed runs the IOTEA-style startup sequence on a fresh-or-existing database: apply the
// embedded migrations (idempotent), then seed the default user, the RBAC (a default organization, an
// admin permission set with permissions {*}, and the default user as an admin member), and the default
// user's "password" account. Every step is ON CONFLICT DO NOTHING, so the sequence is safe on every boot;
// the schema step (Migrate) and the data steps stay separable. The dev password is bcrypt-hashed HERE and
// stored as the account's password_hash; the plaintext never leaves this scope and is NEVER logged. The
// provider_account_id is the lowercased email (login.NormalizeEmail — the SAME normalization the
// Authenticator applies), so POST /auth/login {email, password} resolves this account. This is the
// OAuth-ready seam: a Google/GitHub account is find-or-created the same way (provider 'google'/'github',
// a NULL password_hash) on first OAuth login — only user resolution differs, the mint + authorize do not.
func migrateAndSeed(ctx context.Context, dataStore *persistence.Persistence, environment *Environment) error {
	if err := dataStore.Migrate(ctx); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: apply migrations", err)
	}
	if err := dataStore.Users().EnsureDefault(ctx,
		environment.DefaultUserID, environment.DefaultUserEmail, environment.DefaultUserName); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: seed default user", err)
	}
	if err := dataStore.RBAC().EnsureOrganization(ctx,
		environment.DefaultOrganizationID, environment.DefaultOrganizationName); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: seed default organization", err)
	}
	if err := dataStore.RBAC().EnsurePermissionSet(ctx,
		environment.AdminPermissionSetID, environment.DefaultOrganizationID,
		adminPermissionSetName, adminPermissions); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: seed admin permission set", err)
	}
	if err := dataStore.RBAC().EnsureMembership(ctx,
		environment.DefaultMembershipID, environment.DefaultOrganizationID,
		environment.DefaultUserID, environment.AdminPermissionSetID, adminRole); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: seed default membership", err)
	}
	// bcrypt the dev password HERE (the plaintext never leaves this scope and is never logged), then plant
	// the default user's "password" account keyed on the lowercased email.
	passwordHash, err := credential.Hash(environment.DefaultUserPassword)
	if err != nil {
		return errors.Wrap(errors.KindInvalid, "gateway: hash default user password", err)
	}
	if err := dataStore.Accounts().EnsureAccount(ctx,
		environment.DefaultPasswordAccountID, environment.DefaultUserID,
		persistence.ProviderPassword, login.NormalizeEmail(environment.DefaultUserEmail), passwordHash); err != nil {
		return errors.Wrap(errors.KindUnavailable, "gateway: seed default password account", err)
	}
	return nil
}

// postgresProbe builds the readiness probe backed by the persistence pool: it reports the pool
// reachable iff a trivial round-trip query succeeds, so readiness answers 503 (naming "postgres")
// until the database is reachable. It is the composition root's adaptation of the concrete data
// layer onto the server's narrow healthcheck.Probe port (return-concrete: a usable NamedProbe).
func postgresProbe(dataStore *persistence.Persistence) healthcheck.NamedProbe {
	return healthcheck.NamedProbe{
		Label: "postgres",
		CheckFunc: func(ctx context.Context) error {
			// A bounded list of at most one row round-trips the pool to Postgres and back — the
			// cheapest honest "can I serve traffic" signal over the real connection.
			if _, err := dataStore.Users().List(ctx, 1, 0); err != nil {
				return errors.Wrap(errors.KindUnavailable, "gateway: postgres readiness probe", err)
			}
			return nil
		},
	}
}

// rbacTenantResolver adapts the *persistence.RBAC facade onto the connectors.TenantResolver port: it
// resolves a caller (user id) to their owning organization id via MembershipFor. It is the
// composition root's adaptation seam (the connectors routes depend on the narrow OrganizationFor
// method, not the whole RBAC facade). A membership-less caller surfaces the facade's typed
// KindNotFound, which the route renders as 404 (they own no connectors).
type rbacTenantResolver struct {
	rbac *persistence.RBAC
}

// OrganizationFor resolves the caller's owning organization id from their first/default membership.
func (r rbacTenantResolver) OrganizationFor(ctx context.Context, userID uuid.UUID) (uuid.UUID, error) {
	membership, err := r.rbac.MembershipFor(ctx, userID)
	if err != nil {
		return uuid.UUID{}, errors.Wrap(errors.KindOf(err), "gateway: resolve caller organization", err)
	}
	return membership.OrganizationID, nil
}

// compile-time: the adapter satisfies the connectors tenant-resolution port.
var _ connectors.TenantResolver = rbacTenantResolver{}

// buildSecrets wires the secrets Mediator over the REAL Vault backend (the IOTEA way, mirroring
// agent-runtime's composition). The mode is chosen by EDEN_VAULT_MODE: "token-file" (the
// kubernetes ServiceAccount path) else userpass (local). The composition root is the ONLY place a
// resolver adapter is bound; the server downstream holds the narrow secrets.Provider port.
func buildSecrets(environment *Environment) (*secrets.Mediator, error) {
	address := environment.VaultAddress
	if address == "" {
		address = "http://127.0.0.1:8200"
	}
	var adapter secrets.Provider
	var err error
	if vaultadapter.ParseMode(environment.VaultMode) == vaultadapter.ModeTokenFile {
		adapter, err = vaultadapter.New(
			vaultadapter.Config{Address: address, Mode: vaultadapter.ModeTokenFile, TokenFilePath: os.Getenv("EDEN_VAULT_TOKEN_FILE")},
			vaultadapter.Deps{},
		)
	} else {
		adapter, err = vaultadapter.New(
			vaultadapter.Config{Address: address, Mode: vaultadapter.ModeUserpass},
			vaultadapter.Deps{Username: os.Getenv("VAULT_USERNAME"), Password: os.Getenv("VAULT_PASSWORD")},
		)
	}
	if err != nil {
		return nil, errors.Wrap(errors.KindUnavailable, "gateway: build vault backend", err)
	}
	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"vault": adapter}},
	)
	if err != nil {
		return nil, errors.Wrap(errors.KindInvalid, "gateway: build secrets mediator", err)
	}
	return mediator, nil
}

// serve runs the HTTP server until ctx is canceled, then performs a graceful shutdown.
func serve(ctx context.Context, handler http.Handler, listener net.Listener) error {
	httpServer := &http.Server{
		Handler:           handler,
		ReadHeaderTimeout: readHeaderTimeout,
		BaseContext:       func(net.Listener) context.Context { return ctx },
	}
	serveErr := make(chan error, 1)
	go func() { serveErr <- httpServer.Serve(listener) }()

	select {
	case <-ctx.Done():
		shutdownCtx, cancel := context.WithTimeout(context.Background(), shutdownGrace)
		defer cancel()
		_ = httpServer.Shutdown(shutdownCtx) //nolint:errcheck // shutdown best-effort on signal drain.
		return nil
	case err := <-serveErr:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return errors.Wrap(errors.KindUnavailable, "gateway: serve", err)
	}
}

// address resolves the bind address (EDEN_GATEWAY_ADDRESS or the default).
func address(environment *Environment) string {
	if environment.Address != "" {
		return environment.Address
	}
	return defaultAddress
}

// systemClock is the production time source. The app is the one place a real clock is read — the
// libraries stay pure (10 §4).
type systemClock struct{}

// Now returns the current wall-clock instant.
func (systemClock) Now() time.Time { return time.Now() }
