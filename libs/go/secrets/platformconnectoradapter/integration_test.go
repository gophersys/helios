//go:build integration

// Package platformconnectoradapter_test's integration suite runs against a REAL PostgreSQL — the
// OFFICIAL postgres:16-alpine container (already pre-pulled in the devcontainer) — proving the adapter
// resolves an envelope-sealed connector row END TO END through its real pgx-backed Transport: seal a
// value via the REAL envelope crypto, insert it into a real connectors/connector_secrets schema, then
// Resolve "eden://connector/<id>" and assert the plaintext round-trips into a minted *secrets.Secret,
// the value NEVER leaks, and a cross-tenant id is a typed NotFound (the WHERE organization_id predicate).
//
// It is gated behind the `integration` build tag so the default `go test` (and the pre-commit hook)
// stays fast; run it with `go test -tags integration ./...`. The container is reaped on t.Cleanup (on
// failure too) under a unique per-test name, so parallel or abandoned runs never leak. The adapter
// resolves through its REAL pgx transport — never a mock (ADR-0016 §2). docker-out-of-docker: the
// devcontainer reaches the sibling postgres by its docker-bridge IP.
package platformconnectoradapter_test

import (
	"context"
	"fmt"
	"os/exec"
	"strings"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"

	"github.com/gophersys/libs/go/envelope"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/platformconnectoradapter"
	"github.com/gophersys/libs/go/secrets/secretstest"
)

// postgresImage is the ephemeral database image (pre-pulled in the devcontainer).
const postgresImage = "postgres:16-alpine"

// integrationCanary is the value sealed into REAL Postgres and resolved back through the adapter. It is
// high-entropy + self-labeling so the no-leak assertion's needle is unambiguous.
const integrationCanary = "connector-REAL-PG-roundtrip-9c0ffee-d34db33f-do-not-leak"

// pgxTransport is the REAL platformconnectoradapter.SealedRowLoader for the integration lane: it loads the
// envelope-sealed material for a connector id from the SAME connectors/connector_secrets tables the
// platformgateway domain writes, TENANT-SCOPED to a fixed org (the WHERE organization_id predicate that
// is the cross-tenant isolation invariant, ADR-0029 §2.3). It is the shape the production composition
// root's binding takes; here it drives a real pgxpool. A pgx.ErrNoRows (a miss, or a cross-tenant id)
// is the zero SealedRecord — the documented "no such connector" sentinel the adapter maps to NotFound.
type pgxTransport struct {
	pool           *pgxpool.Pool
	organizationID uuid.UUID
}

func (t *pgxTransport) LoadSealed(ctx context.Context, id string) (platformconnectoradapter.SealedRecord, error) {
	connectorID, err := uuid.Parse(id)
	if err != nil {
		// A non-uuid connector id names no row; the tenant-scoped SELECT below would miss anyway. Return
		// the absent zero value so the adapter maps it to NotFound (not a leaked parse error).
		return platformconnectoradapter.SealedRecord{}, nil
	}
	const query = `
		SELECT cs.ciphertext, cs.wrapped_dek, cs.nonce_ciphertext, cs.nonce_dek, cs.kek_version
		FROM connector_secrets cs
		JOIN connectors c ON c.id = cs.connector_id
		WHERE c.id = $1 AND c.organization_id = $2`
	var record platformconnectoradapter.SealedRecord
	row := t.pool.QueryRow(ctx, query, connectorID, t.organizationID)
	scanErr := row.Scan(&record.Ciphertext, &record.WrappedDEK, &record.NonceCiphertext, &record.NonceDEK, &record.KEKVersion)
	if scanErr != nil {
		if errors.Is(scanErr, pgx.ErrNoRows) {
			return platformconnectoradapter.SealedRecord{}, nil // tenant-scoped miss → absent
		}
		return platformconnectoradapter.SealedRecord{}, errors.Wrap(errors.KindUnavailable, "pgxTransport: load sealed row", scanErr)
	}
	return record, nil
}

// TestIntegration_RealPostgresConnectorRoundTrip is the load-bearing real-Postgres proof: it stands up a
// real database, creates the connectors schema, seals the canary via the REAL envelope crypto under a
// fixed org, inserts the row, and resolves it through the adapter's REAL pgx transport. It asserts (1)
// the value round-trips byte-for-byte through Use, and (2) the canary appears in NO surfaced artifact of
// the resolved Secret. No mock anywhere on this path.
//
//nolint:paralleltest // boots a real container; serial by design so the bridge-IP is deterministic.
func TestIntegration_RealPostgresConnectorRoundTrip(t *testing.T) {
	pool, orgID := startPostgresWithConnectors(t)
	adapter := realAdapter(t, pool, orgID)

	id := uuid.New()
	sealAndInsert(t, pool, orgID, id, integrationCanary)

	sec, err := adapter.Resolve(context.Background(), secrets.Ref("eden://connector/"+id.String()))
	if err != nil {
		t.Fatalf("Resolve against real Postgres: %v", err)
	}
	defer sec.Zeroize()

	got, err := secrets.Use1(sec, func(b []byte) (string, error) { return string(b), nil })
	if err != nil {
		t.Fatalf("Use1: %v", err)
	}
	if got != integrationCanary {
		t.Fatalf("real-Postgres round-trip = %q, want the sealed canary", got)
	}
	assertNoLeak(t, sec)
}

