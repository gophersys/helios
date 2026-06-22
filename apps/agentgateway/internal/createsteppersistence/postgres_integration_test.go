//go:build integration

package createsteppersistence_test

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

	"github.com/gophersys/eden/apps/agentgateway/internal/createsteppersistence"
	"github.com/gophersys/eden/apps/agentgateway/internal/gateway"
	"github.com/gophersys/libs/go/errors"
)

// TestIntegration_PostgresCreateStepStore proves the REAL create-saga ledger against a REAL
// postgres:16-alpine container (no mock): idempotent Record on (project_id, step), Advance to a
// terminal status with its JSONB output, the not-found/invalid fault arms, and StartedAt-ordered List.
// Mirrors the project persistence's real-substrate posture (docker-out-of-docker, reaped on cleanup; SKIP
// without docker locally, REQUIRED in the devcontainer). One container; the ordered phases run as named
// steps (a saga ledger IS state-dependent, so the phases cannot be parallelized).
func TestIntegration_PostgresCreateStepStore(t *testing.T) {
	t.Parallel()
	dsn := startPostgres(t)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	stamp := time.Date(2026, time.June, 22, 11, 0, 0, 0, time.UTC)
	ledger, err := createsteppersistence.NewPostgres(ctx, dsn, createsteppersistence.WithClock(fixedClock{at: stamp}))
	if err != nil {
		t.Fatalf("NewPostgres: %v", err)
	}
	defer ledger.Close()

	assertRecordIsIdempotent(ctx, t, ledger, stamp)
	assertAdvanceStoresOutputDurably(ctx, t, ledger)
	assertFaultArms(ctx, t, ledger)
	assertListScopesByProjectInOrder(ctx, t, ledger)
}

// assertRecordIsIdempotent records a step, then replays it with a different key and proves the first
// record wins (the (project_id, step) idempotency key).
func assertRecordIsIdempotent(ctx context.Context, t *testing.T, ledger *createsteppersistence.PostgresCreateStepStore, stamp time.Time) {
	t.Helper()
	first, err := ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-aa", Step: "provision-repo", IdempotencyKey: "key-1"})
	if err != nil {
		t.Fatalf("Record: %v", err)
	}
	if first.Status != gateway.CreateStepStatusPending || !first.StartedAt.Equal(stamp) || !first.FinishedAt.IsZero() {
		t.Fatalf("recorded step shape: %+v", first)
	}
	replay, err := ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-aa", Step: "provision-repo", IdempotencyKey: "key-2"})
	if err != nil {
		t.Fatalf("Record replay: %v", err)
	}
	if replay.IdempotencyKey != "key-1" {
		t.Fatalf("replay changed the idempotency key: got %q want key-1", replay.IdempotencyKey)
	}
}

// assertAdvanceStoresOutputDurably advances the recorded step to DONE with a JSONB output and proves
// it round-trips on a fresh Get.
func assertAdvanceStoresOutputDurably(ctx context.Context, t *testing.T, ledger *createsteppersistence.PostgresCreateStepStore) {
	t.Helper()
	output := gateway.RawJSON(`{"repoNodeId":"R_123"}`)
	done, err := ledger.Advance(ctx, "project-aa", "provision-repo", gateway.CreateStepStatusDone, output)
	if err != nil {
		t.Fatalf("Advance: %v", err)
	}
	// JSONB is value-preserving, not byte-preserving (it may re-space keys), so compare the JSON value.
	if done.Status != gateway.CreateStepStatusDone || done.FinishedAt.IsZero() || !sameJSON(t, done.Output, output) {
		t.Fatalf("advanced step drift: %+v", done)
	}
	got, err := ledger.Get(ctx, "project-aa", "provision-repo")
	if err != nil || !sameJSON(t, got.Output, output) {
		t.Fatalf("Get after advance: err=%v output=%s", err, got.Output)
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

// assertFaultArms proves the typed fault paths: a non-terminal Advance is invalid; an unrecorded step
// (Advance or Get) is not-found.
func assertFaultArms(ctx context.Context, t *testing.T, ledger *createsteppersistence.PostgresCreateStepStore) {
	t.Helper()
	if _, err := ledger.Advance(ctx, "project-aa", "provision-repo", gateway.CreateStepStatusPending, nil); errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("Advance(pending) kind = %v, want invalid", errors.KindOf(err))
	}
	if _, err := ledger.Advance(ctx, "project-aa", "seed-template", gateway.CreateStepStatusDone, nil); errors.KindOf(err) != errors.KindNotFound {
		t.Fatalf("Advance(missing) kind = %v, want not-found", errors.KindOf(err))
	}
	if _, err := ledger.Get(ctx, "project-aa", "nope"); errors.KindOf(err) != errors.KindNotFound {
		t.Fatalf("Get(missing) kind = %v, want not-found", errors.KindOf(err))
	}
}

// assertListScopesByProjectInOrder records two more steps (one for another project) and proves List
// returns project-aa's steps in record order, scoped to that project.
func assertListScopesByProjectInOrder(ctx context.Context, t *testing.T, ledger *createsteppersistence.PostgresCreateStepStore) {
	t.Helper()
	if _, err := ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-aa", Step: "seed-template", IdempotencyKey: "key-3"}); err != nil {
		t.Fatalf("Record second step: %v", err)
	}
	if _, err := ledger.Record(ctx, gateway.CreateStep{ProjectID: "project-zz", Step: "provision-repo", IdempotencyKey: "key-9"}); err != nil {
		t.Fatalf("Record other project: %v", err)
	}
	steps, err := ledger.List(ctx, "project-aa")
	if err != nil {
		t.Fatalf("List: %v", err)
	}
	if len(steps) != 2 || steps[0].Step != "provision-repo" || steps[1].Step != "seed-template" {
		t.Fatalf("List(project-aa) drift: %+v", steps)
	}
}

// fixedClock is a deterministic gateway.Clock for the ledger's StartedAt/FinishedAt stamps.
type fixedClock struct{ at time.Time }

func (c fixedClock) Now() time.Time { return c.at }

// startPostgres boots a REAL postgres:16-alpine container docker-out-of-docker, reaped on cleanup
// under a unique name, returning a DSN reachable over the container's docker-bridge IP. SKIPS when
// docker is unavailable; REQUIRED in the devcontainer.
func startPostgres(t *testing.T) string {
	t.Helper()
	if _, err := exec.LookPath("docker"); err != nil {
		t.Skip("docker CLI not on PATH: the real-postgres CreateStepStore arm is skipped")
	}
	name := "eden-createsteppersistence-pg-" + strconv.FormatInt(time.Now().UnixNano(), 36)
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
