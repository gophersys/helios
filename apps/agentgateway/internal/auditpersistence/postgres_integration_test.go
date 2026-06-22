//go:build integration

package auditpersistence_test

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"os/exec"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/gophersys/eden/apps/agentgateway/internal/auditpersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
)

// TestIntegration_PostgresAuditStore proves the REAL append-only audit trail against a REAL
// postgres:16-alpine container (no mock): Append assigns a monotonic seq, the JSONB detail round-trips,
// List is newest-first scoped to one project, and the cursor pages the remainder. Mirrors the project
// store's real-substrate posture (docker-out-of-docker, reaped on cleanup; SKIP without docker locally,
// REQUIRED in the devcontainer).
func TestIntegration_PostgresAuditStore(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	trail, err := auditpersistence.NewPostgres(ctx, dsn)
	if err != nil {
		t.Fatalf("NewPostgres: %v", err)
	}
	defer trail.Close()

	occurred := time.Date(2026, time.June, 22, 12, 0, 0, 0, time.UTC)
	detail := gateway.RawJSON(`{"repoNodeId":"R_42"}`)

	seedAuditEvents(ctx, t, trail, detail, occurred)
	assertScopedCursorPaging(ctx, t, trail, detail)
	assertUnscopedSpansAllProjects(ctx, t, trail)
}

// seedAuditEvents appends three events for project-aa (seq ascending) and one for project-zz, proving
// the first append assigns a seq and round-trips its JSONB detail.
func seedAuditEvents(ctx context.Context, t *testing.T, trail *auditpersistence.PostgresAuditStore, detail gateway.RawJSON, occurred time.Time) {
	t.Helper()
	created, err := trail.Append(ctx, gateway.AuditEvent{
		ProjectID: "project-aa", Action: "project.created", Actor: "system", Detail: detail, OccurredAt: occurred,
	})
	if err != nil {
		t.Fatalf("Append: %v", err)
	}
	if created.Seq == 0 || !sameJSON(t, created.Detail, detail) {
		t.Fatalf("first event drift: %+v", created)
	}
	for _, action := range []string{"saga.step.started", "saga.step.done"} {
		if _, err = trail.Append(ctx, gateway.AuditEvent{ProjectID: "project-aa", Action: action, Actor: "system", OccurredAt: occurred}); err != nil {
			t.Fatalf("Append(%s): %v", action, err)
		}
	}
	if _, err = trail.Append(ctx, gateway.AuditEvent{ProjectID: "project-zz", Action: "project.created", OccurredAt: occurred}); err != nil {
		t.Fatalf("Append(other project): %v", err)
	}
}

// assertScopedCursorPaging proves a project-scoped list is newest-first and pages via the cursor, and
// that the JSONB detail survives the round-trip on a paged-to event.
func assertScopedCursorPaging(ctx context.Context, t *testing.T, trail *auditpersistence.PostgresAuditStore, detail gateway.RawJSON) {
	t.Helper()
	first, err := trail.List(ctx, gateway.AuditFilter{ProjectID: "project-aa", Limit: 2})
	if err != nil {
		t.Fatalf("List(limit=2): %v", err)
	}
	if len(first.Events) != 2 || first.Events[0].Action != "saga.step.done" || first.Next == "" {
		t.Fatalf("List page-1 drift: events=%+v next=%q", first.Events, first.Next)
	}
	second, err := trail.List(ctx, gateway.AuditFilter{ProjectID: "project-aa", Limit: 2, Cursor: first.Next})
	if err != nil {
		t.Fatalf("List(cursor): %v", err)
	}
	if len(second.Events) != 1 || second.Events[0].Action != "project.created" || second.Next != "" {
		t.Fatalf("List page-2 drift: events=%+v next=%q", second.Events, second.Next)
	}
	if !sameJSON(t, second.Events[0].Detail, detail) {
		t.Fatalf("detail not round-tripped: got %s want %s", second.Events[0].Detail, detail)
	}
}

