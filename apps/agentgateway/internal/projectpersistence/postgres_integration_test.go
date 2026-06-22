//go:build integration

package projectpersistence_test

import (
	"context"
	"fmt"
	"os/exec"
	"slices"
	"strconv"
	"strings"
	"testing"
	"time"

	"github.com/jackc/pgx/v5"

	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/eden/apps/agentgateway/internal/projectpersistence"
	"github.com/gophersys/libs/go/errors"
)

// TestIntegration_PostgresProjectStore proves the REAL Postgres ProjectStore against a REAL
// postgres:16-alpine container (no mock): create → get (found + not-found) → list newest-first →
// cursor pagination. It mirrors the orchestrator's real-substrate posture (docker-out-of-docker,
// reaped on cleanup; SKIP without docker locally, REQUIRED in the devcontainer).
func TestIntegration_PostgresProjectStore(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	projectStore, err := projectpersistence.NewPostgres(ctx, dsn)
	if err != nil {
		t.Fatalf("NewPostgres: %v", err)
	}
	defer projectStore.Close()

	// Create three projects in order; their seq (insertion order) drives newest-first listing.
	for index, name := range []string{"alpha-service", "beta-app", "gamma-cli"} {
		if _, createErr := projectStore.Create(ctx, gateway.Project{
			ID:      fmt.Sprintf("project-%02d", index),
			Name:    name,
			Idea:    "build " + name,
			Status:  gateway.ProjectStatusBuilding,
			Product: gateway.ProductConfig{ProductName: name, ProductKind: "service"},
		}); createErr != nil {
			t.Fatalf("Create(%s): %v", name, createErr)
		}
	}

	// Get the middle project round-trips faithfully; a missing id is a typed KindNotFound (404).
	got, err := projectStore.Get(ctx, "project-01")
	if err != nil {
		t.Fatalf("Get(project-01): %v", err)
	}
	if got.Name != "beta-app" || got.Product.ProductName != "beta-app" {
		t.Fatalf("Get round-trip drift: got %+v", got)
	}
	if _, missErr := projectStore.Get(ctx, "project-does-not-exist"); errors.KindOf(missErr) != errors.KindNotFound {
		t.Fatalf("Get(missing) kind: got %v want KindNotFound (err=%v)", errors.KindOf(missErr), missErr)
	}

	// List newest-first returns gamma, beta, alpha (the reverse of insertion), no further page.
	all, err := projectStore.List(ctx, gateway.ProjectFilter{})
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	assertNames(t, "List(all)", all.Projects, "gamma-cli", "beta-app", "alpha-service")
	if all.Next != "" {
		t.Fatalf("List(all) Next: got %q want empty", all.Next)
	}

	// Cursor pagination: a page of 2, then the remainder via the returned cursor.
	first, err := projectStore.List(ctx, gateway.ProjectFilter{Limit: 2})
	if err != nil {
		t.Fatalf("List(limit=2): %v", err)
	}
	assertNames(t, "List(limit=2)", first.Projects, "gamma-cli", "beta-app")
	if first.Next == "" {
		t.Fatalf("List(limit=2) Next: want a cursor, got empty")
	}
	second, err := projectStore.List(ctx, gateway.ProjectFilter{Limit: 2, Cursor: first.Next})
	if err != nil {
		t.Fatalf("List(cursor): %v", err)
	}
	assertNames(t, "List(cursor)", second.Projects, "alpha-service")
	if second.Next != "" {
		t.Fatalf("List(cursor) Next: got %q want empty (last page)", second.Next)
	}
}