// TestIntegration_RealPostgresCrossTenantIsNotFound proves the tenancy invariant against a REAL
// database: a connector owned by org A is invisible to an adapter scoped to org B (the WHERE
// organization_id predicate), so Resolve is a typed NotFound — never a cross-tenant leak.
//
//nolint:paralleltest // shares the real-container, serial-by-design discipline.
func TestIntegration_RealPostgresCrossTenantIsNotFound(t *testing.T) {
	pool, orgA := startPostgresWithConnectors(t)
	orgB := seedOrg(t, pool)

	id := uuid.New()
	sealAndInsert(t, pool, orgA, id, integrationCanary) // owned by org A

	// An adapter scoped to org B must not see org A's connector.
	adapterB := realAdapter(t, pool, orgB)
	_, err := adapterB.Resolve(context.Background(), secrets.Ref("eden://connector/"+id.String()))
	if !errors.IsType[secrets.NotFoundError](err) {
		t.Fatalf("cross-tenant Resolve err = %v, want NotFoundError", err)
	}
}

// ── real-Postgres harness (official image, connectors schema, sealed insert, reaped) ────────────.

// realAdapter builds an adapter over the real pgxTransport (scoped to orgID) + a REAL envelope Sealer
// over a fake-sourced 32-byte KEK — the crypto is real; only the KEK bytes are a fixture.
func realAdapter(t *testing.T, pool *pgxpool.Pool, orgID uuid.UUID) *platformconnectoradapter.Adapter {
	t.Helper()
	adapter, err := platformconnectoradapter.New(
		platformconnectoradapter.Config{KEK: secrets.Ref(kekReference), KEKVersion: 1},
		platformconnectoradapter.Deps{
			Loader:  &pgxTransport{pool: pool, organizationID: orgID},
			Secrets: secretstest.New(map[string]string{kekReference: kekPlaintext}),
		},
	)
	if err != nil {
		t.Fatalf("platformconnectoradapter.New: %v", err)
	}
	return adapter
}

// sealAndInsert seals value via the REAL envelope crypto (under the fixture KEK) and inserts the
// connector + its sealed material into the real tables under orgID.
func sealAndInsert(t *testing.T, pool *pgxpool.Pool, orgID, id uuid.UUID, value string) {
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
	ctx := context.Background()
	if _, err := pool.Exec(
		ctx,
		`INSERT INTO connectors (id, organization_id, kind, name, fingerprint) VALUES ($1, $2, 'claude-api', 'integration', $3)`,
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
}

// startPostgresWithConnectors boots a real postgres, creates the minimal connectors schema (the SAME
// shape as the platformgateway migration — connectors + connector_secrets, sans the FK to users/orgs
// tables this lane does not need), and returns the pool + a seeded org id.
func startPostgresWithConnectors(t *testing.T) (*pgxpool.Pool, uuid.UUID) {
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
			fingerprint text NOT NULL
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
	return pool, seedOrg(t, pool)
}

// seedOrg returns a fresh org id (the lane's schema has no organizations table — org ids are just the
// tenancy key the connectors row carries + the transport filters on).
func seedOrg(t *testing.T, _ *pgxpool.Pool) uuid.UUID {
	t.Helper()
	return uuid.New()
}

// startPostgres boots an ephemeral postgres and returns a DSN reachable from the devcontainer (the
// container's docker-bridge IP). Reaped on cleanup.
func startPostgres(t *testing.T) string {
	t.Helper()
	name := "eden-connectoradapter-it-" + strings.ReplaceAll(uuid.NewString(), "-", "")[:12]
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
	dsn := fmt.Sprintf("postgres://postgres:postgres@%s:5432/connectors?sslmode=disable", ip)
	waitReady(t, dsn)
	return dsn
}

// waitReady polls until a pgx connection + ping succeeds or the deadline elapses.
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

// containerIP resolves the container's docker-bridge IP (reachable from the devcontainer).
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

// requireDocker fails (not skips) when docker is absent — in the devcontainer it is guaranteed present,
// so absence is a gate FAILURE, not a skip (ADR-0020 FAIL-NOT-SKIP).
func requireDocker(t *testing.T) {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Fatalf("docker not on PATH — the integration lane requires a real docker daemon (ADR-0020 FAIL-NOT-SKIP): %v", err)
	}
}

// assertNoLeak fails t if the canary appears in any surfaced projection of the resolved Secret.
func assertNoLeak(t *testing.T, sec *secrets.Secret) {
	t.Helper()
	for name, rendered := range redactionSurfaces(t, sec) {
		if strings.Contains(rendered, integrationCanary) {
			t.Fatalf("REAL-Postgres canary leaked through %s: %q", name, rendered)
		}
	}
}
