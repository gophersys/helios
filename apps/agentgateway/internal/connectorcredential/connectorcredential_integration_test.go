//go:build integration

// connectorcredential_integration_test.go is the REAL-substrate proof that a seeded, envelope-sealed
// connector row resolves END TO END into a child-process credential injection (ADR-0029 §4 / A3): it
// stands up a real Postgres with the connectors schema, seals a sentinel value and inserts it as a
// `claude-api` connector under an org, then drives the FULL chain the gateway wires —
// Deriver.DeriveClaudeCredential(org) → eden://connector/<id> → secrets.Mediator("eden" scheme →
// platformconnectoradapter) → agentsession.Pool.Open → the adapter's Spawn receiving an
// InjectedCredential whose Secret.Use yields the sentinel — proving the value is delivered to the
// injection site and NEVER leaks into any event. It also proves the FALLBACK path (an org with no
// claude-api connector derives the platform reference, today's behavior). No mock on the resolution
// path (ADR-0016 §2). docker-out-of-docker: the devcontainer reaches the sibling postgres by its IP.
package connectorcredential_test

import (
	"context"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/platformconnectoradapter"
	"github.com/gophersys/libs/go/secrets/secretstest"

	"github.com/gophersys/eden/apps/agentgateway/internal/connectorcredential"
)

const (
	postgresImage = "postgres:16-alpine"
	// connectorSentinel is the fake credential value sealed into a real connector row and resolved back
	// through the whole chain. A SENTINEL, never a real token — the point is to prove it reaches the
	// injection site yet never leaks into an event.
	connectorSentinel = "SENTINEL-A3-connector-credential-9c0ffee-do-not-leak"
	// kekReference / kekPlaintext are the fixture KEK the test envelope Sealer + the adapter share (the
	// crypto is real; only the KEK bytes are a fixture). kekPlaintext is exactly 32 bytes (AES-256).
	kekReference = "vault://eden/production#connectors-kek"
	kekPlaintext = "0123456789abcdef0123456789abcdef"
)

// TestIntegration_SealedConnectorResolvesIntoChildCredential is the load-bearing A3 proof.
//
//nolint:paralleltest // boots a real container; serial by design so the bridge IP is deterministic.
func TestIntegration_SealedConnectorResolvesIntoChildCredential(t *testing.T) {
	pool := startPostgresWithConnectors(t)
	orgID := uuid.New()

	// Seal the sentinel + insert it as a claude-api connector under orgID (the value crosses once).
	connectorID := sealAndInsertConnector(t, pool, orgID, connectorSentinel)

	// The gateway seam: the Deriver + the "eden"-scheme adapter over the connectors pool + the KEK.
	kekProvider := secretstest.New(map[string]string{kekReference: kekPlaintext})
	adapter, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{KEK: secrets.Ref(kekReference), KEKVersion: 1},
		platformconnectoradapter.Deps{Loader: connectorcredential.NewPostgresLoader(pool), Secrets: kekProvider},
	)
	if err != nil {
		t.Fatalf("platformconnectoradapter.New: %v", err)
	}
	deriver := connectorcredential.NewDeriver(pool, secrets.Ref("vault://eden/production#setup-token"))

	// 1. Derivation: the org has a claude-api connector → eden://connector/<id>.
	derived := deriver.DeriveClaudeCredential(context.Background(), orgID)
	want := "eden://connector/" + connectorID.String()
	if derived.String() != want {
		t.Fatalf("DeriveClaudeCredential = %q, want %q", derived.String(), want)
	}

	// 2. The secrets Mediator routing "eden" → the adapter (the production wiring shape).
	mediator, err := secrets.New(
		secrets.Config{DefaultScheme: "vault"},
		secrets.Deps{Resolvers: map[string]secrets.Provider{"eden": adapter}},
	)
	if err != nil {
		t.Fatalf("secrets.New: %v", err)
	}

	// 3. The agentsession.Pool over the mediator + a CAPTURING adapter that reads the injected credential
	//    at the Spawn injection site — the child-process injection proof.
	captor := &captureAdapter{Adapter: agentsessiontest.New()}
	transcript := agentsessiontest.NewTranscript()
	pool2, err := agentsession.New(
		agentsession.Config{Routing: map[agentsession.RouteKey]agentsession.Route{
			{Role: "assistant"}: {Harness: "capture", Model: "test"},
		}},
		agentsession.Deps{
			Adapters:   map[string]agentsession.Adapter{"capture": captor},
			Secrets:    mediator,
			Transcript: transcript,
			Clock:      systemClock{},
		},
	)
	if err != nil {
		t.Fatalf("agentsession.New: %v", err)
	}

	session, err := pool2.Open(context.Background(), agentsession.Spec{
		Workspace:  t.TempDir(),
		Routing:    agentsession.RouteKey{Role: "assistant"},
		Grants:     []agentsession.ToolGrant{{ID: "grant-read", Tool: "Read", ReadOnly: true}},
		Credential: derived, // the DERIVED eden://connector/<id> — the whole chain hangs off this
	})
	if err != nil {
		t.Fatalf("Pool.Open with the derived connector credential: %v", err)
	}
	t.Cleanup(func() { _ = session.Close(context.Background()) })

	// 4. The child-process injection: the adapter's Spawn received an InjectedCredential whose Secret.Use
	//    yields the SEALED SENTINEL — the value flowed sealed-row → Unseal → mint → inject, end to end.
	got := captor.capturedValue(t)
	if got != connectorSentinel {
		t.Fatalf("injected credential value = %q, want the sealed sentinel (the chain did not deliver it)", got)
	}
}