// sameJSON reports whether two JSON documents are the same VALUE (ignoring insignificant whitespace),
// the correct equality for a JSONB column round-trip (Postgres normalizes JSONB, so a byte compare
// would spuriously fail on re-spaced keys).
func sameJSON(t *testing.T, got, want gateway.RawJSON) bool {
	t.Helper()
	var gotCompact, wantCompact bytes.Buffer
	if err := json.Compact(&gotCompact, got); err != nil {
		t.Fatalf("compact got JSON %q: %v", got, err)
	}
	if err := json.Compact(&wantCompact, want); err != nil {
		t.Fatalf("compact want JSON %q: %v", want, err)
	}
	return gotCompact.String() == wantCompact.String()
}

// assertUnscopedSpansAllProjects proves an unscoped list spans both projects (the four seeded events).
func assertUnscopedSpansAllProjects(ctx context.Context, t *testing.T, trail *auditpersistence.PostgresAuditStore) {
	t.Helper()
	all, err := trail.List(ctx, gateway.AuditFilter{})
	if err != nil {
		t.Fatalf("List(all): %v", err)
	}
	if len(all.Events) != 4 {
		t.Fatalf("List(all): got %d events, want 4", len(all.Events))
	}
}

// startPostgres boots a REAL postgres:16-alpine container docker-out-of-docker, reaped on cleanup
// under a unique name, returning a DSN reachable over the container's docker-bridge IP. SKIPS when
// docker is unavailable; REQUIRED in the devcontainer.
func startPostgres(t *testing.T) string {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH: the real-postgres AuditStore arm is skipped")
	}
	name := "eden-auditpersistence-pg-" + strconv.FormatInt(time.Now().UnixNano(), 36)
	// #nosec G204 -- fixed `docker run` of the official postgres image; name is time-derived, not user input.
	run := exec.Command("docker", "run", "-d", "--rm", "--name", name,
		"-e", "POSTGRES_PASSWORD=eden", "-e", "POSTGRES_USER=eden", "-e", "POSTGRES_DB=eden",
		"postgres:16-alpine", "-c", "fsync=off")
	if out, err := run.CombinedOutput(); err != nil {
		t.Skipf("could not start postgres container (image unavailable?): %v\n%s", err, out)
	}
	t.Cleanup(func() {
		// #nosec G204 -- fixed `docker rm -f` of the just-created container by its time-derived name.
		_ = exec.Command("docker", "rm", "-f", name).Run() //nolint:errcheck // best-effort reap.
	})

	// #nosec G204 -- fixed `docker inspect` of the just-created container by its time-derived name.
	out, err := exec.Command("docker", "inspect", "-f",
		"{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}", name).CombinedOutput()
	if err != nil {
		t.Fatalf("docker inspect: %v\n%s", err, out)
	}
	ip := strings.TrimSpace(string(out))
	if ip == "" {
		t.Fatalf("docker inspect returned an empty bridge IP for %s", name)
	}
	dsn := fmt.Sprintf("postgres://eden:eden@%s:5432/eden?sslmode=disable", ip)
	waitForPostgres(t, dsn)
	return dsn
}

// waitForPostgres polls until the container accepts a real connection and a trivial query succeeds.
func waitForPostgres(t *testing.T, dsn string) {
	t.Helper()
	deadline := time.After(45 * time.Second)
	for {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
		ok := pingPostgres(ctx, dsn)
		cancel()
		if ok {
			return
		}
		select {
		case <-deadline:
			t.Fatalf("postgres at %s never became ready", dsn)
		case <-time.After(300 * time.Millisecond):
		}
	}
}

// pingPostgres opens a single connection and runs SELECT 1.
func pingPostgres(ctx context.Context, dsn string) bool {
	conn, err := pgx.Connect(ctx, dsn)
	if err != nil {
		return false
	}
	defer func() { _ = conn.Close(ctx) }() //nolint:errcheck // best-effort close of the probe conn.
	var one int
	if qerr := conn.QueryRow(ctx, "SELECT 1").Scan(&one); qerr != nil {
		return false
	}
	return one == 1
}