// TestIntegration_PostgresProjectStore_UpdateStatus proves the REAL status-patch path against a REAL
// postgres container: the transactional read-modify-write of the JSONB record walks a draft through
// the saga states, merges the saga scratch (only non-nil fields), re-stamps UpdatedAt from the injected
// clock, rejects an off-contract status (KindInvalid), and 404s a missing id (KindNotFound).
func TestIntegration_PostgresProjectStore_UpdateStatus(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	stamp := time.Date(2026, time.June, 22, 10, 0, 0, 0, time.UTC)
	projectStore, err := projectpersistence.NewPostgres(ctx, dsn, projectpersistence.WithClock(fixedClock{at: stamp}))
	if err != nil {
		t.Fatalf("NewPostgres: %v", err)
	}
	defer projectStore.Close()

	if _, err = projectStore.Create(ctx, gateway.Project{
		ID: "project-saga", Name: "saga-app", Status: gateway.ProjectStatusDraft,
		Product:   gateway.ProductConfig{ProductName: "saga-app", ProductKind: "service"},
		CreatedAt: time.Date(2026, time.June, 22, 8, 0, 0, 0, time.UTC),
	}); err != nil {
		t.Fatalf("Create: %v", err)
	}

	// Patch the saga forward: status + repo coordinates + saga step; Name (a nil field) is preserved.
	advancing := gateway.ProjectStatusProvisioningRepo
	owner := "gophersys"
	patched, err := projectStore.UpdateStatus(ctx, "project-saga", gateway.ProjectStatusPatch{
		Status:      &advancing,
		GitHubOwner: &owner,
		SagaStep:    ptr("provision-repo"),
	})
	if err != nil {
		t.Fatalf("UpdateStatus: %v", err)
	}
	if patched.Status != gateway.ProjectStatusProvisioningRepo || patched.GitHubOwner != owner || patched.Name != "saga-app" {
		t.Fatalf("patched project drift: %+v", patched)
	}
	if !patched.UpdatedAt.Equal(stamp) {
		t.Fatalf("UpdatedAt = %v, want re-stamped %v", patched.UpdatedAt, stamp)
	}

	// The patch is durable (a fresh Get observes it across the JSONB round-trip).
	reread, err := projectStore.Get(ctx, "project-saga")
	if err != nil || reread.Status != gateway.ProjectStatusProvisioningRepo || reread.GitHubOwner != owner {
		t.Fatalf("Get after patch: err=%v project=%+v", err, reread)
	}

	// An off-contract status is rejected and never written.
	bogus := "halfway"
	if _, badErr := projectStore.UpdateStatus(ctx, "project-saga", gateway.ProjectStatusPatch{Status: &bogus}); errors.KindOf(badErr) != errors.KindInvalid {
		t.Fatalf("UpdateStatus(off-contract) kind = %v, want invalid", errors.KindOf(badErr))
	}
	// A missing id is a typed KindNotFound.
	if _, missErr := projectStore.UpdateStatus(ctx, "project-nope", gateway.ProjectStatusPatch{SagaStep: ptr("x")}); errors.KindOf(missErr) != errors.KindNotFound {
		t.Fatalf("UpdateStatus(missing) kind = %v, want not-found", errors.KindOf(missErr))
	}
}

// fixedClock is a deterministic gateway.Clock for the patch path's UpdatedAt re-stamp.
type fixedClock struct{ at time.Time }

func (c fixedClock) Now() time.Time { return c.at }

// ptr returns a pointer to s — the patch's "set this field" form.
func ptr(s string) *string { return &s }

// assertNames fails unless the projects' names equal want in order.
func assertNames(t *testing.T, where string, projects []gateway.Project, want ...string) {
	t.Helper()
	got := make([]string, len(projects))
	for i := range projects {
		got[i] = projects[i].Name
	}
	if !slices.Equal(got, want) {
		t.Fatalf("%s: names = %v, want %v", where, got, want)
	}
}

// startPostgres boots a REAL postgres:16-alpine container docker-out-of-docker, reaped on cleanup
// under a unique name, returning a DSN reachable over the container's docker-bridge IP (the
// devcontainer shares the docker network). SKIPS when docker is unavailable; REQUIRED in the
// devcontainer.
func startPostgres(t *testing.T) string {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH: the real-postgres ProjectStore arm is skipped")
	}
	name := "eden-projectpersistence-pg-" + strconv.FormatInt(time.Now().UnixNano(), 36)
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