// TestIntegration_NoConnectorDerivesFallback proves the fallback path against a REAL database: an org
// with NO claude-api connector derives the platform reference (today's behavior, never regressed).
//
//nolint:paralleltest // shares the real-container, serial-by-design discipline.
func TestIntegration_NoConnectorDerivesFallback(t *testing.T) {
	pool := startPostgresWithConnectors(t)
	fallback := secrets.Ref("vault://eden/production#setup-token")
	deriver := connectorcredential.NewDeriver(pool, fallback)

	// An org with no connectors row → the fallback.
	got := deriver.DeriveClaudeCredential(context.Background(), uuid.New())
	if got.String() != fallback.String() {
		t.Fatalf("DeriveClaudeCredential(no connector) = %q, want the fallback %q", got.String(), fallback.String())
	}
}

// ── the capturing adapter: reads the injected credential at the Spawn injection site ─────────────.

// captureAdapter wraps the fake agentsession adapter but INTERCEPTS Spawn to read the injected
// credential's value via Secret.Use — the child-process injection site a real adapter would place the
// value at. It is the proof that the resolved connector plaintext reaches the injection point.
type captureAdapter struct {
	*agentsessiontest.Adapter
	captured string
}

//nolint:gocritic,ireturn // mirrors the frozen agentsession.Adapter.Spawn seam the fake implements.
func (c *captureAdapter) Spawn(ctx context.Context, spec agentsession.Spec, route agentsession.Route, cred agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	if cred.Secret != nil {
		_ = cred.Secret.Use(func(plaintext []byte) error {
			c.captured = string(plaintext) // the injection site: a real adapter sets an env var / helper here
			return nil
		})
	}
	return c.Adapter.Spawn(ctx, spec, route, cred)
}

func (c *captureAdapter) capturedValue(t *testing.T) string {
	t.Helper()
	// Open resolves + Spawns synchronously, so the value is captured by the time Open returns.
	return c.captured
}

// ── real-Postgres harness (connectors schema, sealed insert, reaped) ────────────────────────────.

func sealAndInsertConnector(t *testing.T, pool *pgxpool.Pool, orgID uuid.UUID, value string) uuid.UUID {
	t.Helper()
	sealer, err := envelope.New(
		envelope.Config{KEK: secrets.Ref(kekReference), KEKVersion: 1},
		envelope.Deps{Secrets: secretstest.New(map[string]string{kekReference: kekPlaintext})},
	)
	if err != nil {
		t.Fatalf("envelope.New: %v", err)
	}
	sealed, err := sealer.Seal(context.Background(), []byte(value))
	if err != nil {
		t.Fatalf("Seal: %v", err)
	}
	id := uuid.New()
	ctx := context.Background()
	if _, err := pool.Exec(
		ctx,
		`INSERT INTO connectors (id, organization_id, kind, name, fingerprint) VALUES ($1, $2, 'claude-api', 'default', $3)`,
		id, orgID, envelope.Fingerprint([]byte(value)),
	); err != nil {
		t.Fatalf("insert connector: %v", err)
	}
	if _, err := pool.Exec(
		ctx,
		`INSERT INTO connector_secrets (connector_id, ciphertext, wrapped_dek, nonce_ciphertext, nonce_dek, kek_version)
		 VALUES ($1, $2, $3, $4, $5, $6)`,
		id, sealed.Ciphertext, sealed.WrappedDEK, sealed.NonceCiphertext, sealed.NonceDEK, sealed.KEKVersion,
	); err != nil {
		t.Fatalf("insert connector_secrets: %v", err)
	}
	return id
}

func startPostgresWithConnectors(t *testing.T) *pgxpool.Pool {
	t.Helper()
	requireDocker(t)
	dsn := startPostgres(t)
	pool, err := pgxpool.New(context.Background(), dsn)
	if err != nil {
		t.Fatalf("pgxpool.New: %v", err)
	}
	t.Cleanup(pool.Close)
	const schema = `
		CREATE TABLE IF NOT EXISTS connectors (
			id uuid PRIMARY KEY,
			organization_id uuid NOT NULL,
			kind text NOT NULL,
			name text NOT NULL,
			account_hint text NOT NULL DEFAULT '',
			fingerprint text NOT NULL,
			created_at timestamptz NOT NULL DEFAULT now()
		);
		CREATE TABLE IF NOT EXISTS connector_secrets (
			connector_id uuid PRIMARY KEY REFERENCES connectors(id) ON DELETE CASCADE,
			ciphertext bytea NOT NULL,
			wrapped_dek bytea NOT NULL,
			nonce_ciphertext bytea NOT NULL,
			nonce_dek bytea NOT NULL,
			kek_version integer NOT NULL
		);`
	if _, err := pool.Exec(context.Background(), schema); err != nil {
		t.Fatalf("create schema: %v", err)
	}
	return pool
}

func startPostgres(t *testing.T) string {
	t.Helper()
	name := "eden-connectorcredential-it-" + strings.ReplaceAll(uuid.NewString(), "-", "")[:12]
	//nolint:gosec // G204: the only variable arg is a test-minted uuid name, never external input.
	out, err := exec.Command("docker", "run", "-d", "--rm",
		"--name", name,
		"-e", "POSTGRES_PASSWORD=postgres", "-e", "POSTGRES_DB=connectors",
		postgresImage).CombinedOutput()
	if err != nil {
		t.Fatalf("docker run postgres: %v: %s", err, out)
	}
	t.Cleanup(func() {
		//nolint:gosec // G204: `name` is a test-minted uuid, never external input.
		_ = exec.Command("docker", "rm", "-f", name).Run() //nolint:errcheck // best-effort reap.
	})
	ip := containerIP(t, name)
	dsn := "postgres://postgres:postgres@" + ip + ":5432/connectors?sslmode=disable"
	waitReady(t, dsn)
	return dsn
}

func waitReady(t *testing.T, dsn string) {
	t.Helper()
	deadline := time.Now().Add(60 * time.Second)
	for time.Now().Before(deadline) {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		conn, err := pgx.Connect(ctx, dsn)
		if err == nil {
			pingErr := conn.Ping(ctx)
			_ = conn.Close(ctx) //nolint:errcheck // probe close fault is irrelevant to readiness.
			cancel()
			if pingErr == nil {
				return
			}
		} else {
			cancel()
		}
		time.Sleep(500 * time.Millisecond)
	}
	t.Fatalf("postgres did not become ready within the deadline")
}

func containerIP(t *testing.T, name string) string {
	t.Helper()
	//nolint:gosec // G204: `name` is a test-minted uuid, never external input.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).Output()
	if err != nil {
		t.Fatalf("docker inspect ip: %v", err)
	}
	ip := strings.TrimSpace(string(out))
	if ip == "" {
		t.Fatalf("container %s has no bridge IP yet", name)
	}
	return ip
}

func requireDocker(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Fatalf("docker not on PATH — the integration lane requires a real docker daemon: %v", err)
	}
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }
